# Molecule importer from mol2 files for Blender
# Install this as a Blender addon
#
# Made by A. Casalino

import bpy
import bmesh
import math
import random
from bpy_extras.io_utils import ImportHelper, ExportHelper


# Information to enable add-on addition to Blender
bl_info = {
    "name": "MolViz",
    "description": "Simple molecule creator from mol2 file",
    "author": "Alessandro Casalino",
    "version": (0, 0, 3),
    "blender": (4, 0, 0),
    "warning": "",
    "doc_url": "https://github.com/alessandrocasalino/MolViz",
    "category": "Import-Export",
}


# ------------------------------------
#             Properties
# ------------------------------------

# Global Molviz settings
class MolViz_Settings(bpy.types.PropertyGroup):
    # Import settings
    same_colors: bpy.props.BoolProperty(default = True,
                name = "Use Same Colors",
                description = "Use the same color palette for all molecules.\nIf some molecules are already available in the scene, the first molecule colors will be used")
    # Menu settings
    menu_colors: bpy.props.BoolProperty(default = True,
                name = "Show Colors",
                description = "Show color settings in the molecule tab")
    menu_statistics: bpy.props.BoolProperty(default = True,
                name = "Show Statistics",
                description = "Show statistics in the molecule tab")

bpy.utils.register_class(MolViz_Settings)
bpy.types.Scene.MolViz_Settings = bpy.props.PointerProperty(type = MolViz_Settings)

# Single atom properties (on atom object)
class MolViz_AtomProperties(bpy.types.PropertyGroup):
    id: bpy.props.IntProperty(default = -1)
    element: bpy.props.StringProperty(default = "")

bpy.utils.register_class(MolViz_AtomProperties)
bpy.types.Object.MolViz_AtomProperties = bpy.props.PointerProperty(type = MolViz_AtomProperties)

# Single bond properties (on bond object)
class MolViz_BondProperties(bpy.types.PropertyGroup):
    id: bpy.props.IntProperty(default = -1)
    source: bpy.props.PointerProperty(type = bpy.types.Object)
    target: bpy.props.PointerProperty(type = bpy.types.Object)

bpy.utils.register_class(MolViz_BondProperties)
bpy.types.Object.MolViz_BondProperties = bpy.props.PointerProperty(type = MolViz_BondProperties)

# Atom property for atoms list in the molecule properties
class MolViz_Atom(bpy.types.PropertyGroup):
    atom: bpy.props.PointerProperty(type = bpy.types.Object)
bpy.utils.register_class(MolViz_Atom)

# Bond property for bonds list in the molecule properties
class MolViz_Bond(bpy.types.PropertyGroup):
    bond: bpy.props.PointerProperty(type = bpy.types.Object)
bpy.utils.register_class(MolViz_Bond)

# Pair of element and its associated material
# This is needed to have a list of all elements and their associate material
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

# Molecule properites
# It also contains the list of atoms, bonds and materials associated to elements
class MolViz_MoleculeProperties(bpy.types.PropertyGroup):
    
    # Atom/bond Properties
    atoms: bpy.props.CollectionProperty(type = MolViz_Atom)
    bonds: bpy.props.CollectionProperty(type = MolViz_Bond)
    element_materials: bpy.props.CollectionProperty(type = MolViz_ElementMaterial)
    
    # UI Properties
    change_name: bpy.props.BoolProperty(default = False,
                        name = "Change name",
                        description = "Rename the Molecule")
    collapsed: bpy.props.BoolProperty(default = False,
                        name = "Collapse",
                        description = "Collapse molecule properties")

bpy.utils.register_class(MolViz_MoleculeProperties)
bpy.types.Object.MolViz_MoleculeProperties = bpy.props.PointerProperty(type = MolViz_MoleculeProperties)


# ------------------------------------
#               Import mol2
# ------------------------------------

class MoleculeVisualizer_ImportMolecule(bpy.types.Operator, ImportHelper):
    """Select file (mol2) to import molecule"""
    bl_idname = "molviz.import_molecule"
    bl_label = "Import Molecule"
    bl_options = {"UNDO"}
    
    name: bpy.props.StringProperty(default = "",
                        name = "Name",
                        description = "Name of the molecule")
    
    def lock_transforms (self, obj, location = True, rotation = True, scale = True):
        for i in range(3):
            obj.lock_location[i] = location
            obj.lock_rotation[i] = rotation
            obj.lock_scale[i] = scale
    
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
        
        self.lock_transforms(basic_sphere)
        
        return basic_sphere
    
    # Create a cylinder (bond) between two points
    def create_bond (self, parent, source, target, r = 0.08):
        
        x1, y1, z1 = source
        x2, y2, z2 = target
        
        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1    
        
        dist = math.sqrt(dx**2 + dy**2 + dz**2)
        
        if dist == 0:
            return None
        
        phi = math.atan2(dy, dx)
        theta = math.acos(dz/dist)
        
        bpy.ops.mesh.primitive_cylinder_add(
            radius = r, 
            depth = dist,
            location = (dx/2 + x1, dy/2 + y1, dz/2 + z1)   
        )
        
        cylinder = bpy.context.object
        
        cylinder.rotation_euler[1] = theta 
        cylinder.rotation_euler[2] = phi
        
        cylinder.parent = parent
        
        self.lock_transforms(cylinder)
        
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
    
    # Remove numbers from the element string and enforce string correctness
    def parse_element_string (self, string):
        
        cleaned_string = ''.join([i for i in string if not i.isdigit()])
        first = ''
        second = ''
        
        for ch in cleaned_string:
            if not first and ch.isupper():
                first = ch
            elif first and ch.islower():
                second = ch
                break
        
        return first + second
    
    def list_materials_in_molecule (self, lines):
        
        elements = []
        
        # Loop over the lines to find atoms and bonds
        atoms = False
        for j, line in enumerate(lines):
            sline = line.strip()
            if "@<TRIPOS>ATOM" in sline:
                atoms = True
                continue
            if "@<TRIPOS>BOND" in sline:
                break
            if atoms:
                cline = sline.split()
                element = self.parse_element_string(cline[1])
                if len(cline) >= 5 and not element in elements:
                    elements.append(element)
        
        return elements
    
    def import_materials (self, mol, elements_in_molecule = []):
        
        assert len(mol.MolViz_MoleculeProperties.element_materials) == 0, "Element materials were already added to the molecule"
        
        # Import materials from other molecules
        num_imported = 0
        molecules = [x for x in bpy.data.objects if x.type == "EMPTY" and len(x.MolViz_MoleculeProperties.atoms)]
        for m in molecules:
            element_materials = m.MolViz_MoleculeProperties.element_materials
            valid_elements = [x for x in element_materials if x.material.node_tree.nodes["Principled BSDF"]]
            for el in valid_elements:
                if el.element in elements_in_molecule and not el.element in [x.element for x in mol.MolViz_MoleculeProperties.element_materials]:
                    molviz_add_element_material(mol.MolViz_MoleculeProperties.element_materials,
                                        (el.element, el.material) )
                    num_imported = num_imported + 1
        
        print("MolViz - Imported " + str(num_imported) + " materials from other molecules")
        
        return        
    
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
    
    def clean (self, obj):
        
        if bpy.context.object.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        for child in obj.children:
            bpy.ops.object.select_all(action='DESELECT')
            bpy.data.objects[child.name].select_set(True)
            bpy.ops.object.delete()
        
        bpy.ops.object.select_all(action='DESELECT')
        bpy.data.objects[obj.name].select_set(True)
        bpy.ops.object.delete()
        
        return
    
    def execute(self, context):
        
        settings = bpy.context.scene.MolViz_Settings
        
        try:
            filepath = self.properties.filepath
            print("filepath=", filepath)
            f = open(filepath, "r")
        except:
            self.report({'ERROR'}, 'MolViz - Can not find filepath.')
            return {'FINISHED'}
        
        # Explore the file
        lines = f.readlines()
        
        # Check the number of molecules in the mol2
        num_mol = 0
        for line in lines:
            if "@<TRIPOS>MOLECULE" in line:
                num_mol = num_mol + 1
        print("MolViz - Found " + str(num_mol) + " molecules")
        
        if not num_mol:
            self.report({'WARNING'}, 'MolViz - No mol2 compatible molecule found.')
            return {'FINISHED'}
        
        # Loop over the available molecules
        starting_line = 0
        for i in range(num_mol):
            
            # Create main molecule object (empty)
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0.,0.,0.))
            empty = bpy.context.view_layer.objects.active
            empty.empty_display_size = 20
            empty.name = "Molecule" if len(self.name) == 0 else self.name
            self.lock_transforms(empty, location = False, rotation = False, scale = True)
            
            # Import color palette from other molecules
            if settings.same_colors:
                elements_in_molecule = self.list_materials_in_molecule(lines[starting_line:])
                self.import_materials(empty, elements_in_molecule)
            
            # Loop over the lines to find atoms and bonds
            atoms = False
            bonds = False
            for j, line in enumerate(lines[starting_line:]):
                sline = line.strip()
                # If we already reached the bonds, this line ends the molecule lines
                if "@<TRIPOS>MOLECULE" in sline and bonds:
                    starting_line = starting_line + j
                    break
                # Start the atoms list
                if "@<TRIPOS>ATOM" in sline:
                    atoms = True
                    continue
                # Start the bonds list
                if "@<TRIPOS>BOND" in sline:
                    atoms = False
                    bonds = True
                    continue
                # Create atom
                if atoms:
                    cline = sline.split()
                    if len(cline) >= 5:
                        location = ( float(cline[2]), float(cline[3]), float(cline[4]) )
                        atom = self.create_atom(empty, location)
                        atom.MolViz_AtomProperties.id = int(cline[0])
                        atom.MolViz_AtomProperties.element = self.parse_element_string(cline[1])
                        atom.name = atom.MolViz_AtomProperties.element
                        molviz_add_atom(empty.MolViz_MoleculeProperties.atoms, atom)
                        self.check_element_and_assign_material(empty, atom)
                # Create bond
                if bonds:
                    cline = sline.split()
                    if len(cline) >= 4:
                        source = self.find_atom_from_id(empty.MolViz_MoleculeProperties.atoms, int(cline[1]) )
                        target = self.find_atom_from_id(empty.MolViz_MoleculeProperties.atoms, int(cline[2]) )
                        
                        bond = self.create_bond(empty, source.location, target.location)
                        
                        if bond == None:
                            self.report({'ERROR'}, 'MolViz - mol2 coordinates seems corrupted.')
                            self.clean(empty)
                            return {'FINISHED'}
                        
                        bond.MolViz_BondProperties.source = source
                        bond.MolViz_BondProperties.target = target
                        bond.MolViz_BondProperties.id = int(cline[0])
                        bond.name = "Bond"
            
        
        self.report({'INFO'}, 'MolViz - Molecule created.')
        
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)  
        return {'RUNNING_MODAL'}
    
    def draw(self, context):
        settings = bpy.context.scene.MolViz_Settings
        
        layout = self.layout
        box = layout.box()
        
        box.label(text = "Import Settings", icon = "IMPORT")
        row = box.row()
        row.label(text = "Name:")
        row.scale_x = 1.8
        row.prop(self, 'name', text = "")
        row = box.row()
        row.label(text = "Unified Colors:")
        row.prop(settings, 'same_colors', text = "")

# ------------------------------------
#           Select molecule
# ------------------------------------

class MoleculeVisualizer_SelectMolecule(bpy.types.Operator):
    """Select molecule"""
    bl_idname = "molviz.select_molecule"
    bl_label = "Select Molecule"
    bl_options = {"UNDO"}
    
    mol: bpy.props.StringProperty(default = "")
    
    def execute(self, context):
        
        obj = bpy.data.objects[self.mol]
        
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select object
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        
        return {'FINISHED'}

# ------------------------------------
#               UI Panel
# ------------------------------------

class MainPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Molviz"
    
# Panel to import the file
class PANEL_PT_MoleculeVisualizer_Input(MainPanel, bpy.types.Panel):
    bl_idname = "PANEL_PT_MoleculeVisualizer_Input"
    bl_label = "Input"
    bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):
        return True
    
    def draw(self, context):
        
        settings = context.scene.MolViz_Settings
        
        layout = self.layout
        
        layout.operator(MoleculeVisualizer_ImportMolecule.bl_idname, text='Import mol2', icon='FILE')

# Panel to visualize the list of molecules and their properties
class PANEL_PT_MoleculeVisualizer_List(MainPanel, bpy.types.Panel):
    bl_idname = "PANEL_PT_MoleculeVisualizer_List"
    bl_label = "Molecules"
    bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):
        return len([x for x in bpy.data.objects if x.type == "EMPTY" and len(x.MolViz_MoleculeProperties.atoms)])
    
    def draw(self, context):
        
        layout = self.layout
        
        settings = context.scene.MolViz_Settings
        
        row = layout.row(align=True)
        row.prop(settings, "menu_colors", text="Colors", icon="COLOR")
        row.prop(settings, "menu_statistics", text="Statistics", icon="INFO")
        
        menu_to_draw = settings.menu_colors or settings.menu_statistics
        
        # List the molecules
        molecules = [x for x in bpy.data.objects if x.type == "EMPTY" and len(x.MolViz_MoleculeProperties.atoms)]
        for mol in molecules:
            
            mol_props = mol.MolViz_MoleculeProperties
            
            row = layout.row()
            if menu_to_draw:
                if not mol_props.collapsed:
                    row.prop(mol_props, 'collapsed', text="", icon="TRIA_DOWN", emboss=False)
                else:
                    row.prop(mol_props, 'collapsed', text="", icon="TRIA_RIGHT", emboss=False)
            if mol.MolViz_MoleculeProperties.change_name:
                row.prop(mol, "name", text="")
            else:
                row.label(text=mol.name)
            row2 = row.row(align=True)
            row2.prop(mol_props, "change_name", text="", icon="OUTLINER_DATA_GP_LAYER")
            row2.operator(MoleculeVisualizer_SelectMolecule.bl_idname, text='', icon='RESTRICT_SELECT_OFF').mol = mol.name
            
            if not mol_props.collapsed and menu_to_draw:
                # Check if there are valid elements
                # i.e. elements whose colors can be changed
                box = layout.box()
                valid_elements = [x for x in mol_props.element_materials if x.material.node_tree.nodes["Principled BSDF"] ]
                if valid_elements and settings.menu_colors:
                    box.label(text="Colors", icon = "COLOR")
                    col = box.column()
                    for el in valid_elements:
                        row = col.row()
                        row.label(text=el.element)
                        row.scale_x = 2
                        mat = el.material
                        row.prop(mat.node_tree.nodes["Principled BSDF"].inputs[0], "default_value", text="")
                    if settings.menu_statistics:
                        box.separator()
                
                # Statistics
                if settings.menu_statistics:
                    num_atoms = len([x for x in mol.children if x.MolViz_AtomProperties.id > -1])
                    num_bonds = len([x for x in mol.children if x.MolViz_BondProperties.id > -1])
                    col = box.column()
                    col.label(text="Statistics", icon="INFO")
                    col.label(text="Atoms: " + str(num_atoms), icon = "DOT")
                    col.label(text="Bonds: " + str(num_bonds), icon = "DOT")
                

# Operators and panel registration
classes = (
    # Input operators
    MoleculeVisualizer_ImportMolecule,
    # Molecule operators
    MoleculeVisualizer_SelectMolecule,
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