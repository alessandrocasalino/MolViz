import bpy
import bmesh
import math
import random
from bpy_extras.io_utils import ImportHelper, ExportHelper

class MolViz_AtomProperties(bpy.types.PropertyGroup):
    id: bpy.props.IntProperty(default = -1)
    element: bpy.props.StringProperty(default = "")

bpy.utils.register_class(MolViz_AtomProperties)
bpy.types.Object.MolViz_AtomProperties = bpy.props.PointerProperty(type = MolViz_AtomProperties)

class MolViz_BondProperties(bpy.types.PropertyGroup):
    id: bpy.props.IntProperty(default = -1)
    source: bpy.props.PointerProperty(type = bpy.types.Object)
    target: bpy.props.PointerProperty(type = bpy.types.Object)

bpy.utils.register_class(MolViz_BondProperties)
bpy.types.Object.MolViz_BondProperties = bpy.props.PointerProperty(type = MolViz_BondProperties)

class MolViz_Atom(bpy.types.PropertyGroup):
    atom: bpy.props.PointerProperty(type = bpy.types.Object)
bpy.utils.register_class(MolViz_Atom)

class MolViz_Bond(bpy.types.PropertyGroup):
    bond: bpy.props.PointerProperty(type = bpy.types.Object)
bpy.utils.register_class(MolViz_Bond)

class MolViz_ElementMaterial(bpy.types.PropertyGroup):
    element: bpy.props.StringProperty(default = "")
    material: bpy.props.PointerProperty(type = bpy.types.Material)
bpy.utils.register_class(MolViz_ElementMaterial)

def molviz_add_atom(collection, obj):
    
    for el in collection:
        if el.atom == obj:
            return False
    
    add_item = collection.add()
    add_item.atom = obj
    
    return True

def molviz_add_element_material(collection, elmat):
    
    for el in collection:
        if el.element == elmat[0]:
            return False
    
    add_item = collection.add()
    add_item.element = elmat[0]
    add_item.material = elmat[1]
    
    return True

# Class with all general settings variables
class MolViz_MoleculeProperties(bpy.types.PropertyGroup):
    
    # Atom/bond Properties
    atoms: bpy.props.CollectionProperty(type = MolViz_Atom)
    bonds: bpy.props.CollectionProperty(type = MolViz_Bond)
    element_materials: bpy.props.CollectionProperty(type = MolViz_ElementMaterial)
    
    # Internal Properties
    change_name: bpy.props.BoolProperty(default = False,
                        description = "Rename the Molecule")

bpy.utils.register_class(MolViz_MoleculeProperties)
bpy.types.Object.MolViz_MoleculeProperties = bpy.props.PointerProperty(type = MolViz_MoleculeProperties)

# Operator to open file
class MoleculeVisualizer_FileBrowser(bpy.types.Operator, ImportHelper):
    bl_idname = "molviz.file_browser"
    bl_label = "Select file"

    def create_atom (self, parent, location = (0.,0.,0.) , r = 0.2):
        # Create an empty mesh and the object.
        mesh = bpy.data.meshes.new('Basic_Sphere')
        basic_sphere = bpy.data.objects.new("Basic_Sphere", mesh)

        # Add the object into the scene.
        bpy.context.collection.objects.link(basic_sphere)

        # Select the newly created object
        bpy.context.view_layer.objects.active = basic_sphere
        basic_sphere.select_set(True)

        # Construct the bmesh sphere and assign it to the blender mesh.
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
        bm.to_mesh(mesh)
        bm.free()
        bpy.ops.object.shade_smooth()
        
        basic_sphere.location = location
        basic_sphere.parent = parent
        
        return basic_sphere
    
    def create_bond (self, parent, source, target, r = 0.08):
        
        x1, y1, z1 = source
        x2, y2, z2 = target
        
        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1    
        
        dist = math.sqrt(dx**2 + dy**2 + dz**2)
        
        bpy.ops.mesh.primitive_cylinder_add(
            radius = r, 
            depth = dist,
            location = (dx/2 + x1, dy/2 + y1, dz/2 + z1)   
        )
        
        phi = math.atan2(dy, dx)
        theta = math.acos(dz/dist)
        
        cylinder = bpy.context.object
        
        cylinder.rotation_euler[1] = theta 
        cylinder.rotation_euler[2] = phi
        
        cylinder.parent = parent
        
        return cylinder
    
    def find_atom_from_id (self, collection, id):
        
        for a in collection:
            if a.atom.MolViz_AtomProperties.id == id:
                return a.atom
        
        return None
    
    def find_material_from_element (self, collection, element):
        
        for a in collection:
            if a.element == element:
                return a.material
        
        return None

    def check_element_and_assign_material (self, mol, obj):
        
        element_materials = mol.MolViz_MoleculeProperties.element_materials
        elements_already_added = [x.element for x in element_materials]
        element = obj.MolViz_AtomProperties.element
        
        if not element in elements_already_added:
            # Create new material with random colors
            mat = bpy.data.materials.new(name=element)
            # Assign it to object
            obj.data.materials.append(mat)
            mat.use_nodes = True
            mat.node_tree.nodes["Principled BSDF"].inputs[0].default_value = (random.random(), random.random(), random.random(), 1.)
            
            molviz_add_element_material(mol.MolViz_MoleculeProperties.element_materials,
                                        (element, mat) )
        else:
            # Gather the material from another atom
            mat = self.find_material_from_element(mol.MolViz_MoleculeProperties.element_materials,
                                        element)
            obj.data.materials.append(mat)
            
        return

    def execute(self, context):
        
        try:
            filepath = self.properties.filepath
            print("filepath=", filepath)
            f = open(filepath, "r")
        except:
            self.report({'ERROR'}, 'MolViz - Can not find filepath.')
            return {'FINISHED'}
        
        # Explore the file
        lines = f.readlines()
        
        num_mol = 0
        for line in lines:
            if "@<TRIPOS>MOLECULE" in line:
                num_mol = num_mol + 1
        print("MolViz - Found " + str(num_mol) + " molecules")
        
        if not num_mol:
            self.report({'WARNING'}, 'MolViz - No mol2 compatible molecule found.')
            return {'FINISHED'}
        
        starting_line = 0
        for i in range(num_mol):
            
            # Create main empty
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.,0.,0.))
            empty = bpy.context.view_layer.objects.active
            empty.empty_display_size = 20
            empty.name = "Molecule"
            
            atoms = False
            bonds = False
            for j, line in enumerate(lines[starting_line:]):
                sline = line.strip()
                if "@<TRIPOS>MOLECULE" in sline and bonds:
                    starting_line = starting_line + j
                    break
                if "@<TRIPOS>ATOM" in sline:
                    atoms = True
                    continue
                if "@<TRIPOS>BOND" in sline:
                    atoms = False
                    bonds = True
                    continue
                if atoms:
                    cline = sline.split()
                    if len(cline) >= 5:
                        location = ( float(cline[2]), float(cline[3]), float(cline[4]) )
                        atom = self.create_atom(empty, location)
                        atom.MolViz_AtomProperties.id = int(cline[0])
                        atom.MolViz_AtomProperties.element = cline[1]
                        atom.name = atom.MolViz_AtomProperties.element
                        molviz_add_atom(empty.MolViz_MoleculeProperties.atoms, atom)
                        self.check_element_and_assign_material(empty, atom)
                if bonds:
                    cline = sline.split()
                    source = self.find_atom_from_id(empty.MolViz_MoleculeProperties.atoms, int(cline[1]) )
                    target = self.find_atom_from_id(empty.MolViz_MoleculeProperties.atoms, int(cline[2]) )
                    
                    bond = self.create_bond(empty, source.location, target.location)
                    bond.MolViz_BondProperties.source = source
                    bond.MolViz_BondProperties.target = target
                    bond.MolViz_BondProperties.id = int(cline[0])
                    bond.name = "Bond"
            
        
        self.report({'INFO'}, 'MolViz - Molecule created.')
        
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)  
        return {'RUNNING_MODAL'}

class MainPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Molviz"
    
    
class PANEL_PT_MoleculeVisualizer_Input(MainPanel, bpy.types.Panel):
    bl_idname = "PANEL_PT_MoleculeVisualizer_Input"
    bl_label = "Input"
    bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):
        return True
    
    def draw(self, context):
        
        layout = self.layout
        
        layout.operator(MoleculeVisualizer_FileBrowser.bl_idname, text='', icon='FILE')

class PANEL_PT_MoleculeVisualizer_List(MainPanel, bpy.types.Panel):
    bl_idname = "PANEL_PT_MoleculeVisualizer_List"
    bl_label = "Molecules"
    bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):
        for mol in [x for x in bpy.data.objects if x.type == "EMPTY" and len(x.MolViz_MoleculeProperties.atoms)]:
            return True
        return False
    
    def draw(self, context):
        
        layout = self.layout
        
        for mol in [x for x in bpy.data.objects if x.type == "EMPTY" and len(x.MolViz_MoleculeProperties.atoms)]:
            box = layout.box()
            row = box.row()
            if mol.MolViz_MoleculeProperties.change_name:
                row.label(text="", icon = "OUTLINER_DATA_MESH")
                row.prop(mol, "name", text="")
            else:
                row.label(text=mol.name, icon = "OUTLINER_DATA_MESH")
            row.prop(mol.MolViz_MoleculeProperties, "change_name", text="", icon="OUTLINER_DATA_GP_LAYER")
            
            valid_elements = [x for x in mol.MolViz_MoleculeProperties.element_materials if x.material.node_tree.nodes["Principled BSDF"] ]
            if valid_elements:
                box = box.box()
                box.label(text="Colors", icon = "COLOR")
                for el in valid_elements:
                    row = box.row()
                    row.label(text=el.element)
                    row.scale_x = 2
                    mat = el.material
                    row.prop(mat.node_tree.nodes["Principled BSDF"].inputs[0], "default_value", text="")

# Register

classes = (
    # Input operators
    MoleculeVisualizer_FileBrowser,
    # Panel classes
    PANEL_PT_MoleculeVisualizer_Input,
    PANEL_PT_MoleculeVisualizer_List
)

def register():
    
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

def unregister():
    
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

if __name__ == "__main__":
    register()