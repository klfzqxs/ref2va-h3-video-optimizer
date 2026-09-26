#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\u957f\u89c6\u9891\u5ba2\u89c2\u6307\u6807\uff08\u7eaf\u6807\u51c6\u5e93 + ffmpeg\uff0c\u65e0\u7b2c\u4e09\u65b9\u4f9d\u8d56\uff09\u3002

\u4e3a\u4ec0\u4e48\u9700\u8981\u5b83
------------
\u5355\u6b21\u751f\u6210\u8d85\u8fc7 H3 \u8bad\u7ec3\u8303\u56f4\uff08\u5b98\u65b9 ~124\u2013362 \u5e27 = 5\u201315 \u79d2\uff09\u4e4b\u540e\uff0c\u753b\u9762\u9000\u5316\u6709\u56fa\u5b9a\u7684\u51e0\u79cd\u5f62\u6001\uff0c
\u800c\u8fd9\u4e9b\u5f62\u6001**\u7528"\u5747\u5300\u62bd N \u5e27\u4ea4\u7ed9\u89c6\u89c9 LLM \u770b"\u6293\u4e0d\u4f4f**\uff0c\u5c24\u5176\u662f\u5c3e\u90e8\uff1a

  * \u5c3e\u90e8\u8fd0\u52a8\u8870\u51cf\uff08\u4e8b\u4ef6\u88ab\u7528\u5b8c\uff0c\u753b\u9762\u524d\u666f\u8d8b\u4e8e\u505c\u6ede\uff09
  * \u5185\u5bb9\u590d\u8bfb / \u7ed5\u56de\u5f00\u5934\uff08\u957f\u7247\u6bb5\u5728\u540e\u6bb5\u91cd\u73b0\u5f00\u5934\u573a\u666f\uff09
  * \u5149\u7167\u4e0e\u8272\u5f69\u8d8b\u4e8e\u6052\u5b9a\u3001\u5bf9\u6bd4\u5ea6\u4e0b\u6ed1\uff08\u957f\u7247"\u51b7\u7070\u4f4e\u9971\u548c"\uff09

\u672c\u6a21\u5757\u628a\u89c6\u9891\u964d\u91c7\u6837\u6210\u4e00\u6761\u5f88\u7a84\u7684\u7070\u5ea6\u65f6\u95f4\u5e8f\u5217 + \u9996\u672b\u5f69\u8272\u5e27 + \u9996\u5c3e\u97f3\u9891\u7535\u5e73\uff0c
\u7eaf Python \u7b97\u51fa**\u53ef\u5224\u5b9a\u7684\u6570\u5b57**\uff0c\u4f9b\u65e5\u5fd7\u4e0e\u8bc4\u5ba1\u63d0\u793a\u8bcd\u5f15\u7528\uff08LLM \u53ea\u8d1f\u8d23\u89e3\u91ca\uff0c\u4e0d\u8d1f\u8d23\u53d1\u73b0\uff09\u3002

\u9608\u503c\u6765\u6e90\uff08\u672c\u9879\u76ee 2026-09 \u5728 512\u00b2/8 \u6b65\u4e0a\u7684\u5b9e\u6d4b\uff0c\u89c1 D:\\H3-longvideo\\REPORT.md\uff09\uff1a
  \u5bf9\u6bd4\u5ea6\uff1a15 s 62.5 / 30 s 61.6 / 60 s 74.8 / 90 s 30.0\uff0890 \u79d2\u8170\u65a9\uff09
  \u8272\u5f69\u6f02\u79fb\uff1a15 s 24.2 / 30 s 46.9 / 60 s 17.0 / 90 s 3.0\uff083.0 = \u5168\u7247\u8272\u8c03\u51e0\u4e4e\u4e0d\u53d8\uff09
  \u5c3e\u90e8/\u5168\u7247\u8fd0\u52a8\u6bd4\uff1a\u5206\u955c\u5f0f 30 s 0.46\uff1b\u6052\u5b9a\u8fd0\u52a8 0.55\u20130.94\uff08<0.7 \u89c6\u4e3a\u8870\u51cf\uff09

\u4efb\u4f55\u4e00\u6b65\u5931\u8d25\u90fd\u53ea\u662f\u5c11\u4e00\u4e2a\u6570\u5b57\uff0c**\u7edd\u4e0d\u5f71\u54cd\u4e3b\u6d41\u7a0b**\u3002
"""
import os
import re
import shutil
import subprocess

# ---- \u5c3a\u5bf8\u4e0e\u65f6\u57fa -------------------------------------------------------------
GRAY_SIZE = 32           # \u7070\u5ea6\u5e8f\u5217\u6bcf\u5e27 32x32\uff081024 \u50cf\u7d20\u8db3\u591f\u6d4b\u8fd0\u52a8/\u590d\u8bfb/\u4eae\u5ea6\uff09
SAMPLE_FPS = 2.0         # \u6bcf\u79d2 2 \u5e27\uff1a1 fps \u65f6"\u8fd0\u52a8\u2192\u51bb\u7ed3"\u7684\u8df3\u53d8\u4f1a\u63a9\u76d6\u51bb\u7ed3\uff08\u5b9e\u6d4b\u8e29\u8fc7\uff09\uff0c2 fps \u624d\u7a33\u5065
MAX_SAMPLES = 600        # \u4e0a\u9650\u4fdd\u62a4

# ---- \u5224\u5b9a\u9608\u503c ---------------------------------------------------------------
TH_TAIL_RATIO = 0.70     # \u5c3e\u90e8\u8fd0\u52a8 / \u5168\u7247\u8fd0\u52a8\uff0c\u4f4e\u4e8e\u6b64\u5224\u4e3a"\u5c3e\u90e8\u8870\u51cf"
TH_FROZEN = 0.15         # \u5168\u7247\u8fd1\u9759\u6b62\u5e27\u5360\u6bd4\u4e0a\u9650
TH_TAIL_FROZEN = 0.50    # \u5c3e\u90e8\u7a97\u53e3\u5185\u8fd1\u9759\u6b62\u5e27\u5360\u6bd4\uff0c\u8d85\u8fc7\u6b64\u5224\u4e3a"\u5c3e\u90e8\u51bb\u7ed3"
TH_REPLAY = 0.95         # \u590d\u8bfb\u76f8\u5173\uff1a\u4ec5\u4f5c\u8f85\u52a9\u8bc1\u636e\uff08\u8be5\u6307\u6807\u57fa\u7ebf\u9ad8\uff0c\u89c1\u4e0b\uff09
TH_AUDIO_TAIL_DB = -10.0  # \u5c3e\u90e8\u76f8\u5bf9\u9996\u90e8\u7684\u7535\u5e73\u5dee\uff08dB\uff09\uff0c\u4f4e\u4e8e\u6b64\u5224\u4e3a"\u5c3e\u90e8\u97f3\u9891\u53d8\u5f31"
TH_CONTRAST_DROP = 0.65  # \u5c3e\u90e8\u5bf9\u6bd4\u5ea6 / \u9996\u90e8\u5bf9\u6bd4\u5ea6\uff0c\u4f4e\u4e8e\u6b64\u5224\u4e3a"\u5bf9\u6bd4\u5ea6\u4e0b\u6ed1"
TH_COLOR_DRIFT = 6.0     # \u9996\u672b\u5f69\u8272\u5e27 RGB \u901a\u9053\u6700\u5927\u5dee\uff1b\u4f4e\u4e8e\u6b64\u5224\u4e3a"\u8272\u8c03\u51e0\u4e4e\u4e0d\u53d8"
TH_FROZEN_DIFF = 1.0     # \u5355\u50cf\u7d20\u7070\u5ea6\u5dee\uff080-255\uff09\u5c0f\u4e8e\u6b64\u89c6\u4e3a\u8be5\u5e27\u8fd1\u9759\u6b62


def ffmpeg_available():
    return bool(shutil.which("ffmpeg"))


def _run(args, timeout=180):
    return subprocess.run(args, capture_output=True, timeout=timeout)


def duration_of(video, default=0.0):
    """\u7528 ffmpeg -i \u8bfb\u65f6\u957f\uff08\u79d2\uff09\u3002\u5931\u8d25\u8fd4\u56de default\u3002"""
    try:
        r = _run(["ffmpeg", "-hide_banner", "-i", video])
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr.decode("utf-8", "replace"))
        if not m:
            return default
        h, mm, s = m.groups()
        return int(h) * 3600 + int(mm) * 60 + float(s)
    except Exception:
        return default


def gray_series(video, fps=SAMPLE_FPS, size=GRAY_SIZE, max_samples=MAX_SAMPLES):
    """\u62bd\u6210\u7070\u5ea6\u65f6\u95f4\u5e8f\u5217\uff1a\u8fd4\u56de (frames, w, h)\uff0c\u6bcf\u5e27\u4e3a bytes\uff08length = w*h\uff09\u3002"""
    w = h = int(size)
    r = _run(["ffmpeg", "-v", "error", "-i", video, "-an", "-sn",
              "-vf", "fps=%g,scale=%d:%d:flags=bilinear,format=gray" % (fps, w, h),
              "-frames:v", str(int(max_samples)), "-f", "rawvideo", "-"])
    buf = r.stdout or b""
    px = w * h
    n = len(buf) // px
    return [buf[i * px:(i + 1) * px] for i in range(n)], w, h


def rgb_mean(video, t, size=16):
    """\u53d6 t \u79d2\u5904\u4e00\u5e27\u7684 RGB \u5747\u503c\u4e0e\u7070\u5ea6\u6807\u51c6\u5dee\u3002\u5931\u8d25\u8fd4\u56de None\u3002"""
    try:
        r = _run(["ffmpeg", "-v", "error", "-ss", "%.3f" % max(0.0, t), "-i", video,
                  "-frames:v", "1", "-vf", "scale=%d:%d:flags=bilinear,format=rgb24" % (size, size),
                  "-f", "rawvideo", "-"])
        b = r.stdout or b""
        if len(b) < size * size * 3:
            return None
        n = size * size
        rs = gs = bs = 0
        for i in range(n):
            rs += b[i * 3]
            gs += b[i * 3 + 1]
            bs += b[i * 3 + 2]
        return {"r": rs / n, "g": gs / n, "b": bs / n}
    except Exception:
        return None


def audio_mean_db(video, start=None, dur=None, default=None):
    """\u4e00\u6bb5\u97f3\u8f68\u7684\u5e73\u5747\u7535\u5e73\uff08dB\uff0cvolumedetect \u7684 mean_volume\uff09\u3002\u65e0\u97f3\u8f68/\u5931\u8d25\u8fd4\u56de default\u3002"""
    args = ["ffmpeg", "-hide_banner"]
    if start:
        args += ["-ss", "%.3f" % start]
    args += ["-i", video]
    if dur:
        args += ["-t", "%.3f" % dur]
    args += ["-vn", "-af", "volumedetect", "-f", "null", "-"]
    try:
        r = _run(args)
        m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", r.stderr.decode("utf-8", "replace"))
        return float(m.group(1)) if m else default
    except Exception:
        return default


def _mean(xs):
    return sum(xs) / float(len(xs)) if xs else 0.0


def _std(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return (sum((x - m) ** 2 for x in xs) / float(len(xs))) ** 0.5


def _corr(a, b):
    """\u76ae\u5c14\u900a\u76f8\u5173\uff1b\u4efb\u4e00\u4fa7\u96f6\u65b9\u5dee\u65f6\u8fd4\u56de 0\u3002"""
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    ma, mb = _mean(a[:n]), _mean(b[:n])
    sa = sum((a[i] - ma) ** 2 for i in range(n))
    sb = sum((b[i] - mb) ** 2 for i in range(n))
    if sa <= 0 or sb <= 0:
        return 0.0
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / (sa ** 0.5 * sb ** 0.5)


def analyze(video, duration=None, fps=SAMPLE_FPS):
    """\u7b97\u4e00\u7ec4\u957f\u89c6\u9891\u5ba2\u89c2\u6307\u6807\u3002\u4efb\u4f55\u5931\u8d25\u90fd\u9000\u5316\u4e3a\u7f3a\u9879\uff0c\u4e0d\u629b\u5f02\u5e38\u3002"""
    m = {"video": os.path.basename(video or ""), "fps": fps}
    if not video or not os.path.exists(video) or not ffmpeg_available():
        m["error"] = "no ffmpeg or missing file"
        return m
    dur = float(duration or duration_of(video, 0.0) or 0.0)
    m["duration"] = round(dur, 3)

    frames = []
    try:
        frames, _, _ = gray_series(video, fps=fps)
    except Exception as e:
        m["error"] = "gray_series: %s" % type(e).__name__
    n = len(frames)

    if n >= 2:
        diffs = []
        for i in range(1, n):
            a, b = frames[i - 1], frames[i]
            s = 0
            for j in range(len(a)):
                d = a[j] - b[j]
                s += d if d >= 0 else -d
            diffs.append(s / float(len(a)))
        m["frames"] = n
        m["motion_mean"] = round(_mean(diffs), 3)
        m["motion_min"] = round(min(diffs), 3)
        m["frozen_ratio"] = round(sum(1 for d in diffs if d < TH_FROZEN_DIFF) / float(len(diffs)), 3)
        tail_k = max(3, int(round(len(diffs) * 0.25)))
        tail_diffs = diffs[-tail_k:]
        tail = _mean(tail_diffs)
        m["motion_tail"] = round(tail, 3)
        m["motion_tail_ratio"] = round(tail / m["motion_mean"], 3) if m["motion_mean"] > 0 else None
        m["tail_frozen_ratio"] = round(
            sum(1 for d in tail_diffs if d < TH_FROZEN_DIFF) / float(len(tail_diffs)), 3)

        lumas = [_mean([float(x) for x in f]) for f in frames]
        m["luma_first"] = round(_mean(lumas[:max(1, n // 10)]), 2)
        m["luma_last"] = round(_mean(lumas[-max(1, n // 10):]), 2)
        m["contrast_first"] = round(_std([float(x) for x in frames[0]]), 2)
        m["contrast_last"] = round(_std([float(x) for x in frames[-1]]), 2)

        # \u590d\u8bfb\uff1a\u5f00\u5934\u7247\u6bb5 vs \u4e4b\u540e\u6bcf\u4e2a\u7b49\u957f\u7a97\u53e3\u7684\u6700\u5927\u76f8\u5173
        win = max(2, int(round(n * 0.15)))
        if n >= win * 3:
            head = [float(x) for f in frames[:win] for x in f]
            best, best_at = 0.0, None
            for s in range(win, n - win + 1):
                seg = [float(x) for f in frames[s:s + win] for x in f]
                c = _corr(head, seg)
                if c > best:
                    best, best_at = c, s / float(fps)
            m["replay_max"] = round(best, 3)
            m["replay_at_s"] = round(best_at, 1) if best_at is not None else None
    else:
        m["frames"] = n

    if dur > 1:
        c0 = rgb_mean(video, min(0.5, dur * 0.05))
        c1 = rgb_mean(video, max(0.0, dur - 0.5))
        if c0 and c1:
            m["color_first"] = {k: round(v, 1) for k, v in c0.items()}
            m["color_last"] = {k: round(v, 1) for k, v in c1.items()}
            m["color_drift"] = round(max(abs(c0[k] - c1[k]) for k in "rgb"), 2)
        h = audio_mean_db(video, start=0, dur=dur / 2.0)
        t = audio_mean_db(video, start=dur / 2.0, dur=dur / 2.0)
        if h is not None and t is not None:
            m["audio_head_db"] = round(h, 1)
            m["audio_tail_db"] = round(t, 1)
            m["audio_tail_delta_db"] = round(t - h, 1)
    return m


def flags(m, duration=None):
    """\u628a\u6307\u6807\u7ffb\u6210"\u80fd\u5931\u8d25"\u7684\u544a\u8b66\u5217\u8868\uff08\u6bcf\u6761\u90fd\u5199\u6e05\u6570\u503c\u4e0e\u9608\u503c\uff09\u3002"""
    out = []
    if not m or m.get("error"):
        return ["\u5ba2\u89c2\u6307\u6807\u4e0d\u53ef\u7528\uff08%s\uff09" % (m or {}).get("error", "ffmpeg \u7f3a\u5931\u6216\u6587\u4ef6\u4e0d\u53ef\u8bfb")]
    tr = m.get("motion_tail_ratio")
    if tr is not None and tr < TH_TAIL_RATIO:
        out.append("\u5c3e\u90e8\u8fd0\u52a8\u8870\u51cf\uff1a\u5c3e\u90e8/\u5168\u7247\u8fd0\u52a8\u6bd4 %.2f < %.2f\uff08\u753b\u9762\u524d\u666f\u8d8b\u4e8e\u505c\u6ede\uff09" % (tr, TH_TAIL_RATIO))
    fr = m.get("frozen_ratio")
    if fr is not None and fr > TH_FROZEN:
        out.append("\u8fd1\u9759\u6b62\u5e27\u8fc7\u591a\uff1a\u5168\u7247 %.0f%% > %.0f%%" % (fr * 100, TH_FROZEN * 100))
    tf = m.get("tail_frozen_ratio")
    if tf is not None and tf > TH_TAIL_FROZEN:
        out.append("\u5c3e\u90e8\u51bb\u7ed3\uff1a\u5c3e\u90e8\u7a97\u53e3\u5185 %.0f%% \u7684\u5e27\u8fd1\u9759\u6b62 > %.0f%%"
                   % (tf * 100, TH_TAIL_FROZEN * 100))
    d = m.get("audio_tail_delta_db")
    if d is not None and d < TH_AUDIO_TAIL_DB:
        out.append("\u5c3e\u90e8\u97f3\u9891\u53d8\u5f31\uff1a\u540e\u534a\u6bb5\u6bd4\u524d\u534a\u6bb5\u4f4e %.1f dB\uff08< %.0f dB\uff09" % (d, TH_AUDIO_TAIL_DB))
    cf, cl = m.get("contrast_first"), m.get("contrast_last")
    if cf and cl is not None and cf > 0 and cl < cf * TH_CONTRAST_DROP:
        out.append("\u5bf9\u6bd4\u5ea6\u4e0b\u6ed1\uff1a\u672b\u5e27 %.1f < \u9996\u5e27 %.1f \u7684 %.0f%%" % (cl, cf, TH_CONTRAST_DROP * 100))
    cd = m.get("color_drift")
    if cd is not None and cd < TH_COLOR_DRIFT:
        out.append("\u8272\u8c03\u51e0\u4e4e\u4e0d\u53d8\uff1a\u9996\u672b\u5f69\u8272\u5e27 RGB \u6700\u5927\u5dee\u4ec5 %.1f < %.1f\uff08\u957f\u7247\u5e38\u89c1\u7684\u51b7\u7070/\u6052\u5b9a\u5149\u7167\u9000\u5316\uff09"
                   % (cd, TH_COLOR_DRIFT))
    return out


def advisories(m):
    """\u8f85\u52a9\u8bc1\u636e\uff1a\u4e0d\u53c2\u4e0e\u786c\u5224\u5b9a\uff0c\u5fc5\u987b\u7ed3\u5408\u8fd0\u52a8/\u51bb\u7ed3/\u8272\u5f69\u4e00\u8d77\u5224\u8bfb\u3002

    \u590d\u8bfb\u76f8\u5173\uff08\u5f00\u5934\u7247\u6bb5 vs \u540e\u6bb5\u7a97\u53e3\u7684\u7070\u5ea6\u76f8\u5173\uff09**\u57fa\u7ebf\u5f88\u9ad8**\uff1a\u6162\u901f\u6f14\u8fdb\u6216\u9759\u6001\u673a\u4f4d\u7684\u6b63\u5e38
    \u957f\u955c\u5934\u4e5f\u4f1a\u7ed9\u51fa\u9ad8\u76f8\u5173\uff0c\u800c\u5b9e\u6d4b\u4e2d\u771f\u6b63\u7684"\u7ed5\u56de\u5f00\u5934"\u6848\u4f8b\u53ea\u6709 0.588\uff08\u672c\u9879\u76ee 2026-09 \u5b9e\u6d4b
    \u62a5\u544a\u660e\u786e\u8981\u6c42\u5b83\u5fc5\u987b\u4e0e\u9010\u79d2\u8fd0\u52a8\u91cf\u3001\u51bb\u7ed3\u7387\u4e00\u8d77\u5224\u8bfb\uff09\u3002\u6545\u53ea\u4f5c\u63d0\u793a\uff0c\u4e0d\u5355\u72ec\u89e6\u53d1\u544a\u8b66\u3002
    """
    out = []
    if not m or m.get("error"):
        return out
    r = m.get("replay_max")
    if r is not None and r > TH_REPLAY:
        out.append("\u590d\u8bfb\u76f8\u5173 %.3f\uff08@%ss\uff09\u504f\u9ad8\uff1a\u82e5\u540c\u65f6\u51fa\u73b0\u5c3e\u90e8\u8fd0\u52a8\u8870\u51cf\u6216\u5bf9\u6bd4\u5ea6\u4e0b\u6ed1\uff0c"
                   "\u57fa\u672c\u53ef\u5224\u5b9a\u4e3a\u957f\u7247\u6bb5\u7ed5\u56de\u5f00\u5934\uff1b\u82e5\u5c3e\u90e8\u8fd0\u52a8\u6b63\u5e38\uff0c\u5219\u66f4\u53ef\u80fd\u53ea\u662f\u9759\u6001\u673a\u4f4d/\u6162\u901f\u6f14\u8fdb\u7684\u6b63\u5e38\u9ad8\u57fa\u7ebf"
                   % (r, m.get("replay_at_s")))
    return out


def format_report(m, fl=None, duration=None):
    """\u4e00\u884c\u6458\u8981 + \u544a\u8b66\uff0c\u4f9b\u65e5\u5fd7\u4e0e\u8bc4\u5ba1\u63d0\u793a\u8bcd\u4f7f\u7528\u3002"""
    if not m:
        return "\u5ba2\u89c2\u6307\u6807\uff1a\u4e0d\u53ef\u7528"
    if m.get("error"):
        return "\u5ba2\u89c2\u6307\u6807\uff1a\u4e0d\u53ef\u7528\uff08%s\uff09" % m["error"]
    parts = ["\u65f6\u957f %.1fs / \u91c7\u6837 %d \u5e27" % (m.get("duration") or 0, m.get("frames") or 0),
             "\u8fd0\u52a8\u5747\u503c %.2f" % (m.get("motion_mean") or 0)]
    if m.get("motion_tail_ratio") is not None:
        parts.append("\u5c3e\u90e8/\u5168\u7247\u8fd0\u52a8 %.2f" % m["motion_tail_ratio"])
    if m.get("frozen_ratio") is not None:
        parts.append("\u8fd1\u9759\u6b62 %.0f%%" % (m["frozen_ratio"] * 100))
    if m.get("tail_frozen_ratio") is not None:
        parts.append("\u5c3e\u90e8\u8fd1\u9759\u6b62 %.0f%%" % (m["tail_frozen_ratio"] * 100))
    if m.get("replay_max") is not None:
        parts.append("\u590d\u8bfb\u76f8\u5173 %.2f@%ss" % (m["replay_max"], m.get("replay_at_s")))
    if m.get("contrast_first") is not None:
        parts.append("\u5bf9\u6bd4\u5ea6 %.1f\u2192%.1f" % (m["contrast_first"], m.get("contrast_last") or 0))
    if m.get("color_drift") is not None:
        parts.append("\u8272\u5f69\u6f02\u79fb %.1f" % m["color_drift"])
    if m.get("audio_tail_delta_db") is not None:
        parts.append("\u97f3\u9891\u524d\u2192\u540e %.1f\u2192%.1f dB" % (m.get("audio_head_db"), m.get("audio_tail_db")))
    txt = "\u5ba2\u89c2\u6307\u6807\uff1a" + "\uff1b".join(parts)
    if fl:
        txt += "\n\u5ba2\u89c2\u544a\u8b66\uff08\u7531\u9608\u503c\u5224\u5b9a\uff0c\u975e\u4e3b\u89c2\u5370\u8c61\uff09\uff1a\n" + "\n".join("  ! " + x for x in fl)
    adv = advisories(m)
    if adv:
        txt += "\n\u8f85\u52a9\u8bc1\u636e\uff08\u57fa\u7ebf\u9ad8\uff0c\u9700\u7ed3\u5408\u4e0a\u9762\u7684\u544a\u8b66\u4e00\u8d77\u5224\u8bfb\uff0c\u4e0d\u5355\u72ec\u4f5c\u4e3a\u5224\u636e\uff09\uff1a\n" + \
               "\n".join("  ? " + x for x in adv)
    return txt
