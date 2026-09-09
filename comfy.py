#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI \u64cd\u4f5c\u5de5\u5177\u7bb1\uff08\u7eaf\u6807\u51c6\u5e93\uff0c\u65e0\u7b2c\u4e09\u65b9\u4f9d\u8d56\uff09\u3002\u6240\u6709\u547d\u4ee4\u8f93\u51fa JSON \u5230 stdout\uff0c\u9519\u8bef\u5230 stderr\u3002

\u7528\u6cd5:
  python comfy.py stats
  python comfy.py models [checkpoints|loras|vae|unet|diffusion_models|text_encoders|...]
  python comfy.py nodes [pattern]
  python comfy.py nodeinfo <class>
  python comfy.py convert <ui_workflow.json> [-o out.json]
  python comfy.py validate|check <workflow.json>
  python comfy.py queue <workflow.json>
  python comfy.py wait <prompt_id> [--timeout 900]
  python comfy.py result <prompt_id> [-o \u8f93\u51fa\u76ee\u5f55]
  python comfy.py run <workflow.json> [-o \u8f93\u51fa\u76ee\u5f55] [--timeout 900]
  python comfy.py status|history [prompt_id]|interrupt|clear
  python comfy.py upload <file>

\u5730\u5740\u53ef\u7531\u73af\u5883\u53d8\u91cf COMFYUI_URL \u8986\u76d6\uff08\u9ed8\u8ba4 http://127.0.0.1:8000\uff09\u3002
"""
import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8000")
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
OBJECT_INFO_PATH = os.path.join(THIS_DIR, "object_info.json")

# \u5f3a\u5236\u65e0\u4ee3\u7406\u76f4\u8fde\uff1aurllib \u9996\u6b21\u8c03\u7528\u4f1a\u8bfb\u53d6\u7cfb\u7edf\u4ee3\u7406\u5e76\u7f13\u5b58\u5230\u5168\u5c40 opener\uff0c
# \u82e5\u4ee3\u7406\u8f6f\u4ef6\u4e2d\u9014\u5173\u95ed\u4f1a\u628a 127.0.0.1:8000 \u7684\u8bf7\u6c42\u8bef\u8def\u7531\u5230\u5931\u6548\u4ee3\u7406\u5bfc\u81f4\u6c38\u4e45\u5361\u6b7b\u3002
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# \u7531\u63a7\u4ef6\uff08widget\uff09\u63d0\u4f9b\u503c\u7684\u8f93\u5165\u7c7b\u578b\uff1b\u5176\u4f59\u7c7b\u578b\uff08IMAGE/MODEL/LATENT/...\uff09\u53ea\u80fd\u8fde\u7ebf
WIDGET_TYPES = ("STRING", "INT", "FLOAT", "BOOLEAN", "COMBO",
                "COMFY_DYNAMICCOMBO_V3", "COMFY_MATCHTYPE_V3",
                "OPTIONS", "NUMBER", "SEED", "JSON", "COLORCODE", "COLOR",
                "VEC2", "VEC3", "VEC4")
# \u4ec5\u524d\u7aef\u5b58\u5728\u3001\u4e0d\u5c5e\u4e8e\u540e\u7aef\u6267\u884c\u56fe\u7684\u8282\u70b9\u7c7b\u578b\uff0c\u8f6c\u6362\u65f6\u5254\u9664
UI_ONLY_TYPES = {"MarkdownNote", "Note", "Reroute", "PrimitiveNode"}


def is_widget_like(spec_in):
    """\u5224\u65ad\u67d0\u8f93\u5165\u5b9a\u4e49\u662f\u5426\u7531\u63a7\u4ef6\u63d0\u4f9b\u503c\uff08STRINT/INT/FLOAT/BOOLEAN/COMBO/\u52a8\u6001COMBO\u7b49\uff09\u3002"""
    if not (isinstance(spec_in, list) and spec_in):
        return False
    t = spec_in[0]
    if isinstance(t, list):  # \u666e\u901a COMBO \u679a\u4e3e
        return True
    if not isinstance(t, str):
        return False
    if t in WIDGET_TYPES:
        return True
    if ":" in t and t.split(":", 1)[0] in ("INT", "FLOAT", "STRING", "SEED"):
        return True
    if any(part.strip() in WIDGET_TYPES for part in t.split(",")):
        return True
    return False

# ---------------------------------------------------------------- HTTP

def http_json(path, method="GET", data=None, timeout=120):
    url = BASE + path
    req = urllib.request.Request(url, method=method)
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with _NO_PROXY_OPENER.open(req, data=body, timeout=timeout) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw.decode("utf-8"))
            except Exception:
                return r.status, {"raw": raw.decode("utf-8", "replace")[:2000]}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw.decode("utf-8"))
        except Exception:
            return e.code, {"http_error": e.code, "body": raw.decode("utf-8", "replace")[:2000]}
    except Exception as e:
        return -1, {"error": str(e)}


def http_multipart(path, filepath, field="image", timeout=300):
    """multipart/form-data \u4e0a\u4f20\uff08/upload/image\uff09\u3002"""
    boundary = uuid.uuid4().hex
    filename = os.path.basename(filepath)
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(filepath, "rb") as f:
        content = f.read()
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(BASE + path, data=head + content + tail, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with _NO_PROXY_OPENER.open(req, timeout=timeout) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw.decode("utf-8"))
            except Exception:
                return r.status, {"raw": raw.decode("utf-8", "replace")[:2000]}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw.decode("utf-8"))
        except Exception:
            return e.code, {"http_error": e.code, "body": raw.decode("utf-8", "replace")[:2000]}
    except Exception as e:
        return -1, {"error": str(e)}


def download_file(view_path, dest):
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    req = urllib.request.Request(BASE + view_path)
    with _NO_PROXY_OPENER.open(req, timeout=300) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    return dest


# ---------------------------------------------------------------- object_info

def load_object_info(force_refresh=False):
    if not force_refresh and os.path.exists(OBJECT_INFO_PATH):
        with open(OBJECT_INFO_PATH, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and data:
                return data
    code, data = http_json("/object_info", timeout=300)
    if code == 200 and isinstance(data, dict) and data:
        with open(OBJECT_INFO_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return data
    print(json.dumps({"ok": False, "error": "\u83b7\u53d6 object_info \u5931\u8d25", "http": code, "detail": data},
                     ensure_ascii=False, indent=2), file=sys.stderr)
    return data if isinstance(data, dict) else {}


def spec_inputs_of(info, cls):
    spec = info.get(cls)
    if not spec:
        return {}
    out = {}
    for part in (spec.get("input", {}).get("required", {}), spec.get("input", {}).get("optional", {})):
        out.update(part)
    return out


def resolve_input_spec(info, cls, name):
    """\u89e3\u6790\u8f93\u5165\u540d\uff08\u652f\u6301 COMFY_AUTOGROW_V3 \u7684\u70b9\u53f7\u5d4c\u5957\u540d\uff09\uff0c\u8fd4\u56de\u8f93\u5165\u5b9a\u4e49\u6216 None\u3002"""
    spec_inputs = spec_inputs_of(info, cls)
    if name in spec_inputs:
        return spec_inputs[name]
    if "." in name:
        base, rest = name.split(".", 1)
        base_in = spec_inputs.get(base)
        if (isinstance(base_in, list) and base_in
                and base_in[0] == "COMFY_AUTOGROW_V3" and isinstance(base_in[1], dict)):
            tpl = base_in[1].get("template", {})
            tinput = tpl.get("input", {})
            req = tinput.get("required", {})
            prefix = tpl.get("prefix")
            if prefix and rest.startswith(prefix) and rest[len(prefix):].isdigit():
                base_key = prefix.rstrip("_")
                if base_key in req:
                    return req[base_key]
            if rest in (tpl.get("names") or []):
                return req.get("value") or ["FLOAT", {}]
    return None


# ---------------------------------------------------------------- \u5de5\u4f5c\u6d41\u8f6c\u6362

def ui_to_api(ui):
    """\u524d\u7aef UI \u683c\u5f0f -> /prompt API \u683c\u5f0f\u3002\u8fd4\u56de (api_graph, warnings)\u3002"""
    info = load_object_info()
    links = {}
    for l in ui.get("links", []):
        links[l[0]] = {"from": l[1], "from_slot": l[2], "to": l[3], "to_slot": l[4]}
    api = {}
    warnings = []
    for node in ui.get("nodes", []):
        nid = str(node.get("id"))
        cls = node.get("type")
        if cls in UI_ONLY_TYPES:
            continue
        spec = info.get(cls)
        if spec is None:
            warnings.append(f"\u8282\u70b9 {nid} [{cls}] \u4e0d\u5728 object_info \u4e2d\uff0c\u5df2\u8df3\u8fc7\uff08\u53ef\u80fd\u662f\u524d\u7aef\u4e13\u5c5e\u8282\u70b9\uff09")
            continue
        spec_inputs = spec_inputs_of(info, cls)
        inputs = {}
        widgets = list(node.get("widgets_values") or [])
        # widgets_values \u4e0e\u300c\u5e26 widget \u7684\u8f93\u5165\u300d\u6309\u987a\u5e8f\u4e00\u4e00\u5bf9\u5e94\uff08\u5305\u62ec\u5df2\u8fde\u7ebf\u7684\u8f93\u5165\uff09
        widget_map = {}
        wi = 0
        for inp in node.get("inputs", []):
            if "widget" in inp and wi < len(widgets):
                widget_map[inp.get("name")] = widgets[wi]
                wi += 1
        for inp in node.get("inputs", []):
            name = inp.get("name")
            link_id = inp.get("link")
            if link_id is not None:
                lk = links.get(link_id)
                if lk is None:
                    warnings.append(f"\u8282\u70b9 {nid} \u8f93\u5165 '{name}' \u5f15\u7528\u4e86\u4e0d\u5b58\u5728\u7684\u94fe\u63a5 {link_id}")
                    continue
                inputs[name] = [str(lk["from"]), lk["from_slot"]]
            else:
                spec_in = resolve_input_spec(info, cls, name) or spec_inputs.get(name)
                val = widget_map.get(name)
                if is_widget_like(spec_in) and name in widget_map and val is not None:
                    inputs[name] = val
                # \u5426\u5219\uff1a\u65e0\u63a7\u4ef6\u503c/\u63a7\u4ef6\u503c\u4e3a\u7a7a\uff0c\u7701\u7565\u8be5\u8f93\u5165\uff08\u7531\u540e\u7aef\u7528\u9ed8\u8ba4\u503c\uff09
        api[nid] = {"class_type": cls, "inputs": inputs}
    return api, warnings


def load_workflow(path):
    """\u8bfb\u5de5\u4f5c\u6d41\u6587\u4ef6\uff1a\u81ea\u52a8\u8bc6\u522b UI \u683c\u5f0f\u5e76\u8f6c\u6362\u3002\u8fd4\u56de API \u683c\u5f0f dict\u3002"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "nodes" in data:
        api, warns = ui_to_api(data)
        if warns:
            print(json.dumps({"convert_warnings": warns}, ensure_ascii=False, indent=2), file=sys.stderr)
        return api
    if isinstance(data, dict) and all(isinstance(v, dict) and "class_type" in v for v in data.values()):
        return data
    raise ValueError("\u65e0\u6cd5\u8bc6\u522b\u7684\u5de5\u4f5c\u6d41\u683c\u5f0f\uff1a\u65e2\u4e0d\u662f API \u683c\u5f0f\u4e5f\u4e0d\u662f UI \u683c\u5f0f")


def validate_api(api):
    """\u672c\u5730\u9759\u6001\u6821\u9a8c\uff08\u5bf9\u7167 object_info \u5feb\u7167\uff09\u3002\u8fd4\u56de (ok, issues)\u3002"""
    info = load_object_info()
    issues = []
    for nid, node in api.items():
        cls = node.get("class_type")
        spec = info.get(cls)
        if spec is None:
            issues.append(f"\u8282\u70b9 {nid}: \u7c7b [{cls}] \u4e0d\u5728 object_info \u4e2d")
            continue
        known = set(spec["input"].get("required", {})) | set(spec["input"].get("optional", {}))
        for k in node.get("inputs", {}):
            if k not in known and resolve_input_spec(info, cls, k) is None:
                issues.append(f"\u8282\u70b9 {nid} [{cls}]: \u672a\u77e5\u8f93\u5165 '{k}'")
        for k, v in node.get("inputs", {}).items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                if v[0] not in api:
                    issues.append(f"\u8282\u70b9 {nid} [{cls}]: \u5f15\u7528\u4e86\u4e0d\u5b58\u5728\u7684\u4e0a\u6e38\u8282\u70b9 '{v[0]}'")
    return (len(issues) == 0), issues


def output_items(rec):
    """\u904d\u5386 history \u8bb0\u5f55\u4e2d\u7684\u8f93\u51fa\u6587\u4ef6\u9879\u3002"""
    for node_id, node_out in rec.get("outputs", {}).items():
        if not isinstance(node_out, dict):
            continue
        for kind, items in node_out.items():
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict) and it.get("filename"):
                    yield node_id, kind, it


# ---------------------------------------------------------------- \u5b50\u547d\u4ee4

def cmd_stats(args):
    code, d = http_json("/system_stats", timeout=30)
    if code == 200:
        s = d.get("system", {})
        devs = d.get("devices", [])
        out({
            "ok": True,
            "comfyui_version": s.get("comfyui_version"),
            "python": s.get("python_version"),
            "pytorch": s.get("pytorch_version"),
            "devices": [{"name": x.get("name"), "vram_total": x.get("vram_total"), "vram_free": x.get("vram_free")} for x in devs],
        })
    else:
        out({"ok": False, "http": code, "detail": d})
        sys.exit(1)


def cmd_models(args):
    kind = args.kind or "checkpoints"
    code, d = http_json(f"/models/{kind}", timeout=30)
    if code == 200 and isinstance(d, list):
        out({"ok": True, "kind": kind, "models": d})
    else:
        out({"ok": False, "http": code, "detail": d,
             "hint": "\u53ef\u7528\u7c7b\u522b: checkpoints / loras / vae / unet / diffusion_models / text_encoders / clip_vision / controlnet / upscale_models \u7b49"})
        sys.exit(1)


def cmd_nodes(args):
    info = load_object_info()
    pat = (args.pattern or "").lower()
    names = [k for k in info.keys() if pat in k.lower()]
    out({"ok": True, "pattern": pat, "count": len(names), "nodes": sorted(names)[:500]})


def cmd_nodeinfo(args):
    info = load_object_info()
    cls = args.class_name
    spec = info.get(cls)
    if not spec:
        out({"ok": False, "error": f"\u7c7b [{cls}] \u4e0d\u5b58\u5728", "hint": "\u7528 nodes \u547d\u4ee4\u641c\u7d22"})
        sys.exit(1)
    out({"ok": True, "class": cls, "input": spec.get("input"), "output": spec.get("output")})


def cmd_convert(args):
    with open(args.workflow, encoding="utf-8") as f:
        ui = json.load(f)
    if "nodes" not in ui:
        out({"ok": False, "error": "\u8f93\u5165\u4e0d\u662f UI \u683c\u5f0f\uff08\u7f3a nodes \u5b57\u6bb5\uff09"})
        sys.exit(1)
    api, warns = ui_to_api(ui)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(api, f, ensure_ascii=False, indent=2)
    ok, issues = validate_api(api)
    out({"ok": True, "converted": True, "valid": ok, "node_count": len(api),
         "warnings": warns, "issues": issues,
         "out_file": args.out, "graph": api if args.show else None})


def cmd_validate(args):
    api = load_workflow(args.workflow)
    ok, issues = validate_api(api)
    out({"ok": True, "valid": ok, "node_count": len(api), "issues": issues})
    if not ok:
        sys.exit(1)


def cmd_queue(args):
    api = load_workflow(args.workflow)
    client_id = args.client_id or uuid.uuid4().hex
    code, d = http_json("/prompt", method="POST", data={"prompt": api, "client_id": client_id}, timeout=120)
    if code == 200 and d.get("prompt_id"):
        out({"ok": True, "prompt_id": d["prompt_id"], "client_id": client_id})
    else:
        out({"ok": False, "http": code, **d})
        sys.exit(3)


def cmd_status(args):
    code, d = http_json("/queue", timeout=30)
    if code == 200:
        run = d.get("queue_running", [])
        pend = d.get("queue_pending", [])

        def _ids(items):
            ids = []
            for it in items:
                if isinstance(it, dict):
                    ids.append(it.get("prompt_id"))
                elif isinstance(it, (list, tuple)) and len(it) > 1 and isinstance(it[1], dict):
                    ids.append(it[1].get("prompt_id"))
                elif isinstance(it, (list, tuple)) and it:
                    ids.append(str(it[0]))
            return ids

        out({"ok": True,
             "running_count": len(run), "running_ids": _ids(run),
             "pending_count": len(pend), "pending_ids": _ids(pend)})
    else:
        out({"ok": False, "http": code, "detail": d})
        sys.exit(1)


def cmd_wait(args):
    pid = args.prompt_id
    deadline = time.time() + args.timeout
    while True:
        code, d = http_json(f"/history/{pid}", timeout=60)
        if code == 200 and isinstance(d, dict) and pid in d:
            rec = d[pid]
            status = rec.get("status", {})
            ss = status.get("status_str")
            if ss == "error":
                msgs = [m for m in status.get("messages", []) if m and m[0] in ("execution_error", "execution_interrupted")]
                out({"ok": False, "status": ss, "prompt_id": pid, "errors": msgs, "outputs": rec.get("outputs", {})})
                sys.exit(4)
            if ss == "success" or status.get("completed") is True:
                out({"ok": True, "status": ss, "prompt_id": pid, "outputs": rec.get("outputs", {})})
                return
        if time.time() >= deadline:
            out({"ok": False, "error": "timeout", "prompt_id": pid})
            sys.exit(2)
        time.sleep(min(args.poll, max(1.0, deadline - time.time())))


def cmd_result(args):
    pid = args.prompt_id
    code, d = http_json(f"/history/{pid}", timeout=60)
    if code != 200 or not (isinstance(d, dict) and pid in d):
        out({"ok": False, "error": f"history \u4e2d\u627e\u4e0d\u5230 prompt_id={pid}", "http": code})
        sys.exit(1)
    rec = d[pid]
    outdir = args.outdir or os.path.join(THIS_DIR, "outputs", pid)
    saved, failed = [], []
    for node_id, kind, it in output_items(rec):
        if it.get("type") != "output":
            continue
        sub = it.get("subfolder") or ""
        name = it["filename"]
        rel = os.path.join(sub, name) if sub else name
        dest = os.path.join(outdir, rel)
        q = urllib.parse.urlencode({"filename": name, "subfolder": sub, "type": "output"})
        try:
            download_file(f"/view?{q}", dest)
            saved.append({"node": node_id, "kind": kind, "file": dest})
        except Exception as e:
            failed.append({"node": node_id, "kind": kind, "file": dest, "error": str(e)})
    out({"ok": len(failed) == 0, "prompt_id": pid, "outdir": outdir, "saved": saved, "failed": failed})


def cmd_run(args):
    api = load_workflow(args.workflow)
    client_id = uuid.uuid4().hex
    code, d = http_json("/prompt", method="POST", data={"prompt": api, "client_id": client_id}, timeout=120)
    if code != 200 or not d.get("prompt_id"):
        out({"ok": False, "stage": "queue", "http": code, **d})
        sys.exit(3)
    pid = d["prompt_id"]
    print(json.dumps({"stage": "queued", "prompt_id": pid}, ensure_ascii=False), flush=True)
    deadline = time.time() + args.timeout
    while True:
        code, d = http_json(f"/history/{pid}", timeout=60)
        if code == 200 and isinstance(d, dict) and pid in d:
            rec = d[pid]
            status = rec.get("status", {})
            ss = status.get("status_str")
            if ss == "error":
                msgs = [m for m in status.get("messages", []) if m and m[0] in ("execution_error", "execution_interrupted")]
                out({"ok": False, "stage": "execute", "status": ss, "prompt_id": pid, "errors": msgs})
                sys.exit(4)
            if ss == "success" or status.get("completed") is True:
                break
        if time.time() >= deadline:
            out({"ok": False, "stage": "timeout", "prompt_id": pid})
            sys.exit(2)
        time.sleep(min(args.poll, max(1.0, deadline - time.time())))
    # \u4e0b\u8f7d\u8f93\u51fa
    outdir = args.outdir or os.path.join(THIS_DIR, "outputs", pid)
    saved, failed = [], []
    for node_id, kind, it in output_items(rec):
        if it.get("type") != "output":
            continue
        sub = it.get("subfolder") or ""
        name = it["filename"]
        rel = os.path.join(sub, name) if sub else name
        dest = os.path.join(outdir, rel)
        q = urllib.parse.urlencode({"filename": name, "subfolder": sub, "type": "output"})
        try:
            download_file(f"/view?{q}", dest)
            saved.append({"node": node_id, "kind": kind, "file": dest})
        except Exception as e:
            failed.append({"node": node_id, "kind": kind, "file": dest, "error": str(e)})
    out({"ok": len(failed) == 0, "stage": "done", "prompt_id": pid, "outdir": outdir,
         "saved": saved, "failed": failed})


def cmd_check(args):
    """\u63d0\u4ea4\u5de5\u4f5c\u6d41\u505a\u540e\u7aef\u6821\u9a8c\uff0c\u901a\u8fc7\u540e\u7acb\u5373\u6e05\u7a7a\u961f\u5217\uff08\u4e0d\u5b9e\u9645\u751f\u6210\uff09\u3002"""
    api = load_workflow(args.workflow)
    code, d = http_json("/prompt", method="POST",
                        data={"prompt": api, "client_id": uuid.uuid4().hex}, timeout=120)
    if code == 200 and d.get("prompt_id"):
        http_json("/queue", method="POST", data={"clear": True}, timeout=30)
        out({"ok": True, "valid": True, "prompt_id": d["prompt_id"],
             "note": "\u540e\u7aef\u6821\u9a8c\u901a\u8fc7\uff1b\u5df2\u7acb\u5373\u6e05\u7a7a\u961f\u5217\uff0c\u672a\u6267\u884c\u751f\u6210"})
    else:
        out({"ok": False, "valid": False, "http": code, **d})
        sys.exit(3)


def cmd_history(args):
    path = f"/history/{args.prompt_id}" if args.prompt_id else "/history"
    code, d = http_json(path, timeout=60)
    if code != 200 or not isinstance(d, dict):
        out({"ok": False, "http": code, "detail": d})
        sys.exit(1)
    items = []
    for pid, rec in d.items():
        status = rec.get("status", {})
        items.append({
            "prompt_id": pid,
            "status": status.get("status_str"),
            "outputs": {nid: list(k.keys()) for nid, k in (rec.get("outputs") or {}).items()},
        })
    out({"ok": True, "count": len(items), "items": items})


def cmd_interrupt(args):
    code, d = http_json("/interrupt", method="POST", data={}, timeout=30)
    out({"ok": code in (200, 201), "http": code, "detail": d} if code not in (200, 201)
        else {"ok": True, "interrupted": True})


def cmd_clear(args):
    code, d = http_json("/queue", method="POST", data={"clear": True}, timeout=30)
    out({"ok": code in (200, 201), "http": code, "detail": d} if code not in (200, 201)
        else {"ok": True, "cleared": True})


def cmd_upload(args):
    if not os.path.isfile(args.file):
        out({"ok": False, "error": f"\u6587\u4ef6\u4e0d\u5b58\u5728: {args.file}"})
        sys.exit(1)
    code, d = http_multipart("/upload/image", args.file)
    if code in (200, 201) and isinstance(d, dict) and d.get("name"):
        name = d["name"]
        sub = d.get("subfolder") or ""
        out({"ok": True, "name": name, "subfolder": sub, "type": d.get("type", "input"),
             "usable_as": name if not sub else f"{sub}/{name}",
             "hint": f"\u5728 LoadImage \u7684 image \u53c2\u6570\u4e2d\u586b\u5199: {name if not sub else sub + '/' + name}"})
    else:
        out({"ok": False, "http": code, "detail": d})
        sys.exit(1)


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main():
    p = argparse.ArgumentParser(description="ComfyUI \u64cd\u4f5c\u5de5\u5177\u7bb1\uff08\u7eaf\u6807\u51c6\u5e93\uff09")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, **kw):
        sp = sub.add_parser(name, **kw)
        sp.set_defaults(fn=fn)
        return sp

    add("stats", cmd_stats)
    m = add("models", cmd_models, help="\u5217\u51fa\u6a21\u578b")
    m.add_argument("kind", nargs="?", default="checkpoints")
    n = add("nodes", cmd_nodes, help="\u641c\u7d22\u8282\u70b9\u7c7b\u540d")
    n.add_argument("pattern", nargs="?", default="")
    ni = add("nodeinfo", cmd_nodeinfo, help="\u67e5\u770b\u8282\u70b9\u8f93\u5165\u5b9a\u4e49")
    ni.add_argument("class_name")
    c = add("convert", cmd_convert, help="UI \u683c\u5f0f -> API \u683c\u5f0f")
    c.add_argument("workflow")
    c.add_argument("-o", "--out", help="\u8f93\u51fa API JSON \u6587\u4ef6")
    c.add_argument("--show", action="store_true", help="\u5728\u7ed3\u679c\u4e2d\u9644\u5e26\u8f6c\u6362\u540e\u7684\u56fe")
    v = add("validate", cmd_validate, help="\u672c\u5730\u9759\u6001\u6821\u9a8c\u5de5\u4f5c\u6d41")
    v.add_argument("workflow")
    ch = add("check", cmd_check, help="\u540e\u7aef\u6821\u9a8c\u540e\u7acb\u5373\u6e05\u961f\u5217\uff08\u4e0d\u751f\u6210\uff09")
    ch.add_argument("workflow")
    q = add("queue", cmd_queue, help="\u63d0\u4ea4\u4efb\u52a1\uff0c\u8fd4\u56de prompt_id")
    q.add_argument("workflow")
    q.add_argument("--client-id")
    w = add("wait", cmd_wait, help="\u7b49\u5f85\u4efb\u52a1\u5b8c\u6210")
    w.add_argument("prompt_id")
    w.add_argument("--timeout", type=float, default=900)
    w.add_argument("--poll", type=float, default=2.0)
    r = add("result", cmd_result, help="\u4e0b\u8f7d\u4efb\u52a1\u8f93\u51fa\u6587\u4ef6")
    r.add_argument("prompt_id")
    r.add_argument("-o", "--outdir")
    run = add("run", cmd_run, help="\u63d0\u4ea4+\u7b49\u5f85+\u4e0b\u8f7d \u4e00\u6b65\u5b8c\u6210")
    run.add_argument("workflow")
    run.add_argument("-o", "--outdir")
    run.add_argument("--timeout", type=float, default=900)
    run.add_argument("--poll", type=float, default=2.0)
    add("status", cmd_status, help="\u961f\u5217\u72b6\u6001")
    h = add("history", cmd_history, help="\u6267\u884c\u5386\u53f2")
    h.add_argument("prompt_id", nargs="?")
    add("interrupt", cmd_interrupt, help="\u4e2d\u65ad\u5f53\u524d\u751f\u6210")
    add("clear", cmd_clear, help="\u6e05\u7a7a\u961f\u5217")
    u = add("upload", cmd_upload, help="\u4e0a\u4f20\u6587\u4ef6\u5230 input \u76ee\u5f55")
    u.add_argument("file")

    args = p.parse_args()
    try:
        args.fn(args)
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
