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
s.cycles.samples=48
for camera,filename in [('HQ_CameraHero','hq-day.png'),('HQ_CameraEntry','hq-entry.png'),('HQ_CameraLobby','hq-lobby.png')]:
    s.camera=s.objects[camera]
    s.view_settings.exposure=.15 if camera=='HQ_CameraLobby' else -.65
    s.render.filepath=str(out/filename)
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
s.render.filepath=str(out/'hq-night.png')
bpy.ops.render.render(write_still=True)
print('HQ_RENDERS_WRITTEN',out)
