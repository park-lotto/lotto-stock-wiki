"""Export v3 geometry plus navigation, leaving the source blend untouched."""
import bpy
import json
from pathlib import Path
from mathutils import Vector

s=bpy.data.scenes['ML_HQ_A_v1'];bpy.context.window.scene=s
assert s.get('hq_finish_version')==3
root=Path(__file__).resolve().parents[1]
out=root/'static'/'hq-walk';out.mkdir(parents=True,exist_ok=True)

def box(name,loc,size,material,parent=None):
    v=[(x*size[0]/2,y*size[1]/2,z*size[2]/2) for x,y,z in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(v,[],[(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)])
    mesh.materials.append(material);o=bpy.data.objects.new(name,mesh);s.collection.objects.link(o);o.location=loc;o.parent=parent
    return o
glass=bpy.data.materials['HQ_ClearGlass'];bronze=bpy.data.materials['HD_Bronze']
for o in list(s.objects):
    if o.name.startswith(('HQ_MainEntrance','HQ_DoorHandle','HQ_AtriumSideEnclosure')) or (o.name.startswith('HQ_DoorFrame') and abs(o.location.x)<.1):
        o.hide_render=True;o.hide_viewport=True

# Architectural glass is cut around actual passageways for ground and mezzanine.
for x in [-8.95,8.95]:
    for ya,yb in [(-7,-3.5),(-1,5),(7.5,9)]:box('Walk_Wall',(x,(ya+yb)/2,7.45),(.18,yb-ya,13.3),glass)
    box('Walk_Wall',(x,-2.25,8.85),(.18,2.5,10.5),glass)
    box('Walk_Wall',(x,6.25,3.0),(.18,2.5,4.5),glass)
    box('Walk_Wall',(x,6.25,11.05),(.18,2.5,6.1),glass)

for side in [-1,1]:
    group=bpy.data.objects.new('Walk_DoorLeft' if side<0 else 'Walk_DoorRight',None);s.collection.objects.link(group)
    group['doorSide']=side
    box('Walk_DoorGlass',(side*1.2,-7.42,2.08),(2.38,.05,2.7),glass,group)
    for x in [side*.04,side*2.38]:box('Walk_DoorFrame',(x,-7.48,2.08),(.055,.09,2.7),bronze,group)
    box('Walk_DoorHandle',(side*.18,-7.56,2.0),(.035,.055,.6),bronze,group)

bpy.context.view_layer.update()
floor_names={'HQ_Ground','HQ_Plaza','HQ_EntranceStep','HQ_AtriumFloor','HQ_WingSlab','HQ_Mezzanine','HQ_Stair','HQ_UpperSlab','HQ_TerraceUpper','HQ_WingRoof'}
solid_names={'HQ_AtriumPier','HQ_WingStonePier','HQ_WingRear','HQ_WingGlazing','HQ_AtriumGlass','HQ_SideWindow','HQ_SidePier','HQ_AtriumRear','HQ_AtriumBackUpper','HQ_UpperRear','HQ_UpperPier','HQ_UpperGlass','HQ_TerraceGlass','HD_WorkDesk','HD_MeetingTable','HD_LoungeSofa','HD_SofaBack','HD_DeskAcousticDivider','HD_OfficeWallPanel','HD_ShelfBack','HD_OfficePartition','HD_ReceptionFeature','HQ_Planter','HQ_ReflectingPoolRim','Walk_Wall'}
floors=[];solids=[]
for o in s.objects:
    if o.type!='MESH' or o.hide_render:continue
    base=o.name.split('.')[0]
    if base not in floor_names|solid_names:continue
    points=[o.matrix_world@Vector(c) for c in o.bound_box]
    points=[(p.x,p.z,-p.y) for p in points]
    entry={'name':o.name,'min':[min(p[i] for p in points) for i in range(3)],'max':[max(p[i] for p in points) for i in range(3)]}
    (floors if base in floor_names else solids).append(entry)
solids.append({'name':'entrance','min':[-2.4,.73,7.36],'max':[2.4,3.43,7.52],'door':True})
assert len(floors)>25 and len(solids)>80
(out/'navigation.json').write_text(json.dumps({'version':1,'source':'makers-lab-hq-a-v3.blend','floors':floors,'solids':solids},ensure_ascii=False),encoding='utf-8')

# The browser supplies lightweight grain maps for procedural Blender materials.
# Retain material identity and PBR constants in glTF, not an unsupported node graph.
for m in bpy.data.materials:
    if m.name.startswith('HD_') and m.use_nodes:
        p=m.node_tree.nodes.get('Principled BSDF')
        if p:
            for link in list(p.inputs['Base Color'].links):m.node_tree.links.remove(link)
            p.inputs['Base Color'].default_value=m.diffuse_color
            for link in list(p.inputs['Normal'].links):m.node_tree.links.remove(link)

bpy.ops.export_scene.gltf(filepath=str(out/'hq-v3.glb'),export_format='GLB',use_active_scene=True,use_renderable=True,use_visible=True,export_apply=True,export_extras=True,export_animations=False,export_cameras=False,export_lights=False,export_yup=True)
print('HQ_WALK_EXPORTED',len(floors),'floors',len(solids),'solids',(out/'hq-v3.glb').stat().st_size,'bytes')
