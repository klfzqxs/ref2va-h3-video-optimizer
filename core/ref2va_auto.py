#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ref2va \u56fe\u5f62\u6784\u5efa\u4e0e\u8bc4\u5ba1\u5de5\u5177\uff08\u4f9b optimizer.py \u8c03\u7528\uff0c\u4e5f\u53ef\u5355\u72ec\u8dd1 CLI\uff09\u3002

\u4f9d\u8d56\uff1a\u540c\u76ee\u5f55 llm.py\u3001\u4e0a\u7ea7 comfy.py\u3001\u540c\u76ee\u5f55 MiniMax_H3_ref2va_guide.md\uff0c\u4ee5\u53ca\u7cfb\u7edf ffmpeg\u3002
"""
import argparse
import json
import os
import sys
import subprocess
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # comfyui\
COMFY = os.path.join(ROOT, "comfy.py")
API_WF = os.path.join(ROOT, "workflows", "video_minimax_h3_r2v.api.json")
GUIDE = os.path.join(HERE, "MiniMax_H3_ref2va_guide.md")

sys.path.insert(0, HERE)
from llm import LLM, LLMError

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MAX_REFS = 9          # MiniMax H3 ref2va \u4e0a\u9650
MAX_AUDIOS = 3

# ============================================================ \u65f6\u957f\u4e0a\u9650\uff082.0\uff1a15 \u79d2 \u2192 60 \u79d2\uff09
# \u5b98\u65b9\u89c4\u683c\u4e0e\u8bad\u7ec3\u8303\u56f4\u662f ~5\u201315 \u79d2\uff0817k+5 \u7f51\u683c\u4e0a\u754c 362 \u5e27 = 15.08 \u79d2\uff09\uff0c\u8282\u70b9 length \u7684\u786c\u4e0a\u9650\u662f
# 3600 \u5e27\uff08150 \u79d2\uff09\uff0c\u6ca1\u6709\u4efb\u4f55\u4ee3\u7801\u94b3\u5236\u3002\u672c\u9879\u76ee 2026-09 \u5728 512\u00b2/8 \u6b65\u4e0a\u5b9e\u6d4b\uff08D:\H3-longvideo\uff09\uff1a
#   15\u201360 \u79d2\u8d28\u91cf\u7a33\u5b9a\u53ef\u7528\uff0c**60 \u79d2\u662f\u8d28\u91cf\u9ad8\u5cf0**\uff08\u5bf9\u6bd4\u5ea6 74.8\u3001\u573a\u666f\u6700\u4e30\u5bcc\uff09\uff1b
#   90 \u79d2\u660e\u663e\u964d\u8d28\uff08\u51b7\u7070\u4f4e\u9971\u548c\u3001\u5bf9\u6bd4\u5ea6\u8170\u65a9\u5230 30\u3001\u97f3\u9891\u5f31 4 dB\u3001\u5f00\u5934\u573a\u666f\u5728\u540e\u6bb5\u91cd\u73b0\uff09\u3002
# \u6545\u672c\u7248\u628a\u5355\u6b21\u751f\u6210\u4e0a\u9650\u62ac\u5230 60 \u79d2\uff0c\u5e76\u628a >15 \u79d2\u7edf\u4e00\u8d70"\u957f\u89c6\u9891"\u5206\u652f\uff08\u63d0\u793a\u8bcd\u4e0e\u68c0\u6d4b\u5404\u6362\u4e00\u5957\u89c4\u5219\uff09\u3002
TRAINED_MAX_S = 15.0      # H3 \u8bad\u7ec3\u8303\u56f4\u5185\u7684\u4e0a\u754c\uff1b> \u6b64\u503c\u5373\u957f\u89c6\u9891
MAX_DURATION_S = 60.0     # \u672c\u9879\u76ee\u5141\u8bb8\u7684\u5355\u6b21\u751f\u6210\u957f\u5ea6\u4e0a\u9650
MIN_DURATION_S = 1.0


def is_long_video(duration):
    """\u662f\u5426\u6309\u957f\u89c6\u9891\u89c4\u5219\u5904\u7406\uff08\u8d85\u8fc7 H3 \u8bad\u7ec3\u8303\u56f4\uff09\u3002"""
    try:
        return float(duration) > TRAINED_MAX_S
    except (TypeError, ValueError):
        return False


def validate_duration(duration):
    """\u6821\u9a8c\u5e76\u89c4\u6574\u65f6\u957f\u3002\u8fd4\u56de (\u79d2, \u9519\u8bef\u4fe1\u606f\u6216 None)\u3002

    \u4e0a\u9650\u662f\u786c\u68c0\u67e5\uff08\u4e0d\u505a\u9759\u9ed8\u5939\u53d6\uff09\uff1a\u8d85\u8fc7 60 \u79d2\u5fc5\u987b\u663e\u5f0f\u5931\u8d25\uff0c\u5426\u5219\u7528\u6237\u4f1a\u4ee5\u4e3a
    "\u8bbe\u4e86 120 \u79d2\u5374\u6e32\u4e86 60 \u79d2"\uff0c\u800c\u5b9e\u9645\u9000\u5316\u98ce\u9669\u8fdc\u5927\u4e8e\u6b64\u3002
    """
    try:
        d = float(duration)
    except (TypeError, ValueError):
        return None, "\u65f6\u957f\u5fc5\u987b\u662f\u6570\u5b57\uff08\u79d2\uff09\uff0c\u5f53\u524d\u503c\uff1a%r" % (duration,)
    if d < MIN_DURATION_S:
        return None, "\u65f6\u957f\u8fc7\u5c0f\uff1a%g \u79d2\uff08\u4e0b\u9650 %g \u79d2\uff09" % (d, MIN_DURATION_S)
    if d > MAX_DURATION_S:
        return None, ("\u5355\u6b21\u751f\u6210\u65f6\u957f\u4e0a\u9650 %g \u79d2\uff0c\u5f53\u524d %g \u79d2\u3002\u957f\u89c6\u9891\u5b9e\u6d4b\u8d28\u91cf\u62d0\u70b9\u5728 60\u201390 \u79d2\u4e4b\u95f4\uff0c"
                      "60 \u79d2\u662f\u672c\u9879\u76ee\u5141\u8bb8\u7684\u4e0a\u9650\uff1b\u9700\u8981\u66f4\u957f\u8bf7\u5206\u4e24\u6bb5\u751f\u6210\u518d\u7528\u5c3e\u5e27\u7eed\u63a5\u3002" % (MAX_DURATION_S, d))
    return d, None


def expected_frames(duration):
    """\u65f6\u957f \u2192 \u5b9e\u9645\u63d0\u4ea4\u5e27\u6570\uff08\u6a21\u677f\u6309 17k+5 \u7f51\u683c**\u5411\u4e0a**\u5438\u9644\uff09\u3002\u7528\u4e8e\u65e5\u5fd7\u4e0e\u6210\u672c\u63d0\u793a\u3002"""
    try:
        n = max(5, int(round(float(duration) * 24)))
    except (TypeError, ValueError):
        return None
    return n + (5 - (n % 17)) % 17


def _long_video_director_rules(d):
    """\u957f\u89c6\u9891\uff08>15 \u79d2\uff09\u4e13\u7528\u7684\u5267\u4f5c\u89c4\u5219\u3002\u89c4\u5219\u7f16\u53f7\u63a5\u5728 system_director \u7684 1)\u20136) \u4e4b\u540e\u3002

    \u6bcf\u6761\u90fd\u5bf9\u5e94\u4e00\u9879\u5b9e\u6d4b\u9000\u5316\uff0c\u4e0d\u662f\u6cdb\u6cdb\u7684"\u5199\u8be6\u7ec6\u70b9"\uff1a
      \u5c3e\u90e8\u8fd0\u52a8\u8870\u51cf / \u5185\u5bb9\u590d\u8bfb\u7ed5\u56de\u5f00\u5934 / \u540e\u534a\u6bb5\u97f3\u9891\u53d8\u5f31\u3002
    \uff08"\u5149\u7167\u8272\u5f69\u968f\u65f6\u95f4\u6f14\u53d8"**\u4e0d\u518d\u5199\u6210\u786c\u8981\u6c42**\uff1a\u6052\u5b9a\u5149\u7167\u3001\u6052\u5b9a\u8272\u8c03\u7684\u573a\u666f\uff08\u9634\u5929\u3001\u5ba4\u5185\u56fa\u5b9a\u5149\u6e90\u3001
    \u591c\u666f\u7b49\uff09\u672c\u6765\u5c31\u662f\u5408\u7406\u7684\uff0c\u8981\u4e0d\u8981\u53d8\u7531\u5267\u672c\u51b3\u5b9a\u3002\uff09
    """
    if not is_long_video(d):
        return ""
    lo = max(4, int(d // 8))
    hi = max(lo + 2, int(round(d / 5.0)))
    return (
        f"**\u957f\u89c6\u9891\u6a21\u5f0f\uff08\u76ee\u6807 {d:g} \u79d2\uff0c\u5df2\u8d85\u51fa H3 \u8bad\u7ec3\u8303\u56f4 ~5\u201315 \u79d2\uff0c\u5fc5\u987b\u6309\u4e0b\u5217\u7ea6\u675f\u5199\uff09**\uff1a\n"
        f"7) \u62cd\u6570\uff1a\u672c\u7247\u9700\u8981 **{lo}\u2013{hi} \u62cd**\uff0c\u6bcf\u62cd 4\u20138 \u79d2\u3002\u62cd\u6570\u592a\u5c11\u4f1a\u8ba9\u6a21\u578b\u5728\u540e\u6bb5\u91cd\u590d\u5f00\u5934"
        "\uff08\u5b9e\u6d4b\u957f\u7247\u6bb5\u4f1a\u5728\u672b\u5c3e\u7ed5\u56de\u8d77\u70b9\uff0c\u56e0\u4e3a\u63d0\u793a\u8bcd\u7ed9\u4e0d\u51fa\u8db3\u591f\u7684\u65b0\u5185\u5bb9\uff09\u3002\n"
        "8) \u8fd0\u52a8\u94fa\u6ee1\u5168\u7247\uff08\u672c\u6a21\u5f0f\u6700\u91cd\u8981\u7684\u4e00\u6761\uff09\uff1a**\u6bcf\u4e00\u62cd\u90fd\u5fc5\u987b\u6709\u53ef\u89c1\u7684\u6301\u7eed\u8fd0\u52a8**"
        "\uff08\u4e3b\u4f53\u4f4d\u79fb / \u955c\u5934\u8fd0\u52a8 / \u73af\u5883\u52a8\u6001\u81f3\u5c11\u5176\u4e00\uff09\uff0c\u7981\u6b62\u4efb\u4f55\u4e00\u62cd\u5199\u6210\u9759\u6001\u3001\u505c\u987f\u3001\u7b49\u5f85\u6216"
        "\"\u5b9a\u683c\u6536\u5c3e\"\u3002\u5b9e\u6d4b\uff1a\u540c\u4e00\u6a21\u578b\u540c\u4e00\u957f\u5ea6\u4e0b\uff0c\u628a\u4e8b\u4ef6\u96c6\u4e2d\u5728\u524d\u534a\u6bb5\u4f1a\u8ba9\u5c3e\u90e8\u8fd0\u52a8\u8870\u51cf\u4e00\u534a\u4ee5\u4e0a"
        "\uff08\u5c3e/\u5747 0.46 vs 0.55\u20130.94\uff09\u3002\n"
        "9) \u65b0\u5185\u5bb9\u5747\u644a\u5230\u5168\u7247\uff1a\u65b0\u573a\u666f\u3001\u65b0\u52a8\u4f5c\u8981\u5747\u5300\u5206\u5e03\u5230\u6bcf\u4e00\u62cd\uff0c\u6700\u540e\u4e00\u62cd\u4ecd\u8981\u6709\u65b0\u7684\u53ef\u89c1\u53d8\u5316\uff1b"
        "\u4e0d\u8981\u628a\u91cd\u5934\u620f\u538b\u5728\u524d 1/3\u3002\n"
        "10) \u5149\u7167\u4e0e\u8272\u5f69\u4ee5\u5267\u672c\u9700\u8981\u4e3a\u51c6\uff1a\u5267\u672c\u82e5\u672c\u5c31\u662f**\u6052\u5b9a\u5149\u7167/\u6052\u5b9a\u8272\u8c03**\u7684\u573a\u666f\uff08\u9634\u5929\u3001\u5ba4\u5185\u56fa\u5b9a\u5149\u6e90\u3001"
        "\u591c\u666f\u7b49\uff09\uff0c\u5c31\u5199\u6e05\u300c\u5168\u7a0b\u6052\u5b9a\u300d\uff1b**\u53ea\u6709\u5267\u60c5\u9700\u8981\u53d8\u5316\u65f6**\u624d\u5199\u6210\u8d2f\u7a7f\u5168\u7a0b\u7684\u8fde\u7eed\u6f14\u53d8"
        "\uff08\u5199\u660e\u5404\u9636\u6bb5\u7684\u5149\u4f4d\u3001\u8272\u6e29\u3001\u660e\u6697\uff09\u3002\u4e0d\u8981\u4e3a\u4e86\u300c\u8981\u6709\u53d8\u5316\u300d\u800c\u786c\u52a0\u5149\u53d8\u3002"
        "\u5b9e\u6d4b\u957f\u7247\u786e\u5b9e\u53ef\u80fd\u51fa\u73b0\u6a21\u578b\u81ea\u5df1\u628a\u8272\u8c03\u538b\u5e73\u3001\u5bf9\u6bd4\u5ea6\u4e0b\u6ed1\uff0890 \u79d2\u6863\u5bf9\u6bd4\u5ea6 75\u219230\uff09\uff0c"
        "\u4f46\u90a3\u8981\u6309\u5267\u60c5\u9700\u8981\u5224\u65ad\uff0c\u4e0d\u662f\u4e00\u5f8b\u8981\u6c42\u975e\u6052\u5b9a\u3002\n"
        "11) \u5355\u4e00\u8fde\u7eed\u955c\u5934\uff1a\u4fdd\u6301\u4e00\u6b21\u8fde\u7eed\u62cd\u6444\uff08\u5141\u8bb8\u955c\u5934\u8fd0\u52a8\u4e0e\u573a\u666f\u6f14\u8fdb\uff09\uff0c\u4e0d\u8981\u5199\u6210\u786c\u5207\u5206\u955c\uff1b"
        "\u82e5\u786e\u9700\u5207\u6362\uff0c\u5207\u70b9\u6240\u5728\u90a3\u4e00\u62cd\u540c\u6837\u8981\u6709\u8fd0\u52a8\uff0c\u5e76\u5199\u660e\u5207\u6362\u524d\u540e\u4fdd\u6301\u4e00\u81f4\u7684\u5143\u7d20\u3002\n"
        "12) \u58f0\u97f3\u8d2f\u7a7f\u5230\u6700\u540e\u4e00\u62cd\uff1a\u6bcf\u4e00\u62cd\u7684 audio_note \u90fd\u8981\u5199\uff0c\u4e14\u6700\u540e\u4e00\u62cd\u5fc5\u987b\u6709\u660e\u786e\u4ecd\u5728\u6301\u7eed\u7684\u58f0\u97f3\uff1b"
        "\u957f\u7247\u6bb5\u7684\u5e38\u89c1\u9000\u5316\u662f\u540e\u534a\u6bb5\u97f3\u9891\u53d8\u5f31\u751a\u81f3\u8fd1\u4e4e\u9759\u97f3\u3002\n"
    )


def _long_video_i2va_rules(d):
    """I2VA \u957f\u89c6\u9891\u8865\u5145\u89c4\u5219\uff08\u82f1\u6587\u63d0\u793a\u8bcd\uff0c\u6545\u6b64\u5904\u4e5f\u5199\u6210\u82f1\u6587\uff0c\u4fbf\u4e8e\u683c\u5f0f\u5e08\u76f4\u63a5\u5185\u5316\uff09\u3002"""
    if not is_long_video(d):
        return ""
    lo = max(4, int(d // 8))
    hi = max(lo + 2, int(round(d / 5.0)))
    return (
        f"- LONG VIDEO MODE (target {d:g} s, beyond the model's trained 5-15 s range):\n"
        f"  * Budget {lo}-{hi} beats of 4-8 seconds each; never concentrate the important "
        "action in the first third.\n"
        "  * **Keep visible motion running in EVERY beat** (subject displacement, camera "
        "movement or environmental dynamics). Never write a static, waiting or frozen beat; "
        "measured long takes lose more than half of their tail motion when events run out early.\n"
        "  * Spread NEW information (new space, new action, new light) across the whole "
        "duration so the model has no reason to loop back to the opening.\n"
        "  * Write lighting and colour as a continuous process evolving across the entire "
        "duration (position of light, colour temperature, contrast) - long takes otherwise "
        "drift to one flat, desaturated look.\n"
        "  * Describe the soundscape so that it is still present in the final beat; long "
        "generations typically fade the audio out in the second half.\n"
        "  * Prefer one continuous take with camera movement over hard cuts; if a cut is "
        "required, give the beat a clear motion across it.\n"
    )



def _strip_placeholder_refs(graph, ref_node):
    """\u5220\u9664\u6a21\u677f\u9ed8\u8ba4\u7684 LoadImage/LoadAudio \u8282\u70b9\u5e76\u6e05\u7a7a ref_node \u7684 ref_* \u94fe\u63a5\u3002
    \u6a21\u677f\u91cc\u8fd9\u4e9b\u8282\u70b9\u5f15\u7528\u7684\u662f\u5360\u4f4d\u6587\u4ef6\u540d\uff08\u5982 ref_image.png\uff0c\u5b9e\u9645\u4e0d\u5b58\u5728\uff09\uff0c
    \u7559\u7740\u4f1a\u8ba9 ComfyUI \u5728\u63d0\u4ea4\u65f6\u56e0 `Invalid image file` \u6821\u9a8c\u5931\u8d25\u3002"""
    for k in list(ref_node):
        if k.startswith(("ref_images.", "ref_videos.", "ref_audios.")):
            del ref_node[k]
    for nid in list(graph):
        if (graph[nid].get("class_type") or "") in ("LoadImage", "LoadAudio"):
            del graph[nid]


def _apply_lora(graph, cfg, unet_id="127"):
    """\u5728 UNET \u4e4b\u540e\u6309\u987a\u5e8f\u4e32\u8054\u82e5\u5e72 LoraLoaderModelOnly\uff08\u652f\u6301\u591a\u4e2a LoRA\u3001\u5404\u81ea\u5f3a\u5ea6\uff09\uff0c
    \u5e76\u628a\u539f\u76f4\u63a5\u5403\u8be5 UNET \u6a21\u578b\u7684\u4e0b\u6e38\u8282\u70b9\u6539\u63a5\u5230\u6700\u540e\u4e00\u4e2a LoRA \u8f93\u51fa\u3002
    unet_id\uff1aref2va \u5de5\u4f5c\u6d41\u4e3a "127"\uff1bI2V \u5de5\u4f5c\u6d41\u4e3a "105:6"\u3002"""
    if unet_id not in graph:
        return
    lores = [l for l in (cfg.get("loras") or []) if (l.get("name") or "").strip()]
    if not lores and cfg.get("lora"):
        lores = [{"name": cfg["lora"], "strength": cfg.get("lora_strength", 1.0)}]
    if not lores:
        return
    prev = unet_id
    lora_ids = set()
    for idx, l in enumerate(lores):
        nid = str(2100 + idx)
        lora_ids.add(nid)
        graph[nid] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": [prev, 0],
            "lora_name": l["name"].strip(),
            "strength_model": float(l.get("strength", 1.0)),
        }}
        prev = nid
    for nid, node in list(graph.items()):
        if nid in lora_ids:
            continue
        if (node.get("inputs") or {}).get("model") == [unet_id, 0]:
            node["inputs"]["model"] = [prev, 0]


def _set_unet_node(graph, nid, cfg):
    """\u628a cfg \u7684 model / weight_dtype \u5199\u8fdb\u6307\u5b9a\u7684 UNET \u52a0\u8f7d\u8282\u70b9\uff08\u4e24\u6761\u6d41\u7a0b\u5171\u7528\uff0c\u907f\u514d\u5efa\u56fe\u903b\u8f91\u518d\u6b21\u5404\u6f02\u5404\u7684\uff09\u3002

    **.gguf \u5fc5\u987b\u6574\u4f53\u6362\u6210 UnetLoaderGGUF**\uff1a\u6838\u5fc3 UNETLoader \u7ecf comfy.utils.load_torch_file
    \u53ea\u6309\u6269\u5c55\u540d\u5206\u6d41\uff0c\u975e .safetensors/.sft \u4e00\u5f8b\u4e22\u7ed9 torch.load\uff0c\u9047\u5230 .gguf \u76f4\u63a5\u629b
    UnpicklingError\uff08\u62a5\u9519\u91cc\u90a3\u53e5 PyTorch weights_only \u63d0\u793a\u662f\u8bef\u5bfc\uff0c\u6362\u5f00\u5173\u6ca1\u7528\uff09\u3002
    UnetLoaderGGUF \u7684 INPUT_TYPES \u6ca1\u6709 weight_dtype\uff0c\u6545 gguf \u5206\u652f\u6574\u4f53\u66ff\u6362 inputs\u3002
    nid\uff1aref2va \u5de5\u4f5c\u6d41\u4e3a "127"\uff1bI2V \u5de5\u4f5c\u6d41\u4e3a "105:6"\u3002
    \u672a\u7ed9 model \u65f6\u4fdd\u7559\u6a21\u677f\u9ed8\u8ba4\uff0c\u4f46\u6a21\u677f\u9ed8\u8ba4\u540d\u672c\u8eab\u5c31\u662f .gguf \u7684\u540c\u6837\u8981\u6362\u52a0\u8f7d\u5668\u3002
    """
    if nid not in graph:
        return
    node = graph[nid]
    inputs = node.setdefault("inputs", {})
    model = cfg.get("model") or inputs.get("unet_name")
    if model and str(model).lower().endswith(".gguf"):
        wd = str(cfg.get("weight_dtype") or "").strip()
        if wd and wd.lower() != "default":
            print(f"[warn] \u5df2\u5ffd\u7565 weight_dtype={wd}\uff1aGGUF \u8d70 UnetLoaderGGUF\uff0c"
                  f"\u8be5\u8282\u70b9\u6ca1\u6709\u8fd9\u4e2a\u8f93\u5165\uff08\u7cbe\u5ea6\u7531 gguf \u6587\u4ef6\u81ea\u5e26\u7684\u91cf\u5316\u7c7b\u578b\u51b3\u5b9a\uff09", file=sys.stderr)
        node["class_type"] = "UnetLoaderGGUF"
        node["inputs"] = {"unet_name": model}
        return
    # \u975e GGUF\uff1a\u6838\u5fc3 UNETLoader \u624d\u80fd\u8bfb safetensors
    node["class_type"] = "UNETLoader"
    if cfg.get("model"):
        inputs["unet_name"] = cfg["model"]
    if cfg.get("weight_dtype"):
        inputs["weight_dtype"] = cfg["weight_dtype"]


# ---- ComfyUI \u76ee\u6807\u670d\u52a1\u5668\uff08\u53ef\u9009\uff0c\u9ed8\u8ba4\u8d70 COMFYUI_URL \u73af\u5883\u53d8\u91cf / \u672c\u673a 127.0.0.1:8000\uff09----
import urllib.error
import urllib.request
_COMFY_BASE = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8000")


def set_comfy_url(url):
    """\u8bbe\u7f6e\u76ee\u6807 ComfyUI \u670d\u52a1\u5668\u5730\u5740\u3002None/\u7a7a \u5219\u56de\u9000\u73af\u5883\u53d8\u91cf\u9ed8\u8ba4\u3002"""
    global _COMFY_BASE
    _COMFY_BASE = (url or os.environ.get("COMFYUI_URL", "http://127.0.0.1:8000")).rstrip("/")


def get_comfy_url():
    return _COMFY_BASE


# ============================================================ \u63d0\u793a\u8bcd\u6a21\u677f
def _read_guide():
    with open(GUIDE, encoding="utf-8") as f:
        return f.read()


# ============================================================ \u63d0\u793a\u8bcd\u5199\u4f5c\u6280\u80fd\uff08skill\uff09
# \u4e00\u4efd skill = \u4e00\u6bb5 Markdown\uff0c\u542b\u300c\u5199\u4f5c\u89c4\u5219\u300d\u4e0e\u300c\u8bc4\u5ba1\u4fa7\u91cd\u300d\u4e24\u5757\uff0c\u7528\u6765\u66ff\u4ee3\u8fc7\u53bb\u90a3\u4e2a\u542b\u4e49\u4e0d\u6e05\u7684
# "\u4f18\u5316\u76ee\u6807"\u8f93\u5165\u6846\uff1a\u5b83\u540c\u65f6\u51b3\u5b9a**\u600e\u4e48\u5199**\u4e0e**\u91cd\u70b9\u6838\u9a8c\u4ec0\u4e48**\u3002
#   * \u9875\u9762\uff1a\u4e00\u4e2a\u53ef\u7f16\u8f91\u6587\u672c\u6846 + \u82e5\u5e72\u300c\u8f7d\u5165\u9884\u8bbe\u300d\u6309\u94ae\uff08\u9884\u8bbe\u6765\u81ea skills/*.md\uff0cGET /api/skills\uff09\uff1b
#   * CLI / \u914d\u7f6e\uff1a`skill` \u76f4\u63a5\u5199\u6b63\u6587\uff0c\u6216\u7528 `skill_path` \u6307\u4e00\u4e2a .md \u6587\u4ef6\uff1b
#   * \u7559\u7a7a = \u4e0d\u52a0\u989d\u5916\u98ce\u683c\u8981\u6c42\uff08\u53ea\u6309\u5b98\u65b9\u516d\u6bb5\u89c4\u8303\u4e0e\u7528\u6237\u6545\u4e8b\u5199\uff09\u3002
#     **\u76ee\u6807\u8fd9\u4ef6\u4e8b\u4e0d\u518d\u6709\u5355\u72ec\u5b57\u6bb5**\uff1a\u8981\u4ec0\u4e48\u6548\u679c\u5199\u5728\u6545\u4e8b\u63cf\u8ff0\u91cc\uff0c\u6216\u5199\u8fdb skill \u6b63\u6587\u3002
SKILLS_DIR = os.path.join(ROOT, "skills")
MAX_SKILL_CHARS = 20000


def list_skills():
    """\u5217\u51fa skills/*.md \u9884\u8bbe\uff1a[{name, file, text}]\uff08\u663e\u793a\u540d\u53d6\u6587\u4ef6\u9996\u884c\u7684 `# \u6807\u9898`\uff09\u3002"""
    out = []
    try:
        names = sorted(os.listdir(SKILLS_DIR))
    except OSError:
        return out
    for fn in names:
        if not fn.lower().endswith((".md", ".txt")):
            continue
        try:
            with open(os.path.join(SKILLS_DIR, fn), encoding="utf-8") as f:
                txt = f.read().strip()
        except OSError:
            continue
        name = os.path.splitext(fn)[0]
        first = (txt.splitlines() or [""])[0].strip()
        if first.startswith("#"):
            name = first.lstrip("#").strip() or name
        out.append({"name": name, "file": fn, "text": txt})
    return out


def load_skill_text(cfg):
    """\u53d6\u672c\u6b21\u8981\u7528\u7684 skill \u6b63\u6587\uff1a\u4f18\u5148 cfg['skill']\uff08\u9875\u9762\u6587\u672c\u6846\uff09\uff0c\u5176\u6b21 cfg['skill_path']\uff08\u8bfb\u6587\u4ef6\uff09\u3002"""
    txt = (cfg.get("skill") or "").strip()
    if not txt and cfg.get("skill_path"):
        path = cfg["skill_path"]
        try:
            with open(path, encoding="utf-8") as f:
                txt = f.read().strip()
        except OSError as e:
            raise RuntimeError("skill \u6587\u4ef6\u8bfb\u4e0d\u51fa\u6765\uff1a%s\uff08%s\uff09" % (path, e))
    if len(txt) > MAX_SKILL_CHARS:
        raise ValueError("skill \u592a\u957f\uff1a%d \u5b57\u7b26 > \u4e0a\u9650 %d" % (len(txt), MAX_SKILL_CHARS))
    return txt


def skill_block(cfg, title="\u5199\u4f5c\u6280\u80fd\uff08skill\uff09"):
    """\u628a skill \u6b63\u6587\u5305\u6210\u53ef\u6ce8\u5165 prompt \u7684\u6bb5\u843d\uff1b\u6ca1\u6709 skill \u65f6\u8fd4\u56de\u7a7a\u4e32\uff08\u4e0d\u5360 token\uff09\u3002"""
    txt = load_skill_text(cfg)
    if not txt:
        return ""
    return "\n# %s\n%s\n" % (title, txt)


def system_director(duration):
    """\u5267\u4f5c\u5bfc\u6f14 system prompt\uff0c\u76ee\u6807\u65f6\u957f\u7531\u8c03\u7528\u65b9\u6307\u5b9a\uff08\u79d2\uff09\u3002"""
    d = float(duration)
    return (
        f"\u4f60\u662f\u8d44\u6df1\u89c6\u9891\u5267\u4f5c\u5bfc\u6f14\uff0c\u8d1f\u8d23\u628a\u4e00\u4efd\u6545\u4e8b\u5927\u7eb2\u6269\u5199\u4e3a\u4e00\u6bb5\u7cbe\u786e\u7684 {d:g} \u79d2\u89c6\u9891\u5267\u672c\u3002\n"
        "\u4f60\u4f1a\u5f97\u5230\uff1a\u4e2d/\u82f1\u6587\u6545\u4e8b\u5927\u7eb2\u3001\u53ef\u7528\u7684\u53c2\u8003\u56fe\u6e05\u5355\u3001\u53ef\u7528\u7684\u53c2\u8003\u97f3\u9891\uff08\u542b\u5404\u81ea\u7684\u201c\u7528\u9014/\u58f0\u97f3\u7279\u5f81\u201d\u8bf4\u660e\uff09\u3002\n"
        "**\u53c2\u8003\u7f16\u53f7\u89c4\u5219\uff08\u4ece 1 \u8d77\uff09**\uff1a\u6e05\u5355\u91cc\u6bcf\u5f20\u53c2\u8003\u56fe\u5df2\u6807\u6ce8 `<Picture N>`\u3001\u6bcf\u6761\u53c2\u8003\u97f3\u9891\u5df2\u6807\u6ce8 `<Audio N>`\uff0c"
        "N \u4e00\u5f8b\u4ece **1** \u5f00\u59cb\u2014\u2014\u7b2c 1 \u5f20\u56fe\u5c31\u662f `<Picture 1>`\uff0c**\u7edd\u4e0d\u662f `<Picture 0>`**\u3002"
        "\u4f60\u5728\u5267\u672c\u91cc\u5f15\u7528\u53c2\u8003\u65f6\uff0c\u5fc5\u987b\u76f4\u63a5\u6cbf\u7528\u6e05\u5355\u7ed9\u51fa\u7684\u6807\u7b7e\uff0c\u4e0d\u8981\u4ece 0 \u91cd\u65b0\u7f16\u53f7\u3001\u4e5f\u4e0d\u8981\u6574\u4f53\u52a0\u51cf 1\u3002\n"
        "\u82e5\u63d0\u4f9b\u4e86\u53c2\u8003\u97f3\u9891\uff0c\u5fc5\u987b\u663e\u5f0f\u5f15\u7528\uff0c\u4f9b\u4e0b\u6e38\u683c\u5f0f\u5e08\u751f\u6210 `<Audio N>` \u5f15\u7528\uff1a\n"
        "  - \u5728 `closed_loop_notes` \u52a0\u4e00\u6761\uff1a`\u4f7f\u7528\u53c2\u8003\u97f3\u9891<N>\uff08\u7528\u9014\uff1axxx\uff09\u4f5c\u4e3a\u672c\u6bb5\u7684\u58f0\u97f3/\u97f3\u8272\u53c2\u8003`\uff08N \u4e3a\u8be5\u97f3\u9891\u5728\u201c\u53ef\u7528\u53c2\u8003\u97f3\u9891\u201d\u91cc\u7684\u5e8f\u53f7\uff0c\u4ece 1 \u8d77\uff09\uff1b\n"
        "  - \u5728\u7528\u5230\u8be5\u58f0\u97f3\u7684\u62cd\u7684 `audio_note` \u91cc\u5199\u660e\u201c\u6309\u53c2\u8003\u97f3\u9891<N>\u201d\u5e94\u8fbe\u6210\u7684\u5177\u4f53\u76ee\u6807\u58f0\u97f3\uff08\u97f3\u8272/\u8282\u594f/\u8bed\u6c14/\u97f3\u91cf\uff09\uff1b\n"
        "  - \u672a\u63d0\u4f9b\u53c2\u8003\u97f3\u9891\u5219\u4e0d\u5199\u8fd9\u4e9b\u3002\n"
        "\n"
        "\u8f93\u51fa\u5fc5\u987b\u662f\u7b26\u5408\u4ee5\u4e0b\u4e25\u683c\u7ed3\u6784\u7684 JSON \u5bf9\u8c61\uff08\u8fd9\u662f\u7ed9\u4e0b\u6e38\u683c\u5f0f\u5e08\u7528\u7684\u4e2d\u95f4\u4ea7\u7269\uff0c\u4e0d\u662f\u6700\u7ec8\u7ed9\u6a21\u578b\u770b\u7684\u63d0\u793a\u8bcd\uff09\uff1a\n"
        "{\n"
        '  "summary_zh": "\u672c\u6bb5\u5267\u60c5\u7684\u4e00\u53e5\u8bdd\u6897\u6982\uff08\u4e2d\u6587\uff09",\n'
        '  "shots": [\n'
        '    {"beat": "\u8fd9\u4e00\u62cd\u7684\u5267\u60c5/\u60c5\u7eea\u63a8\u8fdb", "start_s": 0.0, "duration_s": 5.0,\n'
        '     "frame_note": "\u8fd9\u4e00\u62cd\u7528\u54ea\u5f20\u53c2\u8003\u56fe\u505a\u753b\u9762\u951a\u70b9\uff08\u5199\u6e05\u5355\u91cc\u7684\u6807\u7b7e\uff1b\u4e0d\u9700\u8981\u5c31\u5199 None\uff0c\u5982 <Picture 2>\uff09",\n'
        '     "audio_note": "\u6b64\u6bb5\u5e94\u8be5\u6709\u4ec0\u4e48\u58f0\u97f3/\u8bed\u6c14\uff08\u5982 \u4eba\u58f0\u4f4e\u8bed/\u73af\u5883\u97f3/\u65e0\uff09"}\n'
        '  ],\n'
        '  "subjects": [{"who": "\u89d2\u8272/\u573a\u666f/\u7269\u54c1", "source_hint": "\u7531\u54ea\u4e2a\u53c2\u8003\u6807\u7b7e\u63d0\u4f9b\u6a21\u6837\u6216\u59ff\u6001\uff08\u5982 <Picture 1>\uff09"}],\n'
        '  "closed_loop_notes": ["\u62cd\u6444\u89c6\u89d2/\u8fd0\u955c/\u60c5\u7eea\u5173\u952e\u70b9\uff08\u6bcf\u6761\u90fd\u662f\u753b\u9762\u5e94\u4f53\u73b0\u7684\u5177\u4f53\u8981\u6c42\uff09"]\n'
        "}\n"
        f"\u8981\u6c42\uff1a\u5206\u955c\u603b\u65f6\u957f\u7cbe\u786e\u7b49\u4e8e{d:g}\u79d2\uff08\u53ef\u591a\u62cd\uff0c\u5404\u62cd duration_s \u4e4b\u548c={d:g}\uff09\uff1b\n"
        "closed_loop_notes \u6bcf\u4e00\u6761\u90fd\u662f\u201c\u753b\u9762\u91cc\u5fc5\u987b\u53ef\u89c2\u6d4b\u5230\u201d\u7684\u786c\u6027\u8981\u6c42\uff0c\u4f9b\u540e\u7eed\u8bc4\u4f30\u9010\u6761\u6838\u9a8c\u3002\n"
        "\u6240\u6709\u6587\u672c\u5b57\u6bb5\u4e00\u5f8b\u7528\u7b80\u4f53\u4e2d\u6587\u4e66\u5199\uff1asummary_zh\u3001beat\u3001frame_note\u3001audio_note\u3001"
        "who\u3001source_hint\u3001closed_loop_notes \u5747\u4e3a\u4e2d\u6587\uff1b\u4ec5 start_s/duration_s \u4fdd\u7559\u6570\u5b57\u3002\n"
        "\u5199\u4f5c\u94c1\u5f8b\uff08\u6bcf\u6761\u90fd\u8981\u4e25\u683c\u9075\u5b88\uff09\uff1a\n"
        "1) \u5177\u4f53\u53ef\u89c2\u6d4b > \u62bd\u8c61\u8bcd\uff1aframe_note/closed_loop_notes \u4e2d\u6bcf\u4e2a\u52a8\u4f5c\u4e0e\u72b6\u6001\u90fd\u8981\u5199\u6210\u753b\u9762\u53ef\u76f4\u63a5\u5224\u5b9a\u7684"
        "\u5177\u4f53\u5199\u6cd5\uff08\u660e\u786e\u4f4d\u7f6e\u3001\u8fd0\u52a8\u65b9\u5411\u3001\u5e45\u5ea6\u3001\u901f\u5ea6\u3001\u906e\u6321\u5173\u7cfb\u4e0e\u53ef\u89c1\u8303\u56f4\uff09\uff0c"
        "\u7981\u7528\u201c\u81ea\u7136/\u6d41\u7545/\u66a7\u6627/\u8212\u670d\u201d\u8fd9\u7c7b\u65e0\u6cd5\u4ece\u753b\u9762\u5224\u5b9a\u7684\u62bd\u8c61\u8bcd\u3002\n"
        "2) \u6bcf\u62cd\u5199\u6e05\u52a8\u4f5c\u94fe\uff1a\u8d77\u59cb\u59ff\u6001 \u2192 \u52a8\u4f5c\u8def\u5f84 \u2192 \u53ef\u89c1\u7ed3\u679c \u2192 \u4e0e\u4e0b\u4e00\u62cd/\u6574\u6bb5\u7684\u8fde\u7eed\u6027\u79fb\u4ea4\u72b6\u6001\u3002\n"
        "3) \u6b63\u5411\u72b6\u6001\u4f18\u5148\u4e8e\u8d1f\u9762\u7981\u4ee4\uff1a\u7ea6\u675f\u4e00\u5f8b\u5199\u6210\u53ef\u89c2\u6d4b\u7684\u6b63\u5411\u72b6\u6001\uff08\u5982\u201c\u53cc\u81c2\u5168\u7a0b\u638c\u5fc3\u8d34\u684c\u9762\u3001\u53cc\u8098\u5916\u5c55\u201d\uff0c"
        "\u800c\u975e\u201c\u4e0d\u8981\u62b1\u80f8/\u4e0d\u5f97\u62ac\u81c2/\u7981\u6b62\u5c48\u8098\u201d\uff09\uff1b\u8d1f\u9762\u7981\u4ee4\u5f0f\u5199\u6cd5\u6613\u5f15\u53d1\u80a2\u4f53\u9519\u4e71\uff0c\u907f\u514d\u4f7f\u7528\u3002\n"
        "4) \u533a\u5206\u201c\u52a0\u7ec6\u8282\u201d\u4e0e\u201c\u52a0\u4e8b\u4ef6\u201d\uff1a\u540c\u4e00\u62cd\u4e0d\u8981\u5806\u53e0\u8fc7\u591a\u540c\u65f6\u4e8b\u4ef6\uff08\u9632\u6b62\u52a8\u4f5c\u62e5\u6324\u3001\u80a2\u4f53\u4e92\u76f8\u8bef\u5360\uff09\uff1b"
        "\u6d89\u53ca\u7cbe\u7ec6\u624b\u90e8\u52a8\u4f5c\u65f6\uff0c\u660e\u786e\u6bcf\u53ea\u624b/\u6bcf\u6839\u624b\u6307\u7684\u5206\u5de5\uff08\u54ea\u53ea\u5728\u52a8\u3001\u600e\u4e48\u52a8\u3001\u5176\u4f59\u505c\u5728\u54ea\u3001\u54ea\u4e9b\u88ab\u906e\u6321\uff09\u3002\n"
        "5) audio_note \u5177\u4f53\u5316\uff1a\u7ed1\u5b9a\u5b9e\u9645\u53d1\u58f0\u8005\uff0c\u6309\u201c\u97f3\u8272\u2192\u8282\u594f/\u901f\u5ea6\u2192\u5f3a\u5f31\u2192\u547c\u5438\u201d\u5199\u6e05\u58f0\u97f3\u6f14\u53d8\u8f68\u8ff9\uff0c"
        "\u4e0d\u53ea\u7ed9\u201c\u538b\u6291/\u66a7\u6627\u201d\u8fd9\u7c7b\u60c5\u7eea\u6807\u7b7e\u3002\n"
        f"6) \u65f6\u957f\u786c\u5bf9\u9f50\uff1a\u5404\u62cd duration_s \u4e4b\u548c\u6052\u7b49\u4e8e {d:g} \u79d2\u3002\n"
        + _long_video_director_rules(d)
        + "\u53ea\u8f93\u51fa JSON\u3002"
    )

SYSTEM_FORMATTER = (
    "\u4f60\u662f MiniMax H3 ref2va \u7684\u683c\u5f0f\u5e08\u3002\u628a\u5bfc\u6f14\u7ed9\u51fa\u7684\u5267\u672c\u4e2d\u95f4\u4ea7\u7269\u6539\u5199\u4e3a\u5b98\u65b9 ref2va "
    "full-reference \u6a21\u5f0f prompt\u3002\u5fc5\u987b\u4e25\u683c\u4f9d\u636e\u4e0b\u9762\u9644\u5f55 MiniMax \u5b98\u65b9\u5199\u4f5c\u6307\u5357\u7684\u516d\u6bb5\u7ed3\u6784\u3001"
    "\u6807\u7b7e(`<Subject N>`/`<Picture N>`/`<Audio N>`)\u3001summary \u4efb\u52a1\u7c7b\u578b\u524d\u7f00\u3001"
    "retention_analysis \u6807\u8bb0\u3001detailed_description \u5206\u955c\u683c\u5f0f\u3002\n"
    "**\u53c2\u8003\u7f16\u53f7\uff08\u786c\u6027\uff09**\uff1a\u53c2\u8003\u6e05\u5355\u91cc\u6bcf\u9879\u90fd\u5df2\u6807\u597d `<Picture N>` / `<Audio N>`\uff0cN \u4ece **1** \u8d77"
    "\uff08\u7b2c 1 \u5f20\u53c2\u8003\u56fe = `<Picture 1>`\uff0c**\u4e0d\u662f `<Picture 0>`**\uff09\u3002\u63d0\u793a\u8bcd\u91cc\u5fc5\u987b\u539f\u6837\u4f7f\u7528\u6e05\u5355\u7ed9\u51fa\u7684\u8fd9\u4e9b\u6807\u7b7e\uff0c"
    "\u4e25\u7981\u5199\u6210 0 \u53f7\u3001\u4e25\u7981\u91cd\u65b0\u7f16\u53f7\u6216\u6574\u4f53\u5e73\u79fb\uff1b\u6e05\u5355\u6709\u51e0\u5f20\u5c31\u53ea\u7528\u51e0\u53f7\uff0c\u4e0d\u591a\u4e0d\u5c11\u3002\n"
    "\u76f4\u63a5\u8f93\u51fa\u7eaf\u6587\u672c\u7684\u5b8c\u6574\u516d\u6bb5\u6539\u5199\uff08\u4e0d\u8981 JSON \u5305\u88f9\u3001\u4e0d\u8981\u4ee3\u7801\u5757\u6807\u8bb0\u3001\u4e0d\u8981\u989d\u5916\u8bf4\u660e\uff09\uff0c"
    "\u5404\u6bb5\u7528\u4e2d\u6587\u5c0f\u6bb5\u6807\u9898\u5982 subject_definitions: \u8d77\u4e00\u884c\u540e\u63a5\u5185\u5bb9\u3002\n"
    "\u8be6\u7ec6\u4f53\u91cf\uff1a**\u4e0d\u8bbe\u5b57\u6570\u4e0a\u9650**\u3002\u8bf7\u4e25\u683c\u3001\u5b8c\u6574\u5730\u6309\u5bfc\u6f14\u5267\u672c\u9010\u62cd\u8f6c\u8bd1\uff1a\u628a\u6bcf\u4e00\u62cd\u7684\u6784\u56fe\u3001\u4e3b\u4f53\u4f4d\u7f6e\u4e0e\u59ff\u6001\u3001"
    "\u52a8\u4f5c\u94fe\u3001\u8fd0\u52a8\u5e45\u5ea6\u4e0e\u901f\u5ea6\u3001\u955c\u5934\u8fd0\u52a8\u3001\u5149\u5f71\u4e0e\u8272\u5f69\u3001\u73af\u5883\u7ec6\u8282\u3001\u9010\u5e27\u5bf9\u5e94\u5173\u7cfb\u3001\u58f0\u97f3/\u5bf9\u767d/\u6b4c\u8bcd\u7b49"
    "\u5168\u90e8\u53ef\u89c2\u6d4b\u4fe1\u606f\u5199\u5c3d\uff0c\u505a\u5230\u4e0e\u5267\u672c\u4e00\u4e00\u5bf9\u5e94\u3001\u951a\u5b9a\u7cbe\u786e\uff0c\u5b81\u53ef\u8be6\u7ec6\u4e5f\u4e0d\u5220\u51cf\uff1b\u6b63\u6587\u4e00\u5f8b\u82f1\u6587\uff0c"
    "\u4ec5\u5bf9\u767d/\u6b4c\u8bcd\u4fdd\u7559\u6e90\u8bed\u8a00\u3002\n"
    "**\u53c2\u8003\u97f3\u9891\u8bf4\u660e**\uff1a\u82e5\u4e0a\u65b9\u300c\u53ef\u7528\u53c2\u8003\u97f3\u9891\u300d\u63d0\u4f9b\u4e86\u97f3\u9891\uff0c\u5fc5\u987b\u5728 `subject_definitions` \u91cc\u4e3a\u6bcf\u6761\u58f0\u660e\u4e00\u4e2a "
    "`<Audio N>`\uff0c\u5199\u6e05\u5b83**\u7528\u4e8e\u53c2\u8003\u4ec0\u4e48**\uff08\u7528\u9014/\u58f0\u97f3\u7279\u5f81\uff0c\u542b\u7528\u6237\u7ed9\u51fa\u7684\u201c\u53c2\u8003\u4ec0\u4e48\u201d\u8bf4\u660e\u4e0e\u97f3\u9891\u5206\u6790\uff09\uff0c"
    "\u4f8b\u5982 `<Audio 1> is the ... reference for <Subject N>` \u6216 `<Audio 1> is the reference for ...`\uff1b"
    "\u5e76\u5728 `summary` / `retention_analysis` / `overall_soundscape` \u76f8\u5e94\u5904\u6309\u6307\u5357\u6807\u6ce8 `reference` / `fully_copy` \u5173\u7cfb\u3002"
    "\u4e0d\u8981\u628a\u53c2\u8003\u97f3\u9891\u5f53\u4f5c\u6b63\u6587\u63cf\u8ff0\u6216\u97f3\u4e50\uff0c\u53ea\u6309\u4e0a\u8ff0\u5f15\u7528\u65b9\u5f0f\u5904\u7406\u3002\n"
)


def system_i2va(duration):
    """I2VA \u63d0\u793a\u8bcd\u7f16\u5199 system prompt\uff1a\u628a\u4e2d\u6587\u5bfc\u6f14\u5267\u672c\u4e2d\u95f4\u4ea7\u7269\u5199\u6210**\u82f1\u6587**\u6700\u7ec8\u63d0\u793a\u8bcd
    \uff08MiniMax \u5b98\u65b9 VIDEO_PROMPT_WRITING_GUIDE \u7684 I2VA \u89c4\u8303\uff09\uff0c\u6210\u54c1\u76f4\u63a5\u5582\u7ed9
    MiniMaxH3ImageToVideo\u3002\u5b9e\u6d4b\u82f1\u6587\u63d0\u793a\u8bcd\u6548\u679c\u4f18\u4e8e\u4e2d\u6587\uff0c\u6545\u8f93\u51fa\u8bed\u8a00\u56fa\u5b9a\u4e3a\u82f1\u6587\uff1b
    \u5267\u672c\u672c\u8eab\u4ecd\u4fdd\u6301\u4e2d\u6587\uff0c\u4ec5\u53f0\u8bcd/\u753b\u9762\u5185\u6587\u5b57\u6309\u89c4\u8303\u9010\u5b57\u4fdd\u7559\u539f\u6587\u3002"""
    d = float(duration)
    return (
        "You write the FINAL prompt for MiniMax H3 **I2VA** (image-to-video from a "
        "first frame). The input is a director's script in Chinese (an intermediate "
        "JSON), plus one reference image and the target duration.\n"
        "\n"
        "## OUTPUT LANGUAGE\n"
        "Write the entire prompt in **English**, in natural language prose. "
        "Two exceptions, which must keep their ORIGINAL wording verbatim:\n"
        "  - spoken content inside `<d>...</d>` (with its language tag, e.g. `[Chinese]`)\n"
        "  - on-screen text (signs, banners, subtitles, neon), kept verbatim in "
        "English double quotation marks\n"
        "Do not leave any other part of the prompt in Chinese.\n"
        "\n"
        "## OUTPUT STRUCTURE (fixed order)\n"
        "1) The FIRST LINE is the I2VA first-frame alignment instruction. Emit it "
        "verbatim, character for character, without any change:\n"
        "   For the target video, at 0.00 seconds into the target video, <Picture 1> "
        "(from [Shot 1]) is fully referenced.\n"
        "2) Then one blank line, then exactly these three fields, in this order, each "
        "label in lowercase English followed by a colon:\n"
        "   integrated_multimodal_description: [Shot 1] ...\n"
        "   (blank line)\n"
        "   overall_soundscape: ...\n"
        "   (blank line)\n"
        "   non_diegetic_music: ...\n"
        "\n"
        "## integrated_multimodal_description (the main body)\n"
        "- Describe everything along the timeline: visuals, actions, camera, speech, "
        "singing and diegetic audio. Every detail must be something visible or audible.\n"
        "- Open [Shot 1] by establishing the **overall style and the initial "
        "composition**. Derive the style from <Picture 1> (e.g. Cinematic, live-action, "
        "2D-animated, 3D CG, claymation, watercolor, vintage film), then state the "
        "subject's appearance and position, the scene and key props.\n"
        "- **I2VA rule**: <Picture 1> IS the real first frame at 0.00 seconds and "
        "belongs to [Shot 1]. First anchor the style, subjects, composition and scene "
        "anchors from the image (character identity, clothing, colors, key objects and "
        "spatial relationships stay consistent throughout), then describe the action "
        "that follows. Recommended shape: **first-frame anchor -> action onset -> "
        "continuous development -> result or reaction**.\n"
        "- Shots and cuts: do NOT put a timestamp on the first shot. For later shots "
        "write e.g. `[Shot 2] At 00:03.500, the camera cuts to ...`. Cut times must lie "
        "within the video duration and increase strictly. For ordinary cuts use `the "
        "camera cuts to`, `the shot cuts to`, `the shot transitions to`, `the shot "
        "changes to` or `the shot switches to`; use cross-dissolve, fade or wipe only "
        "if explicitly requested. A cut must introduce new information (subject, space, "
        "state, viewpoint or time). If only the distance or a slight angle changes, "
        "prefer camera motion instead of a cut.\n"
        "- Camera motion must carry all three dimensions -- **motion type + amplitude + "
        "speed** -- written as a natural action inside the shot, never as labels stacked "
        "at the end of a sentence. Motion types: Zoom In / Zoom Out, Push In / Pull "
        "Out, Pan Left / Pan Right, Truck Left / Truck Right, Tilt Up / Tilt Down, "
        "Pedestal Up / Pedestal Down, Arc Shot, Tracking Shot, Static Shot, Shake "
        "Slightly / Shake Strongly, POV, Roll Clockwise / Roll Counterclockwise. "
        "Amplitude: `with small amplitude` / `with large amplitude`. Speed: `at slow "
        "speed` / `at fast speed`. Medium amplitude and normal speed are usually "
        "omitted.\n"
        "- Anyone who speaks or sings gets a stable ID: `(S1)`, `(S2)`; several "
        "numbered speakers together use a compound ID such as `(S1,S2)`. The same "
        "person keeps the same ID across shots; characters who never vocalize get no "
        "ID. On first appearance, establish their identity from the visual and audio "
        "context (character type, age, gender, whether on-screen, pitch, timbre, "
        "speaking rate, accent). Put the identifying phrase, ID, action and delivery "
        "OUTSIDE `<d>`; inside `<d>` put only the language tag and the actual spoken "
        "content. Example: `The young woman with a quiet, breathy voice (S1) says: "
        "<d>[Chinese] \u6211\u4e0b\u4e00\u7ad9\u4e0b\u8f66\u3002</d>`. "
        "**Preserve every original word and punctuation mark verbatim; never translate "
        "or rewrite the spoken line.**\n"
        "- For voiceover use exactly `says in an off-screen voiceover`, and immediately "
        "after the `<d>` block state that the corresponding on-screen character's lips "
        "remain completely closed.\n"
        "- When one line crosses a cut, use `<scenetrans>` at the connecting points in "
        "both parts and state that the audio continues across the cut (e.g. `continues "
        "seamlessly across the cut`). Use `<cutoff>` when speech is truncated by the "
        "end of the video.\n"
        "- On-screen text (banner, sign, label, subtitle, neon) goes inside English "
        "double quotation marks, verbatim, untranslated.\n"
        "\n"
        "## overall_soundscape\n"
        "- One to four English sentences in a single continuous paragraph, summarising "
        "ambient sound, physical action sounds and non-verbal human sounds across the "
        "whole video (wind, rain, traffic, footsteps, fabric movement, impacts, "
        "breathing, laughter, panting, ...).\n"
        "- Dialogue, singing and diegetic music already belong in the main description: "
        "do NOT repeat them here. Use `N/A` only when the user explicitly asks for "
        "complete silence throughout.\n"
        "\n"
        "## non_diegetic_music\n"
        "- One to three English sentences describing background music the characters "
        "cannot hear and only the audience can hear, focusing on **instrumentation, "
        "speed, rhythm and dynamic changes**.\n"
        "- Do NOT use abstract mood words and do NOT explain the score's emotional "
        "function. Singing, instruments, radio, television or phone music audible to "
        "the characters are diegetic events and belong in the main description. Use "
        "`N/A` when there is no non-diegetic music.\n"
        "\n"
        "## HARD REQUIREMENTS\n"
        f"- Total effective duration = {d:g} seconds; every timeline point must fall "
        f"within 0 - {d:.2f} seconds.\n"
        + _long_video_i2va_rules(d)
        + "- Keep character identity, clothing, colors, key objects and spatial "
        "relationships consistent with <Picture 1> throughout.\n"
        "- Prefer positive, observable descriptions over negative prohibitions (write "
        "`both forearms stay flat on the table, palms down` rather than `do not cross "
        "the arms`).\n"
        "- Output ONLY the prompt text itself: no JSON, no markdown code fences, no "
        "commentary, no preamble or suffix.\n"
    )


SYSTEM_CRITIC = (
    "\u4f60\u662f\u6781\u4e25\u683c\u7684\u89c6\u9891-\u9700\u6c42\u7b26\u5408\u5ea6\u8bc4\u5ba1\u3002\u4f9d\u636e\u3010\u6545\u4e8b\u5927\u7eb2\u3011\u3010\u5199\u4f5c\u6280\u80fd\uff08skill\uff09\u3011\u4e0e\u3010\u5baa\u6cd5\u7ea6\u675f\u3011\uff0c"
    "\u89c2\u770b\u5173\u952e\u5e27\u5e76\u628a\u3010\u97f3\u9891\u5b9e\u6d4b\u8bc1\u636e\u3011\u5f53\u4f5c\u5730\u9762\u771f\u76f8\uff0c\u9010\u6761\u6838\u9a8c\u5e76\u6253\u5206\u3002\u5b81\u53ef\u82db\u523b\uff0c\u4e0d\u53ef\u8f7b\u6613\u7ed9\u9ad8\u5206\u3002\n"
    "\n"
    "**\u4e00\u7968\u5426\u51b3\u5236\uff08constitutional gate\uff09**\uff1a\u5148\u9010\u6761\u68c0\u67e5 constitutional_constraints \u4e2d\u7684\u951a\u5b9a\u7ea6\u675f"
    "\uff08\u4f8b\u5982\u7528\u6237\u660e\u786e\u8981\u6c42\u7684\u53c2\u8003\u951a\u5b9a\u3001\u673a\u4f4d\u3001\u65f6\u95f4\u7ebf\u8282\u70b9\u7b49\uff09\u3002"
    "\u82e5\u4efb\u4f55\u4e00\u6761\u88ab\u8fdd\u80cc\uff0c\u5219 overall \u76f4\u63a5\u5224 0\uff0cverdict \u4e3a fail\uff0c"
    "\u5e76\u5728 gaps \u7b2c\u4e00\u6761\u5199\u660e\u54ea\u6761\u5baa\u6cd5\u7ea6\u675f\u88ab\u8fdd\u80cc\u53ca\u5177\u4f53\u753b\u9762\u8868\u73b0\u3002\n"
    "\u4ec5\u5f53\u6240\u6709\u5baa\u6cd5\u7ea6\u675f\u5747\u6ee1\u8db3\u65f6\uff0c\u624d\u8fdb\u5165\u5e38\u89c4\u516d\u7ef4\u5ea6\u6253\u5206\u3002\n"
    "\n"
    "**\u5206\u6863\uff08\u4e25\u683c\uff0c\u52ff\u968f\u624b\u4e22 8-9 \u5206\uff09**\uff1a\n"
    "  0    = \u5b8c\u5168\u4e0d\u7b26\u5408 / \u5baa\u6cd5\u8fdd\u80cc\uff1b\n"
    "  1-3  = \u660e\u663e\u5931\u8d25\uff1a\u52a8\u4f5c\u8dd1\u504f\u3001\u4eba\u7269/\u73af\u5883\u9519\u3001\u58f0\u97f3\u5168\u9519\u3001\u5173\u952e\u60c5\u8282\u7f3a\u5931\uff1b\n"
    "  4-5  = \u90e8\u5206\u7b26\u5408\uff1a\u4e3b\u5e72\u5728\uff0c\u4f46\u591a\u4e2a\u5173\u952e\u7ec6\u8282/\u52a8\u4f5c\u54c1\u8d28\u4e0d\u8fbe\u6807\uff1b\n"
    "  6-7  = \u57fa\u672c\u7b26\u5408\uff1a\u4e3b\u8981\u76ee\u6807\u505a\u5230\uff0c\u4f46\u4ecd\u5b58\u5728\u6e05\u6670\u53ef\u6307\u51fa\u7684**\u5b9e\u8d28\u7f3a\u53e3**\uff08\u52a8\u4f5c\u4e0d\u7cbe\u786e\u3001\u58f0\u97f3\u542b\u6742/\u58f0\u7ebf\u4e0d\u7b26\u3001\u8868\u60c5/\u53cd\u5e94\u4e0d\u5230\u4f4d\u3001\u53ea\u505a\u5230\u7b3c\u7edf\u6ca1\u505a\u5230\u7cbe\u786e\uff09\uff1b\n"
    "  8    = \u826f\u597d\uff1a\u51e0\u4e4e\u5168\u90e8\u505a\u5230\uff0c\u4ec5\u5269\u6781\u8f7b\u5fae\u7455\u75b5\uff1b\n"
    "  9    = \u4f18\u79c0\uff1a\u65e0\u5b9e\u8d28\u7455\u75b5\uff0c\u9ad8\u5ea6\u8d34\u5408\uff1b\n"
    "  10   = \u5b8c\u7f8e\uff1a\u5b8c\u5168\u8d34\u5408\u3001\u65e0\u53ef\u6311\u5254\u3002\n"
    "**\u89c4\u5219\uff1a8 \u5206\u5141\u8bb8\u6781\u8f7b\u5fae\u7455\u75b5\uff08\u826f\u597d\uff09\uff1b\u4f46\u53ea\u8981\u5b58\u5728\u4e0e\u5199\u4f5c\u6280\u80fd\u8981\u6c42\u76f4\u63a5\u76f8\u5173\u7684\u5b9e\u8d28\u7f3a\u53e3"
    "\uff08\u7cbe\u786e\u6027/\u751f\u52a8\u6027/\u58f0\u7ebf\u95ee\u9898\u3001\u52a8\u4f5c\u4e0d\u6309\u6307\u5b9a\u65b9\u5f0f\u3001\u7f3a\u5c11\u4e30\u5bcc\u7684\u5fae\u8868\u60c5\u5c0f\u52a8\u4f5c\uff09\uff0c\u5c31\u964d\u5230 \u22647\u3002\n"
    "\n"
    "**overall \u89c4\u5219\uff08\u4e0d\u662f\u7b80\u5355\u5e73\u5747\uff0c\u9700\u88ab\u6700\u5f31\u5173\u952e\u7ef4\u5ea6\u538b\u5236\uff0c\u4f46\u4e0d\u8fc7\u5ea6\u82db\u523b\uff09**\uff1a\n"
    "  \u00b7 \u4efb\u4e00\u7ef4\u5ea6 \u22643 \u2192 overall \u22645\uff1b\n"
    "  \u00b7 \u4efb\u4e00\u7ef4\u5ea6 \u22644 \u2192 overall \u22646\uff1b\n"
    "  \u00b7 \u4efb\u4e00\u7ef4\u5ea6 \u22645 \u2192 overall \u22647\uff1b\n"
    "  \u00b7 audio_affordance \u22644 \u2192 overall \u22646\uff08\u6d89\u58f0\u4efb\u52a1\u97f3\u9891\u662f\u91cd\u7ea6\u675f\u7ef4\u5ea6\uff09\uff1b\n"
    "  \u00b7 \u53d6\uff08\u516d\u7ef4\u5747\u5206 \u4e0e \u4e0a\u8ff0\u5c01\u9876\uff09\u7684\u8f83\u5c0f\u503c\uff0c\u56db\u820d\u4e94\u5165\u5230 0.5\u3002\n"
    "\u76ee\u6807\uff1a\u5408\u683c\u3001\u8d34\u5408\u7684\u4f5c\u54c1\u5e94\u80fd\u62ff\u5230 7-8 \u5206\uff1b\u6709\u660e\u663e\u7f3a\u53e3\uff08\u5c24\u5176 action_logic / audio_affordance / story_beats\uff09"
    "\u5219\u88ab\u538b\u5230 6 \u6216\u4ee5\u4e0b\uff0c\u4ece\u800c\u7ed9\u722c\u5c71\u7559\u51fa\u53ef\u7ee7\u7eed\u63d0\u5347\u7684\u7a7a\u95f4\uff0c\u800c\u4e0d\u662f\u4e00\u4e0a\u6765\u5c31\u9876\u5230 9\u3002\n"
    "\n"
    "**\u97f3\u9891/\u58f0\u7ebf\u786c\u6838\u9a8c\uff08\u6d89\u58f0\u4efb\u52a1\u5fc5\u987b\u505a\uff09**\uff1a\u82e5\u3010\u6545\u4e8b\u3011\u6216\u3010\u5199\u4f5c\u6280\u80fd\u3011\u5bf9\u58f0\u7ebf/\u58f0\u6e90\u6709\u660e\u786e\u8981\u6c42"
    "\uff08\u5982\u201c\u53ea\u6709\u7279\u5b9a\u4eba\u58f0/\u65e0BGM\u201d\uff09\uff0c\u5fc5\u987b\u636e\u3010\u97f3\u9891\u5b9e\u6d4b\u8bc1\u636e\u3011\u6838\u9a8c\uff1a\n"
    "  \u00b7 \u8981\u6c42\u201c\u65e0\u7537\u6027\u58f0\u97f3\u201d\u800c\u97f3\u8f68\u51fa\u73b0\u4efb\u4f55\u7537\u6027\u4eba\u58f0\uff08\u7537\u6027\u4eba\u58f0/\u5598\u606f/\u8bf4\u8bdd/\u5589\u97f3/\u7537\u6027\u6c14\u606f\uff09"
    "\u2192 audio_affordance \u22643\uff0c\u4e14 overall \u6309\u4e0a\u8ff0\u89c4\u5219\u5c01\u9876\uff08\u22646\uff09\uff1b\u5728 gaps \u4e2d\u5199\u660e\u51fa\u73b0\u4e86\u54ea\u79cd\u7537\u58f0\uff1b\n"
    "  \u00b7 \u8981\u6c42\u7279\u5b9a\u5973\u6027\u53d1\u58f0\uff08\u8f7b\u67d4\u4eba\u58f0/\u547c\u5438\uff09\u800c\u97f3\u8f68\u7f3a\u5c11\u5bf9\u5e94\u5973\u6027\u53d1\u58f0\u3001\u6216\u88ab\u5176\u5b83\u58f0\u6e90\u4ee3\u66ff"
    "\u2192 audio_affordance \u22644\uff0coverall \u22647\uff1b\n"
    "  \u00b7 \u97f3\u8f68\u51fa\u73b0\u6545\u4e8b\u672a\u8981\u6c42\u7684\u97f3\u4e50/\u98ce\u58f0/\u7ec7\u7269\u6469\u64e6/\u989d\u5916\u73af\u5883\u5c42 \u2192 audio_affordance \u6263\u5206\u3002\n"
    "\n"
    "**\u6280\u80fd\u8981\u6c42\u8d34\u5408\u5ea6**\uff1a\u5355\u72ec\u6838\u9a8c\u89c6\u9891\u5bf9\u3010\u5199\u4f5c\u6280\u80fd\uff08skill\uff09\u3011\u7684\u8fbe\u6210\u2014\u2014"
    "\u52a8\u4f5c\u662f\u5426\u7cbe\u786e\u7b26\u5408\u4f60\u6307\u5b9a\u7684\u65b9\u5f0f\u4e0e\u8282\u594f\u3001\u8868\u60c5/\u53cd\u5e94\u662f\u5426\u751f\u52a8\u5230\u6240\u9700\u7a0b\u5ea6\uff08\u5fcd\u7b11/\u60c5\u7eea\u5cf0\u503c/\u66a7\u6627\u4eb2\u6635\uff09\u3001"
    "\u662f\u5426\u6709\u4e30\u5bcc\u7684\u5fae\u8868\u60c5/\u5c0f\u52a8\u4f5c/\u7728\u773c\u547c\u5438\u7b49\u4eba\u7c7b\u771f\u5b9e\u8fd0\u52a8\uff1b\u6b64\u9879\u4e0d\u8db3\u76f4\u63a5\u62c9\u4f4e action_logic / story_beats \u4e0e overall\u3002\n"
    "\u8bc4\u5ba1\u65f6\u4f18\u5148\u6838\u9a8c\u5267\u672c\u8981\u6c42\u7684\u662f\u5426\u4e3a\u6b63\u5411\u53ef\u89c2\u6d4b\u72b6\u6001\uff08\u5982\u201c\u53cc\u81c2\u5168\u7a0b\u6491\u684c\u5916\u5c55\u3001\u638c\u5fc3\u8d34\u684c\u9762\u201d\uff09\uff0c"
    "\u91cd\u70b9\u68c0\u67e5\u5e76\u6263\u5206\u8fd9\u4e9b\u53cd\u590d\u51fa\u73b0\u7684\u80a2\u4f53\u5931\u8d25\u6a21\u5f0f\uff1a\u80a2\u4f53\u9519\u4e71\u3001\u624b\u81c2\u4e92\u76f8\u8bef\u5360\u3001"
    "\u201c\u53cc\u624b\u52a8\u4f5c\u88ab\u81ea\u8eab\u624b\u81c2/\u80a2\u4f53\u66ff\u4ee3\u201d\u3001\u4f38\u5165\u817f\u95f4\u7684\u624b\u88ab\u6e32\u67d3\u6210\u6a21\u7cca\u6293\u63e1\u56e2\u5757\u7b49\uff1b"
    "\u547d\u4e2d\u65f6\u5728 gaps \u5199\u660e\u662f\u54ea\u53ea\u80a2\u4f53\u5e94\u5904\u4e8e\u4ec0\u4e48\u5177\u4f53\u4f4d\u7f6e/\u52a8\u4f5c\u3002\n"
    "\n"
    "\u8f93\u51fa\u5fc5\u987b\u662f\u5408\u6cd5 JSON\uff1a\n"
    "{\n"
    '  "constitutional_check": {"violated": true, "details": "\u8bf4\u660e\u54ea\u6761\u7ea6\u675f\u88ab\u8fdd\u80cc\u3001\u753b\u9762\u5177\u4f53\u8868\u73b0"},\n'
    '  "scores": {"frame_plane": 0, "action_logic": 0, "character_identity": 0,\n'
    '             "environment": 0, "audio_affordance": 0, "story_beats": 0},\n'
    '  "overall": 0,\n'
    '  "verdict": "pass" | "fail",\n'
    '  "gaps": ["\u5dee\u8ddd1\uff0c\u5177\u4f53\u5230\u67d0\u5e27/\u67d0\u5904\u5e94\u6709\u7684\u8c03\u6574\uff08\u636e\u6b64\u505a\u4e0b\u4e00\u8f6e\u4fee\u6539\uff09"],\n'
    '  "strengths": ["\u505a\u5bf9\u4e86\u76841-2\u6761"]\n'
    "}\n"
    "gaps \u5fc5\u987b\u5177\u4f53\u5230\u67d0\u5e27/\u67d0\u5904\u5982\u4f55\u6539\uff1b\u82e5\u67d0\u7ef4\u5ea6\u65e0\u5927\u95ee\u9898\u53ef\u5199\u8be5\u7ef4\u5ea6\u8f83\u5c0f\u7f3a\u53e3\u6216\u7701\u7565\u3002\u603b\u4f53\u8981\u514b\u5236\u3001\u4e25\u82db\uff0c"
    "\u907f\u514d\u201c\u5927\u4f53\u7b26\u5408\u5c31 8-9\u201d\u3002\u53ea\u8f93\u51fa JSON\u3002"
)


# ============================================================ ComfyUI \u4ea4\u4e92
MODEL_DIR = os.environ.get(
    "MODEL_DIR",
    os.path.join(os.getcwd(), "models", "diffusion_models"))


_LAST_RUN_PROMPT_IDS = []   # \u6700\u8fd1\u4e00\u6b21 run_comfy \u63d0\u4ea4\u5230 ComfyUI \u7684 prompt_id \u5217\u8868


def run_comfy(command):
    import json as _json
    env = dict(os.environ)
    env["COMFYUI_URL"] = _COMFY_BASE
    proc = subprocess.run([sys.executable, COMFY] + command,
                          capture_output=True, text=True, encoding="utf-8", env=env)
    out = None
    stdout = proc.stdout or ""
    # comfy.py \u4f1a\u8fde\u7eed\u8f93\u51fa\u591a\u4e2a JSON\uff08\u5982 run: \u5148 queued\u3001\u518d done \u591a\u884c\uff09\u3002
    # \u7528 raw_decode \u6d41\u5f0f\u89e3\u6790\u6574\u4e2a stdout\uff0c\u53d6\u6700\u540e\u4e00\u4e2a\u542b "ok" \u7684\u5bf9\u8c61\u4f5c\u4e3a\u6700\u7ec8\u7ed3\u679c\u3002
    decoder = _json.JSONDecoder()
    idx = 0
    parsed_all = []
    try:
        while idx < len(stdout):
            while idx < len(stdout) and stdout[idx] in " \t\r\n":
                idx += 1
            if idx >= len(stdout):
                break
            obj, idx = decoder.raw_decode(stdout, idx)
            parsed_all.append(obj)
    except Exception:
        pass
    for obj in reversed(parsed_all):
        if isinstance(obj, dict) and "ok" in obj:
            out = obj
            break
    if out is None and parsed_all:
        out = parsed_all[-1]
    if out is None:
        out = {"raw_stdout": stdout[-2000:], "raw_stderr": (proc.stderr or "")[-1000:]}
    # \u8bb0\u5f55\u672c\u6b21\u63d0\u4ea4\u5230 ComfyUI \u7684 prompt_id\uff0c\u4f9b\u201c\u7ec8\u6b62\u4efb\u52a1\u201d\u65f6\u5b9a\u5411\u53d6\u6d88
    _LAST_RUN_PROMPT_IDS[:] = [o.get("prompt_id") for o in parsed_all
                               if isinstance(o, dict) and o.get("prompt_id")]
    if proc.returncode != 0:
        raise RuntimeError(f"comfy.py {command} \u5931\u8d25 rc={proc.returncode}: {out}")
    return out


def comfy_cancel_prompts(pid_list):
    """\u5b9a\u5411\u53d6\u6d88\u5c5e\u4e8e\u67d0\u4efb\u52a1\u7684 ComfyUI \u4f5c\u4e1a\uff1a\u5220\u9664\u4ecd\u5728\u6392\u961f\u7684 prompt_id\uff0c\u5e76\u4e2d\u65ad\u4ecd\u5728\u8fd0\u884c\u7684\u8be5\u4efb\u52a1 prompt\u3002
    \u4e0d\u5f71\u54cd ComfyUI \u4e2d\u5176\u5b83\u6392\u961f\u4efb\u52a1\u3002"""
    pid_set = set(p for p in (pid_list or []) if p)
    if not pid_set:
        return
    try:
        req = urllib.request.Request(f"{_COMFY_BASE}/queue", headers={"User-Agent": "dsh-ref2va"})
        with urllib.request.urlopen(req, timeout=20) as r:
            q = json.loads(r.read().decode("utf-8"))
    except Exception:
        return

    def _ids(items):
        ids = []
        for it in items or []:
            if isinstance(it, dict):
                ids.append(it.get("prompt_id"))
            elif isinstance(it, (list, tuple)) and len(it) > 1 and isinstance(it[1], dict):
                ids.append(it[1].get("prompt_id"))
            elif isinstance(it, (list, tuple)) and it:
                ids.append(str(it[0]))
        return [i for i in ids if i]

    running = _ids(q.get("queue_running", []))
    pending = _ids(q.get("queue_pending", []))
    del_ids = [i for i in pending if i in pid_set]
    if del_ids:
        try:
            req = urllib.request.Request(f"{_COMFY_BASE}/queue", data=json.dumps({"delete": del_ids}).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "User-Agent": "dsh-ref2va"},
                                         method="DELETE")
            urllib.request.urlopen(req, timeout=20)
        except Exception:
            pass
    if any(i in pid_set for i in running):
        try:
            req = urllib.request.Request(f"{_COMFY_BASE}/interrupt", data=b"{}",
                                         headers={"Content-Type": "application/json", "User-Agent": "dsh-ref2va"},
                                         method="POST")
            urllib.request.urlopen(req, timeout=20)
        except Exception:
            pass


def comfy_upload(filepath):
    """\u628a\u6587\u4ef6\uff08\u56fe/\u89c6\u9891/\u97f3\u9891\uff09\u4e0a\u4f20\u5230\u76ee\u6807 ComfyUI \u7684 input \u76ee\u5f55\uff0c\u8fd4\u56de\u53ef\u5f15\u7528\u6587\u4ef6\u540d\u3002
    \u7528\u5b83\u66ff\u4ee3\u672c\u5730\u62f7\u8d1d\uff0c\u80fd\u4fdd\u8bc1\u6587\u4ef6\u843d\u5728 ComfyUI \u771f\u6b63\u8bfb\u53d6\u7684 input \u76ee\u5f55\u3002"""
    import mimetypes
    with open(filepath, "rb") as f:
        data = f.read()
    name = os.path.basename(filepath)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    boundary = uuid.uuid4().hex
    head = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n").encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(f"{_COMFY_BASE}/upload/image", data=head + data + tail, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode("utf-8"))
    name = d.get("name", name)
    sub = d.get("subfolder") or ""
    return name if not sub else f"{sub}/{name}"


def _remote_object_list(node_class, base=None):
    """\u4ece\u76ee\u6807\u670d\u52a1\u5668\u62c9\u53d6\u67d0 loader \u8282\u70b9\u7684\u6a21\u578b COMBO \u5217\u8868\uff08\u7528\u4e8e\u8fdc\u7a0b\u6a21\u578b\u53d1\u73b0\uff09\u3002
    \u53ef\u4f20 base \u6307\u5b9a ComfyUI \u5730\u5740\uff08\u9ed8\u8ba4\u7528\u5168\u5c40 _COMFY_BASE\uff09\u3002
    <\u8282\u70b9>\u7aef\u70b9\u4e0d\u652f\u6301\u7684 ComfyUI \u7248\u672c\u4f1a\u56de\u9000\u5230\u5168\u91cf /object_info\u3002"""
    base = (base or _COMFY_BASE).rstrip("/")

    def _find(data):
        spec = data.get(node_class)
        if not spec:
            return None
        for part in ("required", "optional"):
            for k, v in (spec.get("input", {}).get(part, {})).items():
                if isinstance(v, list):
                    if isinstance(v[0], list):
                        return v[0]
                    if len(v) >= 2 and v[0] == "COMBO" and isinstance(v[1], dict):
                        return v[1].get("options") or []
        return None

    for url in (f"{base}/object_info/{node_class}", f"{base}/object_info"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dsh-ref2va"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            res = _find(data)
            if res is not None:
                return res
            # \u5168\u91cf\u7aef\u70b9\u5df2\u901a\u4f46\u6ca1\u8fd9\u4e2a\u7c7b \u2192 \u7ee7\u7eed/\u7ed3\u675f
        except Exception as e:
            if url.endswith(node_class):
                # \u5355\u8282\u70b9\u7aef\u70b9\u4e0d\u652f\u6301\uff08404/\u5f02\u5e38\uff09\u2192 \u6362\u5168\u91cf
                continue
            print(f"[warn] \u65e0\u6cd5\u4ece {base} \u62c9\u53d6 {node_class} \u6a21\u578b\u5217\u8868: {e}", file=sys.stderr)
    return []


def discover_models(subfolder=None, pattern="ref2va", prefer_remote=True):
    """\u5217\u51fa\u53ef\u7528\u7684\u542b pattern \u6a21\u578b\uff08UNETLoader \u5f15\u7528\u540d\uff09\u3002

    prefer_remote=True\uff08\u9ed8\u8ba4\uff09\uff1a\u4f18\u5148\u4ece\u76ee\u6807 ComfyUI \u670d\u52a1\u5668\u62c9\u53d6 UNETLoader + UnetLoaderGGUF
    \u7684 COMBO \u5217\u8868\uff0c\u5408\u5e76\u53bb\u91cd\u2014\u2014\u8fd9\u6837\u4e0d\u540c\u670d\u52a1\u5668\u5404\u81ea\u7684\u6a21\u578b\u6e05\u5355\u90fd\u80fd\u6b63\u786e\u53d1\u73b0\uff0c
    \u65b0\u4e0b\u8f7d\u7684\u6a21\u578b\u4e5f\u4f1a\u81ea\u52a8\u51fa\u73b0\uff08comfyui \u91cd\u542f\u540e /models \u5373\u65b0\uff09\u3002
    \u8fdc\u7a0b\u4e0d\u53ef\u8fbe\u65f6\u56de\u9000\u5230\u672c\u5730 MODEL_DIR \u626b\u63cf\u3002
    """
    # --- \u8fdc\u7a0b\u4f18\u5148 ---
    if prefer_remote:
        remote = _remote_object_list("UNETLoader") + _remote_object_list("UnetLoaderGGUF")
        if remote:
            seen, out = set(), []
            for m in sorted(set(remote)):
                fn = m.split("\\")[-1].split("/")[-1]
                if pattern and pattern not in fn:
                    continue
                out.append(m)
            return out
        # \u8fdc\u7a0b\u5931\u8d25/\u65e0\u5217\u8868 \u2192 \u843d\u5230\u672c\u5730
    return _discover_local(subfolder, pattern)


def _discover_local(subfolder=None, pattern="ref2va"):
    """\u672c\u5730\u626b\u63cf MODEL_DIR \u515c\u5e95\u3002"""
    found = []
    if subfolder:
        base = os.path.join(os.path.dirname(MODEL_DIR), subfolder)
        prefix = subfolder.replace("/", "\\") + "\\"
        if not os.path.isdir(base):
            print(f"[warn] \u5b50\u76ee\u5f55\u4e0d\u5b58\u5728: {base}", file=sys.stderr)
            return found
        cand = [(fn, prefix + fn) for fn in sorted(os.listdir(base))
                if fn.lower().endswith((".safetensors", ".gguf"))]
    else:
        base = MODEL_DIR
        cand = [(fn, os.path.basename(MODEL_DIR) + "\\" + fn) for fn in sorted(os.listdir(MODEL_DIR))
                if fn.lower().endswith((".safetensors", ".gguf"))]
        root_dir = os.path.dirname(MODEL_DIR)
        cand += [(fn, fn) for fn in sorted(os.listdir(root_dir))
                 if fn.lower().endswith((".safetensors", ".gguf"))]
    for fn, ref in cand:
        if pattern and pattern not in fn:
            continue
        found.append(ref)
    return found


def sync_ref_files(paths, input_dir=None):
    """\u786e\u4fdd\u53c2\u8003\u6587\u4ef6\uff08\u56fe/\u97f3\u9891\uff09\u5728\u76ee\u6807 ComfyUI \u7684 input \u76ee\u5f55\u53ef\u76f4\u63a5\u88ab LoadImage/LoadAudio \u5f15\u7528\u3002
    \u8fd4\u56de\u5404\u81ea basename\u3002\u672c\u5730\u670d\u52a1\u5668\u53ef\u7528\u78c1\u76d8\u68c0\u67e5\u8df3\u8fc7\uff1b\u8fdc\u7a0b\u670d\u52a1\u5668\u4e00\u5f8b\u4e0a\u4f20\u3002"""
    is_local = "127.0.0.1" in _COMFY_BASE or "localhost" in _COMFY_BASE
    input_dir = input_dir or os.environ.get(
        "COMFYUI_INPUT_DIR", os.path.join(os.getcwd(), "input"))
    names = []
    for p in paths:
        if not os.path.isfile(p):
            raise RuntimeError(f"\u53c2\u8003\u6587\u4ef6\u4e0d\u5b58\u5728: {p}")
        bn = os.path.basename(p)
        if is_local and os.path.normpath(os.path.abspath(p)) == os.path.normpath(
                os.path.join(input_dir, bn)):
            names.append(bn)
            continue
        up = run_comfy(["upload", p])
        names.append(up.get("usable_as") or up.get("name") or bn)
    return names


# ============================================================ \u4f4e\u663e\u5b58\u5206\u5757\uff08\u53ef\u9009\uff0c\u9ed8\u8ba4\u5173\u95ed\uff09
# \u4f9d\u636e\uff08\u672c\u673a A/B \u5b9e\u6d4b\uff0c\u89c1 VERIFICATION.md\u300c\u4f4e\u663e\u5b58\u5206\u5757\u300d\uff09\uff1a
#   * \u4e24\u4e2a\u8282\u70b9\u90fd\u6765\u81ea **ComfyUI-KJNodes**\uff08\u672c\u9879\u76ee\u672c\u6765\u5c31\u4f9d\u8d56\u5b83\uff09\uff0c\u96f6\u989d\u5916\u5b89\u88c5\uff1a
#       MiniMaxChunkFeedForward \uff1aMLP(SwiGLU) \u6cbf packed token \u7ef4\u5206\u5757\uff08int8 \u6309 token \u91cf\u5316 \u2192 \u6570\u503c\u7cbe\u786e\uff09
#       MiniMaxLowVRAMAttention \uff1a\u6ce8\u610f\u529b\u6309\u5934\u5206\u7ec4 + \u63d0\u524d\u91ca\u653e\u4e2d\u95f4\u91cf\uff1b**\u4f1a\u4e0e Sage \u8865\u4e01\u7ec4\u5408**\uff0c
#                                 \u4fdd\u7559 Sage \u7684 forward\uff0c\u53ea\u52a0\u5757\u7ea7\u91ca\u653e\u5e76\u628a head_chunks \u900f\u4f20\u4e0b\u53bb
#   * \u6551\u5f97\u56de"\u521a\u597d\u7206\u663e\u5b58"\u7684\u6863\uff1a30s@0.8MP + 19.5GB INT8 \u6a21\u578b\uff0c\u57fa\u7ebf\u4e0d\u53ef\u7528 \u2192 \u5206\u5757 301 \u79d2\u5b8c\u6574\u51fa\u7247\uff1b
#   * \u6551\u4e0d\u56de"\u8d85\u5f97\u592a\u591a"\u7684\u6863\uff1a60s@0.6MP \u5373\u4f7f 8+8 \u4e5f\u4f1a\u843d\u5230\u5171\u4eab\u5185\u5b58\u91cc 0% \u5361\u6b7b\uff08\u6bd4\u786c OOM \u66f4\u96be\u6536\u62fe\uff09\uff1b
#   * **\u5206\u91cf\u4f1a\u6539\u53d8\u8f93\u51fa\u4f4d**\uff1a\u540c seed \u4e0b \u5173/\u53ea MLP/MLP+\u6ce8\u610f\u529b \u4e09\u7ec4\u54c8\u5e0c\u4e24\u4e24\u4e0d\u540c\uff0c\u4e14\u5404\u81ea\u53ef\u590d\u73b0
#     \uff08\u57fa\u7ebf 3/3 \u4e00\u81f4\u3001\u5206\u5757 2/2 \u4e00\u81f4\uff09\u2014\u2014\u6240\u4ee5**\u6574\u8f6e\u4f18\u5316\u671f\u95f4\u5fc5\u987b\u56fa\u5b9a\u8fd9\u4e2a\u5f00\u5173**\u3002
LOW_VRAM_MODES = ("off", "mlp", "mlp_attn")
LOW_VRAM_DEFAULT_CHUNKS = 8
LOW_VRAM_DEFAULT_HEAD_CHUNKS = 8
LOW_VRAM_SEQ_THRESHOLD = 4096            # \u4f4e\u4e8e\u8fd9\u4e2a token \u6570\u4e0d\u5207\u5757\uff08\u5c0f\u5e8f\u5217\u5207\u4e86\u53ea\u6709\u5f00\u9500\uff09
_SAGE_TAIL = "MiniMaxH3MemoryEfficientSageAttentionPatch"


def low_vram_settings(cfg):
    """\u8fd4\u56de (mode, chunks, head_chunks) \u5e76\u505a\u8303\u56f4\u6821\u9a8c\uff1boff \u65f6 chunks \u4e3a None\u3002"""
    raw = (cfg.get("low_vram") or "off")
    mode = str(raw).strip().lower()
    if mode in ("", "none", "false", "0", "\u5173\u95ed", "\u5173"):
        mode = "off"
    if mode not in LOW_VRAM_MODES:
        raise ValueError("low_vram \u53ea\u80fd\u662f off / mlp / mlp_attn\uff0c\u5f53\u524d\uff1a%r" % (raw,))
    if mode == "off":
        return "off", None, None
    def _n(key, default, lo, hi, label):
        v = cfg.get(key)
        try:
            v = int(default if v in (None, "") else v)
        except (TypeError, ValueError):
            raise ValueError("%s \u5fc5\u987b\u662f\u6574\u6570\uff0c\u5f53\u524d\uff1a%r" % (label, cfg.get(key)))
        if not (lo <= v <= hi):
            raise ValueError("%s \u5fc5\u987b\u5728 %d\u2013%d \u4e4b\u95f4\uff0c\u5f53\u524d\uff1a%d" % (label, lo, hi, v))
        return v
    chunks = _n("chunk_chunks", LOW_VRAM_DEFAULT_CHUNKS, 1, 64, "chunk_chunks")
    heads = _n("chunk_head_chunks", LOW_VRAM_DEFAULT_HEAD_CHUNKS, 1, 56, "chunk_head_chunks")
    return mode, chunks, heads


def apply_low_vram_chunk(graph, cfg):
    """\u6309 cfg['low_vram'] \u5728 Sage \u8865\u4e01\u4e4b\u540e\u63d2\u5165 KJNodes \u7684\u5206\u5757\u8282\u70b9\u3002

    \u9ed8\u8ba4 off \u2192 **\u56fe\u5b8c\u5168\u4e0d\u53d8**\uff08\u8fd9\u662f"\u5173\u6389\u5c31\u56de\u5230\u539f\u884c\u4e3a"\u7684\u4fdd\u8bc1\uff0c\u4e5f\u662f\u6d4b\u8bd5\u65ad\u8a00\u7684\u5bf9\u8c61\uff09\u3002
    \u8fd4\u56de\u63d2\u5165\u8bf4\u660e\u5217\u8868\uff08\u4f9b\u65e5\u5fd7\uff09\uff1b\u672a\u542f\u7528\u65f6\u8fd4\u56de []\u3002
    """
    mode, chunks, heads = low_vram_settings(cfg)
    if mode == "off":
        return []
    tail = None
    for nid, node in graph.items():
        if (node.get("class_type") or "") == _SAGE_TAIL:
            tail = nid
            break
    if tail is None:
        raise RuntimeError("\u627e\u4e0d\u5230 %s \u8282\u70b9\uff0c\u65e0\u6cd5\u5728\u5176\u540e\u63d2\u5165\u4f4e\u663e\u5b58\u5206\u5757\u3002" % _SAGE_TAIL)
    # \u5148\u8bb0\u4e0b"\u8c01\u5728\u6d88\u8d39 Sage \u7684\u8f93\u51fa"\uff0c\u63d2\u5b8c\u518d\u628a\u5b83\u4eec\u6539\u6307\u5230\u65b0\u94fe\u5c3e\uff08\u907f\u514d\u628a\u65b0\u8282\u70b9\u81ea\u5df1\u7684\u8f93\u5165\u4e5f\u6539\u6389\uff09
    consumers = [(n, k) for n, node in graph.items()
                 for k, v in (node.get("inputs") or {}).items()
                 if isinstance(v, list) and len(v) == 2 and v[0] == tail and k == "model"]
    if not consumers:
        raise RuntimeError("\u6ca1\u6709\u8282\u70b9\u6d88\u8d39 Sage \u7684 MODEL \u8f93\u51fa\uff0c\u4f4e\u663e\u5b58\u5206\u5757\u65e0\u5904\u53ef\u63d2\u3002")
    added = []
    # \u8282\u70b9 id \u7528\u9ad8\u4f4d\u6570\u5b57\uff0c\u907f\u5f00\u6a21\u677f\u91cc\u7684\u7f16\u53f7\u4e0e "105:xx" \u5f62\u5f0f
    nid = "9001"
    graph[nid] = {"class_type": "MiniMaxChunkFeedForward",
                  "inputs": {"model": [tail, 0], "chunks": chunks,
                             "seq_threshold": LOW_VRAM_SEQ_THRESHOLD}}
    added.append("MiniMaxChunkFeedForward(chunks=%d, seq_threshold=%d)" % (chunks, LOW_VRAM_SEQ_THRESHOLD))
    tail = nid
    if mode == "mlp_attn":
        nid = "9002"
        graph[nid] = {"class_type": "MiniMaxLowVRAMAttention",
                      "inputs": {"model": [tail, 0], "head_chunks": heads}}
        added.append("MiniMaxLowVRAMAttention(head_chunks=%d)" % heads)
        tail = nid
    for n, k in consumers:
        graph[n]["inputs"][k] = [tail, 0]
    return added


def make_graph(cfg):
    """\u751f\u6210 API \u56fe dict\u3002cfg \u76f8\u5173\u952e\uff1a
      prompt        : str  ref2va \u516d\u6bb5\u6587\u672c
      ref_images    : [str] \u5728 input \u76ee\u5f55\u5185\u7684\u56fe\u7247\u6587\u4ef6\u540d\uff08\u22649\uff09
      ref_audios    : [str] \u5728 input \u76ee\u5f55\u5185\u7684\u97f3\u9891\u6587\u4ef6\u540d\uff08\u22643\uff09
      model         : str  UNET \u6a21\u578b\u540d\uff08diffusion_models\uff09
      weight_dtype  : str  \u9ed8\u8ba4 default
      sampler       : str  KSamplerSelect \u540d
      scheduler     : str  BasicScheduler \u540d
      steps         : int
      denoise       : float
      seed          : int
      duration_s    : float
    """
    with open(API_WF, encoding="utf-8") as f:
        graph = json.load(f)

    n = graph["136"]["inputs"]                      # MiniMaxH3ReferenceToVideo
    n["prompt"] = cfg["prompt"]
    _strip_placeholder_refs(graph, n)

    # --- \u53c2\u8003\u56fe\u69fd\u4f4d\uff08\u22649\uff09 ---
    for i, name in enumerate(cfg.get("ref_images") or []):
        if not name or i >= MAX_REFS:
            continue
        lid = str(1000 + i)
        graph[lid] = {"class_type": "LoadImage", "inputs": {"image": name}}
        n[f"ref_images.ref_image_{i}"] = [lid, 0]

    # --- \u53c2\u8003\u89c6\u9891\u69fd\u4f4d\uff08\u89c6\u9891\u7f16\u8f91\u5f0f\u6f14\u5316\uff1b\u53ef\u9009\uff09 ---
    # MiniMaxH3ReferenceToVideo.ref_videos \u671f\u671b IMAGE \u5e27(24fps)\uff0c\u7528 VHS_LoadVideo \u8f93\u51fa0(IMAGE)
    if cfg.get("video_ref"):
        graph["1300"] = {"class_type": "VHS_LoadVideo",
                         "inputs": {"video": cfg["video_ref"], "force_rate": 24, "frame_load_cap": 0,
                                    "select_every_nth": 1, "skip_first_frames": 0,
                                    "custom_width": 0, "custom_height": 0}}
        n["ref_videos.ref_video_0"] = ["1300", 0]

    # --- \u53c2\u8003\u97f3\u9891\u69fd\u4f4d\uff08\u22643\uff09 ---
    for i, name in enumerate(cfg.get("ref_audios") or []):
        if not name or i >= MAX_AUDIOS:
            continue
        lid = str(2000 + i)
        graph[lid] = {"class_type": "LoadAudio", "inputs": {"audio": name}}
        n[f"ref_audios.ref_audio_{i}"] = [lid, 0]

    # --- \u53c2\u8003\u56fe\u5c3a\u5bf8\u7b56\u7565\uff1amatch=\u6309\u751f\u6210\u753b\u5e45\u7f29\u653e\uff08\u7701 token\uff09\uff1bmax=\u53c2\u8003\u7ba1\u7ebf 2048 \u77ed\u8fb9\uff08\u8eab\u4efd\u6700\u51c6\u4f46\u6162\u51e0\u500d\uff09---
    if cfg.get("ref_image_size") in ("match", "max"):
        n["ref_image_size"] = cfg["ref_image_size"]

    # --- \u6a21\u578b\u53d8\u4f53\uff08\u7f3a\u7701\u4fdd\u7559\u6a21\u677f\u9ed8\u8ba4\uff1b.gguf \u81ea\u52a8\u5207\u52a0\u8f7d\u5668\uff0c\u89c1 _set_unet_node\uff09 ---
    _set_unet_node(graph, "127", cfg)
    if cfg.get("clip") and "128" in graph:
        graph["128"]["inputs"]["clip_name"] = cfg["clip"]
    _apply_lora(graph, cfg)
    # --- \u91c7\u6837/\u964d\u566a\uff08\u7f3a\u7701\u4fdd\u7559\u6a21\u677f\u9ed8\u8ba4\uff09 ---
    if cfg.get("sampler"):
        graph["123"]["inputs"]["sampler_name"] = cfg["sampler"]
    if cfg.get("scheduler"):
        graph["124"]["inputs"]["scheduler"] = cfg["scheduler"]
    graph["124"]["inputs"]["steps"] = int(cfg.get("steps", 20))
    graph["124"]["inputs"]["denoise"] = float(cfg.get("denoise", 1.0))
    # --- \u65f6\u957f / \u79cd\u5b50 ---
    graph["132"]["inputs"]["value"] = float(cfg.get("duration_s", 15.0))
    graph["129"]["inputs"]["noise_seed"] = int(cfg.get("seed", 0))
    # --- \u5206\u8fa8\u7387\uff08\u53ef\u9009\u8986\u76d6 ResolutionSelector \u7684 megapixels\uff1b0.3\u2248736x416, 0.4\u2248864x480\uff09 ---
    if cfg.get("megapixels") is not None and "115" in graph:
        graph["115"]["inputs"]["megapixels"] = float(cfg["megapixels"])
    # --- \u6bd4\u4f8b\uff08\u53ef\u9009\u8986\u76d6 ResolutionSelector \u7684 aspect_ratio\uff09 ---
    if cfg.get("aspect_ratio") and "115" in graph:
        graph["115"]["inputs"]["aspect_ratio"] = cfg["aspect_ratio"]
    # --- \u4f4e\u663e\u5b58\u5206\u5757\uff08\u53ef\u9009\uff0c\u9ed8\u8ba4\u5173\u95ed\uff1b\u63d2\u5728 Sage \u8865\u4e01\u4e4b\u540e\uff09---
    apply_low_vram_chunk(graph, cfg)
    return graph


# ============================================================ I2VA \u5de5\u4f5c\u6d41\uff08\u9996\u5e27\u56fe\u751f\u89c6\u9891\uff09
I2V_WF = os.path.join(ROOT, "workflows", "video_minimax_h3_i2v.api.json")
I2V_UNET = "105:6"          # UNETLoader\uff08.gguf \u65f6\u7531 _set_unet_node \u6362\u6210 UnetLoaderGGUF\uff09
I2V_LATENT = "105:104"      # MiniMaxH3ImageToVideo\uff08prompt / first_frame \u5728\u8fd9\u91cc\uff09
I2V_IMAGE = "114"           # LoadImage\uff08\u9996\u5e27\u53c2\u8003\u56fe\uff09
I2V_DURATION = "105:111"    # PrimitiveFloat\uff08\u65f6\u957f\u79d2\uff09
I2V_SEED = "105:15"         # RandomNoise
I2V_RES = "115"             # ResolutionSelector
I2V_SAMPLER = "105:17"      # KSamplerSelect
I2V_SCHED = "105:9"         # BasicScheduler\uff08scheduler / steps / denoise\uff09


def make_graph_i2v(cfg):
    """\u7528 I2VA\uff08\u9996\u5e27\u56fe\u751f\u89c6\u9891\uff09\u5de5\u4f5c\u6d41\u6784\u5efa API \u56fe\u3002
    cfg \u76f8\u5173\u952e\uff1a
      prompt      : str   I2VA \u82f1\u6587\u63d0\u793a\u8bcd\uff08\u9996\u5e27\u58f0\u660e + \u4e09\u4e2a\u6838\u5fc3\u5b57\u6bb5\uff09
      ref_images  : [str] \u53ea\u53d6\u7b2c 1 \u5f20\u4f5c\u4e3a\u89c6\u9891\u9996\u5e27\uff08\u5f3a\u5236\uff0c\u591a\u4f59\u5ffd\u7565\uff09
      model/clip  : str   \u53ef\u8986\u76d6\u6a21\u677f\u9ed8\u8ba4\uff08UNET / CLIP\uff09
      weight_dtype: str   \u9ed8\u8ba4 default
      loras       : []    \u7528\u6237 LoRA\uff08\u4e24\u6761\u6d41\u7a0b\u7684 LoRA \u90fd\u53ea\u5728\u8fd9\u91cc\u52a0\u8f7d\uff0c\u5de5\u4f5c\u6d41\u5185\u4e0d\u542b\u4efb\u4f55\u5185\u7f6e LoRA\uff09
      seed / duration_s / megapixels / aspect_ratio
      sampler / scheduler / steps / denoise\uff1a\u4e0e\u6807\u51c6\u5de5\u4f5c\u6d41\u4e00\u81f4\uff0c\u8bfb\u53d6\u524d\u7aef\u8bbe\u7f6e
    \u6ce8\u610f\uff1a\u8be5\u5de5\u4f5c\u6d41\u4e0d\u5403\u53c2\u8003\u97f3\u9891\uff0c\u6545\u5ffd\u7565 ref_audios\u3002
    """
    with open(I2V_WF, encoding="utf-8") as f:
        graph = json.load(f)

    # --- \u63d0\u793a\u8bcd + \u9996\u5e27\uff08\u7b2c 1 \u5f20\u53c2\u8003\u56fe\u5f3a\u5236\u4f5c\u4e3a\u89c6\u9891\u7b2c\u4e00\u5e27\uff1b\u4e0d\u7ecf\u8fc7 _strip_placeholder_refs\uff0c
    #     \u56e0\u4e3a\u672c\u6a21\u677f\u7684 LoadImage \u5c31\u662f\u9996\u5e27\u6765\u6e90\uff0c\u5220\u6389\u4f1a\u65ad\u94fe\uff09 ---
    graph[I2V_LATENT]["inputs"]["prompt"] = cfg["prompt"]
    refs = [r for r in (cfg.get("ref_images") or []) if r]
    if not refs:
        raise RuntimeError("I2VA \u6d41\u7a0b\u5fc5\u987b\u63d0\u4f9b 1 \u5f20\u53c2\u8003\u56fe\u4f5c\u4e3a\u89c6\u9891\u9996\u5e27\u3002")
    graph[I2V_IMAGE]["inputs"]["image"] = refs[0]

    # --- \u6a21\u578b\uff08.gguf \u81ea\u52a8\u5207 UnetLoaderGGUF\uff0c\u4e0e Ref2VA \u5171\u7528\u540c\u4e00 helper\uff09/ CLIP ---
    _set_unet_node(graph, I2V_UNET, cfg)
    if cfg.get("clip") and "105:13" in graph:
        graph["105:13"]["inputs"]["clip_name"] = cfg["clip"]

    # --- \u7528\u6237 LoRA\uff08\u4e32\u5728 UNET \u4e4b\u540e\uff1b\u5de5\u4f5c\u6d41\u5185\u4e0d\u542b\u5185\u7f6e LoRA\uff09---
    _apply_lora(graph, cfg, unet_id=I2V_UNET)

    # --- \u91c7\u6837\u5668 / \u8c03\u5ea6\u5668 / \u6b65\u6570\uff08\u8bfb\u53d6\u524d\u7aef\u8bbe\u7f6e\uff0c\u4e0e\u6807\u51c6\u5de5\u4f5c\u6d41\u4e00\u81f4\uff09---
    if cfg.get("sampler"):
        graph[I2V_SAMPLER]["inputs"]["sampler_name"] = cfg["sampler"]
    if cfg.get("scheduler"):
        graph[I2V_SCHED]["inputs"]["scheduler"] = cfg["scheduler"]
    graph[I2V_SCHED]["inputs"]["steps"] = int(cfg.get("steps", 16))
    graph[I2V_SCHED]["inputs"]["denoise"] = float(cfg.get("denoise", 1.0))

    # --- \u65f6\u957f / \u79cd\u5b50 / \u5206\u8fa8\u7387 ---
    graph[I2V_DURATION]["inputs"]["value"] = float(cfg.get("duration_s", 15.0))
    graph[I2V_SEED]["inputs"]["noise_seed"] = int(cfg.get("seed", 0))
    if cfg.get("megapixels") is not None:
        graph[I2V_RES]["inputs"]["megapixels"] = float(cfg["megapixels"])
    if cfg.get("aspect_ratio"):
        graph[I2V_RES]["inputs"]["aspect_ratio"] = cfg["aspect_ratio"]
    # --- \u4f4e\u663e\u5b58\u5206\u5757\uff08\u53ef\u9009\uff0c\u9ed8\u8ba4\u5173\u95ed\uff1b\u63d2\u5728 Sage \u8865\u4e01\u4e4b\u540e\uff09---
    apply_low_vram_chunk(graph, cfg)
    return graph


def _basename(s):
    return (s or "").replace("\\", "/").split("/")[-1]


def resolve_remote_name(name, node_class):
    """\u628a\u6a21\u578b\u540d\u89c4\u8303\u5316\u5230\u76ee\u6807 ComfyUI \u7684\u5408\u6cd5\u503c\uff08\u542b\u5b50\u76ee\u5f55\u524d\u7f00\uff09\u3002
    \u5148\u7cbe\u786e\u5339\u914d\uff1b\u518d\u6309 basename \u552f\u4e00\u5339\u914d\uff08\u81ea\u52a8\u8865 Minimax H3\\ \u7b49\u524d\u7f00\uff09\uff1b\u7edf\u4e00 /->\\ \u4e0e\u5927\u5c0f\u5199\u3002
    \u5339\u914d\u4e0d\u5230\u552f\u4e00\u7ed3\u679c\u5c31\u539f\u6837\u8fd4\u56de\uff0c\u4e0d\u4e71\u6539\u3002"""
    options = _remote_object_list(node_class) or []
    if not options or not name:
        return name
    norm = lambda s: (s or "").replace("/", "\\").lower()
    for opt in options:
        if norm(opt) == norm(name):
            return opt
    nb = _basename(name).lower()
    cands = [o for o in options if _basename(o).lower() == nb]
    if len(cands) == 1:
        return cands[0]
    return name


_MODEL_FIELDS = ("lora_name", "unet_name", "clip_name", "vae_name", "ckpt_name")


def normalize_graph_names(graph):
    """\u63d0\u4ea4\u524d\u626b\u63cf\u6574\u5f20\u56fe\uff0c\u628a\u6a21\u578b\u540d\u89c4\u8303\u5316\u5230\u76ee\u6807 ComfyUI \u7684\u5408\u6cd5\u503c\uff08\u6807\u51c6/\u5feb\u901f\u5de5\u4f5c\u6d41\u90fd\u8986\u76d6\uff09\u3002"""
    changes = []
    for nid, node in graph.items():
        cls = node.get("class_type") or ""
        inp = node.get("inputs") or {}
        for field in _MODEL_FIELDS:
            val = inp.get(field)
            if isinstance(val, str) and val:
                resolved = resolve_remote_name(val, cls)
                if resolved != val:
                    inp[field] = resolved
                    changes.append(f"node {nid} [{cls}] {field}: {val!r} -> {resolved!r}")
    if changes:
        print("[normalize] \u6a21\u578b\u540d\u5df2\u6309 ComfyUI \u5217\u8868\u4fee\u6b63:\n  " + "\n  ".join(changes), file=sys.stderr)


def submit_and_fetch(graph, outdir, timeout_s=3600):
    normalize_graph_names(graph)
    tmp = os.path.join(HERE, f"_run_{uuid.uuid4().hex[:8]}.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False)
    try:
        result = run_comfy(["run", tmp, "-o", outdir, "--timeout", str(timeout_s)])
        _record_prompt_ids(outdir)
        return result
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _record_prompt_ids(outdir):
    """\u628a\u6700\u8fd1\u4e00\u6b21\u63d0\u4ea4\u5230 ComfyUI \u7684 prompt_id \u8ffd\u52a0\u5230\u4efb\u52a1\u76ee\u5f55\uff0c\u4f9b\u7ec8\u6b62\u65f6\u5b9a\u5411\u53d6\u6d88\u3002"""
    ids = [i for i in _LAST_RUN_PROMPT_IDS if i]
    if not ids:
        return
    task_dir = os.path.dirname(os.path.abspath(outdir))
    try:
        with open(os.path.join(task_dir, "comfy_prompt_ids.txt"), "a", encoding="utf-8") as f:
            for i in ids:
                f.write(i + "\n")
    except Exception:
        pass


def extract_videos(run_result):
    files = [s["file"] for s in run_result.get("saved", [])]
    return [f for f in files if f.lower().endswith((".mp4", ".webm", ".mov", ".mkv"))]


# ============================================================ \u89c6\u9891\u62bd\u5e27
def extract_frames(video_path, outdir, n_frames=6, width=768, as_jpeg=False):
    import shutil
    import re
    if not shutil.which("ffmpeg"):
        print("[warn] \u672a\u627e\u5230 ffmpeg\uff0c\u65e0\u6cd5\u62bd\u5e27\u7ed9\u8bc4\u5ba1\u770b\u56fe\u3002", file=sys.stderr)
        return []
    probe = subprocess.run(["ffmpeg", "-i", video_path], capture_output=True, text=True,
                           errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", probe.stderr)
    dur = 0.0
    if m:
        h, mm, s = map(float, m.groups())
        dur = h * 3600 + mm * 60 + s
    if dur <= 0:
        dur = 15.0
    ext = ".jpg" if as_jpeg else ".png"
    frames = []
    # \u91c7\u6837\u70b9\uff1a\u5747\u5300\u8986\u76d6\u5168\u7247\u5e76**\u5f3a\u5236\u5305\u542b\u672b\u5e27**\u3002
    # \u65e7\u5b9e\u73b0\u7528 t = dur/n*i\uff0c\u6700\u540e\u4e00\u5e27\u843d\u5728 (n-1)/n \u5904\uff0c**\u6c38\u8fdc\u91c7\u4e0d\u5230\u6700\u540e 1/n \u6bb5**\uff1b\u800c\u5c3e\u90e8\u6b63\u662f\u957f\u89c6\u9891
    # \u9000\u5316\u6700\u96c6\u4e2d\u7684\u5730\u65b9\uff08\u8fd0\u52a8\u8870\u51cf\u3001\u7ed5\u56de\u5f00\u5934\u3001\u97f3\u9891\u53d8\u5f31\uff09\uff0c\u65e7\u91c7\u6837\u7b49\u4e8e\u7cfb\u7edf\u6027\u6f0f\u68c0\u3002
    n = max(2, int(n_frames))
    ts = [dur * i / (n - 1) for i in range(n)]
    ts[-1] = max(0.0, dur - 0.5)          # \u672b\u5e27\u7559 0.5s \u4f59\u91cf\uff0c\u907f\u514d\u8d8a\u754c\u53d6\u4e0d\u5230
    for i, t in enumerate(ts):
        fp = os.path.abspath(os.path.join(outdir, f"frame_{i+1:02d}{ext}"))
        cmd = ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", video_path,
               "-frames:v", "1", "-vf", f"scale={width}:-2"]
        if as_jpeg:
            cmd += ["-q:v", "5"]
        cmd.append(fp)
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and os.path.exists(fp):
            frames.append(fp)
    return frames


def review_frame_count(duration, base=32):
    """\u8bc4\u5ba1\u62bd\u5e27\u6570\u968f\u65f6\u957f\u81ea\u9002\u5e94\uff1a\u77ed\u7247 32 \u5e27\u591f\u7528\uff1b\u957f\u7247\u9700\u8981\u66f4\u5bc6\u7684\u65f6\u95f4\u5206\u8fa8\u7387\u3002

    60 \u79d2 / 40 \u5e27 \u2248 \u6bcf 1.5 \u79d2\u4e00\u5e27\uff1b\u518d\u5bc6\u6536\u76ca\u9012\u51cf\uff0c\u800c\u89c6\u89c9 LLM \u7684\u56fe\u7247 token \u6210\u672c\u662f\u7ebf\u6027\u4e0a\u5347\u7684\u3002
    """
    try:
        d = float(duration)
    except (TypeError, ValueError):
        return int(base)
    if d <= TRAINED_MAX_S:
        return int(base)
    return int(max(int(base), min(40, round(d * 0.66))))


def long_video_critic_addendum(duration):
    """\u957f\u89c6\u9891\u4e13\u7528\u8bc4\u5ba1\u89c4\u5219\uff1b\u226415 \u79d2\u8fd4\u56de\u7a7a\u4e32\uff08\u4fdd\u8bc1\u77ed\u7247\u8bc4\u5ba1 prompt \u5b57\u8282\u4e0d\u53d8\uff09\u3002"""
    if not is_long_video(duration):
        return ""
    try:
        d = float(duration)
    except (TypeError, ValueError):
        d = 0.0
    return (
        "\n"
        f"**\u957f\u89c6\u9891\u989d\u5916\u6838\u9a8c\uff08\u672c\u7247 {d:g} \u79d2\uff0c\u5df2\u8d85\u51fa H3 \u8bad\u7ec3\u8303\u56f4 ~5\u201315 \u79d2\uff0c\u5fc5\u987b\u505a\uff09**\uff1a\n"
        "\u3010\u5ba2\u89c2\u6307\u6807\u3011\u7531 ffmpeg \u9010\u79d2\u91c7\u6837\u7b97\u51fa\uff0c\u662f\u5730\u9762\u771f\u76f8\uff0c**\u4f60\u7684\u5224\u65ad\u4e0d\u5f97\u4e0e\u5b83\u77db\u76fe**\uff1a\n"
        "  \u00b7 \u5c3e\u90e8\u8fd0\u52a8\u6bd4\uff08\u5c3e\u90e8/\u5168\u7247\u8fd0\u52a8\uff09< 0.7 \u2192 \u5224\u5c3e\u90e8\u8870\u51cf\uff0c\u6263 story_beats \u4e0e action_logic\uff1b\n"
        "  \u00b7 \u5c3e\u90e8\u51bb\u7ed3\uff08\u5c3e\u90e8\u7a97\u53e3\u5185\u8fc7\u534a\u5e27\u8fd1\u9759\u6b62\uff09\u2192 \u5224\u753b\u9762\u505c\u4f4f\uff0c\u6263 story_beats \u4e0e action_logic\uff1b\n"
        "  \u00b7 \u590d\u8bfb\u76f8\u5173\u504f\u9ad8\u5c5e\u3010\u8f85\u52a9\u8bc1\u636e\u3011\uff08\u8be5\u6307\u6807\u57fa\u7ebf\u9ad8\uff09\uff0c\u5fc5\u987b\u4e0e\u5c3e\u90e8\u8fd0\u52a8\u8870\u51cf/\u5bf9\u6bd4\u5ea6\u4e0b\u6ed1\u540c\u65f6\u51fa\u73b0"
        "\u624d\u5224\u5b9a\u4e3a\"\u7ed5\u56de\u5f00\u5934\"\uff0c\u4e0d\u8981\u4ec5\u51ed\u5b83\u6263\u5206\uff1b\n"
        "  \u00b7 \u8272\u5f69\u6f02\u79fb\u4e0e\u5bf9\u6bd4\u5ea6\u53d8\u5316**\u53ea\u4f5c\u53c2\u8003**\uff1a\u5267\u672c\u82e5\u8981\u6c42\u6052\u5b9a\u5149\u7167/\u6052\u5b9a\u8272\u8c03\uff0c\u4f4e\u6f02\u79fb**\u4e0d\u7b97\u9000\u5316**\uff1b"
        "\u53ea\u6709\u5f53\u753b\u9762\u4e0e\u5267\u672c\u4e0d\u7b26\uff08\u8be5\u53d8\u7684\u6ca1\u53d8\u3001\u8be5\u4eae\u7684\u6ca1\u4eae\uff09\u65f6\u624d\u6263 environment\uff1b\n"
        "  \u00b7 \u5c3e\u90e8\u97f3\u9891\u6bd4\u9996\u90e8\u4f4e 10 dB \u4ee5\u4e0a \u2192 \u540e\u534a\u6bb5\u58f0\u97f3\u53d8\u5f31\uff0c\u6263 audio_affordance\u3002\n"
        "\u8fd8\u8981\u6838\u9a8c**\u65f6\u957f\u5229\u7528\u7387**\uff1a\u8fd9\u51e0\u5341\u79d2\u662f\u5426\u88ab\u65b0\u5185\u5bb9\u586b\u6ee1\uff0c\u662f\u5426\"\u91cd\u5934\u620f\u5728\u524d\u534a\u6bb5\u3001\u540e\u534a\u6bb5\u5212\u6c34\"\uff1b"
        "\u82e5\u540e\u6bb5\u91cd\u590d\u6216\u505c\u6ede\uff0cgaps \u5fc5\u987b\u5199\u660e\u4ece\u7b2c\u51e0\u79d2\u5f00\u59cb\u51fa\u95ee\u9898\u3002\n"
    )


# ============================================================ LLM \u751f\u6210\u5267\u672c+\u683c\u5f0f
def _ref_list(ref_names, aud_names=None):
    """\u628a\u53c2\u8003\u6e05\u5355\u6574\u7406\u6210\u7ed9 LLM \u7684\u6587\u672c\uff1a**1-based**\uff0c\u5e76\u76f4\u63a5\u6807\u51fa H3 \u7684\u6807\u7b7e\u3002

    \u7b2c 1 \u5f20\u53c2\u8003\u56fe\u63a5\u7684\u662f `ref_image_0` \u63d2\u69fd \u2192 \u5728 H3 \u91cc\u5448\u73b0\u4e3a `<Picture 1>`\uff0c
    \u6240\u4ee5\u6e05\u5355\u5e8f\u53f7\u5fc5\u987b\u4ece 1 \u8d77\u3001\u4e0d\u8bb8\u51fa\u73b0 0 \u53f7\uff08\u4e0e optimizer._fmt_refs \u53e3\u5f84\u4e00\u81f4\uff09\u3002"""
    txt = "\n".join(f"<Picture {i}> = {r}" for i, r in enumerate(ref_names, 1))
    if aud_names:
        txt += ("\n# \u53ef\u7528\u53c2\u8003\u97f3\u9891\uff08\u5e8f\u53f7\u5373\u63d0\u793a\u8bcd\u4e2d\u7684 <Audio N>\uff0c\u4ece 1 \u8d77\uff09\n"
                + "\n".join(f"<Audio {i}> = {a}" for i, a in enumerate(aud_names, 1)))
    return txt


def llm_script_and_prompt(llm, story, ref_names, aud_names, duration=15.0):
    d = float(duration)
    director_user = (
        f"# \u6545\u4e8b\u5927\u7eb2\n{story}\n\n"
        f"# \u53ef\u7528\u53c2\u8003\u56fe\n" + _ref_list(ref_names, aud_names)
        + f"\n\n\u8bf7\u6309 system \u7ea6\u5b9a\u7684 JSON \u4ea7\u51fa {d:g} \u79d2\u5267\u672c\u3002"
    )
    script = llm.chat_json(system_director(d), director_user)
    # \u5b98\u65b9\u6307\u5357\u653e system\uff08\u8de8\u8c03\u7528\u7a33\u5b9a \u2192 \u524d\u7f00\u7f13\u5b58\u53ef\u590d\u7528\uff09\uff1b\u6613\u53d8\u7684\u5267\u672c JSON \u653e user \u672b\u5c3e
    formatter_system = SYSTEM_FORMATTER + "\n\n# MiniMax \u5b98\u65b9\u6307\u5357\n" + _read_guide()
    formatter_user = (
        f"# \u53ef\u7528\u53c2\u8003\u56fe\n" + _ref_list(ref_names, aud_names)
        + f"\n\n# \u5267\u672c\u4e2d\u95f4\u4ea7\u7269\n{json.dumps(script, ensure_ascii=False)}"
        + "\n\n\u8bf7\u76f4\u63a5\u8f93\u51fa\u5b8c\u6574\u516d\u6bb5 ref2va prompt \u7eaf\u6587\u672c\u3002"
    )
    prompt = llm.chat(formatter_system, formatter_user, max_tokens=32000)
    return script, prompt


def parse_critic(raw):
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except Exception:
        return None


# ============================================================ \u81ea\u52a8\u6d41\u7a0b
def run_auto(args, llm):
    with open(args.story, encoding="utf-8") as f:
        story = f.read().strip()
    if not story:
        sys.exit("\u6545\u4e8b\u5927\u7eb2\u4e3a\u7a7a")
    int_dir = os.environ.get("COMFYUI_INPUT_DIR", os.path.join(os.getcwd(), "input"))
    ref_names = sync_ref_files(args.refs, int_dir)
    aud_names = sync_ref_files(args.ref_audios, int_dir) if args.ref_audios else []

    os.makedirs(args.outdir, exist_ok=True)
    print("= 1/4 LLM#1 \u5267\u672c\u6269\u5c55")
    script, ref2va_prompt = llm_script_and_prompt(llm, story, ref_names, aud_names, args.duration)
    print("  \u5267\u672c\u6982\u8981:", script.get("summary_zh", ""), "| prompt\u957f\u5ea6:", len(ref2va_prompt))

    chain = {"script": script, "prompt": ref2va_prompt}
    best = {"overall": -1, "prompt": ref2va_prompt, "video": None, "round": 0}

    base_cfg = {
        "model": os.environ.get(
            "REF2VA_MODEL",
            "minimax_h3_ref2va_pruned_zs05_int8_convrot.safetensors"),
        "weight_dtype": "default", "sampler": "res_multistep",
        "scheduler": "sgm_uniform", "steps": args.steps, "denoise": 1.0,
        "ref_images": ref_names, "ref_audios": aud_names,
        "duration_s": args.duration,
        "megapixels": getattr(args, "megapixels", None),
    }

    for round_no in range(1, args.rounds + 1):
        print(f"= 3/4 Round {round_no}/{args.rounds} ComfyUI \u751f\u6210")
        cfg = dict(base_cfg, prompt=chain["prompt"], seed=args.seed + round_no - 1)
        rundir = os.path.join(args.outdir, f"round_{round_no}")
        os.makedirs(rundir, exist_ok=True)
        res = submit_and_fetch(make_graph(cfg), rundir)
        videos = extract_videos(res)
        if not videos:
            print("[warn] \u672c\u8f6e\u672a\u4ea7\u751f\u89c6\u9891:", json.dumps(res, ensure_ascii=False)[:800]); continue
        video = videos[0]
        print("  \u89c6\u9891:", video)

        print("= 4/4 LLM#3 \u8bc4\u5ba1")
        frames = extract_frames(video, rundir, n_frames=args.frames)
        critic_prompt = (
            f"# \u6545\u4e8b\u5927\u7eb2\n{story}\n\n"
            f"\u4e0b\u9762 {max(len(frames),1)} \u5f20\u5173\u952e\u5e27\u6765\u81ea\u540c\u4e00\u6bb5\u751f\u6210\u7684\u89c6\u9891\uff08\u6309\u65f6\u95f4\u987a\u5e8f\uff09\u3002"
            "\u8bf7\u9010\u7ef4\u5ea6\u6253\u5206\u5e76\u7ed9\u51fa verdict \u4e0e gaps\u3002"
        )
        if frames:
            critic_raw = llm.vision(SYSTEM_CRITIC, critic_prompt,
                                    [llm.encode_image(f) for f in frames], temperature=0)
        else:
            critic_raw = llm.chat(SYSTEM_CRITIC, critic_prompt, temperature=0)
        eval_ = parse_critic(critic_raw)
        if eval_ is None:
            print("[warn] \u8bc4\u5ba1\u975eJSON:"); print(critic_raw[:600]); continue
        overall = float(eval_.get("overall", 0))
        print(f"  \u6574\u4f53:{overall:.1f}  verdict:{eval_.get('verdict')}")
        if overall > best["overall"]:
            best = {"overall": overall, "prompt": chain["prompt"], "video": video, "round": round_no}
        if overall >= args.threshold or eval_.get("verdict") == "pass":
            print("\u2713 \u8fbe\u6807\u6536\u5c3e"); _finalize(args, best, chain, story, eval_, aud_names); return
        if round_no == args.rounds:
            break
        gaps = "\n".join(f"- {g}" for g in eval_.get("gaps", []))
        print("  \u8fdb\u5165\u4e0b\u4e00\u8f6e:")  # \u56de\u7089
        revise_user = (
            f"# \u4e0a\u4e00\u7248\u5267\u672c\n{json.dumps(chain['script'], ensure_ascii=False)}\n\n"
            f"# \u6700\u65b0 ref2va prompt\n{chain['prompt']}\n\n# \u8bc4\u5ba1\u5dee\u8ddd\n{gaps}\n\n"
            f"\u8bf7\u57fa\u4e8e\u53cd\u9988\u4fee\u8ba2\u5267\u672c JSON \u540e\u8f93\u51fa\uff08\u4fdd\u6301\u540c\u4e00\u7ed3\u6784\uff09\u3002"
        )
        chain["script"] = llm.chat_json(system_director(args.duration), revise_user)
        fu = (
            f"# \u53ef\u7528\u53c2\u8003\u56fe\n" + _ref_list(ref_names, aud_names)
            + f"\n\n# \u4fee\u8ba2\u540e\u5267\u672c\n{json.dumps(chain['script'], ensure_ascii=False)}"
            + "\n\n\u8bf7\u57fa\u4e8e\u4fee\u8ba2\u5267\u672c\u91cd\u65b0\u8f93\u51fa ref2va prompt \u7eaf\u6587\u672c\u3002"
        )
        revised = llm.chat(
            SYSTEM_FORMATTER + "\n\u4ec5\u9488\u5bf9\u8bc4\u5ba1\u5dee\u8ddd\u6700\u5c0f\u6539\u52a8\uff0c\u4fdd\u6301\u5df2\u8fbe\u6807\u7684\u63cf\u8ff0\u3002"
            + "\n\n# MiniMax \u5b98\u65b9\u6307\u5357\n" + _read_guide(),
            fu, max_tokens=32000)
        chain["prompt"] = revised
    print("= \u8fbe\u5230\u6700\u5927\u8f6e\u6570\uff0c\u8f93\u51fa\u5f53\u524d\u6700\u4f73")
    _finalize(args, best, chain, story,
              {"overall": best["overall"], "verdict": "fail", "gaps": [], "strengths": []},
              aud_names)


def _finalize(args, best, chain, story, eval_, aud_names):
    report = {
        "story": story, "refs": args.refs, "ref_audios": aud_names,
        "seed": args.seed, "best_overall": best["overall"], "verdict": eval_.get("verdict"),
        "final_prompt": best["prompt"], "final_video": best.get("video"),
        "round": best["round"], "critic": eval_, "script": chain["script"],
    }
    rp = os.path.join(args.outdir, "report.json")
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\u843d\u5730\u62a5\u544a:", rp); print("\u6700\u7ec8\u89c6\u9891:", best.get("video"))


# ============================================================ \u5bf9\u7167\u626b\u63cf
def run_sweep(args, llm):
    """sweep\uff1a\u540c\u4e00 refs + \u540c\u4e00 prompt\uff0c\u904d\u5386\u591a\u7ec4\u6a21\u578b/\u91c7\u6837\u53c2\u6570\u3002"""
    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as f:
            prompt = f.read().strip()
        if not prompt:
            sys.exit("prompt-file \u4e3a\u7a7a")
    else:
        if not args.story:
            sys.exit("sweep \u9700\u8981 --prompt-file \u6216 --story")
        with open(args.story, encoding="utf-8") as f:
            story = f.read().strip()
        int_dir = os.environ.get("COMFYUI_INPUT_DIR", os.path.join(os.getcwd(), "input"))
        ref_names = sync_ref_files(args.refs, int_dir)
        aud_names = sync_ref_files(args.ref_audios, int_dir) if args.ref_audios else []
        print("= LLM \u751f\u6210\u5267\u672c+prompt")
        script, prompt = llm_script_and_prompt(llm, story, ref_names, aud_names, args.duration)
        prompt_file = os.path.join(args.outdir, "prompt.txt")
        os.makedirs(args.outdir, exist_ok=True)
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)
        print("  prompt \u5df2\u5b58:", prompt_file)

    sweeps = _load_sweeps(args.sweep)
    int_dir = os.environ.get("COMFYUI_INPUT_DIR", os.path.join(os.getcwd(), "input"))
    ref_names = sync_ref_files(args.refs, int_dir)
    aud_names = sync_ref_files(args.ref_audios, int_dir) if args.ref_audios else []

    os.makedirs(args.outdir, exist_ok=True)
    results = []
    for idx, scfg in enumerate(sweeps, 1):
        name = scfg.get("name", f"cfg{idx}")
        cfg = {
            "prompt": prompt, "ref_images": ref_names, "ref_audios": aud_names,
            "seed": scfg.get("seed", args.seed),
            "duration_s": scfg.get("duration", args.duration),
            "model": scfg.get("model"), "weight_dtype": scfg.get("weight_dtype", "default"),
            "sampler": scfg.get("sampler", "res_multistep"),
            "scheduler": scfg.get("scheduler", "sgm_uniform"),
            "steps": scfg.get("steps", args.steps), "denoise": scfg.get("denoise", 1.0),
        }
        print(f"[sweep {idx}/{len(sweeps)}] {name}: model={cfg['model']} "
              f"sampler={cfg['sampler']} scheduler={cfg['scheduler']} "
              f"steps={cfg['steps']} denoise={cfg['denoise']}")
        rundir = os.path.join(args.outdir, f"sweep_{idx:02d}_{name}")
        os.makedirs(rundir, exist_ok=True)
        try:
            res = submit_and_fetch(make_graph(cfg), rundir)
            videos = extract_videos(res)
        except Exception as e:
            videos = []; print("  [err]", str(e))
        results.append({"index": idx, "name": name, "config": cfg,
                        "video": videos[0] if videos else None})
        if args.evaluate and videos:
            frames = extract_frames(videos[0], rundir, n_frames=args.frames)
            if frames:
                story_for_critic = args.story_critic or ""
                cp = (f"# \u6545\u4e8b\u5927\u7eb2\n{story_for_critic}\n\n\u4e0b\u9762 {len(frames)} \u5f20\u5173\u952e\u5e27\u6765\u81ea\u4e00\u6bb5\u751f\u6210\u89c6\u9891"
                      "\uff08\u540c\u4e00 refs \u7684\u91cf\u5316/\u964d\u566a\u5bf9\u7167\uff0c\u4ec5\u8bc4\u753b\u8d28\u4e0e\u9700\u6c42\u7b26\u5408\u5ea6\uff09\uff0c\u7ed9\u51fa\u5206\u6570/verdict/gaps\u3002"
                      ) if story_for_critic else (
                    "\u4e0b\u9762\u5173\u952e\u5e27\u6765\u81ea\u4e00\u6bb5\u751f\u6210\u7684\u89c6\u9891\uff08\u91cf\u5316\u6a21\u578b/\u964d\u566a\u5bf9\u7167\uff09\u3002\u8bf7\u6309\u9700\u6c42\u7b26\u5408\u5ea6\u6253\u5206\u5e76\u7ed9\u51fa verdict/gaps\u3002"
                )
                cr = llm.vision(SYSTEM_CRITIC, cp, [llm.encode_image(f) for f in frames], temperature=0)
                ev = {} if parse_critic(cr) is None else parse_critic(cr)
                results[-1]["critic"] = ev
                print("  \u8bc4\u5ba1 overall:", ev.get("overall"))
            else:
                results[-1]["critic"] = {"overall": None, "note": "\u65e0\u5e27\u53ef\u8bc4\u5ba1"}
    out = os.path.join(args.outdir, "sweep_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"prompt": prompt, "refs": ref_names, "audios": aud_names,
                   "results": results}, f, ensure_ascii=False, indent=2)
    print("\n== sweep \u6c47\u603b ==")
    for r in results:
        sc = (r.get("critic") or {}).get("overall")
        print(f"  [{r['name']}] video={r['video']} overall={sc}")
    print("\u6c47\u603b JSON:", out)


def _load_sweeps(path):
    """\u8bfb\u53d6 sweep \u914d\u7f6e\u3002\u652f\u6301\u4e24\u79cd\uff1a
    1) {"configs": [...]} \u663e\u5f0f\u5217\u8868\uff08\u73b0\u6709\uff09
    2) {"model_pattern":"ref2va","sweep_params":{...}, "subfolder":None, "base_dir":...}
       -> \u81ea\u52a8\u626b\u63cf\u6a21\u578b\u76ee\u5f55\uff0c\u4e3a\u6bcf\u4e2a\u5339\u914d\u6a21\u578b\u751f\u6210\u4e00\u4e2a config\uff08\u6cbf\u7528 sweep_params\uff0c\u53ef\u88ab\u6a21\u578b\u7ea7\u8986\u76d6\uff09
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if "configs" in data:
        return data["configs"]
    if "model_pattern" in data:
        sub = data.get("subfolder")
        base_dir = data.get("base_dir")
        pat = data["model_pattern"]
        params = data.get("sweep_params", {}) or {}
        if base_dir:
            # \u9012\u5f52\u626b\u63cf\u81ea\u5b9a\u4e49\u76ee\u5f55\uff0c\u5f15\u7528\u540d=\u76f8\u5bf9\u8be5\u76ee\u5f55\u7236\u7ea7\u7684\u8def\u5f84\uff08\u4e0e UNETLoader COMBO \u4e60\u60ef\u4e00\u81f4\uff09
            parent = os.path.dirname(os.path.abspath(base_dir))
            models = []
            for d0, _dirs, fns in os.walk(base_dir):
                for fn in fns:
                    if pat in fn and fn.lower().endswith((".safetensors", ".gguf")):
                        full = os.path.abspath(os.path.join(d0, fn))
                        rel = os.path.relpath(full, parent).replace("\\", "/")
                        models.append(rel)
        else:
            models = discover_models(sub, pat)
        out = []
        for i, m in enumerate(models, 1):
            cfg = dict(params)
            cfg["model"] = m
            cfg.setdefault("name", os.path.splitext(os.path.basename(m))[0])
            out.append(cfg)
        return out
    return [data]


# ============================================================ CLI
def main():
    p = argparse.ArgumentParser(description="ref2va \u89c6\u9891\u751f\u6210\u7f16\u6392\u5668\uff08auto/sweep\uff09")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--story", help="\u6545\u4e8b\u5927\u7eb2\u6587\u4ef6(.txt) -> \u8d70 LLM#1/#2 \u81ea\u52a8 + \u56de\u7089")
    g.add_argument("--prompt-file", help="\u76f4\u63a5\u7528\u56fa\u5b9a ref2va prompt \u6587\u672c\uff08\u914d\u5408 --sweep\uff09")

    p.add_argument("--refs", nargs="+", default=[], help="\u53c2\u8003\u56fe\u7247\u8def\u5f84\uff08\u22649\uff09")
    p.add_argument("--ref-audios", nargs="+", default=[], help="\u53c2\u8003\u97f3\u9891\u8def\u5f84\uff08\u22643\uff09")
    p.add_argument("--comfy-url", default=None,
                   help="ComfyUI \u76ee\u6807\u670d\u52a1\u5668\u5730\u5740\uff0c\u5982 http://127.0.0.1:8000 "
                        "\uff08\u9ed8\u8ba4\u53d6 COMFYUI_URL \u73af\u5883\u53d8\u91cf\u6216\u672c\u673a 127.0.0.1:8000\uff09")
    # \u81ea\u52a8\u6d41\u7a0b\u53c2\u6570
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--duration", type=float, default=15.0)
    p.add_argument("--steps", type=int, default=20)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--threshold", type=float, default=8.0)
    p.add_argument("--frames", type=int, default=6, help="\u8bc4\u5ba1\u62bd\u5e27\u6570")
    p.add_argument("--outdir", default=os.path.join(ROOT, "outputs", "auto"))
    p.add_argument("--keep-frames", action="store_true")
    # sweep \u6a21\u5f0f\u53c2\u6570
    p.add_argument("--sweep", help="sweep \u914d\u7f6e\u6587\u4ef6(json)")
    p.add_argument("--sweep-outdir", default=None)
    p.add_argument("--evaluate", action="store_true",
                   help="sweep \u6bcf\u7248\u53ef\u9009\u7528 LLM#3 \u8bc4\u5ba1\u6253\u5206")
    p.add_argument("--story-critic", default=None,
                   help="sweep \u8bc4\u5ba1\u65f6\u9644\u5e26\u7684\u5bf9\u7167\u5927\u7eb2\u6587\u4ef6(\u53ef\u9009)")
    args = p.parse_args()
    set_comfy_url(args.comfy_url)

    if args.sweep:
        if args.prompt_file is None and args.story is None:
            sys.exit("sweep \u6a21\u5f0f\u9700\u8981 --prompt-file \u6216 --story")
        if not args.refs:
            sys.exit("sweep \u9700\u8981 --refs")
        args.outdir = args.sweep_outdir or args.outdir
        run_sweep(args, LLM())
        return

    if args.story is None or not args.refs:
        sys.exit("auto \u6a21\u5f0f\u9700\u8981 --story + --refs")
    run_auto(args, LLM())


if __name__ == "__main__":
    main()
