"""Render the saved HQ with identical geometry for day/night review."""
import bpy
from pathlib import Path

s=bpy.data.scenes['ML_HQ_A_v1']
bpy.context.window.scene=s
out=Path(bpy.data.filepath).parent
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX'
prefs.get_devices()
for device in prefs.devices:
    device.use=device.type=='OPTIX'
s.cycles.device='GPU'
s.cycles.samples=96 if s.get('hq_finish_version')==3 else 48
prefix=s.get('hq_render_prefix','hq')
shots=[('HQ_CameraHero','day'),('HQ_CameraEntry','entry'),('HQ_CameraLobby','lobby')]
if s.get('hq_render_detail_camera'):
    shots.append((s['hq_render_detail_camera'],'window'))
for camera,label in shots:
    s.camera=s.objects[camera]
    s.view_settings.exposure=.15 if camera=='HQ_CameraLobby' else -.65
    s.render.filepath=str(out/(prefix+'-'+label+'.png'))
    bpy.ops.render.render(write_still=True)
world=s.world
background=world.node_tree.nodes.get('Background')
for link in list(background.inputs['Color'].links):
    world.node_tree.links.remove(link)
background.inputs['Color'].default_value=(.035,.075,.17,1)
background.inputs['Strength'].default_value=.35
s.view_settings.look='AgX - Medium High Contrast'
s.view_settings.exposure=1
s.camera=s.objects['HQ_CameraHero']
s.render.filepath=str(out/(prefix+'-night.png'))
bpy.ops.render.render(write_still=True)
print('HQ_RENDERS_WRITTEN',out)
