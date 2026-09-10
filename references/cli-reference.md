# CLI 工作流参考

命令统一从调用者当前工作目录执行：`python3 {baseDir}/scripts/catsapi.py`。不要为运行脚本切换到安装目录。

## 发现与预检

```bash
python3 {baseDir}/scripts/catsapi.py --list --type image --offline
python3 {baseDir}/scripts/catsapi.py --info seedream5Pro --type image --offline
python3 {baseDir}/scripts/catsapi.py --info geminiOmniFlash --type video --offline
python3 {baseDir}/scripts/catsapi.py --generate --type image \
  --model seedream5Lite --prompt "一只窗边的橘猫" \
  --param imageSize=portrait_16_9 --param seed=42 --dry-run
```

`--offline` 只用于 list/info；检查生成请求用 `--dry-run`。后者显示有效参数、素材文件名、数量以及会用于费用预览的参数；不读取 Key、不联网、不编码图片、不写文件，也不检查媒体内容。离线目录不保证模型当前在线可用；需要在线确认时去掉 `--offline`。

模型 key 或完整展示名都可用，如 `--model "Seedance 2.0 Mini"`。模糊版本名不应自行补成更昂贵型号。

## 费用预览与实际生成共用参数

```bash
# 仅查询费用，不生成，不必提供 prompt
python3 {baseDir}/scripts/catsapi.py --cost --type video \
  --model seedance20Mini --param resolution=480p --param duration=5

# GPT 按尺寸 + quality 预览，不能漏掉 quality
python3 {baseDir}/scripts/catsapi.py --cost --type image \
  --model gptImage2 --param size=2048x1152 --param quality=high --num 2

# 2.5 精细变体：variant 同时用于预览和提交，透明背景属于生成参数
python3 {baseDir}/scripts/catsapi.py --cost --type image \
  --model gptImage25 --param variant=sunburst --mode auto \
  --param background=transparent --resolution 1024x1024 --num 2
```

`--resolution` 映射到当前模型支持的 resolution / size / imageSize；`--mode` 映射到 mode / quality；`--duration` 对应 duration。与 `--param` 冲突会报错；模型不支持对应字段时也会拒绝。默认值在预览和提交前用同一套逻辑解析。

参考图可按生成命令传入；`--cost --has-image-input` 可在没有本地素材时按有参考图报价。它不能用于生成，生成必须提供实际文件。

实际生成使用 `--generate`，保持报价时的模型、参数和数量，增加用户提示词与已接受的 `--max-coins` 整数上限。脚本每次提交前再次预估；报价无效、余额不足或超过上限都会停止。`--max-coins 0` 表示不设金额上限，不表示免费。此检查不是服务端原子锁价，价格可能在两个请求之间变化。

不要仅因为用户询价而执行 generate。若用户没有同意新预算，不为通过费用检查自动减少数量、时长或改模型。

## 长任务与恢复

在已授权的生成命令后加 `--no-wait --json`。成功会返回一行 `event=submitted` JSON，包含 `task_id`；这只是已提交，不是已生成。

```bash
python3 {baseDir}/scripts/catsapi.py --status TASK_ID
python3 {baseDir}/scripts/catsapi.py --resume TASK_ID --wait-timeout 60 --json
python3 {baseDir}/scripts/catsapi.py --resume TASK_ID -o ./catsapi-output/recovered.mp4
```

resume 查询旧任务、有限等待并下载结果，不调用费用预览或创建任务。无需重传模型、提示词或素材。等待超时退出码为 6，不会自动取消服务器任务；稍后继续 resume。若 POST 提交断线且没有收到任务 ID，先查网页记录，不能盲目重发。

## 输入、语言与输出

- 图片：重复 `--image PATH`。Seedance 家族：`--start-frame`、重复 `--reference-image`、`--end-frame`。Grok/Gemini 视频仅 `--start-frame`。
- 输入只接受 JPG/PNG/WEBP，每张不超过 10 MB；内容是否有效仍由服务端验证。文件字段不能写到 `--param`。
- `--locale zh|en` 指定服务端用户可见结果语言，默认 zh；不会翻译用户 prompt。
- 默认写入当前工作目录 `catsapi-output/`，可用 `-o` 指定文件；输出是绝对路径，已有文件自动换后缀。
- generate/resume 的 `--json` 是 NDJSON 事件流，不是跨多行拼接成的单个 JSON；其他查询/dry-run 是普通 JSON。
- 未用 `--json` 时保留 `TASK_ID:`、`COST:`、`OUTPUT_FILE:` 行。任务 ID 在等待前立即输出。
- 程序 stderr 为进度/错误，不复制完整日志给最终用户。检查退出码和 completed 事件后再宣告成功。

## 离线回归

在项目 Python 环境运行 `python -m unittest discover -s tests -v`。测试使用 mock，不读取真实 Key、不访问网络、不消耗猫币。
