# 视频生成模型菜单

## 使用本文件的硬规则

1. 本 skill 的视频模型**只支持** Seedance 2.0 和 GrokImageVideo。
2. 用户已经明确点名支持模型时,直接使用对应模型,不要再展示菜单。
3. 用户没有点名模型但明确要求"生成视频/做成视频/图生视频"时,按"自动选择规则"直接选模型,不要先展示菜单。
4. 只有用户要求"让我选/有哪些视频模型/换个模型/不知道用哪个"或意图确实不明确时,才把下面菜单**原样**展示给用户,让他用数字选。
5. 生视频之前,先 `message` 发"开始生成啦,视频一般要 1-5 分钟,请稍等～🎬",再 `exec` 脚本。
6. `--num` 对视频**必须**为 1。
7. 选定模型后,必须再读 `parameter-inference.md`,从用户描述中推断合法的 `resolution`、`duration`、`aspectRatio`、`mode` 等参数。

## 自动选择规则

用户没指定模型时,优先按下面规则静默选择,不要把完整决策过程发给用户:

| 用户描述 | 默认选择 |
|---|---|
| 人物、真人、稳定动作、细节、首尾帧、多参考图 | Seedance 2.0 |
| 便宜、创意短片、夸张想象、xAI/Grok 风格 | GrokImageVideo |

## 通用菜单(文生视频 / 带起始帧的图生视频都用这份)

> 视频来啦~ 当前 CatsApiSkill 支持这 2 个视频模型:
>
> 1. 🌱 **Seedance 2.0** — 默认推荐,画面稳定、人物和细节更可靠,最长 15 秒
> 2. 🤖 **GrokImageVideo** — xAI 风格,便宜、想象力强,适合创意短片
>
> 选几号?(默认 1,或者发"1/2")

选中后对应的 `--model` / 常用 `--param` / 限制:

| # | 菜单名 | --model | 常用 --param | 备注 |
|---|---|---|---|---|
| 1 | Seedance 2.0 | `seedance20` | `resolution=720p`(默认) / `480p`;`duration=4`-`15`;`aspectRatio=16:9` / `9:16` / `1:1`;`mode=fast` | 支持起始帧、结束帧、最多 4 张参考图;主工程当前只开放 fast 模式,不支持 1080p |
| 2 | GrokImageVideo | `grokImagineVideo` | `resolution=480p`(默认) / `720p`;`duration=5`-`15`;`aspectRatio=1:1` / `16:9` / `9:16` 等 | 支持起始帧,不支持结束帧 |

## 图生视频提示

如果用户传了图片想做成视频:

- **纯起始帧** → Seedance 2.0 或 GrokImageVideo 都可以,加 `--start-frame /path/to/frame.png`
- **首尾帧** → 只用 Seedance 2.0,加 `--start-frame` 和 `--end-frame`
- **多张参考图** → Seedance 2.0,重复传 `--reference-image /path/to/ref.png`,最多 4 张
- **真人 / 人物动作 / 稳定性优先** → 首选 Seedance 2.0
- **创意短片 / 想象力优先 / 成本敏感** → 可选 GrokImageVideo

主工程模型 schema 里还有 `referenceVideos` / `referenceAudio`,但当前 `/api/tasks` 文件输入链路仍按图片素材校验,只接受 JPG/PNG/WEBP。不要在 CLI 中承诺视频/音频参考素材,除非主工程后端也接通了对应文件类型。

## 调用示例

```bash
# 步骤 1: 告诉用户要等
# (通过 message 工具发: "开始生成啦,视频一般 1-5 分钟,稍等～🎬")

# 步骤 2: 先预览成本(可选,长视频建议)
python3 {baseDir}/scripts/catsapi.py --cost \
  --type video --model seedance20 \
  --resolution 720p --duration 5 --num 1

# 步骤 3: 执行
python3 {baseDir}/scripts/catsapi.py --generate --type video \
  --model seedance20 --prompt "a ginger cat walking through a sunflower field, cinematic" \
  --param resolution=720p --param duration=5 --param aspectRatio=16:9 \
  -o /tmp/openclaw/catsapi-output/cat_$(date +%s).mp4
```

脚本完成后输出:

```
COST:6
OUTPUT_FILE:/tmp/openclaw/catsapi-output/cat_xxxxxxxx.mp4
```

走 `message` 工具交付视频文件,然后:"视频出炉啦~ 花了 6 猫币,要不要换个镜头运动再来一版?"

## 慢任务兜底

如果 `--generate` 因为超时(默认 15 分钟)而报错退出,会打印出 TASK_ID。用 `--status TASK_ID` 继续查:

```bash
python3 {baseDir}/scripts/catsapi.py --status TASK_ID
```

返回的 JSON 里 `status=="completed"` 就拿 `result_video.url` 手动 `curl -o` 下载。
