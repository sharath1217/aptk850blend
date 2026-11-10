"""Short film - step 2 (Blender shot library). Renders any story.json written by writer.py.

  blender -b -noaudio -P studio/film/shots.py -- <chunk> <chunks> <assets_dir> [draft|final]

Everything is built in code, so no assets are needed:
  sets       coast, city, planet, toytown, room, forest   x  day / dusk / night  x  rain / snow / fog
  actors     stylised robots (box / round / tall, 8 colours) with walk, run, talk, wave, look,
             jump, dance, sad, fall, idle - mouths light up exactly while their line is spoken
  vehicles   car drive / car chase (real model if writer.py found one) / spaceship fly / land
  cameras    establish, push_in, orbit, track, closeup, over_shoulder, low_angle, crane_up,
             handheld, top_down - with depth of field, motion blur and mist
Frames are dealt out across the render machines (frame g -> machine g % chunks)."""
import bpy, glob, json, math, os, random, sys
from mathutils import Vector

FPS = 24
COLORS = {"orange": (0.9, 0.35, 0.05), "blue": (0.08, 0.3, 0.85), "red": (0.8, 0.06, 0.05),
          "green": (0.15, 0.6, 0.15), "yellow": (0.95, 0.75, 0.08), "purple": (0.4, 0.12, 0.7),
          "white": (0.85, 0.85, 0.82), "pink": (0.95, 0.4, 0.6)}
SPEED = {"walk": 1.1, "run": 3.4}


# ---------------------------------------------------------------- helpers
def mat(name, rgb, rough=0.5, metal=0.0, emit=0.0, emit_rgb=None, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*(emit_rgb or rgb), 1)
        b.inputs["Emission Strength"].default_value = emit
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return m


def node_mat(name, build):
    """Material whose Base Color (and more) comes from a small node graph."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; build(nt, nt.nodes["Principled BSDF"]); return m


def prim(kind, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), material=None, parent=None, bevel=0.0, **kw):
    getattr(bpy.ops.mesh, f"primitive_{kind}_add")(location=loc, rotation=rot, **kw)
    o = bpy.context.active_object; o.scale = scale
    if material:
        o.data.materials.append(material)
    if bevel:
        m = o.modifiers.new("bevel", "BEVEL"); m.width = bevel; m.segments = 3
    if kind in ("uv_sphere", "ico_sphere", "cylinder", "cone", "torus"):
        o.data.shade_smooth()
    if parent:
        o.parent = parent
    return o


def empty(name, loc=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(o)
    o.location = loc; o.parent = parent
    return o


def light(kind, loc, energy, color=(1, 1, 1), rot=(0, 0, 0), size=0.2, parent=None, **kw):
    d = bpy.data.lights.new("L", kind); d.energy = energy; d.color = color
    if kind in ("POINT", "SPOT"):
        d.shadow_soft_size = size
    elif kind == "AREA":
        d.size = size
    elif kind == "SUN":
        d.angle = size
    for k, v in kw.items():
        setattr(d, k, v)
    o = bpy.data.objects.new("L", d); bpy.context.scene.collection.objects.link(o)
    o.location = loc; o.rotation_euler = rot; o.parent = parent
    return o


def clone(o, loc, scale=None, rot=None):
    c = o.copy(); bpy.context.scene.collection.objects.link(c); c.location = loc
    if scale is not None:
        c.scale = scale
    if rot is not None:
        c.rotation_euler = rot
    return c


def key(o, path, value, frame):
    setattr(o, path, value) if not isinstance(value, tuple) else setattr(o, path, value)
    o.keyframe_insert(path, frame=frame)


def ground(size_x, size_y, material, x0=0.0, y0=0.0, z=0.0, cuts=0, disp=None):
    bpy.ops.mesh.primitive_plane_add(location=(x0, y0, z))
    g = bpy.context.active_object; g.scale = (size_x / 2, size_y / 2, 1)
    g.data.materials.append(material)
    if cuts:
        m = g.modifiers.new("sub", "SUBSURF"); m.subdivision_type = "SIMPLE"
        m.levels = m.render_levels = cuts
    if disp:
        tex = bpy.data.textures.new("d", "CLOUDS"); tex.noise_scale = disp[1]
        m = g.modifiers.new("disp", "DISPLACE"); m.texture = tex; m.strength = disp[0]
        m.texture_coords = "GLOBAL"
    return g


# ---------------------------------------------------------------- sky & light
def sky(time, set_name, rng):
    w = bpy.data.worlds.new("w"); bpy.context.scene.world = w; w.use_nodes = True
    nt = w.node_tree; bg = nt.nodes["Background"]
    if set_name == "room":
        bg.inputs[0].default_value = (0.02, 0.02, 0.03, 1) if time == "night" else (0.4, 0.45, 0.55, 1)
        bg.inputs[1].default_value = 0.3
        return
    if set_name == "planet" or time == "night":
        # dark gradient + procedural stars
        tc = nt.nodes.new("ShaderNodeTexCoord"); vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 420
        ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[1].position = 0.035
        ramp.color_ramp.elements[0].color = (8, 8, 9, 1); ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
        base = {"night": (0.004, 0.006, 0.016), "dusk": (0.12, 0.04, 0.09), "day": (0.35, 0.16, 0.12)}[time]
        if set_name == "planet" and time == "day":
            base = (0.5, 0.22, 0.12)
        add = nt.nodes.new("ShaderNodeMix"); add.data_type = "RGBA"; add.blend_type = "ADD"
        add.inputs[0].default_value = 1.0 if time == "night" else 0.15
        add.inputs[6].default_value = (*base, 1)
        nt.links.new(tc.outputs["Generated"], vor.inputs["Vector"])
        nt.links.new(vor.outputs["Distance"], ramp.inputs[0])
        nt.links.new(ramp.outputs[0], add.inputs[7]); nt.links.new(add.outputs[2], bg.inputs[0])
        bg.inputs[1].default_value = 1.0
        if time == "night":
            light("SUN", (0, 0, 10), 0.25, (0.6, 0.7, 1.0), rot=(math.radians(50), 0, math.radians(30)), size=0.02)
        else:
            light("SUN", (0, 0, 10), 2.2 if time == "day" else 1.2, (1.0, 0.6, 0.4),
                  rot=(math.radians(70 if time == "dusk" else 40), 0, math.radians(-30)), size=0.03)
        return
    s = nt.nodes.new("ShaderNodeTexSky"); s.sky_type = "NISHITA"; s.sun_disc = False  # the sun lamp lights the scene
    elev = 40 if time == "day" else 3
    s.sun_elevation = math.radians(elev); s.sun_rotation = math.radians(rng.uniform(140, 220))
    s.dust_density = 1.5 if time == "dusk" else 0.8
    nt.links.new(s.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.22 if time == "day" else 0.5
    light("SUN", (0, 0, 10), 2.4 if time == "day" else 2.0,
          (1, 0.97, 0.92) if time == "day" else (1, 0.55, 0.3),
          rot=(math.radians(90 - elev), 0, s.sun_rotation - math.pi / 2), size=0.02)


# ---------------------------------------------------------------- sets
def set_coast(time, rng, x0, x1):
    grass = node_mat("grass", lambda nt, b: _noise_color(nt, b, (0.08, 0.2, 0.04), (0.2, 0.3, 0.08), 6))
    ground(x1 - x0 + 80, 40, grass, (x0 + x1) / 2, -4, cuts=5, disp=(0.4, 3.0))
    water = mat("sea", (0.01, 0.04, 0.06), 0.04)
    bump = water.node_tree.nodes.new("ShaderNodeBump"); wav = water.node_tree.nodes.new("ShaderNodeTexWave")
    wav.inputs["Scale"].default_value = 0.6; wav.inputs["Distortion"].default_value = 6
    bump.inputs["Strength"].default_value = 0.25
    water.node_tree.links.new(wav.outputs["Fac"], bump.inputs["Height"])
    water.node_tree.links.new(bump.outputs[0], water.node_tree.nodes["Principled BSDF"].inputs["Normal"])
    ground(4000, 4000, water, 0, 2016, -1.5)
    rock = node_mat("rock", lambda nt, b: _noise_color(nt, b, (0.12, 0.11, 0.1), (0.3, 0.28, 0.25), 3))
    for i in range(int((x1 - x0) / 6) + 12):
        prim("ico_sphere", (x0 - 30 + i * 6 + rng.uniform(-2, 2), rng.uniform(15, 18), -1.2),
             (rng.uniform(1, 3), rng.uniform(1, 2.5), rng.uniform(0.8, 2)), material=rock, subdivisions=2)
    # lighthouse
    white, red = mat("lh_w", (0.85, 0.85, 0.82), 0.4), mat("lh_r", (0.6, 0.04, 0.03), 0.4)
    lx, ly = 7, 26
    for k in range(5):
        prim("cylinder", (lx, ly, k * 3 + 1.5), (2.2 - k * 0.2, 2.2 - k * 0.2, 1.5), material=red if k % 2 else white)
    prim("cylinder", (lx, ly, 16.5), (1.4, 1.4, 1.5), material=mat("lamp", (1, 0.9, 0.6), emit=30 if time != "day" else 2))
    prim("cone", (lx, ly, 19), (1.8, 1.8, 1.2), material=red)
    if time != "day":
        beam = light("SPOT", (lx, ly, 16.5), 400000, (1, 0.9, 0.7), spot_size=math.radians(12), size=0.3)
        beam.rotation_euler = (math.radians(88), 0, 0)
        beam.animation_data_create(); d = beam.driver_add("rotation_euler", 2).driver
        d.expression = "frame*0.05"
        light("POINT", (lx, ly, 16.5), 3000, (1, 0.85, 0.6), size=1)
    # wooden fence along the cliff
    wood = mat("wood", (0.25, 0.14, 0.07), 0.7)
    post = prim("cube", (x0 - 30, 6, 0.5), (0.06, 0.06, 0.5), material=wood)
    for i in range(int((x1 - x0 + 60) / 2.5)):
        clone(post, (x0 - 30 + i * 2.5, 6 + math.sin(i * 0.3) * 0.3, 0.5))
    prim("cube", ((x0 + x1) / 2, 6, 0.8), ((x1 - x0 + 60) / 2, 0.03, 0.04), material=wood)
    _flowers(rng, x0, x1)


def _flowers(rng, x0, x1):
    cols = [mat(f"fl{i}", c, 0.5) for i, c in enumerate([(0.9, 0.85, 0.2), (0.8, 0.2, 0.3), (0.9, 0.9, 0.9)])]
    base = [prim("uv_sphere", (0, 0, -50), (0.06, 0.06, 0.04), material=c, segments=8, ring_count=6) for c in cols]
    for i in range(500):
        x, y = rng.uniform(x0 - 20, x1 + 20), rng.uniform(-30, 5)
        if abs(y) > 1.5:
            clone(base[i % 3], (x, y, 0.08))


def _noise_color(nt, b, c1, c2, scale):
    n = nt.nodes.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = scale
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].color = (*c1, 1); r.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(n.outputs["Fac"], r.inputs[0]); nt.links.new(r.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85


def set_city(time, rng, x0, x1):
    road = node_mat("road", lambda nt, b: _noise_color(nt, b, (0.015, 0.015, 0.017), (0.04, 0.04, 0.045), 30))
    road.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.15
    L = x1 - x0 + 300; cx = (x0 + x1) / 2
    ground(L, 12, road, cx, 0)
    stripe = mat("stripe", (0.8, 0.75, 0.6), 0.4)
    dash = prim("cube", (0, 0, 0.005), (1.2, 0.08, 0.005), material=stripe)
    for i in range(int(L / 6)):
        clone(dash, (cx - L / 2 + i * 6, 0, 0.005))
    walk = mat("pavement", (0.18, 0.18, 0.19), 0.6)
    ground(L, 6, walk, cx, 9, 0.15); ground(L, 6, walk, cx, -9, 0.15)
    ground(L, 300, mat("dark", (0.03, 0.03, 0.03), 0.9), cx, 170, 0.1)
    ground(L, 300, mat("dark2", (0.03, 0.03, 0.03), 0.9), cx, -170, 0.1)
    # buildings with lit windows
    def win(nt, b):
        br = nt.nodes.new("ShaderNodeTexBrick"); br.inputs["Scale"].default_value = 1.0
        br.inputs["Mortar Size"].default_value = 0.25; br.offset = 0
        br.inputs["Color1"].default_value = (1, 0.75, 0.4, 1); br.inputs["Color2"].default_value = (0.02, 0.02, 0.03, 1)
        br.inputs["Mortar"].default_value = (0.05, 0.05, 0.06, 1)
        tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (0.6, 0.6, 0.35)
        nt.links.new(tc.outputs["Object"], mp.inputs[0]); nt.links.new(mp.outputs[0], br.inputs["Vector"])
        nt.links.new(br.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = 2.5 if time == "night" else 0.4
        b.inputs["Base Color"].default_value = (0.08, 0.08, 0.09, 1); b.inputs["Roughness"].default_value = 0.3
    mats = [node_mat(f"bld{i}", win) for i in range(3)]
    for side, y in ((1, 18), (-1, -30)):
        x = x0 - 120
        while x < x1 + 120:
            w = rng.uniform(8, 16); h = rng.uniform(12, 55)
            prim("cube", (x + w / 2, y + side * 6, h / 2), (w / 2 - 0.4, 6, h / 2), material=rng.choice(mats))
            x += w
    pole = mat("pole", (0.1, 0.1, 0.1), 0.4, 0.8)
    bulb = mat("bulb", (1, 0.8, 0.5), emit=40)
    for i in range(int(L / 25)):
        x = cx - L / 2 + i * 25
        for y in (6.5, -6.5):
            prim("cylinder", (x, y, 3.5), (0.08, 0.08, 3.5), material=pole, vertices=8)
            prim("uv_sphere", (x, y * 0.85, 7), (0.25, 0.25, 0.15), material=bulb, segments=8, ring_count=6)
            if time != "day" and abs(x - (x0 + x1) / 2) < (x1 - x0) / 2 + 60:
                light("POINT", (x, y * 0.85, 6.8), 2500, (1, 0.75, 0.45), size=0.3)


def set_planet(time, rng, x0, x1):
    soil = node_mat("soil", lambda nt, b: _noise_color(nt, b, (0.25, 0.08, 0.04), (0.55, 0.25, 0.1), 2))
    g = ground(x1 - x0 + 600, 600, soil, (x0 + x1) / 2, 200, cuts=6, disp=(1.2, 6))
    crystal = mat("crystal", (0.2, 0.9, 1.0), 0.05, emit=6, emit_rgb=(0.1, 0.8, 1.0))
    rock = mat("prock", (0.18, 0.06, 0.05), 0.8)
    for i in range(140):
        x, y = rng.uniform(x0 - 80, x1 + 80), rng.uniform(-60, 120)
        if abs(y) < 4 or (-25 < y < 0 and abs(x) < 30):
            continue
        if i % 3 == 0:
            prim("cone", (x, y, 0), (0.3, 0.3, rng.uniform(1, 3)), rot=(rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), 0), material=crystal, vertices=6)
        else:
            s = rng.uniform(0.5, 4)
            prim("ico_sphere", (x, y, 0), (s, s * 0.8, s * 0.6), material=rock, subdivisions=2)
    # giant ringed planet in the sky
    pm = node_mat("gas", lambda nt, b: _noise_color(nt, b, (0.4, 0.3, 0.6), (0.9, 0.6, 0.4), 1.5))
    p = prim("uv_sphere", (-150, 900, 260), (180, 180, 180), material=pm, segments=64, ring_count=32)
    pm.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.5, 0.4, 0.7, 1)
    pm.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.4
    prim("torus", (-150, 900, 260), (1, 1, 0.02), rot=(0.3, 0.2, 0), material=mat("ring", (0.8, 0.7, 0.6), emit=0.5),
         major_radius=300, minor_radius=40)
    light("POINT", (0, 30, 3), 4000, (0.2, 0.8, 1.0), size=2)


def set_toytown(time, rng, x0, x1):
    ground(x1 - x0 + 300, 300, mat("toygrass", (0.2, 0.6, 0.1), 0.9), (x0 + x1) / 2, 100)
    ground(x1 - x0 + 300, 3, mat("path", (0.85, 0.7, 0.45), 0.9), (x0 + x1) / 2, 0, 0.01)
    pastel = [mat(f"p{i}", c, 0.6) for i, c in enumerate([(0.95, 0.6, 0.6), (0.6, 0.8, 0.95), (0.95, 0.9, 0.55), (0.7, 0.95, 0.7)])]
    roof = [mat(f"r{i}", c, 0.6) for i, c in enumerate([(0.8, 0.15, 0.1), (0.2, 0.3, 0.8)])]
    door, glass = mat("door", (0.4, 0.2, 0.1)), mat("glass", (0.9, 0.95, 1.0), 0.1, emit=2 if time == "night" else 0)
    x = x0 - 60
    while x < x1 + 60:
        for side in (1, -1):
            y = side * rng.uniform(10, 13); w = rng.uniform(3, 4.5); h = rng.uniform(3, 5)
            prim("cube", (x, y, h / 2), (w / 2, w / 2, h / 2), material=rng.choice(pastel), bevel=0.1)
            prim("cone", (x, y, h + 1.2), (w * 0.8, w * 0.8, 1.2), rot=(0, 0, math.pi / 4), material=rng.choice(roof), vertices=4)
            prim("cube", (x, y - side * w / 2, 1), (0.5, 0.05, 1), material=door)
            prim("cube", (x + w / 4, y - side * w / 2, h * 0.65), (0.4, 0.05, 0.4), material=glass)
        x += rng.uniform(9, 14)
    leaf = [mat(f"lf{i}", c, 0.7) for i, c in enumerate([(0.1, 0.5, 0.1), (0.3, 0.65, 0.1)])]
    trunk = mat("trunk", (0.35, 0.2, 0.08), 0.8)
    for i in range(80):
        x, y = rng.uniform(x0 - 60, x1 + 60), rng.choice([-1, 1]) * rng.uniform(4, 30)
        if -25 < y < -3 and abs(x) < 25:
            continue
        prim("cylinder", (x, y, 0.8), (0.18, 0.18, 0.8), material=trunk, vertices=8)
        s = rng.uniform(1, 1.6)
        prim("uv_sphere", (x, y, 2.2), (s, s, s), material=rng.choice(leaf), segments=16, ring_count=8)
    cloud = mat("cloud", (1, 1, 1), 0.9, emit=0.3)
    for i in range(14):
        cxp, cyp = rng.uniform(x0 - 100, x1 + 100), rng.uniform(60, 120)
        for k in range(4):
            s = rng.uniform(4, 7)
            prim("uv_sphere", (cxp + k * 5, cyp, 35 + rng.uniform(-2, 2)), (s, s * 0.8, s * 0.7), material=cloud)
    if time == "night":
        for x in range(int(x0) - 40, int(x1) + 40, 15):
            light("POINT", (x, 3, 3), 600, (1, 0.8, 0.5), size=0.5)


def set_room(time, rng, x0, x1):
    floor = node_mat("floor", lambda nt, b: _wood(nt, b))
    ground(20, 20, floor, 0, 0)
    wall = mat("wall", (0.75, 0.68, 0.58), 0.9)
    prim("cube", (0, 5, 3), (10, 0.1, 3), material=wall); prim("cube", (-8, 0, 3), (0.1, 10, 3), material=wall)
    prim("cube", (8, 0, 3), (0.1, 10, 3), material=wall); prim("cube", (0, 0, 6), (10, 10, 0.1), material=wall)
    sky_col = (0.6, 0.75, 1.0) if time == "day" else ((1, 0.5, 0.25) if time == "dusk" else (0.05, 0.08, 0.2))
    prim("cube", (2.5, 4.9, 3), (1.6, 0.05, 1.2), material=mat("window", sky_col, emit=4 if time != "night" else 1.5))
    light("AREA", (2.5, 4.6, 3), 400 if time != "night" else 40, sky_col, rot=(math.radians(90), 0, 0), size=3)
    wood = mat("table", (0.3, 0.16, 0.07), 0.5)
    prim("cube", (-3, 2.5, 0.75), (1.2, 0.7, 0.05), material=wood)
    for dx in (-1.1, 1.1):
        for dy in (-0.6, 0.6):
            prim("cube", (-3 + dx, 2.5 + dy, 0.37), (0.05, 0.05, 0.37), material=wood)
    prim("cylinder", (-3.6, 2.5, 1.0), (0.1, 0.1, 0.25), material=mat("lampb", (0.2, 0.2, 0.2)))
    prim("cone", (-3.6, 2.5, 1.35), (0.3, 0.3, 0.2), material=mat("shade", (1, 0.85, 0.6), emit=3))
    light("POINT", (-3.6, 2.5, 1.3), 120 if time == "night" else 40, (1, 0.7, 0.4), size=0.2)
    prim("cube", (5, 4.5, 1.6), (1.5, 0.35, 1.6), material=wood)  # shelf
    books = [mat(f"bk{i}", c) for i, c in enumerate([(0.6, 0.1, 0.1), (0.1, 0.3, 0.6), (0.7, 0.6, 0.2)])]
    for i in range(14):
        prim("cube", (3.7 + i * 0.18, 4.3, 2.0 + (i % 2) * 0.9), (0.07, 0.2, 0.25), material=books[i % 3])
    prim("cylinder", (6, 1, 0.3), (0.3, 0.3, 0.3), material=mat("pot", (0.6, 0.3, 0.15)))
    prim("uv_sphere", (6, 1, 1.0), (0.6, 0.6, 0.6), material=mat("plant", (0.1, 0.4, 0.1)))
    prim("cube", (0, 1, 0.01), (2.5, 1.6, 0.01), material=mat("rug", (0.5, 0.12, 0.15), 0.95))
    light("POINT", (0, 0, 5.5), 300 if time != "night" else 80, (1, 0.9, 0.8), size=1)


def _wood(nt, b):
    w = nt.nodes.new("ShaderNodeTexWave"); w.inputs["Scale"].default_value = 3; w.inputs["Distortion"].default_value = 8
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].color = (0.15, 0.07, 0.03, 1); r.color_ramp.elements[1].color = (0.4, 0.22, 0.1, 1)
    nt.links.new(w.outputs["Fac"], r.inputs[0]); nt.links.new(r.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.35


def set_forest(time, rng, x0, x1):
    moss = node_mat("moss", lambda nt, b: _noise_color(nt, b, (0.04, 0.1, 0.02), (0.12, 0.16, 0.05), 4))
    ground(x1 - x0 + 300, 300, moss, (x0 + x1) / 2, 60, cuts=5, disp=(0.5, 5))
    ground(x1 - x0 + 300, 2.5, mat("dirt", (0.2, 0.13, 0.07), 0.9), (x0 + x1) / 2, 0, 0.12)
    bark, needles = mat("bark", (0.15, 0.08, 0.04), 0.9), mat("needles", (0.03, 0.15, 0.05), 0.8)
    trunk = prim("cylinder", (0, 0, -100), (0.3, 0.3, 4), material=bark, vertices=8)
    crown = prim("cone", (0, 0, -100), (2.2, 2.2, 5), material=needles, vertices=10)
    for i in range(500):
        x, y = rng.uniform(x0 - 80, x1 + 80), rng.uniform(-90, 90)
        if abs(y) < 3.5 or (-30 < y < 0 and abs(x - (x0 + x1) / 2) < 10):
            continue
        s = rng.uniform(0.7, 1.5)
        clone(trunk, (x, y, 4 * s), (0.3 * s, 0.3 * s, 4 * s)); clone(crown, (x, y, 9 * s), (2.2 * s, 2.2 * s, 5 * s))
    if time == "night":  # fireflies
        ff = mat("firefly", (1, 0.9, 0.3), emit=60)
        for i in range(120):
            prim("uv_sphere", (rng.uniform(x0 - 20, x1 + 20), rng.uniform(-8, 15), rng.uniform(0.5, 3)),
                 (0.03, 0.03, 0.03), material=ff, segments=6, ring_count=4)
        light("POINT", (0, 2, 3), 150, (1, 0.8, 0.4), size=2)


SETS = {"coast": set_coast, "city": set_city, "planet": set_planet, "toytown": set_toytown,
        "room": set_room, "forest": set_forest}


# ---------------------------------------------------------------- weather (stateless, no simulation)
def weather(kind, focus, n):
    if kind not in ("rain", "snow"):
        return
    rng = random.Random(7)
    verts, faces = [], []
    for i in range(6000 if kind == "rain" else 3000):
        x, y, z = rng.uniform(-15, 15), rng.uniform(-15, 15), rng.uniform(0, 12)
        if kind == "rain":
            h, w = 0.35, 0.006
            vs = [(x - w, y, z), (x + w, y, z), (x + w, y, z + h), (x - w, y, z + h)]
        else:
            s = 0.02
            vs = [(x - s, y, z - s), (x + s, y, z - s), (x + s, y, z + s), (x - s, y, z + s)]
        faces.append(tuple(range(len(verts), len(verts) + 4))); verts += vs
    me = bpy.data.meshes.new("drops"); me.from_pydata(verts, [], faces)
    me.materials.append(mat("drop", (0.8, 0.85, 0.9), emit=0.8 if kind == "rain" else 1.5, alpha=0.6))
    speed = 0.45 if kind == "rain" else 0.04
    for k in (0, 1):
        o = bpy.data.objects.new("drops", me); bpy.context.scene.collection.objects.link(o)
        o.parent = focus
        d = o.driver_add("location", 2).driver
        d.expression = f"{12 * k - 4} - ((frame*{speed}) % 12)"


# ---------------------------------------------------------------- robots
def robot(c, story_lines, n, slot_count):
    col = COLORS.get(c["color"], COLORS["orange"]); shape = c.get("shape", "box")
    body = mat(f"body_{c['id']}", col, 0.3, 0.55); dark = mat(f"joint_{c['id']}", (0.06, 0.06, 0.07), 0.4, 0.8)
    eye = mat(f"eye_{c['id']}", (0.4, 0.95, 1.0), emit=12)
    mouth = mat(f"mouth_{c['id']}", (0.4, 0.95, 1.0), emit=0.5)
    leg_h, torso_h = (0.6, 0.7) if shape == "tall" else (0.42, 0.55)
    root = empty(f"bot_{c['id']}")
    hips = empty("hips", (0, 0, leg_h), root)
    if shape == "round":
        prim("uv_sphere", (0, 0, torso_h / 2), (0.33, 0.3, torso_h / 2 + 0.03), material=body, parent=hips)
    else:
        prim("cube", (0, 0, torso_h / 2), (0.26, 0.18, torso_h / 2), material=body, parent=hips, bevel=0.06)
    prim("cylinder", (0, -0.19 if shape != "round" else -0.3, torso_h * 0.55), (0.07, 0.07, 0.02),
         rot=(math.pi / 2, 0, 0), material=eye, parent=hips)  # chest light
    neck = empty("neck", (0, 0, torso_h + 0.02), hips)
    prim("cylinder", (0, 0, 0.04), (0.06, 0.06, 0.05), material=dark, parent=neck)
    head = empty("head", (0, 0, 0.09), neck)
    if shape == "round":
        prim("uv_sphere", (0, 0, 0.2), (0.24, 0.22, 0.2), material=body, parent=head)
    else:
        prim("cube", (0, 0, 0.19), (0.22, 0.18, 0.18), material=body, parent=head, bevel=0.05)
    prim("cube", (0, -0.17, 0.2), (0.17, 0.02, 0.1), material=mat("visor", (0.01, 0.01, 0.015), 0.1), parent=head)
    eyes = [prim("uv_sphere", (sx * 0.075, -0.19, 0.22), (0.035, 0.015, 0.045), material=eye, parent=head,
                 segments=12, ring_count=8) for sx in (-1, 1)]
    prim("cube", (0, -0.19, 0.14), (0.05, 0.008, 0.008), material=mouth, parent=head)
    prim("cylinder", (0.1, 0, 0.45), (0.01, 0.01, 0.08), material=dark, parent=head)
    prim("uv_sphere", (0.1, 0, 0.54), (0.03, 0.03, 0.03), material=eye, parent=head)
    arms, legs = [], []
    for sx in (-1, 1):
        a = empty("arm", (sx * 0.3, 0, torso_h - 0.06), hips)
        prim("uv_sphere", (0, 0, 0), (0.06, 0.06, 0.06), material=dark, parent=a)
        prim("cylinder", (0, 0, -0.22), (0.045, 0.045, 0.2), material=body, parent=a)
        prim("uv_sphere", (0, 0, -0.45), (0.06, 0.06, 0.06), material=dark, parent=a)
        arms.append(a)
        lg = empty("leg", (sx * 0.12, 0, 0), hips)
        prim("cylinder", (0, 0, -leg_h / 2), (0.055, 0.055, leg_h / 2), material=dark, parent=lg)
        prim("cube", (0, -0.05, -leg_h + 0.03), (0.08, 0.13, 0.03), material=body, parent=lg, bevel=0.02)
        legs.append(lg)
    return dict(root=root, hips=hips, head=head, neck=neck, arms=arms, legs=legs, eyes=eyes,
                eye=eye, mouth=mouth, height=leg_h + torso_h + 0.5)


def animate(bot, action, start, facing, n, talk):
    """Key the robot for n frames. talk = list of (from, to) frame ranges when it speaks."""
    r, hips, neck, arms, legs = bot["root"], bot["hips"], bot["neck"], bot["arms"], bot["legs"]
    base_h = hips.location.z
    sp = SPEED.get(action, 0) / FPS
    dirv = Vector((math.cos(facing + math.pi / 2), math.sin(facing + math.pi / 2), 0)) * -1  # robot front = -Y
    eye_n = bot["eye"].node_tree.nodes["Principled BSDF"]; m_n = bot["mouth"].node_tree.nodes["Principled BSDF"]
    if action == "sad":
        eye_n.inputs["Emission Color"].default_value = (0.2, 0.35, 1.0, 1)
        eye_n.inputs["Emission Strength"].default_value = 5
    for f in range(0, n + 1, 2):
        t = f / FPS; fr = f + 1
        pos = Vector(start) + dirv * sp * f
        r.location = pos; r.rotation_euler = (0, 0, facing)
        bob, lean, hz, hx = 0.0, 0.0, 0.0, 0.0
        arm = [0.0, 0.0]; arm_side = [0.0, 0.0]; leg = [0.0, 0.0]
        breathe = 0.01 * math.sin(t * 2)
        if action in ("walk", "run"):
            ph = t * (7.5 if action == "walk" else 13)
            sw = 0.5 if action == "walk" else 0.9
            leg = [math.sin(ph) * sw, -math.sin(ph) * sw]; arm = [-leg[0] * 0.8, -leg[1] * 0.8]
            bob = abs(math.sin(ph)) * (0.03 if action == "walk" else 0.08)
            lean = 0.0 if action == "walk" else 0.2
        elif action == "wave":
            arm_side[1] = 2.6 + 0.35 * math.sin(t * 9); hz = 0.15
        elif action == "look":
            hz = 0.7 * math.sin(t * 1.3); hx = 0.1 * math.sin(t * 0.7)
        elif action == "jump":
            ph = (t % 1.2) / 1.2
            bob = max(0.0, math.sin(ph * math.pi * 1.3)) * 0.6
            arm_side = [1.2 * bob / 0.6 + 0.2] * 2; leg = [0.3 * bob, 0.3 * bob]
        elif action == "dance":
            hz = 0.3 * math.sin(t * 6); bob = 0.05 * abs(math.sin(t * 6))
            arm_side = [1.5 + math.sin(t * 6), 1.5 - math.sin(t * 6)]
            r.rotation_euler = (0, 0, facing + 0.4 * math.sin(t * 3))
        elif action == "sad":
            hx = 0.45; lean = 0.15; arm = [0.1, 0.1]; bob = -0.03
        elif action == "fall":
            k = min(1.0, max(0.0, (t - 0.8) / 0.5)) ** 2
            r.rotation_euler = (-k * math.pi / 2 * 0.95, 0, facing)
            arm_side = [k * 1.4, k * 1.4]
        else:  # idle / talk
            hz = 0.12 * math.sin(t * 0.6); hx = 0.04 * math.sin(t * 0.9)
            if action == "talk" or any(a <= fr <= b for a, b in talk):
                arm = [0.0, -0.6 - 0.25 * math.sin(t * 4)]; arm_side = [0.0, 0.2]
        speaking = any(a <= fr <= b for a, b in talk)
        if speaking:
            hx += 0.05 * math.sin(t * 11)
        hips.location = (0, 0, base_h + bob + breathe); hips.rotation_euler = (lean, 0, 0)
        neck.rotation_euler = (hx, 0, hz)
        for i in (0, 1):
            arms[i].rotation_euler = (arm[i], arm_side[i] if i == 0 else -arm_side[i], 0)
            legs[i].rotation_euler = (leg[i], 0, 0)
            arms[i].keyframe_insert("rotation_euler", frame=fr); legs[i].keyframe_insert("rotation_euler", frame=fr)
        for o, p in ((r, "location"), (r, "rotation_euler"), (hips, "location"), (hips, "rotation_euler"), (neck, "rotation_euler")):
            o.keyframe_insert(p, frame=fr)
        m_n.inputs["Emission Strength"].default_value = (8 + 6 * math.sin(t * 25)) if speaking else 0.5
        m_n.inputs["Emission Strength"].keyframe_insert("default_value", frame=fr)
    # blink
    for e in bot["eyes"]:
        for f in range(int(FPS * 1.5), n, int(FPS * 3.1)):
            for df, s in ((0, 0.045), (2, 0.005), (4, 0.045)):
                e.scale.z = s; e.keyframe_insert("scale", index=2, frame=f + df + 1)
    return lambda f: Vector(start) + dirv * sp * f


# ---------------------------------------------------------------- vehicles
def car(assets, color, lights=True):
    root = empty("car")
    files = glob.glob(f"{assets}/model/*.glb")
    L = 4.6
    if files and color is None:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=files[0])
        new = [o for o in bpy.data.objects if o not in before]
        holder = empty("holder")
        for o in new:
            if o.parent is None:
                o.parent = holder
        def bounds():
            bpy.context.view_layer.update()
            pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
            return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))
        mn, mx = bounds(); size = mx - mn
        if size.z > max(size.x, size.y):
            holder.rotation_euler.x = math.pi / 2; mn, mx = bounds(); size = mx - mn
        if size.y > size.x:
            holder.rotation_euler.z = math.pi / 2; mn, mx = bounds(); size = mx - mn
        s = L / size.x; holder.scale = (s, s, s); mn, mx = bounds()
        holder.location -= Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z)); holder.parent = root
        W, H = mx.y - mn.y, mx.z - mn.z
    else:
        paint = mat("paint", color or (0.6, 0.02, 0.02), 0.2, 0.7)
        glass = mat("cglass", (0.02, 0.02, 0.03), 0.05)
        prim("cube", (0, 0, 0.6), (2.3, 0.95, 0.3), material=paint, parent=root, bevel=0.15)
        prim("cube", (-0.3, 0, 1.05), (1.2, 0.85, 0.25), material=glass, parent=root, bevel=0.15)
        tyre = mat("tyre", (0.02, 0.02, 0.02), 0.8)
        for x in (-1.45, 1.45):
            for y in (-0.9, 0.9):
                w = prim("cylinder", (x, y, 0.35), (0.35, 0.35, 0.15), rot=(math.pi / 2, 0, 0), material=tyre, parent=root)
                w.driver_add("rotation_euler", 1).driver.expression = "frame*0.9"
        W, H = 1.9, 1.3
    if lights:
        for side in (1, -1):
            hl = light("SPOT", (L / 2 + 0.1, side * W * 0.32, H * 0.4), 3000, (1, 0.95, 0.85),
                       rot=(0, math.radians(-95), 0), parent=root, spot_size=math.radians(45), size=0.05)
            light("POINT", (-L / 2 - 0.05, side * W * 0.36, H * 0.5), 20, (1, 0.05, 0.02), parent=root, size=0.1)
            prim("uv_sphere", (L / 2 - 0.02, side * W * 0.32, H * 0.45), (0.05, 0.15, 0.06), material=mat("hl", (1, 1, 0.9), emit=40), parent=root)
            prim("uv_sphere", (-L / 2 + 0.02, side * W * 0.34, H * 0.55), (0.04, 0.18, 0.05), material=mat("tl", (1, 0.02, 0.02), emit=25), parent=root)
    return root


def ship():
    root = empty("ship")
    hull = mat("hull", (0.75, 0.77, 0.8), 0.25, 0.8); acc = mat("acc", (0.9, 0.3, 0.05), 0.3, 0.5)
    glow = mat("engine", (0.3, 0.7, 1.0), emit=60)
    prim("uv_sphere", (0, 0, 0), (6, 1.5, 1.2), material=hull, parent=root, segments=48, ring_count=24)
    prim("uv_sphere", (2.8, 0, 0.7), (1.6, 0.9, 0.6), material=mat("canopy", (0.05, 0.15, 0.25), 0.05, 0.3), parent=root)
    for s in (1, -1):
        prim("cube", (-1, s * 3.2, -0.2), (2.2, 2.2, 0.1), rot=(0, 0, s * 0.5), material=hull, parent=root, bevel=0.05)
        prim("cube", (-2.3, s * 5.0, 0.2), (1.2, 0.1, 0.6), material=acc, parent=root, bevel=0.03)
        prim("cylinder", (-5, s * 1.1, 0), (0.6, 0.6, 1.0), rot=(0, math.pi / 2, 0), material=hull, parent=root)
        prim("cylinder", (-6.05, s * 1.1, 0), (0.5, 0.5, 0.05), rot=(0, math.pi / 2, 0), material=glow, parent=root)
        light("POINT", (-6.6, s * 1.1, 0), 3000, (0.3, 0.7, 1.0), parent=root, size=0.5)
    return root


# ---------------------------------------------------------------- camera
def camera(shot, focus, scale, n, rng, ots):
    cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd)
    bpy.context.scene.collection.objects.link(cam); bpy.context.scene.camera = cam
    cd.clip_end = 5000
    tgt = empty("target", parent=focus)
    tr = cam.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
    kind, S = shot["camera"], scale
    lens, fstop = 35, 4.0
    side = rng.choice([-1, 1])
    def path(u):
        if kind == "establish":
            return Vector((side * (16 - 4 * u), -22 + 3 * u, 6 - u)) * (0.45 if S == 1 else 0.6 * S)
        if kind == "push_in":
            return Vector((0.4 * side, -6.5 + 3.2 * u, 1.5)) * S
        if kind == "orbit":
            a = math.radians(-90 + side * (-35 + 70 * u)); return Vector((4.5 * math.cos(a), 4.5 * math.sin(a), 1.7)) * S
        if kind == "track":
            return Vector((-0.6 * side, -4.2, 1.25)) * S
        if kind == "closeup":
            return Vector((0.25 * side, -1.9 + 0.2 * u, 1.25)) * S
        if kind == "low_angle":
            return Vector((1.2 * side, -2.8 - 0.4 * u, 0.25)) * S
        if kind == "crane_up":
            return Vector((0.5 * side, -5 - 2 * u, 0.8 + 5 * u)) * S
        if kind == "handheld":
            return Vector((0.6 * side, -3.6 + 0.6 * u, 1.4)) * S
        if kind == "top_down":
            return Vector((0, -0.6, 9 - 2 * u)) * S
        if kind == "over_shoulder":
            return ots if ots is not None else Vector((0.7, -3, 1.5)) * S
        return Vector((0, -5, 1.6)) * S
    lens = {"establish": 24, "closeup": 75, "over_shoulder": 50, "low_angle": 22, "crane_up": 28,
            "top_down": 32, "orbit": 35, "push_in": 40, "track": 35, "handheld": 32}[kind]
    fstop = {"closeup": 2.0, "over_shoulder": 2.8, "push_in": 3.5}.get(kind, 6.0)
    cd.lens = lens; cd.dof.use_dof = kind != "establish"; cd.dof.focus_object = tgt; cd.dof.aperture_fstop = fstop
    tgt.location = (0, 0, (0.3 if kind == "establish" else 0.0))
    cam.parent = focus
    for f in range(0, n + 1, 3):
        u = f / max(n, 1); u = u * u * (3 - 2 * u)
        p = path(u)
        if kind == "handheld" or (shot["vehicle"] == "car_chase"):
            p += Vector((math.sin(f * 0.21) * 0.03 + math.sin(f * 0.53) * 0.02,
                         math.sin(f * 0.17) * 0.02, math.sin(f * 0.37) * 0.025)) * S * 1.5
        cam.location = p; cam.keyframe_insert("location", frame=f + 1)
    return cam


# ---------------------------------------------------------------- one shot
def build_shot(story, i, assets, quality):
    shot = story["shots"][i]; n = shot["frames"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; rng = random.Random(1000 + i)
    sc.frame_start, sc.frame_end, sc.render.fps = 1, n, FPS
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
    draft = quality == "draft"
    # GitHub runners have 4 CPU cores: 720p + denoiser keeps a 5 min film inside the 6 h job limit
    # (the editor upscales to 1080p). Set FILM_SAMPLES / FILM_RES on faster machines.
    sc.cycles.samples = int(os.environ.get("FILM_SAMPLES", 8 if draft else 14))
    sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.05
    sc.cycles.use_denoising = True; sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2; sc.cycles.transmission_bounces = 2; sc.cycles.light_sampling_threshold = 0.05
    res = int(os.environ.get("FILM_RES", 540 if draft else 720))
    sc.render.resolution_x, sc.render.resolution_y = res * 16 // 9, res
    sc.render.use_persistent_data = True
    sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.5
    sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 92
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Punchy" if story.get("genre") == "comedy" else "AgX - Medium High Contrast"
    except TypeError:
        pass
    time_, set_name = shot["time"], shot["set"]
    sky(time_, set_name, rng)
    veh = shot["vehicle"]
    # how far does the action travel?
    travel = 0.0
    if veh.startswith("car"):
        travel = (25 if veh == "car_chase" else 14) * n / FPS
    elif veh == "ship_fly":
        travel = 30 * n / FPS
    else:
        travel = max([SPEED.get(c["action"], 0) * n / FPS for c in shot["characters"]] + [0])
    if set_name == "room":
        travel = min(travel, 7)
    x0 = -travel / 2
    SETS[set_name](time_, rng, x0 - 20, x0 + travel + 20)
    focus = empty("focus"); scale = 1.0; ots = None
    talk = {}
    for ln in shot["lines"]:
        a = int(ln["at"] * FPS) + 1; talk.setdefault(ln["speaker"], []).append((a, a + int(ln["len"] * FPS)))
    if veh.startswith("car"):
        v = 25 if veh == "car_chase" else 14
        hero = car(assets, None); cars = [(hero, 0.0)]
        if veh == "car_chase":
            cop = car(assets, (0.05, 0.05, 0.08))
            bar = [prim("cube", (0, s * 0.3, 1.4), (0.1, 0.25, 0.06), material=mat(f"siren{s}", c, emit=0), parent=cop)
                   for s, c in ((1, (1, 0, 0)), (-1, (0, 0.2, 1)))]
            for k, b in enumerate(bar):
                nd = b.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
                for f in range(0, n + 1, 3):
                    nd.default_value = 80 if (f // 6 + k) % 2 else 0; nd.keyframe_insert("default_value", frame=f + 1)
            cars.append((cop, -14.0))
        for c, off in cars:
            for f in (1, n + 1):
                c.location = (x0 + off + v * (f - 1) / FPS, -1.8, 0)
                c.keyframe_insert("location", frame=f)
            for fc in c.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
            c.driver_add("location", 2).driver.expression = "0.012*sin(frame*1.7)"
            c.driver_add("rotation_euler", 2).driver.expression = "0.03*sin(frame*0.13)"
        for f in (1, n + 1):
            focus.location = (x0 - (5 if veh == "car_chase" else 0) + v * (f - 1) / FPS, 0, 0.6)
            focus.keyframe_insert("location", frame=f)
        scale = 2.2
    elif veh.startswith("ship"):
        sh = ship(); scale = 5.0
        for f in range(0, n + 1, 3):
            u = f / max(n, 1)
            if veh == "ship_fly":
                p = Vector((x0 + 30 * f / FPS, 0, 14 + 2 * math.sin(u * 3)))
                sh.rotation_euler = (0.25 * math.sin(u * 4), 0, 0)
            else:
                k = 1 - (1 - u) ** 3; p = Vector((x0 + 40 * (1 - k), 25, 30 * (1 - k) + 1.6))
                sh.rotation_euler = (0, 0.2 * (1 - k), 0)
            sh.location = p; sh.keyframe_insert("location", frame=f + 1); sh.keyframe_insert("rotation_euler", frame=f + 1)
            focus.location = p; focus.keyframe_insert("location", frame=f + 1)
        if veh == "ship_land":
            light("POINT", (x0, 25, 0.5), 20000, (0.3, 0.7, 1.0), size=3)
    chars = shot["characters"]
    if chars and not veh.startswith("car") and veh != "ship_fly":
        movers = [c for c in chars if c["action"] in SPEED]
        bots, getpos, follow = [], [], []
        for k, ch in enumerate(chars):
            cast = story["cast"][ch["id"]]; b = robot(cast, shot["lines"], n, len(chars))
            two = len(chars) == 2
            sx = (-0.85 if k == 0 else 0.85) if two else 0.0
            if ch["action"] in SPEED:
                facing = math.pi / 2  # walking towards +X
                start = (x0 + (k * -1.2), -0.3 + sx * 0.6, 0)
            else:
                facing = (math.radians(55) if k == 0 else math.radians(-55)) if two else 0.0
                if movers:
                    facing = math.pi / 2
                start = (sx + (x0 if movers else 0), 0, 0)
            gp = animate(b, ch["action"], start, facing, n, talk.get(ch["id"], []))
            bots.append(b); getpos.append(gp)
            if not movers or ch["action"] in SPEED:
                follow.append(gp)
        h = max(b["height"] for b in bots)
        for f in range(0, n + 1, 3):
            pts = [gp(f) for gp in follow]
            c = sum(pts, Vector()) / len(pts); focus.location = (c.x, c.y, h * 0.72)
            focus.keyframe_insert("location", frame=f + 1)
        if shot["camera"] == "over_shoulder" and len(bots) == 2:
            # behind the first speaker, looking at the other
            spk = shot["lines"][0]["speaker"] if shot["lines"] else chars[0]["id"]
            a, b = (1, 0) if chars[0]["id"] == spk else (0, 1)
            pa, pb = getpos[a](0), getpos[b](0); d = (pa - pb).normalized()
            ots = (pa + d * 2.2 + Vector((0, 0, h * 1.05)) + Vector((-d.y, d.x, 0)) * 0.7) - Vector(focus.location)
            ots = Vector((ots.x, ots.y, ots.z))
    elif not veh.startswith(("car", "ship")):
        focus.location = (0, 3, 1.5)
    weather(shot["weather"], focus, n)
    cam = camera(shot, focus, scale, n, rng, ots)
    # soft key + rim light that follow the camera so the actors always read
    light("AREA", (1.5, 0.5, 0.8), (25 if time_ == "day" else 60) * scale * scale, (1, 0.95, 0.9), size=2.5 * scale, parent=cam)
    rim = light("AREA", (0, 3 * scale, 3 * scale), 120 * scale * scale, (0.7, 0.8, 1.0) if time_ != "dusk" else (1, 0.6, 0.35),
                rot=(math.radians(-130), 0, 0), size=3 * scale, parent=focus)
    # mist / fog in the compositor
    sc.view_layers[0].use_pass_mist = True
    w = sc.world; w.mist_settings.start = 3 if shot["weather"] == "fog" else 25
    w.mist_settings.depth = 35 if shot["weather"] == "fog" else (250 if set_name != "room" else 1000)
    sc.use_nodes = True; nt = sc.node_tree
    rl, comp = nt.nodes["Render Layers"], nt.nodes["Composite"]
    mix = nt.nodes.new("CompositorNodeMixRGB")
    fogc = {"day": (0.7, 0.75, 0.8), "dusk": (0.75, 0.45, 0.3), "night": (0.03, 0.04, 0.07)}[time_]
    if set_name == "planet":
        fogc = (0.4, 0.15, 0.1) if time_ != "night" else (0.05, 0.03, 0.06)
    mix.inputs[2].default_value = (*fogc, 1)
    mul = nt.nodes.new("CompositorNodeMath"); mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 0.85 if shot["weather"] == "fog" else 0.45
    nt.links.new(rl.outputs["Mist"], mul.inputs[0]); nt.links.new(mul.outputs[0], mix.inputs[0])
    nt.links.new(rl.outputs["Image"], mix.inputs[1]); nt.links.new(mix.outputs[0], comp.inputs[0])
    return n


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    chunk, chunks, assets = int(argv[0]), int(argv[1]), argv[2]
    quality = argv[3] if len(argv) > 3 else "final"
    only = [int(x) for x in os.environ.get("FILM_ONLY_SHOTS", "").split(",") if x.strip()]
    story = json.load(open(f"{assets}/story.json"))
    total = story["frames"]
    os.makedirs(f"{assets}/frames", exist_ok=True)
    for i, s in enumerate(story["shots"]):
        lo, hi = s["start"], s["start"] + s["frames"]
        # frames are dealt out like cards (frame g goes to machine g % chunks) so every machine
        # gets the same mix of heavy and light shots
        mine = [g for g in range(lo, hi) if g % chunks == chunk]
        if os.environ.get("FILM_STILLS"):  # one frame from the middle of every shot (quick check)
            mine = [(lo + hi) // 2] if i % chunks == chunk else []
        if not mine or (only and i not in only):
            continue
        print(f"shot {i}: {s['set']}/{s['time']}/{s['camera']} - {len(mine)} frames", flush=True)
        build_shot(story, i, assets, quality)
        sc = bpy.context.scene
        for g in mine:
            sc.frame_set(g - s["start"] + 1)
            sc.render.filepath = f"{assets}/frames/f_{g:05d}.jpg"
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
    sys.stdout.flush(); os._exit(0)  # skip Blender's teardown (it can crash after the last render)
