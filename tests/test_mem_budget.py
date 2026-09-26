#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\u663e\u5b58/\u65f6\u957f\u9884\u7b97\u4f30\u8ba1\u7684\u9a8c\u8bc1\u3002

\u8fd0\u884c\uff1a python tests/test_mem_budget.py

\u8981\u70b9\uff1atoken \u662f\u7cbe\u786e\u503c\uff08\u53ef\u4e0e\u5b9e\u6d4b/\u65e2\u6709\u8f93\u51fa\u4ea4\u53c9\u9a8c\u8bc1\uff09\uff0c\u5cf0\u503c\u662f\u7ebf\u6027\u8fd1\u4f3c\uff08\u7528\u5305\u7ebf\u8868\u4e09\u70b9\u53cd\u63a8\uff0c
\u5fc5\u987b\u80fd\u8fd8\u539f\u90a3\u4e09\u70b9\uff1b\u5e76\u4e14"\u8d85\u4e86\u5c31\u7ed9\u51fa\u8be5\u964d\u5230\u591a\u5c11"\u7684\u5efa\u8bae\u5fc5\u987b\u81ea\u6d3d\uff09\u3002
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))
import mem_budget as mb        # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "   -> " + str(detail)))
    if not cond:
        fails.append(name)


print("=" * 72)
print("A. \u5e27\u6570 / latent token\uff08\u7cbe\u786e\u503c\uff0c\u53ef\u4e0e\u5b9e\u6d4b\u4ea4\u53c9\u9a8c\u8bc1\uff09")
print("=" * 72)
check("snap_frames(60) == 1450\uff0817k+5 \u5438\u9644\uff09", mb.snap_frames(60) == 1450, mb.snap_frames(60))
check("snap_frames(15) == 362", mb.snap_frames(15) == 362, mb.snap_frames(15))
check("snap_frames(1) == 39\uff08\u7f51\u683c\u4e0b\u9650\uff09", mb.snap_frames(1) == 39, mb.snap_frames(1))
check("latent_t(1450) == 427", mb.latent_t_of(1450) == 427, mb.latent_t_of(1450))
check("latent_t(362) == 107", mb.latent_t_of(362) == 107, mb.latent_t_of(362))

f, lt, tk = mb.tokens_of(60, 1.0)
check("60 \u79d2 @1.0MP \u2192 1450 \u5e27 / 427 token / 417179", (f, lt, tk) == (1450, 427, 417179), (f, lt, tk))
f, lt, tk = mb.tokens_of(30, 0.6)
check("30 \u79d2 @0.6MP \u2192 736 \u5e27 / 127162 token\uff08\u4e0e doctor \u5b9e\u6d4b\u8f93\u51fa\u4e00\u81f4\uff09",
      (f, lt, tk) == (736, 217, 127162), (f, lt, tk))
f, lt, tk = mb.tokens_of(15, 0.6)
check("15 \u79d2 @0.6MP \u2192 362 \u5e27 / 62702 token", (f, lt, tk) == (362, 107, 62702), (f, lt, tk))

print()
print("=" * 72)
print("B. \u7ebf\u6027\u6a21\u578b\u5fc5\u987b\u80fd\u8fd8\u539f\u5305\u7ebf\u8868\u4e09\u70b9\uff0816/24/32 GB \u2194 230k/380k/530k token\uff09")
print("=" * 72)
pts = [{"tokens": 230000, "peak_gb": 16.0},
       {"tokens": 380000, "peak_gb": 24.0},
       {"tokens": 530000, "peak_gb": 32.0}]
fit = mb.fit(pts)
check("\u62df\u5408\u5f97\u5230\u53c2\u6570", fit is not None, fit)
if fit:
    base, kb = fit
    check("base \u2248 3.73 GB\uff08\u00b10.05\uff09", abs(base - 3.73) < 0.05, round(base, 3))
    check("k \u2248 0.0533 GB/1k token\uff08\u00b10.001\uff09", abs(kb - 0.0533) < 0.001, round(kb, 4))
    for p in pts:
        pred = base + kb * p["tokens"] / 1000.0
        check("\u56de\u4ee3 %dk token \u2192 %.1f GB\uff08\u5b9e\u6d4b %.0f\uff09" % (p["tokens"] // 1000, pred, p["peak_gb"]),
              abs(pred - p["peak_gb"]) < 0.15, round(pred, 2))
check("\u6837\u672c\u4e0d\u8db3\u65f6\u4e0d\u62df\u5408\uff08\u8fd4\u56de None\uff09", mb.fit([pts[0]]) is None)

print()
print("=" * 72)
print("C. \u5224\u5b9a\u4e0e\u5efa\u8bae\uff08\u8d85\u4e86\u5fc5\u987b\u7ed9\u51fa\u8be5\u964d\u5230\u591a\u5c11\uff0c\u4e14\u5efa\u8bae\u503c\u81ea\u6d3d\uff09")
print("=" * 72)
e_over = mb.estimate(60, 1.0, card_gb=24)
print("    60s@1.0MP/24GB ->", mb.format_line(e_over))
check("60 \u79d2 @1.0MP/24GB\uff1atoken \u5224\u4e3a over", e_over["token_verdict"] == "over", e_over["token_verdict"])
check("\u5efa\u8bae\u7684\u6700\u5927\u65f6\u957f < 60 \u79d2", 0 < e_over["max_duration_s_at_this_mp"] < 60,
      e_over["max_duration_s_at_this_mp"])
check("\u5efa\u8bae\u7684\u6700\u5927\u753b\u5e45 < 1.0MP", 0 < e_over["max_megapixels_at_this_duration"] < 1.0,
      e_over["max_megapixels_at_this_duration"])
# \u5efa\u8bae\u503c\u672c\u8eab\u5fc5\u987b"\u80fd\u8fc7"\uff1a\u6309\u5efa\u8bae\u91cd\u7b97\u4e0d\u5f97\u518d over
e_tip = mb.estimate(e_over["max_duration_s_at_this_mp"], 1.0, card_gb=24)
check("\u6309\u5efa\u8bae\u65f6\u957f\u91cd\u7b97\u4e0d\u518d over", e_tip["token_verdict"] != "over", (e_tip["duration_s"], e_tip["token_verdict"]))
e_tip2 = mb.estimate(60, e_over["max_megapixels_at_this_duration"], card_gb=24)
check("\u6309\u5efa\u8bae\u753b\u5e45\u91cd\u7b97\u4e0d\u518d over", e_tip2["token_verdict"] != "over", (e_tip2["megapixels"], e_tip2["token_verdict"]))

e_ok = mb.estimate(30, 0.6, card_gb=24)
print("    30s@0.6MP/24GB ->", mb.format_line(e_ok))
check("30 \u79d2 @0.6MP/24GB\uff1atoken \u5728\u5305\u7ebf\u5185", e_ok["token_verdict"] == "ok", e_ok["token_verdict"])
# \u5b89\u5168\u6027\u8d28\uff1a\u6ca1\u6709\u5b9e\u6d4b\u6837\u672c\u65f6**\u4e0d\u80fd**\u7ed9"ok"\uff08\u771f\u5b9e\u5cf0\u503c\u7531\u68c0\u67e5\u70b9\u5e38\u9a7b\u6743\u91cd\u4e3b\u5bfc\uff0c\u5b9e\u6d4b 512\u00b2 \u4e0b
# 30 \u79d2\u4e0e 90 \u79d2\u5cf0\u503c\u90fd\u662f ~23.5 GB\uff0c\u4e0e\u65f6\u957f\u51e0\u4e4e\u65e0\u5173\uff1b\u672a\u6807\u5b9a\u5c31\u7ed9\u7eff\u706f\u4f1a\u8bef\u5bfc\uff09
check("\u672a\u6807\u5b9a\u65f6\u4e0d\u7ed9\u7eff\u706f\uff08peak_verdict=uncalibrated\uff09",
      e_ok["peak_verdict"] == "uncalibrated" and e_ok["lower_bound"] is True,
      (e_ok["peak_verdict"], e_ok["lower_bound"]))
check("\u672a\u6807\u5b9a\u65f6\u63d0\u793a\u91cc\u8bf4\u660e\u662f\u504f\u4f4e\u4f30\u8ba1", "\u504f\u4f4e\u4f30\u8ba1" in e_ok["note"], e_ok["note"][:60])
e_small = mb.estimate(5, 0.3, card_gb=24)
check("5 \u79d2 @0.3MP/24GB\uff1atoken \u5728\u5305\u7ebf\u5185", e_small["token_verdict"] == "ok", e_small["token_verdict"])

# \u6807\u5b9a\u540e\u5fc5\u987b\u7ed9\u51fa\u660e\u786e\u7ed3\u8bba\uff08\u800c\u4e0d\u662f\u6c38\u8fdc uncalibrated\uff09
e_cal_over = mb.estimate(60, 1.0, card_gb=24, samples=pts)
e_cal_ok = mb.estimate(10, 0.3, card_gb=24, samples=pts)
check("\u6807\u5b9a\u540e 60s@1.0MP \u5224 over", e_cal_over["peak_verdict"] == "over", e_cal_over["peak_verdict"])
check("\u6807\u5b9a\u540e 10s@0.3MP \u5224 ok", e_cal_ok["peak_verdict"] == "ok", e_cal_ok["peak_verdict"])

print()
print("=" * 72)
print("D. \u5355\u8c03\u6027\u4e0e\u6a21\u578b\u4f53\u79ef\u88d5\u91cf")
print("=" * 72)
toks = [mb.tokens_of(d, 0.6)[2] for d in (5, 15, 30, 60)]
check("token \u968f\u957f\u5ea6\u5355\u8c03\u9012\u589e", all(a < b for a, b in zip(toks, toks[1:])), toks)
toks_mp = [mb.tokens_of(30, mp)[2] for mp in (0.4, 0.6, 0.8, 1.0)]
check("token \u968f\u753b\u5e45\u5355\u8c03\u9012\u589e", all(a < b for a, b in zip(toks_mp, toks_mp[1:])), toks_mp)
e_m = mb.estimate(60, 1.0, card_gb=24, model="x_w4a8_14gb.safetensors", model_gb=14)
check("\u7ed9\u51fa\u6a21\u578b\u6863\u6848\uff08W4A8 / 14 GB / \u5e38\u9a7b 14 GB\uff09",
      e_m["model_profile"]["format"] == "W4A8" and e_m["model_profile"]["size_gb"] == 14
      and e_m["model_profile"]["resident_gb"] == 14.0, e_m["model_profile"])
check("\u533a\u95f4\u4e0d\u5012\u7f6e\u4e14\u4e0a\u9650\u4e0d\u8d85\u8fc7\u663e\u5361",
      e_m["est_peak_lo_gb"] <= e_m["est_peak_gb"] <= 24, e_m["peak_range_gb"])
check("token \u672c\u8eab\u8d85\u5305\u7ebf\u65f6\u5224 over\uff08\u4e0e\u662f\u5426\u6709\u6a21\u578b\u6863\u6848\u65e0\u5173\uff09", e_m["peak_verdict"] == "over", e_m["peak_verdict"])
# \u771f\u5b9e\u573a\u666f\u4e0b\u7684 offload\uff1a19.53GB int8 \u6a21\u578b\u300160s@0.6MP\u300123.9GB \u5361 \u2192 token \u5728\u5305\u7ebf\u5185\u4f46\u6743\u91cd\u5e38\u9a7b\u4f1a\u8d34\u9876
e_off = mb.estimate(60, 0.6, card_gb=23.9, model="MiniMax H3\\h3_int8.safetensors", model_gb=19.53)
check("\u6743\u91cd\u5e38\u9a7b\u8d34\u9876\u65f6\u5224 offload\uff08\u80fd\u8dd1\u4f46\u66f4\u6162\uff09", e_off["peak_verdict"] == "offload",
      (e_off["peak_verdict"], e_off["peak_range_gb"], e_off["note"][:40]))
check("offload \u63d0\u793a\u8bf4\u660e\u4f1a\u9760\u5378\u8f7d\u786c\u6491", "\u5378\u8f7d" in e_off["note"], e_off["note"][:60])
e_fit = mb.estimate(60, 1.0, card_gb=24, samples=pts)
check("\u6709\u5b9e\u6d4b\u6837\u672c\u65f6\u6539\u7528\u5b9e\u6d4b\u62df\u5408", e_fit["fitted_from_samples"] == 3 and "\u5b9e\u6d4b\u62df\u5408" in e_fit["source"],
      e_fit["source"])

print()
print("=" * 72)
print("D2. \u6a21\u578b\u6863\u6848\uff1a\u4ece\u540d\u5b57\u8bfb\u6743\u91cd\u683c\u5f0f\uff08\u4e00\u822c\u4eba\u4e0d\u6539\u4e0b\u8f7d\u6765\u7684\u540d\u5b57\uff09")
print("=" * 72)
cases = [
    ("MiniMax H3\\minimax_h3_hybrid_fl2va_ref2va_b20-49-int8.safetensors", "INT8", False),
    ("10Eros_Max_h3_hybrid_beta5_w4a8_14gb_optimized.safetensors", "W4A8", False),
    ("MiniMax-H3-ref2va-pruned-zs05-comfy-nvfp4.safetensors", "NVFP4", False),
    ("MiniMax-H3-ref2va-curve-zs05-Q5_1.gguf", "GGUF", True),
    ("ltx-2.5-22b-distilled-transformer_nvfp4_convrot_int8.safetensors", "NVFP4", False),
]
for name, want_fmt, want_deq in cases:
    pr = mb.parse_model_profile(name)
    check("%-46s \u2192 %s" % (name[-46:], want_fmt), pr["format"] == want_fmt, pr["format"])
    check("   \u9700\u53cd\u91cf\u5316\u6807\u8bb0 == %s" % want_deq, pr["needs_dequant"] == want_deq, pr["needs_dequant"])
pr = mb.parse_model_profile("10Eros_Max_h3_hybrid_beta5_w4a8_14gb_optimized.safetensors")
check("\u80fd\u4ece\u6587\u4ef6\u540d\u8bfb\u51fa\u4f53\u79ef\uff0814gb\uff09", pr["size_gb"] == 14.0 and pr["size_source"] == "name",
      (pr["size_gb"], pr["size_source"]))
pr = mb.parse_model_profile("MiniMax-H3-ref2va-curve-zs05-Q5_1.gguf")
check("GGUF \u7684\u5907\u6ce8\u8bf4\u660e\u9700\u53cd\u91cf\u5316\u4e0e weight_dtype \u65e0\u6548",
      any("\u53cd\u91cf\u5316" in n for n in pr["notes"]) and any("weight_dtype" in n for n in pr["notes"]),
      pr["notes"])
pr = mb.parse_model_profile("MiniMax H3\\minimax_h3_hybrid_fl2va_ref2va_b20-49-int8.safetensors")
check("\u90e8\u5206 block \u91cf\u5316\u4f1a\u88ab\u6ce8\u660e", any("\u90e8\u5206 block" in n for n in pr["notes"]), pr["notes"])
check("hybrid \u4f1a\u88ab\u6807\u6ce8\u4e3a\u6df7\u5408\u7cbe\u5ea6\uff08\u5b9e\u6d4b\u65e5\u5fd7\u8bc1\u5b9e\u662f\u591a\u91cf\u5316\u6df7\u7528\uff09",
      any("\u6df7\u5408\u7cbe\u5ea6\u6a21\u578b" in n for n in pr["notes"]), pr["notes"])
pr = mb.parse_model_profile("some_unknown_model.safetensors")
check("\u8bfb\u4e0d\u51fa\u683c\u5f0f\u65f6\u6807\u4e3a\u672a\u77e5\u4e14\u4e0d\u7f16\u9020\u4f53\u79ef", pr["format"] == "\u672a\u77e5" and pr["size_gb"] is None, pr)

print()
print("=" * 72)
print("D3. \u6587\u672c\u7f16\u7801\u5668\uff08TE\uff09\uff1a\u5b9e\u6d4b\u65e5\u5fd7\u663e\u793a\u5b83\u7684 staged \u4f53\u79ef\u6bd4 DiT \u8fd8\u5927\uff0825 GB vs 20 GB\uff09")
print("=" * 72)
e_te = mb.estimate(30, 0.6, card_gb=24, model="h3_int8.safetensors", model_gb=19.53,
                   clip="qwen3vl_32b_minimax_h3_ultra_uncensored_heretic_int8_convrot.safetensors", clip_gb=24.55)
check("\u8fd4\u56de clip_profile", bool(e_te.get("clip_profile")), e_te.get("clip_profile"))
_te_txt = (e_te.get("clip_profile") or {}).get("text", "")
check("TE \u63d0\u793a\u5199\u660e\u4e0e DiT \u5206\u5f00\u52a0\u8f7d", "\u5206\u5f00" in _te_txt, _te_txt)
check("TE \u63d0\u793a\u5199\u660e\u53ef\u80fd\u6bd4 DiT \u8fd8\u5927", "\u6bd4 DiT \u8fd8\u5927" in _te_txt, _te_txt)
check("TE \u63d0\u793a\u5199\u660e\u7f16\u7801\u5b8c\u6210\u540e\u5378\u8f7d", "\u5378\u8f7d" in _te_txt, _te_txt)
check("TE \u63d0\u793a\u4e0d\u518d\u58f0\u79f0'\u52a0\u8f7d\u540e\u88ab\u653e\u5927'", "\u8ba1\u7b97\u7cbe\u5ea6" not in _te_txt, _te_txt)
e_note = mb.estimate(30, 0.6, card_gb=24)
check("\u672a\u7ed9 clip \u65f6\u4e0d\u4ea7\u751f clip_profile", e_note.get("clip_profile") is None, e_note.get("clip_profile"))

print()
print("=" * 72)
print("D4. \u9762\u5411\u7528\u6237\u7684\u8bf4\u6cd5\uff1a\u53ea\u7ed9\u7ed3\u8bba + \u4e00\u53e5\u539f\u56e0 + \u5173\u952e\u6570\u5b57\uff08\u6280\u672f\u7ec6\u8282\u53e6\u5b58\uff09")
print("=" * 72)
u_over = mb.user_line(e_over)
u_off = mb.user_line(e_off)
u_unk = mb.user_line(mb.estimate(30, 0.6, card_gb=24))
u_ok = mb.user_line(mb.estimate(15, 0.6, card_gb=24, model="h3_int8.safetensors", model_gb=11.67))
for nm, u in (("\u8d85\u5305\u7ebf", u_over), ("\u8d34\u9876", u_off), ("\u4f30\u4e0d\u51c6", u_unk), ("\u53ef\u4ee5\u8dd1", u_ok)):
    check("user_line(%s) = %s" % (nm, u["verdict"]), bool(u["verdict"] and u["reason"]), u)
    check("    %s \u7684\u539f\u56e0\u662f\u4e00\u53e5\u4eba\u8bdd\uff08\u65e0 token/\u5305\u7ebf\u7b49\u672f\u8bed\uff09" % nm,
          ("token" not in u["reason"]) and ("\u5305\u7ebf" not in u["reason"]), u["reason"])
check("\u8d85\u5305\u7ebf\u65f6\u7ed9\u51fa\u53ef\u6267\u884c\u5efa\u8bae", "\u5efa\u8bae\uff1a" in (u_over.get("advice") or ""), u_over.get("advice"))
check("\u6570\u5b57\u884c\u542b\u9884\u6d4b\u5cf0\u503c\u4e0e\u5e27\u6570", "\u9884\u6d4b\u5cf0\u503c" in u_over["numbers"] and "\u5e27" in u_over["numbers"], u_over["numbers"])
check("user_text \u5355\u884c\u7248\u542b\u7ed3\u8bba\u4e0e\u539f\u56e0", "\u2014\u2014" in mb.user_text(e_over) and "\u9884\u6d4b\u5cf0\u503c" in mb.user_text(e_over),
      mb.user_text(e_over))

print()
print("=" * 72)
print("E0. \u4e94\u6bb5\u5f0f\u8f93\u51fa\u4e0e\u4e09\u6863\u5224\u5b9a\uff08DiT / TE / Token / \u5378\u8f7dTE\u540e\u5360\u7528 / \u9884\u8ba1\u4f7f\u7528\u6548\u679c\uff09")
print("=" * 72)
WANT = ["\u9884\u4f30\u6a21\u578b\uff08DiT\uff09\u5360\u7528\u91cf", "\u6587\u672c\u7f16\u7801\u5668\uff08Text Encoder\uff09\u5360\u7528\u91cf", "\u6765\u81ea Token \u7684\u5360\u7528\u91cf",
        "\u6587\u672c\u7f16\u7801\u5668\u5728\u6e32\u67d3\u9636\u6bb5", "\u6b63\u786e\u5378\u8f7d\u540e\u9884\u4f30\u663e\u5b58\u5360\u7528"]
b_perfect = mb.budget_lines(mb.estimate(15, 0.3, card_gb=24, model="small.safetensors", model_gb=5),
                            ram_free_gb=50, ram_total_gb=64)
b_slow = mb.budget_lines(mb.estimate(60, 0.6, card_gb=23.9, model="h3_int8.safetensors", model_gb=19.53,
                                     clip="te.safetensors", clip_gb=24.55),
                         ram_free_gb=53.7, ram_total_gb=111)
b_tight_ram = mb.budget_lines(mb.estimate(60, 0.6, card_gb=23.9, model="h3_int8.safetensors", model_gb=19.53,
                                          clip="te.safetensors", clip_gb=24.55),
                              ram_free_gb=40, ram_total_gb=64)
b_dead = mb.budget_lines(mb.estimate(60, 0.6, card_gb=23.9, model="h3_int8.safetensors", model_gb=19.53,
                                     clip="te.safetensors", clip_gb=24.55),
                         ram_free_gb=20, ram_total_gb=64)
b_unknown = mb.budget_lines(mb.estimate(30, 0.6, card_gb=24), ram_free_gb=50)

check("\u4e94\u6bb5\u5f0f\u6807\u7b7e\u4e0e\u8981\u6c42\u4e00\u81f4", [x["label"] for x in b_slow["lines"]][:5] == WANT,
      [x["label"] for x in b_slow["lines"]])
check("\u7b2c 4 \u884c\u5199\u660e\u300c\u6743\u91cd\u7559\u5728\u5185\u5b58\uff08\u4e0d\u91ca\u653e\uff09\u300d\uff08\u5df2\u6838 ComfyUI \u6e90\u7801\uff09",
      any(x["label"] == "\u6587\u672c\u7f16\u7801\u5668\u5728\u6e32\u67d3\u9636\u6bb5" and "\u7559\u5728\u5185\u5b58" in x["value"] for x in b_slow["lines"]),
      [x["value"] for x in b_slow["lines"] if x["label"] == "\u6587\u672c\u7f16\u7801\u5668\u5728\u6e32\u67d3\u9636\u6bb5"])
check("\u7b2c 5 \u884c = DiT + Token\uff08%.1f\uff09" % b_slow["need_gb"], abs(b_slow["need_gb"] - (19.6 + 13.3)) < 0.5,
      b_slow["need_gb"])
check("\u4e09\u8005\u5168\u91cf\u7ed9\u51fa\u4e14 > \u91c7\u6837\u9700\u6c42", b_slow["total_three_gb"] > b_slow["need_gb"],
      (b_slow["total_three_gb"], b_slow["need_gb"]))
# \u5173\u952e\u4fee\u6b63\uff1a\u6c60 = \u53ef\u7528\u663e\u5b58 + (\u7a7a\u95f2\u5185\u5b58 \u2212 TE \u2212 \u7cfb\u7edf\u9884\u7559)\uff0c\u56e0\u4e3a TE \u5378\u8f7d\u540e\u4ecd\u5360\u5185\u5b58
check("\u53ef\u7528\u603b\u91cf\u6263\u9664\u4e86 TE \u4e0e\u7cfb\u7edf\u9884\u7559\uff08%.1f = %.1f + (%.1f \u2212 %.1f \u2212 %.1f)\uff09"
      % (b_slow["pool_gb"], b_slow["usable_gb"], 53.7, 24.55, mb.OS_RAM_RESERVE_GB),
      abs(b_slow["pool_gb"] - (b_slow["usable_gb"] + 53.7 - 24.55 - mb.OS_RAM_RESERVE_GB)) < 0.3,
      (b_slow["pool_gb"], b_slow["ram_for_offload_gb"]))
check("\u53ef\u7528\u603b\u91cf\u884c\u4f1a\u663e\u793a\u663e\u5b58/\u5185\u5b58\u62c6\u5206\u4e0e\u7cfb\u7edf\u9884\u7559",
      any(x["label"] == "\u6e32\u67d3\u9636\u6bb5\u53ef\u7528\u603b\u91cf" and "\u5185\u5b58\u53ef\u7528" in x["value"] and "\u9884\u7559" in x["value"]
          for x in b_slow["lines"]),
      b_slow["lines"][-1])
# \u62ec\u53f7\u91cc\u7684\u6bcf\u4e2a\u6570\u5b57\u90fd\u8981\u5e26\u5355\u4f4d\uff1a\u66fe\u6f0f\u6210"\uff08\u663e\u5b58 23.2 + \u5185\u5b58\u53ef\u7528 25.2\uff0c\u5df2\u9884\u7559 4 \u7ed9\u7cfb\u7edf\uff09"
_u = [x["value"] for x in b_slow["lines"] if x["label"] == "\u6e32\u67d3\u9636\u6bb5\u53ef\u7528\u603b\u91cf"][0]
check("\u53ef\u7528\u603b\u91cf\u62ec\u53f7\u5185\u6bcf\u4e2a\u6570\u503c\u90fd\u5e26 GiB\uff08\u663e\u5b58/\u5185\u5b58/\u9884\u7559\uff09",
      "GiB\uff08\u663e\u5b58" in _u and "GiB + \u5185\u5b58\u53ef\u7528" in _u and "GiB \u7ed9\u7cfb\u7edf" in _u
      and "GiB\uff08\u663e\u5b58" in _u and _u.count("GiB") == 4, _u)
check("\u2460 \u5b8c\u7f8e\uff08DiT+Token \u5728\u663e\u5b58\u5185\uff09", b_perfect["effect"] == "\u5b8c\u7f8e", b_perfect["effect"])
check("\u2461 \u80fd\u7528\u4f46\u4f1a\u6162\uff08\u8d85\u663e\u5b58\u4f46\u53ef\u7528\u603b\u91cf\u591f\uff09", b_slow["effect"] == "\u80fd\u7528\u4f46\u4f1a\u6162", b_slow["effect"])
check("\u2462 \u4e0d\u53ef\u7528\uff08\u5185\u5b58\u88ab TE \u5360\u6ee1\u3001\u6ca1\u6709\u4f59\u91cf\u53ef\u5378\u8f7d\uff09", b_dead["effect"] == "\u4e0d\u53ef\u7528",
      (b_dead["effect"], b_dead["pool_gb"], b_dead["need_gb"]))
check("\u300c\u4e0d\u53ef\u7528\u300d\u7684\u7406\u7531\u70b9\u660e swap \u4f1a\u6781\u6162\u4e14\u78e8\u635f SSD\uff08\u529d\u9000\u800c\u4e0d\u662f\u7559\u60ac\u5ff5\uff09",
      "swap" in b_dead["why"] and "SSD" in b_dead["why"], b_dead["why"])
check("\u672a\u9009\u6a21\u578b \u2192 \u8fd8\u4f30\u4e0d\u51c6", b_unknown["effect"] == "\u8fd8\u4f30\u4e0d\u51c6\uff0c\u5148\u8dd1\u4e00\u6863", b_unknown["effect"])
# \u4e09\u8005\u5168\u91cf\u88c5\u4e0d\u4e0b\u3001\u4f46"TE \u5378\u8f7d\u540e"\u7684\u91c7\u6837\u96c6\u88c5\u5f97\u4e0b\u65f6\uff0c\u4ecd\u5224\u80fd\u7528\u4f46\u4f1a\u6162\uff08\u4e0d\u7ed9\u5047\u4e0d\u53ef\u7528\uff09
check("\u4e09\u8005\u5168\u91cf\u8d85\u53ef\u7528\u603b\u91cf\u4f46\u91c7\u6837\u96c6\u88c5\u5f97\u4e0b \u2192 \u4ecd\u5224\u300c\u80fd\u7528\u4f46\u4f1a\u6162\u300d",
      b_tight_ram["effect"] == "\u80fd\u7528\u4f46\u4f1a\u6162" and b_tight_ram["total_three_gb"] > b_tight_ram["pool_gb"],
      (b_tight_ram["effect"], b_tight_ram["total_three_gb"], b_tight_ram["pool_gb"]))
check("\u8be5\u60c5\u5f62\u7684\u8bf4\u660e\u70b9\u51fa TE \u662f\u4ece\u663e\u5b58\u5378\u8f7d\u7684", "\u4ece\u663e\u5b58\u5378\u8f7d" in b_tight_ram["why"], b_tight_ram["why"])
b_meas = mb.budget_lines(mb.estimate(60, 0.6, card_gb=23.9, model="h3_int8.safetensors", model_gb=19.53,
                                     clip="te.safetensors", clip_gb=24.55),
                         ram_free_gb=53.7, measured_ram_gb=35.0)
check("\u80fd\u5e26\u4e0a\u5b9e\u6d4b\u5185\u5b58\u5360\u7528\uff08\u9a8c\u8bc1 TE \u5360\u4e86\u591a\u5c11\u5185\u5b58\uff09",
      any("\u5b9e\u6d4b\u6e32\u67d3\u671f\u5185\u5b58\u989d\u5916\u5360\u7528 35.0" in x["value"] for x in b_meas["lines"]),
      [x["value"] for x in b_meas["lines"] if x["label"] == "\u6587\u672c\u7f16\u7801\u5668\u5728\u6e32\u67d3\u9636\u6bb5"])
check("budget_text \u5355\u884c\u7248\u542b\u4e94\u884c\u4e0e\u6548\u679c",
      all(k in mb.budget_text(b_slow, 53.7, 111) for k in WANT[:1] + ["\u9884\u8ba1\u4f7f\u7528\u6548\u679c\uff1a\u80fd\u7528\u4f46\u4f1a\u6162"]),
      mb.budget_text(b_slow, 53.7, 111)[:140])

print()
print("=" * 72)
print("E. \u547d\u4ee4\u884c\u5165\u53e3")
print("=" * 72)
r = subprocess.run([sys.executable, os.path.join(ROOT, "core", "mem_budget.py"),
                    "--duration", "60", "--megapixels", "1.0", "--card", "24"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
check("CLI \u9000\u51fa\u7801 0", r.returncode == 0, r.stderr[:200])
check("CLI \u8f93\u51fa\u542b\u5224\u5b9a\u4e0e\u5efa\u8bae", "over" in (r.stdout or "") and "\u5efa\u8bae" in (r.stdout or ""), r.stdout[:200])

print()
print("=" * 72)
print("F. \u5b9e\u6d4b\u6807\u5b9a\u94fe\u8def\uff08\u663e\u5b58\u91c7\u6837 \u2192 \u5386\u53f2\u6837\u672c \u2192 \u6539\u7528\u5b9e\u6d4b\u62df\u5408\uff09")
print("=" * 72)
tmp = tempfile.mkdtemp(prefix="h3_samples_")
try:
    import json as _json
    import server as srv
    for job, tokens, peaks in (("j1", 100000, [12.5, 13.0]), ("j2", 300000, [20.0])):
        d = os.path.join(tmp, job)
        os.makedirs(d)
        with open(os.path.join(d, "optimizer_history.json"), "w", encoding="utf-8") as fh:
            _json.dump({"run": {"model": "m1", "tokens": tokens},
                        "attempts": [{"label": "a%d" % i, "vram_peak_gb": p} for i, p in enumerate(peaks)]}, fh)
    srv.OUTPUT_DIR = tmp                          # \u53ea\u5728\u6d4b\u8bd5\u91cc\u6539\u6307\u5411\uff0c\u4e0d\u78b0\u771f\u5b9e outputs/
    s = srv._mem_samples("m1")
    check("_mem_samples \u6536\u96c6\u5230\u5b9e\u6d4b\u6837\u672c\uff083 \u4e2a\uff09", len(s) == 3, s)
    check("_mem_samples \u6309\u6a21\u578b\u8fc7\u6ee4", srv._mem_samples("other") == [], srv._mem_samples("other"))
    e_cal = mb.estimate(60, 1.0, card_gb=24, samples=s)
    check("\u6709\u5b9e\u6d4b\u6837\u672c\u540e\u8f6c\u4e3a\u5df2\u6807\u5b9a\uff08\u4e0d\u518d\u662f uncalibrated\uff09",
          e_cal["fitted_from_samples"] == 3 and e_cal["peak_verdict"] in ("ok", "tight", "over"),
          (e_cal["fitted_from_samples"], e_cal["peak_verdict"]))
    check("\u6807\u5b9a\u540e\u4e0d\u518d\u6807\u8bb0\u4e3a\u504f\u4f4e\u4f30\u8ba1", e_cal["lower_bound"] is False, e_cal["lower_bound"])

    # \u504f\u5dee\u6838\u5bf9\u95ed\u73af\uff1a_collect_rounds \u5fc5\u987b\u5e26\u51fa run\uff08\u542b budget_pred\uff09\uff0c\u5426\u5219\u524d\u7aef\u7b97\u4e0d\u51fa"\u9884\u6d4b vs \u5b9e\u6d4b"
    hp = os.path.join(tmp, "j1", "optimizer_history.json")
    with open(hp, encoding="utf-8") as fh:
        h = _json.load(fh)
    h["run"]["budget_pred"] = {"est_peak_gb": 20.0, "est_peak_lo_gb": 8.0, "peak_verdict": "offload"}
    with open(hp, "w", encoding="utf-8") as fh:
        _json.dump(h, fh, ensure_ascii=False)
    rr = srv._collect_rounds({"id": "j1", "outdir": os.path.join(tmp, "j1")})
    check("_collect_rounds \u5e26\u51fa run.budget_pred\uff08\u4f9b\u504f\u5dee\u53cd\u9988\uff09",
          bool(rr.get("ready")) and (rr.get("run") or {}).get("budget_pred", {}).get("est_peak_gb") == 20.0,
          (rr.get("run") or {}).get("budget_pred"))
    check("_collect_rounds \u5e26\u51fa\u6bcf\u8f6e\u5b9e\u6d4b\u5cf0\u503c",
          any(r.get("vram_peak_gb") for r in rr.get("rounds") or []),
          [r.get("vram_peak_gb") for r in rr.get("rounds") or []])
except Exception as e:
    check("\u6807\u5b9a\u94fe\u8def\u53ef\u5bfc\u5165\u5e76\u8fd0\u884c", False, "%s: %s" % (type(e).__name__, e))

# \u663e\u5b58\u91c7\u6837\u5668\uff1a\u9700\u8981 ComfyUI \u5728\u7ebf\uff0c\u4e0d\u5728\u7ebf\u5c31\u8df3\u8fc7\uff08\u5b83\u8f6e\u8be2\u7684\u662f ComfyUI \u7684 /system_stats\uff09
try:
    import time as _time
    import optimizer as opt
    with opt._VramWatch("http://127.0.0.1:8000", interval=0.5) as vw:
        _time.sleep(3)
    if vw.total_gb:
        check("_VramWatch \u53d6\u5230\u663e\u5361\u603b\u663e\u5b58\uff08%.1f GB\uff09" % vw.total_gb, vw.total_gb > 1, vw.total_gb)
        check("_VramWatch \u91c7\u5230\u5cf0\u503c\uff08%s\uff09" % vw.peak_gb, vw.peak_gb is not None, vw.peak_gb)
        check("_VramWatch \u6709\u91c7\u6837\u6b21\u6570\uff08%d\uff09" % vw.samples, vw.samples >= 1, vw.samples)
    else:
        print("SKIP  _VramWatch \u5b9e\u6d4b\u53d6\u6837\uff08ComfyUI \u672a\u8fd0\u884c\uff09")
except Exception as e:
    print("SKIP  _VramWatch \u5b9e\u6d4b\u53d6\u6837\uff08%s\uff09" % type(e).__name__)

print()
print("checks:", "ALL PASS" if not fails else "%d FAILED" % len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
