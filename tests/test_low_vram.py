#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\u4f4e\u663e\u5b58\u5206\u5757\uff08\u53ef\u9009\u529f\u80fd\uff09\u7684\u79bb\u7ebf\u9a8c\u8bc1\uff1a**\u4e0d\u9700\u8981 GPU\u3001\u4e0d\u9700\u8981\u771f\u7684\u6e32\u67d3**\u3002

\u88ab\u6d4b\u673a\u5236
--------
`core/ref2va_auto.py` \u7684 `apply_low_vram_chunk()`\uff1a\u6309 `cfg['low_vram']` \u5728 Sage \u6ce8\u610f\u529b\u8865\u4e01\u4e4b\u540e
\u63d2\u5165 ComfyUI-KJNodes \u7684\u4e24\u4e2a\u8282\u70b9\uff08MiniMaxChunkFeedForward / MiniMaxLowVRAMAttention\uff09\u3002

\u4e3a\u4ec0\u4e48\u8fd9\u4e9b\u68c0\u67e5"\u80fd\u5931\u8d25"
----------------------
* \u5173\u6389\u65f6\u5fc5\u987b\u4e0e\u6a21\u677f**\u5b8c\u5168\u4e00\u81f4**\uff08\u8282\u70b9\u96c6\u5408\u3001\u8fde\u7ebf\u90fd\u4e0d\u53d8\uff09\u2014\u2014\u5426\u5219"\u9ed8\u8ba4\u5173\u95ed"\u5c31\u662f\u5047\u7684\uff1b
* \u6253\u5f00\u65f6\u5fc5\u987b\u771f\u7684\u591a\u51fa\u8282\u70b9\u3001\u4e14**\u539f\u672c\u6d88\u8d39 Sage \u8f93\u51fa\u7684\u8fde\u7ebf\u88ab\u6539\u6307\u5230\u65b0\u94fe\u5c3e**\u2014\u2014
  \u53ea\u63d2\u8282\u70b9\u4e0d\u6539\u8fde\u7ebf\uff0cComfyUI \u4f9d\u7136\u8d70\u539f\u8def\u5f84\uff0c\u529f\u80fd\u7b49\u4e8e\u6ca1\u63a5\u4e0a\uff1b
* \u975e\u6cd5\u53d6\u503c\u5fc5\u987b\u62a5\u9519\uff0c\u4e0d\u80fd\u9759\u9ed8\u56de\u9000\uff08\u5426\u5219\u7528\u6237\u4ee5\u4e3a\u5f00\u4e86\u5176\u5b9e\u6ca1\u5f00\uff09\u3002

\u5b9e\u6d4b\u4f9d\u636e\u89c1 VERIFICATION.md\u300c\u4f4e\u663e\u5b58\u5206\u5757\u300d\uff1b\u6a21\u677f\u6587\u4ef6\u91cc**\u4e0d\u542b**\u8fd9\u4e24\u4e2a\u8282\u70b9\uff08\u6761\u4ef6\u63d2\u5165\uff09\u3002
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))

import ref2va_auto as ra  # noqa: E402

PASS = 0
FAIL = 0


def check(name, ok, extra=None):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("PASS  %s" % name)
    else:
        FAIL += 1
        print("FAIL  %s   -> %s" % (name, extra))


def base_cfg(**kw):
    cfg = {"prompt": "test prompt", "model": None, "clip": None, "weight_dtype": "default",
           "sampler": "euler", "scheduler": "simple", "steps": 4, "denoise": 1.0,
           "seed": 1, "duration_s": 10.0, "megapixels": 0.4,
           "ref_images": [], "ref_audios": [], "ref_image_size": "match"}
    cfg.update(kw)
    return cfg


def graph_of(**kw):
    return ra.make_graph(base_cfg(**kw))


def nodes_of_type(g, cls):
    return sorted(k for k, v in g.items() if (v.get("class_type") or "") == cls)


def model_consumers(g, target):
    """\u8c01\u628a target \u5f53 model \u8f93\u5165\u3002"""
    out = []
    for n, node in g.items():
        v = (node.get("inputs") or {}).get("model")
        if isinstance(v, list) and len(v) == 2 and v[0] == target:
            out.append(n)
    return sorted(out)


print("A. \u9ed8\u8ba4\u5173\u95ed\uff1a\u56fe\u5fc5\u987b\u4e0e\u6a21\u677f\u5b8c\u5168\u4e00\u81f4")
tpl = json.load(io.open(os.path.join(ROOT, "workflows", "video_minimax_h3_r2v.api.json"),
                        encoding="utf-8"))
g_off = graph_of(low_vram="off")
check("low_vram=off \u65f6\u4e0d\u542b 9001/9002", "9001" not in g_off and "9002" not in g_off)
check("low_vram \u7f3a\u7701\uff08\u4e0d\u4f20\uff09\u7b49\u540c off", "9001" not in graph_of(), sorted(graph_of().keys())[:3])
# \u8fde\u7ebf\u4e5f\u4e0d\u80fd\u53d8\uff1a\u628a\u6a21\u677f\u8dd1\u4e00\u904d make_graph\uff08\u540c\u53c2\u6570\uff09\uff0c\u4e24\u8005\u5e94\u5b8c\u5168\u4e00\u81f4
cfg_same = base_cfg(low_vram="off")
g_a = ra.apply_low_vram_chunk(json.loads(json.dumps(g_off)), cfg_same)
check("\u5173\u6389\u65f6 apply_low_vram_chunk \u4e0d\u52a8\u56fe\uff08\u8fd4\u56de\u7a7a\u8bf4\u660e\uff09", g_a == [], g_a)

print("\nB. mlp \u6863\uff1a\u53ea\u63d2 MLP \u5206\u5757\uff0c\u5e76\u628a Sage \u7684\u4e0b\u6e38\u6539\u6307\u8fc7\u53bb")
g_mlp = graph_of(low_vram="mlp")
sage_nodes = nodes_of_type(g_mlp, "MiniMaxH3MemoryEfficientSageAttentionPatch")
check("\u6a21\u677f\u91cc\u6709 Sage \u8865\u4e01\u8282\u70b9\uff08\u63d2\u5165\u951a\u70b9\uff09", len(sage_nodes) == 1, sage_nodes)
sage = sage_nodes[0] if sage_nodes else None
check("mlp \u6863\u63d2\u5165 1 \u4e2a MiniMaxChunkFeedForward", len(nodes_of_type(g_mlp, "MiniMaxChunkFeedForward")) == 1)
check("mlp \u6863\u4e0d\u63d2\u5165 MiniMaxLowVRAMAttention", nodes_of_type(g_mlp, "MiniMaxLowVRAMAttention") == [])
ch = nodes_of_type(g_mlp, "MiniMaxChunkFeedForward")[0]
check("\u5206\u5757\u8282\u70b9\u7684 model \u63a5\u5728 Sage \u4e4b\u540e", g_mlp[ch]["inputs"]["model"] == [sage, 0],
      g_mlp[ch]["inputs"]["model"])
check("\u5206\u5757\u53c2\u6570\u6309\u9ed8\u8ba4\u5199\u5165\uff08chunks=8 / seq_threshold=4096\uff09",
      g_mlp[ch]["inputs"]["chunks"] == ra.LOW_VRAM_DEFAULT_CHUNKS
      and g_mlp[ch]["inputs"]["seq_threshold"] == ra.LOW_VRAM_SEQ_THRESHOLD,
      g_mlp[ch]["inputs"])
before = model_consumers(g_off, sage)      # \u5173\u6389\u65f6\u8c01\u6d88\u8d39 Sage
after = model_consumers(g_mlp, sage)
check("Sage \u7684\u8f93\u51fa\u53ea\u88ab\u65b0\u5206\u5757\u8282\u70b9\u6d88\u8d39\uff08\u539f\u6d88\u8d39\u8005\u5df2\u6539\u6307\uff09", after == [ch], after)
check("\u539f\u6d88\u8d39 Sage \u7684\u8282\u70b9\u5168\u90e8\u6539\u6307\u5230\u5206\u5757\u8282\u70b9",
      sorted(model_consumers(g_mlp, ch)) == before, (before, model_consumers(g_mlp, ch)))

print("\nC. mlp_attn \u6863\uff1a\u4e24\u4e2a\u8282\u70b9\u4e32\u8d77\u6765\uff0c\u94fe\u5c3e\u662f\u6ce8\u610f\u529b\u5934\u5206\u7ec4")
g_attn = graph_of(low_vram="mlp_attn")
c1 = nodes_of_type(g_attn, "MiniMaxChunkFeedForward")
c2 = nodes_of_type(g_attn, "MiniMaxLowVRAMAttention")
check("mlp_attn \u6863\u63d2\u5165\u4e24\u4e2a\u8282\u70b9", len(c1) == 1 and len(c2) == 1, (c1, c2))
check("\u6ce8\u610f\u529b\u8282\u70b9\u63a5\u5728 MLP \u5206\u5757\u4e4b\u540e", g_attn[c2[0]]["inputs"]["model"] == [c1[0], 0],
      g_attn[c2[0]]["inputs"]["model"])
check("\u6ce8\u610f\u529b\u5934\u5206\u7ec4\u9ed8\u8ba4 8", g_attn[c2[0]]["inputs"]["head_chunks"] == ra.LOW_VRAM_DEFAULT_HEAD_CHUNKS)
check("\u94fe\u5c3e\u662f\u6ce8\u610f\u529b\u8282\u70b9\uff08\u539f Sage \u6d88\u8d39\u8005\u90fd\u6539\u6307\u5b83\uff09",
      sorted(model_consumers(g_attn, c2[0])) == before and model_consumers(g_attn, c1[0]) == [c2[0]],
      (model_consumers(g_attn, c2[0]), model_consumers(g_attn, c1[0])))

print("\nC2. \u53cd\u5411\u8fd8\u539f\uff1a\u5220\u6389\u5206\u5757\u8282\u70b9 + \u8fd8\u539f\u8fde\u7ebf \u21d2 \u5fc5\u987b\u4e0e\u5173\u6389\u65f6\u9010\u5b57\u8282\u76f8\u540c\uff08\u8bc1\u660e\u6ca1\u52a8\u522b\u7684\u4e1c\u897f\uff09")


def strip_chunk(g_on, g_base):
    g = json.loads(json.dumps(g_on))
    for nid in ("9001", "9002"):
        g.pop(nid, None)
    for n, node in g.items():
        v = (node.get("inputs") or {}).get("model")
        if isinstance(v, list) and v and v[0] in ("9001", "9002"):
            node["inputs"]["model"] = g_base[n]["inputs"]["model"]
    return g


check("mlp_attn \u6863\u8fd8\u539f\u540e == off \u6863",
      json.dumps(strip_chunk(g_attn, g_off), sort_keys=True)
      == json.dumps(g_off, sort_keys=True))
check("mlp \u6863\u8fd8\u539f\u540e == off \u6863",
      json.dumps(strip_chunk(g_mlp, g_off), sort_keys=True)
      == json.dumps(g_off, sort_keys=True))

print("\nD. \u81ea\u5b9a\u4e49\u5206\u5757\u6570\u4e0e\u6570\u503c\u6821\u9a8c")
g_c = graph_of(low_vram="mlp", chunk_chunks=3, chunk_head_chunks=5)
check("chunk_chunks \u751f\u6548", g_c[nodes_of_type(g_c, "MiniMaxChunkFeedForward")[0]]["inputs"]["chunks"] == 3)
g_c2 = graph_of(low_vram="mlp_attn", chunk_chunks=16, chunk_head_chunks=2)
check("chunk_head_chunks \u751f\u6548\uff08\u4e32\u8d77\u6765\u65f6\uff09",
      g_c2[nodes_of_type(g_c2, "MiniMaxLowVRAMAttention")[0]]["inputs"]["head_chunks"] == 2)
for bad, why in (({"low_vram": "banana"}, "\u672a\u77e5\u6863\u4f4d"),
                 ({"low_vram": "mlp", "chunk_chunks": 0}, "chunks \u4e0b\u754c"),
                 ({"low_vram": "mlp", "chunk_chunks": 65}, "chunks \u4e0a\u754c"),
                 ({"low_vram": "mlp_attn", "chunk_head_chunks": 57}, "head_chunks \u4e0a\u754c"),
                 ({"low_vram": "mlp", "chunk_chunks": "abc"}, "chunks \u975e\u6574\u6570")):
    try:
        graph_of(**bad)
        check("%s \u5e94\u62a5\u9519" % why, False, "\u6ca1\u6709\u62a5\u9519")
    except ValueError as e:
        check("%s \u62a5 ValueError\uff08%s\uff09" % (why, str(e)[:34]), True)

print("\nE. \u6a21\u677f\u6587\u4ef6\u91cc\u4e0d\u542b\u8fd9\u4e24\u4e2a\u8282\u70b9\uff08\u6761\u4ef6\u63d2\u5165\uff0c\u4e0d\u662f\u6539\u6a21\u677f\uff09")
for fn in ("video_minimax_h3_r2v.api.json", "video_minimax_h3_i2v.api.json"):
    t = io.open(os.path.join(ROOT, "workflows", fn), encoding="utf-8").read()
    check("%s \u4e0d\u542b\u5206\u5757\u8282\u70b9" % fn,
          "MiniMaxChunkFeedForward" not in t and "MiniMaxLowVRAMAttention" not in t)

print("\nF. I2VA \u6d41\u7a0b\u540c\u6837\u652f\u6301")
gi = ra.make_graph_i2v(base_cfg(low_vram="mlp_attn", ref_images=["x.png"]))
check("I2VA \u4e5f\u80fd\u63d2\u5165\u4e24\u4e2a\u5206\u5757\u8282\u70b9",
      len(nodes_of_type(gi, "MiniMaxChunkFeedForward")) == 1
      and len(nodes_of_type(gi, "MiniMaxLowVRAMAttention")) == 1)
check("I2VA \u5173\u6389\u65f6\u56fe\u4e0d\u53d8\uff08\u65e0 9001/9002\uff09",
      "9001" not in ra.make_graph_i2v(base_cfg(low_vram="off", ref_images=["x.png"])))

print("\nG. \u914d\u7f6e\u6821\u9a8c\uff08CLI \u8def\u5f84\uff09\uff1aload_config \u62d2\u7edd\u975e\u6cd5\u503c")
sys.path.insert(0, ROOT)
import optimizer as opt  # noqa: E402
tmp = os.path.join(HERE, "_tmp_lowvram_config.json")
for val, why in (("banana", "\u975e\u6cd5\u6863\u4f4d"), ("mlp_attn", "\u5408\u6cd5\u6863\u4f4d\u5e94\u901a\u8fc7")):
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump({"story": "s", "llm_base": "http://x/v1", "llm_model": "m", "low_vram": val}, f)
    try:
        c = opt.load_config(tmp)
        ok = (c.get("low_vram") == val)
        check("load_config \u63a5\u53d7 %s" % val, ok if why.startswith("\u5408\u6cd5") else False, c.get("low_vram"))
    except SystemExit as e:
        check("load_config \u62d2\u7edd %s" % val, why.startswith("\u975e\u6cd5"), str(e)[:60])
os.remove(tmp)

print("\nchecks: %s" % ("ALL PASS" if FAIL == 0 else "%d FAILED" % FAIL))
sys.exit(1 if FAIL else 0)
