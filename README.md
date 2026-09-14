# Ref2VA H3 视频提示词优化器（Web 控制台版）

> 版本：**v1.0 正式版** · 协议：MIT · 联系：微博 @快乐肥宅庆先森

一个**本地 Web 界面驱动**的 MiniMax-H3 视频提示词迭代优化器，支持两条流程：

- **Ref2VA**（参考图/视频 → 视频）：六段英文 full-reference 提示词，支持 A/B 两种参考模式；
- **I2VA**（首帧图生视频）：**1 张**参考图强制作为视频第一帧，按 MiniMax 官方 I2VA 规范直出**英文**提示词（首帧声明 + 三字段）。剧本仍为中文，仅台词/画面内文字按规范逐字保留原文。不吃参考音频、无快速渲染模式。

它把提示词当作唯一变量，在固定模型/参数/种子下，通过 LLM 写剧本 → ComfyUI 渲染 → LLM 评分收敛，逐步把一条视频的提示词优化到更好画质/表现。

---

## 它做什么

```
写剧本(LLM) → 成稿提示词 → ComfyUI 渲染 → 抽帧/评分(LLM) → 依分数重写/演进
                    └──────────── 达标 / 迭代上限 / 刷不动 则出最终最优 ────────────┘
    成稿方式：两条流程均按官方规范写**英文** —— Ref2VA = 六段 full-reference；I2VA = 首帧声明 + 三字段
```

- **准入**：先拿到一条 ≥ 分数的合格基线；
- **爬山**：在基线上按“优化目标+薄弱点”逐个改进，只采纳更好的，退步换方向重试；
- **精渲**：可选用全质量工作流对最优提示词再渲一次最终产物。

## 主要特性

- **两条流程可选（I2VA / Ref2VA）**：在参考图区上方切换。**I2VA** 只能选 1 张参考图并强制作为视频第一帧，按官方 I2VA 规范直出**英文**提示词（首帧声明 + `integrated_multimodal_description` / `overall_soundscape` / `non_diegetic_music` 三字段）。
- **A / B 两种参考模式**（仅 Ref2VA）：A=仅参考图/文字（省显存、效果略差）；B=视频编辑（显存高、效果最佳，自动用上一步生成的视频作参考，无需传视频）。
- **参考素材逐个注明用途**：每张参考图/每条参考音频都可填“参考什么”，连同**音频 LLM 听声分析出的声音特征**一起写入提示词（音频参考功能）。
- **纯文字 T2VA**：参考图可全留空＝纯文字驱动生成。
- **ComfyUI 模型一键读取**：自动列出 UNET / CLIP / VAE / LoRA / 采样器 / 调度器，下拉/可搜选择；模型名提交前**自动规范化**（含子目录前缀自愈，裸名也能对上）。
- **LLM 模型一键读取**：填地址+API Key 后读取该端点 `/v1/models` 的可选模型。
- **任务排队 + 历史回看**：任务运行时可“任务排队”，串行依次执行；历史可按任务轮询日志并回填该任务预填信息。
- **强制终止**：终止运行/排队任务，并**定向取消它提交到 ComfyUI 的作业**（不影响其它排队任务）。
- **日志分阶段 + 时间戳 + 耗时**：写剧本/转译/渲染/评分每阶段打印 `[HH:MM:SS]` 与耗时；日志可**自动/手动**刷新。
- **LoRA 加载器**：可加多条 LoRA、各设强度，精渲与快速模式都生效。
- **转译不限字数**：严格按剧本**逐拍详转写尽**，复杂剧本锚定更精确。
- **发布包闭源**：`.py` 已转义（源码不出现中文），开箱即用。

## 环境要求

- **Python 3.10+**（工作台只用标准库，无需第三方 pip 依赖；用系统 Python 即可）。
- **ComfyUI**：已装 MiniMax-H3 模型（UNET/CLIP/VAE）与所需自定义节点（含 `ComfyUI-KJNodes`）；加速 LoRA（如有）由你在页面自行加载，本项目不内置、不依赖任何特定 LoRA。
- **一个 OpenAI 兼容的 LLM 端点**（能看图/多模态，用于写剧本与评分；也可用云端 API）。
- **ffmpeg**：需位于 PATH 且名为 `ffmpeg.exe`（用于评分前抽帧/抽音频；缺失会明确报错并中止，而不是无限重写）。
- 参考音频分析需另配**音频 LLM**（可选）。

## 快速开始

1. 解压到任意目录，双击 **`run.bat`**（自动选 Python、起服务、自动打开浏览器）。
   - 本机访问 `http://127.0.0.1:8090/`；局域网 `http://<本机IP>:8090/`。
   - 若找不到 `python`，在 `run.bat` 顶部加 `set "PYTHON=C:\你的Python\python.exe"`。
2. 页面上：
   - 填 **ComfyUI 地址** → 点「读取 ComfyUI 模型列表」→ 选好 **模型/CLIP/LoRA/采样器/调度器**；
   - 填 **LLM 地址/模型/API Key** →（可选）点「读取 LLM 模型列表」；
   - 在参考图区上方选 **流程**：**Ref2VA** 支持多图/参考音频与 A/B 模式；**I2VA** 只需 1 张首帧图（A/B 与参考音频会自动隐藏）；
   - 填**画面描述**、上传**参考图/音频**（可选，注明用途）；
   - 点「运行优化」/「任务排队」，页面看日志与结果视频。

## 配置字段（`config.json`，主要）

| 字段 | 说明 |
|------|------|
| `story`（必填） | 画面内容/剧情描述 |
| `flow` | 流程：`ref2va`（默认）或 `i2va`（首帧图生视频） |
| `optimize_target` | 本轮要重点达成的质量点 |
| `refs` / `audios` | 参考图/音频：`[{path, note}]` |
| `video_edit` | 是否 B 方式（自动用上一步视频作参考） |
| `llm_base` / `llm_model` / `llm_api_key` | 写剧/评分 LLM（必填地址+模型） |
| `audio_llm_base` / `audio_llm_model` / `audio_llm_api_key` | 音频 LLM（可选，做参考音频分析/音频评审） |
| `comfy_url` | ComfyUI 地址（默认 `http://127.0.0.1:8000`） |
| `model` / `clip` / `loras` | 模型名 / CLIP 名 / `[{name,strength}]`（ComfyUI 内全名，提交前自动规范化） |
| `sampler` / `scheduler` / `steps` | 采样器/调度器/步数；**两条流程均按此生效**（勾选快速渲染时步数自动 ×0.707） |
| `megapixels` / `aspect` / `duration` | 分辨率 / 画幅 / 时长 |
| `quick_render` / `fine_render` | 快速渲染（仅分辨率与步数 ×0.707，耗时约减半）/ 结束精渲（全分辨率全步数再渲一次） |
| `admission_threshold` / `max_iterations` / `base_patience` | 准入线 / 迭代上限 / 同基线耐心 |

> **快速渲染（`quick_render`）**：模型、采样器、时长、画幅、LoRA 与精渲**完全相同**，只把
> 分辨率（`megapixels`）与采样步数各乘 **0.707** 并向下取整（分辨率按 `ResolutionSelector` 的
> `step=0.1` 取整，步数取整到整数、下限 1）。因 0.707 × 0.707 = 0.5，渲染耗时约为精渲的一半，
> 提示词遵从度下降有限。该模式**不注入任何 LoRA**——要加速请在页面「LoRA」区自行加载。

## 目录结构

```
ref2va-h3-video-optimizer-1.0/
├── run.bat          一键启动（自动开浏览器）
├── server.py        本地 Web 服务（纯标准库）
├── optimizer.py     顺序爬山优化主逻辑
├── comfy.py         ComfyUI 操作工具（纯标准库）
├── core/            llm 客户端 / ref2va 构图与评审 / MiniMax 官方指南
├── web/             前端页面（index.html）
├── workflows/       Ref2VA / I2VA 两套工作流模板
├── examples/        示例配置
├── README.md / USAGE.md / 使用说明.md / RELEASE_NOTES.md
└── LICENSE
```

## 常见问题

- **模型名报 `not in list`**：在页面用「读取 ComfyUI 模型列表」选真实名即可（提交前会自动规范化，含子目录）。
- **`value_not_in_list` 采样器/调度器**：用下拉/候选输入框选 ComfyUI 里的值。
- **`[warn] 未找到 ffmpeg` → 无限重写/无评分**：装 ffmpeg 并确认名为 `ffmpeg.exe` 且在 PATH；缺失会直接报错并中止（已加固）。
- **参考音频分析**：需配置音频 LLM，并给参考音频注明“参考什么”。
- **B 方式**：显存占用更高，依赖本机 ComfyUI 在线。
- **I2VA 提示「必须提供 1 张参考图」**：I2VA 流程必须上传 1 张图，它会**强制作为视频第一帧**（多余参考图会被忽略）。
- **I2VA 下「模式 A/B」「参考音频」不见了**：属正常——I2V 工作流只吃首帧图、不吃参考音频。（**快速渲染两条流程都可用**。）
- **I2VA 渲染报节点缺失**：需 ComfyUI 装有 `MiniMaxH3ImageToVideo` / `MiniMaxH3SigmaShift` / `ResolutionSelector` / `ComfyMathExpression` 等节点，以及 `ComfyUI-KJNodes` 提供的 **`PathchSageAttentionKJ`**（`sage_attention=sageattn3`）与 **`MiniMaxH3MemoryEfficientSageAttentionPatch`**（两者与 Ref2VA 相同，需 sageattention 3）。I2V 用的 UNET/VAE/CLIP 需自行准备。
- **加速 LoRA**：两条流程的工作流都**不含任何内置 LoRA**，快速渲染也只是缩分辨率与步数、不会替你加载 LoRA。需要加速（lightx2v / 8 步 turbo 类）时，在页面「LoRA」区自行添加（可用「读取 ComfyUI 模型列表」列出），并把步数设成与该 LoRA 匹配的值。

## 许可

MIT License（见 `LICENSE`）。模型文件/ffmpeg 等外部依赖需自行准备。
