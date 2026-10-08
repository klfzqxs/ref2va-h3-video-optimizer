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
print("=" * 72)
print("E. \u53c2\u8003\u7d20\u6750\u7528\u6cd5\uff1a\u4e0d\u9884\u8bbe\u300c\u7b2c 1 \u5f20\u56fe\uff1d\u89c6\u9891\u9996\u5e27\u300d\uff08\u53ea\u6709\u7528\u6237\u660e\u786e\u8981\u6c42\u624d\u9501\uff09")
print("=" * 72)
import optimizer as opt  # noqa: E402

_ref_hint = opt._IMG_HINT
check("Ref2VA \u9644\u56fe\u8bf4\u660e\u4e0d\u518d\u628a <Picture 1> \u5f53\u6210\u9996\u5e27",
      "<Picture 1>\uff08\u9996\u5e27" not in _ref_hint and "\u4f7f\u9996\u5e27\u4e0e" not in _ref_hint)
check("\u300c\u9996\u5e27\u300d\u53ea\u51fa\u73b0\u5728\u300c\u7528\u6237\u660e\u786e\u8981\u6c42\u624d\u9501\u300d\u7684\u6761\u4ef6\u53e5\u91cc",
      all(("\u660e\u786e\u5199\u4e86" in _ln) or ("\u9996\u5e27" not in _ln) for _ln in _ref_hint.splitlines()),
      [ln for ln in _ref_hint.splitlines() if "\u9996\u5e27" in ln and "\u660e\u786e\u5199\u4e86" not in ln])
check("Ref2VA \u9644\u56fe\u8bf4\u660e\u4e0d\u518d\u8981\u6c42\u300c\u9996\u5e27\u5b8c\u5168\u4e00\u81f4\u300d",
      "\u5b8c\u5168\u4e00\u81f4" not in _ref_hint and "\u89c6\u9891\u5f00\u5934" not in _ref_hint)
check("Ref2VA \u9644\u56fe\u8bf4\u660e\u4e0d\u518d\u7981\u6b62\u8fd0\u955c/\u5207\u955c",
      "\u65e0\u4efb\u4f55\u5207\u6362" not in _ref_hint and "\u65e0\u4efb\u4f55\u8fd0\u955c" not in _ref_hint)
check("Ref2VA \u9644\u56fe\u8bf4\u660e\u4e0d\u518d\u6709\u300c\u4e0d\u8981\u9884\u8bbe\u2026\u300d\u8fd9\u7c7b\u7981\u6b62\u6027\u9884\u8bbe\uff08\u4ea4\u7ed9\u7528\u6237\u63d0\u793a\u8bcd\u51b3\u5b9a\uff09",
      "\u4e0d\u8981\u9884\u8bbe" not in _ref_hint and "\u4e0d\u8981\u9ed8\u8ba4" not in _ref_hint)
check("Ref2VA \u9644\u56fe\u8bf4\u660e\u4fdd\u7559\u300c\u7528\u6237\u660e\u786e\u8981\u6c42\u624d\u9501\u300d\u7684\u6761\u4ef6", "\u660e\u786e\u5199\u4e86" in _ref_hint)
check("\u5267\u672c schema \u91cc frame_note \u4e0d\u518d\u9884\u8bbe\u300c\u9996\u5e27\u300d",
      "\u9996\u5e27\u6216\u5173\u952e\u5e27" not in d10 and "\u753b\u9762\u951a\u70b9" in d10)
check("I2VA \u9644\u56fe\u8bf4\u660e\u4ecd\u7136\u5199\u6b7b\u7b2c\u4e00\u5e27\uff08\u90a3\u662f\u89c4\u8303\uff09", "0.00 \u79d2\u7684\u7b2c\u4e00\u5e27" in opt._I2VA_IMG_HINT)
check("I2VA \u7684 system prompt \u4ecd\u542b\u9996\u5e27\u58f0\u660e",
      "at 0.00 seconds into the target video, <Picture 1>" in ra.system_i2va(10))
check("\u8bc4\u5ba1\u4e0d\u518d\u9884\u8bbe\u300c\u9996\u5e27\u6784\u56fe\u5fc5\u987b\u5339\u914d\u53c2\u8003\u56fe\u300d",
      "\u9996\u5e27\u89c6\u89d2/\u6784\u56fe\u5fc5\u987b\u5339\u914d\u6307\u5b9a\u53c2\u8003\u56fe" not in ra.SYSTEM_CRITIC)
check("\u8bc4\u5ba1\u4ecd\u4fdd\u7559\u4e00\u7968\u5426\u51b3\u673a\u5236", "\u4e00\u7968\u5426\u51b3\u5236" in ra.SYSTEM_CRITIC)


class _FakeLLM:
    """\u53ea\u5b9e\u73b0 encode_image \u7684\u5047 LLM\uff1a\u8bb0\u5f55\u88ab\u8981\u6c42\u7f16\u7801\u4e86\u54ea\u4e9b\u56fe\u3002"""

    def __init__(self, fail_on=()):
        self.calls = []
        self.fail_on = set(fail_on)

    def encode_image(self, path):
        self.calls.append(path)
        if path in self.fail_on:
            raise RuntimeError("\u6a21\u62df\u8bfb\u53d6\u5931\u8d25")
        return "b64:" + os.path.basename(path)


_three = {"refs": [{"path": "a.png"}, {"path": "b.png"}, {"path": "c.png"}]}
_fk = _FakeLLM()
_imgs = opt._load_script_imgs(_fk, _three)
check("\u5199\u5267\u672c\u65f6\u628a**\u5168\u90e8**\u53c2\u8003\u56fe\u90fd\u5582\u7ed9 LLM\uff08\u539f\u6765\u53ea\u5582\u7b2c 1 \u5f20\uff09", len(_imgs) == 3, _imgs)
check("\u6309\u987a\u5e8f\u7f16\u7801\u3001\u6807\u7b7e\u4e00\u4e00\u5bf9\u5e94", _fk.calls == ["a.png", "b.png", "c.png"], _fk.calls)
_fk2 = _FakeLLM(fail_on=("b.png",))
check("\u5355\u5f20\u8bfb\u56fe\u5931\u8d25\u53ea\u8df3\u8fc7\u3001\u4e0d\u5f71\u54cd\u5176\u4f59", len(opt._load_script_imgs(_fk2, _three)) == 2,
      opt._load_script_imgs(_FakeLLM(), _three))
check("\u65e0\u53c2\u8003\u56fe\u65f6\u8fd4\u56de\u7a7a\u5217\u8868\uff08\u8d70\u7eaf\u6587\u672c\u8def\u5f84\uff09",
      opt._load_script_imgs(_FakeLLM(), {"refs": []}) == [])
check("\u9644\u56fe\u8bf4\u660e\u5728\u65e0\u56fe\u65f6\u4e0d\u6ce8\u5165", opt._img_hint({"flow": "ref2va"}, []) == "")
check("\u6709\u56fe\u65f6 Ref2VA \u6ce8\u5165\u4e2d\u6027\u7248\u8bf4\u660e",
      opt._img_hint({"flow": "ref2va"}, ["x"]) == opt._IMG_HINT)
check("\u6709\u56fe\u65f6 I2VA \u6ce8\u5165\u9996\u5e27\u7248\u8bf4\u660e",
      opt._img_hint({"flow": "i2va"}, ["x"]) == opt._I2VA_IMG_HINT)
check("\u53c2\u8003\u56fe\u6570\u91cf\u4e0a\u9650\uff08\u22649 \u5f20\uff09", len(opt._load_script_imgs(
    _FakeLLM(), {"refs": [{"path": "p%d.png" % i} for i in range(12)]})) == 9)

print()
print("=" * 72)
print("F. \u5149\u7167/\u8272\u8c03\u4e0d\u5f3a\u5236\u53d8\u5316\uff1a\u6052\u5b9a\u5149\u7167\u7684\u573a\u666f\u4e0d\u8be5\u88ab\u5f53\u6210\u9000\u5316")
print("=" * 72)
check("\u957f\u89c6\u9891\u5199\u4f5c\u89c4\u5219\u4e0d\u518d\u4e00\u5f8b\u8981\u6c42\u300c\u8fde\u7eed\u6f14\u53d8\u300d",
      "\u5149\u7167\u4e0e\u8272\u5f69\u5199\u6210\u8d2f\u7a7f\u5168\u7a0b\u7684\u8fde\u7eed\u6f14\u53d8\uff1a\u660e\u786e\u5199\u51fa\u5404\u9636\u6bb5" not in d60)
check("\u957f\u89c6\u9891\u5199\u4f5c\u89c4\u5219\u660e\u786e\u5141\u8bb8\u300c\u6052\u5b9a\u5149\u7167/\u6052\u5b9a\u8272\u8c03\u300d",
      "\u6052\u5b9a\u5149\u7167/\u6052\u5b9a\u8272\u8c03" in d60 and "\u53ea\u6709\u5267\u60c5\u9700\u8981\u53d8\u5316\u65f6" in d60)
check("\u300c\u65b0\u5185\u5bb9\u5747\u644a\u300d\u4e0d\u518d\u628a\u300c\u65b0\u5149\u4f4d\u300d\u5f53\u5fc5\u8981\u6761\u4ef6", "\u65b0\u5149\u4f4d" not in d60)

_add60 = ra.long_video_critic_addendum(60)
check("\u8bc4\u5ba1\u4e0d\u518d\u628a\u300c\u8272\u5f69\u6f02\u79fb\u8fc7\u4f4e\u300d\u4e00\u5f8b\u5f53\u9000\u5316\u6263\u5206",
      "\u8272\u5f69\u6f02\u79fb\u8fc7\u4f4e" not in _add60 and "\u4e0d\u7b97\u9000\u5316" in _add60)

_m_const = {"color_drift": 1.0, "contrast_first": 60.0, "contrast_last": 60.0,
            "motion_tail_ratio": 0.9, "frozen_ratio": 0.0, "tail_frozen_ratio": 0.0,
            "audio_tail_delta_db": 0.0}
_flags_c = vm.flags(_m_const, 20.0)
check("\u8272\u8c03\u6052\u5b9a\u4e0d\u518d\u8fdb\u786c\u544a\u8b66", not any("\u8272\u8c03" in x for x in _flags_c), _flags_c)
check("\u8272\u8c03\u6052\u5b9a\u6539\u4e3a\u8f85\u52a9\u8bc1\u636e\uff08\u4ea4\u8bc4\u5ba1\u6309\u5267\u672c\u5224\u65ad\uff09",
      any("\u8272\u8c03" in x for x in vm.advisories(_m_const)), vm.advisories(_m_const))
_m_dark = dict(_m_const, contrast_last=10.0)
check("\u5bf9\u6bd4\u5ea6\u4e0b\u6ed1\u4ecd\u662f\u786c\u544a\u8b66\uff08\u6ca1\u6709\u628a\u68c0\u67e5\u4e00\u8d77\u524a\u6389\uff09",
      any("\u5bf9\u6bd4\u5ea6\u4e0b\u6ed1" in x for x in vm.flags(_m_dark, 20.0)), vm.flags(_m_dark, 20.0))

print()
print("checks:", "ALL PASS" if not fails else "%d FAILED" % len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
