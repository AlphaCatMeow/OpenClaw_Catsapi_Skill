# 参数推断与提示词约束

由宿主 Agent 理解自然语言，CLI 不调用额外 LLM。先用 `--info MODEL --type image|video --offline` 查看模型字段；推断后用 `--dry-run` 检查。

## 保留用户意图

- 完整提示词要求原样使用时原样传入。创意简述可整理成可执行描述，但不擅自改变主体、精确文字、身份、产品细节、画幅、数量或预算。
- 编辑请求区分“要改什么”和“必须保持什么”；使用指定参考图，不自动搜图替代用户素材。
- 默认 `rewritePrompt=false`。用户确实要润色/改写时才启用；它可能影响费用。
- 参数冲突、硬性要求不支持、模型不在名单、素材缺失，或预算不足以满足要求时问一个具体问题。不静默降级，不把 16:9 改成“差不多”的 3:2。
- 没有要求时采用 schema 默认值；不要自动加分辨率、质量、张数或时长。

## 画幅映射

| 目标 | GPT Image 2 size 示例 | Seedream imageSize / FLUX aspectRatio | Nano Banana / Grok aspectRatio |
| --- | --- | --- | --- |
| 方图 1:1 | 1024x1024 | square | 1:1 |
| 横屏 16:9 | 2048x1152 | landscape_16_9 | 16:9 |
| 竖屏 9:16 | 1152x2048 | portrait_16_9 | 9:16 |
| 横版 4:3 | 2048x1536 | landscape_4_3 | 4:3 |
| 竖版 3:4 | 1536x2048 | portrait_4_3 | 3:4 |

GPT 的 1536x1024 是 3:2，不是 16:9；3840x1280 是 3:1，不是 21:9。精确 21:9 可查 2688x1152。不要把此表误用成强制提高尺寸；如精确画幅需要更高尺寸，预估差价并尊重预算。

## 字段差异

- GPT Image 2：`size` + `quality`，保留 `quality=auto`。
- Nano Banana 2 / Pro：`resolution` + `aspectRatio`，默认 1K；联网开关是布尔值 `enableWebSearch`。
- Seedream 5 Lite / Pro：`imageSize`，可选数值 `seed`；没有 resolution/quality 档位。
- FLUX.2 Pro：`aspectRatio` 用 square / portrait_* / landscape_*，只输出 1 张。
- Grok Imagine Image / Image 2：`aspectRatio` 用 16:9 等字符串，只接收 1 张参考图。
- Seedance 2.0：reference / fast；Mini：reference 且没有 mode。两者时长 4–15 秒。
- Gemini Omni Flash：时长 5–10 秒、16:9 / 9:16；没有 resolution/mode。
- `--num` 控制图片输出数量；视频必须 1。不支持的数量不要自动拆单。

所有枚举、布尔值、有限数值、模型默认值和素材数量都由脚本校验；未知参数与通过 `--param` 传文件字段会被拒绝。离线预检不检查媒体内容、线上启用状态或实时价格。
