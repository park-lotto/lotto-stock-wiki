"""A-reference headquarters: isolated editable architectural scene via MCP."""
import bpy
import math
import random
from mathutils import Vector

assert 'ML_HQ_A_v1' not in bpy.data.scenes, 'Refuse to overwrite an existing HQ'
random.seed(42)
s = bpy.data.scenes.new('ML_HQ_A_v1')
bpy.context.window.scene = s

def material(name, color, metal=0, rough=.45, transmission=0, emission=0):
    m = bpy.data.materials.new('HQ_' + name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    p.inputs['Transmission Weight'].default_value = transmission
    p.inputs['IOR'].default_value = 1.45
    p.inputs['Emission Color'].default_value = (*color, 1)
    p.inputs['Emission Strength'].default_value = emission
    return m

stone = material('Limestone', (.62,.54,.40), rough=.62)
cream = material('PaleStone', (.78,.72,.60), rough=.48)
bronze = material('BrushedBronze', (.29,.17,.065), .8, .27)
dark = material('Graphite', (.025,.035,.037), .45, .32)
glass = material('ClearGlass', (.73,.87,.88), rough=.07, transmission=1)
floor = material('Travertine', (.55,.48,.36), rough=.3)
wood = material('Walnut', (.18,.073,.028), rough=.42)
warm = material('WarmLight', (1,.57,.23), emission=5)
white = material('Letter', (.91,.87,.72), emission=.3)
water = material('Water', (.025,.16,.18), .3, .11, .25)
soil = material('Soil', (.05,.035,.021), rough=.95)
greens = [material('Leaf'+str(i), c, rough=.85) for i,c in enumerate([
    (.09,.18,.035),(.18,.29,.055),(.045,.12,.026),(.27,.34,.075)])]
grass = material('Grass', (.13,.22,.055), rough=.94)
for m in [stone, cream, floor]:
    nodes = m.node_tree.nodes
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 75
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .17
    bump.inputs['Distance'].default_value = .045
    m.node_tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    m.node_tree.links.new(bump.outputs['Normal'], nodes.get('Principled BSDF').inputs['Normal'])

def box(name, loc, size, mat, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if bevel:
        mod = o.modifiers.new('Soft stone edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
    return o

def rod(name, a, b, radius, mat):
    d = Vector(b)-Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=radius, depth=d.length, location=(Vector(a)+Vector(b))/2)
    o = bpy.context.object
    o.name = name
    o.rotation_euler = d.to_track_quat('Z','Y').to_euler()
    o.data.materials.append(mat)
    return o

def light(name, loc, power, size, target, color=(1,.72,.43)):
    d = bpy.data.lights.new(name, 'AREA')
    d.energy = power
    d.shape = 'DISK'
    d.size = size
    d.color = color
    o = bpy.data.objects.new(name, d)
    s.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    return o

font = bpy.data.fonts.load('C:/Windows/Fonts/malgunbd.ttf')
def text(name, body, loc, size, mat):
    c = bpy.data.curves.new(name, 'FONT')
    c.body = body
    c.font = font
    c.align_x = 'CENTER'
    c.size = size
    c.extrude = .012
    o = bpy.data.objects.new(name, c)
    s.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (math.pi/2,0,0)
    o.data.materials.append(mat)
    return o

def foliage(loc, scale, index):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1, location=loc)
    o = bpy.context.object
    o.name = 'HQ_Foliage'
    o.scale = scale
    o.rotation_euler = (random.random(),random.random(),random.random()*3)
    o.data.materials.append(greens[index%4])

def tree(x,y,z,h=3):
    rod('HQ_TreeTrunk',(x,y,z),(x,y,z+h*.78),.065,wood)
    for j in range(7):
        a = j*2.4
        end=(x+math.cos(a)*h*.24,y+math.sin(a)*h*.24,z+h*(.62+j*.043))
        rod('HQ_Branch',(x,y,z+h*.43),end,.025,wood)
        foliage(end,(h*.25,h*.22,h*.28),j)

def planter(x,y,z,w,d,trees=False):
    box('HQ_Planter',(x,y,z+.25),(w,d,.5),stone,.05)
    box('HQ_PlanterSoil',(x,y,z+.51),(w-.16,d-.16,.04),soil)
    for i in range(max(2,int(w*2))):
        foliage((x+random.uniform(-w*.43,w*.43),y+random.uniform(-d*.3,d*.3),z+.72),(.35,.3,.38),i)
    if trees:
        for offset in [-w*.3,w*.3]:
            tree(x+offset,y,z+.52,2.3)

def railing(x,y,z,w):
    box('HQ_TerraceGlass',(x,y,z+.65),(w,.035,1.15),glass)
    box('HQ_RailTop',(x,y,z+1.24),(w,.055,.045),bronze,.015)
    for i in range(int(w/1.5)+1):
        box('HQ_RailPost',(x-w/2+i*w/max(1,int(w/1.5)),y,z+.6),(.045,.06,1.2),bronze)

# Ground and immediate approach only; no other campus buildings.
box('HQ_Ground',(0,0,-.35),(220,220,.4),grass)
box('HQ_Plaza',(0,-3,-.08),(56,43,.25),floor,.08)
for x in range(-27,28,3):
    box('HQ_PavingJoint',(x,-3,.052),(.018,42,.008),stone)
for y in range(-23,19,3):
    box('HQ_PavingJoint',(0,y,.053),(55,.018,.008),stone)
for x in [-20,20]:
    box('HQ_ReflectingPoolRim',(x,-14,.17),(8,13,.35),dark,.09)
    box('HQ_ReflectingPool',(x,-14,.36),(7.6,12.6,.045),water,.03)
    for y in [-19,-13,-7]:
        planter(x+(-5 if x<0 else 5),y,.1,2.2,2.2,True)
for i in range(4):
    box('HQ_EntranceStep',(0,-10.8+i*.55,.09+i*.14),(18-i*.2,1.3,.18+i*.28),cream,.025)

# Two flanking wings, articulated stone piers, real floors and glazing.
def wing(cx):
    for level in range(3):
        z=.7+level*4.3
        box('HQ_WingSlab',(cx,1,z),(11,17,.3),cream,.045)
        box('HQ_WingRear',(cx,9,z+2.1),(11,.3,4.2),stone)
        box('HQ_WingGlazing',(cx,-7.25,z+2.1),(10.6,.045,3.9),glass)
        for dx in [-5.25,-2.65,0,2.65,5.25]:
            box('HQ_WingMullion',(cx+dx,-7.32,z+2.1),(.065,.16,4.05),bronze)
        for dx in [-4.1,0,4.1]:
            box('HQ_OfficeDesk',(cx+dx,-3,z+.95),(2.3,1,.13),wood,.035)
            box('HQ_OfficeScreen',(cx+dx,-2.7,z+1.4),(.8,.07,.46),dark,.025)
            box('HQ_OfficeChair',(cx+dx,-4,z+.65),(.65,.65,.15),dark,.05)
        box('HQ_WingCeilingLight',(cx,-4,z+3.98),(8,.16,.055),warm)
        light('HQ_InteriorLight',(cx,-3,z+3.9),220,5,(cx,-3,z))
    box('HQ_WingRoof',(cx,1,13.6),(11.6,17.6,.4),cream,.065)
    railing(cx,-7.65,13.8,11.3)
    planter(cx,-6.3,13.8,9.5,1.6,True)
    for dx in [-5.5,5.5]:
        box('HQ_WingStonePier',(cx+dx,-7.45,7.1),(.7,.75,13.1),stone,.035)
        box('HQ_PierBronzeInset',(cx+dx,-7.84,7.1),(.065,.025,12.4),bronze)
    # Exterior side elevations also modeled, not a front-only facade.
    outer=cx+(-5.5 if cx<0 else 5.5)
    for y in [-5,-1,3,7]:
        box('HQ_SideWindow',(outer,y,7),(.035,3.7,12.3),glass)
        box('HQ_SidePier',(outer,y+1.9,7),(.55,.32,13),stone,.025)
    for z in [5,9.3]:
        box('HQ_SideBand',(outer,1,z),(.5,17,.3),cream,.02)

wing(-14.4)
wing(14.4)

# Tall central atrium with genuinely open interior.
box('HQ_AtriumFloor',(0,1,.67),(18,18,.3),floor,.025)
box('HQ_AtriumRear',(0,9.7,6.5),(18,.45,12),stone,.025)
for x in [-8.7,8.7]:
    box('HQ_AtriumPier',(x,-7.6,7.5),(1.1,1.5,13.7),cream,.06)
    box('HQ_AtriumInnerFin',(x+(.7 if x<0 else -.7),-7.6,7.4),(.12,1.6,12.8),bronze,.015)
box('HQ_AtriumGlass',(0,-7.12,7.9),(16.2,.04,9.4),glass)
for x in [-7.6,-5.1,-2.55,0,2.55,5.1,7.6]:
    box('HQ_AtriumMullion',(x,-7.18,7.7),(.075,.19,9.8),bronze)
for z in [3.3,7.2,11.2]:
    box('HQ_AtriumTransom',(0,-7.18,z),(16.2,.16,.07),bronze)
box('HQ_MainEntrance',(0,-7.42,2.08),(4.8,.06,2.7),glass)
for x in [-2.4,0,2.4]:
    box('HQ_DoorFrame',(x,-7.5,2.1),(.065,.11,2.8),bronze)
for x in [-.19,.19]:
    box('HQ_DoorHandle',(x,-7.62,2.0),(.035,.09,.62),bronze,.015)
box('HQ_EntryCanopy',(0,-8.4,3.6),(8.6,3.9,.24),bronze,.035)
box('HQ_EntryCanopyLight',(0,-9.8,3.46),(7.8,.08,.025),warm)
box('HQ_SignPanel',(0,-7.6,13),(16.6,.4,2.3),dark,.035)
text('HQ_Sign','메이커스랩',(0,-7.83,12.5),1.12,white)
box('HQ_AtriumCornice',(0,-7.4,14.3),(19,1.1,.38),cream,.05)

# Lobby reception, gallery mezzanine, stair, wall fins and suspended lights.
box('HQ_Reception',(0,4,1.45),(5,1.5,1.25),cream,.12)
box('HQ_ReceptionTop',(0,4,2.1),(5.15,1.65,.13),wood,.04)
box('HQ_ReceptionUnderlight',(0,3.23,.95),(4.7,.035,.09),warm)
text('HQ_LobbyBrand','MAKERS LAB',(0,9.43,5.7),.8,bronze)
text('HQ_LobbySubtitle','IDEAS INTO REALITY',(0,9.42,4.9),.24,bronze)
for x in [-7,-6.5,-6,-5.5,5.5,6,6.5,7]:
    box('HQ_LobbyWallFin',(x,9.3,4),(.12,.3,6.2),wood,.02)
box('HQ_Mezzanine',(0,7,5.1),(17,5,.27),cream,.035)
railing(0,4.48,5.25,16.7)
for i in range(25):
    box('HQ_Stair',(-6.8,-4+i*.34,.85+i*.174),(2.3,.36,.18),cream,.02)
rod('HQ_StairHandrail',(-5.55,-4,1.85),(-5.55,4.3,6.0),.035,bronze)
for x in [-5,0,5]:
    for y in [-1,3]:
        rod('HQ_PendantCable',(x,y,12),(x,y,8),.012,bronze)
        box('HQ_Pendant',(x,y,8),(2.5,.12,.12),warm,.025)
light('HQ_LobbyKey',(0,0,10),1500,8,(0,2,.7))
for x in [-5,5]:
    planter(x,1,.8,1.6,1.6,True)

# Setback upper volumes and planted terraces establish A silhouette.
for level,w,d,cy in [(0,17,12,2),(1,12,8,3.5)]:
    z=14.5+level*3.9
    box('HQ_UpperSlab' if level==0 else 'HQ_TerraceUpper',(0,cy,z),(w+1,d+1,.38),cream,.06)
    box('HQ_UpperRear',(0,cy+d/2,z+1.7),(w,.25,3.4),stone)
    box('HQ_UpperGlass',(0,cy-d/2,z+1.65),(w,.04,3.2),glass)
    for x in [-w/2,w/2]:
        box('HQ_UpperPier',(x,cy,z+1.7),(.5,d,3.4),stone,.035)
    for i in range(int(w/2)+1):
        box('HQ_UpperMullion',(-w/2+i*w/int(w/2),cy-d/2-.06,z+1.65),(.07,.14,3.2),bronze)
    box('HQ_UpperRoof',(0,cy,z+3.45),(w+1,d+1,.35),cream,.05)
    planter(0,cy-d/2+.8,z+3.65,w-1,1.4,True)
    railing(0,cy-d/2-.35,z+3.65,w+.5)
    light('HQ_UpperInterior',(0,cy,z+3),350,6,(0,cy,z))
planter(-6,-5.1,14.5,4,1.6,True)
planter(6,-5.1,14.5,4,1.6,True)
railing(0,-6.2,14.5,17)

for x in [-23,23]:
    for y in [1,7,13]:
        planter(x,y,.1,3,3,True)
for x in [-7,7]:
    planter(x,-15,.1,3,5)
for x in [-19.9,-8.7,8.7,19.9]:
    light('HQ_FacadeUplight',(x,-9,1),130,1,(x,-7,10))
for x in [-11,11]:
    for y in [-20,-15,-10]:
        box('HQ_Bollard',(x,y,.65),(.16,.16,1.2),bronze,.02)
        box('HQ_BollardLight',(x,y,1.21),(.17,.17,.1),warm,.02)

world = bpy.data.worlds.new('HQ_DayWorld')
s.world = world
world.use_nodes = True
nodes = world.node_tree.nodes
sky = nodes.new('ShaderNodeTexSky')
sky.sky_type = 'NISHITA'
sky.sun_elevation = math.radians(32)
sky.sun_rotation = math.radians(145)
sky.altitude = .2
world.node_tree.links.new(sky.outputs['Color'], nodes.get('Background').inputs['Color'])
nodes.get('Background').inputs['Strength'].default_value = .3

def camera(name, loc, target, lens):
    d=bpy.data.cameras.new(name)
    d.lens=lens
    d.clip_end=500
    o=bpy.data.objects.new(name,d)
    s.collection.objects.link(o)
    o.location=loc
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    return o
s.camera=camera('HQ_CameraHero',(43,-66,31),(0,0,8),48)
camera('HQ_CameraEntry',(14,-27,6),(0,-3,7),33)
camera('HQ_CameraLobby',(3,-5.8,2.4),(0,5,4),21)
s.render.engine='CYCLES'
s.cycles.samples=48
s.cycles.use_denoising=True
s.render.resolution_x=1600
s.render.resolution_y=1100
s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG'
s.view_settings.view_transform='AgX'
s.render.filepath=OUTPUT_DIR+'/hq-day.png'
bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_DIR+'/makers-lab-hq-a-v1.blend')
print('HQ_BUILT',len(s.objects),'objects; saved own scene, render pending')
