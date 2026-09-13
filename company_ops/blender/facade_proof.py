"""One real facade bay: a connection/material proof, NOT the campus design."""
import bpy
import math
from mathutils import Vector

assert 'ML_Connection_Proof' not in bpy.data.scenes, 'Proof already exists; preserve it.'
scene = bpy.data.scenes.new('ML_Connection_Proof')
bpy.context.window.scene = scene
scene.unit_settings.system = 'METRIC'

def material(name, color, rough=.4, metal=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    return m

stone = material('ML_Warm_Limestone', (.64,.55,.4), .65)
bronze = material('ML_Bronze', (.3,.19,.07), .24, .8)
dark = material('ML_Dark_Interior', (.035,.05,.045), .5)
glass = material('ML_Glass', (.82,.93,.96), .08)
glass.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value = 1
glass.node_tree.nodes.get('Principled BSDF').inputs['IOR'].default_value = 1.45
wood = material('ML_Oak', (.24,.115,.045), .4)
ground = material('ML_Paving', (.22,.25,.25), .7)

def box(name, center, dims, mat, bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Crafted edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        obj.modifiers.new('Face normals', 'WEIGHTED_NORMAL')
    return obj

box('ML_Floor', (0,0,-.15), (12,10,.3), ground)
box('ML_Step', (0,-2.6,.1), (7,1,.2), stone)
box('ML_InteriorFloor', (0,0,.2), (6.8,4.5,.2), wood)
box('ML_Rear', (0,2.2,2.6), (6.8,.25,5), dark)
for x in [-3.25,3.25]:
    box('ML_StonePier', (x,0,2.7), (.55,4.7,5.2), stone, .08)
box('ML_StoneHeader', (0,0,5.15), (7,4.7,.65), stone, .07)
box('ML_GlassPane', (0,-2.05,2.65), (5.95,.045,4.45), glass, .006)
for x in [-2.9,-1.45,0,1.45,2.9]:
    box('ML_Mullion', (x,-2.15,2.65), (.065,.17,4.5), bronze, .012)
for z in [.4,2.1,4.9]:
    box('ML_Transom', (0,-2.15,z), (5.9,.17,.055), bronze, .009)
box('ML_Canopy', (0,-2.65,3.8), (3.5,1.6,.15), bronze)
for x in [-1.6,1.6]:
    box('ML_Desk', (x,.1,1.05), (1.8,.85,.09), wood)
    box('ML_DeskPedestal', (x,.1,.65), (.5,.55,.75), bronze)
    box('ML_Monitor', (x,.35,1.4), (.7,.06,.45), dark)

world = bpy.data.worlds.new('ML_Proof_World')
scene.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.3,.42,.6,1)
world.node_tree.nodes['Background'].inputs[1].default_value = .35

def area(name, pos, target, energy, color, size):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = energy
    data.color = color
    data.shape = 'DISK'
    data.size = size
    o = bpy.data.objects.new(name, data)
    scene.collection.objects.link(o)
    o.location = pos
    o.rotation_euler = (Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()

area('ML_SoftSky', (1,-5,10), (0,0,2), 1800, (.8,.9,1), 8)
area('ML_InteriorLight', (0,.5,4.6), (0,0,0), 450, (1,.66,.32), 4)
area('ML_Sunset', (-6,-3,6), (0,0,2), 1600, (1,.76,.49), 5)
camdata = bpy.data.cameras.new('ML_ProofCamera')
camera = bpy.data.objects.new('ML_ProofCamera', camdata)
scene.collection.objects.link(camera)
camera.location = (9,-14,8)
camera.rotation_euler = (Vector((0,0,2.4))-camera.location).to_track_quat('-Z','Y').to_euler()
camdata.type = 'ORTHO'
camdata.ortho_scale = 12
scene.camera = camera
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = 1000
scene.render.resolution_y = 750
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUTPUT_DIR + '/blender-facade-proof.png'
assert len(scene.objects) >= 25
bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_DIR + '/blender-facade-proof.blend')
print('PROOF_SAVED', len(scene.objects))
