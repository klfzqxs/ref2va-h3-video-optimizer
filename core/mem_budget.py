#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\u663e\u5b58 / \u65f6\u957f\u9884\u7b97\u4f30\u8ba1\uff08\u72ec\u7acb\u529f\u80fd\uff0c\u7eaf\u6807\u51c6\u5e93\uff09\u3002

\u5b83\u7b97\u4ec0\u4e48
--------
  tokens\uff08**\u7cbe\u786e**\uff09= latent_t \u00d7 (\u5bbd/32) \u00d7 (\u9ad8/32)
      \u5176\u4e2d frames = \u65f6\u957f(\u79d2)\u00d724 \u5411\u4e0a\u5438\u9644\u5230 17k+5 \u7f51\u683c\uff1blatent_t = ((frames-5)//17)*5+2
  peak VRAM\uff08**\u8fd1\u4f3c**\uff09= base + k \u00d7 tokens      \u2190 \u7ebf\u6027\u4e8e token\uff0c\u800c token \u5df2\u540c\u65f6\u542b\u753b\u5e03\u4e0e\u65f6\u957f

\u7ebf\u6027\u6a21\u578b\u7684\u6765\u6e90\uff08\u4e0d\u662f\u62cd\u8111\u888b\uff09
---------------------------
ComfyUI-MAINodes \u7684\u5b9e\u6d4b\u5305\u7ebf\u8868\u7ed9\u51fa\u4e09\u4e2a\u70b9\uff08\u540c\u4e00\u53f0\u673a\u5668\u3001int8 \u68c0\u67e5\u70b9\u3001\u52a8\u6001\u663e\u5b58\uff09\uff1a
    16 GB \u2192 \u7ea6 230k token \u521a\u597d\u8dd1\u6ee1
    24 GB \u2192 \u7ea6 380k token
    32 GB \u2192 \u7ea6 530k token
\u4e09\u70b9\u51e0\u4e4e\u5b8c\u7f8e\u5171\u7ebf\uff1ak = 8 GB / 150k token = **53.3 KB/token**\uff1bbase = 16 \u2212 0.0533\u00d7230 = **3.73 GB**
\uff08\u7b2c\u4e09\u70b9\u56de\u4ee3\u9a8c\u7b97\uff1a3.73 + 0.0533\u00d7530 = 32.0 GB \u2713\uff09

\u504f\u5dee\u4e0e\u5c40\u9650\uff08\u52a1\u5fc5\u4e00\u8d77\u8bfb\uff09
------------------------
* base \u91cc\u542b"\u5e38\u9a7b\u6743\u91cd + \u6587\u672c\u7f16\u7801\u5668\u4f59\u7559"\uff0c\u53d6\u51b3\u4e8e ComfyUI \u7684\u6743\u91cd\u6d41\u5f0f/\u5378\u8f7d\u7b56\u7565\uff0c\u6545\u6b64\u5904\u5bf9
  \u6a21\u578b\u4f53\u79ef\u7ed9\u4e00\u4e2a**\u4fdd\u5b88\u88d5\u91cf** `model_gb \u00d7 0.10`\uff1b\u4e00\u65e6\u4f60\u6709\u5b9e\u6d4b\u6837\u672c\uff0c\u5c31\u4ee5\u5b9e\u6d4b\u62df\u5408\u4e3a\u51c6\u3002
* \u91c7\u6837\u5cf0\u503c\u53d7\u6ce8\u610f\u529b\u5b9e\u73b0\u5f71\u54cd\uff08SageAttention3 / \u5206\u5757\u6ce8\u610f\u529b\u4f1a\u660e\u663e\u538b\u4f4e\u5cf0\u503c\uff09\u3002
* VAE \u89e3\u7801\u3001\u53c2\u8003\u56fe token\u3001LoRA \u9644\u52a0\u6743\u91cd\u5404\u6709\u81ea\u5df1\u7684\u9879\uff0c\u672c\u6a21\u578b\u4e0d\u5355\u72ec\u5efa\u9879\u3002
\u7ed3\u8bba\u7528\u4e8e**\u63d0\u524d\u9884\u8b66\u4e0e\u6392\u5e8f**\uff08\u8be5\u964d\u5230\u591a\u5c11\uff09\uff0c\u4e0d\u7528\u4e8e\u7cbe\u786e\u89c4\u5212\u3002
"""
import argparse
import os
import re

# --- \u7ebf\u6027\u6a21\u578b\u7684\u9ed8\u8ba4\u53c2\u6570\uff08\u6765\u6e90\u89c1\u4e0a\uff09---
DEFAULT_BASE_GB = 3.73
DEFAULT_KB_PER_TOKEN = 0.0533      # GB / 1k token
MODEL_RESIDENT_FRACTION = 0.10     # \u6a21\u578b\u4f53\u79ef\u672a\u77e5\u65f6\u6309\u8fd9\u4e2a\u6bd4\u4f8b\u8ba1\u5165\u5e38\u9a7b\u88d5\u91cf\uff08\u4fdd\u5b88\uff09
HEADROOM = 0.97                    # \u663e\u5361\u6807\u79f0\u663e\u5b58\u91cc\u53ef\u7528\u6bd4\u4f8b\uff08\u5b9e\u6d4b\uff1a24.4 GB \u5361\u5cf0\u503c\u5230\u8fc7 23.5 GB \u4ecd\u7a33\uff09
OS_RAM_RESERVE_GB = 4.0            # \u7ed9\u7cfb\u7edf/\u5176\u5b83\u8fdb\u7a0b\u7559\u7684\u5185\u5b58\u4f59\u91cf\uff1a\u957f\u4efb\u52a1\u671f\u95f4\u6d4f\u89c8\u5668\u7b49\u8fd8\u4f1a\u957f
FPS = 24

# ---- \u6743\u91cd\u683c\u5f0f\u6863\u6848\uff1a\u4ece\u6587\u4ef6\u540d/\u6269\u5c55\u540d\u63a8\u65ad ----------------------------------------------------
# \u4f9d\u636e\uff1a\u4e00\u822c\u4eba\u4e0d\u4f1a\u6539\u4e0b\u8f7d\u6765\u7684\u6a21\u578b\u540d\uff1b\u540d\u5b57\u91cc\u7684 int8 / w4a8 / nvfp4 / mxfp8 / gguf / bf16
# \u76f4\u63a5\u5bf9\u5e94"\u6743\u91cd\u4ee5\u4ec0\u4e48\u7cbe\u5ea6\u5b58\u653e\u3001\u8981\u4e0d\u8981\u53cd\u91cf\u5316"\u3002resident_frac \u662f"\u6743\u91cd\u5e38\u9a7b"\u76f8\u5bf9**\u6587\u4ef6\u4f53\u79ef**\u7684
# \u7cfb\u6570\uff081.0 = \u5047\u5b9a\u6574\u4efd\u8fdb\u663e\u5b58\uff1bGGUF \u9700\u8981\u53cd\u91cf\u5316\uff0c\u6545\u7559 >1 \u7684\u7f13\u51b2\uff09\u3002
FORMAT_RULES = [
    ("w4a8", "W4A8", 1.00, False, "int4 \u6743\u91cd / int8 \u6fc0\u6d3b\uff0c\u76f4\u63a5 int8 \u8ba1\u7b97\u3001\u65e0\u9700\u53cd\u91cf\u5316 \u2192 \u540c\u4f53\u79ef\u4e0b\u663e\u5b58\u6700\u7701"),
    ("nvfp4", "NVFP4", 1.00, False, "\u539f\u751f fp4 \u6743\u91cd\uff0c\u514d\u53cd\u91cf\u5316"),
    ("mxfp4", "MXFP4", 1.00, False, "\u539f\u751f fp4 \u6743\u91cd\uff0c\u514d\u53cd\u91cf\u5316"),
    ("mxfp8", "MXFP8", 1.00, False, "\u539f\u751f fp8 \u6743\u91cd\uff0c\u514d\u53cd\u91cf\u5316"),
    ("fp8", "FP8", 1.02, False, "fp8 \u6743\u91cd\uff0c\u901a\u5e38\u514d\u53cd\u91cf\u5316"),
    ("int8", "INT8", 1.00, False, "\u76f4\u63a5 int8 \u8ba1\u7b97\u3001\u65e0\u9700\u53cd\u91cf\u5316"),
    ("gguf", "GGUF", 1.15, True, "\u9700\u8981\u53cd\u91cf\u5316\u5230\u8ba1\u7b97\u7cbe\u5ea6 \u2192 \u5cf0\u503c\u901a\u5e38\u9ad8\u4e8e\u540c\u4f53\u79ef int8 \u76f4\u7b97\uff1b\u4e14 weight_dtype \u65e0\u6548\uff08\u9700 ComfyUI-GGUF \u8282\u70b9\uff09"),
    ("bf16", "BF16", 1.00, False, "\u672a\u91cf\u5316\uff0c\u4f53\u79ef\u6700\u5927"),
    ("fp16", "FP16", 1.00, False, "\u672a\u91cf\u5316\uff0c\u4f53\u79ef\u6700\u5927"),
]
SIZE_IN_NAME = re.compile(r"(\d+(?:\.\d+)?)\s*gb", re.I)


def parse_model_profile(name, size_gb=None, size_source=None):
    """\u4ece\u6a21\u578b\u540d/\u6269\u5c55\u540d\u63a8\u65ad\u6743\u91cd\u683c\u5f0f\uff0c\u5e76\u7ed9\u51fa\u5e38\u9a7b\u663e\u5b58\u4f30\u8ba1\u3002

    name        \u7528\u6237\u9009\u7684\u6a21\u578b\u540d\uff08ComfyUI \u5185\u5168\u540d\uff0c\u53ef\u542b\u5b50\u76ee\u5f55\uff09
    size_gb     \u771f\u5b9e\u6587\u4ef6\u4f53\u79ef\uff08\u4f18\u5148\u7531 ComfyUI \u7684 /experiment/models/<folder> \u63d0\u4f9b\uff1bGiB\uff09
    size_source \u4f53\u79ef\u6765\u6e90\uff08comfy / disk / name / unknown\uff09\uff0c\u4f1a\u5e26\u8fdb\u7ed3\u679c\u91cc\u4ee5\u4fbf\u8ffd\u8d23
    """
    n = (name or "").lower()
    base = os.path.basename(n.replace("\\", "/")) if name else ""
    hits = [r for r in FORMAT_RULES if r[0] in n]
    if not hits and n.endswith(".gguf"):
        hits = [r for r in FORMAT_RULES if r[0] == "gguf"]
    fmt, frac, dequant, why = "\u672a\u77e5", 1.00, False, "\u540d\u5b57\u91cc\u8bfb\u4e0d\u51fa\u6743\u91cd\u683c\u5f0f\uff0c\u6309\u6574\u4efd\u5e38\u9a7b\u7c97\u4f30"
    if hits:
        _key, fmt, frac, dequant, why = hits[0]
    notes = [why]
    if hits and len(hits) > 1:
        notes.append("\u6df7\u5408\u7cbe\u5ea6\uff08\u540d\u5b57\u91cc\u540c\u65f6\u51fa\u73b0\uff1a%s\uff09" % "\u3001".join(h[1] for h in hits))
    if "hybrid" in n or "mixed" in n:
        notes.append("**\u6df7\u5408\u7cbe\u5ea6\u6a21\u578b**\uff1a\u591a\u79cd\u91cf\u5316\u6df7\u7528\uff08ComfyUI \u65e5\u5fd7\u4f1a\u5217 Native ops\uff0c\u5982 mxfp8/int8_tensorwise/"
                     "convrot_w4a4/asym_w4a8_int8/nvfp4\uff09\u3002\u6309\u540d\u5b57\u53ea\u80fd\u5224\u51fa\u5176\u4e2d\u6700\u663e\u773c\u7684\u4e00\u79cd\uff0c"
                     "\u4f53\u79ef\u624d\u662f\u53ef\u9760\u53e3\u5f84\u2014\u2014\u672c\u4f30\u7b97\u4f18\u5148\u7528\u4f53\u79ef\u3002")
    if "pruned" in n or "zs05" in n:
        notes.append("\u526a\u679d/\u84b8\u998f\u7248\uff1a\u4f53\u79ef\u66f4\u5c0f\uff0c\u4f46\u4fdd\u771f\u5ea6\u4e0e\u539f\u7248\u4e0d\u540c")
    if re.search(r"b\d+-\d+", n):
        notes.append("\u4ec5\u90e8\u5206 block \u505a\u4e86\u8be5\u91cf\u5316\uff08b20-49 \u4e4b\u7c7b\uff09\uff0c\u5b9e\u9645\u4f53\u79ef\u4ecb\u4e8e\u4e24\u8005\u4e4b\u95f4")

    src = size_source
    if size_gb is None:
        m = SIZE_IN_NAME.search(base)
        if m:
            size_gb, src = float(m.group(1)), "name"
    if size_gb is not None and not src:
        src = "unknown"
    resident = (float(size_gb) * frac) if size_gb else None
    return {"name": name, "format": fmt, "needs_dequant": dequant,
            "size_gb": round(float(size_gb), 2) if size_gb else None,
            "size_source": src or "unknown", "resident_frac": frac,
            "resident_gb": round(resident, 2) if resident else None, "notes": notes}


def snap_frames(duration):
    """\u65f6\u957f(\u79d2) \u2192 \u5b9e\u9645\u63d0\u4ea4\u5e27\u6570\uff08\u5411\u4e0a\u5438\u9644\u5230 17k+5\uff09\u3002"""
    n = max(5, int(round(float(duration) * FPS)))
    return n + (5 - (n % 17)) % 17


def latent_t_of(frames):
    if frames <= 1:
        return 1
    if frames <= 5:
        return 2
    return ((frames - 5) // 17) * 5 + 2


def tokens_of(duration, megapixels):
    """\u8fd4\u56de (frames, latent_t, tokens)\u3002tokens \u4e3a\u7cbe\u786e\u503c\uff0c\u4e0d\u542b\u53c2\u8003\u56fe/\u6587\u672c token\u3002"""
    frames = snap_frames(duration)
    lt = latent_t_of(frames)
    per_frame = max(1, int(round(float(megapixels) * 1e6 / 1024.0)))   # (W/32)*(H/32) = WH/1024
    return frames, lt, lt * per_frame


def fit(samples):
    """\u7528\u5b9e\u6d4b\u6837\u672c\u6700\u5c0f\u4e8c\u4e58\u62df\u5408 peak = base + k\u00d7tokens\u3002

    samples: [{"tokens": int, "peak_gb": float}, ...]\uff08\u81f3\u5c11 2 \u4e2a\u4e14 token \u4e0d\u540c\uff09
    \u8fd4\u56de (base_gb, kb_per_token) \u6216 None\u3002
    """
    pts = [(float(s["tokens"]), float(s["peak_gb"])) for s in (samples or [])
           if s.get("tokens") and s.get("peak_gb")]
    if len(pts) < 2 or len({p[0] for p in pts}) < 2:
        return None
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    den = n * sxx - sx * sx
    if den == 0:
        return None
    k = (n * sxy - sx * sy) / den              # GB / token
    base = (sy - k * sx) / n
    if k <= 0:
        return None
    return base, k * 1000.0                    # GB, GB/1k token


def _usable(card_gb, headroom=HEADROOM):
    return float(card_gb) * float(headroom)


def fetch_model_size_gb(base, name, folders=("diffusion_models", "unet", "unet_gguf")):
    """\u7528 ComfyUI \u7684 /experiment/models/<folder> \u53d6**\u771f\u5b9e\u6587\u4ef6\u4f53\u79ef**\uff08GiB\uff09\u3002

    \u8fd9\u4e2a\u63a5\u53e3\u8fde\u8fdc\u7a0b ComfyUI \u4e5f\u80fd\u7528\uff08\u4e0d\u50cf\u672c\u5730 stat \u53ea\u80fd\u540c\u673a\uff09\uff0c\u8fd4\u56de [{name, size, ...}]\u3002
    \u8fd4\u56de (size_gb, "comfy")\uff1b\u53d6\u4e0d\u5230\u8fd4\u56de (None, None)\u2014\u2014\u8c03\u7528\u65b9\u518d\u9000\u56de"\u6587\u4ef6\u540d\u91cc\u7684 Xgb"\u6216\u672a\u77e5\u3002
    """
    if not base or not name:
        return None, None
    import json as _json
    import urllib.request as _ur
    want = name.replace("/", "\\").lower()
    for folder in folders:
        try:
            with _ur.urlopen(base.rstrip("/") + "/experiment/models/" + folder, timeout=6) as r:
                items = _json.load(r)
        except Exception:
            continue
        for it in items or []:
            nm = (it.get("name") or "").replace("/", "\\").lower()
            if nm == want or nm.endswith("\\" + want):
                try:
                    sz = float(it.get("size") or 0)
                except (TypeError, ValueError):
                    sz = 0
                if sz > 0:
                    return round(sz / 2 ** 30, 2), "comfy"
    return None, None


def clip_note(clip, clip_gb=None):
    """\u6587\u672c\u7f16\u7801\u5668\uff08TE\uff09\u7684\u663e\u5b58\u63d0\u793a\u3002

    \u5b9e\u6d4b\u8bc1\u636e\uff08\u7528\u6237 2.0 \u8fd0\u884c\u65e5\u5fd7 + ComfyUI \u4f53\u79ef\u63a5\u53e3\u4e24\u5904\u543b\u5408\uff09\uff1a
      \u00b7 \u65e5\u5fd7 `MiniMaxH3TEModel_ ... 25140MB Staged` = 24.55 GiB\uff1b\u63a5\u53e3\u8bfb\u8be5 clip \u6587\u4ef6 = **24.55 GB**\uff1b
      \u00b7 \u65e5\u5fd7 `Model MiniMaxH3 ... 19995MB Staged` = 19.53 GiB\uff1b\u63a5\u53e3\u8bfb\u8be5 DiT \u6587\u4ef6 = **19.53 GB**\u3002
    \u5373 **Staged \u2248 \u6587\u4ef6\u4f53\u79ef**\uff08ComfyUI \u6253\u5370\u7684 MB \u5b9e\u4e3a MiB\uff09\uff0c\u4e0d\u5b58\u5728"\u52a0\u8f7d\u540e\u88ab\u653e\u5927"\u3002
    \u771f\u6b63\u7684\u8981\u70b9\u662f\uff1a**TE \u6587\u4ef6\u53ef\u4ee5\u6bd4 DiT \u8fd8\u5927**\uff0824.55 vs 19.53 GiB\uff09\uff0c\u800c\u5b83\u5728\u7f16\u7801\u9636\u6bb5\u72ec\u7acb\u9a7b\u7559\u3001
    \u7f16\u7801\u5b8c\u6210\u540e\u624d\u5378\u8f7d\uff1b\u4e00\u65e6\u4e0e DiT \u91cd\u53e0\uff0c\u5cf0\u503c\u5c31\u4f1a\u989d\u5916\u62ac\u9ad8\u4e00\u622a\u3002
    \uff08\u65e5\u5fd7\u91cc\u7684 `manual cast: torch.bfloat16` \u8bf4\u7684\u662f DiT \u7684\u6df7\u5408\u7cbe\u5ea6\u8ba1\u7b97\uff0c\u4e0d\u662f TE \u7684\u52a0\u8f7d\u653e\u5927\u3002\uff09
    """
    if not clip:
        return None
    return {
        "name": clip, "size_gb": round(float(clip_gb), 2) if clip_gb else None,
        "text": ("\u6587\u672c\u7f16\u7801\u5668%s\uff1a\u4e0e DiT \u5206\u5f00\u52a0\u8f7d\u3001\u7f16\u7801\u5b8c\u6210\u540e\u5378\u8f7d\u3002\u6ce8\u610f**\u5b83\u53ef\u80fd\u6bd4 DiT \u8fd8\u5927**"
                 "\uff08\u5b9e\u6d4b 24.55 GB vs 19.53 GB\uff09\uff0c\u4e24\u8005\u540c\u65f6\u9a7b\u7559\u4f1a\u989d\u5916\u62ac\u9ad8\u5cf0\u503c\u3002"
                 % (("\uff08\u6587\u4ef6 %.2f GB\uff09" % clip_gb) if clip_gb else "")),
    }


def estimate(duration, megapixels, card_gb=24.0, model=None, model_gb=None, size_source=None,
             samples=None, headroom=HEADROOM, clip=None, clip_gb=None):
    """\u7ed9\u51fa\u9884\u7b97\u4f30\u8ba1\u4e0e\u5efa\u8bae\u3002\u8fd4\u56de dict\uff08\u89c1\u6a21\u5757\u6587\u6863\uff09\u3002

    \u523b\u610f\u62c6\u6210**\u4e24\u4e2a\u6b63\u4ea4\u7ed3\u8bba**\uff1a
      * `token_verdict` \u2014\u2014 \u4ee5\u7ecf\u9a8c\u5305\u7ebf\u5224"token \u662f\u5426\u5728\u5305\u7ebf\u5185"\uff08\u4fdd\u5b88\uff0c\u53ef\u76f4\u63a5\u7528\u6765\u51b3\u5b9a\u964d\u4e0d\u964d\uff09\uff1b
      * `peak_verdict`  \u2014\u2014 \u5cf0\u503c\u662f\u5426\u88c5\u5f97\u4e0b\uff1a
          `ok` \u5373\u4f7f\u6743\u91cd\u6574\u4efd\u5e38\u9a7b\u4e5f\u5728\u53ef\u7528\u663e\u5b58\u5185\uff1b
          `offload` \u6743\u91cd\u5e38\u9a7b\u65f6\u4f1a\u8d34\u9876\uff0cComfyUI \u9760\u6743\u91cd\u5378\u8f7d\u786c\u6491\uff08\u80fd\u8dd1\u4f46\u660e\u663e\u66f4\u6162\uff09\uff1b
          `over` \u8fde\u5b8c\u5168\u6d41\u5f0f\u7684\u4e50\u89c2\u4f30\u8ba1\u90fd\u8d85\u4e86\uff1b
          `tight` \u5b9e\u6d4b\u6807\u5b9a\u540e\u8d34\u8fd1\u4e0a\u9650\uff1b
          `uncalibrated` \u65e2\u65e0\u5b9e\u6d4b\u6837\u672c\u3001\u4e5f\u8bfb\u4e0d\u51fa\u6a21\u578b\u683c\u5f0f\u4e0e\u4f53\u79ef\uff08\u6b64\u65f6\u53ea\u7ed9\u504f\u4f4e\u4f30\u8ba1\uff0c\u4e0d\u7ed9\u7eff\u706f\uff09\u3002
    \u6709\u5b9e\u6d4b\u6837\u672c\u65f6\u4f18\u5148\u7528\u6837\u672c\u62df\u5408\uff0c\u4e0d\u518d\u7ed9\u533a\u95f4\u3002
    """
    frames, lt, tokens = tokens_of(duration, megapixels)
    card_gb = float(card_gb)
    usable = _usable(card_gb, headroom)
    prof = parse_model_profile(model, model_gb, size_source)
    resident = prof["resident_gb"]

    # \u7ecf\u9a8c\u5305\u7ebf\uff1a\u7528\u9ed8\u8ba4\u53c2\u6570\u7b97\u51fa\u7684 token \u4e0a\u9650\uff08\u4e0e\u662f\u5426\u6807\u5b9a\u65e0\u5173\uff09
    env_tokens = max(0.0, (usable - DEFAULT_BASE_GB) * 1000.0 / DEFAULT_KB_PER_TOKEN)
    token_verdict = "over" if tokens > env_tokens else "ok"

    fitted = fit(samples)
    calibrated = fitted is not None
    warn = None
    if calibrated:
        base, kb = fitted
        est = base + kb * tokens / 1000.0
        lo = hi = est
        source = "\u5b9e\u6d4b\u62df\u5408\uff08%d \u4e2a\u6837\u672c\uff09" % len(samples)
        if est > usable:
            peak_verdict, note = "over", "\u6309\u4f60\u81ea\u5df1\u7684\u5b9e\u6d4b\u62df\u5408\uff0c\u9884\u8ba1\u8d85\u51fa\u53ef\u7528\u663e\u5b58"
        elif est > usable * 0.90:
            peak_verdict, note = "tight", "\u6309\u4f60\u81ea\u5df1\u7684\u5b9e\u6d4b\u62df\u5408\uff0c\u9884\u8ba1\u8d34\u8fd1\u4e0a\u9650\uff08\u5efa\u8bae\u7559\u4f59\u91cf\u6216\u964d\u4e00\u6863\uff09"
        else:
            peak_verdict, note = "ok", "\u6309\u4f60\u81ea\u5df1\u7684\u5b9e\u6d4b\u62df\u5408\uff0c\u9884\u8ba1\u53ef\u4ee5\u8dd1"
    else:
        base, kb = DEFAULT_BASE_GB, DEFAULT_KB_PER_TOKEN
        # \u5cf0\u503c\u4e0d\u53ef\u80fd\u8d85\u8fc7\u663e\u5361\u6807\u79f0\u503c\uff08ComfyUI \u4f1a\u5378\u8f7d\uff1b\u771f\u5230\u4e0d\u4e86\u5c31\u662f OOM\uff09\uff0c\u6545\u4e0a\u4e0b\u9650\u90fd\u6309\u663e\u5361\u622a\u65ad
        lo = min(float(card_gb), base + kb * tokens / 1000.0)
        if resident:
            # \u6743\u91cd\u5e38\u9a7b\u662f\u4e0a\u9650\u60c5\u5f62\uff1bComfyUI \u88c5\u4e0d\u4e0b\u65f6\u4f1a\u81ea\u5df1\u5378\u8f7d\uff0c\u6545\u540c\u6837\u4e0d\u8d85\u8fc7\u663e\u5361\u6807\u79f0\u503c
            hi = min(float(card_gb), resident + kb * tokens / 1000.0)
            src_txt = {"comfy": "ComfyUI \u8bfb\u53d6", "disk": "\u672c\u5730\u6587\u4ef6", "name": "\u4ece\u6587\u4ef6\u540d\u8bfb\u51fa"}.get(
                prof["size_source"], prof["size_source"])
            source = "\u533a\u95f4\u4f30\u8ba1\uff08%s %.2f GB\uff0c\u4f53\u79ef\u6765\u6e90\uff1a%s\uff09" % (prof["format"], prof["size_gb"], src_txt)
            if lo > usable:
                peak_verdict, note = "over", "\u8fde\u300c\u6743\u91cd\u5b8c\u5168\u6d41\u5f0f\u300d\u7684\u4e50\u89c2\u4f30\u8ba1\u90fd\u5df2\u8d85\u51fa\u53ef\u7528\u663e\u5b58\uff0c\u5efa\u8bae\u5148\u964d\u4e00\u6863"
            elif hi > usable:
                peak_verdict, note = "offload", (
                    "\u6743\u91cd\u82e5\u6574\u4efd\u5e38\u9a7b\u4f1a\u8d34\u9876\uff08%.1f GB > \u53ef\u7528 %.1f GB\uff09\uff1aComfyUI \u4f1a\u9760\u6743\u91cd\u5378\u8f7d\u786c\u6491\u2014\u2014\u80fd\u8dd1\uff0c"
                    "\u4f46 s/step \u660e\u663e\u4e0a\u5347\u3002\u60f3\u8ba9\u5cf0\u503c\u964d\u4e0b\u6765\uff0c\u4f18\u5148\u9009\u66f4\u5c0f\u7684\u68c0\u67e5\u70b9\u6216\u964d\u753b\u5e45/\u65f6\u957f\u3002" % (hi, usable))
            else:
                peak_verdict, note = "ok", "\u5373\u4f7f\u6743\u91cd\u6574\u4efd\u5e38\u9a7b\u4e5f\u5728\u53ef\u7528\u663e\u5b58\u5185\uff08%s\uff09" % prof["format"]
        else:
            hi = lo
            source = "\u7ecf\u9a8c\u5305\u7ebf\uff08\u672a\u6807\u5b9a\uff0c\u504f\u4f4e\u4f30\u8ba1\uff09"
            peak_verdict, note = "uncalibrated", (
                "\u65e2\u6ca1\u6709\u5b9e\u6d4b\u6837\u672c\uff0c\u4e5f\u8bfb\u4e0d\u51fa\u6a21\u578b\u683c\u5f0f/\u4f53\u79ef\uff1a%.1f GB \u53ea\u662f**\u504f\u4f4e\u4f30\u8ba1**\u3002"
                "\u771f\u5b9e\u5cf0\u503c\u7531\u68c0\u67e5\u70b9\u5e38\u9a7b\u6743\u91cd\u4e0e\u6743\u91cd\u6d41\u5f0f/\u5378\u8f7d\u7b56\u7565\u4e3b\u5bfc\u2014\u2014\u5148\u8dd1\u4e00\u6b21\u77ed\u6863\uff08\u4f1a\u81ea\u52a8\u8bb0\u5f55\u5cf0\u503c\uff09\uff0c"
                "\u4e4b\u540e\u672c\u529f\u80fd\u6539\u7528\u4f60\u7684\u5b9e\u6d4b\u62df\u5408\u3002" % lo)

    # \u53cd\u63a8\uff1a\u56fa\u5b9a\u753b\u5e45\u4e0b\u80fd\u8dd1\u5230\u591a\u957f\uff1b\u56fa\u5b9a\u65f6\u957f\u4e0b\u80fd\u7528\u591a\u5927\u753b\u5e45
    # \u6ce8\u610f\uff1a\u5efa\u8bae\u503c\u4e00\u5f8b**\u5411\u4e0b\u53d6\u6574**\u2014\u2014\u56db\u820d\u4e94\u5165\u4f1a\u628a\u5efa\u8bae\u503c\u63a8\u56de\u8d85\u7ebf\uff08\u5b9e\u6d4b\u8e29\u8fc7\uff1a0.8473 \u56db\u820d\u4e94\u5165\u5230
    # 0.85 \u540e\u91cd\u7b97\u4ecd\u662f over\uff09\uff0c\u800c"\u5efa\u8bae\u4e86\u4f46\u7167\u505a\u4ecd\u5931\u8d25"\u6bd4\u4e0d\u7ed9\u5efa\u8bae\u66f4\u7cdf\u3002
    tok_max = env_tokens
    per_frame = max(1, int(round(float(megapixels) * 1e6 / 1024.0)))
    max_lt = int(tok_max // per_frame) if per_frame else 0
    max_frames = (17 * ((max_lt - 2) // 5) + 5) if max_lt >= 2 else 0
    max_duration = int(max_frames / float(FPS) * 10) / 10.0 if max_frames >= 5 else 0.0
    mp_max = 0.0
    if lt:
        mp_max = int(tok_max / lt * 1024.0 / 1e6 * 100) / 100.0

    return {
        "duration_s": float(duration), "megapixels": float(megapixels),
        "frames": frames, "frames_seconds": round(frames / float(FPS), 2),
        "latent_t": lt, "tokens": tokens, "per_frame_tokens": per_frame,
        "card_gb": card_gb, "usable_gb": round(usable, 2),
        "envelope_tokens": int(env_tokens), "token_verdict": token_verdict,
        "base_gb": round(base, 2), "kb_per_token": round(kb, 4),
        "est_peak_gb": round(hi, 2), "est_peak_lo_gb": round(lo, 2),
        "peak_range_gb": [round(lo, 2), round(hi, 2)],
        "calibrated": calibrated, "lower_bound": (not calibrated) and (resident is None),
        "source": source, "peak_verdict": peak_verdict, "note": note,
        "max_duration_s_at_this_mp": max_duration,
        "max_megapixels_at_this_duration": mp_max,
        "fitted_from_samples": len(samples) if calibrated else 0,
        "model_profile": prof, "model_notes": prof["notes"],
        "clip_profile": clip_note(clip, clip_gb),
    }


def budget_lines(e, ram_free_gb=None, ram_total_gb=None, te_retained_gb=None, measured_ram_gb=None):
    """\u7528\u6237\u8981\u7684\u4e94\u6bb5\u5f0f\u7ed3\u8bba\uff08\u754c\u9762\u539f\u6837\u663e\u793a\u3001\u65e5\u5fd7\u538b\u7f29\u6210\u4e00\u884c\uff1b\u5224\u5b9a\u53ea\u5728\u8fd9\u91cc\u505a\u4e00\u6b21\uff09\u3002

    **"\u5378\u8f7d"\u7684\u8bed\u4e49\uff08\u5df2\u6838 ComfyUI \u6e90\u7801\uff09**\uff1a`partially_unload(offload_device, \u2026)` \u662f\u628a\u6743\u91cd
    \u642c\u5230 offload_device\uff08= CPU \u5185\u5b58\uff09\uff0c`detach()` \u53ea\u91ca\u653e\u663e\u5b58\u91cc\u7684\u526f\u672c\u2014\u2014\u6240\u4ee5\u6587\u672c\u7f16\u7801\u5668
    "\u4ece\u663e\u5b58\u5378\u8f7d"\u4e4b\u540e **\u6743\u91cd\u4ecd\u7136\u5360\u7740\u5185\u5b58\uff0c\u5e76\u6ca1\u6709\u91ca\u653e**\u3002\u56e0\u6b64\uff1a
        \u53ef\u7528\u603b\u91cf = \u53ef\u7528\u663e\u5b58 + (\u7a7a\u95f2\u5185\u5b58 \u2212 \u6587\u672c\u7f16\u7801\u5668\u5360\u7528)
    \u800c\u4e0d\u662f \u53ef\u7528\u663e\u5b58 + \u7a7a\u95f2\u5185\u5b58\uff08\u90a3\u6837\u4f1a\u628a TE \u7684 20+ GB \u91cd\u590d\u8ba1\u4e00\u904d\uff09\u3002
    \uff08\u82e5 ComfyUI \u7528 --fast-disk \u628a\u6743\u91cd\u653e\u78c1\u76d8/page cache\uff0c\u5185\u5b58\u538b\u529b\u4f1a\u5c0f\u4e00\u4e9b\uff0c\u5c5e\u672a\u5efa\u6a21\u9879\u3002\uff09

    \u5224\u5b9a\u4e09\u6863\uff1a\u5b8c\u7f8e\uff08DiT+Token \u5728\u53ef\u7528\u663e\u5b58\u5185\uff09/ \u80fd\u7528\u4f46\u4f1a\u6162\uff08\u8d85\u663e\u5b58\uff0c\u4f46"\u53ef\u7528\u603b\u91cf"\u88c5\u5f97\u4e0b\uff0c
    ComfyUI \u5378\u8f7d\u6743\u91cd\u786c\u6491\uff09/ \u4e0d\u53ef\u7528\uff08\u8fde\u53ef\u7528\u603b\u91cf\u90fd\u88c5\u4e0d\u4e0b\uff09\u3002
    """
    prof = e.get("model_profile") or {}
    cp = e.get("clip_profile") or {}
    dit = prof.get("resident_gb") or prof.get("size_gb")
    te = cp.get("size_gb") if isinstance(cp, dict) else None
    te_keep = te if te_retained_gb is None else te_retained_gb
    tok = round(e["kb_per_token"] * e["tokens"] / 1000.0, 1)
    usable = e["usable_gb"]
    need = round((dit or 0.0) + tok, 1)
    total3 = round(need + (te or 0.0), 1)
    ram_for_offload = None
    if ram_free_gb is not None:
        ram_for_offload = round(max(0.0, float(ram_free_gb) - float(te_keep or 0.0) - OS_RAM_RESERVE_GB), 1)
    pool = round(usable + (ram_for_offload or 0.0), 1)

    te_note = "\u4ece\u663e\u5b58\u5378\u8f7d\uff0c\u6743\u91cd\u7559\u5728\u5185\u5b58\uff08\u4e0d\u91ca\u653e\uff09"
    if measured_ram_gb:
        te_note += "\uff1b\u5b9e\u6d4b\u6e32\u67d3\u671f\u5185\u5b58\u989d\u5916\u5360\u7528 %.1f GiB" % float(measured_ram_gb)
    lines = [
        ("\u9884\u4f30\u6a21\u578b\uff08DiT\uff09\u5360\u7528\u91cf", ("%.1f GiB" % dit) if dit else "\u672a\u77e5\uff08\u672a\u9009\u6a21\u578b\u6216\u8bfb\u4e0d\u51fa\u4f53\u79ef\uff09"),
        ("\u6587\u672c\u7f16\u7801\u5668\uff08Text Encoder\uff09\u5360\u7528\u91cf", ("%.1f GiB" % te) if te else "\u672a\u77e5"),
        ("\u6765\u81ea Token \u7684\u5360\u7528\u91cf", "%.1f GiB" % tok),
        ("\u6587\u672c\u7f16\u7801\u5668\u5728\u6e32\u67d3\u9636\u6bb5", te_note),
        ("\u6b63\u786e\u5378\u8f7d\u540e\u9884\u4f30\u663e\u5b58\u5360\u7528", "%.1f GiB" % need),
    ]
    if ram_free_gb is not None:
        lines.append(("\u6e32\u67d3\u9636\u6bb5\u53ef\u7528\u603b\u91cf",
                      "%.1f GiB\uff08\u663e\u5b58 %.1f GiB + \u5185\u5b58\u53ef\u7528 %.1f GiB\uff0c\u5df2\u9884\u7559 %.0f GiB \u7ed9\u7cfb\u7edf\uff09"
                      % (pool, usable, ram_for_offload, OS_RAM_RESERVE_GB)))
    if not dit:
        effect = "\u8fd8\u4f30\u4e0d\u51c6\uff0c\u5148\u8dd1\u4e00\u6863"
        why = "\u6ca1\u9009\u6a21\u578b\u6216\u8bfb\u4e0d\u51fa\u5b83\u7684\u4f53\u79ef\uff0c\u53ea\u80fd\u6309\u7ecf\u9a8c\u5305\u7ebf\u7ed9\u504f\u4f4e\u4f30\u8ba1\uff1b\u8dd1\u4e00\u6863\u4e4b\u540e\u5c31\u7528\u4f60\u81ea\u5df1\u7684\u5b9e\u6d4b\u6570\u636e\u6765\u4f30\u3002"
    elif need <= usable:
        effect = "\u5b8c\u7f8e"
        why = "\u91c7\u6837\u65f6\uff08DiT+Token\uff09\u5728 %.1f GiB \u53ef\u7528\u663e\u5b58\u5185\u3002%s" % (
            usable, ("\uff08\u4e09\u8005\u5168\u91cf %.1f GiB \u4e5f\u5728\u53ef\u7528\u603b\u91cf %.1f GiB \u5185\uff09" % (total3, pool))
            if ram_free_gb is not None else "")
    elif need <= pool:
        effect = "\u80fd\u7528\u4f46\u4f1a\u6162"
        why = ("\u91c7\u6837\u9700 %.1f GiB\uff0c\u8d85\u8fc7\u53ef\u7528\u663e\u5b58 %.1f GiB\uff1b\u4f46\u53ef\u7528\u603b\u91cf %.1f GiB\uff08\u542b\u5185\u5b58\u6263\u9664 TE \u540e\u7684 %.1f GiB\uff09"
               "\u88c5\u5f97\u4e0b\uff0cComfyUI \u4f1a\u628a\u6743\u91cd\u5378\u8f7d\u5230\u5185\u5b58\u786c\u6491\u2014\u2014\u80fd\u51fa\u7247\uff0c\u6bcf\u6b65\u66f4\u6162\u3002"
               % (need, usable, pool, ram_for_offload or 0.0))
        if total3 > pool:
            why += "\uff08\u4e09\u8005\u5168\u91cf %.1f GiB \u8d85\u8fc7\u53ef\u7528\u603b\u91cf\uff0c\u4f46 TE \u662f\u4ece\u663e\u5b58\u5378\u8f7d\u7684\uff0c\u6240\u4ee5\u4ecd\u80fd\u8dd1\uff09" % total3
    else:
        effect = "\u4e0d\u53ef\u7528"
        why = ("\u91c7\u6837\u9700 %.1f GiB\uff0c\u800c\u53ef\u7528\u603b\u91cf\u53ea\u6709 %.1f GiB\uff0c\u88c5\u4e0d\u4e0b\u3002"
               "\u865a\u62df\u5185\u5b58 / swap \u7406\u8bba\u4e0a\u80fd\u8ba9\u5b83\u786c\u8dd1\u8d77\u6765\uff0c\u4f46\u90a3\u4f1a**\u6781\u6162**\u3001\u5e76**\u4e25\u91cd\u78e8\u635f SSD**\uff0c"
               "\u6240\u4ee5\u8fd9\u91cc\u76f4\u63a5\u5efa\u8bae\u522b\u8dd1\uff1a\u964d\u753b\u5e45\u3001\u7f29\u77ed\u65f6\u957f\uff0c\u6216\u6362\u66f4\u5c0f\u7684\u68c0\u67e5\u70b9\u3002" % (need, pool))

    return {"lines": [{"label": a, "value": b} for a, b in lines],
            "effect": effect, "why": why, "need_gb": need, "total_three_gb": total3,
            "pool_gb": pool, "usable_gb": usable, "card_gb": e.get("card_gb"),
            "ram_free_gb": ram_free_gb, "ram_total_gb": ram_total_gb,
            "ram_for_offload_gb": ram_for_offload, "te_retained_gb": te_keep,
            "measured_ram_gb": measured_ram_gb}


def budget_text(e, ram_free_gb=None, ram_total_gb=None, sep=" \uff5c "):
    """\u4e94\u6bb5\u5f0f\u7684\u538b\u7f29\u5355\u884c\u7248\uff08\u65e5\u5fd7/CLI/\u81ea\u68c0\u7528\uff09\u3002

    \u5165\u53c2\u53ef\u7ed9 estimate() \u7684\u7ed3\u679c\uff0c\u4e5f\u53ef\u76f4\u63a5\u7ed9 budget_lines() \u7684\u7ed3\u679c\uff08\u5df2\u7b97\u8fc7\u5c31\u4e0d\u518d\u7b97\u4e00\u904d\uff09\u3002
    """
    b = e if (isinstance(e, dict) and "lines" in e) else budget_lines(e, ram_free_gb, ram_total_gb)
    parts = ["%s\uff1a%s" % (x["label"], x["value"]) for x in b["lines"]]
    return sep.join(parts) + "%s\u9884\u8ba1\u4f7f\u7528\u6548\u679c\uff1a%s\uff08%s\uff09" % (sep, b["effect"], b["why"])


def user_line(e):
    """\u9762\u5411\u7528\u6237\u7684\u8bf4\u6cd5\uff1a**\u7ed3\u8bba + \u4e00\u53e5\u539f\u56e0 + \u5173\u952e\u6570\u5b57**\u3002

    \u6280\u672f\u53e3\u5f84\uff08token/\u5305\u7ebf\u3001base\u3001staged \u8bed\u4e49\u3001\u6df7\u5408\u7cbe\u5ea6\u2026\uff09\u7559\u5728 note / model_notes / \u6587\u6863\u91cc\uff0c
    \u8fd9\u91cc\u53ea\u8bf4\u4eba\u8bdd\u2014\u2014\u754c\u9762\u3001\u65e5\u5fd7\u3001\u81ea\u68c0\u90fd\u7528\u8fd9\u4e00\u4efd\uff0c\u907f\u514d\u4e09\u5904\u5404\u5199\u4e00\u5957\u3002
    """
    tv, pv = e.get("token_verdict"), e.get("peak_verdict")
    prof = e.get("model_profile") or {}
    size = prof.get("size_gb")
    dur = e["frames_seconds"]
    card = e["card_gb"]
    lo, hi = e.get("est_peak_lo_gb"), e.get("est_peak_gb")
    rng = ("%.0f\u2013%.0f" % (lo, hi)) if (lo is not None and hi - lo > 0.4) else ("%.0f" % hi)
    msize = ("\u6a21\u578b %.1f GB" % size) if size else "\u6a21\u578b\u4f53\u79ef\u672a\u77e5"

    if tv == "over":
        verdict = "\u9884\u8ba1\u8dd1\u4e0d\u52a8\uff0c\u5efa\u8bae\u964d\u4e00\u6863"
        reason = ("%.0f \u79d2 @%sMP \u7684\u7b97\u91cf\u5df2\u7ecf\u8d85\u8fc7 %s GB \u5361\u80fd\u627f\u53d7\u7684\u7ecf\u9a8c\u4e0a\u9650\u3002"
                  % (dur, e["megapixels"], card))
        adv = "\u964d\u5230 \u2264%.0f \u79d2 \u6216 \u2264%.2f MP" % (e["max_duration_s_at_this_mp"],
                                        e["max_megapixels_at_this_duration"])
    elif pv == "over":
        verdict = "\u9884\u8ba1\u8d85\u51fa\u663e\u5b58"
        reason = "\u8fde\u6700\u4e50\u89c2\u7684\u4f30\u8ba1\u90fd\u8d85\u8fc7 %s GB \u5361\u4e86\uff08%s + %.0f \u79d2\u7684\u7b97\u91cf\uff09\u3002" % (card, msize, dur)
        adv = "\u964d\u753b\u5e45\u6216\u7f29\u77ed\u65f6\u957f"
    elif pv == "offload":
        verdict = "\u80fd\u8dd1\uff0c\u4f46\u4f1a\u8d34\u9876\u53d8\u6162"
        tok_gb = e["kb_per_token"] * e["tokens"] / 1000.0
        reason = ("\u6a21\u578b %.1f GB \uff0b %.0f \u79d2\u7684\u7b97\u91cf\u7ea6 %.0f GB\uff0c\u5408\u8ba1\u5df2\u7ecf\u9876\u5230 %s GB \u4e0a\u9650\u2014\u2014ComfyUI \u4f1a\u81ea\u52a8\u5378\u8f7d\u6743\u91cd\u786c\u6491\uff0c"
                  "\u80fd\u51fa\u7247\uff0c\u4f46\u6bcf\u6b65\u660e\u663e\u66f4\u6162\u3002" % (size or 0.0, dur, tok_gb, card))
        adv = None
    elif pv == "tight":
        verdict = "\u80fd\u8dd1\uff0c\u4f46\u5df2\u7ecf\u5f88\u8d34\u4e0a\u9650"
        reason = "\u6309\u4f60\u81ea\u5df1\u8dd1\u51fa\u6765\u7684\u6570\u636e\uff0c\u5cf0\u503c%s GB \u5df2\u7ecf\u5f88\u63a5\u8fd1 %s GB \u5361\u7684\u53ef\u7528\u4e0a\u9650\u3002" % (rng, card)
        adv = "\u60f3\u66f4\u7a33\u5c31\u964d\u4e00\u6863"
    elif pv == "ok":
        verdict = "\u9884\u8ba1\u53ef\u4ee5\u8dd1"
        reason = "%s + %.0f \u79d2\u7684\u7b97\u91cf\uff0c\u5728 %s GB \u5361\u80fd\u627f\u53d7\u7684\u8303\u56f4\u91cc\u3002" % (msize, dur, card)
        adv = None
    else:
        verdict = "\u8fd8\u4f30\u4e0d\u51c6\uff0c\u5148\u8dd1\u4e00\u6863"
        if not e.get("model_profile", {}).get("name"):
            reason = "\u8fd8\u6ca1\u9009\u6a21\u578b\uff1a\u9009\u597d\u4e4b\u540e\u4f1a\u6309\u5b83\u7684\u4f53\u79ef\u6765\u4f30\uff1b\u5148\u8dd1\u4e00\u6863\u4e5f\u80fd\u7528\u4f60\u81ea\u5df1\u7684\u5b9e\u6d4b\u6570\u636e\u6765\u6807\u5b9a\u3002"
        else:
            reason = "\u8fd9\u4e2a\u6a21\u578b\u7684\u4f53\u79ef\u8bfb\u4e0d\u51fa\u6765\uff0c\u53ea\u80fd\u7ed9\u504f\u4f4e\u4f30\u8ba1\uff1b\u8dd1\u4e00\u6863\u4e4b\u540e\u5c31\u7528\u4f60\u7684\u5b9e\u6d4b\u6570\u636e\u6765\u4f30\u3002"
        adv = None

    numbers = "\u9884\u6d4b\u5cf0\u503c %s GB / \u53ef\u7528 %.1f GB \u00b7 %d \u5e27\uff08%.1f \u79d2\uff09" % (
        rng, e["usable_gb"], e["frames"], dur)
    out = {"verdict": verdict, "reason": reason, "numbers": numbers}
    if adv:
        out["advice"] = "\u5efa\u8bae\uff1a" + adv
    return out


def user_text(e):
    """user_line \u7684\u5355\u884c\u7248\u672c\uff08\u65e5\u5fd7/CLI/\u81ea\u68c0\u7528\uff09\u3002"""
    u = user_line(e)
    txt = "%s \u2014\u2014 %s" % (u["verdict"], u["reason"])
    if u.get("advice"):
        txt += " %s\u3002" % u["advice"]
    return txt + "\uff08%s\uff09" % u["numbers"]


def format_line(e, with_suggestion=True):
    """\u4e00\u884c\u6458\u8981\uff08\u65e5\u5fd7/\u63a5\u53e3/\u9875\u9762\u5171\u7528\uff09\u3002\u672a\u6807\u5b9a\u7528 \u2265\uff1b\u6709\u6a21\u578b\u6863\u6848\u65f6\u7ed9\u533a\u95f4\uff1b\u6807\u5b9a\u540e\u7ed9\u5355\u503c\u3002"""
    lo, hi = e.get("est_peak_lo_gb"), e.get("est_peak_gb")
    if e.get("lower_bound"):
        peak = "\u2265 %.1f" % hi
    elif lo is not None and abs(hi - lo) > 0.3:
        peak = "%.1f\u2013%.1f" % (lo, hi)
    else:
        peak = "%.1f" % hi
    prof = (e.get("model_profile") or {})
    pinfo = ""
    if prof.get("format") and prof["format"] != "\u672a\u77e5":
        pinfo = "\uff5c\u6a21\u578b %s%s" % (prof["format"], (" %.2f GB" % prof["size_gb"]) if prof.get("size_gb") else "")
    txt = ("%d \u5e27\uff08%.1f \u79d2\uff09\u00b7 %s token / \u5305\u7ebf %s\uff08%s\uff09\u00b7 \u5cf0\u503c %s GB / \u53ef\u7528 %.1f GB\uff08%s\uff09%s"
           % (e["frames"], e["frames_seconds"], format(e["tokens"], ","),
              format(e["envelope_tokens"], ","), e["token_verdict"],
              peak, e["usable_gb"], e["peak_verdict"], pinfo))
    if with_suggestion and e["token_verdict"] == "over":
        tips = []
        if e["max_duration_s_at_this_mp"]:
            tips.append("\u65f6\u957f \u2264 %.1f \u79d2" % e["max_duration_s_at_this_mp"])
        if e["max_megapixels_at_this_duration"]:
            tips.append("\u753b\u5e45 \u2264 %.2f MP" % e["max_megapixels_at_this_duration"])
        if tips:
            txt += "\uff1b\u5efa\u8bae\uff1a" + " \u6216 ".join(tips)
    return txt


def main(argv=None):
    p = argparse.ArgumentParser(description="\u663e\u5b58/\u65f6\u957f\u9884\u7b97\u4f30\u8ba1\uff08\u6309\u65f6\u957f\u3001\u753b\u5e45\u3001\u663e\u5361\u4e0e\u6a21\u578b\u4f30\u7b97\uff09")
    p.add_argument("--duration", type=float, required=True, help="\u65f6\u957f\uff08\u79d2\uff09")
    p.add_argument("--megapixels", type=float, default=0.6, help="\u753b\u5e45\uff08MP\uff0c\u9ed8\u8ba4 0.6\uff09")
    p.add_argument("--card", type=float, default=24.0, help="\u663e\u5361\u6807\u79f0\u663e\u5b58 GB\uff08\u9ed8\u8ba4 24\uff09")
    p.add_argument("--model", default=None, help="\u6a21\u578b\u540d\uff08\u7528\u4e8e\u4ece\u540d\u5b57\u63a8\u65ad\u6743\u91cd\u683c\u5f0f int8/w4a8/nvfp4/gguf\u2026\uff09")
    p.add_argument("--model-gb", type=float, default=None, help="\u6a21\u578b\u6587\u4ef6\u4f53\u79ef GB\uff08\u53ef\u9009\uff1bComfyUI \u53ef\u81ea\u52a8\u63d0\u4f9b\uff09")
    a = p.parse_args(argv)
    e = estimate(a.duration, a.megapixels, a.card, model=a.model, model_gb=a.model_gb)
    print(format_line(e))
    prof = e.get("model_profile") or {}
    if prof.get("format") and prof["format"] != "\u672a\u77e5":
        print("  \u6a21\u578b\u6863\u6848\uff1a%s%s%s" % (prof["format"],
                                 ("  %.2f GB" % prof["size_gb"]) if prof.get("size_gb") else "  \u4f53\u79ef\u672a\u77e5",
                                 "\uff08\u9700\u53cd\u91cf\u5316\uff09" if prof.get("needs_dequant") else ""))
    for n in e.get("model_notes") or []:
        print("    \u00b7 %s" % n)
    print("  latent token = %d\uff08\u6bcf\u5e27 %d\uff09\u00b7 base %.2f GB + %.4f GB/1k token"
          % (e["tokens"], e["per_frame_tokens"], e["base_gb"], e["kb_per_token"]))
    print("  \u5cf0\u503c\u533a\u95f4 = %.1f\u2013%.1f GB \u00b7 %s" % (e["est_peak_lo_gb"], e["est_peak_gb"], e["note"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
