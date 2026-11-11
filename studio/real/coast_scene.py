"""Realistic 15 s coastal drive: mountains, ocean, a real car on a cliff road. Rendered with Cycles on a GPU.

  blender -b -P coast_scene.py -- <assets_dir> <out_frames_dir> [preview]

assets_dir may contain (all optional, procedural fallbacks otherwise):
  sky.hdr                             real HDRI sky (Poly Haven, CC0)
  rock_*/grass_*/asphalt_* folders    photo-scanned PBR textures: diff.jpg, nor.jpg, rough.jpg
  car.glb                             real car model (licence-checked by asset_finder)
"""
import bpy, glob, math, os, random, sys
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:]
ASSETS, OUT = argv[0], argv[1]
PREVIEW = len(argv) > 2 and argv[2] == "preview"
FPS, SECONDS = 24, 15
N = FPS * SECONDS
V = 24.0                      # car speed m/s (~86 km/h)
X0 = -150.0                   # car start
rng = random.Random(3)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


# ------------------------------------------------------------------ geography (metres)
def road_y(x):                # the road winds along the cliff top
    return 9 * math.sin(x / 70) + 4 * math.sin(x / 31 + 1)


def road_z(x):
    return 32 + 3 * math.sin(x / 120)


def smooth(a, b, v):
    t = max(0.0, min(1.0, (v - a) / (b - a))); return t * t * (3 - 2 * t)


def height(x, y):
    """Land height. Sea is at y > ~35 (z = 0). Cliff, a road shelf, then rising mountains inland."""
    ry, rz = road_y(x), road_z(x)
    d = y - ry                                         # distance from road centre (+ toward sea)
    p = Vector((x * 0.004, y * 0.004, 0.3))
    hills = noise.multi_fractal(p, 1.0, 2.0, 6) * 18
    ridge = noise.ridged_multi_fractal(Vector((x * 0.0012, y * 0.0012, 1.7)), 0.9, 2.1, 6, 1.0, 2.0)
    mountains = (ridge * 480 + noise.multi_fractal(Vector((x * 0.002, y * 0.002, 4)), 1, 2, 4) * 90) * smooth(-120, -900, d)
    inland = rz + 2 + max(0.0, -d - 7) * 0.35 + hills * smooth(-8, -60, d) * 1.6 + mountains
    detail = noise.noise(Vector((x * 0.08, y * 0.08, 0))) * 0.6
    cliff_edge = 14 + 4 * math.sin(x / 23) + 3 * noise.noise(Vector((x * 0.03, 0, 2)))
    if d < 6:                                         # road shelf + inland
        shelf = rz - 0.15
        t = smooth(6, -12, d)
        return shelf * (1 - t) + inland * t + detail * t
    if d < cliff_edge:                                # grassy verge toward the cliff edge
        return rz - 0.3 - (d - 6) * 0.25 + detail
    drop = smooth(cliff_edge, cliff_edge + 14, d)     # the cliff falls to the sea
    rocky = noise.noise(Vector((x * 0.05, d * 0.05, 5))) * 4
    return (rz - 2) * (1 - drop) + (-6 + rocky) * drop


def grid(name, x0, x1, y0, y1, nx, ny, fn):
    verts, faces = [], []
    for j in range(ny + 1):
        y = y0 + (y1 - y0) * j / ny
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx
            verts.append((x, y, fn(x, y)))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.shade_smooth()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    return o


# ------------------------------------------------------------------ materials from real photo textures
def tex_set(kind):
    hits = sorted(glob.glob(os.path.join(ASSETS, f"{kind}*")))
    return hits[0] if hits else None


def pbr(name, kind, fallback, scale, rough=0.8):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]; b.inputs["Roughness"].default_value = rough
    d = tex_set(kind)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / scale, 1 / scale, 1 / scale)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    if d and os.path.exists(os.path.join(d, "diff.jpg")):
        def img(file, non_color=False):
            n = nt.nodes.new("ShaderNodeTexImage"); n.image = bpy.data.images.load(os.path.join(d, file))
            n.projection = "BOX"; n.projection_blend = 0.3
            if non_color:
                n.image.colorspace_settings.name = "Non-Color"
            nt.links.new(mp.outputs["Vector"], n.inputs["Vector"]); return n
        nt.links.new(img("diff.jpg").outputs["Color"], b.inputs["Base Color"])
        if os.path.exists(os.path.join(d, "rough.jpg")):
            nt.links.new(img("rough.jpg", True).outputs["Color"], b.inputs["Roughness"])
        if os.path.exists(os.path.join(d, "nor.jpg")):
            nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 1.0
            nt.links.new(img("nor.jpg", True).outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
        print("texture:", name, "->", d)
    else:  # procedural stand-in (local tests only)
        nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3
        r = nt.nodes.new("ShaderNodeValToRGB")
        r.color_ramp.elements[0].color = (*fallback[0], 1); r.color_ramp.elements[1].color = (*fallback[1], 1)
        nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"]); nt.links.new(nz.outputs["Fac"], r.inputs["Fac"])
        nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    return m


def terrain_material():
    """Grass on gentle slopes, rock on steep ones and high up - like real coastal mountains."""
    m = bpy.data.materials.new("terrain"); m.use_nodes = True
    nt = m.node_tree; out = nt.nodes["Material Output"]; nt.nodes.remove(nt.nodes["Principled BSDF"])
    rock = pbr("rock", "rock", ((0.22, 0.2, 0.18), (0.42, 0.39, 0.35)), 6.0)
    grass = pbr("grass", "grass", ((0.12, 0.17, 0.05), (0.25, 0.3, 0.1)), 3.0)
    groups = []
    for sub in (rock, grass):  # copy each material's node graph into a group
        g = bpy.data.node_groups.new(sub.name, "ShaderNodeTree")
        g.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
        go = g.nodes.new("NodeGroupOutput")
        mapping = {}
        for n in sub.node_tree.nodes:
            if n.type == "OUTPUT_MATERIAL":
                continue
            c = g.nodes.new(n.bl_idname); mapping[n.name] = c
            for attr in ("image", "projection", "projection_blend"):
                if hasattr(n, attr):
                    setattr(c, attr, getattr(n, attr))
            if n.bl_idname == "ShaderNodeValToRGB":
                for k, e in enumerate(n.color_ramp.elements):
                    c.color_ramp.elements[k].color = e.color
            for i, s in enumerate(n.inputs):
                if hasattr(s, "default_value") and not s.is_linked:
                    try:
                        c.inputs[i].default_value = s.default_value
                    except Exception:
                        pass
        for l in sub.node_tree.links:
            if l.to_node.type == "OUTPUT_MATERIAL":
                g.links.new(mapping[l.from_node.name].outputs[l.from_socket.name], go.inputs[0])
            else:
                g.links.new(mapping[l.from_node.name].outputs[l.from_socket.name], mapping[l.to_node.name].inputs[l.to_socket.identifier])
        node = nt.nodes.new("ShaderNodeGroup"); node.node_tree = g; groups.append(node)
    geo = nt.nodes.new("ShaderNodeNewGeometry"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], sep.inputs[0])
    slope = nt.nodes.new("ShaderNodeMapRange")
    slope.inputs["From Min"].default_value = 0.93; slope.inputs["From Max"].default_value = 0.8
    nt.links.new(sep.outputs["Z"], slope.inputs["Value"])
    pos = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Position"], pos.inputs[0])
    hi = nt.nodes.new("ShaderNodeMapRange"); hi.inputs["From Min"].default_value = 120; hi.inputs["From Max"].default_value = 300
    nt.links.new(pos.outputs["Z"], hi.inputs["Value"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.05
    nt.links.new(geo.outputs["Position"], nz.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"; add.use_clamp = True
    nt.links.new(slope.outputs["Result"], add.inputs[0]); nt.links.new(hi.outputs["Result"], add.inputs[1])
    mix_n = nt.nodes.new("ShaderNodeMath"); mix_n.operation = "MULTIPLY_ADD"
    nt.links.new(nz.outputs["Fac"], mix_n.inputs[0]); mix_n.inputs[1].default_value = 0.3; mix_n.inputs[2].default_value = -0.15
    add2 = nt.nodes.new("ShaderNodeMath"); add2.operation = "ADD"; add2.use_clamp = True
    nt.links.new(add.outputs[0], add2.inputs[0]); nt.links.new(mix_n.outputs[0], add2.inputs[1])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(add2.outputs[0], mix.inputs[0])
    nt.links.new(groups[1].outputs[0], mix.inputs[1]); nt.links.new(groups[0].outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


# ------------------------------------------------------------------ build the world
res = 0.35 if PREVIEW else 1.0
land = grid("land", -700, 1100, -1600, 120, int(360 * res), int(340 * res), height)
land.data.materials.append(terrain_material())
far = grid("far_mountains", -6000, 6000, -9000, -1500, int(160 * res), int(60 * res),
           lambda x, y: 300 + noise.ridged_multi_fractal(Vector((x * 0.0004, y * 0.0004, 9)), 0.9, 2.0, 6, 1.0, 2.0) * 900)
far.data.materials.append(land.data.materials[0])

# road: a strip that follows the winding cliff road, with lane paint and a guard rail
def road_strip(name, off0, off1, dz, mat, x0=-650, x1=1050, step=1.5):
    verts, faces, uvs = [], [], []
    n = int((x1 - x0) / step)
    for i in range(n + 1):
        x = x0 + i * step
        y, z = road_y(x), road_z(x)
        dy = (road_y(x + 0.5) - road_y(x - 0.5)); t = Vector((1, dy, 0)).normalized(); nn = Vector((-t.y, t.x, 0))
        p = Vector((x, y, z + dz))
        verts += [p + nn * off0, p + nn * off1]
    for i in range(n):
        a = 2 * i; faces.append((a, a + 1, a + 3, a + 2))
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces)
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); return o

asphalt = pbr("asphalt", "asphalt", ((0.05, 0.05, 0.055), (0.11, 0.11, 0.115)), 4.0, 0.6)
road_strip("road", -4.2, 4.2, 0.0, asphalt)
paint = bpy.data.materials.new("paint"); paint.use_nodes = True
paint.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.75, 0.72, 0.62, 1)
paint.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.55
for off in (-3.9, 3.75):
    road_strip("edge_line", off, off + 0.15, 0.01, paint)
for k in range(-650, 1050, 12):  # dashed centre line
    road_strip("dash", -0.07, 0.07, 0.01, paint, k, k + 4.5, 1.5)
steel = bpy.data.materials.new("steel"); steel.use_nodes = True
b = steel.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (0.6, 0.6, 0.62, 1)
b.inputs["Metallic"].default_value = 1.0; b.inputs["Roughness"].default_value = 0.35
rail = road_strip("rail", 5.6, 5.6, 0.0, steel)
rail.data.vertices.foreach_set("co", [c for v in rail.data.vertices for c in (v.co.x, v.co.y, v.co.z)])
# guard rail = vertical ribbon on the sea side + posts
verts, faces = [], []
for i, x in enumerate(range(-650, 1050, 2)):
    y, z = road_y(x), road_z(x); dy = road_y(x + 0.5) - road_y(x - 0.5)
    t = Vector((1, dy, 0)).normalized(); nn = Vector((-t.y, t.x, 0)); p = Vector((x, y, z)) + nn * 5.6
    verts += [p + Vector((0, 0, 0.45)), p + Vector((0, 0, 0.8))]
    if i:
        a = 2 * (i - 1); faces.append((a, a + 2, a + 3, a + 1))
me = bpy.data.meshes.new("guardrail"); me.from_pydata(verts, [], faces); me.materials.append(steel)
gr = bpy.data.objects.new("guardrail", me); sc.collection.objects.link(gr)
bpy.context.view_layer.objects.active = gr
sol = gr.modifiers.new("t", "SOLIDIFY"); sol.thickness = 0.08
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.06, depth=0.85)
post = bpy.context.active_object; post.data.materials.append(steel)
for x in range(-650, 1050, 4):
    y, z = road_y(x), road_z(x); dy = road_y(x + 0.5) - road_y(x - 0.5)
    t = Vector((1, dy, 0)).normalized(); nn = Vector((-t.y, t.x, 0)); p = Vector((x, y, z)) + nn * 5.65
    c = post.copy(); sc.collection.objects.link(c); c.location = p + Vector((0, 0, 0.42))

# boulders along the cliff, with the rock texture
rockm = land.data.materials[0]
for k in range(220):
    x = rng.uniform(-600, 1000); d = rng.uniform(15, 40)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1)
    r = bpy.context.active_object; s = rng.uniform(0.6, 4.5)
    r.scale = (s * rng.uniform(0.8, 1.4), s, s * rng.uniform(0.5, 0.9)); r.rotation_euler = (rng.random(), rng.random(), rng.random())
    dm = r.modifiers.new("d", "DISPLACE"); tx = bpy.data.textures.new("rk", "VORONOI"); tx.noise_scale = 0.6; dm.texture = tx; dm.strength = 0.4
    r.location = (x, road_y(x) + d, height(x, road_y(x) + d) - 0.3); r.data.materials.append(rockm); r.data.shade_smooth()

# ocean: Blender's physically based ocean simulation (animated waves + foam)
bpy.ops.mesh.primitive_plane_add(size=1, location=(200, 600, 0))
sea = bpy.context.active_object
oc = sea.modifiers.new("ocean", "OCEAN")
oc.geometry_mode = "GENERATE"; oc.spatial_size = 200; oc.repeat_x = oc.repeat_y = 12
oc.resolution = 7 if PREVIEW else 12; oc.wave_scale = 1.4; oc.wind_velocity = 14; oc.choppiness = 1.3
oc.wave_alignment = 0.4; oc.wave_direction = math.radians(-100); oc.use_foam = True; oc.foam_layer_name = "foam"
oc.foam_coverage = 0.02
sea.location = (200 - 1200, 600 - 1200, 0)
fc = oc.driver_add("time").driver; fc.expression = "frame/24"
water = bpy.data.materials.new("sea"); water.use_nodes = True; nt = water.node_tree; b = nt.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.004, 0.035, 0.045, 1); b.inputs["Roughness"].default_value = 0.04
b.inputs["IOR"].default_value = 1.333
attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "foam"
foam_mix = nt.nodes.new("ShaderNodeMix"); foam_mix.data_type = "RGBA"
nt.links.new(attr.outputs["Fac"], foam_mix.inputs[0]); foam_mix.inputs[6].default_value = (0.004, 0.035, 0.045, 1)
foam_mix.inputs[7].default_value = (0.85, 0.88, 0.9, 1); nt.links.new(foam_mix.outputs[2], b.inputs["Base Color"])
sea.data.materials.append(water)
bpy.ops.mesh.primitive_plane_add(size=40000, location=(0, 0, -0.4))  # horizon sea beyond the simulated patch
hor = bpy.context.active_object; hor.data.materials.append(water)

# sky: real HDRI if downloaded, else a physically based sky; plus the sun
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; wn = w.node_tree; bg = wn.nodes["Background"]
hdr = os.path.join(ASSETS, "sky.hdr")
if os.path.exists(hdr):
    env = wn.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(hdr)
    mpn = wn.nodes.new("ShaderNodeMapping"); tcn = wn.nodes.new("ShaderNodeTexCoord")
    mpn.inputs["Rotation"].default_value[2] = math.radians(float(os.environ.get("SKY_ROT", "0")))
    wn.links.new(tcn.outputs["Generated"], mpn.inputs["Vector"]); wn.links.new(mpn.outputs["Vector"], env.inputs["Vector"])
    wn.links.new(env.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 1.0
    print("sky: HDRI")
else:
    sky = wn.nodes.new("ShaderNodeTexSky"); sky.sky_type = "NISHITA"; sky.sun_disc = False
    sky.sun_elevation = math.radians(14); sky.sun_rotation = math.radians(250)
    wn.links.new(sky.outputs[0], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 0.3
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 4.5; sun.data.angle = math.radians(0.6); sun.data.color = (1.0, 0.86, 0.7)
sun.rotation_euler = (math.radians(76), 0, math.radians(160)); sc.collection.objects.link(sun)

# ------------------------------------------------------------------ the car
car = bpy.data.objects.new("car", None); sc.collection.objects.link(car)
glbs = glob.glob(os.path.join(ASSETS, "*.glb"))
L = 4.6
if glbs:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glbs[0])
    new = [o for o in bpy.data.objects if o not in before]
    holder = bpy.data.objects.new("holder", None); sc.collection.objects.link(holder)
    for o in new:
        if o.parent is None:
            o.parent = holder
    def bounds():
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
        return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])
    mn, mx = bounds(); size = mx - mn
    if size.z > max(size.x, size.y):
        holder.rotation_euler.x = math.pi / 2; mn, mx = bounds(); size = mx - mn
    if size.y > size.x:
        holder.rotation_euler.z = math.pi / 2; mn, mx = bounds(); size = mx - mn
    s = L / size.x; holder.scale = (s, s, s); mn, mx = bounds()
    holder.location -= Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    if os.environ.get("CAR_FLIP") == "1":
        holder.rotation_euler.z += math.pi
    holder.parent = car
    print("car: real model", glbs[0])
else:  # stand-in box for local layout tests only
    bpy.ops.mesh.primitive_cube_add(size=1); b0 = bpy.context.active_object
    b0.scale = (4.5, 1.9, 1.3); b0.location = (0, 0, 0.75); b0.parent = car
    print("car: STAND-IN (no model found)")

def car_pose(f):
    x = X0 + V * (f - 1) / FPS
    y = road_y(x) - 1.9                      # left lane... keep to the inland lane
    dy = road_y(x + 0.5) - road_y(x - 0.5); yaw = math.atan2(dy, 1.0)
    return Vector((x, y, road_z(x) + 0.0)), yaw

for f in range(1, N + 2, 2):
    p, yaw = car_pose(f)
    car.location = p + Vector((0, 0, 0.015 * math.sin(f * 1.1)))
    car.rotation_euler = (0, 0.004 * math.sin(f * 0.7), yaw)
    car.keyframe_insert("location", frame=f); car.keyframe_insert("rotation_euler", frame=f)

# ------------------------------------------------------------------ three cinematic shots (5 s each)
def camera(name, lens, path, aim, fstop=None):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 20000; cd.sensor_width = 36
    cam = bpy.data.objects.new(name, cd); sc.collection.objects.link(cam)
    tgt = bpy.data.objects.new(name + "_aim", None); sc.collection.objects.link(tgt)
    tr = cam.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
    if fstop:
        cd.dof.use_dof = True; cd.dof.focus_object = car; cd.dof.aperture_fstop = fstop
    for f in range(1, N + 2, 2):
        p, yaw = car_pose(f)
        cam.location = path(f, p, yaw); tgt.location = aim(f, p, yaw)
        cam.keyframe_insert("location", frame=f); tgt.keyframe_insert("location", frame=f)
    return cam

def u(f, a, b):
    return min(1.0, max(0.0, (f - a) / (b - a)))

def fwd(yaw):
    return Vector((math.cos(yaw), math.sin(yaw), 0)), Vector((-math.sin(yaw), math.cos(yaw), 0))

# 1) drone over the sea, tracking the car with the cliffs and mountains behind it
c1 = camera("drone", 30, lambda f, p, y: p + Vector((60 - 14 * u(f, 1, 120), 48, 30 - 8 * u(f, 1, 120))),
            lambda f, p, y: p + Vector((-25, -8, 2)))
# 2) low tracking shot alongside the car (sea side), long lens, road rushing past
c2 = camera("track", 50, lambda f, p, y: p + fwd(y)[0] * (2.5 - 2 * u(f, 121, 240)) + fwd(y)[1] * 6.5 + Vector((0, 0, 0.9)),
            lambda f, p, y: p + Vector((0, 0, 0.8)), fstop=4.0)
# 3) behind the car, rising and pulling back to reveal the whole coastline
c3 = camera("reveal", 26, lambda f, p, y: p - fwd(y)[0] * (10 + 55 * u(f, 241, 361) ** 1.4) + fwd(y)[1] * (2 + 30 * u(f, 241, 361))
            + Vector((0, 0, 2.5 + 70 * u(f, 241, 361) ** 1.3)),
            lambda f, p, y: p + fwd(y)[0] * (25 + 120 * u(f, 241, 361)) + Vector((0, 0, 1)))
for start, cam in ((1, c1), (121, c2), (241, c3)):
    m = sc.timeline_markers.new(cam.name, frame=start); m.camera = cam
sc.camera = c1

# ------------------------------------------------------------------ render settings (Cycles, GPU)
sc.render.engine = "CYCLES"; sc.frame_start, sc.frame_end, sc.render.fps = 1, N, FPS
prefs = bpy.context.preferences.addons["cycles"].preferences
gpu = False
for kind in ("CUDA", "OPTIX"):  # CUDA first: Kaggle's driver can't create OptiX denoisers
    try:
        prefs.compute_device_type = kind; prefs.get_devices()
        devs = [d for d in prefs.devices if d.type == kind]
        if devs:
            for d in prefs.devices:
                d.use = d.type == kind
            gpu = True; print("GPU render:", kind, [d.name for d in devs]); break
    except Exception as exc:
        print("no", kind, exc)
sc.cycles.device = "GPU" if gpu else "CPU"
sc.cycles.samples = 16 if PREVIEW else int(os.environ.get("SAMPLES", 160))
sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.denoising_use_gpu = gpu
except Exception:
    pass
sc.cycles.max_bounces = 8
sc.render.resolution_x, sc.render.resolution_y = (960, 540) if PREVIEW else (1920, 1080)
sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.5
sc.render.use_persistent_data = True
sc.view_settings.view_transform = "AgX"
try:
    sc.view_settings.look = "AgX - Medium High Contrast"
except TypeError:
    pass
sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 95
# aerial perspective: distant mountains fade into blue haze, like real air
sc.view_layers[0].use_pass_mist = True; w.mist_settings.start = 150; w.mist_settings.depth = 5000; w.mist_settings.falloff = "QUADRATIC"
sc.use_nodes = True; ct = sc.node_tree; rl, comp = ct.nodes["Render Layers"], ct.nodes["Composite"]
mix = ct.nodes.new("CompositorNodeMixRGB"); mix.inputs[2].default_value = (0.62, 0.7, 0.8, 1)
mul = ct.nodes.new("CompositorNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 0.55
ct.links.new(rl.outputs["Mist"], mul.inputs[0]); ct.links.new(mul.outputs[0], mix.inputs[0])
ct.links.new(rl.outputs["Image"], mix.inputs[1]); ct.links.new(mix.outputs[0], comp.inputs[0])

os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ.get("FRAMES", "").split(",") if x] or range(1, N + 1)
for f in frames:
    sc.frame_set(f); sc.render.filepath = os.path.join(OUT, f"f_{f:04d}.jpg")
    bpy.ops.render.render(write_still=True)
    print("frame", f, "done", flush=True)
sys.stdout.flush(); os._exit(0)
