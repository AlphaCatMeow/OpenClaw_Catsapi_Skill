# 视频模型选择

当前支持 4 个视频模型，每次请求只生成 1 个视频。

| 模型 | model key | 默认值与范围 | 图片输入 |
| --- | --- | --- | --- |
| Seedance 2.0 | `seedance20` | reference / fast；480p；8 秒，范围 4–15 秒；默认 16:9 | 合计最多 4 张参考素材 |
| Grok Imagine Video | `grokImagineVideo` | 720p；8 秒，范围 5–15 秒；默认 1:1 | 1 张起始帧 |
| Seedance 2.0 Mini | `seedance20Mini` | reference；480p；8 秒，范围 4–15 秒；默认 16:9；无 mode | 合计最多 4 张参考素材 |
| Gemini Omni Flash | `geminiOmniFlash` | 5 秒，范围 5–10 秒；16:9 / 9:16；无分辨率选项 | 1 张起始帧 |

Seedance 两个版本与 Grok 视频只开放 480p / 720p。Gemini Omni Flash 没有可选分辨率，不能把“没有分辨率选项”解释成支持任意分辨率。

## 路由

- 用户点名模型/版本就使用它。Gemini Omni Flash 是这里的视频模型，不要误认为对话或图片模型。
- 多参考图约束先选择 Seedance 家族。已有明确版本偏好时不再询问；需要在普通版/Mini 间按预算选择时用实时费用预览比较。
- 单图起始帧或简单短片可考虑 Grok / Gemini Omni；未指定模型时可以沿用既有视频模型，但不能用默认替换用户点名的版本。
- 不对质量、速度或真人效果作未经验证的排名承诺。实际时长、参考数量和可接受预算比营销名更重要。

## Seedance 的实际执行限制

`--start-frame`、重复的 `--reference-image`、`--end-frame` 按此顺序合并为 `referenceImages`，合计最多 4 张。两个版本都固定为 `inputMode=reference`；这些输入不保证严格首尾帧控制。用户要求严格控制时应先说明限制。

主站 schema 声明 9 张图片，但 worker 目前仅保留 4 张，客户端按实际 4 张上限提前拒绝，避免丢素材。Mini 没有 `mode`，不要继承普通版的 `mode=fast`。主站已接通部分视频参考，但当前 Skill/ComfyUI 尚未提供视频/音频参考输入。

## 执行与恢复

先预估与确认视频预算，建议用 `--no-wait --json` 提交；记录 `submitted` 事件中的任务 ID，然后 `--resume TASK_ID --json`。若一次等待超时，只恢复原任务，不再次生成。具体命令见 [cli-reference.md](cli-reference.md)。
