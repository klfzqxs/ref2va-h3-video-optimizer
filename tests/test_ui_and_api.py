#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2.0 \u524d\u7aef\u4e0e\u63a5\u53e3\u9a8c\u8bc1\u3002

\u8fd0\u884c\uff1a python tests/test_ui_and_api.py

\u8986\u76d6\uff1a
  A. \u5185\u8054 JS \u8bed\u6cd5\uff08node --check\uff1b\u6ca1\u6709 node \u5219\u8df3\u8fc7\uff09
  B. \u4e34\u65f6\u670d\u52a1\u4e0a\u7684\u9996\u9875 / /api/ping / /api/doctor / \u65f6\u957f\u4e0a\u9650 400
  C. **\u4e0e\u73af\u5883\u65e0\u5173\u7684\u8d1f\u4f8b**\uff1a\u628a comfy_url \u6307\u5411\u4e0d\u53ef\u8fbe\u7aef\u53e3\uff0c\u81ea\u68c0\u5fc5\u987b\u62a5 error \u2014\u2014 
     \u5426\u5219"\u81ea\u68c0\u5168\u7eff"\u5c31\u6ca1\u6709\u8bc1\u660e\u529b\uff08\u68c0\u67e5\u5fc5\u987b\u80fd\u5931\u8d25\uff09\u3002

\u53ea\u53d1\u975e\u6cd5\u7684 /api/run \u8bf7\u6c42\uff0c\u4e0d\u4f1a\u771f\u7684\u6392\u961f\u6e32\u67d3\u3002
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PORT = 8098
BASE = "http://127.0.0.1:%d" % PORT
LIVE_COMFY = "http://127.0.0.1:8000"
fails, skips = [], []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "   -> " + str(detail)))
    if not cond:
        fails.append(name)


def skip(name, why):
    print("SKIP  " + name + "   -> " + why)
    skips.append(name)


class _ComfyOffline(Exception):
    """ComfyUI \u6ca1\u5728\u8dd1\uff1a\u5b9e\u673a\u68c0\u67e5\u6574\u5757\u8df3\u8fc7\uff08\u672c\u5957\u6d4b\u8bd5\u4e0d\u8be5\u4f9d\u8d56\u7528\u6237\u5f00\u7740 ComfyUI\uff09\u3002"""


# \u5b9e\u673a\u5757\u7528\u5230\u7684\u6807\u5fd7\uff1a\u63a2\u6d4b\u5230 ComfyUI \u5728\u7ebf\u624d\u7f6e True
_live = False


# ---------- A. \u5185\u8054 JS \u8bed\u6cd5 ----------
html = open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8").read()
blocks = [s for s in re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)]
js = "\n;\n".join(blocks)
tmp = os.path.join(tempfile.mkdtemp(prefix="h3_ui_"), "inline.js")
open(tmp, "w", encoding="utf-8").write(js)
print("\u62bd\u51fa JS %d \u5b57\u7b26 / %d \u4e2a <script> \u5757" % (len(js), len(blocks)))
try:
    r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
    check("\u5185\u8054 JS \u8bed\u6cd5\u68c0\u67e5", r.returncode == 0, (r.stderr or r.stdout)[:400])
except FileNotFoundError:
    skip("\u5185\u8054 JS \u8bed\u6cd5\u68c0\u67e5", "\u672a\u627e\u5230 node\uff08\u53ef\u9009\uff09")

check("\u9875\u9762\u6709\u300c\u73af\u5883\u81ea\u68c0\u300d\u6309\u94ae", "runDoctor()" in html)
check("\u9875\u9762\u6709 ComfyUI \u72b6\u6001\u706f", 'id="comfypill"' in html)
check("\u4ea7\u54c1\u540d\u5df2\u7edf\u4e00\u4e3a MiniMAX H3 Ref2VA/I2VA \u89c6\u9891\u8d28\u91cf\u4f18\u5316\u5668",
      "MiniMAX H3 Ref2VA/I2VA \u89c6\u9891\u8d28\u91cf\u4f18\u5316\u5668" in html)
check("\u9875\u9762\u7248\u672c\u53f7\u4e3a 2.0\u6b63\u5f0f\u7248", "2.0\u6b63\u5f0f\u7248" in html)
check("\u9875\u9762\u65e0\u65e7\u7248\u672c\u53f7/\u65e7\u540d\u6b8b\u7559",
      all(v not in html for v in ("1.0\u6b63\u5f0f\u7248", "1.1\u6b63\u5f0f\u7248", "1.2\u6b63\u5f0f\u7248"))
      and "Ref2VA \u89c6\u9891\u8d28\u91cf\u4f18\u5316\u5668" not in html.replace(
          "MiniMAX H3 Ref2VA/I2VA \u89c6\u9891\u8d28\u91cf\u4f18\u5316\u5668", ""))
check("\u7248\u672c\u53f7\u5728\u6807\u9898\u884c\u3001\u526f\u6807\u9898\u53ea\u7559\u4f5c\u8005",
      '\u89c6\u9891\u8d28\u91cf\u4f18\u5316\u5668 <span class="ver">2.0\u6b63\u5f0f\u7248</span></h1>' in html
      and '<span class="sub">\u4f5c\u8005 <a class="wb" href="https://weibo.com/u/2987585965"' in html)
check("\u5fae\u535a\u662f\u8d85\u94fe\u4e14\u5730\u5740\u6b63\u786e\uff08\u9875\u7709 + \u9875\u811a\uff09",
      html.count('href="https://weibo.com/u/2987585965"') >= 2
      and html.count('>\u5fae\u535a@\u5feb\u4e50\u80a5\u5b85\u5e86\u5148\u68ee</a>') >= 2)

# \u9759\u6001\u4e00\u81f4\u6027\uff1aJS \u91cc $('id') \u5f15\u7528\u7684\u5143\u7d20\u5fc5\u987b\u90fd\u5728 HTML \u91cc\u5b58\u5728\uff08\u624b\u6539\u5355\u6587\u4ef6 UI \u6700\u5bb9\u6613\u6f0f\u7684\u4e00\u7c7b\u9519\uff09
ids = set(re.findall(r"\$\('([A-Za-z_][A-Za-z0-9_]*)'\)", js))
missing_ids = sorted(i for i in ids if ('id="%s"' % i) not in html)
check("JS \u5f15\u7528\u7684\u5143\u7d20\u90fd\u5b58\u5728\uff08\u5171 %d \u4e2a id\uff09" % len(ids), not missing_ids, missing_ids)

# P1 \u529f\u80fd\u9f50\u5907\u6027
check("\u6298\u53e0\u673a\u5236\uff08foldh / foldstop / initFolders\uff09",
      "foldh" in html and "foldstop" in html and "initFolders" in html)
head = html.split("<script>")[0]        # \u53ea\u7edf\u8ba1 HTML \u90e8\u5206\uff0c\u907f\u514d\u628a JS \u91cc\u7684\u5b57\u7b26\u4e32\u7b97\u8fdb\u6765
foldh = len(re.findall(r'class="foldh"', head))
fold_attr = len(re.findall(r"data-fold(?![-a-z])", head))
fold_closed = len(re.findall(r"data-fold-closed", head))
check("\u6298\u53e0\u5757\u6570\u91cf\u4e00\u81f4\uff08%d \u4e2a\u53ef\u6298\u53e0\uff0c\u5176\u4e2d\u9ed8\u8ba4\u6536\u8d77 %d \u4e2a\uff09" % (foldh, fold_closed),
      foldh == fold_attr and foldh >= fold_closed and foldh > 0, (foldh, fold_attr, fold_closed))
check("\u9010\u8f6e\u7ed3\u679c\uff1a\u6e32\u67d3\u51fd\u6570 + \u63a5\u53e3 + \u5bb9\u5668", all(x in html for x in ("renderRounds", "/rounds", 'id="rounds"')))
check("\u4e00\u952e\u590d\u5236\uff1a\u6700\u4f18\u63d0\u793a\u8bcd/\u5267\u672c/\u9010\u8f6e", all(x in html for x in ("copyChampion", "copyFromUrl", "copyText")))
check("\u914d\u7f6e\uff1a\u5bfc\u51fa/\u56de\u586b/\u6e05\u7a7a", all(x in html for x in ("exportConfig()", "fillExample()", "resetForm()")))
check("toast \u901a\u77e5\u4e0e\u515c\u5e95\u526a\u8d34\u677f", 'id="toast"' in html and "execCommand('copy')" in html)
check("ref_image_size \u9009\u62e9\uff08match/max\uff09",
      'id="ref_image_size"' in html and 'value="max"' in html)
check("\u8bc4\u5ba1\u62bd\u5e27\u6570\u53ef\u8c03", 'id="review_frames"' in html)
check("\u663e\u5b58\u9884\u7b97\u9762\u677f\u5b58\u5728", 'id="budgetBox"' in html and "calcBudget" in html)
check("LLM \u7aef\u70b9\u6807\u9898\u5199\u660e\u300c\u5fc5\u987b\u662f\u80fd\u770b\u56fe\u7684\u591a\u6a21\u6001\u6a21\u578b\u300d\uff08\u672c\u5730/\u5185\u7f51/\u4e91\u7aef\uff09",
      "\u5fc5\u987b\u662f\u53ef\u4ee5\u770b\u56fe\u7684\u591a\u6a21\u6001\u6a21\u578b\uff0c\u652f\u6301\u672c\u5730\u3001\u5185\u7f51\u6216\u4e91\u7aef API\uff0c\u4e91\u7aef API \u9700\u81ea\u5907 API-Key" in html)
check("\u9884\u7b97\u9762\u677f\u7528\u63a5\u53e3\u800c\u975e\u524d\u7aef\u590d\u5236\u516c\u5f0f", "/api/budget?" in html or "'/api/budget?" in html)
check("\u663e\u5b58\u9884\u7b97\u6807\u6ce8\u4e3a\u6d4b\u8bd5\u529f\u80fd", "\u663e\u5b58\u9884\u7b97\u4f30\u8ba1\uff08\u6d4b\u8bd5\u529f\u80fd\uff09" in html)
# \u6548\u679c\u884c\u53ea\u7559\u7ed3\u8bba\uff08\u4e0d\u53ef\u7528\u52a0\u7c97\u6807\u7ea2\uff09\uff0c\u7406\u7531\u4e00\u5f8b\u6298\u53e0\u8fdb\u300c\u6280\u672f\u7ec6\u8282\u300d
_eff = html.find('\u9884\u8ba1\u4f7f\u7528\u6548\u679c\uff1a<b class="eff')
_det = html.find("<details style=\"margin-top:6px\"><summary", _eff)
check("\u6548\u679c\u884c\u53ea\u7559\u7ed3\u8bba\u3001\u7406\u7531\u5168\u90e8\u6536\u8fdb\u6280\u672f\u7ec6\u8282",
      _eff > 0 and _det > _eff and "b.why" not in html[_eff:_det],
      html[_eff:_eff + 120] if _eff > 0 else "\u672a\u627e\u5230\u6548\u679c\u884c")
check("\u300c\u4e0d\u53ef\u7528\u300d\u52a0\u7c97\u6807\u7ea2",
      'const effCls=(b.effect===\'\u4e0d\u53ef\u7528\')?\'bad\'' in html
      and 'class="eff ${effCls}"' in html and "b.eff.bad{color:var(--bad)}" in html)
check("\u300c\u4e0d\u53ef\u7528\u300d\u65f6\u70b9\u8fd0\u884c\u4f1a\u5148\u5f39\u5bf9\u8bdd\u6846\u7ed9\u7406\u7531\u3001\u53ef\u5f3a\u884c\u7ee7\u7eed",
      "async function budgetGate" in html and "confirm(" in html
      and "gate==='cancel'" in html and "gate==='forced'" in html
      and "const gate=await budgetGate()" in html)
check("\u9884\u7b97\u6587\u6848\u91cc\u7684 **\u5f3a\u8c03** \u4f1a\u6e32\u67d3\u6210\u7c97\u4f53\uff08\u4e0d\u662f\u5b57\u9762\u661f\u53f7\uff09",
      "function mdBold" in html and "mdBold(b.why" in html)
check("\u63d0\u4f9b\u504f\u5dee\u8bb0\u5f55\u590d\u5236\u4e0e issue \u5165\u53e3",
      "copyBudgetReport" in html and "issues/new" in html and "\u590d\u5236\u504f\u5dee\u8bb0\u5f55" in html)
# \u63d0\u4ea4 payload \u5fc5\u987b\u771f\u7684\u5e26\u4e0a\u65b0\u5b57\u6bb5\uff0c\u5426\u5219 UI \u9009\u4e86\u4e5f\u4e0d\u751f\u6548\uff08\u8fd9\u7c7b"\u9009\u9879\u6ca1\u63a5\u7ebf"\u7684\u6f0f\u6d1e\u4e0d\u62a5\u9519\u3001\u53ea\u9759\u9ed8\u7528\u9ed8\u8ba4\u503c\uff09
_payload = html.split("const payload={", 1)[1].split("};", 1)[0] if "const payload={" in html else ""
for _f in ("weight_dtype", "ref_image_size", "review_frames",
           "low_vram", "chunk_chunks", "chunk_head_chunks"):
    check("\u63d0\u4ea4 payload \u542b %s" % _f, (_f + ":") in _payload)
check("\u9875\u9762\u6709 weight_dtype \u9009\u62e9", 'id="weight_dtype"' in html)
# \u4f4e\u663e\u5b58\u5206\u5757\uff1a\u9ed8\u8ba4\u5fc5\u987b\u5173\uff0c\u4e09\u6863\u9f50\u5168\uff0c\u4e14\u5206\u5757\u6570\u53ef\u8c03
check("\u4f4e\u663e\u5b58\u5206\u5757\uff1a\u9009\u62e9\u5668\u4e09\u6863\u9f50\u5168\uff08off/mlp/mlp_attn\uff09",
      'id="low_vram"' in html and 'value="off"' in html
      and 'value="mlp"' in html and 'value="mlp_attn"' in html)
check("\u4f4e\u663e\u5b58\u5206\u5757\uff1a\u5206\u5757\u6570\u53ef\u8c03",
      'id="chunk_chunks"' in html and 'id="chunk_head_chunks"' in html)
check("\u4f4e\u663e\u5b58\u5206\u5757\uff1a\u754c\u9762\u5199\u660e\u4f1a\u6539\u53d8\u8f93\u51fa\u4f4d\u3001\u6574\u8f6e\u9700\u56fa\u5b9a",
      "\u5b83\u4f1a\u6539\u53d8\u8f93\u51fa\u4f4d" in html and "\u6574\u8f6e\u4f18\u5316\u671f\u95f4\u5fc5\u987b\u4fdd\u6301\u540c\u4e00\u8bbe\u7f6e" in html)
check("\u914d\u7f6e\u5bfc\u51fa/\u56de\u586b\u4e5f\u5e26\u4e0a\u4f4e\u663e\u5b58\u5206\u5757\u5b57\u6bb5",
      "'low_vram','chunk_chunks','chunk_head_chunks'" in html)
check("weight_dtype \u53ea\u63d0\u4f9b\u5408\u6cd5\u53d6\u503c",
      "fp8_e4m3fn_fast" in html and "fp16" not in html.split('id="weight_dtype"')[1].split("</select>")[0])
check("\u9875\u9762\u6709 IndexedDB \u53c2\u8003\u56fe\u6301\u4e45\u5316", "indexedDB.open" in html and "IDB_REF_KEY" in html)

# ---------- B/C. \u63a5\u53e3 ----------
env = dict(os.environ)
env.update(PORT=str(PORT), HOST="127.0.0.1", PYTHONIOENCODING="utf-8")
proc = subprocess.Popen([sys.executable, "-u", "server.py"], cwd=ROOT, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    up = False
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/", timeout=1)
            up = True
            break
        except Exception:
            time.sleep(0.25)
    check("\u4e34\u65f6\u670d\u52a1\u5c31\u7eea", up)
    if up:
        with urllib.request.urlopen(BASE + "/", timeout=10) as r:
            body = r.read().decode("utf-8", "replace")
        check("\u9996\u9875 200 \u4e14\u542b\u65b0 UI", "runDoctor" in body)

        def getj(path, timeout=60):
            with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
                return r.status, json.load(r)

        # C. \u8d1f\u4f8b\uff1a\u4e0d\u53ef\u8fbe\u7684 ComfyUI \u5fc5\u987b\u88ab\u5224\u4e3a error\uff08\u4e0e\u73af\u5883\u65e0\u5173\uff0c\u4efb\u4f55\u673a\u5668\u90fd\u6210\u7acb\uff09
        s, j = getj("/api/doctor?comfy_url=http://127.0.0.1:9", timeout=30)
        lv = [c["level"] for c in j.get("checks", [])]
        check("\u81ea\u68c0\u5bf9\u4e0d\u53ef\u8fbe\u7684 ComfyUI \u62a5 error", s == 200 and "error" in lv, j.get("summary"))
        check("\u81ea\u68c0\u7ed3\u8bba ok=false", j.get("ok") is False, j.get("ok"))

        # \u5b9e\u673a\uff08ComfyUI \u5728\u7ebf\u65f6\uff09
        try:
            s, j = getj("/api/ping?comfy_url=" + urllib.parse.quote(LIVE_COMFY), timeout=15)
            if not j.get("ok"):
                raise _ComfyOffline("ComfyUI \u672a\u8fd0\u884c\u6216\u4e0d\u53ef\u8fbe\uff1a%s" % LIVE_COMFY)
            _live = True
            check("/api/ping \u62a5\u544a ComfyUI \u5728\u7ebf", True, j)
            check("/api/ping \u5e26\u663e\u5b58\u4fe1\u606f", j.get("vram_free_gb") is not None, j)
            s, j = getj("/api/doctor?comfy_url=" + urllib.parse.quote(LIVE_COMFY))
            _ids = [c["id"] for c in j.get("checks", [])]
            check("/api/doctor \u8fd4\u56de\u73af\u5883\u68c0\u67e5\u9879\uff08ffmpeg / ComfyUI / \u8282\u70b9 / \u6a21\u578b\u5217\u8868 / LLM\uff09",
                  all(k in _ids for k in ("ffmpeg", "comfy", "nodes", "model_list", "llm")),
                  _ids)
            # \u751f\u6210\u5206\u652f\u662f\u540e\u53f0\u6309\u65f6\u957f\u81ea\u52a8\u9009\u7684\u7b56\u7565\uff0c\u4e0d\u5728\u524d\u7aef/\u81ea\u68c0\u91cc\u4f53\u73b0
            check("/api/doctor \u4e0d\u542b\u751f\u6210\u5206\u652f\u63d0\u793a\uff08\u540e\u53f0\u7b56\u7565\uff0c\u524d\u7aef\u4e0d\u4f53\u73b0\uff09",
                  not any(c["id"] == "branch" or "\u5206\u652f" in c["detail"] or "\u5206\u652f" in c["label"]
                          for c in j["checks"]),
                  [c["label"] for c in j["checks"]])
            # \u663e\u5b58\u9884\u7b97\u5728\u9875\u9762\u4e0a\u662f\u72ec\u7acb\u6309\u94ae\uff08/api/budget\uff09\uff0c\u81ea\u68c0\u91cc\u4e0d\u518d\u91cd\u590d\u62a5\u4e00\u904d
            check("/api/doctor \u4e0d\u518d\u91cd\u590d\u663e\u5b58\u9884\u7b97\u9879",
                  not any(c["id"] == "budget" or "\u9884\u7b97" in c["label"] for c in j["checks"]),
                  [c["label"] for c in j["checks"]])
            check("/api/doctor \u4e0d\u518d\u62a5\u6587\u672c\u7f16\u7801\u5668\u4f53\u79ef\u63d0\u793a\uff08\u5f52\u5165\u663e\u5b58\u9884\u7b97\uff09",
                  not any(c["id"] == "clip_profile" or "\u6587\u672c\u7f16\u7801\u5668" in c["label"] for c in j["checks"]),
                  [c["label"] for c in j["checks"]])
            check("/api/doctor \u4e5f\u4e0d\u542b\u9884\u7b97\u6b63\u6587\uff08DiT/TE/Token \u4e09\u6bb5\u5f0f\uff09",
                  not any("\u9884\u4f30\u6a21\u578b\uff08DiT\uff09\u5360\u7528\u91cf" in c["detail"] for c in j["checks"]),
                  [c["detail"][:40] for c in j["checks"]])
            # \u4f4e\u663e\u5b58\u5206\u5757\u7528\u7684\u4e24\u4e2a KJNodes \u8282\u70b9\uff1a\u5b9e\u673a\u5fc5\u987b\u5b58\u5728\uff08\u7f3a\u4e86 Doctor \u4f1a\u62a5"\u53ef\u9009\u8282\u70b9\u7f3a\u5931"\uff09
            _lvmiss = [c["id"] for c in j["checks"]
                       if c["id"] in ("opt_MiniMaxChunkFeedForward", "opt_MiniMaxLowVRAMAttention")]
            check("\u4f4e\u663e\u5b58\u5206\u5757\u6240\u9700\u8282\u70b9\uff08KJNodes\uff09\u5b9e\u673a\u5b58\u5728", not _lvmiss, _lvmiss)
        except _ComfyOffline as e:
            skip("\u5b9e\u673a\u68c0\u67e5\uff08ping / doctor / \u4f4e\u663e\u5b58\u8282\u70b9\uff09", str(e))
        except Exception as e:
            skip("\u5b9e\u673a\u81ea\u68c0\u68c0\u67e5", "ComfyUI \u672a\u8fd0\u884c\u6216\u4e0d\u53ef\u8fbe\uff08%s\uff09" % type(e).__name__)

        # \u65f6\u957f\u4e0a\u9650\uff08\u53ea\u53d1\u975e\u6cd5\u8bf7\u6c42\uff09
        req = urllib.request.Request(BASE + "/api/run", method="POST",
                                     data=json.dumps({"story": "t", "llm_base": "http://127.0.0.1:9/v1",
                                                      "llm_model": "x", "duration": 120}).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=10)
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        check("duration=120 \u88ab 400 \u62d2\u7edd", code == 400, code)

        # \u65b0\u589e\u63a5\u53e3
        s, j = getj("/api/defaults")
        check("/api/defaults \u8fd4\u56de\u793a\u4f8b\u914d\u7f6e", s == 200 and "story" in j and "llm_base" in j, list(j)[:6])

        # \u663e\u5b58\u9884\u7b97\u4f30\u8ba1
        s, j = getj("/api/budget?duration=60&megapixels=1.0&card_gb=24")
        check("/api/budget token \u6570\u7cbe\u786e\uff08417179\uff09", j.get("tokens") == 417179, j.get("tokens"))
        check("/api/budget \u5224\u8d85\u5305\u7ebf\u5e76\u7ed9\u51fa\u5efa\u8bae",
              j.get("token_verdict") == "over" and j.get("max_duration_s_at_this_mp"),
              (j.get("token_verdict"), j.get("max_duration_s_at_this_mp")))
        check("/api/budget \u672a\u6807\u5b9a\u65f6\u4e0d\u7ed9\u7eff\u706f", j.get("peak_verdict") == "uncalibrated", j.get("peak_verdict"))
        check("/api/budget \u8fd4\u56de\u6a21\u578b\u6863\u6848\u5b57\u6bb5", "model_profile" in j and "model_notes" in j, list(j)[:8])
        check("/api/budget \u540c\u65f6\u7ed9\u6280\u672f\u53e3\u5f84(summary)\u4e0e\u7528\u6237\u53e3\u5f84(user/budget)",
              "token" in (j.get("summary") or "") and "reason" in (j.get("user") or {})
              and len((j.get("budget") or {}).get("lines") or []) >= 4,
              {"summary": (j.get("summary") or "")[:40], "lines": len((j.get("budget") or {}).get("lines") or [])})
        if _live:
            check("/api/budget \u53ef\u7528\u603b\u91cf\u6263\u9664\u4e86 TE\uff08\u5185\u5b58\u884c\u5b58\u5728\uff09",
                  any(x["label"] == "\u6e32\u67d3\u9636\u6bb5\u53ef\u7528\u603b\u91cf" for x in (j.get("budget") or {}).get("lines") or []),
                  [x["label"] for x in (j.get("budget") or {}).get("lines") or []])
        else:
            skip("/api/budget \u53ef\u7528\u603b\u91cf\uff08\u9700\u8981\u5b9e\u673a\u5185\u5b58\u8bfb\u6570\uff09", "ComfyUI \u79bb\u7ebf")
        s, j = getj("/api/budget?duration=30&megapixels=0.6&card_gb=24")
        check("/api/budget \u5305\u7ebf\u5185\u5224\u5b9a\u4e3a ok", j.get("token_verdict") == "ok", j.get("token_verdict"))
        try:
            getj("/api/budget?duration=abc")
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        check("/api/budget \u975e\u6cd5\u53c2\u6570\u8fd4\u56de 400", code == 400, code)

        # \u4e0d\u5b58\u5728\u7684\u4efb\u52a1\uff1arounds \u5fc5\u987b 404\uff08\u800c\u4e0d\u662f 500/\u6302\u8d77\uff09
        try:
            getj("/api/jobs/nonexistent-id/rounds", timeout=10)
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        check("/api/jobs/<\u4e0d\u5b58\u5728>/rounds \u8fd4\u56de 404", code == 404, code)
finally:
    proc.terminate()
    try:
        proc.communicate(timeout=5)
    except Exception:
        proc.kill()

print()
print("checks:", "ALL PASS" if not fails else "%d FAILED" % len(fails),
      ("(%d skipped)" % len(skips)) if skips else "")
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
