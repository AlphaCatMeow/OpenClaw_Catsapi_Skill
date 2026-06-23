# 图片生成 / 编辑 模型菜单

## 使用本文件的硬规则

1. 本 skill 的图片模型**只支持** GPT Image 2、Nano Banana 2、Nano Banana Pro、FLUX.2 Pro、GrokImage。
2. 用户已经明确点名支持模型时,直接使用对应模型,不要再展示菜单。
3. 用户没有点名模型时,把下面菜单**原样**展示给用户,让他用数字选。
4. 选定模型后,必须再读 `parameter-inference.md`,从用户描述中推断合法参数;能推断就直接填,不要为了常见画幅/尺寸反复追问。
5. 如果用户要求独立放大、去噪、Qwen 编辑、Kling、Midjourney 等非本页模型,说明当前 CatsApiSkill 已收窄模型范围,并推荐下面最接近的支持模型。

## 通用图片菜单(文生图 / 图生图 / 图片编辑都用这份)

> 想画点什么?当前 CatsApiSkill 支持这 5 个图片模型:
>
> 1. 🧠 **GPT Image 2** — 指令理解最好,适合复杂文字要求、海报、精确构图和超大尺寸
> 2. ⚡ **Nano Banana 2** — 快速、便宜、可多参考图,适合批量试稿和灵感探索
> 3. 🍌 **Nano Banana Pro** — 综合默认推荐,人像、场景、风格化都稳
> 4. 🌈 **FLUX.2 Pro** — 细节和提示词跟随度强,适合复杂视觉风格和质感
> 5. 🤖 **GrokImage** — 想象力强、风格大胆,适合创意/抽象题材
>
> 选几号?(默认 3,或者直接发"1/2/3/4/5")

选中后对应的 `--model` / 常用 `--param`:

| # | 菜单名 | --model | 常用 --param |
|---|---|---|---|
| 1 | GPT Image 2 | `gptImage2` | `size=1024x1024`(默认),可 `1536x1024` / `1024x1536` / `2048x2048` / `3840x2160` 等;`quality=auto`/`low`/`medium`/`high` |
| 2 | Nano Banana 2 | `nanoBanana2` | `resolution=512px`(主工程默认),常用 `1K` / `2K` / `4K`;`aspectRatio=16:9` 等 |
| 3 | Nano Banana Pro | `nanoBananaPro` | `resolution=2K`(推荐) 或 `1K` / `4K`;`aspectRatio=16:9` 等 |
| 4 | FLUX.2 Pro | `flux2Pro` | `aspectRatio=square`(默认) / `landscape_16_9` / `portrait_16_9` / `landscape_4_3` / `portrait_4_3` |
| 5 | GrokImage | `grokImagineImage` | `aspectRatio=1:1`(默认),可 `16:9` / `9:16` / `4:3` / `3:4` / `2:1` 等 |

## 带图输入时

用户传了图片、要求图生图或图片编辑时,仍然只从上面 5 个模型里选:

| 用户意图 | 优先模型 | 说明 |
|---|---|---|
| 精确改图、海报文字、复杂约束 | GPT Image 2 | 支持最多 4 张参考图 |
| 多图参考、快速试稿 | Nano Banana 2 | 支持最多 4 张参考图 |
| 人物/主体一致性、综合质量 | Nano Banana Pro | 默认推荐,支持最多 4 张参考图 |
| 风格化、质感、复杂视觉 | FLUX.2 Pro | 支持最多 3 张参考图 |
| 创意变体、夸张想象 | GrokImage | 可带图,但更偏创意重绘 |

## 调用示例

```bash
# 用户选了 3 号 Nano Banana Pro,提示词"星空下的黑猫",AI 推断为横屏 2K
python3 {baseDir}/scripts/catsapi.py --generate --type image \
  --model nanoBananaPro --prompt "星空下的黑猫, 电影感" \
  --param resolution=2K --param aspectRatio=16:9 --num 1 \
  -o /tmp/openclaw/catsapi-output/cat_$(date +%s).png
```

成功后脚本会输出:

```
COST:14
OUTPUT_FILE:/tmp/openclaw/catsapi-output/cat_1714xxxxxx.png
```

走 `message` 工具把那个文件发给用户,然后自然地跟一句:"完成啦~花了 14 猫币,要不要再出一张或者做成视频?"
