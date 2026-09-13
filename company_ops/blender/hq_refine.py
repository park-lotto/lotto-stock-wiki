"""Visual correction after examining first renders; retain v1 on disk."""
import bpy
import math
import random
from mathutils import Vector
from pathlib import Path

s=bpy.data.scenes['ML_HQ_A_v1']
bpy.context.window.scene=s
random.seed(72)
def box(name,loc,size,mat):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([(x*size[0]/2,y*size[1]/2,z*size[2]/2) for x,y,z in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]],[],[(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)])
    mesh.materials.append(bpy.data.materials[mat])
    o=bpy.data.objects.new(name,mesh)
    s.collection.objects.link(o)
    o.location=loc
    b=o.modifiers.new('Fine bevel','BEVEL'); b.width=.025;b.segments=2
    return o

# Replace temporary polygon crowns with individually oriented leaf sprays.
for crown in list(s.objects):
    if not crown.name.startswith('HQ_Foliage'):
        continue
    crown.hide_render=True
    crown.hide_viewport=True
    vertices=[];faces=[]
    for i in range(95):
        u=random.uniform(-1,1);a=random.uniform(0,math.tau)
        r=random.random()**.33
        p=Vector((math.sqrt(1-u*u)*math.cos(a),math.sqrt(1-u*u)*math.sin(a),u))*r
        p=Vector((p.x*crown.scale.x,p.y*crown.scale.y,p.z*crown.scale.z))
        length=random.uniform(.09,.20)
        direction=Vector((random.uniform(-1,1),random.uniform(-1,1),random.uniform(-.3,.8))).normalized()
        side=direction.cross(Vector((0,0,1))).normalized()*length*.38
        tip=direction*length
        start=len(vertices)
        vertices.extend([tuple(p-tip),tuple(p+side),tuple(p+Vector((0,0,.025))),tuple(p-side),tuple(p+tip)])
        faces.extend([(start,start+1,start+2),(start,start+2,start+3),(start+1,start+4,start+2),(start+2,start+4,start+3)])
    mesh=bpy.data.meshes.new('HQ_LeafSpray');mesh.from_pydata(vertices,[],faces)
    for j in range(4):mesh.materials.append(bpy.data.materials['HQ_Leaf'+str(j)])
    for polygon in mesh.polygons:polygon.material_index=random.randrange(4)
    o=bpy.data.objects.new('HQ_DetailedPlanting',mesh);s.collection.objects.link(o);o.location=crown.location

# Close atrium, furnish upper rooms and improve stone facade articulation.
box('HQ_AtriumRoof',(0,1,14.1),(18,18,.3),'HQ_PaleStone')
box('HQ_AtriumBackUpper',(0,9.7,13),(18,.45,2),'HQ_Limestone')
for x in [-8.95,8.95]:
    box('HQ_AtriumSideEnclosure',(x,1,7.5),(.18,16,13.2),'HQ_ClearGlass')
for o in s.objects:
    if o.name.startswith('HQ_WingStonePier'):
        o.scale.x=1.75
    if o.name.startswith('HQ_Pendant') and o.type=='MESH':
        o.location.z=9.5
        if o.name.startswith('HQ_PendantCable'):
            o.location.z=10.75
            o.scale.z=.625
for o in list(s.objects):
    if o.name.startswith('HQ_OfficeDesk'):
        for dx in [-.95,.95]:
            box('HQ_DeskLeg',(o.location.x+dx,o.location.y,o.location.z-.43),(.09,.75,.8),'HQ_Graphite')
    if o.name.startswith('HQ_OfficeChair'):
        box('HQ_ChairBack',(o.location.x,o.location.y-.3,o.location.z+.35),(.64,.1,.65),'HQ_Graphite')
        box('HQ_ChairPedestal',(o.location.x,o.location.y,o.location.z-.22),(.1,.1,.45),'HQ_BrushedBronze')
        box('HQ_ChairBase',(o.location.x,o.location.y,o.location.z-.44),(.55,.55,.06),'HQ_Graphite')
for level,w,cy in [(0,17,2),(1,12,3.5)]:
    z=14.7+level*3.9
    for x in [-3,3]:
        box('HQ_UpperDesk',(x,cy,z+.8),(2.5,1,.14),'HQ_Walnut')
        box('HQ_UpperMonitor',(x,cy+.3,z+1.2),(.8,.08,.5),'HQ_Graphite')
for cx in [-14.4,14.4]:
    for z in [4.85,9.15,13.45]:
        box('HQ_FacadeSpandrel',(cx,-7.4,z),(10.3,.16,.52),'HQ_Graphite')
    for dx in [-5.5,5.5]:
        for z in range(1,14):
            box('HQ_StoneJoint',(cx+dx,-7.836,z),(1.2,.012,.018),'HQ_BrushedBronze')
    # Roof perimeter rather than an empty bare roof plate.
    for y in [0,5]:
        box('HQ_RoofGardenBed',(cx,y,13.98),(8.5,2.4,.25),'HQ_Soil')
    box('HQ_RoofBench',(cx,2.5,14.3),(5,.7,.4),'HQ_Walnut')
s.objects['HQ_LobbyBrand'].location=(0,9.42,3.5)
s.objects['HQ_LobbyBrand'].data.size=.62
s.objects['HQ_LobbySubtitle'].location.z=2.95
s.objects['HQ_Ground'].scale=(12,12,1)

def color(name,c):
    m=bpy.data.materials[name]
    m.diffuse_color=(*c,1)
    m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*c,1)
color('HQ_PaleStone',(.43,.38,.29))
color('HQ_Limestone',(.31,.26,.19))
color('HQ_Grass',(.028,.067,.017))
color('HQ_Travertine',(.28,.25,.20))
color('HQ_ClearGlass',(.91,.96,.97))
s.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.16
s.view_settings.look='AgX - Medium High Contrast'
s.view_settings.exposure=-.65
s.objects['HQ_CameraHero'].location=(33,-74,28)
s.objects['HQ_CameraHero'].rotation_euler=(Vector((0,0,9))-s.objects['HQ_CameraHero'].location).to_track_quat('-Z','Y').to_euler()
s.objects['HQ_CameraHero'].data.lens=48
for o in s.objects:
    if o.type=='LIGHT' and o.name.startswith('HQ_FacadeUplight'):o.data.energy=500
for x in [-14,14]:
    d=bpy.data.lights.new('HQ_RoofWarmWash','AREA');d.energy=450;d.color=(1,.67,.35);d.shape='DISK';d.size=5
    o=bpy.data.objects.new('HQ_RoofWarmWash',d);s.collection.objects.link(o);o.location=(x,-6,17)
    o.rotation_euler=(Vector((x,0,13.8))-o.location).to_track_quat('-Z','Y').to_euler()
s.camera=s.objects['HQ_CameraHero']
bpy.ops.wm.save_as_mainfile(filepath=str(Path(bpy.data.filepath).with_name('makers-lab-hq-a-v2.blend')))
print('HQ_REFINED',len(s.objects))
