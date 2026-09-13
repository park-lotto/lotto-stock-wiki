"""Run inside Blender, initially RED before the named scene is built."""
import bpy

assert 'ML_HQ_A_v1' in bpy.data.scenes, 'HQ building scene is not built'
s = bpy.data.scenes['ML_HQ_A_v1']
for name in ['HQ_AtriumFloor', 'HQ_Reception', 'HQ_MainEntrance', 'HQ_Sign',
             'HQ_TerraceUpper', 'HQ_CameraHero', 'HQ_CameraEntry', 'HQ_CameraLobby']:
    assert name in s.objects, 'Missing ' + name
assert len([o for o in s.objects if o.type == 'CAMERA']) >= 3
assert s.objects['HQ_MainEntrance'].dimensions.x >= 3
assert s.objects['HQ_TerraceUpper'].location.z > 15
assert len(s.objects) > 200, 'Missing facade/landscape detail'
assert 'ML_Connection_Proof' in bpy.data.scenes, 'Previous proof was not preserved'
print('HQ_STRUCTURE_VERIFIED', len(s.objects), 'Visual acceptance still requires renders')
