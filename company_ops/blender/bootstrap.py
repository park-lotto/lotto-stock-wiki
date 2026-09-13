"""Run in a fresh GUI Blender process with the isolated MakersLab profile."""
import os
import bpy
import addon_utils

assert os.environ.get('DISABLE_TELEMETRY') == 'true'
addon_utils.enable('blender_mcp', default_set=True, persistent=True)
prefs = bpy.context.preferences.addons['blender_mcp'].preferences
prefs.telemetry_consent = False
scene = bpy.context.scene
scene.blendermcp_auto_start_server = False
scene.blendermcp_use_polyhaven = False
scene.blendermcp_use_hyper3d = False
scene.blendermcp_use_sketchfab = False
scene.blendermcp_use_hunyuan3d = False
server = bpy.types.blendermcp_server
server.stop()
server.host = '127.0.0.1'
server.port = 9876
server.start()
scene.blendermcp_server_running = server.running
bpy.ops.wm.save_userpref()
print('MAKERSLAB_READY', bpy.app.version_string, server.host, server.port,
      'telemetry', prefs.telemetry_consent, flush=True)
