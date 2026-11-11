"""Runs ON KAGGLE (free GPU): downloads Blender + real CC0 assets (Poly Haven), renders the scene
on the GPU and encodes the video. The scene script and (optionally) a car model come with the job."""
import glob, json, os, subprocess, sys, time, urllib.request
W = "/kaggle/working"; A = "/kaggle/temp/assets"; os.makedirs(A, exist_ok=True)
def sh(cmd):
    print("+", cmd[:200], flush=True); subprocess.run(cmd, shell=True, check=True)
def get(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "getyr-studio-render"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        f.write(r.read())
def api(path):
    req = urllib.request.Request("https://api.polyhaven.com" + path, headers={"User-Agent": "getyr-studio-render"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())

# 1. Blender 4.2 LTS
sh("cd /kaggle/temp && wget -q https://download.blender.org/release/Blender4.2/blender-4.2.3-linux-x64.tar.xz && tar -xJf blender-4.2.3-linux-x64.tar.xz")
BL = "/kaggle/temp/blender-4.2.3-linux-x64/blender"
sh("apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 >/dev/null 2>&1 || true")

# 2. real assets from Poly Haven (all CC0)
def best(kind, words, prefer):
    assets = api(f"/assets?t={kind}")
    for p in prefer:
        if p in assets:
            return p
    for k, v in assets.items():
        tags = " ".join(v.get("tags", []) + v.get("categories", []) + [k]).lower()
        if all(w in tags for w in words):
            return k
try:
    sky = best("hdris", ["sky"], ["kloofendal_48d_partly_cloudy_puresky", "kloofendal_43d_clear_puresky", "qwantani_puresky"])
    f = api(f"/files/{sky}"); get(f["hdri"]["4k"]["hdr"]["url"], f"{A}/sky.hdr"); print("sky:", sky)
except Exception as exc:
    print("sky failed:", exc)
for kind, words, prefer in (("rock", ["rock"], ["rock_face", "aerial_rocks_02", "rocky_terrain_02", "rock_face_03"]),
                            ("grass", ["grass"], ["aerial_grass_rock", "forrest_ground_01", "brown_mud_leaves_01", "sparse_grass"]),
                            ("asphalt", ["asphalt"], ["asphalt_02", "asphalt_track", "asphalt_01", "asphalt_03"])):
    try:
        tid = best("textures", words, prefer); f = api(f"/files/{tid}")
        d = f"{A}/{kind}_{tid}"; os.makedirs(d, exist_ok=True)
        for key, name in (("Diffuse", "diff.jpg"), ("nor_gl", "nor.jpg"), ("Rough", "rough.jpg")):
            if key in f:
                get(f[key]["2k"]["jpg"]["url"], f"{d}/{name}")
        print("texture", kind, "->", tid)
    except Exception as exc:
        print("texture failed:", kind, exc)
sh("find /kaggle/input -maxdepth 6 | head -50 || true")  # show what Kaggle attached
cars = [os.path.join(r, f) for r, _, fs in os.walk("/kaggle/input") for f in fs if f.lower().endswith(".glb")]
if not cars and os.environ.get("CAR_URL", CAR_URL if "CAR_URL" in globals() else ""):
    get(CAR_URL, f"{A}/car.glb"); cars = [f"{A}/car.glb"]
if not cars:
    raise SystemExit("NO CAR MODEL - refusing to render a stand-in")
if cars[0] != f"{A}/car.glb":
    sh(f"cp '{cars[0]}' {A}/car.glb")
print("car file:", cars[0], flush=True)

# 3. render on the GPU (scene script is embedded below by the GitHub workflow)
open("/kaggle/temp/scene.py", "w").write(SCENE)
t = time.time()
sh(f"{BL} -b -noaudio -P /kaggle/temp/scene.py -- {A} /kaggle/temp/frames 2>&1 | grep -E 'GPU|frame|car:|sky:|texture|Error|Traceback' ; ls /kaggle/temp/frames | wc -l")
print(f"render time: {(time.time() - t) / 60:.1f} min", flush=True)

# 4. encode: gentle film grade, light grain, 2.39:1 cinema bars, ambient sound (wind + sea)
sh(f"ffmpeg -y -loglevel error -framerate 24 -i /kaggle/temp/frames/f_%04d.jpg "
   f"-f lavfi -i 'anoisesrc=c=brown:a=0.5:d=15,lowpass=f=600,tremolo=f=0.15:d=0.6' "
   f"-vf 'eq=contrast=1.03:saturation=1.04,noise=alls=2:allf=t,drawbox=y=0:w=iw:h=ih*0.12:color=black:t=fill,drawbox=y=ih*0.88:w=iw:h=ih*0.12:color=black:t=fill' "
   f"-c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p -c:a aac -b:a 160k -shortest {W}/coast_blender.mp4")
sh(f"cp /kaggle/temp/frames/f_0060.jpg /kaggle/temp/frames/f_0180.jpg /kaggle/temp/frames/f_0330.jpg {W}/ || true")
print("ALL DONE", flush=True)
