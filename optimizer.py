#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ref2VA \u63d0\u793a\u8bcd\u4f18\u5316\u5668\uff08\u987a\u5e8f\u722c\u5c71\uff09\u3002

\u7528\u6cd5:
  python optimizer.py --config <config.json> [--dry-run]
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "core"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import ref2va_auto as ra
from llm import LLM

ASPECT_LABELS = [
    "16:9 (Widescreen)", "1:1 (Square)", "9:16 (Portrait Widescreen)",
    "4:3 (Standard)", "3:4 (Portrait Standard)",
]


def normalize_aspect(a):
    """\u628a\u6bd4\u4f8b\u89c4\u8303\u6210 ResolutionSelector \u9700\u8981\u7684\u5b8c\u6574\u6807\u7b7e\uff084:3 \u2192 '4:3 (Standard)'\uff09\u3002"""
    if not a:
        return None
    a = str(a).strip()
    for label in ASPECT_LABELS:
        if a == label or a == label.split(" ")[0]:
            return label
    return a


def ask(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    try:
        v = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        v = ""
    return v if v else (default if default is not None else "")


# ============================================================ \u5de5\u5177
_T_T = {}
def _ts():
    return time.strftime("%H:%M:%S")

def _stage(name):
    _T_T[name] = time.time()
    print(f"[{_ts()}] \u25b8 \u9636\u6bb5\u5f00\u59cb \u00b7 {name}")
    return name

def _stage_end(name):
    t0 = _T_T.pop(name, None)
    if t0 is None:
        return
    print(f"[{_ts()}] \u25c2 \u9636\u6bb5\u7ed3\u675f \u00b7 {name}\uff08\u8017\u65f6 {time.time()-t0:.1f}s\uff09")


QUICK_FACTOR = 0.707     # \u5feb\u901f\u6e32\u67d3\uff1a\u5206\u8fa8\u7387(megapixels)\u4e0e\u91c7\u6837\u6b65\u6570\u5747\u4e58\u6b64\u7cfb\u6570


def _flow(cfg):
    """\u5f53\u524d\u6d41\u7a0b\uff1aref2va\uff08\u53c2\u8003\u56fe/\u89c6\u9891\u2192\u89c6\u9891\uff0c\u516d\u6bb5\u82f1\u6587\uff09\u6216 i2va\uff08\u9996\u5e27\u56fe\u751f\u89c6\u9891\uff0c\u4e09\u5b57\u6bb5\u82f1\u6587\uff09\u3002"""
    return (cfg.get("flow") or "ref2va").strip().lower()


def _quick_scale(cfg, megapixels, steps):
    """\u5feb\u901f\u6e32\u67d3\u6a21\u5f0f\uff08\u4e24\u6761\u6d41\u7a0b\u901a\u7528\uff09\uff1a
    \u6a21\u578b / \u91c7\u6837\u5668 / \u65f6\u957f / \u753b\u5e45 / LoRA **\u5168\u90e8\u4e0e\u7cbe\u6e32\u76f8\u540c**\uff0c\u53ea\u628a\u4e24\u4ef6\u4e8b\u7f29\u4e0b\u6765\uff1a
      \u00b7 \u5206\u8fa8\u7387 megapixels  \u00d7 0.707\uff08\u6309 ResolutionSelector \u7684 step=0.1 \u5411\u4e0b\u53d6\u6574\uff09
      \u00b7 \u91c7\u6837\u6b65\u6570 steps      \u00d7 0.707\uff08\u5411\u4e0b\u53d6\u6574\u5230\u6574\u6570\uff0c\u4e0b\u9650 1\uff09
    \u56e0\u4e3a 0.707 \u00d7 0.707 = 0.5\uff0c\u6e32\u67d3\u8017\u65f6\u7ea6\u4e3a\u7cbe\u6e32\u7684\u4e00\u534a\uff1b\u63d0\u793a\u8bcd\u9075\u4ece\u5ea6\u4e0b\u964d\u6709\u9650\u3002
    \u4e0d\u505a\u4efb\u4f55\u5185\u7f6e LoRA \u6ce8\u5165\u2014\u2014\u8981\u52a0\u901f\u7531\u7528\u6237\u5728\u9875\u9762\u300cLoRA\u300d\u533a\u81ea\u884c\u52a0\u8f7d\u3002"""
    if not cfg.get("quick_render"):
        return megapixels, steps
    mp = megapixels
    if mp:
        mp = math.floor(float(mp) * QUICK_FACTOR * 10.0) / 10.0
        mp = max(mp, 0.1)
    st = max(1, int(math.floor(int(steps) * QUICK_FACTOR)))
    return mp, st


def build_gcfg(cfg, prompt, seed):
    flow = _flow(cfg)
    i2v = flow == "i2va"
    # \u5feb\u901f\u6e32\u67d3\uff1a\u4ec5\u7f29\u5206\u8fa8\u7387\u4e0e\u6b65\u6570\uff0c\u5176\u4f59\uff08\u6a21\u578b/\u91c7\u6837\u5668/\u65f6\u957f/\u753b\u5e45/LoRA\uff09\u4e0e\u7cbe\u6e32\u5b8c\u5168\u4e00\u81f4
    mp, st = _quick_scale(cfg, cfg.get("megapixels"), cfg.get("steps", 20))
    return {
        "prompt": prompt,
        "flow": flow,
        # I2VA \u53ea\u7528\u7b2c 1 \u5f20\u53c2\u8003\u56fe\u4f5c\u4e3a\u89c6\u9891\u9996\u5e27\uff08make_graph_i2v \u5185\u90e8\u53d6 ref_images[0]\uff09
        "ref_images": cfg["_ref_names"][:1] if i2v else cfg["_ref_names"],
        "ref_audios": cfg["_aud_names"],
        "seed": seed,
        "duration_s": cfg.get("duration", 10),
        "steps": st, "denoise": 1.0,
        "model": cfg.get("model"), "clip": cfg.get("clip"), "weight_dtype": "default",
        "loras": cfg.get("loras") or [],
        "sampler": cfg.get("sampler"), "scheduler": cfg.get("scheduler"),
        "megapixels": mp,
        "aspect_ratio": normalize_aspect(cfg.get("aspect")),
        # I2VA \u53ea\u5403\u9996\u5e27\uff0c\u6ca1\u6709 B \u65b9\u5f0f\uff08\u89c6\u9891\u7f16\u8f91\uff09\u6f14\u5316
        "video_ref": None if i2v else cfg.get("video_ref"),
    }


def render(gcfg, rundir):
    _stage("\u6e32\u67d3")
    if (gcfg.get("flow") or "ref2va") == "i2va":
        print(f"  \u23f3 I2VA \u9996\u5e27\u56fe\u751f\u89c6\u9891\uff08{gcfg.get('steps')} \u6b65 \u00b7 {gcfg.get('megapixels')}MP\uff09")
        graph = ra.make_graph_i2v(gcfg)
    else:
        print(f"  \u23f3 Ref2VA\uff08{gcfg.get('steps')} \u6b65 \u00b7 {gcfg.get('megapixels')}MP\uff09")
        graph = ra.make_graph(gcfg)
    print(f"  \u23f3 ComfyUI \u6e32\u67d3\u4e2d\uff08{rundir}\uff09\uff0c\u6b64\u6b65\u901a\u5e38\u9700\u8981\u6570\u5206\u949f\uff0c\u8bf7\u8010\u5fc3\u7b49\u5f85\u2026")
    res = ra.submit_and_fetch(graph, rundir, timeout_s=7200)
    vids = ra.extract_videos(res)
    _stage_end("\u6e32\u67d3")
    return vids[0] if vids else None


def _sync_video_ref(video_path):
    """\u628a\u89c6\u9891\u9001\u5165 ComfyUI input\uff08\u4f18\u5148\u7528 /upload\uff0c\u5931\u8d25\u56de\u9000\u672c\u5730\u62f7\uff09\uff0c\u8fd4\u56de\u6587\u4ef6\u540d\u4f9b VHS_LoadVideo \u5f15\u7528\u3002"""
    if not video_path or not os.path.exists(video_path):
        return None
    try:
        name = ra.comfy_upload(video_path)
        print(f"  [\u53c2\u8003\u89c6\u9891] \u5df2\u4e0a\u4f20\u5230 ComfyUI: {name}", file=sys.stderr)
        return name
    except Exception as e:
        print(f"    [warn] \u53c2\u8003\u89c6\u9891\u4e0a\u4f20\u5931\u8d25\uff0c\u56de\u9000\u672c\u5730\u62f7\u8d1d: {str(e)[:80]}", file=sys.stderr)
    import shutil
    int_dir = os.environ.get("COMFYUI_INPUT_DIR", os.path.join(os.getcwd(), "input"))
    os.makedirs(int_dir, exist_ok=True)
    name = f"vidref_{abs(hash(video_path)) % 10 ** 7}_{os.path.basename(video_path)}"
    shutil.copy(video_path, os.path.join(int_dir, name))
    return name


def _parse_critic_robust(raw):
    """\u89e3\u6790\u8bc4\u5ba1\u6587\u672c\u4e3a dict\u3002\u5148\u4e25\u683c parse_critic\uff0c\u5931\u8d25\u5219\u4ece\u540e\u5f80\u524d\u627e\u6700\u540e\u4e00\u4e2a\u5e73\u8861\u7684 {...}\u3002
    \u601d\u8003\u94fe\u6a21\u578b\u53ef\u80fd\u628a\u601d\u8003\u4e0e\u6700\u7ec8 JSON \u62fc\u5728\u4e00\u8d77\u3002"""
    c = ra.parse_critic(raw)
    if isinstance(c, dict):
        return c
    text = (raw or "").strip()
    for i in range(len(text) - 1, -1, -1):
        if text[i] != "}":
            continue
        depth = 0
        for j in range(i, -1, -1):
            if text[j] == "}":
                depth += 1
            elif text[j] == "{":
                depth -= 1
                if depth == 0:
                    cand = text[j:i + 1]
                    try:
                        return json.loads(cand)
                    except Exception:
                        break
    return None


# ============================================================ \u97f3\u9891\u53cc\u901a\u9053\u8bc4\u5ba1
# \u81ea\u52a8\u68c0\u6d4b\u662f\u5426\u6d89\u58f0\uff08audio_scoring=auto \u65f6\u7528\uff09\u3002\u53ea\u8981\u76ee\u6807/\u60c5\u8282/\u53c2\u8003\u97f3\u9891\u547d\u4e2d\u5176\u4e00\u5373\u5224\u5b9a\u9700\u8981\u97f3\u9891\u8bc1\u636e\u3002
_AUDIO_KEYWORDS = [
    "\u58f0", "\u97f3", "\u53eb", "\u54fc", "\u5598\u606f", "\u547c\u5438", "\u8bf4\u8bdd", "\u5bf9\u767d", "\u4f4e\u8bed", "\u8bed\u97f3",
    "voice", "audio", "sound", "whisper", "breath", "gasp", "sigh", "cry",
    "\u558a", "\u54ed", "\u7b11", "\u5531", "\u94c3", "\u96e8\u58f0", "\u73af\u5883\u97f3", "\u95f7\u54fc",
]


def _audio_mode(cfg, story):
    """\u8fd4\u56de\u8be5\u4efb\u52a1\u662f\u5426\u542f\u7528\u97f3\u9891\u8bc4\u5ba1\u901a\u9053\u3002audio_scoring: on/off/auto\uff08\u9ed8\u8ba4 auto\uff09\u3002"""
    mode = (cfg.get("audio_scoring") or "auto").lower()
    if mode == "on":
        return True
    if mode == "off":
        return False
    # auto\uff1a\u60c5\u8282/\u4f18\u5316\u76ee\u6807 \u6216 \u6709\u53c2\u8003\u97f3\u9891 \u2192 \u542f\u7528
    blob = (f"{story} {cfg.get('optimize_target') or ''}").lower()
    if any(k in blob for k in _AUDIO_KEYWORDS):
        return True
    if cfg.get("_aud_names"):
        return True
    return False


def _extract_audio(video, rundir):
    """\u7528 ffmpeg \u4ece\u89c6\u9891\u62bd\u97f3\u9891\u8f68 \u2192 wav(16k/mono)\u3002\u65e0\u97f3\u8f68\u8fd4\u56de None\u3002"""
    import shutil
    if not shutil.which("ffmpeg"):
        print("    \u26a0 \u65e0 ffmpeg\uff0c\u65e0\u6cd5\u62bd\u97f3\u9891\u7ed9\u97f3\u9891\u8bc4\u5ba1", file=sys.stderr)
        return None
    out = os.path.join(rundir, "audio_audit.wav")
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", out],
        capture_output=True)
    if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
        return out
    return None


# \u97f3\u9891\u5ba1\u542c\u6a21\u578b\uff1a\u53ea\u8f93\u51fa\u300c\u5b9e\u6d4b\u542c\u5230\u4ec0\u4e48 + \u4e0e\u5baa\u6cd5\u97f3\u9891\u7ea6\u675f\u7684\u76f8\u7b26/\u504f\u79bb\u300d\uff0c\u4e0d\u8f93\u51fa\u6700\u7ec8\u5206\uff08\u6700\u7ec8\u5206\u4ea4\u7ed9\u753b\u9762 LLM \u7edf\u4e00\u8bc4\uff09\u3002
SYSTEM_AUDIO_CRITIC = (
    "\u4f60\u662f\u89c6\u9891\u97f3\u9891\u8f68\u5ba1\u542c\u5458\u3002\u8ba4\u771f\u542c\u8f93\u5165\u97f3\u9891\uff0c\u5ba2\u89c2\u8f6c\u8ff0\u4f60\u5b9e\u9645\u542c\u5230\u7684\u58f0\u97f3\uff0c"
    "\u5e76\u4e0e\u5267\u60c5/\u5baa\u6cd5\u91cc\u8981\u6c42\u7684\u58f0\u97f3\u7ea6\u675f\u9010\u6761\u6838\u5bf9\uff0c\u6307\u51fa\u76f8\u7b26\u6216\u504f\u79bb\u3002\n"
    "\u53ea\u8f93\u51fa\u7eaf\u6587\u672c\uff0c\u7ed3\u6784\u5982\u4e0b\uff1a\n"
    "\u3010\u5b9e\u6d4b\u97f3\u9891\u3011\u2026\uff08\u5b9e\u9645\u542c\u5230\u7684\u97f3\u8272/\u97f3\u91cf/\u8282\u594f/\u5185\u5bb9/\u60c5\u7eea\uff0c\u5ba2\u89c2\u8f6c\u5199\uff0c\u542b\u6587\u5b57\u5185\u5bb9\u82e5\u6709\uff09\n"
    "\u3010\u97f3\u9891\u7ea6\u675f\u6838\u5bf9\u3011\u9010\u6761\u5217\u51fa\u8981\u6c42\u7684\u97f3\u9891\u70b9\u5b9e\u9645\u662f\u5426\u8fbe\u6210\uff08\u8fbe\u6210/\u672a\u8fbe\u6210/\u90e8\u5206\uff09\uff0c\u672a\u8fbe\u6210\u5904\u5177\u4f53\u8bf4\u660e\u5dee\u5728\u54ea\u3001\u5e94\u5982\u4f55\u6539\u3002\n"
    "\u4e0d\u8981\u8f93\u51fa JSON\u3001\u4e0d\u8981\u6253\u5206 overall\uff0c\u53ea\u505a\u5ba2\u89c2\u542c\u58f0\u4e0e\u6838\u5bf9\u3002"
)


def audio_evidence(llm_audio, video, story, prompt, rundir):
    """\u62bd\u89c6\u9891\u97f3\u8f68 \u2192 \u97f3\u9891\u6a21\u578b\u542c\u58f0 \u2192 \u8fd4\u56de\u5b9e\u6d4b\u8bc1\u636e\u6587\u672c\uff1b\u5931\u8d25\u8fd4\u56de None\u3002"""
    audio_path = _extract_audio(video, rundir)
    if not audio_path:
        print("    \u26a0 \u89c6\u9891\u65e0\u97f3\u8f68\uff0c\u97f3\u9891\u901a\u9053\u8df3\u8fc7")
        return None
    try:
        b64 = llm_audio.encode_audio(audio_path)
        fmt = os.path.splitext(audio_path)[1].lstrip(".").lower() or "wav"
        user = (
            f"# \u6545\u4e8b\u5927\u7eb2\n{story}\n\n"
            f"# \u5baa\u6cd5\uff08\u89c6\u9891/\u97f3\u9891\u4e0d\u5f97\u8fdd\u80cc\u5176\u4e2d\u4efb\u4f55\u7ea6\u675f\uff0c\u91cd\u70b9\u6838\u5bf9\u58f0\u97f3\u76f8\u5173\uff09\n{prompt}\n\n"
            "\u8bf7\u542c\u8be5\u89c6\u9891\u7684\u97f3\u9891\u8f68\u5e76\u505a\u5b9e\u6d4b\u8f6c\u5199 + \u97f3\u9891\u7ea6\u675f\u6838\u5bf9\u3002"
        )
        for attempt in range(1, 4):
            try:
                txt = llm_audio.audio(SYSTEM_AUDIO_CRITIC, user, b64,
                                      audio_format=fmt, temperature=0, max_tokens=4000)
                if txt and len(txt) > 10:
                    return txt
            except Exception as e:
                print(f"    \u26a0 \u97f3\u9891\u5ba1\u542c\u5931\u8d25({attempt}/3): {str(e)[:80]}")
        return None
    except Exception as e:
        print(f"    \u26a0 \u97f3\u9891\u8bc1\u636e\u751f\u6210\u5931\u8d25: {str(e)[:80]}")
        return None


SYSTEM_AUDIO_ANALYZER = (
    "\u4f60\u662f\u97f3\u9891\u5206\u6790\u5458\u3002\u542c\u8f93\u5165\u7684\u53c2\u8003\u97f3\u9891\uff0c\u5ba2\u89c2\u63cf\u8ff0\u5b83\u7684\u58f0\u97f3\u7279\u5f81\uff0c\u4f9b\u89c6\u9891\u751f\u6210\u63d0\u793a\u8bcd\u4f7f\u7528\u3002\n"
    "\u53ea\u8f93\u51fa\u4e00\u6bb5\u7eaf\u6587\u672c\uff0c\u5305\u542b\uff1a\u97f3\u8272/\u58f0\u7ebf\u7279\u70b9\u3001\u97f3\u533a\u4e0e\u97f3\u9ad8\u3001\u8282\u594f/\u8bed\u901f\u3001\u60c5\u7eea\u4e0e\u8bed\u6c14\u3001"
    "\u53d1\u58f0\u5185\u5bb9(\u82e5\u6709\u6587\u5b57/\u6b4c\u8bcd)\u3001\u4e0e\u5176\u5b83\u97f3\u5c42\u7684\u5206\u79bb\u5ea6\u3002\u4e0d\u8981\u8f93\u51fa JSON\u3001\u4e0d\u8981\u6253\u5206\u3001\u4e0d\u8981\u81c6\u6d4b\uff0c\u53ea\u63cf\u8ff0\u5b9e\u9645\u542c\u5230\u7684\u3002"
)


def analyze_ref_audio(llm_audio, path, note=""):
    """\u7528\u97f3\u9891 LLM \u5206\u6790\u4e00\u6761\u53c2\u8003\u97f3\u9891\uff0c\u8fd4\u56de\u58f0\u97f3\u7279\u5f81\u63cf\u8ff0\uff1b\u5931\u8d25\u8fd4\u56de None\u3002"""
    try:
        b64 = llm_audio.encode_audio(path)
        fmt = os.path.splitext(path)[1].lstrip(".").lower() or "wav"
        user = (f"\u8fd9\u662f\u53c2\u8003\u97f3\u9891\uff0c\u7528\u9014\uff1a{note or '\u63d0\u4f9b\u58f0\u97f3/\u97f3\u8272\u53c2\u8003'}\u3002"
                "\u8bf7\u542c\u5e76\u5ba2\u89c2\u63cf\u8ff0\u5b83\u7684\u58f0\u97f3\u7279\u5f81\uff0c\u4f9b\u751f\u6210\u65f6\u8fd8\u539f\u3002")
        for attempt in range(1, 3):
            try:
                txt = llm_audio.audio(SYSTEM_AUDIO_ANALYZER, user, b64,
                                      audio_format=fmt, temperature=0, max_tokens=1000)
                if txt and len(txt) > 10:
                    return txt.strip()
            except Exception as e:
                print(f"    \u26a0 \u53c2\u8003\u97f3\u9891\u5206\u6790\u5931\u8d25({attempt}/2): {str(e)[:80]}")
        return None
    except Exception as e:
        print(f"    \u26a0 \u53c2\u8003\u97f3\u9891\u5206\u6790\u9519\u8bef: {str(e)[:80]}")
        return None


def evaluate(llm, video, story, prompt, rundir, n_frames=4, audio_llm=None,
             use_audio=None, frame_width=768, frame_jpeg=False, target=None):
    """\u8bc4\u5ba1\uff1a\u62bd\u5e27\u7ed9\u753b\u9762 LLM\u3002\u82e5 use_audio\uff0c\u5219\u5148\u97f3\u9891\u6a21\u578b\u542c\u58f0\u4ea7\u51fa\u5b9e\u6d4b\u8bc1\u636e\uff0c
    \u5e76\u5165\u753b\u9762 LLM \u7684 prompt\uff0c\u8ba9\u5b83\u7edf\u4e00\u8bc4 audio_affordance \u4e0e overall\u3002"""
    _stage("\u8bc4\u5206")
    try:
        frames = ra.extract_frames(video, rundir, n_frames=n_frames,
                                   width=frame_width, as_jpeg=frame_jpeg)
        if not frames:
            return None
        cp = (
            f"# \u6545\u4e8b\u5927\u7eb2\n{story}\n\n"
            + (f"# \u4f18\u5316\u76ee\u6807\uff08\u672c\u8f6e\u8981\u8fbe\u6210\u7684\u6838\u5fc3\uff0c\u8bc4\u5ba1\u987b\u4e25\u683c\u6838\u9a8c\u5176\u8fbe\u6210\u5ea6\uff09\n{target}\n\n" if target else "")
            + f"# \u751f\u6210\u8be5\u89c6\u9891\u4f7f\u7528\u7684\u5b8c\u6574 ref2va prompt\uff08\u5baa\u6cd5\uff1a\u89c6\u9891\u4e0d\u5f97\u8fdd\u80cc\u5176\u4e2d\u4efb\u4f55\u7ea6\u675f\uff09\n{prompt}\n\n"
        )
        if use_audio and audio_llm is not None:
            ev = audio_evidence(audio_llm, video, story, prompt, rundir)
            if ev:
                cp += (
                    f"\n# \u97f3\u9891\u5b9e\u6d4b\u8bc1\u636e\uff08\u7531\u72ec\u7acb\u97f3\u9891\u5ba1\u542c\u6a21\u578b\u5bf9\u89c6\u9891\u97f3\u8f68\u9010\u6761\u8f6c\u5199\u5e76\u6838\u5bf9\u5baa\u6cd5\uff09\n{ev}\n\n"
                    "\u8bf7\u4f9d\u636e\u4e0a\u8ff0\u3010\u97f3\u9891\u5b9e\u6d4b\u8bc1\u636e\u3011\u6765\u8bc4 audio_affordance \u4e0e\u6d89\u53ca\u58f0\u97f3\u7684\u7ea6\u675f\u7ef4\u5ea6\uff0c"
                    "\u4e0d\u8981\u51ed\u7a7a\u731c\u6d4b\u58f0\u97f3\u662f\u5426\u7b26\u5408\u3002\n\n"
                )
        cp += f"\u4e0b\u9762 {n_frames} \u5f20\u5173\u952e\u5e27\u6765\u81ea\u8be5\u89c6\u9891\uff0c\u8bf7\u9010\u7ef4\u5ea6\u6253\u5206\u5e76\u7ed9\u51fa verdict \u4e0e gaps\u3002"
        imgs = [llm.encode_image(f) for f in frames]
        for attempt in range(1, 4):
            try:
                raw = llm.vision(ra.SYSTEM_CRITIC, cp, imgs, temperature=0, max_tokens=24000)
                critic = _parse_critic_robust(raw)
                if critic is not None and critic.get("overall") is not None:
                    return critic
                print(f"    \u26a0 \u8bc4\u5ba1\u7ed3\u679c\u65e0\u6709\u6548\u8bc4\u5206(\u7b2c{attempt}/3\u6b21)\uff0c\u91cd\u8bd5\u2026")
            except Exception as e:
                print(f"    \u26a0 \u8bc4\u5ba1\u5931\u8d25: {str(e)[:80]}")
                if attempt >= 3:
                    return None
        return None
    finally:
        _stage_end("\u8bc4\u5206")


def score_of(critic):
    try:
        return float((critic or {}).get("overall"))
    except Exception:
        return None


def script_to_text(script):
    """LLM1 \u5267\u672c\uff08\u4e2d\u6587\uff09\u6e32\u67d3\u6210\u53ef\u8bfb\u6587\u672c\uff0c\u4fbf\u4e8e\u843d\u76d8\u5ba1\u9605\u3002"""
    if not isinstance(script, dict):
        return str(script)
    lines = [f"\u6897\u6982: {script.get('summary_zh') or ''}"]
    shots = script.get("shots") or []
    if shots:
        lines.append(f"\u5206\u955c ({len(shots)} \u62cd):")
        for s in shots:
            if not isinstance(s, dict):
                continue
            st = float(s.get("start_s") or 0)
            du = float(s.get("duration_s") or 0)
            b = s.get("beat") or ""
            fn = s.get("frame_note") or ""
            an = s.get("audio_note") or ""
            lines.append(f"  [{st:.1f}s-{st+du:.1f}s] {b}" + (f" | \u5e27: {fn}" if fn else "") + (f" | \u58f0: {an}" if an else ""))
    for s_ in script.get("subjects") or []:
        if isinstance(s_, dict):
            who = s_.get("who") or ""
            src = s_.get("source_hint") or ""
            lines.append(f"\u4e3b\u4f53: {who}" + (f"\uff08\u6765\u6e90: {src}\uff09" if src else ""))
    for n_ in script.get("closed_loop_notes") or []:
        lines.append(f"\u786c\u6027\u8981\u6c42: {n_}")
    return "\n".join(lines)


def _save_variant(outdir, rel_dir, data):
    """\u628a\u5355\u4e2a\u53d8\u4f53\u7684 script + prompt \u7acb\u5373\u843d\u76d8\uff0c\u4f9b\u6e32\u67d3\u5931\u8d25\u540e\u590d\u7528\u3001\u907f\u514d\u91cd\u751f\u6210\u3002"""
    try:
        d = os.path.join(outdir, rel_dir)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "prompt.txt"), "w", encoding="utf-8") as f:
            f.write(data.get("prompt") or "")
        with open(os.path.join(d, "script.json"), "w", encoding="utf-8") as f:
            json.dump(data.get("script"), f, ensure_ascii=False, indent=2)
        with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({k: data.get(k) for k in ("phase", "index", "kind", "focus", "suggestion")},
                      f, ensure_ascii=False, indent=2)
        print(f"    \U0001f4be \u5df2\u843d\u76d8 {rel_dir}/(prompt.txt, script.json)")
    except Exception as e:
        print(f"    \u26a0 \u843d\u76d8\u5931\u8d25: {str(e)[:80]}")


def _load_script_img(llm, cfg):
    """\u5199/\u6539\u5267\u672c\u65f6\u628a\u56fe1\uff08\u9996\u5e27\u53c2\u8003\uff09\u7f16\u7801\u4f9b LLM \u770b\u56fe\u8f85\u52a9\uff1b\u65e0\u56fe\u5219\u8fd4\u56de None\u3002"""
    refs_list = cfg.get("refs") or []
    if refs_list and refs_list[0].get("path"):
        try:
            b64 = llm.encode_image(refs_list[0]["path"])
            print(f"  [\u56fe1\u8f85\u52a9] \u5df2\u52a0\u8f7d\u9996\u5e27\u53c2\u8003\u56fe\u4f9b LLM \u770b\u56fe\u5199\u5267\u672c")
            return b64
        except Exception as e:
            print(f"  [\u56fe1\u8f85\u52a9] \u52a0\u8f7d\u5931\u8d25\uff0c\u56de\u9000\u7eaf\u6587\u672c: {e}")
    return None


_IMG_HINT = ("\n\n# \u9644\u56fe\u8bf4\u660e\n\u4e0b\u65b9\u9644\u56fe\u4e3a\u56fe1\uff08\u9996\u5e27/\u80cc\u666f\u73af\u5883/\u4e3b\u4f53\u521d\u59cb\u59ff\u6001/\u670d\u88c5/\u4f53\u6001\u53c2\u8003\uff09\u3002"
             "\u8bf7\u636e\u6b64\u7cbe\u786e\u8fd8\u539f\u89c6\u9891\u5f00\u5934\u7684\u573a\u666f\u3001\u4e3b\u4f53\u7684\u59ff\u6001\u3001\u670d\u88c5\u4e0e\u4f53\u6001\uff0c\u4f7f\u9996\u5e27\u4e0e\u56fe1\u5b8c\u5168\u4e00\u81f4\uff1b"
             "\u5e76\u4fdd\u8bc1\u5168\u7a0b\u955c\u5934\u65e0\u4efb\u4f55\u5207\u6362/\u8fd0\u955c/\u63a8\u62c9\u3002")

_I2VA_IMG_HINT = ("\n\n# \u9644\u56fe\u8bf4\u660e\n\u4e0b\u65b9\u9644\u56fe\u4e3a <Picture 1>\uff0c\u5373\u76ee\u6807\u89c6\u9891 0.00 \u79d2\u7684\u7b2c\u4e00\u5e27\u3002"
                  "\u8bf7\u636e\u6b64\u7cbe\u786e\u8fd8\u539f\u5176\u98ce\u683c\u3001\u4e3b\u4f53\u5916\u89c2\u3001\u6784\u56fe\u4e0e\u573a\u666f\u951a\u70b9\uff0c\u5e76\u8ba9\u540e\u7eed\u52a8\u4f5c\u4ece\u8fd9\u4e00\u5e27\u81ea\u7136\u53d1\u5c55"
                  "\uff08I2VA \u5141\u8bb8\u5206\u955c\u4e0e\u955c\u5934\u8fd0\u52a8\uff0c\u6309\u5b98\u65b9\u89c4\u5219\u5199\uff09\u3002")


def _img_hint(cfg, has_img):
    """\u5199\u5267\u672c\u65f6\u9644\u56fe\u8bf4\u660e\uff1aI2VA \u7528\u9996\u5e27\u7248\uff08\u5141\u8bb8\u5206\u955c/\u8fd0\u955c\uff09\uff0cRef2VA \u7528\u539f\u7248\uff08\u9501\u5b9a\u9996\u5e27\u4e0d\u5207\u955c\uff09\u3002"""
    if not has_img:
        return ""
    return _I2VA_IMG_HINT if _flow(cfg) == "i2va" else _IMG_HINT


def _valid_script(s):
    """\u5267\u672c\u5fc5\u987b\u975e\u7a7a\uff1a\u6709 summary_zh \u4e14\u81f3\u5c11\u4e00\u62cd\uff08\u542b beat/frame_note\uff09\u3002"""
    if not isinstance(s, dict):
        return False
    if not (s.get("summary_zh") or "").strip():
        return False
    shots = s.get("shots") or []
    return isinstance(shots, list) and any(
        isinstance(sh, dict) and ((sh.get("beat") or "").strip() or (sh.get("frame_note") or "").strip())
        for sh in shots)


def _gen_script_json(llm, system, user, img, attempts=5):
    """\u751f\u6210\u5267\u672c JSON\uff08\u5e26\u56fe\u5219\u591a\u6a21\u6001\uff09\uff0c\u5e26\u91cd\u8bd5 + \u91cd\u8bd5\u65f6\u5f3a\u63d0\u793a\uff1b\u7a7a/\u4e0d\u5b8c\u6574\u5267\u672c\u5224\u5931\u8d25\u91cd\u8bd5\u3002"""
    _stage("\u5199\u5267\u672c")
    last = None
    try:
        for attempt in range(1, attempts + 1):
            try:
                script = (llm.vision_json(system, user, [img], max_tokens=16000)
                          if img is not None else llm.chat_json(system, user, max_tokens=16000))
                if _valid_script(script):
                    return script
                last = ValueError("\u5267\u672c\u4e3a\u7a7a\u6216\u4e0d\u5b8c\u6574")
                if attempt >= attempts:
                    raise last
                print(f"    [\u91cd\u8bd5 {attempt}/{attempts}] \u5267\u672c\u4e3a\u7a7a/\u4e0d\u5b8c\u6574\uff08\u7f3a summary_zh \u6216\u5206\u955c\uff09\uff0c\u8ffd\u52a0\u5f3a\u63d0\u793a\u91cd\u8bd5\u2026")
                user = (user.rstrip() +
                        "\n\n\uff08\u6ce8\u610f\uff1a\u4f60\u8f93\u51fa\u4e86\u7a7a\u6216\u7f3a\u5c11\u5173\u952e\u5b57\u6bb5\u7684\u5267\u672c\u3002\u8bf7\u56de\u590d\u4e00\u4e2a\u5b8c\u6574\u3001\u5177\u4f53\u3001\u975e\u7a7a\u7684\u5267\u672cJSON\uff1a"
                        "summary_zh \u4e00\u53e5\u8bdd\u6982\u62ec\uff0cshots \u81f3\u5c11\u4e00\u62cd\uff08\u542b beat/frame_note/audio_note\uff09\uff0c\u5b57\u6bb5\u7167 system \u7ea6\u5b9a\u3002\uff09")
            except Exception as e:
                last = e
                if attempt >= attempts:
                    raise
                print(f"    [\u91cd\u8bd5 {attempt}/{attempts}] \u5267\u672cJSON\u5931\u8d25({type(e).__name__})\uff0c\u8ffd\u52a0\u5f3a\u63d0\u793a\u91cd\u8bd5\u2026")
                user = (user.rstrip() +
                        "\n\n\uff08\u6ce8\u610f\uff1a\u4e0a\u4e00\u8f6e\u4f60\u6ca1\u6709\u8f93\u51fa\u6700\u7ec8JSON\u5bf9\u8c61\u3002\u8bf7\u5728\u56de\u590d\u7684\u6700\u672b\u5c3e\uff0c\u5b8c\u6574\u8f93\u51fa\u4e00\u4e2a\u5408\u6cd5\u3001\u72ec\u7acb\u7684JSON\u5bf9\u8c61\uff0c"
                        "\u4e0d\u8981\u53ea\u8f93\u51fa\u601d\u8003\u8fc7\u7a0b\u3001\u4e0d\u8981markdown\u4ee3\u7801\u5757\u3002\uff09")
    finally:
        _stage_end("\u5199\u5267\u672c")
    raise last


# ============================================================ \u5355\u4e00\u5267\u672c/\u8f6c\u8bd1\u751f\u6210
def _fmt_refs(cfg):
    refs = cfg["refs"] or []
    auds = cfg["audios"] or []

    def _desc(item, name):
        n = (item or {}).get("note") or ""
        return f"{name} \u00b7 \u53c2\u8003\uff1a{n}" if n else name

    ref_txt = "\n".join(f"{i}. " + _desc(r, cfg["_ref_names"][i]) for i, r in enumerate(refs))
    aud_txt = ("\n# \u53ef\u7528\u53c2\u8003\u97f3\u9891\n" + "\n".join(f"{i}. " + _desc(a, cfg["_aud_names"][i])
                                        for i, a in enumerate(auds))
               if auds else "")
    aud_desc = cfg.get("_aud_ref_desc") or ""
    if aud_desc:
        aud_txt += "\n\n# \u53c2\u8003\u97f3\u9891\u00b7\u58f0\u97f3\u7279\u5f81\uff08\u7531\u97f3\u9891 LLM \u542c\u58f0\u5206\u6790\uff0c\u751f\u6210\u65f6\u5e94\u5c3d\u91cf\u8fd8\u539f\uff09\n" + aud_desc
    return ref_txt, aud_txt


def _translate(llm, cfg, script, tag):
    """\u628a\u5355\u4e2a\u5267\u672c\u8f6c\u8bd1\u4e3a\u5b8c\u6574\u516d\u6bb5 ref2va prompt \u7eaf\u6587\u672c\u3002

    **prompt \u524d\u7f00\u7a33\u5b9a\u6027**\uff1a\u5b98\u65b9\u6307\u5357\uff08\u7ea6 6k token\uff09\u653e\u8fdb system prompt\uff0c\u53d8\u5316\u7684\u5267\u672c JSON
    \u653e\u5230 user \u6d88\u606f\u6700\u540e\u3002\u8fd9\u6837\u540c\u4e00\u8f6e\u4f18\u5316\u91cc\u7684\u591a\u6b21\u8c03\u7528\u5171\u4eab\u540c\u4e00\u524d\u7f00\uff0c\u670d\u52a1\u7aef\uff08llama.cpp \u7b49\uff09
    \u7684 KV cache \u524d\u7f00\u590d\u7528\u53ef\u4ee5\u76f4\u63a5\u8df3\u8fc7\u6574\u4efd\u6307\u5357\u7684 prefill\u3002"""
    _stage("\u8f6c\u8bd1")
    guide = ra._read_guide()
    ref_txt, aud_txt = _fmt_refs(cfg)
    formatter_system = (
        ra.SYSTEM_FORMATTER
        + "\n\n# MiniMax \u5b98\u65b9\u5199\u4f5c\u6307\u5357\uff08\u9644\u5f55\uff0c\u5fc5\u987b\u4e25\u683c\u9075\u5b88\uff09\n" + guide
    )
    formatter_user = (
        f"# \u53ef\u7528\u53c2\u8003\u56fe\n{ref_txt}{aud_txt}\n\n"
        f"# \u5267\u672c\u4e2d\u95f4\u4ea7\u7269\uff08{tag}\uff09\n{json.dumps(script, ensure_ascii=False)}\n\n"
        "\u8bf7\u8f6c\u5199\u4e3a\u5b8c\u6574\u516d\u6bb5 ref2va prompt \u7eaf\u6587\u672c\u3002"
    )
    prompt = llm.chat(formatter_system, formatter_user, max_tokens=32000)
    _stage_end("\u8f6c\u8bd1")
    print(f"  \u251c\u2500 Ref2VA {tag}\uff08{len(prompt)} \u5b57\u7b26\uff09")
    return prompt


def _compose_i2va(llm, cfg, script, tag):
    """I2VA\uff1a\u628a\u4e2d\u6587\u5267\u672c\u4e2d\u95f4\u4ea7\u7269\u5199\u6210\u6700\u7ec8**\u82f1\u6587** I2VA \u63d0\u793a\u8bcd\uff08\u9996\u5e27\u58f0\u660e + \u4e09\u4e2a\u6838\u5fc3\u5b57\u6bb5\uff09\u3002
    \u6309\u5b98\u65b9 I2VA \u89c4\u5219\u6210\u7a3f\uff0c\u6210\u54c1\u76f4\u63a5\u5582\u7ed9 MiniMaxH3ImageToVideo\uff1b\u5267\u672c\u4ecd\u4e3a\u4e2d\u6587\uff0c
    \u4ec5\u53f0\u8bcd/\u753b\u9762\u5185\u6587\u5b57\u6309\u89c4\u8303\u9010\u5b57\u4fdd\u7559\u539f\u6587\u3002"""
    _stage("\u5199\u63d0\u793a\u8bcd")
    dur = float(cfg.get("duration", 10) or 10)
    refs = cfg.get("refs") or []
    note = (refs[0].get("note") or "").strip() if refs else ""
    ref_txt = "<Picture 1>\uff08\u76ee\u6807\u89c6\u9891 0.00 \u79d2\u7684\u9996\u5e27\uff09" + (f" \u00b7 \u53c2\u8003\uff1a{note}" if note else "")
    user = (
        f"# \u6545\u4e8b\u5927\u7eb2\n{cfg.get('story')}\n\n"
        f"# \u9996\u5e27\u53c2\u8003\u56fe\n{ref_txt}\n\n"
        f"# \u89c6\u9891\u65f6\u957f\n{dur:g} \u79d2\n\n"
        f"# \u5267\u672c\u4e2d\u95f4\u4ea7\u7269\uff08{tag}\uff09\n{json.dumps(script, ensure_ascii=False)}\n\n"
        "\u8bf7\u6309 system \u89c4\u5219\uff0c\u76f4\u63a5\u5199\u6210\u6700\u7ec8 I2VA \u82f1\u6587\u63d0\u793a\u8bcd\uff08\u9996\u5e27\u58f0\u660e + \u4e09\u4e2a\u6838\u5fc3\u5b57\u6bb5\uff09\uff0c\u53ea\u8f93\u51fa\u63d0\u793a\u8bcd\u6b63\u6587\uff1b"
        "\u53f0\u8bcd\u4e0e\u753b\u9762\u5185\u6587\u5b57\u6309\u89c4\u8303\u9010\u5b57\u4fdd\u7559\u539f\u6587\u3002"
    )
    prompt = llm.chat(ra.system_i2va(dur), user, max_tokens=32000).strip()
    _stage_end("\u5199\u63d0\u793a\u8bcd")
    print(f"  \u251c\u2500 I2VA {tag}\uff08{len(prompt)} \u5b57\u7b26\uff09")
    return prompt


def _compose(llm, cfg, script, tag):
    """\u6309\u6d41\u7a0b\u9009\u62e9\u6210\u7a3f\u65b9\u5f0f\uff1a\u4e24\u6761\u6d41\u7a0b\u6700\u7ec8\u63d0\u793a\u8bcd\u5747\u4e3a\u82f1\u6587\uff08ref2va = \u516d\u6bb5 full-reference\uff1bi2va = \u9996\u5e27\u58f0\u660e + \u4e09\u5b57\u6bb5\uff09\u3002"""
    if _flow(cfg) == "i2va":
        return _compose_i2va(llm, cfg, script, tag)
    return _translate(llm, cfg, script, tag)


def gen_fresh(llm, story, cfg, index, prev_weak=None):
    """\u751f\u6210\u4e00\u4e2a\u5168\u65b0\u7684\u5b8c\u6574\u5267\u672c\uff08\u6574\u7248\u91cd\u5199\uff09\u3002
    prev_weak\uff1a\u6b64\u524d\u672a\u8fc7\u51c6\u5165\u7ebf\u7684\u7248\u672c\u8584\u5f31\u70b9\uff0c\u7528\u6765\u8ba9\u65b0\u7248\u907f\u5f00\u540c\u6837\u95ee\u9898\u3002"""
    target = cfg.get("optimize_target") or "\u6574\u4f53\u753b\u8d28\u4e0e\u8868\u73b0\u6700\u4f18"
    dur = float(cfg.get("duration", 10) or 10)
    ref_txt, aud_txt = _fmt_refs(cfg)
    weak_hint = ""
    if prev_weak:
        weak_txt = "\n".join(
            f"- \u7248\u672c{it.get('index')}: overall={it.get('score')} | \u4f4e\u5206: {', '.join(it.get('dims') or []) or '\u65e0'} | \u5dee\u8ddd: {'; '.join(it.get('gaps') or [])[:200] or '\u65e0'}"
            for it in prev_weak[-6:])
        weak_hint = (
            "\n\n# \u6b64\u524d\u672a\u8fc7\u51c6\u5165\u7ebf\u7684\u7248\u672c\uff08\u52ff\u518d\u72af\u540c\u6837\u95ee\u9898\uff09\n"
            f"{weak_txt}\n\n\u8bf7\u8fd9\u6b21\u628a\u5267\u672c\u5199\u5f97\u660e\u663e\u66f4\u597d\uff0c\u52a1\u5fc5\u5728\u8584\u5f31\u7ef4\u5ea6\u4e0a\u505a\u5230\u7cbe\u786e\uff0c\u4f7f\u5206\u6570\u8fbe\u5230\u51c6\u5165\u7ebf\u4ee5\u4e0a\u3002"
        )
    dir_prompt = (
        f"# \u6545\u4e8b\u5927\u7eb2\n{story}\n\n# \u53ef\u7528\u53c2\u8003\u56fe\n{ref_txt}{aud_txt}\n\n"
        f"# \u4f18\u5316\u76ee\u6807\n{target}\n\n{weak_hint}\n\n"
        f"\u8bf7\u56f4\u7ed5\u4f18\u5316\u76ee\u6807\uff0c\u5168\u65b0\u521b\u4f5c\u4e00\u4e2a\u5b8c\u6574\u7684 {dur:g} \u79d2\u5267\u672c\uff08\u5206\u955c\u603b\u65f6\u957f={dur:g}s\uff09\uff0c"
        "\u671d\u6574\u4f53\u4f18\u5316\u76ee\u6807\u505a\u6574\u4f53\u4f18\u5316\u3001\u4e0d\u62c6\u5206\u76ee\u6807\uff1b\u7528\u8db3\u591f\u7cbe\u786e\u7684\u8c03\u5ea6/\u52a8\u4f5c/\u58f0\u97f3/\u8d1f\u5411\u7ea6\u675f\u63cf\u5199\u6765\u843d\u5b9e\u76ee\u6807\u3002"
    )
    script_img = _load_script_img(llm, cfg)
    img_hint = _img_hint(cfg, script_img)
    script = _gen_script_json(llm, ra.system_director(dur), dir_prompt + img_hint, script_img)
    print(f"\n  \u250c\u2500 \u5168\u65b0\u5267\u672c[{index}]")
    for _l in script_to_text(script).splitlines():
        print(f"  \u2502  {_l}")
    prompt = _compose(llm, cfg, script, f"\u51c6\u5165-\u5168\u65b0{index}")
    print("  \u2514\u2500 \u751f\u6210\u5b8c\u6bd5\uff0c\u5f00\u59cb\u6e32\u67d3\u2026")
    return {"kind": "admission_rewrite", "script": script, "prompt": prompt, "focus": "\u6574\u7248\u91cd\u5199"}


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return -1.0


def weak_parts(rec):
    """\u63d0\u53d6\u4e00\u6b21\u8bb0\u5f55\u7684\u8584\u5f31\u90e8\u5206\uff1a\u6700\u4f4e\u5206\u7ef4\u5ea6 + \u8bc4\u5ba1 gaps\u3002"""
    critic = rec.get("critic") or {}
    scores = critic.get("scores") or {}
    weak_dims = []
    if isinstance(scores, dict) and scores:
        ranked = sorted(scores.items(), key=lambda kv: _safe_float(kv[1]))
        weak_dims = [f"{d}={_safe_float(v):.1f}" for d, v in ranked[:3]]
    gaps = critic.get("gaps") or []
    return weak_dims, list(gaps[:5])


def ask_suggestion(llm, story, champion, cfg, tried):
    """\u4f9d\u4f18\u5316\u76ee\u6807\u4e0e\u5f53\u524d\u6700\u4f18\u8584\u5f31\u70b9\uff0c\u7ed9\u51fa\u4e00\u4e2a\u5177\u4f53\u4fee\u6539\u5efa\u8bae/\u5207\u5165\u65b9\u5411\u3002
    tried\uff1a\u5df2\u5728\u8be5\u57fa\u7ebf\u4e0a\u8bd5\u8fc7\u4e14\u672a\u63d0\u5347\u7684\u65b9\u5411\uff0c\u672c\u6b21\u987b\u6362\u4e00\u4e2a\u4e0d\u540c\u7684\u3002"""
    target = cfg.get("optimize_target") or "\u6574\u4f53\u753b\u8d28\u4e0e\u8868\u73b0\u6700\u4f18"
    weak_dims, gaps = weak_parts(champion)
    dims_txt = "\n".join(f"- {d}" for d in weak_dims) or "(\u65e0\u660e\u786e\u4f4e\u5206\u7ef4\u5ea6)"
    gaps_txt = "\n".join(f"- {g}" for g in gaps) or "(\u65e0)"
    tried_txt = ("\n".join(f"- {t}" for t in tried[-8:])) if tried else "(\u65e0\uff0c\u9996\u6b21\u5efa\u8bae)"
    prompt = (
        f"# \u4f18\u5316\u76ee\u6807\n{target}\n\n"
        f"# \u5f53\u524d\u6700\u4f18\u5267\u672c\u6982\u8981\n{script_to_text(champion.get('script'))}\n\n"
        f"# \u5f53\u524d\u8bc4\u5206\noverall={champion.get('score')}\n\n"
        f"# \u4f4e\u5206\u7ef4\u5ea6\uff08\u672a\u62ff\u6ee1\u5206\uff09\n{dims_txt}\n\n# \u8bc4\u5ba1\u5dee\u8ddd\n{gaps_txt}\n\n"
        f"# \u5df2\u5728\u6b64\u57fa\u7ebf\u4e0a\u8bd5\u8fc7\u4e14\u672a\u63d0\u5347\u7684\u65b9\u5411\n{tried_txt}\n\n"
        "\u8bf7\u9488\u5bf9\u4f18\u5316\u76ee\u6807\u4e0e\u4e0a\u8ff0\u8584\u5f31\u70b9\uff0c\u7ed9\u51fa\u3010\u4e00\u4e2a\u3011\u660e\u786e\u7684\u4fee\u6539\u5efa\u8bae\uff08\u5207\u5165\u89d2\u5ea6\uff09\uff1a\u5177\u4f53\u5230\u6539\u54ea\u4e00\u6bb5\u3001\u600e\u4e48\u6539\uff0c"
        "\u53ea\u9488\u5bf9\u8584\u5f31\u90e8\u5206\u505a\u5b9a\u70b9\u6539\u8fdb\uff0c\u4e0d\u52a8\u5df2\u8fbe\u6807\u5904\uff0c\u4e14\u4e0d\u8981\u63a8\u5012\u91cd\u6765\u3002"
        "\u5fc5\u987b\u4e0e\u4e0a\u9762\u300c\u5df2\u8bd5\u8fc7\u7684\u65b9\u5411\u300d\u4e0d\u540c\u3002\u53ea\u8f93\u51fa\u4e00\u6bb5\u8bdd\uff08\u65b9\u5411\u8bf4\u660e + \u5177\u4f53\u6539\u6cd5\uff09\uff0c\u4e0d\u8981\u8f93\u51fa\u5176\u4ed6\u6587\u5b57\u3002"
    )
    for _ in range(2):
        try:
            s = llm.chat("\u4f60\u662f\u89c6\u9891\u63d0\u793a\u8bcd\u4f18\u5316\u4e13\u5bb6\uff0c\u53ea\u8f93\u51fa\u5efa\u8bae\u672c\u8eab\u3002", prompt, max_tokens=2000).strip()
            if s and not s.lower().startswith(("\u597d\u7684", "\u662f", "{")):
                return s[:500]
        except Exception:
            pass
    return f"\u5f3a\u5316\u4f4e\u5206\u7ef4\u5ea6\u5e76\u4fee\u590d\u8bc4\u5ba1\u5dee\u8ddd\uff08\u907f\u5f00\u5df2\u8bd5\u65b9\u5411\uff09"


def gen_child(llm, story, champion, cfg, suggestion):
    """\u5728\u6700\u4f18\u5267\u672c\u4e0a\u6309\u5efa\u8bae\u5b9a\u70b9\u4fee\u6b63\uff0c\u751f\u6210\u4e00\u4e2a\u5b50\u53d8\u4f53\u3002"""
    target = cfg.get("optimize_target") or "\u6574\u4f53\u753b\u8d28\u4e0e\u8868\u73b0\u6700\u4f18"
    dur = float(cfg.get("duration", 10) or 10)
    weak_dims, gaps = weak_parts(champion)
    dims_txt = "\n".join(f"- {d}" for d in weak_dims) or "(\u65e0)"
    gaps_txt = "\n".join(f"- {g}" for g in gaps) or "(\u65e0)"
    ref_txt, aud_txt = _fmt_refs(cfg)
    script_img = _load_script_img(llm, cfg)
    img_hint = _img_hint(cfg, script_img)
    director_user = (
        f"# \u6545\u4e8b\u5927\u7eb2\n{story}\n\n# \u53ef\u7528\u53c2\u8003\u56fe\n{ref_txt}{aud_txt}\n\n"
        f"# \u4f18\u5316\u76ee\u6807\n{target}\n\n"
        f"# \u5f53\u524d\u6700\u4f18\u5267\u672c\n{json.dumps(champion['script'], ensure_ascii=False)}\n\n"
        f"# \u5f53\u524d\u8bc4\u5206\noverall={champion.get('score')}\n\n"
        f"# \u4f4e\u5206\u7ef4\u5ea6\uff08\u672a\u62ff\u6ee1\u5206\uff09\n{dims_txt}\n\n# \u8bc4\u5ba1\u5dee\u8ddd\n{gaps_txt}\n\n"
        f"# \u672c\u8f6e\u4fee\u6539\u5efa\u8bae\uff08\u53ea\u6309\u6b64\u5b9a\u70b9\u6539\u8fdb\uff09\n{suggestion}\n\n"
        "\u8bf7\u3010\u4fee\u6b63\u3011\u8fd9\u4e2a\u5267\u672c\uff1a\u4fdd\u6301\u6574\u4f53\u65b9\u5411\u4e0e\u98ce\u683c\u4e0d\u53d8\uff0c\u53ea\u6309\u4e0a\u9762\u7684\u5efa\u8bae\u628a\u4f4e\u5206\u7ef4\u5ea6/\u5dee\u8ddd\u6539\u597d\uff0c"
        "\u4e0d\u8981\u63a8\u5012\u91cd\u6765\u3001\u4e0d\u8981\u987a\u624b\u6539\u5df2\u8fbe\u6807\u5904\u3002"
        f"{img_hint}"
        "\u6309 system \u7ea6\u5b9a\u7684 JSON \u7ed3\u6784\u8f93\u51fa\u3002"
    )
    new_script = _gen_script_json(llm, ra.system_director(dur), director_user, script_img)
    print(f"\n  \u250c\u2500 \u5b50\u53d8\u4f53\u5267\u672c\uff08\u5efa\u8bae: {suggestion[:60]}\uff09")
    for _l in script_to_text(new_script).splitlines():
        print(f"  \u2502  {_l}")
    prompt = _compose(llm, cfg, new_script, "\u722c\u5c71-\u5b50\u53d8\u4f53")
    print("  \u2514\u2500 \u751f\u6210\u5b8c\u6bd5\uff0c\u5f00\u59cb\u6e32\u67d3\u2026")
    return {"kind": "hill_child", "script": new_script, "prompt": prompt,
            "focus": suggestion, "suggestion": suggestion}


def _report(rec):
    """\u51fa\u62a5\u544a\uff1a\u6253\u5370\u5355\u4e2a\u53d8\u4f53\u7684\u7ed3\u6784\u5316\u8bc4\u5ba1\u6458\u8981\u3002"""
    if not rec:
        return
    c = rec.get("critic") or {}
    scores = c.get("scores") or {}
    dims = " | ".join(f"{k}={_safe_float(v):.1f}" for k, v in
                      (sorted(scores.items(), key=lambda kv: _safe_float(kv[1])) if isinstance(scores, dict) else []))
    print(f"  \u250c\u2500 \u62a5\u544a \u00b7 {rec.get('label')}  [{rec.get('kind')}]")
    print(f"  \u2502  \u5207\u5165/\u5efa\u8bae: {(rec.get('focus') or '')[:80]}")
    print(f"  \u2502  overall = {rec.get('score')}")
    print(f"  \u2502  verdict = {(c.get('verdict') or '')[:200]}")
    if dims:
        print(f"  \u2502  \u5206\u7ef4\u5ea6: {dims}")
    print(f"  \u2502  \u89c6\u9891: {rec.get('video')}")
    print("  \u2514\u2500")


def run_attempt(llm, cand, story, cfg, outdir, label, seed, index, audio_llm=None,
                use_audio=False):
    """\u628a\u5355\u4e2a\u53d8\u4f53\u4fdd\u5b58 + \u6e32\u67d3 + \u8bc4\u5ba1\u6253\u5206 + \u51fa\u62a5\u544a\uff0c\u8fd4\u56de\u8bb0\u5f55\uff08score \u53ef\u80fd\u4e3a None\uff09\u3002"""
    rd = os.path.join(outdir, label)
    os.makedirs(rd, exist_ok=True)
    _save_variant(outdir, label, {**cand, "phase": None, "index": index})
    print(f"  \u23f3 \u6e32\u67d3 {label}\u2026")
    video = render(build_gcfg(cfg, cand["prompt"], seed), rd)
    if not video:
        print(f"    \u2717 {label} \u65e0\u8f93\u51fa\uff0c\u8df3\u8fc7")
        return None
    critic = evaluate(llm, video, story, cand["prompt"], rd,
                      audio_llm=audio_llm, use_audio=use_audio,
                      n_frames=int(cfg.get("review_frames", 32)),
                      frame_width=int(cfg.get("review_frame_width", 448)),
                      frame_jpeg=bool(cfg.get("review_frame_jpeg", True)),
                      target=cfg.get("optimize_target"))
    sc = score_of(critic)
    rec = {**cand, "label": label, "index": index, "video": video, "critic": critic, "score": sc}
    _report(rec)
    return rec


# ============================================================ \u4e3b\u6d41\u7a0b
def run_optimizer(cfg, llm):
    outdir = cfg["outdir"]
    os.makedirs(outdir, exist_ok=True)
    seed = int(cfg["seed"]) if cfg.get("seed") is not None else random.randint(0, 2**31 - 1)
    story = cfg["story"]
    i2v = _flow(cfg) == "i2va"
    video_edit = bool(cfg.get("video_edit")) and not i2v
    if i2v:
        cfg["video_edit"] = False        # I2VA \u53ea\u5403\u9996\u5e27\u56fe\uff0c\u6ca1\u6709 B \u65b9\u5f0f\uff08\u89c6\u9891\u7f16\u8f91\uff09\u6f14\u5316
        cfg["video_ref"] = None
    if video_edit:
        cfg["video_ref"] = None   # \u51c6\u5165\u9996\u6b65\u65e0\u4e0a\u4e00\u6b65\u89c6\u9891\uff0c\u4e0d\u6ce8\u5165\uff1b\u722c\u5c71/\u7cbe\u6e32\u9636\u6bb5\u518d\u5e26\u4e0a\u4e00\u6b65\u751f\u6210\u7684\u89c6\u9891

    admission = float(cfg.get("admission_threshold", 5))     # \u51c6\u5165\u7ebf
    max_iter = int(cfg.get("max_iterations", 12))            # \u603b\u751f\u6210\u6b21\u6570\u4e0a\u9650
    base_patience = int(cfg.get("base_patience", 3))         # \u540c\u4e00\u57fa\u7ebf\u8fde\u7eed\u672a\u63d0\u5347\u591a\u5c11\u6b21\u505c
    threshold = cfg.get("threshold")                          # \u65e9\u671f\u8fbe\u6807\u7ebf(\u53ef\u9009)
    manual = (cfg.get("stop_mode") or "auto") == "manual"

    print("=" * 60)
    print("\u63d0\u793a\u8bcd\u4f18\u5316\u5668\uff08\u987a\u5e8f\u722c\u5c71 \u00b7 \u51c6\u5165\u2192\u6f14\u8fdb\uff09")
    print(f"\u6d41\u7a0b     : {'I2VA \u00b7 \u9996\u5e27\u56fe\u751f\u89c6\u9891\uff08\u82f1\u6587\u63d0\u793a\u8bcd\uff1a\u9996\u5e27\u58f0\u660e + \u4e09\u5b57\u6bb5\uff09' if i2v else 'Ref2VA \u00b7 \u53c2\u8003\u56fe/\u89c6\u9891\uff08\u516d\u6bb5\u82f1\u6587\uff09'}")
    print(f"\u670d\u52a1\u5668   : {ra.get_comfy_url()}")
    print(f"\u5199\u5165/\u8bc4\u5206 LLM: {getattr(llm, 'base', '?')}  /  {getattr(llm, 'model', '?')}")
    if i2v:
        print("\u53c2\u8003\u65b9\u5f0f : \u9996\u5e27\u53c2\u8003\u56fe\uff08\u5f3a\u5236\u4f5c\u4e3a\u89c6\u9891\u7b2c\u4e00\u5e27\uff09| \u65e0\u5feb\u901f\u6e32\u67d3\u6a21\u5f0f | \u4e0d\u5403\u53c2\u8003\u97f3\u9891")
        print(f"\u53c2\u8003\u56fe   : {len(cfg['_ref_names'][:1])} \u5f20\uff08\u4ec5\u53d6\u7b2c 1 \u5f20\u4f5c\u9996\u5e27\uff09")
    else:
        print(f"\u53c2\u8003\u65b9\u5f0f : {'B \u00b7 \u89c6\u9891\u7f16\u8f91\uff08\u81ea\u52a8\u7528\u4e0a\u4e00\u6b65\u89c6\u9891\uff09' if cfg.get('video_edit') else 'A \u00b7 \u4ec5\u53c2\u8003\u56fe/\u6587\u5b57'}")
        print(f"\u53c2\u8003\u56fe   : {len(cfg['_ref_names'])} \u5f20 | \u97f3\u9891: {len(cfg['_aud_names'])} \u6761")
    print(f"\u89c6\u9891     : {cfg.get('megapixels')}MP {normalize_aspect(cfg.get('aspect'))} {cfg.get('duration')}s")
    print(f"\u79cd\u5b50     : {seed}\uff08\u5168\u7a0b\u6052\u5b9a\uff09| \u51c6\u5165\u7ebf\u2265{admission} | \u8fed\u4ee3\u4e0a\u9650 {max_iter} | \u540c\u57fa\u7ebf\u8010\u5fc3 {base_patience}")
    print("=" * 60)

    # ---- \u524d\u7f6e\u4f9d\u8d56\u68c0\u67e5\uff1affmpeg\uff08\u8bc4\u5206\u62bd\u5e27/\u62bd\u97f3\u9891\u5fc5\u9700\uff09----
    import shutil
    if not shutil.which("ffmpeg"):
        print("\u2717 \u672a\u68c0\u6d4b\u5230 ffmpeg\uff1a\u8bc4\u5ba1\u9700\u8981\u7528\u5b83\u4ece\u89c6\u9891\u62bd\u5e27\uff08\u4ee5\u53ca\u53ef\u9009\u62bd\u97f3\u9891\uff09\u3002", file=sys.stderr)
        print("  \u8bf7\u5148\u5b89\u88c5 ffmpeg \u5e76\u52a0\u5165\u7cfb\u7edf PATH\uff0c\u5426\u5219\u65e0\u6cd5\u4f18\u5316\u8bc4\u5206\uff1a", file=sys.stderr)
        print("  \u00b7 Windows: winget install ffmpeg   \u6216   \u4ece https://ffmpeg.org/download.html \u4e0b\u8f7d\u89e3\u538b\uff0c"
              "\u628a bin \u76ee\u5f55\u52a0\u5165 PATH \u540e\u91cd\u5f00\u7ec8\u7aef\u3002", file=sys.stderr)
        sys.exit(2)

    attempts = []       # \u6240\u6709\u5df2\u6e32\u67d3\u5c1d\u8bd5\uff08\u51c6\u5165\u91cd\u5199 + \u722c\u5c71\u5b50\u53d8\u4f53\uff09
    champion = None     # \u5f53\u524d\u6700\u4f18
    iteration = 0       # \u5168\u5c40\u751f\u6210\u8ba1\u6570\uff08\u51c6\u5165\u91cd\u5199\u4e0e\u722c\u5c71\u5171\u7528\uff0c\u505c\u7ebf\u4f9d\u636e\u4e4b\u4e00\uff09
    stop_reason = None

    # ---- \u97f3\u9891\u901a\u9053\uff1a\u6d89\u58f0\u8bc4\u5206 \u6216 \u6709\u53c2\u8003\u97f3\u9891 \u65f6\u8fde\u97f3\u9891 LLM ----
    use_audio = _audio_mode(cfg, story)
    has_ref_audio = bool(cfg.get("_aud_names"))
    audio_conf = bool(cfg.get("audio_llm_base") or cfg.get("audio_llm_model"))
    need_audio_llm = use_audio or (has_ref_audio and audio_conf)
    audio_llm = None
    if need_audio_llm:
        try:
            audio_llm = LLM(model=cfg.get("audio_llm_model") or None,
                            base=cfg.get("audio_llm_base") or None,
                            api_key=cfg.get("audio_llm_api_key") or None)
            print("\U0001f3a7 \u97f3\u9891\u901a\u9053\u5f00\u542f\uff1a" + "\uff0c".join(
                [s for s in ["\u6d89\u58f0\u8bc4\u5ba1" if use_audio else "", "\u53c2\u8003\u97f3\u9891\u5206\u6790" if has_ref_audio else ""] if s]))
        except Exception as e:
            print(f"    \u26a0 \u97f3\u9891 LLM \u5b9e\u4f8b\u5316\u5931\u8d25\uff0c\u5173\u95ed\u97f3\u9891\u901a\u9053: {str(e)[:80]}")
            audio_llm = None
    else:
        print("\U0001f507 \u97f3\u9891\u901a\u9053\u5173\u95ed\uff1a\u4e0d\u6d89\u58f0\u3001\u65e0\u53c2\u8003\u97f3\u9891\uff0c\u6216\u672a\u914d\u7f6e\u97f3\u9891 LLM")

    # ---- \u53c2\u8003\u97f3\u9891\uff1a\u4ea4\u7ed9\u97f3\u9891 LLM \u542c\u58f0\uff0c\u628a\u300c\u7528\u9014 + \u58f0\u97f3\u7279\u5f81\u300d\u5199\u5165\u63d0\u793a\u8bcd\uff08\u4f9b\u5199\u5267\u672c/\u8f6c\u8bd1\u8fd8\u539f\uff09 ----
    if has_ref_audio and audio_llm is not None and not cfg.get("_aud_ref_desc"):
        try:
            descs = []
            for i, aud in enumerate(cfg["audios"] or []):
                p = aud.get("path")
                note = (aud.get("note") or "").strip()
                if p and os.path.isfile(p):
                    d = analyze_ref_audio(audio_llm, p, note)
                    if d:
                        descs.append(f"- \u53c2\u8003\u97f3\u9891{i+1}\uff08\u7528\u9014\uff1a{note}\uff09: {d}" if note else f"- \u53c2\u8003\u97f3\u9891{i+1}: {d}")
            if descs:
                cfg["_aud_ref_desc"] = "\n".join(descs)
                print(f"  [\u53c2\u8003\u97f3\u9891] \u5df2\u5206\u6790 {len(descs)} \u6761\u58f0\u97f3\u7279\u5f81 -> \u5199\u5165\u63d0\u793a\u8bcd")
        except Exception as e:
            print(f"    \u26a0 \u53c2\u8003\u97f3\u9891\u5206\u6790\u5f02\u5e38: {str(e)[:80]}")

    # ================= \u51c6\u5165 =================
    print(f"\n\u3010\u9636\u6bb5\u4e00\u00b7\u51c6\u5165\u3011\u6574\u7248\u5168\u65b0\u521b\u4f5c\u76f4\u5230 overall \u2265 {admission} \u2026")
    rew_index = 0
    prev_weak = []
    while champion is None:
        iteration += 1
        rew_index += 1
        if iteration > max_iter:
            stop_reason = f"\u8fed\u4ee3\u4e0a\u9650({max_iter}\uff0c\u51c6\u5165\u9636\u6bb5\u8017\u5149\uff0c\u672a\u8fc7\u51c6\u5165\u7ebf)"
            break
        if manual:
            if ask(f"\u51c6\u5165\u91cd\u5199\u7b2c {rew_index} \u7248\uff1f", "y").lower() not in ("y", "yes"):
                stop_reason = "\u624b\u52a8\u505c\u6b62"
                break
        _bp = os.path.join(outdir, "baseline", "prompt.txt")
        _bs = os.path.join(outdir, "baseline", "script.json")
        if rew_index == 1 and os.path.exists(_bp) and os.path.exists(_bs):
            try:
                with open(_bp, encoding="utf-8") as _f:
                    _base_prompt = _f.read()
                with open(_bs, encoding="utf-8") as _f:
                    _base_script = json.load(_f)
                cand = {"kind": "admission_rewrite", "script": _base_script,
                        "prompt": _base_prompt, "focus": "\u6574\u7248\u91cd\u5199(\u57fa\u51c6\u9884\u751f\u6210)"}
                print("  [\u57fa\u51c6] \u5df2\u8f7d\u5165\u9884\u751f\u6210\u7684 baseline script+prompt \u4f5c\u4e3a\u9996\u6b21\u51c6\u5165")
            except Exception as _e:
                print(f"  [\u57fa\u51c6] \u8f7d\u5165\u5931\u8d25\uff0c\u56de\u9000 LLM \u751f\u6210: {_e}")
                cand = gen_fresh(llm, story, cfg, rew_index, prev_weak)
        else:
            cand = gen_fresh(llm, story, cfg, rew_index, prev_weak)
        label = f"admit{rew_index:02d}"
        rec = run_attempt(llm, cand, story, cfg, outdir, label, seed, index=rew_index,
                          audio_llm=audio_llm, use_audio=use_audio)
        if rec is None:
            # \u6e32\u67d3\u5931\u8d25\uff1a\u4e0d\u8ba1\u5165 prev_weak\uff0c\u9000\u56de\u91cd\u5199\uff08\u6d88\u8017\u4e00\u6b21\u8fed\u4ee3\uff09
            continue
        attempts.append(rec)
        if rec["score"] is not None and rec["score"] >= admission:
            champion = rec
            print(f"\n  \U0001f3af \u51c6\u5165\u8fbe\u6807! overall={champion['score']} \u2265 {admission}\uff0c\u6210\u4e3a\u722c\u5c71\u57fa\u51c6")
        elif rec["score"] is None:
            print("    \u2192 \u65e0\u6709\u6548\u8bc4\u5206\uff0c\u7ee7\u7eed\u91cd\u5199\u2026")
        else:
            dims, gaps = weak_parts(rec)
            prev_weak.append({"index": rew_index, "score": rec["score"], "dims": dims, "gaps": gaps})
            print(f"    \u2192 overall={rec['score']} < {admission}\uff0c\u6574\u7248\u91cd\u5199\u5267\u672c\u2026")

    if champion is None:
        print(f"\n\u2717 \u672a\u80fd\u5728\u9884\u7b97\u5185\u8fc7\u51c6\u5165\u7ebf\uff0c\u7ec8\u6b62\u3002\u539f\u56e0: {stop_reason}")
        _finalize(outdir, champion, attempts, seed, stop_reason)
        return None

    # ================= \u722c\u5c71 =================
    print(f"\n\u3010\u9636\u6bb5\u4e8c\u00b7\u722c\u5c71\u3011\u5728\u6700\u4f18\u57fa\u7840\u4e0a\u9010\u4e2a\u6f14\u8fdb\uff08\u9000\u6b65\u5219\u540c\u57fa\u7ebf\u6362\u65b9\u5411\u91cd\u8bd5\uff0c\u8fde\u7eed {base_patience} \u6b21\u672a\u63d0\u5347\u5373\u505c\uff09\u2026")
    hill_no = 0
    while True:
        # \u505c\u7ebf\u68c0\u67e5\uff08\u6bcf\u6b65\u524d\u8fdb\u524d\uff09
        if threshold is not None and champion["score"] is not None and champion["score"] >= threshold:
            stop_reason = f"\u8fbe\u6807(overall={champion['score']} \u2265 {threshold})"
            break
        if iteration >= max_iter:
            stop_reason = f"\u8fed\u4ee3\u4e0a\u9650({max_iter})"
            break
        if manual:
            cont = ask(f"\u7ee7\u7eed\u722c\u5c71\u7b2c {hill_no + 1} \u6b65\uff08\u5f53\u524d\u6700\u4f18 overall={champion['score']}\uff09\uff1f", "n")
            if cont.lower() not in ("y", "yes"):
                stop_reason = "\u624b\u52a8\u505c\u6b62"
                break

        # \u5df2\u5728\u672c\u57fa\u7ebf\u4e0a\u8bd5\u8fc7\u4e14\u672a\u63d0\u5347\u7684\u65b9\u5411\uff0c\u7528\u4e8e\u8ba9 LLM \u6362\u65b0\u65b9\u5411
        tried_on_base = [a.get("suggestion") for a in attempts
                         if a.get("kind") == "hill_child" and not a.get("_improved")
                         and a.get("_base_score") == champion["score"]]
        tried_txt = [t for t in tried_on_base if t]

        hill_no += 1
        iteration += 1
        suggestion = ask_suggestion(llm, story, champion, cfg, tried_txt)
        print(f"\n  \U0001f4a1 \u5efa\u8bae: {suggestion}")
        cand = gen_child(llm, story, champion, cfg, suggestion)
        label = f"hill{hill_no:02d}"
        if video_edit:
            cfg["video_ref"] = _sync_video_ref(champion.get("video"))
        rec = run_attempt(llm, cand, story, cfg, outdir, label, seed, index=hill_no,
                          audio_llm=audio_llm, use_audio=use_audio)
        if rec is None:
            # \u6e32\u67d3\u5931\u8d25\uff1a\u4e0d\u63d0\u5347\u4e5f\u4e0d\u505c\uff0c\u91cd\u65b0\u7ed9\u5efa\u8bae\u518d\u6d4b\uff08\u7ee7\u7eed\u8fed\u4ee3\u8ba1\u6570\uff09
            print("    \u2192 \u6e32\u67d3\u5931\u8d25\uff0c\u9000\u56de\u5f53\u524d\u6700\u4f18\u6362\u65b9\u5411\u518d\u8bd5\u2026")
            continue
        attempts.append(rec)
        sc = rec["score"]
        cur = champion["score"]
        if sc is not None and sc > cur:
            rec["_improved"] = True
            rec["_base_score"] = cur
            champion = rec
            print(f"\n  \U0001f3c6 \u91c7\u7eb3\u65b0\u6700\u4f18! overall={sc}\uff08\u8f83 {cur} +{sc - cur:.2f}\uff09\u2192 \u7ee7\u7eed\u5f80\u524d\u722c")
        elif sc is None:
            rec["_base_score"] = cur
            print("    \u2192 \u65e0\u6709\u6548\u8bc4\u5206\uff0c\u9000\u56de\u5f53\u524d\u6700\u4f18\u6362\u65b9\u5411\u518d\u8bd5\u2026")
        else:
            rec["_base_score"] = cur
            # \u540c\u4e00\u57fa\u7ebf\u4e0a\u7684\u8fde\u7eed\u5931\u8d25\u5224\u5b9a\uff1a\u7edf\u8ba1\u8be5\u57fa\u7ebf\u4e0a\u6240\u6709\u672a\u63d0\u5347\u5b50\u53d8\u4f53
            fails_on_base = sum(1 for a in attempts
                                if a.get("kind") == "hill_child"
                                and a.get("score") is not None
                                and a.get("score") <= a.get("_base_score")
                                and a.get("_base_score") == cur)
            print(f"    \u2192 overall={sc} \u672a\u8d85\u8fc7\u5f53\u524d\u6700\u4f18 {cur}\uff08\u540c\u57fa\u7ebf\u4e0a\u5df2\u7d2f\u8ba1 {fails_on_base}/{base_patience} \u6b21\u672a\u63d0\u5347\uff09")
            if fails_on_base >= base_patience:
                stop_reason = f"\u540c\u57fa\u7ebf\u8fde\u7eed {base_patience} \u6b21\u672a\u63d0\u5347\uff08\u5237\u4e0d\u52a8\uff09"
                break
            print("    \u2192 \u9000\u56de\u5f53\u524d\u6700\u4f18\uff0c\u6362\u65b0\u65b9\u5411\u91cd\u8bd5\u2026")

    # ================= \u5c3e\u90e8\u7cbe\u7ec6\u5316\u6e32\u67d3\uff08\u5feb\u901f\u6a21\u5f0f\u53ef\u9009\u7528\u539f\u5de5\u4f5c\u6d41\u505a\u6700\u7ec8\u7cbe\u6e32\uff09 =================
    if champion is not None and cfg.get("fine_render"):
        fine_cfg = dict(cfg)
        fine_cfg["quick_render"] = False        # \u7cbe\u6e32\u6052\u4e3a\u5168\u5206\u8fa8\u7387/\u5168\u6b65\u6570
        if video_edit:
            fine_cfg["video_ref"] = _sync_video_ref(champion.get("video"))
        fine_gcfg = build_gcfg(fine_cfg, champion["prompt"], seed)
        fine_dir = os.path.join(outdir, "fine")
        print("\n[\u7cbe\u7ec6\u5316\u6e32\u67d3] \u7528\u539f\u5de5\u4f5c\u6d41\u5bf9\u6700\u4f18\u63d0\u793a\u8bcd\u505a\u4e00\u6b21\u7cbe\u7ec6\u6e32\u67d3\uff08\u5feb\u901f\u6a21\u5f0f\u5df2\u5b9a\u4f4d\u6700\u4f18\uff1b\u7cbe\u6e32\u4e3a\u6700\u7ec8\u4ea7\u7269\uff09\u2026")
        fine_video = render(fine_gcfg, fine_dir)
        if fine_video:
            champion["video_fine"] = fine_video
            print(f"  \u2705 \u7cbe\u7ec6\u6e32\u67d3\u89c6\u9891: {fine_video}")
        else:
            print("  \u26a0 \u7cbe\u7ec6\u6e32\u67d3\u65e0\u8f93\u51fa\uff0c\u56de\u9000\u4f7f\u7528\u5feb\u901f\u6e32\u67d3\u7248")

    # ================= \u6c47\u603b / \u843d\u76d8 =================
    _finalize(outdir, champion, attempts, seed, stop_reason)
    return champion


def _finalize(outdir, champion, attempts, seed, stop_reason):
    print("\n" + "=" * 60)
    if champion is None:
        print("\u3010\u4f18\u5316\u7ed3\u675f\u3011\u65e0\u8fbe\u6807\u57fa\u51c6")
        return
    print("\u3010\u4f18\u5316\u7ed3\u675f\u3011")
    print(f"  \u505c\u6b62\u539f\u56e0: {stop_reason}")
    print(f"  \u6700\u7ec8\u6700\u4f18: overall={champion['score']}  verdict={(champion.get('critic') or {}).get('verdict')}")
    print(f"  \u5feb\u901f\u7248\u89c6\u9891: {champion['video']}")
    if champion.get("video_fine"):
        print(f"  \u2705 \u7cbe\u7ec6\u6e32\u67d3\u7248\u89c6\u9891: {champion['video_fine']}")
    print(f"  \u7ecf\u5386 {len(attempts)} \u6b21\u6e32\u67d3\uff08\u51c6\u5165 {sum(1 for a in attempts if a.get('kind')=='admission_rewrite')} + \u722c\u5c71 {sum(1 for a in attempts if a.get('kind')=='hill_child')}\uff09")
    print("=" * 60)

    champ_prompt = os.path.join(outdir, "champion_prompt.txt")
    with open(champ_prompt, "w", encoding="utf-8") as f:
        f.write(champion["prompt"])
    champ_script = os.path.join(outdir, "champion_script.txt")
    with open(champ_script, "w", encoding="utf-8") as f:
        f.write(script_to_text(champion["script"]) + "\n\n# \u2014\u2014 LLM1 \u539f\u59cb JSON \u2014\u2014\n"
                + json.dumps(champion["script"], ensure_ascii=False, indent=2))
    hist = os.path.join(outdir, "optimizer_history.json")
    with open(hist, "w", encoding="utf-8") as f:
        json.dump({
            "stop_reason": stop_reason,
            "seed": seed,
            "champion": {
                "label": champion["label"], "score": champion["score"],
                "video": champion["video"],
                "video_fine": champion.get("video_fine"),
                "verdict": (champion.get("critic") or {}).get("verdict"),
            },
            "attempts": [{
                "label": a["label"], "kind": a.get("kind"), "score": a["score"],
                "video": a["video"], "verdict": (a.get("critic") or {}).get("verdict"),
                "prompt_len": len(a["prompt"]),
            } for a in attempts],
        }, f, ensure_ascii=False, indent=2)
    print(f"\n\u2705 \u5df2\u5bfc\u51fa:")
    print(f"    {champ_prompt}")
    print(f"    {champ_script}")
    print(f"    {hist}")


def load_config(path):
    with open(path, encoding="utf-8-sig") as f:
        c = json.load(f)
    c.setdefault("comfy_url", "http://127.0.0.1:8000")
    c.setdefault("refs", [])
    c.setdefault("audios", [])
    c.setdefault("model", None)
    c.setdefault("clip", None)             # CLIP \u6a21\u578b\u540d\uff08ComfyUI \u5185\u540d\u5b57\uff0c\u542b\u5b50\u76ee\u5f55\uff1b\u7a7a=\u7528\u6a21\u677f\u9ed8\u8ba4/\u524d\u6b21\u6210\u529f\uff09
    c.setdefault("loras", [])              # LoRA \u5217\u8868 [{"name":..., "strength":...}]\uff1b\u7a7a=\u4e0d\u52a0 LoRA
    c.setdefault("lora", None)             # \u517c\u5bb9\u65e7\u5355 LoRA \u5b57\u6bb5\uff1b\u4e00\u822c\u7528\u4e0a\u9762\u7684 loras \u5217\u8868
    c.setdefault("lora_strength", 1.0)
    c.setdefault("sampler", None)
    c.setdefault("scheduler", None)
    c.setdefault("steps", 20)
    c.setdefault("seed", None)
    c.setdefault("megapixels", 0.4)
    c.setdefault("aspect", "4:3 (Standard)")
    c.setdefault("duration", 10)
    c.setdefault("video_edit", False)          # B \u65b9\u5f0f\uff1a\u81ea\u52a8\u7528\u4e0a\u4e00\u6b65\u751f\u6210\u7684\u89c6\u9891\u4f5c\u5019\u9009\u53c2\u8003
    c.setdefault("quick_render", False)        # \u5feb\u901f\u6e32\u67d3\uff1a\u4ec5\u5206\u8fa8\u7387\u4e0e\u6b65\u6570 \u00d70.707\uff08\u5176\u4f59\u540c\u7cbe\u6e32\uff09
    c.setdefault("fine_render", True)          # \u7ed3\u675f\u7cbe\u6e32\uff1a\u722c\u5c71\u7ed3\u675f\u540e\u7528\u5168\u5206\u8fa8\u7387/\u5168\u6b65\u6570\u518d\u6e32\u4e00\u6b21
    c.setdefault("flow", "ref2va")             # \u6d41\u7a0b\uff1aref2va\uff08\u9ed8\u8ba4\uff09| i2va\uff08\u9996\u5e27\u56fe\u751f\u89c6\u9891\uff0c\u82f1\u6587\u63d0\u793a\u8bcd\uff09
    c.setdefault("optimize_target", None)
    c.setdefault("admission_threshold", 5)
    c.setdefault("max_iterations", 12)
    c.setdefault("base_patience", 3)
    c.setdefault("threshold", None)
    c.setdefault("stop_mode", "auto")
    c.setdefault("llm_model", None)
    c.setdefault("llm_api_key", None)           # \u4e91\u7aef/API LLM \u9700\u8981\u65f6\u586b\u5199\uff1b\u672c\u5730\u53ef\u4e0d\u586b
    c.setdefault("audio_scoring", "off")           # \u9ed8\u8ba4\u5173\u95ed\uff1b\u4ec5\u5728\u914d\u6709\u97f3\u9891 LLM \u4e14\u9700\u8981\u65f6\u5f00\u542f(on)
    # \u97f3\u9891\u8bc4\u5ba1\u4e3a\u53ef\u9009\u901a\u9053\uff1a\u4ec5\u5f53\u4efb\u52a1\u6d89\u53ca\u58f0\u97f3\u4e14\u914d\u7f6e\u4e86\u97f3\u9891 LLM \u65f6\u624d\u542f\u7528\uff0c\u4e0d\u5728\u4ee3\u7801\u91cc\u5199\u6b7b\u4efb\u4f55\u670d\u52a1\u5668/\u6a21\u578b\u3002
    c.setdefault("audio_llm_base", None)
    c.setdefault("audio_llm_model", None)
    c.setdefault("audio_llm_api_key", None)
    c.setdefault("review_frames", 32)          # \u8bc4\u5ba1\u62bd\u5e27\u6570\u91cf
    c.setdefault("review_frame_width", 448)     # \u8bc4\u5ba1\u62bd\u5e27\u5bbd\u5ea6\uff08JPEG \u538b\u7f29\uff0c\u7f29\u5c0f\u56fe\u7247 token/\u52a0\u901f\u9884\u586b\u5145\uff09
    c.setdefault("review_frame_jpeg", True)
    c.setdefault("outdir", os.path.join(HERE, "outputs", "optimizer"))
    # \u4e3b LLM \u670d\u52a1\u5668\u5fc5\u987b\u663e\u5f0f\u6307\u5b9a\uff1a\u6bcf\u6b21\u4efb\u52a1\u542f\u52a8\u65f6\u586b\u5199\uff0c\u4e0d\u5199\u6b7b\uff0c\u53ef\u968f\u65f6\u5207\u6362\u4e13\u7528\u670d\u52a1\u5668\u6216\u4e91\u7aef\u6a21\u578b
    _missing = []
    if not c.get("llm_base"):
        _missing.append("llm_base\uff08\u753b\u9762+\u6587\u5b57 LLM \u670d\u52a1\u5668\u5730\u5740\uff0c\u5982 http://127.0.0.1:8080/v1\uff09")
    if not c.get("llm_model"):
        _missing.append("llm_model\uff08\u753b\u9762+\u6587\u5b57 LLM \u6a21\u578b id\uff0c\u7528\u8be5\u670d\u52a1\u5668 /v1/models \u67e5\u8be2\uff09")
    if _missing:
        raise SystemExit(
            "[config \u6821\u9a8c\u5931\u8d25] \u7f3a\u5931\u5fc5\u586b\u5b57\u6bb5\uff08\u4e3b LLM \u670d\u52a1\u5668\u6bcf\u6b21\u4efb\u52a1\u9700\u663e\u5f0f\u6307\u5b9a\uff09\uff1a\n  - "
            + "\n  - ".join(_missing)
            + "\n\u8bf7\u7528 <llm_base>/v1/models \u67e5\u8be2\u8be5\u670d\u52a1\u5668\u7684\u6a21\u578b id \u540e\u586b\u5165 llm_base / llm_model\u3002")
    ra.set_comfy_url(c["comfy_url"])
    # \u89e3\u6790\u53c2\u8003\u6587\u4ef6 \u2192 input \u76ee\u5f55\u53ef\u7528\u540d
    c["_ref_names"] = ra.sync_ref_files([r["path"] for r in c["refs"]])
    c["_aud_names"] = ra.sync_ref_files([a["path"] for a in c["audios"]]) if c["audios"] else []
    # ---- I2VA\uff1a\u5fc5\u987b\u4e14\u53ea\u53d6 1 \u5f20\u53c2\u8003\u56fe\u4f5c\u4e3a\u89c6\u9891\u9996\u5e27\uff1b\u4e0d\u5403\u53c2\u8003\u97f3\u9891\uff08\u5feb\u901f\u6e32\u67d3\u540c\u6837\u9002\u7528\uff09----
    if (c.get("flow") or "ref2va").strip().lower() == "i2va":
        if not c["refs"]:
            raise SystemExit("[config \u6821\u9a8c\u5931\u8d25] I2VA \u6d41\u7a0b\u5fc5\u987b\u63d0\u4f9b 1 \u5f20\u53c2\u8003\u56fe\u4f5c\u4e3a\u89c6\u9891\u9996\u5e27\u3002")
        c["refs"] = c["refs"][:1]
        c["_ref_names"] = c["_ref_names"][:1]
        c["audios"] = []
        c["_aud_names"] = []
        c["video_edit"] = False
    return c


def main():
    p = argparse.ArgumentParser(description="Ref2VA \u63d0\u793a\u8bcd\u4f18\u5316\u5668\uff08\u987a\u5e8f\u722c\u5c71\uff09")
    p.add_argument("--config", required=True, help="\u914d\u7f6e\u6587\u4ef6\u8def\u5f84\uff08JSON\uff09")
    p.add_argument("--dry-run", action="store_true", help="\u53ea\u52a0\u8f7d\u914d\u7f6e\u5e76\u6253\u5370\uff0c\u4e0d\u6267\u884c")
    args = p.parse_args()
    cfg = load_config(args.config)
    if args.dry_run:
        print("\u914d\u7f6e\u52a0\u8f7d\u6210\u529f\uff1a")
        print(json.dumps({k: v for k, v in cfg.items() if not k.startswith("_")},
                         ensure_ascii=False, indent=2))
        print("\u53c2\u8003\u56fe(input \u540d):", cfg["_ref_names"])
        print("\u53c2\u8003\u97f3\u9891(input \u540d):", cfg["_aud_names"])
        return
    llm = LLM(model=cfg.get("llm_model") or None,
              base=cfg.get("llm_base") or None,
              api_key=cfg.get("llm_api_key") or None)
    run_optimizer(cfg, llm)


if __name__ == "__main__":
    main()
