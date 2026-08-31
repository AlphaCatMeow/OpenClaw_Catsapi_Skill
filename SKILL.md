---
name: catsapi
description: "Create or edit images and generate videos through CatsAPI. Use for CatsAPI creative requests, model/parameter discovery, cost or balance checks, and recovering existing generation tasks. Respect an explicitly chosen different provider; do not route unrelated image analysis or repository maintenance into generation."
metadata: {"openclaw":{"emoji":"🐱","homepage":"https://catsapi.com","requires":{"bins":["python3"]},"primaryEnv":"CATSAPI_API_KEY"}}
---

# CatsAPI 创作助手

入口：`python3 {baseDir}/scripts/catsapi.py`。只依赖 Python 标准库。
支持 8 个图片模型、4 个视频模型；完整参数在 `data/capabilities.json`。CLI 负责校验与调用，宿主 Agent 负责理解需求与选择模型，不额外调用 LLM。

使用用户当前语言，简洁说明结果。可以友好，但不强制喵系口吻、中文、固定话术或交付后的追问。

英文会话请求传 `--locale en`，中文传 `--locale zh`；不要因界面语言变化而擅自翻译用户的提示词或图片文字。

## 先分清用户要什么

- 只问模型、参数、费用、余额或状态：只查询，不创建生成任务。
- 要生成：明确图片/视频、数量、输入素材、必须保留的文字/主体、画幅及预算；已给出的信息不要再问。
- 要编辑：先用宿主可用能力查看用户指定的图片，保留未要求更改的主体、构图、文字和风格。没有素材时不要假装已经看到。
- 要续做：找已有任务 ID 或已交付文件。超时、断线、下载失败都不意味着需要重新生成。
- 用户点名模型时按支持名单使用；未点名时按对应模型指南选一个默认，不先弹完整菜单。只有用户要比较/选择，或缺失信息会改变结果时才询问。

## 按需读取

| 需要解决的问题 | 读取 |
| --- | --- |
| 选图片模型、图片参考限制 | [image-models.md](references/image-models.md) |
| 选视频模型、起始帧/参考图差异 | [video-models.md](references/video-models.md) |
| 从自然语言推断画幅、参数和编辑约束 | [parameter-inference.md](references/parameter-inference.md) |
| 命令细节、离线预检、费用、异步/恢复、JSON | [cli-reference.md](references/cli-reference.md) |
| 第一次配 Key 或鉴权失败 | [api-key-setup.md](references/api-key-setup.md) |
| 媒体交付、超时/下载失败、错误处理 | [output-delivery.md](references/output-delivery.md) |

不需要为每次简单查询读取所有文件。明确模型后用 `--info MODEL --type image|video --offline` 获取该模型的精简 schema；只有需要核对线上可用性或最新参数时才去掉 `--offline`。

## 创作流程

1. **拟定请求。** 尊重指定模型、原始提示词、准确文字、输入图片和数量。不擅自加图、切换模型、提高分辨率或重写用户要求原样使用的提示词。默认 `rewritePrompt=false`。
2. **预检。** 新组合或复杂参数先用 `--generate ... --dry-run`。它只检查参数/数量，不读取 Key、不联网、不编码图片、不写文件；不代表媒体内容或线上可用性已验证。枚举和类型由脚本校验，不猜字段。
3. **核对花费。** 用相同模型/参数/数量执行 `--cost`，读取实际返回值，不引用文档旧价格。告诉用户总价。已有明确生成授权且在已知预算内时可继续；批量、视频、明显升级成本而预算不明时先确认花费上限。不能把“看看多少钱”当成生成授权。
4. **只提交一次。** `--generate ... --max-coins N` 会再次预估并阻止超限/余额不足的请求；N 用用户允许的上限，没有更宽预算时用本次已接受报价。此保护是提交前检查，不是服务端原子锁价。
5. **等待或恢复。** 短任务可直接等待。长任务用 `--no-wait --json` 拿到任务 ID，再用 `--resume TASK_ID --json` 等待和下载。保存任务 ID；恢复命令不会创建新任务。遇到未知提交结果，不自动重试 POST，先查网页任务记录。
6. **检查并交付。** 检查文件存在、数量和可查看的视觉结果；明确说明不能保证的部分。报告实际成本，交付所有文件。不要为弥补输出质量或数量不足自动发起额外付费任务。

## 常用入口

```bash
# 只查本地支持的模型，不需要 Key
python3 {baseDir}/scripts/catsapi.py --list --type image --offline

# 只预检，不付费；Seedream 用 imageSize，不是 aspectRatio
python3 {baseDir}/scripts/catsapi.py --generate --type image \
  --model seedream5Lite --prompt "窗边的一只橘猫" \
  --param imageSize=landscape_16_9 --dry-run

# 查已有任务 / 恢复等待与下载；都不会重新生成
python3 {baseDir}/scripts/catsapi.py --status TASK_ID
python3 {baseDir}/scripts/catsapi.py --resume TASK_ID --json
```

## 不可忽略的边界

- 两个 Seedance 都只用 `inputMode=reference`；Mini **没有** `mode`。起始图 → 参考图 → 结束图合计最多 4 张，是参考素材，不保证严格首尾帧。schema 的 9 张尚未在主站 worker 全部生效。
- Gemini Omni Flash 只有 `duration=5..10` 和 `aspectRatio=16:9|9:16`，不要承诺或传入分辨率/质量档位。
- 当前客户端只接收 JPG/PNG/WEBP 图片输入。虽然上游 schema 里有视频/音频字段，本客户端没有开放这些输入；不能通过 `--param` 绕过。
- 密钥只由脚本读取环境变量/本地配置；不询问完整 Key、不把它写进聊天或命令行、不输出配置文件内容。设置问题按需读 Key 指南，不重复盘问已配置用户。
- 默认输出到当前工作目录 `catsapi-output/`；用户指定 `-o` 时服从指定路径，已有文件不覆盖。不要为了运行脚本切到 skill 目录。
- 交付适配宿主：有原生附件工具就用附件；支持本地媒体预览/文件链接就提供对应链接；否则给绝对路径并说明。不要假设一定有 `message`，不要固定回复 `NO_REPLY`，不要向用户暴露内部结果 URL。
