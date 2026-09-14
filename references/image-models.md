# 图片模型选择

这是客户端支持表，不是质量排名或实时价格表。用户点名时优先使用指定模型；当前共 10 个图片模型。

| 模型 | model key | 主要尺寸参数 | 最多参考图 | 输出数量 |
| --- | --- | --- | ---: | --- |
| GPT Image 2.5 | `gptImage25` | `size`、`quality`、`variant`、`background` | 16 | 1–4 |
| GPT Image 2 | `gptImage2` | `size`、`quality` | 16 | 1–4 |
| Nano Banana 2 | `nanoBanana2` | `resolution`、`aspectRatio` | 14 | 1–4 |
| Nano Banana Pro | `nanoBananaPro` | `resolution`、`aspectRatio` | 4 | 1–4 |
| FLUX.2 Pro | `flux2Pro` | `aspectRatio` 枚举 | 3 | 1 |
| Grok Imagine Image | `grokImagineImage` | `aspectRatio` 比例字符串 | 1 | 1–4 |
| Seedream 5 Lite | `seedream5Lite` | `imageSize` 枚举，可选数值 `seed` | 4 | 1–4 |
| Seedream 5 Pro | `seedream5Pro` | `imageSize` 枚举，可选数值 `seed` | 4 | 1–4 |
| Grok Imagine Image 2 | `grokImagineImage2` | `aspectRatio` 比例字符串 | 1 | 1–4 |
| Midjourney | `midjourney` | `aspectRatio`、`version`、`processMode`，可选 `negativePrompt` | 0 | 固定 4 张 / 次，`--num 1` |

参考图用重复的 `--image PATH`，不能把输出数量 `--num` 当作参考图数量。数量超限会报错，不会自动拆成多次付费任务。

## 用户未指定模型时

- 一般创作/编辑可沿用 Nano Banana Pro；没有特别需求时用 schema 的 1K 默认值，不自动提高到 2K/4K。
- 明确文字排版、复杂约束或精确像素尺寸时，可优先考虑 GPT Image 2；是否升高 quality 由需求和费用预览决定。
- 用户想尝试 Seedream 时，按其 Lite/Pro 选择；未分版本且在意费用时先比较实时报价，不宣称 Pro 一定更好。
- 用户明确要 Grok Image 2 时使用 `grokImagineImage2`，不误用旧版；宽泛的“Grok”不足以确定版本且差价会影响选择时再问。
- 参考图数量先约束模型选择。不要为迁就默认模型丢弃用户素材。
- 用户要列举/比较时才展示相关选项；无需每次展示完整菜单。

## Midjourney

- 默认 `version=v7`、`aspectRatio=1:1`、`processMode=fast`。版本为 `v7 / v6 / niji 6`；比例为 `1:1 / 16:9 / 9:16 / 4:3 / 3:4 / 1:2 / 2:1`；模式为 `fast / turbo / relax`。`--mode` 也可指定处理模式，报价与提交使用相同值。
- 每次固定返回 4 张、按次计费，`--num` 只能为 1；不要改成 4 或自动拆单，实际价格以 `--cost` 为准。仅支持文生图，不接收参考图，也没有 `resolution`、`quality` 或 `rewritePrompt` 参数。
- 负面提示词用 `--param "negativePrompt=blur, text"`。提示词最多 2500 字符；支持的行内标记有 `--sref <code>`、`--sw`、`--seed`、`--stylize`、`--chaos`、`--weird`、`--tile`、`--style raw`、`--no`。这些标记保留在 prompt 中，不作为独立的 `--param` 字段。
- 按主站 schema，URL 和其他行内 `--` 标记不属于开放输入；比例、版本、速度/质量模式使用表单参数。遇到用户要求原样保留但含不支持标记的提示词，说明限制并确认如何处理，不擅自删改。

## 参数提醒

- GPT Image 2.5 默认 Flare（快速）、`quality=auto`、`size=1024x1024`、`background=auto`；质量选项顺序为 `low / auto / medium / high / xhigh / max`，共 20 档尺寸，提示词最多 10000 字符。带参考图也支持 1–4 张输出。
- 2.5 的 Sunburst（精细）用 `--param variant=sunburst`，CatsAPI 同质量、同尺寸按 Flare 单张价的 1.25 倍四舍五入收费；这是站内定价，最终使用服务端费用预览。客户端保留 `quality=auto`，不自行换档或计算倍率。
- 2.5 背景选项为 `auto / transparent / opaque`；透明 PNG 用 `--param background=transparent`。这些变体、背景和新增质量档位只用于 2.5，不传给 GPT Image 2。
- Seedream 的横屏是 `imageSize=landscape_16_9`，竖屏是 `portrait_16_9`；不传 `resolution` 或 `aspectRatio`。
- Grok Image 2 不开放 `resolution`、`quality` 或 `imageSize`。
- Nano Banana 2 / Pro 的 `enableWebSearch` 默认 true，可用 `--param enableWebSearch=false` 关闭；这不改变用户原始提示词。
- 精确默认值、全部选项和提示词限制用 `--info MODEL --type image --offline` 查。未单独配置提示词上限的模型按主站 2500 字符限制；不得直接截断用户提示词。
- 用户要求放大时，区分重新生成大图与无损放大原图；本客户端没有独立超分辨率端点，不应承诺等价效果。
