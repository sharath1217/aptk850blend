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
        t = smooth(-5.5, -15, d)  # flat road shelf across the full road width
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
    slope.inputs["From Min"].default_value = 0.82; slope.inputs["From Max"].default_value = 0.66
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
_nt = asphalt.node_tree; _b = _nt.nodes["Principled BSDF"]
if _b.inputs["Roughness"].is_linked:  # wet road: same texture, much glossier, with damp patches
    src = _b.inputs["Roughness"].links[0].from_socket
    wet = _nt.nodes.new("ShaderNodeMath"); wet.operation = "MULTIPLY"; wet.inputs[1].default_value = 0.35
    pn = _nt.nodes.new("ShaderNodeTexNoise"); pn.inputs["Scale"].default_value = 0.08
    mr = _nt.nodes.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 0.25; mr.inputs["To Max"].default_value = 1.0
    _nt.links.new(pn.outputs["Fac"], mr.inputs["Value"])
    m2 = _nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
    _nt.links.new(src, wet.inputs[0]); _nt.links.new(wet.outputs[0], m2.inputs[0]); _nt.links.new(mr.outputs[0], m2.inputs[1])
    _nt.links.new(m2.outputs[0], _b.inputs["Roughness"])
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

# real photo-scanned plants and rocks (Poly Haven models, CC0), scattered as instances
def load_models(kind):
    cols = []
    for gl in sorted(glob.glob(os.path.join(ASSETS, "models", kind, "*", "*.gltf")))[:4]:
        before = set(bpy.data.objects)
        try:
            bpy.ops.import_scene.gltf(filepath=gl)
        except Exception as exc:
            print("model failed", gl, exc); continue
        col = bpy.data.collections.new(os.path.basename(os.path.dirname(gl)))
        for o in [o for o in bpy.data.objects if o not in before]:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            col.objects.link(o)
        cols.append(col); print("model:", kind, col.name, flush=True)
    return cols

def scatter(cols, n, where, scale):
    if not cols:
        return
    for k in range(n):
        x, y = where()
        z = height(x, y)
        e = bpy.data.objects.new("inst", None); e.instance_type = "COLLECTION"; e.instance_collection = rng.choice(cols)
        e.location = (x, y, z - 0.1); e.rotation_euler = (0, 0, rng.uniform(0, 6.283))
        sc_ = rng.uniform(*scale); e.scale = (sc_, sc_, sc_); sc.collection.objects.link(e)

trees, shrubs, rocks_m = load_models("tree"), load_models("shrub"), load_models("rock")
def inland(a, b):
    def w():
        x = rng.uniform(-400, 700); return x, road_y(x) - rng.uniform(a, b)
    return w
def verge():
    x = rng.uniform(-400, 700); return x, road_y(x) + rng.choice([-1, 1]) * rng.uniform(5.5, 12)
scatter(trees, 700 if not PREVIEW else 150, inland(10, 160), (0.8, 1.4))
scatter(shrubs, 4000 if not PREVIEW else 300, verge, (0.6, 1.6))
scatter(shrubs, 6000 if not PREVIEW else 300, inland(7, 120), (0.7, 1.8))
scatter(rocks_m, 400 if not PREVIEW else 80, lambda: (lambda x: (x, road_y(x) + rng.uniform(13, 40)))(rng.uniform(-400, 700)), (0.6, 3.0))

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
sun.data.energy = 5.0; sun.data.angle = math.radians(0.5); sun.data.color = (1.0, 0.72, 0.45)
# low sun over the sea (elevation ~8 deg), shining toward the land: backlit cars, glowing haze, long shadows
sun.rotation_euler = (math.radians(-82), 0, math.radians(-15)); sc.collection.objects.link(sun)
vol = wn.nodes.new("ShaderNodeVolumePrincipled"); vol.inputs["Density"].default_value = float(os.environ.get("HAZE", "0.0006"))
vol.inputs["Anisotropy"].default_value = 0.7; vol.inputs["Color"].default_value = (0.95, 0.85, 0.75, 1)
# haze lives in a big box around the action (a world volume would also swallow the sky)
bpy.ops.mesh.primitive_cube_add(size=1, location=(150, -200, 120)); hz = bpy.context.active_object
hz.scale = (2400, 2400, 240); hzm = bpy.data.materials.new("haze"); hzm.use_nodes = True
hzm.node_tree.nodes.remove(hzm.node_tree.nodes["Principled BSDF"])
hzm.node_tree.links.new(vol.outputs[0], hzm.node_tree.nodes["Material Output"].inputs["Volume"])
wn.nodes.remove(vol); vol = hzm.node_tree.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value = float(os.environ.get("HAZE", "0.0004")); vol.inputs["Anisotropy"].default_value = 0.7
vol.inputs["Color"].default_value = (0.95, 0.85, 0.75, 1)
hzm.node_tree.links.new(vol.outputs[0], hzm.node_tree.nodes["Material Output"].inputs["Volume"])
hz.data.materials.append(hzm)

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
    # which end is the front? tail lights / brake lights / number plate sit at the back, headlights at the front
    bpy.context.view_layer.update()
    vote = 0.0
    for o in new:
        if o.type != "MESH":
            continue
        names = (o.name + " " + " ".join(sl.material.name for sl in o.material_slots if sl.material)).lower()
        cx = sum((o.matrix_world @ Vector(b)).x for b in o.bound_box) / 8
        if any(k in names for k in ("tail", "brake", "rear", "plate", "exhaust", "back")):
            vote -= cx          # these should be at -X
        if any(k in names for k in ("head", "front", "grill", "bumper_f", "hood", "bonnet")):
            vote += cx          # these should be at +X
        for sl in o.material_slots:  # red emissive = tail lights
            m = sl.material
            if m and m.use_nodes:
                b = m.node_tree.nodes.get("Principled BSDF")
                if b and b.inputs["Emission Strength"].default_value > 0 and not b.inputs["Emission Color"].is_linked:
                    c = b.inputs["Emission Color"].default_value
                    if c[0] > 0.5 and c[1] < 0.3:
                        vote -= cx
    if os.environ.get("CAR_FLIP") is not None:
        flip = os.environ["CAR_FLIP"] == "1"
    else:
        flip = vote < 0 if vote != 0 else os.environ.get("CAR_FLIP_IF_UNSURE", "0") == "1"
    print("car front check: vote", round(vote, 2), "-> flip" if flip else "-> ok", flush=True)
    if flip:  # turn 180 deg and re-centre on the car's origin
        holder.rotation_euler.z += math.pi
        mn, mx = bounds(); holder.location -= Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    holder.parent = car
    print("car: real model", glbs[0])
    def P(name, rgb, rough, metal=0.0, coat=0.0, trans=0.0, emit=0.0):
        m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal; b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.03; b.inputs["Transmission Weight"].default_value = trans
        if emit:
            b.inputs["Emission Color"].default_value = (*rgb, 1); b.inputs["Emission Strength"].default_value = emit
        return m
    paint_rgb = tuple(float(v) for v in os.environ.get("CAR_PAINT", "0.02,0.05,0.09").split(","))  # deep metallic blue
    LOOK = {"glass": P("car_glass", (0.01, 0.012, 0.015), 0.0, trans=0.85), "window": None, "wind": None,
            "tire": P("car_rubber", (0.015, 0.015, 0.015), 0.6), "tyre": None, "rubber": None,
            "chrome": P("car_chrome", (0.9, 0.9, 0.92), 0.08, metal=1.0), "rim": None, "wheel": None, "metal": None,
            "head": P("car_lamp", (1.0, 0.97, 0.9), 0.05, emit=6), "lamp": None, "light": None,
            "tail": P("car_tail", (0.8, 0.02, 0.02), 0.1, emit=4), "brake": None,
            "interior": P("car_interior", (0.03, 0.03, 0.03), 0.7), "seat": None,
            "black": P("car_trim", (0.01, 0.01, 0.01), 0.35), "trim": None, "grill": None, "plastic": None}
    last = None
    for k in list(LOOK):
        LOOK[k] = LOOK[k] or last; last = LOOK[k]
    body = P("car_paint", paint_rgb, 0.28, metal=0.7, coat=1.0)
    for o in new:
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            m = slot.material; name = (m.name if m else "").lower()
            textured = m and m.use_nodes and any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes)
            hit = next((v for k, v in LOOK.items() if k in name), None)
            if hit:
                slot.material = hit
            elif not textured:  # untextured "clay" surface -> real car paint
                slot.material = body
        if not o.material_slots:
            o.data.materials.append(body)
else:  # stand-in box for local layout tests only
    bpy.ops.mesh.primitive_cube_add(size=1); b0 = bpy.context.active_object
    b0.scale = (4.5, 1.9, 1.3); b0.location = (0, 0, 0.75); b0.parent = car
    print("car: STAND-IN (no model found)")

for side in (0.62, -0.62):
    hl = bpy.data.objects.new("headlight", bpy.data.lights.new("headlight", "SPOT"))
    hl.data.energy = 900; hl.data.spot_size = math.radians(55); hl.data.spot_blend = 0.4
    hl.data.color = (1.0, 0.95, 0.88); hl.data.shadow_soft_size = 0.05
    hl.location = (2.25, side, 0.65); hl.rotation_euler = (0, math.radians(-92), 0); hl.parent = car
    sc.collection.objects.link(hl)


def spin_wheels():
    """Find the wheels in the car model and spin them at the true rolling speed (distance / radius)."""
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.parent and
              (o.parent == car or o.parent.name == "holder" or (o.parent.parent and o.parent.parent.name == "holder"))]
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(p == car for p in iter_parents(o))]
    bpy.context.view_layer.update()
    keys = ("wheel", "tire", "tyre", "rim", "rueda", "rad", "brake_disc", "disc")
    wheels = [o for o in meshes if any(k in o.name.lower() for k in keys)
              or any(k in (s.material.name.lower() if s.material else "") for s in o.material_slots for k in ("tire", "tyre", "rubber", "rim"))]
    inv = car.matrix_world.inverted()
    def extent(o):
        pts = [inv @ (o.matrix_world @ Vector(b)) for b in o.bound_box]
        return Vector([max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)])
    # several wheels in ONE mesh (common in game/Sketchfab models): split them into separate pieces first
    split = []
    for o in wheels:
        e = extent(o)
        if e.x > 1.1 or e.y > 0.7:
            bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
            try:
                bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.mesh.separate(type="LOOSE"); bpy.ops.object.mode_set(mode="OBJECT")
                split += list(bpy.context.selected_objects)
            except Exception as exc:
                print("wheels: split failed", exc); bpy.ops.object.mode_set(mode="OBJECT")
        else:
            split.append(o)
    bpy.context.view_layer.update()
    # keep only wheel-sized pieces (a wheel is < ~1 m tall/long and < ~0.5 m wide); everything else stays on the body
    wheels = []
    for o in split:
        e = extent(o)
        if 0.15 < e.z < 1.0 and e.x < 1.0 and e.y < 0.55:
            wheels.append(o)
    groups = {}
    for o in wheels:  # group parts by corner (front/rear x left/right) in car space
        c = sum((car.matrix_world.inverted() @ (o.matrix_world @ Vector(b)) for b in o.bound_box), Vector()) / 8
        if c.z > 1.0:
            continue
        groups.setdefault((c.x > 0, c.y > 0), []).append((o, c))
    if len(groups) < 4:
        print("wheels: could not separate 4 wheels (found", len(groups), ") - left static, motion blur hides it"); return
    for corner, parts in groups.items():
        pts = [car.matrix_world.inverted() @ (o.matrix_world @ Vector(b)) for o, _ in parts for b in o.bound_box]
        lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
        centre = (lo + hi) / 2; radius = max(0.2, (hi.z - lo.z) / 2)
        hub = bpy.data.objects.new("hub", None); sc.collection.objects.link(hub); hub.parent = car; hub.location = centre
        bpy.context.view_layer.update()
        for o, _ in parts:
            mw = o.matrix_world.copy(); o.parent = hub; o.matrix_world = mw
        d = hub.driver_add("rotation_euler", 1).driver
        d.expression = f"(frame-1)/{FPS}*{V}/{radius:.3f}"
        print(f"wheels: corner {corner} r={radius:.2f} m, {len(parts)} parts", flush=True)

def iter_parents(o):
    while o.parent:
        o = o.parent; yield o

if glbs:
    spin_wheels()


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

def rig(name, start, end, lens, loc, aim, fstop=2.8, shake=0.006, slide=(0, 0, 0)):
    """Camera bolted to a car rig (moves with the car), with engine/road vibration."""
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 20000
    cam = bpy.data.objects.new(name, cd); sc.collection.objects.link(cam); cam.parent = car
    tgt = bpy.data.objects.new(name + "_aim", None); sc.collection.objects.link(tgt); tgt.parent = car; tgt.location = aim
    tr = cam.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
    cd.dof.use_dof = True; cd.dof.focus_object = tgt; cd.dof.aperture_fstop = fstop
    for f in range(start, end + 1):
        k = (f - start) / max(1, end - start)
        cam.location = Vector(loc) + Vector(slide) * k + Vector((noise.noise(Vector((f * 0.31, 0, 0))), noise.noise(Vector((0, f * 0.37, 0))),
                                                                  noise.noise(Vector((0, 0, f * 0.43))))) * shake
        cam.keyframe_insert("location", frame=f)
    return cam

def world_cam(name, start, end, lens, path, aim, fstop=None, shake=0.0):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 20000
    cam = bpy.data.objects.new(name, cd); sc.collection.objects.link(cam)
    tgt = bpy.data.objects.new(name + "_aim", None); sc.collection.objects.link(tgt)
    tr = cam.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
    if fstop:
        cd.dof.use_dof = True; cd.dof.focus_object = car; cd.dof.aperture_fstop = fstop
    for f in range(start, end + 1, 2):
        p, yaw = car_pose(f)
        cam.location = path(f, p, yaw) + Vector((noise.noise(Vector((f * 0.11, 3, 0))), noise.noise(Vector((5, f * 0.13, 0))), 0)) * shake
        tgt.location = aim(f, p, yaw)
        cam.keyframe_insert("location", frame=f); tgt.keyframe_insert("location", frame=f)
    return cam

# car-local axes: +X forward, +Y left (sea side), +Z up
SHOTS = [
    (1,   rig("headlight", 1, 40, 35, (4.8, 2.3, 0.7), (1.2, 0.2, 0.6), 2.2, 0.004, (0, -0.4, 0))),          # headlight & grille
    (41,  rig("rear_low", 41, 80, 24, (-3.6, 1.6, 0.35), (0.4, 0.3, 0.7), 4.0, 0.008)),                              # low rear 3/4, road rushing
    (81,  rig("front_track", 81, 130, 32, (11, 0.8, 0.6), (0, 0, 0.75), 2.8, 0.01, (-2.5, 0, 0))),                    # car charging at the lens
    (131, rig("side", 131, 175, 32, (1.0, 6.8, 1.25), (0.0, -1.0, 0.9), 4.0, 0.004)),                         # driver against the sun & sea
    (176, world_cam("telephoto", 176, 235, 150,                                                                      # roadside long lens, heat-haze feel
                    lambda f, p, y: Vector((X0 + V * 235 / FPS + 30, road_y(X0 + V * 235 / FPS + 30) + 9, road_z(X0 + V * 235 / FPS + 30) + 1.4)),
                    lambda f, p, y: p + Vector((0, 0, 0.7)), 2.8, 0.03)),
    (236, world_cam("topdown", 236, 275, 28, lambda f, p, y: p + Vector((2 + 0.05 * (f - 236), 0.5, 26)),
                    lambda f, p, y: p + Vector((2.5, 0, 0)))),
    (276, world_cam("reveal", 276, 361, 30,                                                                          # drone pull-back into the sun
                    lambda f, p, y: p + fwd(y)[0] * (-14 - 70 * u(f, 276, 361) ** 1.3) + fwd(y)[1] * (-6 - 25 * u(f, 276, 361))
                    + Vector((0, 0, 4 + 55 * u(f, 276, 361) ** 1.2)),
                    lambda f, p, y: p + fwd(y)[0] * (30 + 90 * u(f, 276, 361)) + fwd(y)[1] * (20 * u(f, 276, 361)) + Vector((0, 0, 2)))),
]
for start, cam in SHOTS:
    m = sc.timeline_markers.new(cam.name, frame=start); m.camera = cam
c1 = SHOTS[0][1]
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
if os.environ.get("RES"):
    sc.render.resolution_x, sc.render.resolution_y = map(int, os.environ["RES"].split("x"))
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
mul = ct.nodes.new("CompositorNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 0.35
ct.links.new(rl.outputs["Mist"], mul.inputs[0]); ct.links.new(mul.outputs[0], mix.inputs[0])
ct.links.new(rl.outputs["Image"], mix.inputs[1])
glare = ct.nodes.new("CompositorNodeGlare"); glare.glare_type = "FOG_GLOW"; glare.quality = "HIGH"
glare.threshold = 1.0; glare.size = 8; glare.mix = -0.75
lens = ct.nodes.new("CompositorNodeLensdist"); lens.inputs["Distortion"].default_value = -0.012; lens.inputs["Dispersion"].default_value = 0.006
ct.links.new(mix.outputs[0], glare.inputs["Image"]); ct.links.new(glare.outputs["Image"], lens.inputs["Image"])
ct.links.new(lens.outputs["Image"], comp.inputs[0])

os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ.get("FRAMES", "").split(",") if x] or range(1, N + 1)
for f in frames:
    sc.frame_set(f); sc.render.filepath = os.path.join(OUT, f"f_{f:04d}.jpg")
    bpy.ops.render.render(write_still=True)
    print("frame", f, "done", flush=True)
sys.stdout.flush(); os._exit(0)
