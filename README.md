# CatsAPI Agent Skill

[English](README_en.md)

让支持 Agent Skills 的助手通过 [CatsAPI / 猫影工坊](https://catsapi.com) 生成、编辑图片和生成视频。Skill 负责理解意图和交付，Python CLI 负责参数校验、费用预览、任务提交与恢复。

## 支持模型

| 类型 | 模型 key | 名称 |
| --- | --- | --- |
| 图片 | `gptImage2` | GPT Image 2 |
| 图片 | `nanoBanana2` | Nano Banana 2 |
| 图片 | `nanoBananaPro` | Nano Banana Pro |
| 图片 | `flux2Pro` | FLUX.2 Pro |
| 图片 | `grokImagineImage` | GrokImage |
| 图片 | `seedream5Lite` | Seedream 5 Lite |
| 图片 | `seedream5Pro` | Seedream 5 Pro |
| 图片 | `grokImagineImage2` | Grok Imagine Image 2 |
| 视频 | `seedance20` | Seedance 2.0 |
| 视频 | `grokImagineVideo` | GrokImageVideo |
| 视频 | `seedance20Mini` | Seedance 2.0 Mini |
| 视频 | `geminiOmniFlash` | Gemini Omni Flash |

共 8 个图片、4 个视频模型。CLI 也接受显示名，例如 `--model "Seedance 2.0 Mini"`；支持名单不等于线上当前全部可用，使用 `--list` 核对线上状态。

## 安装与配置

仓库根目录就是 Skill 根目录，入口为 [SKILL.md](SKILL.md)。克隆到宿主支持的 Skill 目录并按宿主配置启用，也可以保留独立仓库、在宿主中关联这个目录：

```bash
git clone https://github.com/maodeyu180/CatsAPI-Agent-Skill.git catsapi
```

在 OpenClaw 中也可以要求助手从上述仓库安装 `catsapi`。使用时不需要把它作为主站的 Git submodule。

CLI 要求 Python 3.8+，仅用标准库。通过 CatsAPI 账户创建 API Key，并确保余额足够；不要把完整 Key 发到聊天中。配置环境变量或本地私密配置文件，详见 [密钥指南](references/api-key-setup.md)。

```bash
export CATSAPI_API_KEY=cats-your-key
# 仅自建部署需要覆盖，默认 https://catsapi.com
export CATSAPI_BASE=http://localhost:8000

python3 scripts/catsapi.py --check
```

## 使用逻辑

直接告诉助手需求即可，例如：

- “用 Seedream 5 Pro 把这张产品图换成白色背景，其他不动。”
- “查一下 Gemini Omni Flash 做 6 秒竖屏视频多少钱，先不要生成。”
- “用 Grok Imagine Image 2 出 2 张方图，预算上限以我确认的报价为准。”
- “刚才的任务超时了，继续查原任务，不要重新生成。”

助手区分查询、创作、编辑和恢复；不先强制展示模型菜单，不改写要求原样保留的文字，不默认升级分辨率。生成前校验参数并查看实际报价；预算不明的批量、视频或明显升级会先确认。

脚本每次提交前都会重新预估并检查余额和 `--max-coins`。这是提交前保护，**不是服务端原子锁价**；0 表示不设上限。超时、断线或下载失败时保留任务 ID，用 `--resume` 继续，不能盲目重试生成。

## CLI 示例

以下查询和预检不消耗生成额度；`--cost` 会联网，离线命令不会读取 Key：

```bash
python3 scripts/catsapi.py --list --type image --offline
python3 scripts/catsapi.py --info geminiOmniFlash --type video --offline

python3 scripts/catsapi.py --generate --type image \
  --model seedream5Lite --prompt "窗边的橘猫" \
  --param imageSize=landscape_16_9 --dry-run

python3 scripts/catsapi.py --cost --type video \
  --model seedance20Mini --resolution 720p --duration 6
```

`--dry-run` 校验参数和数量，但不读取图片内容、不检查线上可用性、不写文件。真实生成需移除它，并使用已接受的花费上限：

```bash
# N 替换为用户已确认的猫币上限；此命令会提交付费任务
python3 scripts/catsapi.py --generate --type video \
  --model geminiOmniFlash --prompt "橘猫走过花园" \
  --duration 6 --param aspectRatio=9:16 --max-coins N --no-wait --json

# 用上一条命令返回的 ID 继续等待并下载，不创建新任务
python3 scripts/catsapi.py --resume TASK_ID --json
```

默认下载到运行命令时所在目录的 `catsapi-output/`；用 `-o` 指定文件名，已有文件会加序号而不是覆盖。宿主用原生附件、媒体预览或本地文件链接交付，不依赖特定 `message` 工具。

完整命令、JSON 输出与错误恢复见 [CLI 参考](references/cli-reference.md)。

## 参数与输入边界

- GPT Image 2：20 档尺寸、最多 16 张参考图；Nano Banana 2：最多 14 张。Nano Banana 2 / Pro 默认开启联网搜索，可用 `--param enableWebSearch=false` 关闭。
- Seedream 5 Lite / Pro：用 `imageSize`，最多 4 张参考图；可传数字 `seed`。不支持独立的 `resolution`、`quality` 或 `aspectRatio` 字段。
- Grok Imagine Image 2：用 `aspectRatio`，最多 1 张参考图；与 GrokImage 是不同模型。
- Seedance 2.0 / Mini：默认 reference / 480p / 8 秒。Mini 没有 `mode`，不能传 `fast`。
- 两个 Seedance 的起始图 → 参考图 → 结束图合计最多 4 张，仅作参考，不保证严格首尾帧。主站 schema 写 9 张，但 worker 仍只保留 4 张，CLI 按实际限制拒绝超限请求。
- Gemini Omni Flash：5–10 秒，16:9 / 9:16，可选单张起始图；不提供分辨率或质量档位。
- 图片输入只接受 JPG / PNG / WEBP，单张不超过 10 MB。当前 CLI 不提供视频或音频参考输入。

详见 [图片模型](references/image-models.md)、[视频模型](references/video-models.md) 和 [参数推断](references/parameter-inference.md)。

## 维护与验证

`scripts/model_catalog.py` 集中维护支持名单和别名。参数快照从主站生成，不手工维护另一份价格表：

```bash
python3 scripts/build_capabilities.py \
  --image-models /path/to/backend/app/image_models.json \
  --video-models /path/to/backend/app/abacus_video_models.json \
  -o data/capabilities.json
```

也可用 `--from-api https://catsapi.com -o data/capabilities.json` 读取线上公开 schema。价格始终以执行时 `--cost` 返回为准。

在项目 Python 环境运行 `python -m unittest discover -s tests -v`。测试模拟媒体和网络，覆盖支持名单、请求参数、费用保护、离线预检、恢复和交付；不读取真实 Key、不创建付费任务。不能替代上游模型的实际出图验证。

本次交互设计的参考与取舍见 [设计说明](docs/skill-design.md)。目录按入口 `SKILL.md`、详细说明 `references/`、实现 `scripts/`、快照 `data/` 和离线测试 `tests/` 分层。

## 相关项目与许可

- [CatsAPI 主站](https://catsapi.com)
- [ComfyUI_Catsapi](https://github.com/maodeyu180/ComfyUI_Catsapi) — 同一主站的 ComfyUI 节点
- [Apache License 2.0](LICENSE)
