# Ref2VA H3 视频提示词优化器（Web 控制台版）

> 版本：**v1.0 正式版** · 协议：MIT · 联系：微博 @快乐肥宅庆先森

一个**本地 Web 界面驱动**的 MiniMax-H3 Ref2VA（Reference-to-Video）视频提示词迭代优化器。
它把提示词当作唯一变量，在固定模型/参数/种子下，通过 LLM 写剧本 → ComfyUI 渲染 → LLM 评分收敛，逐步把一条视频的提示词优化到更好画质/表现。

---

## 它做什么

```
写剧本(LLM) → 转译成 ref2va 提示词 → ComfyUI 渲染 → 抽帧/评分(LLM) → 依分数重写/演进
                    └──────────── 达标 / 迭代上限 / 刷不动 则出最终最优 ────────────┘
```

- **准入**：先拿到一条 ≥ 分数的合格基线；
- **爬山**：在基线上按“优化目标+薄弱点”逐个改进，只采纳更好的，退步换方向重试；
- **精渲**：可选用全质量工作流对最优提示词再渲一次最终产物。

## 主要特性

- **A / B 两种参考模式**：A=仅参考图/文字（省显存、效果略差）；B=视频编辑（显存高、效果最佳，自动用上一步生成的视频作参考，无需传视频）。
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
- **ComfyUI**：已装 MiniMax-H3 模型（UNET/CLIP/VAE）、turbo LoRA（可选）、`ComfyUI-MiniMax-H3-Turbo` 与 `ComfyUI-KJNodes` 自定义节点。
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
   - 填**画面描述**、上传**参考图/音频**（可选，注明用途）、选 **A/B 模式**；
   - 点「运行优化」/「任务排队」，页面看日志与结果视频。

## 配置字段（`config.json`，主要）

| 字段 | 说明 |
|------|------|
| `story`（必填） | 画面内容/剧情描述 |
| `optimize_target` | 本轮要重点达成的质量点 |
| `refs` / `audios` | 参考图/音频：`[{path, note}]` |
| `video_edit` | 是否 B 方式（自动用上一步视频作参考） |
| `llm_base` / `llm_model` / `llm_api_key` | 写剧/评分 LLM（必填地址+模型） |
| `audio_llm_base` / `audio_llm_model` / `audio_llm_api_key` | 音频 LLM（可选，做参考音频分析/音频评审） |
| `comfy_url` | ComfyUI 地址（默认 `http://127.0.0.1:8000`） |
| `model` / `clip` / `loras` | 模型名 / CLIP 名 / `[{name,strength}]`（ComfyUI 内全名，提交前自动规范化） |
| `sampler` / `scheduler` / `steps` | 采样器/调度器/步数；快速工作流会固定 `euler+beta+8` |
| `megapixels` / `aspect` / `duration` | 分辨率 / 画幅 / 时长 |
| `quick_workflow` / `fine_render` | 快速(turbo 8 步) / 结束精渲 |
| `admission_threshold` / `max_iterations` / `base_patience` | 准入线 / 迭代上限 / 同基线耐心 |

> 快速工作流（turbo 8 步）需在 `ComfyUI\models\lora\` 下有
> `minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_resized_avg_rank_64_bf16.safetensors`；缺失自动回退标准工作流。

## 目录结构

```
ref2va-h3-video-optimizer-1.0/
├── run.bat          一键启动（自动开浏览器）
├── server.py        本地 Web 服务（纯标准库）
├── optimizer.py     顺序爬山优化主逻辑
├── comfy.py         ComfyUI 操作工具（纯标准库）
├── core/            llm 客户端 / ref2va 构图与评审 / MiniMax 官方指南
├── web/             前端页面（index.html）
├── workflows/       标准 / 快速 两套工作流模板
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

## 许可

MIT License（见 `LICENSE`）。模型文件/ffmpeg 等外部依赖需自行准备。
