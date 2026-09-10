# 使用说明（Quick start）

本页只讲**怎么把优化器跑起来**。项目结构与概念见 [README.md](README.md)。

## 0. 环境

- Python 3.10+（本项目只用标准库，无第三方依赖）
- 一个正在运行的 **ComfyUI** 服务，已装好你在用的 MiniMax-H3 模型/LoRA/VAE/CLIP 与所需节点
- 系统里能直接调用 **ffmpeg**（`ffmpeg -version` 有输出即可）
- 一个 **OpenAI 兼容的 LLM 端点**（要支持看图/多模态，用于写剧本与评分）

## 1. 拿到仓库

直接克隆或整包拷贝，运行前无需任何安装：

```bash
git clone https://github.com/<你>/ref2va-h3-video-optimizer.git
cd ref2va-h3-video-optimizer
```

## 2. 写一个配置文件

新建一个 `config.json`（可参照 `examples/example_config.json`）。必填项只有 `llm_base` / `llm_model` / `story`：

```json
{
  "story": "一句话或一小段场景描述，作为这一条视频的剧情大纲",
  "optimize_target": "这条视频要重点达成的质量点",
  "flow": "ref2va",
  "refs": [{"path": "C:\\你的路径\\face.png"}, {"path": "C:\\你的路径\\scene.png"}],
  "audios": [],
  "video_ref": null,

  "llm_base": "http://127.0.0.1:8080/v1",
  "llm_model": "你的模型 id",

  "comfy_url": "http://127.0.0.1:8000",
  "model": "minimax_h3_ref2va_pruned_zs05_int8_convrot.safetensors",
  "sampler": "res_multistep",
  "scheduler": "sgm_uniform",
  "steps": 20,
  "seed": 0,
  "megapixels": 0.8,
  "aspect": "16:9 (Widescreen)",
  "duration": 10,

  "quick_workflow": true,
  "fine_render": true,
  "admission_threshold": 5,
  "max_iterations": 12,
  "base_patience": 3
}
```

**先确认你的模型 id：**

```bash
curl http://127.0.0.1:8080/v1/models
```

把 `llm_base` / `llm_model` 填成你自己的端点与模型。`refs` 里的 `path` 是你本地参考图的绝对路径（会同步到 ComfyUI 的 `input` 目录供其读取）。

## 3. 先做一次 dry run（不渲染、不联网）

这会校验配置并打印每个字段的最终取值，确认路径与环境正常：

```bash
python optimizer.py --config config.json --dry-run
```

## 4. 正式跑

```bash
python optimizer.py --config config.json
```

流程：写剧本 → 渲染 → 评分 → 依评分重写/演进，直到达到阈值或迭代上限；可选在最后做一次精渲。运行日志与结果写在 `outdir`（默认 `./outputs/optimizer`）：

- 每次尝试的 `prompt.txt` / `script.json` / `meta.json`
- 最终最优的 `champion_prompt.txt`、`champion_script.txt`
- 历史记录 `optimizer_history.json`

## 5. 两种流程：Ref2VA / I2VA

| 流程 | 配置 | 说明 |
|------|------|------|
| **Ref2VA** | `"flow": "ref2va"`（默认） | 参考图/视频 → 视频。支持多张参考图 + 参考音频、A/B 两种参考方式；成稿为**六段英文** full-reference 提示词（经转译）。 |
| **I2VA** | `"flow": "i2va"` | 首帧图生视频。**只取第 1 张**参考图并**强制作为视频第一帧**；按 MiniMax 官方 I2VA 规则直出**中文**提示词（首帧声明 + `integrated_multimodal_description` / `overall_soundscape` / `non_diegetic_music`），**免转译**；不吃参考音频、无快速渲染模式。缺图会在加载配置时直接报错。 |

> I2VA 使用 `workflows/video_minimax_h3_i2v.api.json`（lightx2v turbo + `MiniMaxH3ImageToVideo`）。时长、种子、分辨率/画幅、**采样器/调度器/步数**、模型/CLIP 与用户 LoRA 均按 config（或页面表单）生效；用户 LoRA 串在内置 turbo LoRA 之前。

### Ref2VA 的两种参考方式

| 模式 | 配置 | 效果 |
|------|------|------|
| **A** | `video_edit: false` | 仅参考图/文字生成，省显存、效果略差 |
| **B** | `video_edit: true` | 视频编辑，显存消耗大、效果最佳 |

> 说明：这是**单条**剪辑的优化器，不是长视频/接续生成工具。**B 方式**在爬山时自动把**上一步生成的视频**作为下一步的候选参考（单条剪辑内部的自我参考），无需也不应手动传参考视频。**A 方式**不传视频。
>
> **显存/效率权衡**：**A 方式**只载入参考图片，显存消耗低；**B 方式**逐帧载入参考视频，显存消耗高但优化效果更好。请根据你的显卡配置与需求选择。

## 6. 可选：音频评审

任务涉及声音时，接一个「听声」LLM（可选，配了才启用）：

```json
{
  "audio_llm_base": "http://127.0.0.1:8081/v1",
  "audio_llm_model": "你的音频模型 id",
  "audio_scoring": "auto"
}
```

不配则自动关闭音频通道，只做画面评审。

## 7. 环境变量（覆盖默认值）

| 变量 | 作用 | 默认 |
|------|------|------|
| `LLM_BASE_URL` | 写/评 LLM 端点 | `http://127.0.0.1:8080/v1` |
| `LLM_API_KEY` | 密钥 | `dummy` |
| `REF2VA_LLM` | 写/评模型 id | 空 |
| `COMFYUI_URL` | ComfyUI 服务 | `http://127.0.0.1:8000` |
| `COMFYUI_INPUT_DIR` | ComfyUI `input` 目录 | `./input` |
| `MODEL_DIR` | 本地模型扫描兜底目录 | `./models/diffusion_models` |
| `REF2VA_MODEL` | CLI 自动路径用模型名 | 占位 |

## 8. 模型文件

`workflows/*.json` 里的 checkpoint / LoRA / CLIP / VAE 文件名是**占位**，需替换成你 ComfyUI `models/` 里真实的文件名；也可在 config 的 `model` 字段直接指定。模型本体不在仓库内（Git 不提交大文件）。

## 9. 常见问题

- **`llm_base` / `llm_model` 缺失**：config 里必须显式填这两个字段。
- **提示参考文件不存在**：`refs` 的 `path` 指向的文件不存在；换成真实绝对路径，或用绝对路径。
- **渲染无输出**：先 `python comfy.py check <workflow>` 看后端校验是否通过；确认 ComfyUI 在 `comfy_url` 上运行、模型文件存在。
- **评分一直很低**：检查 `llm_base` 模型是否可以看图；`optimize_target` 写具体些。
- **报 ffmpeg 相关错误**：确认系统 PATH 里有 ffmpeg。
