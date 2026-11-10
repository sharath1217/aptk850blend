"""Racing module for shots.py: a full race circuit, race cars driven by the series' robots,
race events (start, pack racing, overtake, crash, finish) and TV-style race cameras.
Everything is a pure function of the frame, so any render machine can render any frame."""
import bpy, math, random
from mathutils import Vector

FPS = 24
V = 52.0          # racing speed, m/s (~190 km/h)
WIDTH = 14.0      # track width
# circuit control points (metres): long main straight, hairpin, esses, fast sweeper (~1.6 km)
CTRL = [(0, 0), (260, 0), (330, 20), (350, 90), (310, 150), (250, 160), (200, 210), (230, 280),
        (180, 330), (60, 320), (-40, 260), (-60, 170), (-120, 120), (-130, 50), (-80, 5)]


def _catmull(p0, p1, p2, p3, t):
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


def _samples():
    pts = [Vector((x, y, 0)) for x, y in CTRL]; out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        for k in range(40):
            out.append(_catmull(p0, p1, p2, p3, k / 40))
    return out


PTS = _samples()
CUM = [0.0]
for a, b in zip(PTS, PTS[1:] + PTS[:1]):
    CUM.append(CUM[-1] + (b - a).length)
LENGTH = CUM[-1]


def at(d):
    """Point and unit tangent at distance d along the racing line (wraps around the lap)."""
    d %= LENGTH
    lo, hi = 0, len(PTS)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if CUM[mid] <= d else (lo, mid)
    a, b = PTS[lo], PTS[(lo + 1) % len(PTS)]
    u = (d - CUM[lo]) / max(CUM[lo + 1] - CUM[lo], 1e-6)
    t = (b - a).normalized()
    return a.lerp(b, u), t


def frame_at(d, lane):
    p, t = at(d); n = Vector((-t.y, t.x, 0))
    return p + n * lane, t


# ------------------------------------------------------------------ the circuit
def build_track(time, mat, prim, light, rng, ground):
    S = len(PTS)
    def strip(name, inner, outer, z, material, every=1, seg_mats=None):
        verts, faces, mids = [], [], []
        for i in range(0, S, every):
            p, t = PTS[i], (PTS[(i + 1) % S] - PTS[i]).normalized(); n = Vector((-t.y, t.x, 0))
            verts += [p + n * inner + Vector((0, 0, z)), p + n * outer + Vector((0, 0, z))]
        m = len(verts) // 2
        for i in range(m):
            j = (i + 1) % m
            faces.append((2 * i, 2 * i + 1, 2 * j + 1, 2 * j)); mids.append(i)
        me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces)
        for mm in (seg_mats or [material]):
            me.materials.append(mm)
        if seg_mats:
            for k, poly in enumerate(me.polygons):
                poly.material_index = (k // 2) % len(seg_mats)
        o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
        return o
    asphalt = mat("tarmac", (0.035, 0.035, 0.04), 0.35 if time != "night" else 0.25)
    strip("road", -WIDTH / 2, WIDTH / 2, 0.02, asphalt)
    white = mat("kw", (0.9, 0.9, 0.9), 0.5); red = mat("kr", (0.75, 0.03, 0.03), 0.5)
    strip("kerbL", WIDTH / 2, WIDTH / 2 + 1.2, 0.05, None, seg_mats=[red, white])
    strip("kerbR", -WIDTH / 2 - 1.2, -WIDTH / 2, 0.05, None, seg_mats=[red, white])
    strip("lineL", WIDTH / 2 - 0.5, WIDTH / 2 - 0.3, 0.025, white)
    strip("lineR", -WIDTH / 2 + 0.3, -WIDTH / 2 + 0.5, 0.025, white)
    barrier = mat("barrier", (0.75, 0.75, 0.78), 0.4, 0.6)
    _walls(barrier)
    ground(4000, 4000, mat("infield", (0.09, 0.25, 0.05), 0.9), 100, 150, -0.02)
    # start / finish line and grid boxes
    check = bpy.data.materials.new("checker"); check.use_nodes = True
    nt = check.node_tree; ct = nt.nodes.new("ShaderNodeTexChecker"); ct.inputs["Scale"].default_value = 14
    ct.inputs["Color1"].default_value = (0.9, 0.9, 0.9, 1); ct.inputs["Color2"].default_value = (0.01, 0.01, 0.01, 1)
    nt.links.new(ct.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    prim("plane", (0, 0, 0.03), (1.0, WIDTH / 2, 1), material=check)
    for k in range(6):
        prim("plane", (-12 - k * 10, (k % 2 * 2 - 1) * 3, 0.03), (0.15, 1.4, 1), material=white)
    # start gantry with 5 lights
    steel = mat("gantry", (0.15, 0.15, 0.17), 0.4, 0.8)
    for y in (WIDTH / 2 + 1, -WIDTH / 2 - 1):
        prim("cube", (2, y, 4), (0.3, 0.3, 4), material=steel)
    prim("cube", (2, 0, 8), (0.4, WIDTH / 2 + 1.5, 0.6), material=steel)
    lamps = []
    for k in range(5):
        lm = mat(f"startlamp{k}", (1, 0.02, 0.02), emit=0.0)
        prim("uv_sphere", (1.55, -3 + k * 1.5, 8), (0.35, 0.35, 0.35), material=lm, segments=12, ring_count=8)
        lamps.append(lm)
    sponsor = [mat(f"sp{i}", c, 0.4, emit=1.5) for i, c in enumerate([(0.9, 0.5, 0.0), (0.0, 0.5, 0.9), (0.9, 0.9, 0.1)])]
    for k in range(10):
        d = k * LENGTH / 10 + 40
        p, t = frame_at(d, WIDTH / 2 + 8.5)
        prim("cube", (p.x, p.y, 1.6), (4, 0.15, 1), rot=(0, 0, math.atan2(t.y, t.x)), material=sponsor[k % 3])
    _grandstand(prim, mat, rng)
    if time == "night":  # floodlights all round the lap
        for k in range(24):
            p, t = frame_at(k * LENGTH / 24, -(WIDTH / 2 + 14))
            prim("cylinder", (p.x, p.y, 10), (0.25, 0.25, 10), material=steel, vertices=8)
            prim("cube", (p.x, p.y, 20.3), (1.2, 0.3, 0.6), material=mat(f"fl{k}", (1, 1, 0.95), emit=30))
            light("SPOT", (p.x, p.y, 20), 60000, (1, 0.97, 0.9), rot=(math.radians(35), 0, math.atan2(t.y, t.x) - math.pi / 2),
                  spot_size=math.radians(100), size=1.0)
    return lamps


def _walls(material):
    verts, faces = [], []
    S = len(PTS)
    for side in (1, -1):
        base = len(verts)
        for i in range(S):
            p, t = PTS[i], (PTS[(i + 1) % S] - PTS[i]).normalized(); n = Vector((-t.y, t.x, 0))
            q = p + n * side * (WIDTH / 2 + 9)
            verts += [q, q + Vector((0, 0, 1.1))]
        for i in range(S):
            j = (i + 1) % S
            faces.append((base + 2 * i, base + 2 * j, base + 2 * j + 1, base + 2 * i + 1))
    me = bpy.data.meshes.new("armco"); me.from_pydata(verts, [], faces); me.materials.append(material)
    o = bpy.data.objects.new("armco", me); bpy.context.scene.collection.objects.link(o)


def _grandstand(prim, mat, rng):
    """Main-straight grandstand with a crowd (one mesh of thousands of little people-blocks)."""
    concrete = mat("stand", (0.45, 0.45, 0.47), 0.8)
    for r in range(12):
        prim("cube", (130, -(WIDTH / 2 + 14 + r * 1.2), 0.4 + r * 0.6), (125, 0.6, 0.4 + r * 0.6), material=concrete)
    prim("cube", (130, -(WIDTH / 2 + 22), 12), (126, 8, 0.3), material=mat("roof", (0.85, 0.85, 0.88), 0.4, 0.5))
    verts, faces, idx = [], [], []
    for r in range(12):
        for x in range(0, 250, 1):
            if rng.random() < 0.25:
                continue
            cx, cy, cz = 5 + x + rng.uniform(-0.2, 0.2), -(WIDTH / 2 + 14 + r * 1.2), 0.8 + r * 1.2 + 0.4
            s, h = 0.22, rng.uniform(0.45, 0.6)
            b = len(verts)
            verts += [(cx - s, cy - s, cz), (cx + s, cy - s, cz), (cx + s, cy + s, cz), (cx - s, cy + s, cz),
                      (cx - s, cy - s, cz + h), (cx + s, cy - s, cz + h), (cx + s, cy + s, cz + h), (cx - s, cy + s, cz + h)]
            faces += [(b, b + 1, b + 5, b + 4), (b + 4, b + 5, b + 6, b + 7), (b + 1, b + 2, b + 6, b + 5)]
            idx += [rng.randrange(6)] * 3
    me = bpy.data.meshes.new("crowd"); me.from_pydata(verts, [], faces)
    for i, c in enumerate([(0.8, 0.1, 0.1), (0.1, 0.2, 0.8), (0.9, 0.8, 0.1), (0.9, 0.9, 0.9), (0.1, 0.5, 0.15), (0.9, 0.4, 0.05)]):
        me.materials.append(mat(f"fan{i}", c, 0.8))
    for p, m in zip(me.polygons, idx):
        p.material_index = m
    o = bpy.data.objects.new("crowd", me); bpy.context.scene.collection.objects.link(o)
    # crowd bounce (cheers)
    o.driver_add("location", 2).driver.expression = "0.05*abs(sin(frame*0.6))"


# ------------------------------------------------------------------ race cars
def race_car(mat, prim, light, empty, color, driver_color, number, night):
    root = empty(f"car{number}")
    paint = mat(f"paint{number}", color, 0.18, 0.6)
    carbon = mat(f"carbon{number}", (0.02, 0.02, 0.025), 0.3, 0.3)
    white = mat(f"liv{number}", (0.92, 0.92, 0.92), 0.25, 0.2)
    prim("cube", (0, 0, 0.45), (2.3, 0.85, 0.28), material=paint, parent=root, bevel=0.12)       # tub
    prim("cube", (1.9, 0, 0.32), (1.0, 0.45, 0.14), material=paint, parent=root, bevel=0.08)    # nose
    prim("cube", (0.1, 0, 0.62), (2.2, 0.12, 0.12), material=white, parent=root)                 # stripe
    prim("cube", (-0.6, 0, 0.82), (0.9, 0.55, 0.2), material=paint, parent=root, bevel=0.1)     # engine cover
    prim("cube", (2.7, 0, 0.12), (0.25, 1.05, 0.03), material=carbon, parent=root)               # front wing
    prim("cube", (-2.2, 0, 1.15), (0.3, 0.95, 0.04), material=paint, parent=root)                # rear wing
    for y in (0.85, -0.85):
        prim("cube", (-2.2, y, 0.95), (0.25, 0.03, 0.22), material=carbon, parent=root)
    # driver: the series robot's head in a helmet colour, so viewers know who is driving
    head = prim("uv_sphere", (0.35, 0, 0.98), (0.24, 0.22, 0.24), material=mat(f"helmet{number}", driver_color, 0.2, 0.3),
                parent=root, segments=20, ring_count=12)
    prim("cube", (0.55, 0, 1.0), (0.06, 0.16, 0.06), material=mat(f"visor{number}", (0.02, 0.03, 0.05), 0.05), parent=root)
    prim("cube", (0.75, 0, 0.82), (0.05, 0.4, 0.12), rot=(0, 0.5, 0), material=mat("screen", (0.2, 0.3, 0.35), 0.0, 0.0, alpha=0.4), parent=root)
    tyre = mat("tyre", (0.02, 0.02, 0.02), 0.7)
    wheels = []
    for x, r, w in ((1.55, 0.36, 0.2), (-1.55, 0.42, 0.26)):
        for y in (1.05, -1.05):
            wh = prim("cylinder", (x, y, r), (r, r, w), rot=(math.pi / 2, 0, 0), material=tyre, parent=root, vertices=24)
            wheels.append(wh)
    num = bpy.data.curves.new(f"n{number}", "FONT"); num.body = str(number); num.size = 0.5; num.align_x = "CENTER"
    for y, rz in ((0.87, math.pi), (-0.87, 0)):
        t = bpy.data.objects.new("num", num); bpy.context.scene.collection.objects.link(t)
        t.data.materials.append(white) if not t.data.materials else None
        t.location = (-0.2, y, 0.32); t.rotation_euler = (math.pi / 2, 0, rz); t.parent = root
    if night:
        for y in (0.5, -0.5):
            light("SPOT", (2.6, y, 0.4), 2000, (1, 0.95, 0.85), rot=(0, math.radians(-92), 0), parent=root,
                  spot_size=math.radians(50), size=0.05)
    light("POINT", (-2.45, 0, 0.6), 30, (1, 0.05, 0.02), parent=root, size=0.1)
    return root, wheels


def ease(u):
    u = max(0.0, min(1.0, u)); return u * u * (3 - 2 * u)


def race(shot, story, n, helpers, x0=0.0):
    """Builds the cars and keys their motion for this shot. Returns the hero car root."""
    mat, prim, light, empty = helpers
    rng = random.Random(len(story["shots"]) + shot["start"])
    ev = shot["vehicle"]; night = shot["time"] == "night"
    cast = story["cast"]
    COL = {"orange": (0.9, 0.35, 0.05), "blue": (0.08, 0.3, 0.85), "red": (0.8, 0.06, 0.05), "green": (0.15, 0.6, 0.15),
           "yellow": (0.95, 0.75, 0.08), "purple": (0.4, 0.12, 0.7), "white": (0.85, 0.85, 0.82), "pink": (0.95, 0.4, 0.6)}
    ids = [c["id"] for c in shot["characters"]] or list(cast)[:2]
    drivers = ids + [k for k in cast if k not in ids]
    cars = []
    for k in range(6):
        if k < len(drivers):
            c = cast[drivers[k]]; col = COL.get(c["color"], (0.5, 0.5, 0.5)); num = c.get("slot", k) + 7
        else:
            col = [(0.3, 0.3, 0.32), (0.05, 0.05, 0.05), (0.85, 0.85, 0.8)][k % 3]; num = 20 + k
        cars.append(race_car(mat, prim, light, empty, col, col, num, night))
    # race state at local time t for car k -> (distance, lane, spin)
    start_d = 900.0 if ev not in ("race_start", "finish") else 0.0
    def state(k, t):
        u = t / max(n / FPS, 0.1)
        base_gap = 11.0
        lane = (-3.2 if k % 2 else 3.2) * (0.6 + 0.4 * math.sin(t * 0.7 + k))
        if ev == "race_start":
            go = max(0.0, t - 3.0)
            d = -10 - k * 10 + 0.5 * 9.0 * min(go, 5.5) ** 2 + max(0.0, go - 5.5) * 49.5 - k * 0.3 * go
            lane = (k % 2 * 2 - 1) * 3.0
            return d, lane, 0.0
        if ev == "finish":
            d = -60 + V * t - k * base_gap * (1 + 0.1 * k)
            return d, lane, 0.0
        d = start_d + V * t - k * base_gap
        if ev == "overtake" and k in (0, 1):
            # hero (0) starts behind the rival (1) and sweeps past on the outside
            if k == 0:
                d = start_d + V * t - 1.3 * base_gap + 2.2 * base_gap * ease((u - 0.2) / 0.6)
                lane = 3.2 - 6.8 * ease((u - 0.1) / 0.3) + 3.6 * ease((u - 0.8) / 0.2)
            else:
                d, lane = start_d + V * t, 3.2
        if ev == "crash" and k == 1:
            tc = 0.3 * n / FPS; c = ease((u - 0.3) / 0.5)
            d = start_d - base_gap + V * min(t, tc) + (V * (1 - math.exp(-(t - tc) * 1.2)) / 1.2 if t > tc else 0)
            return d, 3.0 + 14 * c, c * 4.5
        return d, lane, 0.0
    for k, (root, wheels) in enumerate(cars):
        for f in range(0, n + 1, 2):
            t = f / FPS
            d, lane, spin = state(k, t)
            p, tg = frame_at(d + x0, lane)
            root.location = p + Vector((0, 0, 0.004 * math.sin(f * 1.3 + k)))
            root.rotation_euler = (0, 0, math.atan2(tg.y, tg.x) + spin)
            root.keyframe_insert("location", frame=f + 1); root.keyframe_insert("rotation_euler", frame=f + 1)
        for w in wheels:
            w.driver_add("rotation_euler", 1).driver.expression = "frame*2.2"
    return cars, state


def race_camera(shot, cars, state, n, empty, frame_at_fn=frame_at):
    """TV race coverage. Camera kinds from the shot list are mapped to race shots."""
    sc = bpy.context.scene
    hero = cars[0][0]
    cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam); sc.camera = cam; cd.clip_end = 6000
    kind = shot["camera"]
    mode = {"track": "chase", "handheld": "onboard", "low_angle": "bumper", "establish": "heli", "crane_up": "heli",
            "orbit": "orbit", "closeup": "driver", "top_down": "top", "push_in": "trackside", "over_shoulder": "trackside"}[kind]
    tgt = empty("tgt"); tgt.parent = hero
    tr = cam.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
    cd.lens = {"chase": 28, "onboard": 16, "bumper": 20, "heli": 60, "orbit": 30, "driver": 55, "top": 35, "trackside": 120}[mode]
    cd.dof.use_dof = mode in ("driver", "trackside", "bumper"); cd.dof.focus_object = tgt; cd.dof.aperture_fstop = 2.8
    if mode == "trackside":
        d, lane, _ = state(0, n / FPS * 0.5)
        p, tg = frame_at_fn(d, -(WIDTH / 2 + 7))
        cam.location = p + Vector((0, 0, 1.6)) - tg * 15
        tgt.location = (0, 0, 0.6)
        return cam
    cam.parent = hero
    offs = {"chase": (-9.5, 0, 2.6), "onboard": (-0.45, 0, 1.45), "bumper": (3.2, 1.6, 0.35), "heli": (-35, 45, 28),
            "driver": (2.6, 1.5, 1.45), "top": (0, 0, 32)}
    tgt.location = {"onboard": (30, 0, 0.8), "driver": (0.35, 0, 0.98), "bumper": (0, 0, 0.6)}.get(mode, (0, 0, 0.5))
    for f in range(0, n + 1, 3):
        u = f / max(n, 1)
        if mode == "orbit":
            a = math.radians(-150 + 120 * u); o = Vector((10 * math.cos(a), 10 * math.sin(a), 2.2))
        else:
            o = Vector(offs[mode])
            if mode == "heli":
                o = o * (1.0 - 0.3 * u)
        shake = Vector((0, math.sin(f * 1.7) * 0.01, math.sin(f * 2.3) * 0.012)) if mode in ("onboard", "chase") else Vector()
        cam.location = o + shake; cam.keyframe_insert("location", frame=f + 1)
    return cam


def start_lights(lamps, n):
    """F1-style start: five reds come on one by one, then all go out -> lights out and away."""
    for k, lm in enumerate(lamps):
        nd = lm.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        for f, v in ((1, 0), (int((0.5 + k * 0.5) * FPS), 0), (int((0.5 + k * 0.5) * FPS) + 1, 40), (int(3.0 * FPS), 40), (int(3.0 * FPS) + 1, 0)):
            nd.default_value = v; nd.keyframe_insert("default_value", frame=max(1, f))
