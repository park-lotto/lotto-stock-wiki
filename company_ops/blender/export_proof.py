import bpy

scene = bpy.data.scenes['ML_Connection_Proof']
bpy.context.window.scene = scene
assert len(scene.objects) == 27
assert bpy.data.objects['ML_GlassPane'].type == 'MESH'
bpy.ops.export_scene.gltf(
    filepath=OUTPUT_DIR + '/blender-facade-proof.glb',
    export_format='GLB', use_active_scene=True, export_apply=True,
    export_animations=False, export_cameras=False, export_lights=False,
)
print('GLB_EXPORTED', len(scene.objects))
