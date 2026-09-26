#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\u73af\u5883\u81ea\u68c0\uff08doctor\uff09\uff1a\u8dd1\u957f\u4efb\u52a1\u4e4b\u524d\uff0c\u628a"\u80fd\u4e0d\u80fd\u8dd1\u3001\u4f1a\u4e0d\u4f1a\u8d85\u5305\u7ebf"\u4e00\u6b21\u67e5\u6e05\u3002

\u4e3a\u4ec0\u4e48\u503c\u5f97\u505a
------------
\u957f\u89c6\u9891\u4e00\u6b21\u6e32\u67d3 8\u201316 \u5206\u949f\uff0c\u8dd1\u5230\u4e00\u534a\u624d\u53d1\u73b0"\u8282\u70b9\u6ca1\u88c5/\u6a21\u578b\u540d\u4e0d\u5bf9/\u663e\u5b58\u4e0d\u591f"\u4ee3\u4ef7\u5f88\u5927\u3002
\u672c\u6a21\u5757\u628a\u6240\u6709\u524d\u7f6e\u6761\u4ef6\u53d8\u6210**\u53ef\u5224\u5b9a\u7684\u68c0\u67e5\u9879**\uff0c\u6bcf\u9879\u90fd\u7ed9\u51fa `ok / warn / error` \u4e0e
**\u53ef\u76f4\u63a5\u7167\u505a\u7684\u8bf4\u660e**\uff0c\u800c\u4e0d\u662f\u6253\u5370\u4e00\u53e5"\u5931\u8d25"\u3002

\u8bbe\u8ba1\u8981\u70b9
--------
* **\u6240\u9700\u8282\u70b9\u4ece\u5de5\u4f5c\u6d41\u6a21\u677f\u73b0\u8bfb**\uff08`workflows/*.api.json` \u91cc\u7684 class_type \u96c6\u5408\uff09\uff0c
  \u4e0d\u786c\u7f16\u7801\u6e05\u5355\u2014\u2014\u6a21\u677f\u6539\u4e86\u3001\u81ea\u68c0\u81ea\u52a8\u8ddf\u7740\u6539\uff0c\u4e0d\u4f1a\u6f02\u3002\u8fd9\u4e00\u70b9\u662f\u6709\u6559\u8bad\u7684\uff1a\u53c2\u8003\u9879\u76ee
  \u66fe\u56e0\u8282\u70b9\u7c7b\u540d\u5199\u9519\u5bfc\u81f4 sampler/scheduler \u5217\u8868\u5168\u4e3a 0\uff0c\u800c\u6ca1\u4eba\u5bdf\u89c9\u3002
* **\u53ea\u7b54"\u73af\u5883\u672c\u8eab"**\uff1a\u88c5\u6ca1\u88c5\u3001\u8fde\u4e0d\u8fde\u5f97\u4e0a\u3001\u540d\u5b57\u5bf9\u4e0d\u5bf9\u3002\u4e24\u7c7b\u8bdd**\u4e0d\u5728\u8fd9\u91cc\u8bf4**\u2014\u2014
  \u2460\u300c\u5360\u591a\u5c11\u663e\u5b58\u300d\u7684\u9884\u7b97\u4e0e\u6587\u672c\u7f16\u7801\u5668\u4f53\u79ef\uff1a\u90a3\u662f\u9875\u9762\u4e0a\u72ec\u7acb\u7684\u300c\u663e\u5b58\u9884\u7b97\u4f30\u8ba1\u300d\u6309\u94ae
  \uff08`/api/budget`\uff0c\u540c\u4e00\u4efd `core/mem_budget.py`\uff09\uff1b\u2461\u300c\u4f1a\u8d70\u54ea\u4e2a\u751f\u6210\u5206\u652f\u300d\uff1a\u90a3\u662f\u540e\u53f0\u6309
  \u65f6\u957f\u81ea\u52a8\u9009\u7684\u7b56\u7565\uff08`core/ref2va_auto.py`\uff09\uff0c\u524d\u7aef\u4e0d\u5fc5\u4f53\u73b0\uff0c\u8fd0\u884c\u65f6\u65e5\u5fd7\u91cc\u6709\u3002
* **\u7edd\u4e0d\u629b\u5f02\u5e38**\uff1a\u4efb\u4f55\u4e00\u9879\u67e5\u4e0d\u52a8\u5c31\u9000\u5316\u6210 error \u9879\uff0c\u81ea\u68c0\u672c\u8eab\u4e0d\u80fd\u6210\u4e3a\u65b0\u7684\u6545\u969c\u70b9\u3002
"""
import io
import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKFLOWS = os.path.join(ROOT, "workflows")


def _get_json(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def _ck(cid, label, level, detail):
    return {"id": cid, "label": label, "level": level, "detail": detail}


def required_nodes():
    """\u4e24\u4e2a\u6a21\u677f\u91cc\u51fa\u73b0\u8fc7\u7684\u5168\u90e8 class_type\uff08\u73b0\u8bfb\uff0c\u4e0d\u786c\u7f16\u7801\uff09\u3002"""
    out = set()
    try:
        for fn in sorted(os.listdir(WORKFLOWS)):
            if not fn.endswith(".json"):
                continue
            g = json.load(io.open(os.path.join(WORKFLOWS, fn), encoding="utf-8"))
            for node in g.values():
                if isinstance(node, dict) and node.get("class_type"):
                    out.add(node["class_type"])
    except Exception:
        pass
    return out


def check_comfy(base, classes):
    """ComfyUI \u53ef\u8fbe\u6027 + \u8282\u70b9\u9f50\u5907 + \u6a21\u578b\u5217\u8868\u3002\u8fd4\u56de (checks, object_info \u53ef\u7528\u4e0e\u5426, models, card_gb)\u3002"""
    checks, models = [], {}
    card_gb = None
    try:
        st = _get_json(base.rstrip("/") + "/system_stats", timeout=8)
        dev = (st.get("devices") or [{}])[0]
        sysinfo = st.get("system") or {}
        if dev.get("vram_total"):
            card_gb = round(float(dev["vram_total"]) / 2 ** 30, 1)
        ram_free = round(float(sysinfo["ram_free"]) / 2 ** 30, 1) if sysinfo.get("ram_free") else None
        ram_total = round(float(sysinfo["ram_total"]) / 2 ** 30, 1) if sysinfo.get("ram_total") else None
        checks.append(_ck("comfy", "ComfyUI \u53ef\u8fbe", "ok",
                          "%s \u00b7 vram %.1f/%.1f GB \u7a7a\u95f2 \u00b7 \u5185\u5b58 %.1f/%.1f GB \u7a7a\u95f2 \u00b7 comfy %s / torch %s" % (
                              dev.get("name", "?"),
                              dev.get("vram_free", 0) / 2**30, dev.get("vram_total", 0) / 2**30,
                              (sysinfo.get("ram_free") or 0) / 2**30, (sysinfo.get("ram_total") or 0) / 2**30,
                              sysinfo.get("comfyui_version", "?"), sysinfo.get("pytorch_version", "?"))))
    except Exception as e:
        checks.append(_ck("comfy", "ComfyUI \u53ef\u8fbe", "error",
                          "\u8fde\u4e0d\u4e0a %s\uff08%s\uff09\u3002\u5148\u542f\u52a8 ComfyUI\uff0c\u5e76\u786e\u8ba4\u5730\u5740/\u7aef\u53e3\u6b63\u786e\u3002" % (base, type(e).__name__)))
        return checks, False, models, None, None, None

    missing = []
    for c in sorted(classes):
        try:
            _get_json(base.rstrip("/") + "/object_info/" + urllib.parse.quote(c), timeout=15)
        except Exception:
            missing.append(c)
    if missing:
        checks.append(_ck("nodes", "\u6a21\u677f\u6240\u9700\u8282\u70b9\uff08%d \u4e2a\uff09" % len(classes), "error",
                          "\u7f3a\u5c11 %d \u4e2a\uff1a%s\u3002\u88c5\u9f50\u5bf9\u5e94\u81ea\u5b9a\u4e49\u8282\u70b9\u540e\u91cd\u8bd5\u3002" % (len(missing), "\u3001".join(missing))))
    else:
        checks.append(_ck("nodes", "\u6a21\u677f\u6240\u9700\u8282\u70b9\uff08%d \u4e2a\uff09" % len(classes), "ok",
                          "\u5168\u90e8\u5b58\u5728\uff08\u542b MiniMax H3 \u4e0e SageAttention \u76f8\u5173\u8282\u70b9\uff09"))

    # \u53ef\u9009/\u8fdb\u9636\u8282\u70b9\uff1a\u7f3a\u4e86\u4e0d\u5f71\u54cd\u57fa\u672c\u6d41\u7a0b\uff0c\u4f46\u5f71\u54cd\u5bf9\u5e94\u529f\u80fd
    optional = {
        "UnetLoaderGGUF": "\u7528 GGUF \u91cf\u5316\u6743\u91cd",
        "VHS_LoadVideo": "Ref2VA \u7684 B \u65b9\u5f0f\uff08\u89c6\u9891\u7f16\u8f91\uff09",
        "MiniMaxH3AddGuide": "\u5728\u4efb\u610f\u5e27\u951a\u5b9a\u56fe\u50cf/\u97f3\u9891\uff08\u957f\u89c6\u9891\u5206\u6bb5\u8854\u63a5\u4f1a\u7528\u5230\uff09",
    }
    for cls, why in optional.items():
        try:
            _get_json(base.rstrip("/") + "/object_info/" + urllib.parse.quote(cls), timeout=10)
        except Exception:
            checks.append(_ck("opt_" + cls, "\u53ef\u9009\u8282\u70b9 %s" % cls, "warn",
                              "\u672a\u5b89\u88c5 \u2192 \u65e0\u6cd5%s\u3002\u9700\u8981\u65f6\u518d\u88c5\u3002" % why))

    for cls, key in (("UNETLoader", "unet"), ("UnetLoaderGGUF", "unet_gguf"),
                     ("CLIPLoader", "clip"), ("VAELoader", "vae"), ("LoraLoaderModelOnly", "lora")):
        try:
            oi = _get_json(base.rstrip("/") + "/object_info/" + cls, timeout=20)
            req = ((oi.get(cls) or {}).get("input") or {}).get("required") or {}
            names = []
            for field in ("unet_name", "clip_name", "vae_name", "lora_name"):
                v = req.get(field)
                if v and isinstance(v[0], list):
                    names = v[0]
                    break
            models[key] = names
        except Exception:
            models[key] = []
    unet_all = (models.get("unet") or []) + (models.get("unet_gguf") or [])
    checks.append(_ck("model_list", "\u6a21\u578b\u5217\u8868", "ok" if unet_all else "warn",
                      "UNET %d\uff08\u542b GGUF %d\uff09/ CLIP %d / VAE %d / LoRA %d" % (
                          len(unet_all), len(models.get("unet_gguf") or []),
                          len(models.get("clip") or []), len(models.get("vae") or []),
                          len(models.get("lora") or []))))
    return checks, True, models, card_gb, ram_free, ram_total


def check_named(models, model, clip, loras):
    """\u6821\u9a8c\u8868\u5355\u91cc\u9009\u7684\u5177\u4f53\u6a21\u578b\u540d\u662f\u5426\u771f\u7684\u5728 ComfyUI \u5217\u8868\u91cc\uff08\u907f\u514d\u63d0\u4ea4\u540e\u624d\u62a5 not in list\uff09\u3002"""
    checks = []

    def _norm(s):
        return (s or "").replace("/", "\\").lower()

    def _has(name, key):
        want = _norm(name)
        pool = [_norm(x) for x in (models.get(key) or [])]
        if want in pool:
            return True
        base = want.split("\\")[-1]
        return sum(1 for p in pool if p.split("\\")[-1] == base) == 1

    if model:
        ok = _has(model, "unet") or _has(model, "unet_gguf")
        checks.append(_ck("model_sel", "\u6240\u9009 UNET \u6a21\u578b", "ok" if ok else "error",
                          ("%s \u5728\u5217\u8868\u4e2d" % model) if ok else
                          "%s \u4e0d\u5728 ComfyUI \u7684 UNET/GGUF \u5217\u8868\u91cc\u3002\u7528\u9875\u9762\u300c\u8bfb\u53d6 ComfyUI \u6a21\u578b\u5217\u8868\u300d\u91cd\u9009\u3002" % model))
    if clip:
        ok = _has(clip, "clip")
        checks.append(_ck("clip_sel", "\u6240\u9009 CLIP", "ok" if ok else "error",
                          ("%s \u5728\u5217\u8868\u4e2d" % clip) if ok else "%s \u4e0d\u5728 CLIP \u5217\u8868\u91cc\u3002" % clip))
    for l in (loras or []):
        nm = (l.get("name") if isinstance(l, dict) else l) or ""
        if not nm:
            continue
        ok = _has(nm, "lora")
        checks.append(_ck("lora_" + nm, "\u6240\u9009 LoRA", "ok" if ok else "error",
                          ("%s \u5728\u5217\u8868\u4e2d" % nm) if ok else "%s \u4e0d\u5728 LoRA \u5217\u8868\u91cc\u3002" % nm))
    return checks


def check_ffmpeg():
    p = shutil.which("ffmpeg")
    return [_ck("ffmpeg", "ffmpeg\uff08\u8bc4\u5206\u62bd\u5e27/\u62bd\u97f3\u9891\u5fc5\u9700\uff09", "ok" if p else "error",
                p if p else "\u672a\u627e\u5230\u3002Windows: winget install ffmpeg\uff0c\u6216\u4e0b\u8f7d\u540e\u628a bin \u52a0\u5165 PATH \u518d\u91cd\u5f00\u7ec8\u7aef\u3002")]


def check_llm(base, key=None):
    if not base:
        return [_ck("llm", "LLM \u7aef\u70b9", "warn", "\u672a\u586b\u5730\u5740\uff08\u5199\u5267\u672c/\u8bc4\u5206\u5fc5\u9700\uff09\u3002")]
    try:
        req = urllib.request.Request(base.rstrip("/") + "/models")
        if key:
            req.add_header("Authorization", "Bearer " + key)
        with urllib.request.urlopen(req, timeout=8) as r:
            j = json.load(r)
        n = len((j or {}).get("data") or (j or {}).get("models") or [])
        return [_ck("llm", "LLM \u7aef\u70b9", "ok" if n else "warn",
                    "\u53ef\u8fbe\uff0c\u5217\u51fa %d \u4e2a\u6a21\u578b" % n if n else "\u53ef\u8fbe\u4f46\u6ca1\u5217\u51fa\u6a21\u578b\uff08\u53ef\u80fd\u9700\u8981 API Key\uff09")]
    except Exception as e:
        return [_ck("llm", "LLM \u7aef\u70b9", "warn",
                    "\u8fde\u4e0d\u4e0a %s\uff08%s\uff09\u3002\u586b\u597d\u5730\u5740/Key \u540e\u518d\u8bd5\uff1b\u4e0d\u5f71\u54cd ComfyUI \u4fa7\u68c0\u67e5\u3002" % (base, type(e).__name__))]


def check_model_profile(base, model):
    """\u4ece\u6a21\u578b\u540d\u8bfb\u51fa\u6743\u91cd\u683c\u5f0f\u3001\u53d6\u771f\u5b9e\u4f53\u79ef\uff0c\u5e76\u8bf4\u660e\u5b83\u5bf9\u663e\u5b58\u7684\u610f\u4e49\u3002"""
    if not model:
        return []
    try:
        import mem_budget as mb
    except Exception:
        return []
    size_gb, src = (None, None)
    try:
        size_gb, src = mb.fetch_model_size_gb(base, model)
    except Exception:
        pass
    prof = mb.parse_model_profile(model, size_gb, src)
    detail = "\u683c\u5f0f **%s**%s" % (prof["format"],
                              ("\uff0c%.2f GB" % prof["size_gb"]) if prof.get("size_gb") else "\uff0c\u4f53\u79ef\u672a\u77e5")
    if "hybrid" in (model or "").lower() or "mixed" in (model or "").lower():
        detail += "\uff08\u5b9e\u9645\u662f\u6df7\u5408\u7cbe\u5ea6\uff0c\u591a\u79cd\u91cf\u5316\u6df7\u7528\uff09"
    if prof.get("needs_dequant"):
        detail += "\uff1b\u9700\u8981\u53cd\u91cf\u5316\uff0c\u5cf0\u503c\u901a\u5e38\u9ad8\u4e8e\u540c\u4f53\u79ef int8 \u76f4\u7b97"
    if prof.get("resident_gb"):
        detail += "\uff1b\u91c7\u6837\u65f6\u5e38\u9a7b\u7ea6 %.1f GB" % prof["resident_gb"]
    return [_ck("model_profile", "\u6240\u9009\u6a21\u578b\u683c\u5f0f", "ok", detail)]


def run_doctor(comfy_url, llm_base=None, llm_key=None, model=None, clip=None, loras=None):
    """\u8dd1\u5b8c\u6574\u81ea\u68c0\uff0c\u8fd4\u56de {ok, checks, summary, comfy_online}\u3002

    \u53ea\u67e5\u73af\u5883\uff1affmpeg / ComfyUI \u53ef\u8fbe / \u6a21\u677f\u6240\u9700\u8282\u70b9 / \u6a21\u578b\u5217\u8868 / \u6240\u9009\u6a21\u578b\u4e0e CLIP \u662f\u5426\u5b58\u5728 /
    \u6240\u9009\u6a21\u578b\u683c\u5f0f / LLM \u7aef\u70b9\u3002\u663e\u5b58\u9884\u7b97\u4e0e\u751f\u6210\u5206\u652f\u90fd\u4e0d\u5728\u8fd9\u91cc\u3002
    """
    base = (comfy_url or "http://127.0.0.1:8000").rstrip("/")
    classes = required_nodes()
    checks = []
    checks += check_ffmpeg()
    comfy_checks, online, models, _card_gb, _ram_free, _ram_total = check_comfy(base, classes)
    checks += comfy_checks
    if online:
        checks += check_named(models, model, clip, loras)
        checks += check_model_profile(base, model)
    checks += check_llm(llm_base, llm_key)

    n_err = sum(1 for c in checks if c["level"] == "error")
    n_warn = sum(1 for c in checks if c["level"] == "warn")
    n_ok = sum(1 for c in checks if c["level"] == "ok")
    if n_err:
        summary = "%d \u9879\u5fc5\u987b\u5148\u89e3\u51b3\uff08\u9519\u8bef %d / \u8b66\u544a %d / \u901a\u8fc7 %d\uff09" % (n_err + n_warn, n_err, n_warn, n_ok)
    elif n_warn:
        summary = "\u53ef\u4ee5\u8dd1\uff0c\u4f46\u6709 %d \u9879\u8b66\u544a\uff08\u901a\u8fc7 %d\uff09" % (n_warn, n_ok)
    else:
        summary = "\u5168\u90e8\u901a\u8fc7\uff08%d \u9879\uff09" % n_ok
    return {"ok": n_err == 0, "comfy_online": online, "summary": summary, "checks": checks}


def main(argv=None):
    """\u547d\u4ee4\u884c\u81ea\u68c0\uff1apython core/doctor.py [--comfy URL] [--llm URL] [--model \u540d] [--clip \u540d]"""
    import argparse
    p = argparse.ArgumentParser(description="\u73af\u5883\u81ea\u68c0\uff08ComfyUI \u8282\u70b9/\u6a21\u578b\u3001ffmpeg\u3001LLM\uff09")
    p.add_argument("--comfy", default="http://127.0.0.1:8000", help="ComfyUI \u5730\u5740")
    p.add_argument("--llm", default=None, help="LLM \u7aef\u70b9\uff08\u53ef\u9009\uff0c\u4f8b\u5982 http://127.0.0.1:8080/v1\uff09")
    p.add_argument("--llm-key", default=None)
    p.add_argument("--model", default=None, help="\u8981\u6821\u9a8c\u7684 UNET \u6a21\u578b\u540d\uff08\u53ef\u9009\uff09")
    p.add_argument("--clip", default=None)
    a = p.parse_args(argv)
    rep = run_doctor(comfy_url=a.comfy, llm_base=a.llm, llm_key=a.llm_key, model=a.model,
                     clip=a.clip)
    mark = {"ok": "[ok]  ", "warn": "[warn]", "error": "[ERR] "}
    for c in rep["checks"]:
        print("%s %-32s %s" % (mark.get(c["level"], "[?]   "), c["label"], c["detail"]))
    print()
    print("\u81ea\u68c0\u7ed3\u8bba\uff1a", rep["summary"])
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
