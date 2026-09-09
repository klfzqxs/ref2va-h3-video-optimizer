#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI \u517c\u5bb9 LLM \u5ba2\u6237\u7aef\uff08\u7eaf\u6807\u51c6\u5e93\uff09\uff1a\u6587\u672c / \u591a\u6a21\u6001 / \u97f3\u9891\u3002

\u7aef\u70b9\u3001\u6a21\u578b\u3001\u5bc6\u94a5\u9ed8\u8ba4\u53d6\u73af\u5883\u53d8\u91cf\uff08LLM_BASE_URL / LLM_API_KEY / REF2VA_LLM\uff09\uff0c
\u4e5f\u53ef\u5728\u6784\u9020\u65f6\u7528 model= / base= / api_key= \u8986\u76d6\u3002

\u7528\u6cd5:
  from llm import LLM
  llm = LLM()
  llm.chat(system, user)                # \u7eaf\u6587\u672c
  llm.chat_json(system, user)           # \u5f3a\u5236 JSON -> dict
  llm.vision(system, text, [image_b64]) # \u591a\u6a21\u6001
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
KEY = os.environ.get("LLM_API_KEY", "dummy")
MODEL = os.environ.get("REF2VA_LLM", "")

# \u5f3a\u5236\u65e0\u4ee3\u7406\u76f4\u8fde\uff1a\u907f\u514d urllib \u8bfb\u53d6\u7cfb\u7edf\u4ee3\u7406\u540e\u628a\u8bf7\u6c42\u8bef\u8def\u7531\u5230\u5931\u6548\u4ee3\u7406\u5bfc\u81f4\u5361\u6b7b
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class LLMError(RuntimeError):
    pass


def _clean_surrogates(obj):
    """\u9012\u5f52\u6e05\u7406\u5b57\u7b26\u4e32\u4e2d\u7684 lone surrogates\uff08Windows \u7ba1\u9053/\u63a7\u5236\u53f0\u7f16\u7801\u635f\u574f\u5e38\u89c1\uff09\u3002
    \u5426\u5219 json.dumps \u4f1a\u628a\u5b83\u8f6c\u4e49\u6210 \\udcXX \u53d1\u7ed9\u670d\u52a1\u5668\u5bfc\u81f4 JSON \u89e3\u6790 500\u3002"""
    if isinstance(obj, str):
        try:
            return obj.encode("utf-8", errors="replace").decode("utf-8")
        except Exception:
            return obj
    if isinstance(obj, list):
        return [_clean_surrogates(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _clean_surrogates(v) for k, v in obj.items()}
    return obj


def _extract_json(text):
    """\u4ece\u6a21\u578b\u6587\u672c\u4e2d\u89e3\u6790 JSON \u5bf9\u8c61\u3002\u5148\u8bd5\u6574\u4f53\uff0c\u518d\u5265\u4ee3\u7801\u5757\uff0c\u6700\u540e\u4ece\u540e\u5f80\u524d\u627e\u6700\u540e\u4e00\u4e2a\u5e73\u8861\u7684 {...}\u3002
    \u601d\u8003\u94fe\u6a21\u578b\u5e38\u628a\u601d\u8003\u8fc7\u7a0b\u4e0e\u6700\u7ec8 JSON \u62fc\u5728\u4e00\u8d77\uff08\u751a\u81f3\u53ea\u8fd4\u56de\u601d\u8003\uff09\uff0c\u8fd9\u4e2a\u51fd\u6570\u5c3d\u91cf\u62a0\u51fa\u6700\u7ec8\u7b54\u6848\u3002"""
    text = (text or "").strip()
    candidates = [text]
    if text.startswith("```"):
        t2 = text.split("\n", 1)[-1]
        if "```" in t2:
            t2 = t2.rsplit("```", 1)[0]
        candidates.append(t2.strip())
    for c in candidates:
        if not c:
            continue
        try:
            return json.loads(c)
        except Exception:
            pass
    # \u4ece\u540e\u5f80\u524d\u627e\u6700\u540e\u4e00\u4e2a\u5e73\u8861\u7684 {...} \u5757
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
                    candidate = text[j:i + 1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        break
    raise LLMError(f"\u6a21\u578b\u8f93\u51fa\u4e0d\u662f\u5408\u6cd5JSON: {text[:800]}")


class LLM:
    def __init__(self, model=None, base=None, api_key=None, temperature=0.6,
                 max_tokens=32000, timeout=3600):
        self.model = model or MODEL
        self.base = (base or BASE).rstrip("/") + "/chat/completions"
        self.key = api_key or KEY
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    # ---- \u5185\u90e8 ----
    def _call(self, messages, temperature=None, max_tokens=None, retries=5):
        payload = {
            "model": self.model,
            "messages": _clean_surrogates(messages),
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.key}"}
        last_exc = None
        import time
        for attempt in range(1, retries + 1):
            req = urllib.request.Request(self.base, data=body, headers=headers, method="POST")
            try:
                with _NO_PROXY_OPENER.open(req, timeout=self.timeout) as r:
                    resp = json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                last_exc = LLMError(f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:500]}")
                # 5xx \u670d\u52a1\u7aef\u9519\u8bef\u53ef\u91cd\u8bd5\uff1b4xx \u4e00\u822c\u4e0d\u4f1a\u56e0\u91cd\u8bd5\u597d\u8f6c
                if not (500 <= e.code <= 599):
                    raise last_exc
            except Exception as e:
                last_exc = LLMError(f"request failed: {e}")
            else:
                # \u8bf7\u6c42\u6210\u529f\uff1a\u68c0\u67e5 content\u3002\u601d\u8003\u94fe\u6a21\u578b\u53ef\u80fd\u53ea\u8f93\u51fa reasoning_content\uff08\u8fd8\u5728\u601d\u8003\uff09
                # \u800c content \u4e3a\u7a7a \u2014\u2014 \u6b64\u65f6\u89c6\u4e3a\u4e00\u6b21\u5931\u8d25\uff0c\u91cd\u8bd5\uff0c\u7edd\u4e0d\u8981\u628a\u601d\u8003\u6587\u672c\u5f53\u7b54\u6848\u8fd4\u56de\u3002
                try:
                    content = resp["choices"][0]["message"]["content"]
                except Exception:
                    content = None
                if content:
                    return content
                usage = resp.get("usage", {})
                last_exc = LLMError(
                    f"\u6a21\u578b\u53ea\u8fd4\u56de\u601d\u8003\u672a\u8f93\u51facontent (finish={resp['choices'][0].get('finish_reason')}, "
                    f"usage={json.dumps(usage, ensure_ascii=False)})\uff0c\u91cd\u8bd5")
            # \u6162\u6a21\u578b\u573a\u666f\u4e0b\u9000\u907f\u653e\u5bbd\uff1a5s/10s/20s/40s/60s
            time.sleep(min(5.0 * (2 ** (attempt - 1)), 60))
        raise last_exc or LLMError("request failed: unknown error")

    def _image_url(self, b64data):
        # \u6309 base64 \u524d\u7f00\u55c5\u63a2\u771f\u5b9e\u56fe\u7247\u683c\u5f0f\uff1aPNG -> iVBORw0KGgo\uff1bJPEG -> /9j/
        if b64data.startswith("/9j/"):
            mime = "image/jpeg"
        elif b64data.startswith("iVBORw0KGgo"):
            mime = "image/png"
        else:
            mime = "image/png"
        return {"type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64data}"}}

    # ---- \u516c\u5f00 ----
    def chat(self, system, user, temperature=None, max_tokens=None):
        """\u7eaf\u6587\u672c\u5bf9\u8bdd\uff0c\u8fd4\u56de\u5b57\u7b26\u4e32\u3002"""
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user})
        return self._call(msgs, temperature=temperature, max_tokens=max_tokens).strip()

    def chat_json(self, system, user, temperature=None, max_tokens=None):
        """\u5f3a\u5236 JSON \u8f93\u51fa\u3002\u5728 user \u91cc\u9644\u52a0 '\u53ea\u8f93\u51fa\u5408\u6cd5JSON\u5bf9\u8c61' \u7ea6\u675f\u3002"""
        user = (user.strip().rstrip(".") +
                "\n\n\u53ea\u8f93\u51fa\u4e00\u4e2a\u5408\u6cd5\u7684JSON\u5bf9\u8c61\uff08\u4e0d\u8981markdown\u4ee3\u7801\u5757\u3001\u4e0d\u8981\u5176\u4ed6\u4efb\u4f55\u6587\u5b57\uff09\u3002")
        text = self.chat(system, user, temperature, max_tokens)
        return _extract_json(text)

    def vision_json(self, system, user, image_b64_list, temperature=None, max_tokens=None):
        """\u591a\u6a21\u6001 + \u5f3a\u5236 JSON \u8f93\u51fa\uff1a\u628a base64 \u56fe\u4e0e\u6587\u672c\u4e00\u8d77\u53d1\u7ed9 LLM\uff0c\u8fd4\u56de\u89e3\u6790\u540e\u7684 JSON\u3002"""
        user = (user.strip().rstrip(".") +
                "\n\n\u53ea\u8f93\u51fa\u4e00\u4e2a\u5408\u6cd5\u7684JSON\u5bf9\u8c61\uff08\u4e0d\u8981markdown\u4ee3\u7801\u5757\u3001\u4e0d\u8981\u5176\u4ed6\u4efb\u4f55\u6587\u5b57\uff09\u3002")
        text = self.vision(system, user, image_b64_list, temperature, max_tokens)
        return _extract_json(text)

    def vision(self, system, user_text, image_b64_list, temperature=None,
               max_tokens=None):
        """\u591a\u6a21\u6001\uff1a\u4f20\u5165\u591a\u5f20 base64 PNG/JPEG\uff0c\u8fd4\u56de\u8bc4\u4f30\u6587\u672c\u3002"""
        if not image_b64_list:
            raise LLMError("vision \u8c03\u7528\u9700\u8981\u81f3\u5c11\u4e00\u5f20\u56fe\u7247")
        content = [{"type": "text", "text": user_text}]
        content.extend(self._image_url(b) for b in image_b64_list)
        msgs = ([{"role": "system", "content": system}] if system else [])
        msgs.append({"role": "user", "content": content})
        return self._call(msgs, temperature=temperature, max_tokens=max_tokens).strip()

    def encode_image(self, filepath):
        """\u8bfb\u53d6\u56fe\u7247\u6587\u4ef6\u5e76\u8f6c base64\u3002png/jpg/jpeg\u3002"""
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")

    def encode_audio(self, filepath):
        """\u8bfb\u53d6\u97f3\u9891\u6587\u4ef6\u5e76\u8f6c base64\u3002mp3/wav/m4a \u7b49\u3002"""
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")

    def audio(self, system, user_text, audio_b64, audio_format="wav",
              temperature=None, max_tokens=None):
        """\u591a\u6a21\u6001\uff1a\u4f20\u5165\u4e00\u6bb5 base64 \u97f3\u9891\uff08input_audio\uff09\uff0c\u8fd4\u56de\u6a21\u578b\u6587\u672c\uff08\u542c\u58f0/\u8bc6\u522b\uff09\u3002

        audio_format: \u97f3\u9891\u6269\u5c55\u540d\uff08wav/mp3/m4a\u2026\uff09\uff0c\u670d\u52a1\u7aef\u636e\u6b64\u89e3\u7801\u3002
        """
        content = [{"type": "text", "text": user_text},
                   {"type": "input_audio",
                    "input_audio": {"data": audio_b64, "format": audio_format}}]
        msgs = ([{"role": "system", "content": system}] if system else [])
        msgs.append({"role": "user", "content": content})
        return self._call(msgs, temperature=temperature, max_tokens=max_tokens).strip()


def _cli():
    import argparse
    p = argparse.ArgumentParser(description="LLM CLI\uff08\u5f00\u53d1/\u6d4b\u8bd5\u7528\uff09")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("chat"); s.add_argument("--system", default="")
    s.add_argument("user"); s.set_defaults(op="chat")
    s = sub.add_parser("vision"); s.add_argument("--system", default="")
    s.add_argument("user"); s.add_argument("images", nargs="+")
    s.set_defaults(op="vision")
    s = sub.add_parser("models"); s.set_defaults(op="models")
    a = p.parse_args()
    llm = LLM()
    if a.op == "models":
        req = urllib.request.Request(os.environ.get("LLM_BASE_URL", BASE).rstrip("/") + "/models",
                                     headers={"Authorization": f"Bearer {KEY}"})
        with _NO_PROXY_OPENER.open(req, timeout=30) as r:
            print(r.read().decode("utf-8", "replace"))
    elif a.op == "chat":
        print(llm.chat(a.system, a.user))
    elif a.op == "vision":
        print(llm.vision(a.system, a.user, [llm.encode_image(p) for p in a.images], temperature=0))


if __name__ == "__main__":
    _cli()
