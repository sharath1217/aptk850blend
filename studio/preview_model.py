"""Quick 3/4-view preview of a 3D model, for the vision check.
blender -b -P preview_model.py -- <model.glb> <out.png>"""
import bpy, math, sys
from mathutils import Vector

glb, png = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 12; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 768, 432
bpy.ops.import_scene.gltf(filepath=glb)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
c, r = (mn + mx) / 2, (mx - mn).length / 2
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam)
sc.camera = cam; cam.data.lens = 40
cam.location = c + Vector((math.cos(0.7), -math.sin(0.7) * 1.4, 0.45)).normalized() * r * 2.6
cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.45, 0.5, 0.55, 1)
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3
sun.rotation_euler = (math.radians(50), 0, math.radians(30)); sc.collection.objects.link(sun)
sc.render.filepath = png
bpy.ops.render.render(write_still=True)
