"""Runs ON KAGGLE (free GPU). Generates video clips with the open-source Wan 2.2 TI2V-5B model
(Apache 2.0 licence: free for commercial use, no watermark).
Input: shots.json next to this script (embedded by the GitHub workflow). Output: /kaggle/working/clip_XXX.mp4"""
import json, os, subprocess, sys, time
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "diffusers>=0.35", "transformers", "accelerate",
                "ftfy", "imageio", "imageio-ffmpeg", "sentencepiece"], check=True)
import torch
from diffusers import WanPipeline, AutoencoderKLWan
from diffusers.utils import export_to_video

SHOTS = json.loads(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots.json")).read()) \
    if os.path.exists("shots.json") else json.loads(os.environ.get("SHOTS_JSON", "[]"))
print("GPU:", torch.cuda.get_device_name(0), torch.cuda.get_device_properties(0).total_memory // 2**30, "GB", flush=True)
MODEL = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
vae = AutoencoderKLWan.from_pretrained(MODEL, subfolder="vae", torch_dtype=torch.float32)
pipe = WanPipeline.from_pretrained(MODEL, vae=vae, torch_dtype=dtype)
pipe.enable_model_cpu_offload()  # fits 16 GB cards (T4 / P100)
# Older GPUs (T4) have no memory-efficient attention for this model and fall back to plain attention,
# which needs 13+ GB at once. Run it in chunks of queries instead: same result, ~1 GB at a time.
import torch.nn.functional as F
_sdpa = F.scaled_dot_product_attention
def chunked_sdpa(query, key, value, attn_mask=None, dropout_p=0.0, is_causal=False, scale=None, **kw):
    n = query.shape[-2]
    if n <= 2048 or attn_mask is not None or is_causal:
        return _sdpa(query, key, value, attn_mask=attn_mask, dropout_p=dropout_p, is_causal=is_causal, scale=scale, **kw)
    return torch.cat([_sdpa(query[..., i:i + 1024, :], key, value, dropout_p=dropout_p, scale=scale, **kw)
                      for i in range(0, n, 1024)], dim=-2)
F.scaled_dot_product_attention = chunked_sdpa
torch.nn.functional.scaled_dot_product_attention = chunked_sdpa
pipe.vae.enable_tiling() if hasattr(pipe.vae, "enable_tiling") else None
NEG = ("cartoon, anime, 3d render, cgi, blurry, low quality, deformed face, extra fingers, bad hands, "
       "text, watermark, logo, subtitles, oversaturated, static, frozen frame")
os.makedirs("/kaggle/working", exist_ok=True)
for i, s in enumerate(SHOTS):
    t = time.time()
    frames = pipe(prompt=s["prompt"], negative_prompt=NEG, height=s.get("h", 480), width=s.get("w", 832),
                  num_frames=s.get("frames", 121), guidance_scale=5.0, num_inference_steps=s.get("steps", 40),
                  generator=torch.Generator("cpu").manual_seed(s.get("seed", 42))).frames[0]
    import numpy as np
    print("frame brightness (0 = black / broken):", float(np.asarray(frames[len(frames) // 2]).mean()), flush=True)
    export_to_video(frames, f"/kaggle/working/clip_{i:03d}.mp4", fps=24)
    torch.cuda.empty_cache()
    print(f"clip {i} done in {time.time() - t:.0f}s", flush=True)
print("ALL DONE", flush=True)
