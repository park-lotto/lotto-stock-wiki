"""Approved material and interior pass on v2; preserve building and cameras."""
import bpy
import math
import random
from pathlib import Path
from mathutils import Vector

s=bpy.data.scenes['ML_HQ_A_v1']
bpy.context.window.scene=s
assert s.get('hq_finish_version') is None, 'Use the unmodified v2 source'
assert Path(bpy.data.filepath).name=='makers-lab-hq-a-v2.blend'
random.seed(341)

def mat(name,color,rough=.45,metal=0):
    m=bpy.data.materials.new('HD_'+name);m.use_nodes=True;m.diffuse_color=(*color,1)
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    return m

def grain(m,colors,scale,bump_strength,bump_distance):
    n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF')
    coord=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY'
    mapping.inputs[1].default_value=scale;l.new(coord.outputs['Generated'],mapping.inputs[0])
    noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=5;noise.inputs['Detail'].default_value=4
    l.new(mapping.outputs[0],noise.inputs['Vector'])
    ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.15;ramp.color_ramp.elements[1].position=.85
    ramp.color_ramp.elements[0].color=(*colors[0],1);ramp.color_ramp.elements[1].color=(*colors[1],1)
    l.new(noise.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs['Color'],p.inputs['Base Color'])
    bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=bump_strength;bump.inputs['Distance'].default_value=bump_distance
    l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs[0],p.inputs['Normal'])

stone=mat('Stone',(.52,.46,.36),.38)
grain(stone,[(.38,.33,.26),(.58,.52,.43)],(2,2,19),.16,.018)
walnut=mat('Walnut',(.11,.045,.023),.34)
grain(walnut,[(.043,.018,.01),(.19,.081,.032)],(1.2,30,3),.13,.008)
fabric=mat('Fabric',(.39,.35,.28),.84)
grain(fabric,[(.29,.27,.23),(.44,.41,.34)],(75,75,75),.27,.007)
teal=mat('TealFabric',(.025,.09,.084),.81)
grain(teal,[(.016,.054,.05),(.04,.11,.105)],(70,70,70),.23,.006)
carpet=mat('Carpet',(.075,.085,.084),.94)
grain(carpet,[(.06,.07,.07),(.13,.14,.135)],(90,90,90),.3,.008)
marble=mat('HonedMarble',(.44,.42,.36),.23)
grain(marble,[(.29,.28,.245),(.55,.53,.47)],(1,2,15),.06,.008)
bronze=mat('Bronze',(.075,.054,.035),.29,.78)
bronze.node_tree.nodes.get('Principled BSDF').inputs['Anisotropic'].default_value=.38
metal=mat('Metal',(.027,.034,.035),.31,.7)
white=mat('Plaster',(.55,.54,.49),.73)
paper=mat('Paper',(.67,.63,.52),.72)
leather=mat('Leather',(.036,.029,.024),.5)
screen=mat('Screen',(.012,.026,.036),.24)
p=screen.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(.027,.07,.09,1);p.inputs['Emission Strength'].default_value=.55
accent=mat('ScreenAccent',(.09,.32,.36),.5)
p=accent.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(.08,.3,.34,1);p.inputs['Emission Strength'].default_value=.35
lamp=mat('Diffuser',(1,.79,.51),.5)
p=lamp.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(1,.78,.5,1);p.inputs['Emission Strength'].default_value=3
glass=bpy.data.materials['HQ_ClearGlass']
p=glass.node_tree.nodes.get('Principled BSDF');p.inputs['Roughness'].default_value=.025;p.inputs['Base Color'].default_value=(.98,.99,1,1)

cube_verts=[(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]
cube_faces=[(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]
def box(name,loc,size,m,bevel=.015):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([(x*size[0]/2,y*size[1]/2,z*size[2]/2) for x,y,z in cube_verts],[],cube_faces)
    mesh.materials.append(m);o=bpy.data.objects.new(name,mesh);s.collection.objects.link(o);o.location=loc
    if bevel:
        b=o.modifiers.new('Machined edges','BEVEL');b.width=bevel;b.segments=3
        o.modifiers.new('Weighted face normals','WEIGHTED_NORMAL')
    return o

def cylinder(name,loc,radius,depth,m):
    count=24
    vertices=[(math.cos(i*math.tau/count)*radius,math.sin(i*math.tau/count)*radius,z*depth/2) for z in [-1,1] for i in range(count)]
    faces=[tuple(reversed(range(count))),tuple(range(count,2*count))]
    faces.extend((i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.materials.append(m)
    for poly in mesh.polygons:
        if len(poly.vertices)==4:poly.use_smooth=True
    o=bpy.data.objects.new(name,mesh);s.collection.objects.link(o);o.location=loc
    return o

def light(name,loc,target,power,size=2,color=(1,.83,.66)):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color
    o=bpy.data.objects.new(name,d);s.collection.objects.link(o);o.location=loc
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    return o

def lettering(name,body,loc,size,m):
    c=bpy.data.curves.new(name,'FONT');c.body=body;c.size=size;c.extrude=.004;c.align_x='CENTER'
    o=bpy.data.objects.new(name,c);s.collection.objects.link(o);o.location=loc;o.rotation_euler.x=math.pi/2;c.materials.append(m)
    return o

def replace_material(old,new):
    for o in s.objects:
        if o.type=='MESH':
            for slot in o.material_slots:
                if slot.material and slot.material.name==old:slot.material=new

replace_material('HQ_PaleStone',stone)
replace_material('HQ_Limestone',stone)
replace_material('HQ_BrushedBronze',bronze)
replace_material('HQ_Travertine',marble)
replace_material('HQ_Walnut',walnut)

# Preserve v2 placeholder furniture in the file, but replace its render geometry.
old_prefixes=('HQ_OfficeDesk','HQ_OfficeScreen','HQ_OfficeChair','HQ_DeskLeg','HQ_ChairBack','HQ_ChairPedestal','HQ_ChairBase','HQ_UpperDesk','HQ_UpperMonitor','HQ_WingCeilingLight')
for o in s.objects:
    if o.name.startswith(old_prefixes):o.hide_render=True;o.hide_viewport=True
    if o.type=='LIGHT' and o.name.startswith('HQ_InteriorLight'):o.data.energy=0
    if o.type=='LIGHT' and o.name.startswith('HQ_FacadeUplight'):o.data.energy=180
    if o.type=='LIGHT' and o.name.startswith('HQ_LobbyKey'):o.data.energy=1100;o.data.color=(1,.86,.71)

def chair(x,y,z,rotation=0,upholstery=leather):
    parts=[]
    parts.append(box('HD_ChairSeat',(x,y,z+.47),(.61,.59,.12),upholstery,.065))
    parts.append(box('HD_ChairBack',(x,y+.26,z+.88),(.59,.12,.68),upholstery,.07))
    for dx in [-.34,.34]:
        parts.append(box('HD_ChairArm',(x+dx,y,z+.69),(.07,.42,.06),metal,.022))
        parts.append(box('HD_ChairArmUpright',(x+dx,y+.12,z+.56),(.04,.04,.26),metal))
    cylinder('HD_ChairGasLift',(x,y,z+.24),.04,.43,metal)
    for a in range(5):
        angle=a*math.tau/5
        o=box('HD_ChairStarBase',(x+math.sin(angle)*.16,y+math.cos(angle)*.16,z+.07),(.055,.37,.045),metal)
        o.rotation_euler.z=-angle
        cylinder('HD_ChairCaster',(x+math.sin(angle)*.32,y+math.cos(angle)*.32,z+.035),.048,.055,metal)
    for o in parts:
        dx=o.location.x-x;dy=o.location.y-y
        o.location.x=x+dx*math.cos(rotation)-dy*math.sin(rotation)
        o.location.y=y+dx*math.sin(rotation)+dy*math.cos(rotation);o.rotation_euler.z=rotation

def workstation(x,y,z):
    box('HD_WorkDesk',(x,y,z+.76),(2.15,.88,.07),walnut,.03)
    for dx in [-.92,.92]:
        box('HD_DeskFrame',(x+dx,y,z+.38),(.045,.7,.74),metal)
    box('HD_CableTray',(x,y+.22,z+.62),(1.7,.2,.13),metal)
    box('HD_MonitorStand',(x,y+.2,z+.93),(.06,.06,.28),metal)
    box('HD_MonitorBase',(x,y+.16,z+.81),(.38,.22,.025),metal)
    box('HD_Monitor',(x,y+.2,z+1.15),(.86,.055,.48),metal,.018)
    box('HD_MonitorDisplay',(x,y+.166,z+1.15),(.8,.007,.42),screen,.003)
    for i in range(7):
        box('HD_DisplayLine',(x-.13,y+.161,z+1.28-i*.036),(.21+random.random()*.25,.003,.009),accent,0)
    box('HD_Keyboard',(x,y-.12,z+.815),(.48,.16,.028),metal,.008)
    for row in range(3):
        for col in range(11):
            box('HD_Key',(x-.20+col*.04,y-.17+row*.047,z+.834),(.029,.031,.006),white,.002)
    box('HD_Mouse',(x+.38,y-.15,z+.83),(.055,.1,.035),metal,.02)
    box('HD_Notebook',(x-.72,y-.05,z+.816),(.29,.39,.035),paper,.006)
    cylinder('HD_Cup',(x+.75,y+.19,z+.86),.046,.12,white)
    cylinder('HD_Coffee',(x+.75,y+.19,z+.922),.038,.002,walnut)
    chair(x,y-1.0,z,math.pi)

def sofa(x,y,z,w=2.7,rotation=0):
    pieces=[]
    pieces.append(box('HD_LoungeSofa',(x,y,z+.27),(w,1,.38),teal,.13))
    pieces.append(box('HD_SofaBack',(x,y+.4,z+.67),(w,.23,.63),teal,.12))
    for dx in [-w/2+.13,w/2-.13]:pieces.append(box('HD_SofaArm',(x+dx,y,z+.54),(.24,.98,.52),teal,.1))
    for dx in [-w*.23,w*.23]:pieces.append(box('HD_SofaCushion',(x+dx,y-.035,z+.52),(w*.42,.72,.17),fabric,.08))
    for o in pieces:
        dx=o.location.x-x;dy=o.location.y-y;o.location=(x+dx*math.cos(rotation)-dy*math.sin(rotation),y+dx*math.sin(rotation)+dy*math.cos(rotation),o.location.z);o.rotation_euler.z=rotation

def shelving(cx,y,z,w=8):
    box('HD_ShelfBack',(cx,y,z+1.75),(w,.12,3.2),walnut)
    for height in [.25,1.0,1.75,2.5,3.3]:box('HD_Shelf',(cx,y-.24,z+height),(w,.52,.07),walnut)
    for dx in [-w/2,-w/4,0,w/4,w/2]:box('HD_ShelfDivider',(cx+dx,y-.24,z+1.75),(.065,.52,3.25),walnut)
    for j in range(4):
        for i in range(7):
            x=cx-w*.43+i*w*.13
            h=random.uniform(.2,.45)
            box('HD_Book',(x,y-.25,z+.29+j*.75+h/2),(.12,.28,h),[paper,teal,leather][(i+j)%3],.004)
    box('HD_ShelfLight',(cx,y-.51,z+3.27),(w-.2,.025,.024),lamp,.002)

# Full-depth interiors: each floor has a ceiling, finish, rear storage and distinct use.
for cx in [-14.4,14.4]:
    for level in range(3):
        z=.86+level*4.3
        box('HD_OfficeCarpet',(cx,0,z+.015),(10.5,15.4,.025),carpet,.004)
        box('HD_OfficeCeiling',(cx,0,z+3.91),(10.4,15.5,.1),white,.005)
        shelving(cx,8.5,z,8)
        box('HD_WallSkirting',(cx,8.17,z+.09),(10.4,.07,.18),metal)
        for y in [-4.5,-.8,3.2]:
            box('HD_CeilingRecess',(cx,y,z+3.835),(7.8,.18,.035),metal,.005)
            box('HD_CeilingDiffuser',(cx,y,z+3.815),(7.6,.06,.018),lamp,.003)
            light('HD_RoomLight',(cx,y,z+3.76),(cx,y,z),160 if level==1 else 240,4)
        for dx in [-4.7,4.7]:
            box('HD_OfficeWallPanel',(cx+dx,5,z+1.6),(.18,6,3.2),walnut)
        if cx<0 and level==1:
            # Conference room with clear partition, detailed seating and screen.
            box('HD_MeetingTable',(cx,-2.4,z+.76),(5.6,1.65,.10),walnut,.12)
            for dx in [-1.8,1.8]:box('HD_MeetingBase',(cx+dx,-2.4,z+.36),(.35,1,.7),metal,.05)
            for dx in [-1.8,0,1.8]:
                chair(cx+dx,-3.8,z,math.pi, fabric);chair(cx+dx,-1.1,z,0,fabric)
                box('HD_MeetingNotepad',(cx+dx,-2.65,z+.83),(.3,.4,.025),paper,.004)
            box('HD_OfficePartition',(cx,1.4,z+1.8),(9.7,.04,3.6),glass,0)
            for dx in [-4.8,-2.4,0,2.4,4.8]:box('HD_PartitionFrame',(cx+dx,1.37,z+1.8),(.045,.07,3.6),metal)
            box('HD_MeetingScreen',(cx,1.30,z+2.05),(2.6,.07,1.35),screen,.035)
            lettering('HD_ConferenceLabel','RESEARCH / STRATEGY',(cx,1.24,z+2.13),.15,white)
        elif cx>0 and level==0:
            box('HD_LoungeRug',(cx,-2.2,z+.04),(8.6,6,.035),fabric,.015)
            sofa(cx-2.4,-2.5,z,2.6,-math.pi/2);sofa(cx+2.4,-2.5,z,2.6,math.pi/2)
            cylinder('HD_CoffeeTable',(cx,-2.4,z+.47),.88,.10,marble)
            cylinder('HD_CoffeePedestal',(cx,-2.4,z+.24),.30,.43,bronze)
            box('HD_LoungeBook',(cx,-2.4,z+.54),(.42,.29,.035),paper)
            cylinder('HD_LoungeVase',(cx+.32,-2.15,z+.65),.08,.22,bronze)
            box('HD_LoungeDivider',(cx,1.4,z+1.25),(9,.22,2.5),walnut)
            lettering('HD_LoungeLabel','MAKERS / COMMONS',(cx,1.26,z+1.6),.27,white)
            for dx in [-4.2,4.2]:
                cylinder('HD_FloorLampBase',(cx+dx,-4.4,z+.05),.22,.06,metal)
                cylinder('HD_FloorLampStem',(cx+dx,-4.4,z+.82),.018,1.5,bronze)
                cylinder('HD_FloorLampShade',(cx+dx,-4.4,z+1.55),.24,.32,fabric)
                light('HD_LoungeLamp',(cx+dx,-4.4,z+1.38),(cx+dx,-4.4,z),35,.5)
        else:
            for dx in [-3.25,0,3.25]:
                workstation(cx+dx,-3.7,z)
                workstation(cx+dx,.3,z)
            for dx in [-1.65,1.65]:box('HD_DeskAcousticDivider',(cx+dx,-1.8,z+.72),(.12,5.6,1.4),fabric,.03)
    # Fine facade edges, shadow reveal and inset bronze soffit strips.
    for level in range(3):
        z=.7+level*4.3
        box('HD_FacadeSoffit',(cx,-7.1,z+3.94),(10,.7,.10),bronze,.015)
        box('HD_FacadeEdgeLight',(cx,-7.38,z+3.87),(9.9,.03,.025),lamp,.003)

# Lobby: honed feature stone, fluted walnut, layered reception, lounge furniture.
s.objects['HQ_Reception'].hide_render=True
s.objects['HQ_ReceptionTop'].hide_render=True
box('HD_ReceptionFeature',(0,4,1.46),(5.7,1.8,1.26),marble,.10)
box('HD_ReceptionWorktop',(0,4.22,2.12),(5.8,1.5,.09),walnut,.025)
box('HD_ReceptionPlinth',(0,4,.90),(5.25,1.53,.17),bronze,.03)
box('HD_ReceptionInlay',(0,3.08,1.37),(5.35,.025,.025),bronze,.004)
for x in [-1.8,1.8]:
    box('HD_ReceptionTerminal',(x,4.35,2.29),(.57,.09,.36),metal,.025)
box('HD_LobbyFeatureWall',(0,9.28,2.9),(7.5,.17,4.0),marble,.03)
for x in [-6.9,-6.65,-6.4,-6.15,-5.9,-5.65,5.65,5.9,6.15,6.4,6.65,6.9]:
    box('HD_LobbyFluting',(x,9.02,2.9),(.10,.24,4.0),walnut,.022)
s.objects['HQ_LobbyBrand'].location.y=9.17
s.objects['HQ_LobbyBrand'].data.materials.clear();s.objects['HQ_LobbyBrand'].data.materials.append(bronze)
s.objects['HQ_LobbySubtitle'].location.y=9.17
light('HD_ReceptionWash',(0,6.1,4.55),(0,9,2.9),240,3)
box('HD_LobbyRug',(3.9,-1,.85),(5.3,4.6,.035),carpet)
sofa(5.1,-1,.87,2.5,math.pi/2)
cylinder('HD_LobbyTable',(3.4,-1,1.3),.65,.1,marble)
cylinder('HD_LobbyTableBase',(3.4,-1,1.06),.2,.4,bronze)
for x in [-7,7]:
    box('HD_CeilingCove',(x,1,13.77),(.09,16,.025),lamp,.004)
    light('HD_AtriumWallWash',(x,1,11),(x,5,4),300,3)

# Upper offices no longer empty display boxes.
for level,cy in [(0,2),(1,3.5)]:
    z=14.73+level*3.9
    box('HD_UpperCarpet',(0,cy,z),(10,6,.035),carpet)
    for x in [-3,3]:workstation(x,cy-1,z+.03)
    shelving(0,cy+3,z,7)

# Rooftop warmth and refined metalwork, without changing silhouette.
for o in s.objects:
    if o.type=='LIGHT':
        o.visible_glossy=False
        if o.name.startswith('HD_RoomLight'):
            o.data.shape='RECTANGLE';o.data.size=7.6;o.data.size_y=.07
        o.data.specular_factor=.15
    if o.name.startswith('HQ_RailTop') or o.name.startswith('HQ_RailPost'):
        o.data.materials.clear();o.data.materials.append(bronze)

for x in [-8.7,8.7]:
    for z in [2,4,6,8,10,12]:
        box('HD_StonePanelReveal',(x,-8.354,z),(1.03,.009,.014),metal,.001)
for o in s.objects:
    if o.name.startswith('HQ_StoneJoint'):
        o.data.materials.clear();o.data.materials.append(metal)
    if o.name.startswith('HQ_RoofGardenBed'):
        o.data.materials.clear();o.data.materials.append(carpet)
    if o.name.startswith('HQ_EntryCanopy') and o.type=='MESH' and not o.name.startswith('HQ_EntryCanopyLight'):
        o.data.materials.clear();o.data.materials.append(bronze)

d=bpy.data.cameras.new('HD_CameraWindow');d.lens=42
o=bpy.data.objects.new('HD_CameraWindow',d);s.collection.objects.link(o);o.location=(22,-19,7.2)
o.rotation_euler=(Vector((13,-1.4,4.4))-o.location).to_track_quat('-Z','Y').to_euler()
s['hq_finish_version']=3
s['hq_render_prefix']='hq-premium'
s['hq_render_detail_camera']='HD_CameraWindow'
s.cycles.samples=96
s.camera=s.objects['HQ_CameraHero']
bpy.ops.wm.save_as_mainfile(filepath=str(Path(bpy.data.filepath).with_name('makers-lab-hq-a-v3.blend')))
print('HQ_PREMIUM_BUILT',len(s.objects))
