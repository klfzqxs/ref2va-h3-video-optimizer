#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2.0 \u957f\u89c6\u9891\u6539\u9020\u9a8c\u8bc1\uff08\u79bb\u7ebf\uff1b\u7528 ffmpeg \u5408\u6210\u6837\u672c\u6765\u8bc1\u660e\u68c0\u67e5"\u80fd\u5931\u8d25"\uff09\u3002

\u8fd0\u884c\uff1a python tests/test_long_video.py

\u8986\u76d6\uff1a
  A. \u65f6\u957f\u4e0a\u9650\u4e0e\u957f\u89c6\u9891\u5206\u652f\u5224\u5b9a\uff0815 \u2192 60 \u79d2\uff09
  B. \u957f\u89c6\u9891\u63d0\u793a\u8bcd\u53ea\u5728 >15 \u79d2\u6ce8\u5165\uff08\u226415 \u79d2\u5fc5\u987b\u4fdd\u6301\u539f\u6837\uff09
  C. extract_frames \u662f\u5426\u771f\u7684\u91c7\u5230\u672b\u5e27\uff08\u65e7\u5b9e\u73b0\u7cfb\u7edf\u6027\u6f0f\u6389\u6700\u540e 1/n \u6bb5\uff09
  D. video_metrics \u662f\u5426\u771f\u80fd\u6293\u5230"\u5c3e\u90e8\u51bb\u7ed3"\u548c"\u5c3e\u90e8\u97f3\u9891\u8870\u51cf"
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))
import ref2va_auto as ra          # noqa: E402
import video_metrics as vm        # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "   -> " + str(detail)))
    if not cond:
        fails.append(name)


def sh(args):
    return subprocess.run(args, capture_output=True)


def rgb_mean(png):
    """PNG -> rgb24 -> \u901a\u9053\u5747\u503c\uff08\u5224\u65ad\u67d0\u5e27\u662f\u4e0d\u662f\u7eaf\u7ea2\uff09\u3002"""
    r = sh(["ffmpeg", "-v", "error", "-i", png, "-vf", "scale=16:16,format=rgb24",
            "-f", "rawvideo", "-"])
    b = r.stdout or b""
    if len(b) < 16 * 16 * 3:
        return None
    n = 256
    return [sum(b[i * 3 + c] for i in range(n)) / n for c in range(3)]


def make_media(work):
    good = os.path.join(work, "good.mp4")
    redtail = os.path.join(work, "redtail.mp4")
    audiodrop = os.path.join(work, "audiodrop.mp4")
    sh(["ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=20",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", good])
    # \u524d 14 \u79d2\u6301\u7eed\u8fd0\u52a8 + \u6700\u540e 6 \u79d2\u7eaf\u7ea2\u9759\u6b62\uff08\u5c3e\u90e8\u51bb\u7ed3\uff0c\u51bb\u7ed3\u5360 30%\uff09
    sh(["ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=14",
        "-f", "lavfi", "-i", "color=c=red:size=320x240:rate=24:duration=6",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", redtail])
    # \u524d 10 \u79d2\u6b63\u5e38\u97f3\u91cf + \u540e 10 \u79d2 -20dB\uff08\u5c3e\u90e8\u97f3\u9891\u53d8\u5f31\uff09
    sh(["ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=20",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10,volume=0.08",
        "-filter_complex", "[1:a][2:a]concat=n=2:v=0:a=1[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", audiodrop])
    return good, redtail, audiodrop


print("=" * 72)
print("A. \u65f6\u957f\u4e0a\u9650\u4e0e\u957f\u89c6\u9891\u5206\u652f")
print("=" * 72)
check("validate_duration(15) \u901a\u8fc7", ra.validate_duration(15) == (15.0, None), ra.validate_duration(15))
check("validate_duration(60) \u901a\u8fc7", ra.validate_duration(60) == (60.0, None), ra.validate_duration(60))
check("validate_duration(60.1) \u88ab\u62d2", ra.validate_duration(60.1)[1] is not None)
check("validate_duration(120) \u88ab\u62d2", ra.validate_duration(120)[1] is not None)
check("validate_duration(0.5) \u88ab\u62d2", ra.validate_duration(0.5)[1] is not None)
check("validate_duration('abc') \u88ab\u62d2", ra.validate_duration("abc")[1] is not None)
check("MAX_DURATION_S == 60", ra.MAX_DURATION_S == 60.0, ra.MAX_DURATION_S)
check("is_long_video(15) \u4e3a\u5047", ra.is_long_video(15) is False)
check("is_long_video(15.5) \u4e3a\u771f", ra.is_long_video(15.5) is True)
check("is_long_video(60) \u4e3a\u771f", ra.is_long_video(60) is True)
check("expected_frames(60) == 1450\uff0817k+5 \u5438\u9644\uff09", ra.expected_frames(60) == 1450, ra.expected_frames(60))
check("expected_frames(15) == 362", ra.expected_frames(15) == 362, ra.expected_frames(15))
check("review_frame_count(10) == 32", ra.review_frame_count(10, 32) == 32, ra.review_frame_count(10, 32))
check("review_frame_count(60) == 40", ra.review_frame_count(60, 32) == 40, ra.review_frame_count(60, 32))

print()
print("=" * 72)
print("B. \u957f\u89c6\u9891\u63d0\u793a\u8bcd\u53ea\u5728 >15 \u79d2\u6ce8\u5165")
print("=" * 72)
d10, d15, d60 = ra.system_director(10), ra.system_director(15), ra.system_director(60)
check("director(10) \u65e0\u957f\u89c6\u9891\u89c4\u5219", "\u957f\u89c6\u9891\u6a21\u5f0f" not in d10)
check("director(15) \u65e0\u957f\u89c6\u9891\u89c4\u5219", "\u957f\u89c6\u9891\u6a21\u5f0f" not in d15)
check("director(60) \u6709\u957f\u89c6\u9891\u89c4\u5219", "\u957f\u89c6\u9891\u6a21\u5f0f" in d60)
check("director(60) \u542b\u300c\u8fd0\u52a8\u94fa\u6ee1\u5168\u7247\u300d", "\u8fd0\u52a8\u94fa\u6ee1\u5168\u7247" in d60)
check("director(60) \u4fdd\u7559 1)-6) \u89c4\u5219", "6) \u65f6\u957f\u786c\u5bf9\u9f50" in d60 and "1) \u5177\u4f53\u53ef\u89c2\u6d4b" in d60)
i10, i60 = ra.system_i2va(10), ra.system_i2va(60)
check("i2va(10) \u65e0 LONG VIDEO MODE", "LONG VIDEO MODE" not in i10)
check("i2va(60) \u6709 LONG VIDEO MODE", "LONG VIDEO MODE" in i60)
check("i2va(60) \u4fdd\u7559 HARD REQUIREMENTS", "## HARD REQUIREMENTS" in i60)
check("critic addendum(10) \u4e3a\u7a7a", ra.long_video_critic_addendum(10) == "")
check("critic addendum(60) \u542b\u5ba2\u89c2\u6307\u6807\u8981\u6c42", "\u5ba2\u89c2\u6307\u6807" in ra.long_video_critic_addendum(60))

print()
print("=" * 72)
print("C/D. \u7528 ffmpeg \u5408\u6210\u6837\u672c\u9a8c\u8bc1\u62bd\u5e27\u8986\u76d6\u4e0e\u6307\u6807")
print("=" * 72)
if not vm.ffmpeg_available():
    check("ffmpeg \u53ef\u7528", False, "\u672a\u627e\u5230 ffmpeg\uff08\u672c\u7ec4\u68c0\u67e5\u9700\u8981\uff09")
else:
    work = tempfile.mkdtemp(prefix="h3_verify_")
    good, redtail, audiodrop = make_media(work)

    frames = ra.extract_frames(redtail, work, n_frames=4, width=160, as_jpeg=False)
    check("extract_frames \u8fd4\u56de 4 \u5e27", len(frames) == 4, len(frames))
    if len(frames) == 4:
        last, first = rgb_mean(frames[-1]), rgb_mean(frames[0])
        check("\u672b\u5e27\u662f\u7ea2\u8272\uff08\u8bc1\u660e\u91c7\u5230\u4e86\u7ed3\u5c3e\uff09", last and last[0] > 120 and last[0] > 1.8 * last[2], last)
        check("\u9996\u5e27\u4e0d\u662f\u7ea2\u8272\uff08\u5bf9\u7167\uff09", first and not (first[0] > 1.8 * first[2]), first)

    m_good, f_good = vm.analyze(good, 20.0), None
    f_good = vm.flags(m_good, 20.0)
    print("    good.mp4  ->", vm.format_report(m_good, f_good, 20.0).replace("\n", " | "))
    check("\u6b63\u5e38\u8fd0\u52a8\u7247\u65e0\u4efb\u4f55\u786c\u544a\u8b66", f_good == [], f_good)
    check("\u590d\u8bfb\u53ea\u4f5c\u8f85\u52a9\u8bc1\u636e\uff08\u4e0d\u8fdb\u786c\u544a\u8b66\uff09", not any("\u590d\u8bfb" in x for x in f_good), f_good)

    m_fr = vm.analyze(redtail, 20.0)
    f_fr = vm.flags(m_fr, 20.0)
    print("    redtail   ->", vm.format_report(m_fr, f_fr, 20.0).replace("\n", " | "))
    check("\u5c3e\u90e8\u51bb\u7ed3\u6837\u672c\u62a5\u300c\u5c3e\u90e8\u8fd0\u52a8\u8870\u51cf\u300d", any("\u5c3e\u90e8\u8fd0\u52a8\u8870\u51cf" in x for x in f_fr), f_fr)
    check("\u5c3e\u90e8\u51bb\u7ed3\u6837\u672c\u62a5\u300c\u5c3e\u90e8\u51bb\u7ed3\u300d", any("\u5c3e\u90e8\u51bb\u7ed3" in x for x in f_fr), f_fr)
    check("\u5c3e\u90e8\u51bb\u7ed3\u6837\u672c\u62a5\u300c\u8fd1\u9759\u6b62\u5e27\u8fc7\u591a\u300d", any("\u8fd1\u9759\u6b62\u5e27\u8fc7\u591a" in x for x in f_fr), f_fr)

    m_au = vm.analyze(audiodrop, 20.0)
    f_au = vm.flags(m_au, 20.0)
    print("    audiodrop ->", vm.format_report(m_au, f_au, 20.0).replace("\n", " | "))
    check("\u97f3\u9891\u8870\u51cf\u6837\u672c\u62a5\u300c\u5c3e\u90e8\u97f3\u9891\u53d8\u5f31\u300d", any("\u5c3e\u90e8\u97f3\u9891\u53d8\u5f31" in x for x in f_au), f_au)

print()
print("checks:", "ALL PASS" if not fails else "%d FAILED" % len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
