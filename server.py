#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ref2VA optimizer - local web UI (stdlib only).

Run:
  python server.py            # serve on 0.0.0.0:8090 (LAN)
  set HOST/PORT to override.

The page lets a tester fill an optimization task, upload reference images,
optionally give a reference video (Mode B), then run the optimizer and watch
live logs + the champion result/video.
"""
import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "core"))
try:
    import ref2va_auto as _ra
except Exception:
    _ra = None
try:
    import doctor as _doctor
except Exception:
    _doctor = None
WEB_DIR = os.path.join(HERE, "web")
UPLOAD_DIR = os.path.join(HERE, "uploads")
TASK_DIR = os.path.join(HERE, "tasks")
OUTPUT_DIR = os.path.join(HERE, "outputs")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8090"))

for _d in (WEB_DIR, UPLOAD_DIR, TASK_DIR, OUTPUT_DIR):
    os.makedirs(_d, exist_ok=True)

LOCK = threading.Lock()
JOBS = {}   # id -> dict

_pending = []            # ordered list of queued job ids (FIFO)
_running_jid = None      # currently executing job id
_worker_active = threading.Event()

WS = None  # optional future SSE/webhook hook


def _safe_name(name):
    base = os.path.basename(name or "")
    base = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]", "_", base)
    return base or "file"


def _enqueue(jid):
    with LOCK:
        _pending.append(jid)
    _ensure_worker()


def _ensure_worker():
    if not _worker_active.is_set():
        _worker_active.set()
        threading.Thread(target=_drain, daemon=True).start()


def _drain():
    global _running_jid
    while True:
        with LOCK:
            if not _pending:
                _worker_active.clear()
                return
            jid = _pending.pop(0)
            job = JOBS.get(jid)
            _running_jid = jid if job else None
        if job:
            _run_job(job)
        with LOCK:
            _running_jid = None


def _run_job(job):
    job["status"] = "running"
    cfg_path = job.get("cfg_path")
    cmd = [sys.executable, "-u", os.path.join(HERE, "optimizer.py"), "--config", cfg_path]
    job["log"] += "[server] starting: " + " ".join(cmd) + "\n"
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=HERE)
        job["proc"] = proc
        for line in proc.stdout:
            txt = line.decode("utf-8", "replace").rstrip()
            if txt:
                job["log"] += txt + "\n"
        code = proc.wait()
        if job.get("cancel"):
            job["status"] = "cancelled"
        else:
            job["status"] = "done" if code == 0 else "error"
        job["exit"] = code
    except Exception as e:
        job["status"] = "error"
        job["log"] += "\n[server] " + str(e) + "\n"
    finally:
        job["proc"] = None
    job["log"] += "\n[server] finished (%s)\n" % job.get("status")


def _llm_models(base, key=None):
    """\u4ece OpenAI \u517c\u5bb9 LLM \u7aef\u70b9 /v1/models \u62c9\u53d6\u53ef\u7528\u6a21\u578b id\uff1b\u5931\u8d25\u8fd4\u56de []\u3002"""
    import json as _json
    url = (base or "").rstrip("/") + "/models"
    if not url.startswith("http"):
        return []
    headers = {"Authorization": "Bearer " + (key or "")} if key else {}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            d = _json.loads(r.read().decode("utf-8"))
        return [m.get("id") for m in d.get("data", []) if m.get("id")]
    except Exception:
        return []


def _queue_position(tid):
    with LOCK:
        run = 1 if _running_jid else 0
        try:
            idx = _pending.index(tid) + 1
        except ValueError:
            idx = 0
    return run + idx


def _cancel_job(jid):
    with LOCK:
        job = JOBS.get(jid)
        if not job or job["status"] not in ("queued", "running"):
            return False
        job["cancel"] = True
        if job["status"] == "queued":
            try:
                _pending.remove(jid)
            except ValueError:
                pass
        proc = job.get("proc")
        outdir = job.get("outdir")
    if proc:
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=20)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    # \u5b9a\u5411\u53d6\u6d88\u8be5\u4efb\u52a1\u63d0\u4ea4\u5230 ComfyUI \u7684\u4f5c\u4e1a\uff08\u4e0d\u5f71\u54cd\u5176\u5b83\u6392\u961f\u4efb\u52a1\uff09
    if _ra is not None and outdir:
        pf = os.path.join(outdir, "comfy_prompt_ids.txt")
        pids = []
        try:
            with open(pf, encoding="utf-8") as f:
                pids = [l.strip() for l in f if l.strip()]
        except Exception:
            pass
        try:
            _ra.comfy_cancel_prompts(pids)
        except Exception:
            pass
    return True


def _form_meta(payload):
    """\u628a\u63d0\u4ea4\u7684\u9664\u6587\u4ef6\u6570\u636e\u5916\u7684\u8868\u5355\u5b57\u6bb5\u5b58\u4e0b\u6765\uff0c\u4f9b\u5386\u53f2\u680f\u56de\u586b\u3002"""
    files = [{"name": f.get("name"), "note": f.get("note") or ""} for f in payload.get("files") or []]
    return {
        "name": payload.get("name"), "story": payload.get("story"), "optimize_target": payload.get("optimize_target"),
        "duration": payload.get("duration"), "model": payload.get("model"), "clip": payload.get("clip"),
        "loras": payload.get("loras"),
        "sampler": payload.get("sampler"), "scheduler": payload.get("scheduler"), "steps": payload.get("steps"),
        "seed": payload.get("seed"), "megapixels": payload.get("megapixels"), "aspect": payload.get("aspect"),
        "video_edit": bool(payload.get("video_edit")), "flow": payload.get("flow") or "ref2va",
        "llm_base": payload.get("llm_base"),
        "llm_model": payload.get("llm_model"), "llm_api_key": payload.get("llm_api_key"),
        "audio_llm_base": payload.get("audio_llm_base"), "audio_llm_model": payload.get("audio_llm_model"),
        "audio_llm_api_key": payload.get("audio_llm_api_key"), "audio_scoring": payload.get("audio_scoring") or "off",
        "comfy_url": payload.get("comfy_url"), "quick_render": bool(payload.get("quick_render")),
        "fine_render": bool(payload.get("fine_render")), "admission_threshold": payload.get("admission_threshold"),
        "max_iterations": payload.get("max_iterations"), "base_patience": payload.get("base_patience"),
        "files": files,
    }


def _collect_outputs(job):
    """Find generated videos/prompts under the task outdir and expose URLs."""
    outdir = job.get("outdir")
    res = {"videos": [], "prompts": []}
    if not outdir or not os.path.isdir(outdir):
        return res
    rel = os.path.relpath(outdir, OUTPUT_DIR) if OUTPUT_DIR in outdir else job["id"]
    for root, _dirs, files in os.walk(outdir):
        for fn in sorted(files):
            if fn.lower().endswith((".mp4", ".webm", ".mov", ".mkv")):
                p = os.path.join(root, fn)
                rp = os.path.relpath(p, OUTPUT_DIR).replace("\\", "/")
                res["videos"].append("/outputs/" + rp)
            elif fn in ("champion_prompt.txt", "champion_script.txt"):
                rp = os.path.relpath(os.path.join(root, fn), OUTPUT_DIR).replace("\\", "/")
                res["prompts"].append("/outputs/" + rp)
    return res


def _collect_rounds(job):
    """\u9010\u8f6e\u7ed3\u679c\uff1a\u628a optimizer_history.json \u4e0e\u6bcf\u8f6e\u843d\u76d8\u7684\u4ea7\u7269\uff08prompt/script/\u89c6\u9891\uff09\u5408\u5e76\u6210 URL\u3002

    \u957f\u89c6\u9891\u6bcf\u8f6e\u8981 8\u201316 \u5206\u949f\uff0c\u9010\u8f6e\u5bf9\u6bd4\u662f\u521a\u9700\u2014\u2014\u8fd9\u91cc\u4e0d\u91cd\u7b97\u4efb\u4f55\u4e1c\u897f\uff0c\u53ea\u628a\u5df2\u6709\u4ea7\u7269\u66b4\u9732\u51fa\u6765\u3002
    """
    out = {"ready": False, "stop_reason": None, "champion": None, "rounds": []}
    outdir = job.get("outdir")
    if not outdir or not os.path.isdir(outdir):
        return out
    hist = os.path.join(outdir, "optimizer_history.json")
    if not os.path.isfile(hist):
        return out                      # \u4efb\u52a1\u8fd8\u6ca1\u7ed3\u675f\uff08_finalize \u624d\u4f1a\u5199\u8fd9\u4e2a\u6587\u4ef6\uff09
    try:
        with open(hist, encoding="utf-8") as fh:
            h = json.load(fh)
    except Exception as e:
        out["error"] = "\u8bfb\u53d6 optimizer_history.json \u5931\u8d25\uff1a%s" % e
        return out
    out["ready"] = True
    out["stop_reason"] = h.get("stop_reason")
    out["champion"] = h.get("champion")
    out["run"] = h.get("run") or {}          # \u542b budget_pred\uff08\u5f00\u8dd1\u524d\u7684\u9884\u7b97\u9884\u6d4b\uff09\u4e0e tokens\uff0c\u4f9b\u504f\u5dee\u6838\u5bf9

    def _url(p):
        try:
            if OUTPUT_DIR in p:
                return "/outputs/" + os.path.relpath(p, OUTPUT_DIR).replace("\\", "/")
        except Exception:
            pass
        return None

    for a in h.get("attempts") or []:
        d = os.path.join(outdir, a.get("label") or "")
        row = dict(a)
        row["videos"] = []
        row["files"] = {}
        if os.path.isdir(d):
            for fn, key in (("prompt.txt", "prompt"), ("script.json", "script"), ("meta.json", "meta")):
                u = _url(os.path.join(d, fn))
                if u and os.path.isfile(os.path.join(d, fn)):
                    row["files"][key] = u
            for root, _dirs, files in os.walk(d):
                for fn in sorted(files):
                    if fn.lower().endswith((".mp4", ".webm", ".mov", ".mkv")):
                        u = _url(os.path.join(root, fn))
                        if u:
                            row["videos"].append(u)
        row["video"] = _url(a.get("video") or "") or (row["videos"][0] if row["videos"] else None)
        out["rounds"].append(row)
    return out


def _mem_samples(model=None, limit=60):
    """\u4ece\u5386\u53f2\u4efb\u52a1\u91cc\u6536\u96c6"\u5b9e\u6d4b\u663e\u5b58\u5cf0\u503c"\u6837\u672c\uff0c\u4f9b\u663e\u5b58\u9884\u7b97\u6807\u5b9a\uff08\u540c\u6a21\u578b\u4f18\u5148\uff09\u3002

    \u6570\u636e\u6765\u6e90\uff1a\u6bcf\u4e2a\u4efb\u52a1\u7684 optimizer_history.json \u91cc\u7684 run.tokens \u4e0e attempts[].vram_peak_gb\uff0c
    \u540e\u8005\u7531 optimizer.render() \u5728\u91c7\u6837\u671f\u95f4\u8f6e\u8be2 ComfyUI /system_stats \u8bb0\u5f55\u4e0b\u6765\u3002
    """
    out = []
    try:
        for tid in sorted(os.listdir(OUTPUT_DIR)):
            hist = os.path.join(OUTPUT_DIR, tid, "optimizer_history.json")
            if not os.path.isfile(hist):
                continue
            try:
                with open(hist, encoding="utf-8") as fh:
                    h = json.load(fh)
            except Exception:
                continue
            run = h.get("run") or {}
            tk = run.get("tokens")
            m = run.get("model")
            if model and m and m != model:
                continue
            for a in (h.get("attempts") or []):
                pk = a.get("vram_peak_gb")
                if tk and pk:
                    out.append({"tokens": int(tk), "peak_gb": float(pk), "model": m, "job": tid,
                                "ram_extra_gb": a.get("ram_extra_gb")})
    except Exception:
        pass
    return out[-limit:]


class Handler(BaseHTTPRequestHandler):
    server_version = "Ref2VAUI/2.0"   # HTTP Server \u5934\u53ea\u80fd\u7528 ASCII\uff0c\u6545\u6b64\u5904\u4e0d\u653e\u4e2d\u6587\u4ea7\u54c1\u540d

    def log_message(self, fmt, *args):  # silence noisy default logs
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self, limit=64 * 1024 * 1024):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > limit:
            return b""
        return self.rfile.read(length)

    # ---- routes ----
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            f = os.path.join(WEB_DIR, "index.html")
            if os.path.isfile(f):
                self._send(200, open(f, "rb").read(), "text/html; charset=utf-8")
            else:
                self._send(500, "index.html missing")
        elif path == "/api/jobs":
            with LOCK:
                items = []
                for jid, j in JOBS.items():
                    items.append({"id": jid, "status": j["status"],
                                  "created": j["created"],
                                  "name": j.get("name", ""),
                                  "exit": j.get("exit"),
                                  "has_form": bool(j.get("form"))})
            items.sort(key=lambda x: x["created"], reverse=True)
            for it in items:
                it["position"] = _queue_position(it["id"])
            self._send(200, {"jobs": items})
        elif path == "/api/ping":
            # \u8f7b\u91cf\u72b6\u6001\u63a2\u6d4b\uff08\u53ea\u6253 /system_stats\uff09\uff1a\u7ed9\u9875\u9762\u9876\u90e8\u300cComfyUI \u5728\u7ebf\u300d\u6307\u793a\u706f\u7528
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            base = ((qs.get("comfy_url") or [""])[0] or "http://127.0.0.1:8000").rstrip("/")
            try:
                with urllib.request.urlopen(base + "/system_stats", timeout=5) as r:
                    st = json.load(r)
                dev = (st.get("devices") or [{}])[0]
                self._send(200, {"ok": True, "device": dev.get("name"),
                                 "vram_free_gb": round(dev.get("vram_free", 0) / 2**30, 1),
                                 "vram_total_gb": round(dev.get("vram_total", 0) / 2**30, 1),
                                 "version": (st.get("system") or {}).get("comfyui_version")})
            except Exception as e:
                self._send(200, {"ok": False, "error": type(e).__name__})
        elif path == "/api/doctor":
            # \u73af\u5883\u81ea\u68c0\uff1a\u8dd1\u957f\u4efb\u52a1\uff08\u4e00\u6b21 8\u201316 \u5206\u949f\uff09\u4e4b\u524d\u5148\u628a\u524d\u7f6e\u6761\u4ef6\u67e5\u6e05\u3002
            # \u6240\u9700\u8282\u70b9\u7531 core/doctor.py \u4ece\u5de5\u4f5c\u6d41\u6a21\u677f\u73b0\u8bfb\uff0c\u4e0d\u786c\u7f16\u7801\u3002
            if _doctor is None:
                self._send(500, {"error": "doctor \u6a21\u5757\u5bfc\u5165\u5931\u8d25"})
                return
            try:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

                def _q(k):
                    return (qs.get(k) or [""])[0]

                loras = [{"name": x.strip()} for x in (_q("loras") or "").split(",") if x.strip()]
                rep = _doctor.run_doctor(
                    comfy_url=_q("comfy_url") or "http://127.0.0.1:8000",
                    llm_base=_q("llm_base") or None,
                    llm_key=_q("llm_key") or None,
                    model=_q("model") or None,
                    clip=_q("clip") or None,
                    loras=loras,
                )
                self._send(200, rep)
            except Exception as e:
                self._send(500, {"error": "\u81ea\u68c0\u5931\u8d25\uff1a%s: %s" % (type(e).__name__, e)})
        elif path == "/api/models":
            if _ra is None:
                self._send(500, {"error": "ref2va_auto import failed"})
                return
            def uniq(seq):
                seen, out = set(), []
                for m in seq or []:
                    if m not in seen:
                        seen.add(m)
                        out.append(m)
                return out
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            cb = (qs.get("comfy_url") or [None])[0]
            def _rl(cls):
                return _ra._remote_object_list(cls, base=cb) if cb else _ra._remote_object_list(cls)
            result = {
                "unet": uniq(_rl("UNETLoader")) + uniq(_rl("UnetLoaderGGUF")),
                "clip": uniq(_rl("CLIPLoader")),
                "vae": uniq(_rl("VAELoader")),
                "lora": uniq(_rl("LoraLoaderModelOnly")),
                "samplers": uniq(_rl("KSamplerSelect")),
                "schedulers": uniq(_rl("BasicScheduler")),
                "llm_models": [],
            }
            try:
                lb = (qs.get("llm_base") or [None])[0]
                if lb:
                    result["llm_models"] = _llm_models(lb, (qs.get("llm_key") or [None])[0])
            except Exception:
                pass
            self._send(200, result)
        elif path == "/api/budget":
            # \u663e\u5b58/\u65f6\u957f\u9884\u7b97\u4f30\u8ba1\uff1atoken \u7cbe\u786e\uff0c\u5cf0\u503c\u8fd1\u4f3c\uff1b\u6709\u5b9e\u6d4b\u6837\u672c\u65f6\u6539\u7528\u4f60\u81ea\u5df1\u7684\u6570\u636e\u62df\u5408
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

            def _q(k, d=None):
                return (qs.get(k) or [d])[0]

            try:
                dur = float(_q("duration") or 10)
                mp = float(_q("megapixels") or 0.6)
            except (TypeError, ValueError):
                self._send(400, {"error": "duration / megapixels \u5fc5\u987b\u662f\u6570\u5b57"})
                return
            card = None
            try:
                card = float(_q("card_gb")) if _q("card_gb") else None
            except (TypeError, ValueError):
                card = None
            # \u663e\u5b58 + \u7cfb\u7edf\u5185\u5b58\u90fd\u95ee ComfyUI\uff08/system_stats\uff09\uff0c"\u80fd\u7528\u4f46\u4f1a\u6162"\u7684\u5224\u5b9a\u8981\u7528\u5230\u5185\u5b58
            ram_free = ram_total = None
            try:
                base0 = (_q("comfy_url") or "http://127.0.0.1:8000").rstrip("/")
                with urllib.request.urlopen(base0 + "/system_stats", timeout=5) as r:
                    st = json.load(r)
                dev = (st.get("devices") or [{}])[0]
                tot = float(dev.get("vram_total") or 0)
                if card is None:
                    card = round(tot / 2 ** 30, 1) if tot else 24.0
                sysinfo = st.get("system") or {}
                if sysinfo.get("ram_free"):
                    ram_free = round(float(sysinfo["ram_free"]) / 2 ** 30, 1)
                if sysinfo.get("ram_total"):
                    ram_total = round(float(sysinfo["ram_total"]) / 2 ** 30, 1)
            except Exception:
                if card is None:
                    card = 24.0
            try:
                mgb = float(_q("model_gb")) if _q("model_gb") else None
            except (TypeError, ValueError):
                mgb = None
            model = _q("model") or None
            clip = _q("clip") or None
            msrc = "client" if mgb else None
            samples = _mem_samples(model)
            try:
                import mem_budget as _mb
                base = _q("comfy_url") or "http://127.0.0.1:8000"
                if model and mgb is None:      # \u95ee ComfyUI \u8981\u771f\u5b9e\u4f53\u79ef\uff08\u8de8\u673a\u5668\u4e5f\u6210\u7acb\uff09
                    mgb, msrc = _mb.fetch_model_size_gb(base, model)
                cgb = None
                if clip:                       # \u6587\u672c\u7f16\u7801\u5668\uff08TE\uff09\u4f53\u79ef\uff1a\u7f16\u7801\u9636\u6bb5\u72ec\u7acb\u9a7b\u7559\uff0c\u503c\u5f97\u5355\u5217
                    cgb, _ = _mb.fetch_model_size_gb(base, clip, folders=("text_encoders", "clip"))
                est = _mb.estimate(dur, mp, card_gb=card, model=model, model_gb=mgb,
                                   size_source=msrc, samples=samples, clip=clip, clip_gb=cgb)
                est["samples_used"] = len(samples)
                est["summary"] = _mb.format_line(est)
                est["user"] = _mb.user_line(est)      # \u754c\u9762\u53ea\u8bf4"\u7ed3\u8bba + \u4e00\u53e5\u539f\u56e0"
                # \u4e94\u6bb5\u5f0f\uff08\u754c\u9762\u539f\u6837\u663e\u793a\uff09\uff1b\u5e26\u4e0a"\u5b9e\u6d4b\u6e32\u67d3\u671f\u5185\u5b58\u989d\u5916\u5360\u7528"\u2014\u2014\u5b83\u80fd\u9a8c\u8bc1 TE \u5230\u5e95\u5360\u591a\u5c11\u5185\u5b58
                _meas_ram = max([s.get("ram_extra_gb") or 0 for s in samples] or [0]) or None
                est["budget"] = _mb.budget_lines(est, ram_free, ram_total, measured_ram_gb=_meas_ram)
                est["ram_free_gb"] = ram_free
                est["ram_total_gb"] = ram_total
                est["measured_tail"] = samples[-5:]
                self._send(200, est)
            except Exception as e:
                self._send(500, {"error": "\u9884\u7b97\u4f30\u8ba1\u5931\u8d25\uff1a%s: %s" % (type(e).__name__, e)})
        elif path == "/api/defaults":
            # \u300c\u56de\u586b\u793a\u4f8b\u300d\uff1a\u76f4\u63a5\u8bfb examples/example_config.json\uff0c\u4fdd\u8bc1\u53ea\u6709\u4e00\u4e2a\u771f\u76f8\u6765\u6e90
            try:
                with open(os.path.join(HERE, "examples", "example_config.json"), encoding="utf-8") as fh:
                    self._send(200, json.load(fh))
            except Exception as e:
                self._send(500, {"error": "\u8bfb\u53d6\u793a\u4f8b\u914d\u7f6e\u5931\u8d25\uff1a%s" % e})
        elif path.startswith("/api/jobs/") and path.endswith("/rounds"):
            jid = path[len("/api/jobs/"):-len("/rounds")].strip("/")
            with LOCK:
                j = JOBS.get(jid)
            if not j:
                self._send(404, {"error": "job not found"})
                return
            self._send(200, _collect_rounds(j))
        elif path.startswith("/api/jobs/"):
            jid = path.rsplit("/", 1)[-1]
            with LOCK:
                j = JOBS.get(jid)
            if not j:
                self._send(404, {"error": "job not found"})
                return
            self._send(200, {"id": jid, "status": j["status"], "exit": j.get("exit"),
                             "log": j["log"][-120000:],
                             "outdir": j.get("outdir"),
                             "position": _queue_position(jid),
                             "form": j.get("form"),
                             "outputs": _collect_outputs(j) if j["status"] in ("done", "error") else {}})
        elif path.startswith("/outputs/"):
            rel = path[len("/outputs/"):]
            rel = re.sub(r"\.\.", "", rel).lstrip("/")
            fp = os.path.join(OUTPUT_DIR, rel)
            if os.path.isfile(fp):
                self._send(200, open(fp, "rb").read(),
                           "video/mp4" if fp.lower().endswith(".mp4") else "text/plain; charset=utf-8")
            else:
                self._send(404, "not found")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/cancel":
            try:
                payload = json.loads(self._read_body().decode("utf-8-sig")) or {}
            except Exception:
                payload = {}
            jid = payload.get("id")
            with LOCK:
                if not jid:
                    jid = _running_jid or (_pending[0] if _pending else None)
            if jid and _cancel_job(jid):
                with LOCK:
                    st = (JOBS.get(jid) or {}).get("status", "cancelled")
                self._send(200, {"id": jid, "cancelled": True, "status": st})
            else:
                self._send(404, {"error": "\u6ca1\u6709\u53ef\u7ec8\u6b62\u7684\u8fdb\u884c\u4e2d/\u6392\u961f\u4efb\u52a1"})
            return
        if path != "/api/run":
            self._send(404, {"error": "not found"})
            return
        try:
            payload = json.loads(self._read_body().decode("utf-8-sig"))
        except Exception as e:
            self._send(400, {"error": "bad json: %s" % e})
            return
        if not payload.get("story") or not payload.get("llm_base") or not payload.get("llm_model"):
            self._send(400, {"error": "story / llm_base / llm_model are required"})
            return

        tid = uuid.uuid4().hex[:10]
        task_dir = os.path.join(TASK_DIR, tid)
        up_dir = os.path.join(UPLOAD_DIR, tid)
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(up_dir, exist_ok=True)

        # save uploaded reference files (each with its own "what it references" note)
        refs, audios = [], []
        for f in payload.get("files") or []:
            try:
                data = base64.b64decode(f.get("data", ""))
            except Exception:
                continue
            name = _safe_name(f.get("name"))
            note = (f.get("note") or "").strip()
            kind = "audio" if name.lower().endswith((".wav", ".mp3", ".m4a", ".flac", ".ogg")) else "image"
            fp = os.path.join(up_dir, name)
            with open(fp, "wb") as fh:
                fh.write(data)
            entry = {"path": fp}
            if note:
                entry["note"] = note
            (audios if kind == "audio" else refs).append(entry)

        # ---- \u6d41\u7a0b\uff1aref2va\uff08\u9ed8\u8ba4\uff0c\u53c2\u8003\u56fe/\u89c6\u9891\uff09/ i2va\uff08\u9996\u5e27\u56fe\u751f\u89c6\u9891\uff0c\u82f1\u6587\u63d0\u793a\u8bcd\uff09----
        flow = (payload.get("flow") or "ref2va").strip().lower()
        if flow == "i2va":
            if not refs:
                self._send(400, {"error": "I2VA \u6d41\u7a0b\u5fc5\u987b\u4e0a\u4f20 1 \u5f20\u53c2\u8003\u56fe\u4f5c\u4e3a\u89c6\u9891\u9996\u5e27"})
                return
            refs = refs[:1]      # \u53ea\u53d6\u7b2c 1 \u5f20\u53c2\u8003\u56fe\u5f3a\u5236\u4f5c\u4e3a\u89c6\u9891\u7b2c\u4e00\u5e27
            audios = []          # I2V \u5de5\u4f5c\u6d41\u4e0d\u5403\u53c2\u8003\u97f3\u9891

        # ---- \u65f6\u957f\u6821\u9a8c\uff082.0\uff1a\u5355\u6b21\u751f\u6210\u4e0a\u9650 60 \u79d2\uff1b\u8d85\u9650\u76f4\u63a5 400\uff0c\u4e0d\u505a\u9759\u9ed8\u5939\u53d6\uff09----
        _dur, _derr = _ra.validate_duration(payload.get("duration"))
        if _derr:
            self._send(400, {"error": _derr})
            return

        # ---- \u4f4e\u663e\u5b58\u5206\u5757\u6821\u9a8c\uff08\u53ef\u9009\u529f\u80fd\uff1b\u975e\u6cd5\u503c\u76f4\u63a5 400\uff0c\u4e0d\u505a\u9759\u9ed8\u56de\u9000\uff09----
        _lv = {"low_vram": payload.get("low_vram") or "off",
               "chunk_chunks": payload.get("chunk_chunks"),
               "chunk_head_chunks": payload.get("chunk_head_chunks")}
        try:
            _lv_mode, _lv_chunks, _lv_heads = _ra.low_vram_settings(_lv)
        except ValueError as e:
            self._send(400, {"error": "\u4f4e\u663e\u5b58\u5206\u5757\u8bbe\u7f6e\u975e\u6cd5\uff1a%s" % e})
            return

        outdir = os.path.join(OUTPUT_DIR, tid)
        cfg = {
            "story": payload["story"],
            "flow": flow,
            "optimize_target": payload.get("optimize_target") or "overall quality and performance",
            "refs": refs,
            "audios": audios,
            "video_edit": bool(payload.get("video_edit")) and flow != "i2va",
            "video_ref": None,                       # B mode: optimizer auto-uses previous step's video
            "llm_base": payload["llm_base"],
            "llm_model": payload["llm_model"],
            "llm_api_key": (payload.get("llm_api_key") or None),
            "audio_llm_base": (payload.get("audio_llm_base") or None),
            "audio_llm_model": (payload.get("audio_llm_model") or None),
            "audio_llm_api_key": (payload.get("audio_llm_api_key") or None),
            "audio_scoring": payload.get("audio_scoring") or "off",
            "comfy_url": payload.get("comfy_url") or "http://127.0.0.1:8000",
            "model": (payload.get("model") or None),
            "clip": (payload.get("clip") or None),
            "weight_dtype": (payload.get("weight_dtype") or "default"),
            "ref_image_size": (payload.get("ref_image_size") or "match"),
            "low_vram": _lv_mode,
            "chunk_chunks": _lv_chunks,
            "chunk_head_chunks": _lv_heads,
            "review_frames": int(payload.get("review_frames") or 32),
            "loras": [{"name": (l.get("name") or "").strip(), "strength": float(l.get("strength") or 1.0)}
                      for l in (payload.get("loras") or []) if (l.get("name") or "").strip()],
            "sampler": payload.get("sampler") or "res_multistep",
            "scheduler": payload.get("scheduler") or "sgm_uniform",
            "steps": int(payload.get("steps") or 20),
            "seed": payload.get("seed"),
            "megapixels": float(payload.get("megapixels") or 0.6),
            "aspect": payload.get("aspect") or "16:9 (Widescreen)",
            "duration": _dur,
            "quick_render": bool(payload.get("quick_render")),
            "fine_render": bool(payload.get("fine_render")),
            "admission_threshold": float(payload.get("admission_threshold") or 5),
            "max_iterations": int(payload.get("max_iterations") or 12),
            "base_patience": int(payload.get("base_patience") or 3),
            "threshold": None,
            "stop_mode": "auto",
            "review_frame_width": 448,
            "review_frame_jpeg": True,
            "outdir": outdir,
        }
        cfg_path = os.path.join(task_dir, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)

        job = {"id": tid, "status": "queued", "log": "[server] \u5df2\u52a0\u5165\u961f\u5217\uff0c\u7b49\u5f85\u524d\u5e8f\u4efb\u52a1\u7ed3\u675f\u540e\u6267\u884c\u2026\n",
               "created": time.time(), "name": payload.get("name") or ("job " + tid),
               "outdir": outdir, "exit": None, "cfg_path": cfg_path, "form": _form_meta(payload)}
        with LOCK:
            JOBS[tid] = job
        _enqueue(tid)

        self._send(200, {"id": tid, "status": "queued", "outdir": outdir,
                         "queued": True, "position": _queue_position(tid)})


def main():
    print("MiniMAX H3 Ref2VA/I2VA \u89c6\u9891\u8d28\u91cf\u4f18\u5316\u5668 2.0\u6b63\u5f0f\u7248")
    print("web UI on http://%s:%s  (LAN: use your machine IP)" % (HOST, PORT))
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
