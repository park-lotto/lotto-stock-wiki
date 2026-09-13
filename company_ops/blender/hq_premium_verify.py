"""Execute against a real Blender scene; visual quality is checked separately."""
import bpy
s=bpy.data.scenes['ML_HQ_A_v1']
assert s.get('hq_finish_version')==3, 'Premium finish has not been built'
for name in ['HD_MeetingTable','HD_LoungeSofa','HD_WorkDesk','HD_OfficePartition','HD_CameraWindow','HD_ReceptionFeature']:
    assert name in s.objects, 'Missing spatial detail: '+name
for name in ['HD_Stone','HD_Walnut','HD_Fabric']:
    m=bpy.data.materials[name]
    assert any(n.type=='BUMP' for n in m.node_tree.nodes), 'Missing microtexture: '+name
assert tuple(round(v,3) for v in s.objects['HQ_CameraHero'].location)==(33,-74,28), 'Comparison camera moved'
assert abs(s.objects['HQ_TerraceUpper'].location.z-18.4)<.01
assert s.objects['HQ_Sign'].data.body=='메이커스랩'
assert 'ML_Connection_Proof' in bpy.data.scenes
print('HQ_PREMIUM_STRUCTURE_VERIFIED',len(s.objects),'objects; still requires visual review')
