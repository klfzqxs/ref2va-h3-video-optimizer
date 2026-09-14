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


class Handler(BaseHTTPRequestHandler):
    server_version = "Ref2VAUI/1.0"

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
            self._send(200, {"jobs": items})
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
            "loras": [{"name": (l.get("name") or "").strip(), "strength": float(l.get("strength") or 1.0)}
                      for l in (payload.get("loras") or []) if (l.get("name") or "").strip()],
            "sampler": payload.get("sampler") or "res_multistep",
            "scheduler": payload.get("scheduler") or "sgm_uniform",
            "steps": int(payload.get("steps") or 20),
            "seed": payload.get("seed"),
            "megapixels": float(payload.get("megapixels") or 0.6),
            "aspect": payload.get("aspect") or "16:9 (Widescreen)",
            "duration": float(payload.get("duration") or 10),
            "quick_render": bool(payload.get("quick_render")),
            "fine_render": bool(payload.get("fine_render")),
            "admission_threshold": float(payload.get("admission_threshold") or 5),
            "max_iterations": int(payload.get("max_iterations") or 12),
            "base_patience": int(payload.get("base_patience") or 3),
            "threshold": None,
            "stop_mode": "auto",
            "review_frames": 32,
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
    print("Ref2VA web UI on http://%s:%s  (LAN: use your machine IP)" % (HOST, PORT))
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
