# 参数推断规则

## 核心原则

1. 这里的"AI 推断"由宿主 Agent 完成,不是 `scripts/catsapi.py` 内置 LLM。Agent 读完本文件后,把用户自然语言转成合法 `--param key=value`。
2. 只使用所选模型支持的参数。拿不准时用 `python3 {baseDir}/scripts/catsapi.py --info MODEL --type image/video` 查。
3. 用户没有明确说参数时,用默认推荐值;不要为常见画幅、分辨率、时长反复追问。
4. 用户要求的值不被模型支持时,选择最接近的合法值并说明一句。只有会明显偏离意图时才追问。
5. 不要生成 `prompt=` 参数,提示词始终走脚本的 `--prompt`。

## 从描述推断画幅

| 用户描述 | 标准画幅 | GPT Image 2 size | FLUX.2 Pro aspectRatio |
|---|---|---|---|
| 横屏、电影感、YouTube、B 站封面、电脑壁纸、16:9 | `16:9` | `1536x1024` / 高清 `2048x1152` / 4K `3840x2160` | `landscape_16_9` |
| 竖屏、手机壁纸、短视频、抖音、Reels、小红书、9:16 | `9:16` | `1024x1536` / 高清 `1152x2048` / 4K `2160x3840` | `portrait_16_9` |
| 方图、头像、Logo、图标、表情包、1:1 | `1:1` | `1024x1024` / 高清 `2048x2048` | `square` |
| 海报、人物半身、竖版构图、3:4 | `3:4` | `1024x1536` | `portrait_4_3` |
| 产品图、横版展示、4:3 | `4:3` | `1536x1024` | `landscape_4_3` |
| 超宽、电影横幅、21:9 | `21:9` | `3840x1280` | `landscape_16_9` |

如果用户同时说"横屏"和"9:16"这类冲突信息,先追问确认。

## 图片模型参数

### GPT Image 2 (`gptImage2`)

- 使用 `size`,不要传 `resolution` 或 `aspectRatio`。
- 默认: `size=1024x1024`, `quality=auto`, `rewritePrompt=false`。
- 用户说"高清/精细/正式稿/商业海报": `quality=high`。
- 用户说"草稿/省钱/快速试试": `quality=low` 或 `quality=medium`。
- 用户说"4K/超清/壁纸":按画幅选 `3840x2160` / `2160x3840` / `2048x2048`。
- 用户要求多图时用 `--num N`,最多 4。

### Nano Banana 2 (`nanoBanana2`)

- 使用 `resolution` + `aspectRatio`。
- 主工程默认: `resolution=512px`, `aspectRatio=1:1`, `rewritePrompt=false`。
- 没有特别要求省钱/草稿时,建议用 `resolution=1K` 起步。
- 用户说"高清/正式稿": `resolution=2K`。
- 用户说"4K/超清/壁纸/海报": `resolution=4K`。
- 用户说"草图/便宜/快速试试": `resolution=512px` 或 `1K`。
- 用户要求多图时用 `--num N`,最多 4。

### Nano Banana Pro (`nanoBananaPro`)

- 使用 `resolution` + `aspectRatio`。
- 主工程默认: `resolution=1K`, `aspectRatio=1:1`, `rewritePrompt=false`。
- 没有特别要求省钱/草稿时,建议用 `resolution=2K`。
- 用户说"省钱/快速试试": `resolution=1K`。
- 用户说"4K/超清/最终稿/壁纸": `resolution=4K`。
- 用户要求多图时用 `--num N`,最多 4。

### FLUX.2 Pro (`flux2Pro`)

- 只推断 `aspectRatio`,不要传 `resolution`。
- 默认: `aspectRatio=square`, `rewritePrompt=false`。
- 横屏用 `landscape_16_9`,竖屏用 `portrait_16_9`,4:3 用 `landscape_4_3`,3:4 用 `portrait_4_3`。
- 该模型没有 `numImages` 参数时,不要强行多图;默认 `--num 1`。

### GrokImage (`grokImagineImage`)

- 只推断 `aspectRatio`,不要传 `resolution`。
- 默认: `aspectRatio=1:1`, `rewritePrompt=false`。
- 横屏用 `16:9`,竖屏用 `9:16`,方图用 `1:1`,超宽可用 `2:1` 或 `20:9`。
- 用户要求多图时用 `--num N`,最多 4。

## 视频模型参数

### Seedance 2.0 (`seedance20`)

- 默认: `inputMode=standard`, `resolution=720p`, `duration=5`, `aspectRatio=16:9`, `mode=fast`, `generateAudio=true`, `cameraFixed=false`, `rewritePrompt=false`。
- 支持分辨率只有 `480p` / `720p`;用户说 1080p 或 4K 时,说明当前模型最高 720p,并用 `720p`。
- 主工程当前 `mode` 只有 `fast`,不要生成 `mode=standard`。
- 用户说"高质量/稳定/真人/细节/正式稿":仍用 `mode=fast`,可提高提示词细节,不要伪造不存在的质量档位。
- 用户说"快速/省钱/先试试": `mode=fast`。
- 时长按用户明确秒数取 `4` 到 `15` 的合法整数;没说时用 `5`。如果用户说超过 15 秒,说明最长 15 秒并用 `duration=15`。
- 支持 `--start-frame`、`--end-frame` 和最多 4 个 `--reference-image`。带图片素材时主工程 worker 会归一成 `referenceImages`,并强制 `inputMode=reference`。
- 主工程模型 schema 中有 `referenceVideos` / `referenceAudio`,但当前任务接口图片校验链路只接受 JPG/PNG/WEBP,CLI 不要承诺视频/音频参考素材。

### GrokImageVideo (`grokImagineVideo`)

- 默认: `resolution=480p`, `duration=5`, `aspectRatio=1:1`。
- 用户说"高清/720p": `resolution=720p`。不支持 1080p/4K,遇到时说明最高 720p 并用 `720p`。
- 时长按用户明确秒数取 `5` 到 `15` 的合法整数;没说时用 `5`。如果用户说超过 15 秒,说明最长 15 秒并用 `duration=15`。
- 支持 `--start-frame`,不支持 `--end-frame`;用户给首尾帧时改用 Seedance 2.0 或追问。

## 何时必须追问

- 用户没点名模型,且不能接受默认菜单推荐。
- 用户的画幅描述互相矛盾。
- 用户要求一个本 skill 不支持的模型,并且没有明显替代模型。
- 用户要求首尾帧视频但指定了 GrokImageVideo。
- 用户要求严格的不可降级参数,比如"必须 1080p 视频",但两个支持视频模型都不支持。
