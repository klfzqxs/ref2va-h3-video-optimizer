#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ref2VA 提示词优化器（顺序爬山）。

用法:
  python optimizer.py --config <config.json> [--dry-run]
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "core"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import ref2va_auto as ra
from llm import LLM

ASPECT_LABELS = [
    "16:9 (Widescreen)", "1:1 (Square)", "9:16 (Portrait Widescreen)",
    "4:3 (Standard)", "3:4 (Portrait Standard)",
]


def normalize_aspect(a):
    """把比例规范成 ResolutionSelector 需要的完整标签（4:3 → '4:3 (Standard)'）。"""
    if not a:
        return None
    a = str(a).strip()
    for label in ASPECT_LABELS:
        if a == label or a == label.split(" ")[0]:
            return label
    return a


def ask(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    try:
        v = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        v = ""
    return v if v else (default if default is not None else "")


# ============================================================ 工具
_T_T = {}
def _ts():
    return time.strftime("%H:%M:%S")

def _stage(name):
    _T_T[name] = time.time()
    print(f"[{_ts()}] ▸ 阶段开始 · {name}")
    return name

def _stage_end(name):
    t0 = _T_T.pop(name, None)
    if t0 is None:
        return
    print(f"[{_ts()}] ◂ 阶段结束 · {name}（耗时 {time.time()-t0:.1f}s）")


QUICK_FACTOR = 0.707     # 快速渲染：分辨率(megapixels)与采样步数均乘此系数


def _flow(cfg):
    """当前流程：ref2va（参考图/视频→视频，六段英文）或 i2va（首帧图生视频，三字段英文）。"""
    return (cfg.get("flow") or "ref2va").strip().lower()


def _quick_scale(cfg, megapixels, steps):
    """快速渲染模式（两条流程通用）：
    模型 / 采样器 / 时长 / 画幅 / LoRA **全部与精渲相同**，只把两件事缩下来：
      · 分辨率 megapixels  × 0.707（按 ResolutionSelector 的 step=0.1 向下取整）
      · 采样步数 steps      × 0.707（向下取整到整数，下限 1）
    因为 0.707 × 0.707 = 0.5，渲染耗时约为精渲的一半；提示词遵从度下降有限。
    不做任何内置 LoRA 注入——要加速由用户在页面「LoRA」区自行加载。"""
    if not cfg.get("quick_render"):
        return megapixels, steps
    mp = megapixels
    if mp:
        mp = math.floor(float(mp) * QUICK_FACTOR * 10.0) / 10.0
        mp = max(mp, 0.1)
    st = max(1, int(math.floor(int(steps) * QUICK_FACTOR)))
    return mp, st


def build_gcfg(cfg, prompt, seed):
    flow = _flow(cfg)
    i2v = flow == "i2va"
    # 快速渲染：仅缩分辨率与步数，其余（模型/采样器/时长/画幅/LoRA）与精渲完全一致
    mp, st = _quick_scale(cfg, cfg.get("megapixels"), cfg.get("steps", 20))
    return {
        "prompt": prompt,
        "flow": flow,
        # I2VA 只用第 1 张参考图作为视频首帧（make_graph_i2v 内部取 ref_images[0]）
        "ref_images": cfg["_ref_names"][:1] if i2v else cfg["_ref_names"],
        "ref_audios": cfg["_aud_names"],
        "seed": seed,
        "duration_s": cfg.get("duration", 10),
        "steps": st, "denoise": 1.0,
        "model": cfg.get("model"), "clip": cfg.get("clip"), "weight_dtype": "default",
        "loras": cfg.get("loras") or [],
        "sampler": cfg.get("sampler"), "scheduler": cfg.get("scheduler"),
        "megapixels": mp,
        "aspect_ratio": normalize_aspect(cfg.get("aspect")),
        # I2VA 只吃首帧，没有 B 方式（视频编辑）演化
        "video_ref": None if i2v else cfg.get("video_ref"),
    }


def render(gcfg, rundir):
    _stage("渲染")
    if (gcfg.get("flow") or "ref2va") == "i2va":
        print(f"  ⏳ I2VA 首帧图生视频（{gcfg.get('steps')} 步 · {gcfg.get('megapixels')}MP）")
        graph = ra.make_graph_i2v(gcfg)
    else:
        print(f"  ⏳ Ref2VA（{gcfg.get('steps')} 步 · {gcfg.get('megapixels')}MP）")
        graph = ra.make_graph(gcfg)
    print(f"  ⏳ ComfyUI 渲染中（{rundir}），此步通常需要数分钟，请耐心等待…")
    res = ra.submit_and_fetch(graph, rundir, timeout_s=7200)
    vids = ra.extract_videos(res)
    _stage_end("渲染")
    return vids[0] if vids else None


def _sync_video_ref(video_path):
    """把视频送入 ComfyUI input（优先用 /upload，失败回退本地拷），返回文件名供 VHS_LoadVideo 引用。"""
    if not video_path or not os.path.exists(video_path):
        return None
    try:
        name = ra.comfy_upload(video_path)
        print(f"  [参考视频] 已上传到 ComfyUI: {name}", file=sys.stderr)
        return name
    except Exception as e:
        print(f"    [warn] 参考视频上传失败，回退本地拷贝: {str(e)[:80]}", file=sys.stderr)
    import shutil
    int_dir = os.environ.get("COMFYUI_INPUT_DIR", os.path.join(os.getcwd(), "input"))
    os.makedirs(int_dir, exist_ok=True)
    name = f"vidref_{abs(hash(video_path)) % 10 ** 7}_{os.path.basename(video_path)}"
    shutil.copy(video_path, os.path.join(int_dir, name))
    return name


def _parse_critic_robust(raw):
    """解析评审文本为 dict。先严格 parse_critic，失败则从后往前找最后一个平衡的 {...}。
    思考链模型可能把思考与最终 JSON 拼在一起。"""
    c = ra.parse_critic(raw)
    if isinstance(c, dict):
        return c
    text = (raw or "").strip()
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
                    cand = text[j:i + 1]
                    try:
                        return json.loads(cand)
                    except Exception:
                        break
    return None


# ============================================================ 音频双通道评审
# 自动检测是否涉声（audio_scoring=auto 时用）。只要目标/情节/参考音频命中其一即判定需要音频证据。
_AUDIO_KEYWORDS = [
    "声", "音", "叫", "哼", "喘息", "呼吸", "说话", "对白", "低语", "语音",
    "voice", "audio", "sound", "whisper", "breath", "gasp", "sigh", "cry",
    "喊", "哭", "笑", "唱", "铃", "雨声", "环境音", "闷哼",
]


def _audio_mode(cfg, story):
    """返回该任务是否启用音频评审通道。audio_scoring: on/off/auto（默认 auto）。"""
    mode = (cfg.get("audio_scoring") or "auto").lower()
    if mode == "on":
        return True
    if mode == "off":
        return False
    # auto：情节/优化目标 或 有参考音频 → 启用
    blob = (f"{story} {cfg.get('optimize_target') or ''}").lower()
    if any(k in blob for k in _AUDIO_KEYWORDS):
        return True
    if cfg.get("_aud_names"):
        return True
    return False


def _extract_audio(video, rundir):
    """用 ffmpeg 从视频抽音频轨 → wav(16k/mono)。无音轨返回 None。"""
    import shutil
    if not shutil.which("ffmpeg"):
        print("    ⚠ 无 ffmpeg，无法抽音频给音频评审", file=sys.stderr)
        return None
    out = os.path.join(rundir, "audio_audit.wav")
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", out],
        capture_output=True)
    if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
        return out
    return None


# 音频审听模型：只输出「实测听到什么 + 与宪法音频约束的相符/偏离」，不输出最终分（最终分交给画面 LLM 统一评）。
SYSTEM_AUDIO_CRITIC = (
    "你是视频音频轨审听员。认真听输入音频，客观转述你实际听到的声音，"
    "并与剧情/宪法里要求的声音约束逐条核对，指出相符或偏离。\n"
    "只输出纯文本，结构如下：\n"
    "【实测音频】…（实际听到的音色/音量/节奏/内容/情绪，客观转写，含文字内容若有）\n"
    "【音频约束核对】逐条列出要求的音频点实际是否达成（达成/未达成/部分），未达成处具体说明差在哪、应如何改。\n"
    "不要输出 JSON、不要打分 overall，只做客观听声与核对。"
)


def audio_evidence(llm_audio, video, story, prompt, rundir):
    """抽视频音轨 → 音频模型听声 → 返回实测证据文本；失败返回 None。"""
    audio_path = _extract_audio(video, rundir)
    if not audio_path:
        print("    ⚠ 视频无音轨，音频通道跳过")
        return None
    try:
        b64 = llm_audio.encode_audio(audio_path)
        fmt = os.path.splitext(audio_path)[1].lstrip(".").lower() or "wav"
        user = (
            f"# 故事大纲\n{story}\n\n"
            f"# 宪法（视频/音频不得违背其中任何约束，重点核对声音相关）\n{prompt}\n\n"
            "请听该视频的音频轨并做实测转写 + 音频约束核对。"
        )
        for attempt in range(1, 4):
            try:
                txt = llm_audio.audio(SYSTEM_AUDIO_CRITIC, user, b64,
                                      audio_format=fmt, temperature=0, max_tokens=4000)
                if txt and len(txt) > 10:
                    return txt
            except Exception as e:
                print(f"    ⚠ 音频审听失败({attempt}/3): {str(e)[:80]}")
        return None
    except Exception as e:
        print(f"    ⚠ 音频证据生成失败: {str(e)[:80]}")
        return None


SYSTEM_AUDIO_ANALYZER = (
    "你是音频分析员。听输入的参考音频，客观描述它的声音特征，供视频生成提示词使用。\n"
    "只输出一段纯文本，包含：音色/声线特点、音区与音高、节奏/语速、情绪与语气、"
    "发声内容(若有文字/歌词)、与其它音层的分离度。不要输出 JSON、不要打分、不要臆测，只描述实际听到的。"
)


def analyze_ref_audio(llm_audio, path, note=""):
    """用音频 LLM 分析一条参考音频，返回声音特征描述；失败返回 None。"""
    try:
        b64 = llm_audio.encode_audio(path)
        fmt = os.path.splitext(path)[1].lstrip(".").lower() or "wav"
        user = (f"这是参考音频，用途：{note or '提供声音/音色参考'}。"
                "请听并客观描述它的声音特征，供生成时还原。")
        for attempt in range(1, 3):
            try:
                txt = llm_audio.audio(SYSTEM_AUDIO_ANALYZER, user, b64,
                                      audio_format=fmt, temperature=0, max_tokens=1000)
                if txt and len(txt) > 10:
                    return txt.strip()
            except Exception as e:
                print(f"    ⚠ 参考音频分析失败({attempt}/2): {str(e)[:80]}")
        return None
    except Exception as e:
        print(f"    ⚠ 参考音频分析错误: {str(e)[:80]}")
        return None


def evaluate(llm, video, story, prompt, rundir, n_frames=4, audio_llm=None,
             use_audio=None, frame_width=768, frame_jpeg=False, target=None):
    """评审：抽帧给画面 LLM。若 use_audio，则先音频模型听声产出实测证据，
    并入画面 LLM 的 prompt，让它统一评 audio_affordance 与 overall。"""
    _stage("评分")
    try:
        frames = ra.extract_frames(video, rundir, n_frames=n_frames,
                                   width=frame_width, as_jpeg=frame_jpeg)
        if not frames:
            return None
        cp = (
            f"# 故事大纲\n{story}\n\n"
            + (f"# 优化目标（本轮要达成的核心，评审须严格核验其达成度）\n{target}\n\n" if target else "")
            + f"# 生成该视频使用的完整 ref2va prompt（宪法：视频不得违背其中任何约束）\n{prompt}\n\n"
        )
        if use_audio and audio_llm is not None:
            ev = audio_evidence(audio_llm, video, story, prompt, rundir)
            if ev:
                cp += (
                    f"\n# 音频实测证据（由独立音频审听模型对视频音轨逐条转写并核对宪法）\n{ev}\n\n"
                    "请依据上述【音频实测证据】来评 audio_affordance 与涉及声音的约束维度，"
                    "不要凭空猜测声音是否符合。\n\n"
                )
        cp += f"下面 {n_frames} 张关键帧来自该视频，请逐维度打分并给出 verdict 与 gaps。"
        imgs = [llm.encode_image(f) for f in frames]
        for attempt in range(1, 4):
            try:
                raw = llm.vision(ra.SYSTEM_CRITIC, cp, imgs, temperature=0, max_tokens=24000)
                critic = _parse_critic_robust(raw)
                if critic is not None and critic.get("overall") is not None:
                    return critic
                print(f"    ⚠ 评审结果无有效评分(第{attempt}/3次)，重试…")
            except Exception as e:
                print(f"    ⚠ 评审失败: {str(e)[:80]}")
                if attempt >= 3:
                    return None
        return None
    finally:
        _stage_end("评分")


def score_of(critic):
    try:
        return float((critic or {}).get("overall"))
    except Exception:
        return None


def script_to_text(script):
    """LLM1 剧本（中文）渲染成可读文本，便于落盘审阅。"""
    if not isinstance(script, dict):
        return str(script)
    lines = [f"梗概: {script.get('summary_zh') or ''}"]
    shots = script.get("shots") or []
    if shots:
        lines.append(f"分镜 ({len(shots)} 拍):")
        for s in shots:
            if not isinstance(s, dict):
                continue
            st = float(s.get("start_s") or 0)
            du = float(s.get("duration_s") or 0)
            b = s.get("beat") or ""
            fn = s.get("frame_note") or ""
            an = s.get("audio_note") or ""
            lines.append(f"  [{st:.1f}s-{st+du:.1f}s] {b}" + (f" | 帧: {fn}" if fn else "") + (f" | 声: {an}" if an else ""))
    for s_ in script.get("subjects") or []:
        if isinstance(s_, dict):
            who = s_.get("who") or ""
            src = s_.get("source_hint") or ""
            lines.append(f"主体: {who}" + (f"（来源: {src}）" if src else ""))
    for n_ in script.get("closed_loop_notes") or []:
        lines.append(f"硬性要求: {n_}")
    return "\n".join(lines)


def _save_variant(outdir, rel_dir, data):
    """把单个变体的 script + prompt 立即落盘，供渲染失败后复用、避免重生成。"""
    try:
        d = os.path.join(outdir, rel_dir)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "prompt.txt"), "w", encoding="utf-8") as f:
            f.write(data.get("prompt") or "")
        with open(os.path.join(d, "script.json"), "w", encoding="utf-8") as f:
            json.dump(data.get("script"), f, ensure_ascii=False, indent=2)
        with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({k: data.get(k) for k in ("phase", "index", "kind", "focus", "suggestion")},
                      f, ensure_ascii=False, indent=2)
        print(f"    💾 已落盘 {rel_dir}/(prompt.txt, script.json)")
    except Exception as e:
        print(f"    ⚠ 落盘失败: {str(e)[:80]}")


def _load_script_img(llm, cfg):
    """写/改剧本时把图1（首帧参考）编码供 LLM 看图辅助；无图则返回 None。"""
    refs_list = cfg.get("refs") or []
    if refs_list and refs_list[0].get("path"):
        try:
            b64 = llm.encode_image(refs_list[0]["path"])
            print(f"  [图1辅助] 已加载首帧参考图供 LLM 看图写剧本")
            return b64
        except Exception as e:
            print(f"  [图1辅助] 加载失败，回退纯文本: {e}")
    return None


_IMG_HINT = ("\n\n# 附图说明\n下方附图为 <Picture 1>（首帧/背景环境/主体初始姿态/服装/体态参考）。"
             "请据此精确还原视频开头的场景、主体的姿态、服装与体态，使首帧与 <Picture 1> 完全一致；"
             "并保证全程镜头无任何切换/运镜/推拉。")

_I2VA_IMG_HINT = ("\n\n# 附图说明\n下方附图为 <Picture 1>，即目标视频 0.00 秒的第一帧。"
                  "请据此精确还原其风格、主体外观、构图与场景锚点，并让后续动作从这一帧自然发展"
                  "（I2VA 允许分镜与镜头运动，按官方规则写）。")


def _img_hint(cfg, has_img):
    """写剧本时附图说明：I2VA 用首帧版（允许分镜/运镜），Ref2VA 用原版（锁定首帧不切镜）。"""
    if not has_img:
        return ""
    return _I2VA_IMG_HINT if _flow(cfg) == "i2va" else _IMG_HINT


def _valid_script(s):
    """剧本必须非空：有 summary_zh 且至少一拍（含 beat/frame_note）。"""
    if not isinstance(s, dict):
        return False
    if not (s.get("summary_zh") or "").strip():
        return False
    shots = s.get("shots") or []
    return isinstance(shots, list) and any(
        isinstance(sh, dict) and ((sh.get("beat") or "").strip() or (sh.get("frame_note") or "").strip())
        for sh in shots)


def _gen_script_json(llm, system, user, img, attempts=5):
    """生成剧本 JSON（带图则多模态），带重试 + 重试时强提示；空/不完整剧本判失败重试。"""
    _stage("写剧本")
    last = None
    try:
        for attempt in range(1, attempts + 1):
            try:
                script = (llm.vision_json(system, user, [img], max_tokens=16000)
                          if img is not None else llm.chat_json(system, user, max_tokens=16000))
                if _valid_script(script):
                    return script
                last = ValueError("剧本为空或不完整")
                if attempt >= attempts:
                    raise last
                print(f"    [重试 {attempt}/{attempts}] 剧本为空/不完整（缺 summary_zh 或分镜），追加强提示重试…")
                user = (user.rstrip() +
                        "\n\n（注意：你输出了空或缺少关键字段的剧本。请回复一个完整、具体、非空的剧本JSON："
                        "summary_zh 一句话概括，shots 至少一拍（含 beat/frame_note/audio_note），字段照 system 约定。）")
            except Exception as e:
                last = e
                if attempt >= attempts:
                    raise
                print(f"    [重试 {attempt}/{attempts}] 剧本JSON失败({type(e).__name__})，追加强提示重试…")
                user = (user.rstrip() +
                        "\n\n（注意：上一轮你没有输出最终JSON对象。请在回复的最末尾，完整输出一个合法、独立的JSON对象，"
                        "不要只输出思考过程、不要markdown代码块。）")
    finally:
        _stage_end("写剧本")
    raise last


# ============================================================ 单一剧本/转译生成
def _fmt_refs(cfg):
    """把参考图/音频整理成给 LLM 的参考清单。

    **必须 1-based**：H3 提示词用 `<Picture N>` / `<Audio N>` 引用参考，序号从 1 起，
    且第 1 张参考图接到的正是 `ref_image_0` 插槽 → 在 H3 里呈现为 `<Picture 1>`。
    清单里直接标出该标签，避免格式师写成 `<Picture 0>` 或整体错位一位。
    """
    refs = cfg["refs"] or []
    auds = cfg["audios"] or []

    def _desc(item, name):
        n = (item or {}).get("note") or ""
        return f"{name} · 参考：{n}" if n else name

    ref_txt = "\n".join(f"<Picture {i}> = " + _desc(r, nm)
                        for i, (r, nm) in enumerate(zip(refs, cfg["_ref_names"]), 1))
    aud_txt = ("\n# 可用参考音频（序号即提示词中的 <Audio N>，从 1 起）\n"
               + "\n".join(f"<Audio {i}> = " + _desc(a, nm)
                           for i, (a, nm) in enumerate(zip(auds, cfg["_aud_names"]), 1))
               if auds else "")
    aud_desc = cfg.get("_aud_ref_desc") or ""
    if aud_desc:
        aud_txt += "\n\n# 参考音频·声音特征（由音频 LLM 听声分析，生成时应尽量还原）\n" + aud_desc
    return ref_txt, aud_txt


def _translate(llm, cfg, script, tag):
    """把单个剧本转译为完整六段 ref2va prompt 纯文本。

    **prompt 前缀稳定性**：官方指南（约 6k token）放进 system prompt，变化的剧本 JSON
    放到 user 消息最后。这样同一轮优化里的多次调用共享同一前缀，服务端（llama.cpp 等）
    的 KV cache 前缀复用可以直接跳过整份指南的 prefill。"""
    _stage("转译")
    guide = ra._read_guide()
    ref_txt, aud_txt = _fmt_refs(cfg)
    formatter_system = (
        ra.SYSTEM_FORMATTER
        + "\n\n# MiniMax 官方写作指南（附录，必须严格遵守）\n" + guide
    )
    formatter_user = (
        f"# 可用参考图\n{ref_txt}{aud_txt}\n\n"
        f"# 剧本中间产物（{tag}）\n{json.dumps(script, ensure_ascii=False)}\n\n"
        "请转写为完整六段 ref2va prompt 纯文本。"
    )
    prompt = llm.chat(formatter_system, formatter_user, max_tokens=32000)
    _stage_end("转译")
    print(f"  ├─ Ref2VA {tag}（{len(prompt)} 字符）")
    return prompt


def _compose_i2va(llm, cfg, script, tag):
    """I2VA：把中文剧本中间产物写成最终**英文** I2VA 提示词（首帧声明 + 三个核心字段）。
    按官方 I2VA 规则成稿，成品直接喂给 MiniMaxH3ImageToVideo；剧本仍为中文，
    仅台词/画面内文字按规范逐字保留原文。"""
    _stage("写提示词")
    dur = float(cfg.get("duration", 10) or 10)
    refs = cfg.get("refs") or []
    note = (refs[0].get("note") or "").strip() if refs else ""
    ref_txt = "<Picture 1>（目标视频 0.00 秒的首帧）" + (f" · 参考：{note}" if note else "")
    user = (
        f"# 故事大纲\n{cfg.get('story')}\n\n"
        f"# 首帧参考图\n{ref_txt}\n\n"
        f"# 视频时长\n{dur:g} 秒\n\n"
        f"# 剧本中间产物（{tag}）\n{json.dumps(script, ensure_ascii=False)}\n\n"
        "请按 system 规则，直接写成最终 I2VA 英文提示词（首帧声明 + 三个核心字段），只输出提示词正文；"
        "台词与画面内文字按规范逐字保留原文。"
    )
    prompt = llm.chat(ra.system_i2va(dur), user, max_tokens=32000).strip()
    _stage_end("写提示词")
    print(f"  ├─ I2VA {tag}（{len(prompt)} 字符）")
    return prompt


def _compose(llm, cfg, script, tag):
    """按流程选择成稿方式：两条流程最终提示词均为英文（ref2va = 六段 full-reference；i2va = 首帧声明 + 三字段）。"""
    if _flow(cfg) == "i2va":
        return _compose_i2va(llm, cfg, script, tag)
    return _translate(llm, cfg, script, tag)


def gen_fresh(llm, story, cfg, index, prev_weak=None):
    """生成一个全新的完整剧本（整版重写）。
    prev_weak：此前未过准入线的版本薄弱点，用来让新版避开同样问题。"""
    target = cfg.get("optimize_target") or "整体画质与表现最优"
    dur = float(cfg.get("duration", 10) or 10)
    ref_txt, aud_txt = _fmt_refs(cfg)
    weak_hint = ""
    if prev_weak:
        weak_txt = "\n".join(
            f"- 版本{it.get('index')}: overall={it.get('score')} | 低分: {', '.join(it.get('dims') or []) or '无'} | 差距: {'; '.join(it.get('gaps') or [])[:200] or '无'}"
            for it in prev_weak[-6:])
        weak_hint = (
            "\n\n# 此前未过准入线的版本（勿再犯同样问题）\n"
            f"{weak_txt}\n\n请这次把剧本写得明显更好，务必在薄弱维度上做到精确，使分数达到准入线以上。"
        )
    dir_prompt = (
        f"# 故事大纲\n{story}\n\n# 可用参考图\n{ref_txt}{aud_txt}\n\n"
        f"# 优化目标\n{target}\n\n{weak_hint}\n\n"
        f"请围绕优化目标，全新创作一个完整的 {dur:g} 秒剧本（分镜总时长={dur:g}s），"
        "朝整体优化目标做整体优化、不拆分目标；用足够精确的调度/动作/声音/负向约束描写来落实目标。"
    )
    script_img = _load_script_img(llm, cfg)
    img_hint = _img_hint(cfg, script_img)
    script = _gen_script_json(llm, ra.system_director(dur), dir_prompt + img_hint, script_img)
    print(f"\n  ┌─ 全新剧本[{index}]")
    for _l in script_to_text(script).splitlines():
        print(f"  │  {_l}")
    prompt = _compose(llm, cfg, script, f"准入-全新{index}")
    print("  └─ 生成完毕，开始渲染…")
    return {"kind": "admission_rewrite", "script": script, "prompt": prompt, "focus": "整版重写"}


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return -1.0


def weak_parts(rec):
    """提取一次记录的薄弱部分：最低分维度 + 评审 gaps。"""
    critic = rec.get("critic") or {}
    scores = critic.get("scores") or {}
    weak_dims = []
    if isinstance(scores, dict) and scores:
        ranked = sorted(scores.items(), key=lambda kv: _safe_float(kv[1]))
        weak_dims = [f"{d}={_safe_float(v):.1f}" for d, v in ranked[:3]]
    gaps = critic.get("gaps") or []
    return weak_dims, list(gaps[:5])


def ask_suggestion(llm, story, champion, cfg, tried):
    """依优化目标与当前最优薄弱点，给出一个具体修改建议/切入方向。
    tried：已在该基线上试过且未提升的方向，本次须换一个不同的。"""
    target = cfg.get("optimize_target") or "整体画质与表现最优"
    weak_dims, gaps = weak_parts(champion)
    dims_txt = "\n".join(f"- {d}" for d in weak_dims) or "(无明确低分维度)"
    gaps_txt = "\n".join(f"- {g}" for g in gaps) or "(无)"
    tried_txt = ("\n".join(f"- {t}" for t in tried[-8:])) if tried else "(无，首次建议)"
    prompt = (
        f"# 优化目标\n{target}\n\n"
        f"# 当前最优剧本概要\n{script_to_text(champion.get('script'))}\n\n"
        f"# 当前评分\noverall={champion.get('score')}\n\n"
        f"# 低分维度（未拿满分）\n{dims_txt}\n\n# 评审差距\n{gaps_txt}\n\n"
        f"# 已在此基线上试过且未提升的方向\n{tried_txt}\n\n"
        "请针对优化目标与上述薄弱点，给出【一个】明确的修改建议（切入角度）：具体到改哪一段、怎么改，"
        "只针对薄弱部分做定点改进，不动已达标处，且不要推倒重来。"
        "必须与上面「已试过的方向」不同。只输出一段话（方向说明 + 具体改法），不要输出其他文字。"
    )
    for _ in range(2):
        try:
            s = llm.chat("你是视频提示词优化专家，只输出建议本身。", prompt, max_tokens=2000).strip()
            if s and not s.lower().startswith(("好的", "是", "{")):
                return s[:500]
        except Exception:
            pass
    return f"强化低分维度并修复评审差距（避开已试方向）"


def gen_child(llm, story, champion, cfg, suggestion):
    """在最优剧本上按建议定点修正，生成一个子变体。"""
    target = cfg.get("optimize_target") or "整体画质与表现最优"
    dur = float(cfg.get("duration", 10) or 10)
    weak_dims, gaps = weak_parts(champion)
    dims_txt = "\n".join(f"- {d}" for d in weak_dims) or "(无)"
    gaps_txt = "\n".join(f"- {g}" for g in gaps) or "(无)"
    ref_txt, aud_txt = _fmt_refs(cfg)
    script_img = _load_script_img(llm, cfg)
    img_hint = _img_hint(cfg, script_img)
    director_user = (
        f"# 故事大纲\n{story}\n\n# 可用参考图\n{ref_txt}{aud_txt}\n\n"
        f"# 优化目标\n{target}\n\n"
        f"# 当前最优剧本\n{json.dumps(champion['script'], ensure_ascii=False)}\n\n"
        f"# 当前评分\noverall={champion.get('score')}\n\n"
        f"# 低分维度（未拿满分）\n{dims_txt}\n\n# 评审差距\n{gaps_txt}\n\n"
        f"# 本轮修改建议（只按此定点改进）\n{suggestion}\n\n"
        "请【修正】这个剧本：保持整体方向与风格不变，只按上面的建议把低分维度/差距改好，"
        "不要推倒重来、不要顺手改已达标处。"
        f"{img_hint}"
        "按 system 约定的 JSON 结构输出。"
    )
    new_script = _gen_script_json(llm, ra.system_director(dur), director_user, script_img)
    print(f"\n  ┌─ 子变体剧本（建议: {suggestion[:60]}）")
    for _l in script_to_text(new_script).splitlines():
        print(f"  │  {_l}")
    prompt = _compose(llm, cfg, new_script, "爬山-子变体")
    print("  └─ 生成完毕，开始渲染…")
    return {"kind": "hill_child", "script": new_script, "prompt": prompt,
            "focus": suggestion, "suggestion": suggestion}


def _report(rec):
    """出报告：打印单个变体的结构化评审摘要。"""
    if not rec:
        return
    c = rec.get("critic") or {}
    scores = c.get("scores") or {}
    dims = " | ".join(f"{k}={_safe_float(v):.1f}" for k, v in
                      (sorted(scores.items(), key=lambda kv: _safe_float(kv[1])) if isinstance(scores, dict) else []))
    print(f"  ┌─ 报告 · {rec.get('label')}  [{rec.get('kind')}]")
    print(f"  │  切入/建议: {(rec.get('focus') or '')[:80]}")
    print(f"  │  overall = {rec.get('score')}")
    print(f"  │  verdict = {(c.get('verdict') or '')[:200]}")
    if dims:
        print(f"  │  分维度: {dims}")
    print(f"  │  视频: {rec.get('video')}")
    print("  └─")


def run_attempt(llm, cand, story, cfg, outdir, label, seed, index, audio_llm=None,
                use_audio=False):
    """把单个变体保存 + 渲染 + 评审打分 + 出报告，返回记录（score 可能为 None）。"""
    rd = os.path.join(outdir, label)
    os.makedirs(rd, exist_ok=True)
    _save_variant(outdir, label, {**cand, "phase": None, "index": index})
    print(f"  ⏳ 渲染 {label}…")
    video = render(build_gcfg(cfg, cand["prompt"], seed), rd)
    if not video:
        print(f"    ✗ {label} 无输出，跳过")
        return None
    critic = evaluate(llm, video, story, cand["prompt"], rd,
                      audio_llm=audio_llm, use_audio=use_audio,
                      n_frames=int(cfg.get("review_frames", 32)),
                      frame_width=int(cfg.get("review_frame_width", 448)),
                      frame_jpeg=bool(cfg.get("review_frame_jpeg", True)),
                      target=cfg.get("optimize_target"))
    sc = score_of(critic)
    rec = {**cand, "label": label, "index": index, "video": video, "critic": critic, "score": sc}
    _report(rec)
    return rec


# ============================================================ 主流程
def run_optimizer(cfg, llm):
    outdir = cfg["outdir"]
    os.makedirs(outdir, exist_ok=True)
    seed = int(cfg["seed"]) if cfg.get("seed") is not None else random.randint(0, 2**31 - 1)
    story = cfg["story"]
    i2v = _flow(cfg) == "i2va"
    video_edit = bool(cfg.get("video_edit")) and not i2v
    if i2v:
        cfg["video_edit"] = False        # I2VA 只吃首帧图，没有 B 方式（视频编辑）演化
        cfg["video_ref"] = None
    if video_edit:
        cfg["video_ref"] = None   # 准入首步无上一步视频，不注入；爬山/精渲阶段再带上一步生成的视频

    admission = float(cfg.get("admission_threshold", 5))     # 准入线
    max_iter = int(cfg.get("max_iterations", 12))            # 总生成次数上限
    base_patience = int(cfg.get("base_patience", 3))         # 同一基线连续未提升多少次停
    threshold = cfg.get("threshold")                          # 早期达标线(可选)
    manual = (cfg.get("stop_mode") or "auto") == "manual"

    print("=" * 60)
    print("提示词优化器（顺序爬山 · 准入→演进）")
    print(f"流程     : {'I2VA · 首帧图生视频（英文提示词：首帧声明 + 三字段）' if i2v else 'Ref2VA · 参考图/视频（六段英文）'}")
    print(f"服务器   : {ra.get_comfy_url()}")
    print(f"写入/评分 LLM: {getattr(llm, 'base', '?')}  /  {getattr(llm, 'model', '?')}")
    if i2v:
        print("参考方式 : 首帧参考图（强制作为视频第一帧）| 不吃参考音频")
        print(f"参考图   : {len(cfg['_ref_names'][:1])} 张（仅取第 1 张作首帧）")
    else:
        print(f"参考方式 : {'B · 视频编辑（自动用上一步视频）' if cfg.get('video_edit') else 'A · 仅参考图/文字'}")
        print(f"参考图   : {len(cfg['_ref_names'])} 张 | 音频: {len(cfg['_aud_names'])} 条")
    _qmp, _qst = _quick_scale(cfg, cfg.get("megapixels"), cfg.get("steps", 20))
    if cfg.get("quick_render"):
        print(f"渲染     : 快速（分辨率 {cfg.get('megapixels')}→{_qmp}MP，步数 {cfg.get('steps')}→{_qst}）")
    else:
        print("渲染     : 精渲（全分辨率/全步数）")
    print(f"视频     : {_qmp}MP {normalize_aspect(cfg.get('aspect'))} {cfg.get('duration')}s")
    print(f"种子     : {seed}（全程恒定）| 准入线≥{admission} | 迭代上限 {max_iter} | 同基线耐心 {base_patience}")
    print("=" * 60)

    # ---- 前置依赖检查：ffmpeg（评分抽帧/抽音频必需）----
    import shutil
    if not shutil.which("ffmpeg"):
        print("✗ 未检测到 ffmpeg：评审需要用它从视频抽帧（以及可选抽音频）。", file=sys.stderr)
        print("  请先安装 ffmpeg 并加入系统 PATH，否则无法优化评分：", file=sys.stderr)
        print("  · Windows: winget install ffmpeg   或   从 https://ffmpeg.org/download.html 下载解压，"
              "把 bin 目录加入 PATH 后重开终端。", file=sys.stderr)
        sys.exit(2)

    attempts = []       # 所有已渲染尝试（准入重写 + 爬山子变体）
    champion = None     # 当前最优
    iteration = 0       # 全局生成计数（准入重写与爬山共用，停线依据之一）
    stop_reason = None

    # ---- 音频通道：涉声评分 或 有参考音频 时连音频 LLM ----
    use_audio = _audio_mode(cfg, story)
    has_ref_audio = bool(cfg.get("_aud_names"))
    audio_conf = bool(cfg.get("audio_llm_base") or cfg.get("audio_llm_model"))
    need_audio_llm = use_audio or (has_ref_audio and audio_conf)
    audio_llm = None
    if need_audio_llm:
        try:
            audio_llm = LLM(model=cfg.get("audio_llm_model") or None,
                            base=cfg.get("audio_llm_base") or None,
                            api_key=cfg.get("audio_llm_api_key") or None)
            print("🎧 音频通道开启：" + "，".join(
                [s for s in ["涉声评审" if use_audio else "", "参考音频分析" if has_ref_audio else ""] if s]))
        except Exception as e:
            print(f"    ⚠ 音频 LLM 实例化失败，关闭音频通道: {str(e)[:80]}")
            audio_llm = None
    else:
        print("🔇 音频通道关闭：不涉声、无参考音频，或未配置音频 LLM")

    # ---- 参考音频：交给音频 LLM 听声，把「用途 + 声音特征」写入提示词（供写剧本/转译还原） ----
    if has_ref_audio and audio_llm is not None and not cfg.get("_aud_ref_desc"):
        try:
            descs = []
            for i, aud in enumerate(cfg["audios"] or []):
                p = aud.get("path")
                note = (aud.get("note") or "").strip()
                if p and os.path.isfile(p):
                    d = analyze_ref_audio(audio_llm, p, note)
                    if d:
                        descs.append(f"- <Audio {i+1}>（用途：{note}）: {d}" if note else f"- <Audio {i+1}>: {d}")
            if descs:
                cfg["_aud_ref_desc"] = "\n".join(descs)
                print(f"  [参考音频] 已分析 {len(descs)} 条声音特征 -> 写入提示词")
        except Exception as e:
            print(f"    ⚠ 参考音频分析异常: {str(e)[:80]}")

    # ================= 准入 =================
    print(f"\n【阶段一·准入】整版全新创作直到 overall ≥ {admission} …")
    rew_index = 0
    prev_weak = []
    while champion is None:
        iteration += 1
        rew_index += 1
        if iteration > max_iter:
            stop_reason = f"迭代上限({max_iter}，准入阶段耗光，未过准入线)"
            break
        if manual:
            if ask(f"准入重写第 {rew_index} 版？", "y").lower() not in ("y", "yes"):
                stop_reason = "手动停止"
                break
        _bp = os.path.join(outdir, "baseline", "prompt.txt")
        _bs = os.path.join(outdir, "baseline", "script.json")
        if rew_index == 1 and os.path.exists(_bp) and os.path.exists(_bs):
            try:
                with open(_bp, encoding="utf-8") as _f:
                    _base_prompt = _f.read()
                with open(_bs, encoding="utf-8") as _f:
                    _base_script = json.load(_f)
                cand = {"kind": "admission_rewrite", "script": _base_script,
                        "prompt": _base_prompt, "focus": "整版重写(基准预生成)"}
                print("  [基准] 已载入预生成的 baseline script+prompt 作为首次准入")
            except Exception as _e:
                print(f"  [基准] 载入失败，回退 LLM 生成: {_e}")
                cand = gen_fresh(llm, story, cfg, rew_index, prev_weak)
        else:
            cand = gen_fresh(llm, story, cfg, rew_index, prev_weak)
        label = f"admit{rew_index:02d}"
        rec = run_attempt(llm, cand, story, cfg, outdir, label, seed, index=rew_index,
                          audio_llm=audio_llm, use_audio=use_audio)
        if rec is None:
            # 渲染失败：不计入 prev_weak，退回重写（消耗一次迭代）
            continue
        attempts.append(rec)
        if rec["score"] is not None and rec["score"] >= admission:
            champion = rec
            print(f"\n  🎯 准入达标! overall={champion['score']} ≥ {admission}，成为爬山基准")
        elif rec["score"] is None:
            print("    → 无有效评分，继续重写…")
        else:
            dims, gaps = weak_parts(rec)
            prev_weak.append({"index": rew_index, "score": rec["score"], "dims": dims, "gaps": gaps})
            print(f"    → overall={rec['score']} < {admission}，整版重写剧本…")

    if champion is None:
        print(f"\n✗ 未能在预算内过准入线，终止。原因: {stop_reason}")
        _finalize(outdir, champion, attempts, seed, stop_reason)
        return None

    # ================= 爬山 =================
    print(f"\n【阶段二·爬山】在最优基础上逐个演进（退步则同基线换方向重试，连续 {base_patience} 次未提升即停）…")
    hill_no = 0
    while True:
        # 停线检查（每步前进前）
        if threshold is not None and champion["score"] is not None and champion["score"] >= threshold:
            stop_reason = f"达标(overall={champion['score']} ≥ {threshold})"
            break
        if iteration >= max_iter:
            stop_reason = f"迭代上限({max_iter})"
            break
        if manual:
            cont = ask(f"继续爬山第 {hill_no + 1} 步（当前最优 overall={champion['score']}）？", "n")
            if cont.lower() not in ("y", "yes"):
                stop_reason = "手动停止"
                break

        # 已在本基线上试过且未提升的方向，用于让 LLM 换新方向
        tried_on_base = [a.get("suggestion") for a in attempts
                         if a.get("kind") == "hill_child" and not a.get("_improved")
                         and a.get("_base_score") == champion["score"]]
        tried_txt = [t for t in tried_on_base if t]

        hill_no += 1
        iteration += 1
        suggestion = ask_suggestion(llm, story, champion, cfg, tried_txt)
        print(f"\n  💡 建议: {suggestion}")
        cand = gen_child(llm, story, champion, cfg, suggestion)
        label = f"hill{hill_no:02d}"
        if video_edit:
            cfg["video_ref"] = _sync_video_ref(champion.get("video"))
        rec = run_attempt(llm, cand, story, cfg, outdir, label, seed, index=hill_no,
                          audio_llm=audio_llm, use_audio=use_audio)
        if rec is None:
            # 渲染失败：不提升也不停，重新给建议再测（继续迭代计数）
            print("    → 渲染失败，退回当前最优换方向再试…")
            continue
        attempts.append(rec)
        sc = rec["score"]
        cur = champion["score"]
        if sc is not None and sc > cur:
            rec["_improved"] = True
            rec["_base_score"] = cur
            champion = rec
            print(f"\n  🏆 采纳新最优! overall={sc}（较 {cur} +{sc - cur:.2f}）→ 继续往前爬")
        elif sc is None:
            rec["_base_score"] = cur
            print("    → 无有效评分，退回当前最优换方向再试…")
        else:
            rec["_base_score"] = cur
            # 同一基线上的连续失败判定：统计该基线上所有未提升子变体
            fails_on_base = sum(1 for a in attempts
                                if a.get("kind") == "hill_child"
                                and a.get("score") is not None
                                and a.get("score") <= a.get("_base_score")
                                and a.get("_base_score") == cur)
            print(f"    → overall={sc} 未超过当前最优 {cur}（同基线上已累计 {fails_on_base}/{base_patience} 次未提升）")
            if fails_on_base >= base_patience:
                stop_reason = f"同基线连续 {base_patience} 次未提升（刷不动）"
                break
            print("    → 退回当前最优，换新方向重试…")

    # ================= 尾部精细化渲染（快速模式可选用原工作流做最终精渲） =================
    if champion is not None and cfg.get("fine_render"):
        fine_cfg = dict(cfg)
        fine_cfg["quick_render"] = False        # 精渲恒为全分辨率/全步数
        if video_edit:
            fine_cfg["video_ref"] = _sync_video_ref(champion.get("video"))
        fine_gcfg = build_gcfg(fine_cfg, champion["prompt"], seed)
        fine_dir = os.path.join(outdir, "fine")
        print("\n[精细化渲染] 用原工作流对最优提示词做一次精细渲染（快速模式已定位最优；精渲为最终产物）…")
        fine_video = render(fine_gcfg, fine_dir)
        if fine_video:
            champion["video_fine"] = fine_video
            print(f"  ✅ 精细渲染视频: {fine_video}")
        else:
            print("  ⚠ 精细渲染无输出，回退使用快速渲染版")

    # ================= 汇总 / 落盘 =================
    _finalize(outdir, champion, attempts, seed, stop_reason)
    return champion


def _finalize(outdir, champion, attempts, seed, stop_reason):
    print("\n" + "=" * 60)
    if champion is None:
        print("【优化结束】无达标基准")
        return
    print("【优化结束】")
    print(f"  停止原因: {stop_reason}")
    print(f"  最终最优: overall={champion['score']}  verdict={(champion.get('critic') or {}).get('verdict')}")
    print(f"  快速版视频: {champion['video']}")
    if champion.get("video_fine"):
        print(f"  ✅ 精细渲染版视频: {champion['video_fine']}")
    print(f"  经历 {len(attempts)} 次渲染（准入 {sum(1 for a in attempts if a.get('kind')=='admission_rewrite')} + 爬山 {sum(1 for a in attempts if a.get('kind')=='hill_child')}）")
    print("=" * 60)

    champ_prompt = os.path.join(outdir, "champion_prompt.txt")
    with open(champ_prompt, "w", encoding="utf-8") as f:
        f.write(champion["prompt"])
    champ_script = os.path.join(outdir, "champion_script.txt")
    with open(champ_script, "w", encoding="utf-8") as f:
        f.write(script_to_text(champion["script"]) + "\n\n# —— LLM1 原始 JSON ——\n"
                + json.dumps(champion["script"], ensure_ascii=False, indent=2))
    hist = os.path.join(outdir, "optimizer_history.json")
    with open(hist, "w", encoding="utf-8") as f:
        json.dump({
            "stop_reason": stop_reason,
            "seed": seed,
            "champion": {
                "label": champion["label"], "score": champion["score"],
                "video": champion["video"],
                "video_fine": champion.get("video_fine"),
                "verdict": (champion.get("critic") or {}).get("verdict"),
            },
            "attempts": [{
                "label": a["label"], "kind": a.get("kind"), "score": a["score"],
                "video": a["video"], "verdict": (a.get("critic") or {}).get("verdict"),
                "prompt_len": len(a["prompt"]),
            } for a in attempts],
        }, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已导出:")
    print(f"    {champ_prompt}")
    print(f"    {champ_script}")
    print(f"    {hist}")


def load_config(path):
    with open(path, encoding="utf-8-sig") as f:
        c = json.load(f)
    c.setdefault("comfy_url", "http://127.0.0.1:8000")
    c.setdefault("refs", [])
    c.setdefault("audios", [])
    c.setdefault("model", None)
    c.setdefault("clip", None)             # CLIP 模型名（ComfyUI 内名字，含子目录；空=用模板默认/前次成功）
    c.setdefault("loras", [])              # LoRA 列表 [{"name":..., "strength":...}]；空=不加 LoRA
    c.setdefault("lora", None)             # 兼容旧单 LoRA 字段；一般用上面的 loras 列表
    c.setdefault("lora_strength", 1.0)
    c.setdefault("sampler", None)
    c.setdefault("scheduler", None)
    c.setdefault("steps", 20)
    c.setdefault("seed", None)
    c.setdefault("megapixels", 0.4)
    c.setdefault("aspect", "4:3 (Standard)")
    c.setdefault("duration", 10)
    c.setdefault("video_edit", False)          # B 方式：自动用上一步生成的视频作候选参考
    c.setdefault("quick_render", False)        # 快速渲染：仅分辨率与步数 ×0.707（其余同精渲）
    c.setdefault("fine_render", True)          # 结束精渲：爬山结束后用全分辨率/全步数再渲一次
    c.setdefault("flow", "ref2va")             # 流程：ref2va（默认）| i2va（首帧图生视频，英文提示词）
    c.setdefault("optimize_target", None)
    c.setdefault("admission_threshold", 5)
    c.setdefault("max_iterations", 12)
    c.setdefault("base_patience", 3)
    c.setdefault("threshold", None)
    c.setdefault("stop_mode", "auto")
    c.setdefault("llm_model", None)
    c.setdefault("llm_api_key", None)           # 云端/API LLM 需要时填写；本地可不填
    c.setdefault("audio_scoring", "off")           # 默认关闭；仅在配有音频 LLM 且需要时开启(on)
    # 音频评审为可选通道：仅当任务涉及声音且配置了音频 LLM 时才启用，不在代码里写死任何服务器/模型。
    c.setdefault("audio_llm_base", None)
    c.setdefault("audio_llm_model", None)
    c.setdefault("audio_llm_api_key", None)
    c.setdefault("review_frames", 32)          # 评审抽帧数量
    c.setdefault("review_frame_width", 448)     # 评审抽帧宽度（JPEG 压缩，缩小图片 token/加速预填充）
    c.setdefault("review_frame_jpeg", True)
    c.setdefault("outdir", os.path.join(HERE, "outputs", "optimizer"))
    # 主 LLM 服务器必须显式指定：每次任务启动时填写，不写死，可随时切换专用服务器或云端模型
    _missing = []
    if not c.get("llm_base"):
        _missing.append("llm_base（画面+文字 LLM 服务器地址，如 http://127.0.0.1:8080/v1）")
    if not c.get("llm_model"):
        _missing.append("llm_model（画面+文字 LLM 模型 id，用该服务器 /v1/models 查询）")
    if _missing:
        raise SystemExit(
            "[config 校验失败] 缺失必填字段（主 LLM 服务器每次任务需显式指定）：\n  - "
            + "\n  - ".join(_missing)
            + "\n请用 <llm_base>/v1/models 查询该服务器的模型 id 后填入 llm_base / llm_model。")
    ra.set_comfy_url(c["comfy_url"])
    # 解析参考文件 → input 目录可用名
    c["_ref_names"] = ra.sync_ref_files([r["path"] for r in c["refs"]])
    c["_aud_names"] = ra.sync_ref_files([a["path"] for a in c["audios"]]) if c["audios"] else []
    # ---- I2VA：必须且只取 1 张参考图作为视频首帧；不吃参考音频（快速渲染同样适用）----
    if (c.get("flow") or "ref2va").strip().lower() == "i2va":
        if not c["refs"]:
            raise SystemExit("[config 校验失败] I2VA 流程必须提供 1 张参考图作为视频首帧。")
        c["refs"] = c["refs"][:1]
        c["_ref_names"] = c["_ref_names"][:1]
        c["audios"] = []
        c["_aud_names"] = []
        c["video_edit"] = False
    return c


def main():
    p = argparse.ArgumentParser(description="Ref2VA 提示词优化器（顺序爬山）")
    p.add_argument("--config", required=True, help="配置文件路径（JSON）")
    p.add_argument("--dry-run", action="store_true", help="只加载配置并打印，不执行")
    args = p.parse_args()
    cfg = load_config(args.config)
    if args.dry_run:
        print("配置加载成功：")
        print(json.dumps({k: v for k, v in cfg.items() if not k.startswith("_")},
                         ensure_ascii=False, indent=2))
        print("参考图(input 名):", cfg["_ref_names"])
        print("参考音频(input 名):", cfg["_aud_names"])
        return
    llm = LLM(model=cfg.get("llm_model") or None,
              base=cfg.get("llm_base") or None,
              api_key=cfg.get("llm_api_key") or None)
    run_optimizer(cfg, llm)


if __name__ == "__main__":
    main()
