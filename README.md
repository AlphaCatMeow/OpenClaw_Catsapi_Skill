# CatsAPI Skill — OpenClaw Skill for 猫影工坊

[English](./README_en.md)

一款面向 [OpenClaw](https://openclaw.ai) / Cursor / Claude Code / Codex CLI 等支持 **Agent Skills** 标准的客户端的技能包,让 AI 助手直接调用 [猫影工坊 (catsapi.com)](https://catsapi.com) 的生图、生视频能力。

当前版本采用精简模型范围:

| 类别 | 数量 | 代表模型 |
|---|---:|---|
| 图片生成 | 5 | GPT Image 2、Nano Banana 2、Nano Banana Pro、FLUX.2 Pro、GrokImage |
| 视频生成 | 2 | Seedance 2.0、GrokImageVideo |

## 快速开始

### 方式 1:OpenClaw 直接安装(推荐给 OpenClaw 用户)

在 OpenClaw 对话里发:

> 从 <https://github.com/maodeyu180/OpenClaw_Catsapi_Skill> 安装 catsapi 技能

助手会自动克隆仓库、放到正确目录、引导你配置 API Key。

### 方式 2:Cursor / Claude Code / Codex CLI

```bash
# 用户级全局安装(所有项目都能用)
git clone https://github.com/maodeyu180/OpenClaw_Catsapi_Skill.git ~/.cursor/skills/catsapi

# Claude Code / Codex CLI
git clone https://github.com/maodeyu180/OpenClaw_Catsapi_Skill.git ~/.claude/skills/catsapi
git clone https://github.com/maodeyu180/OpenClaw_Catsapi_Skill.git ~/.codex/skills/catsapi
```

Cursor 下次启动会在 Settings → Rules → Agent Decides 里自动发现 `catsapi`。

### 方式 3:作为 git submodule 接入项目

```bash
cd your-project/
git submodule add https://github.com/maodeyu180/OpenClaw_Catsapi_Skill.git .cursor/skills/catsapi
git commit -m "Add catsapi skill"
```

## 前置条件

- **Python 3.8+**(脚本只用标准库,无需额外依赖)
- **API Key** — 在 [catsapi.com](https://catsapi.com) 登录后 → API Key 页面创建,形如 `cats-xxxxxxxx`
- **猫币余额** — 通过兑换码或新用户赠送获取

## 配置

```bash
export CATSAPI_API_KEY=cats-你的Key
# 自建部署可覆盖 API 基址(默认 https://catsapi.com)
export CATSAPI_BASE=http://localhost:8000
```

自检:

```bash
python3 scripts/catsapi.py --check
```

## 使用示例(直接命令行)

```bash
# 文生图
python3 scripts/catsapi.py --generate --type image \
  --model nanoBananaPro --prompt "一只戴墨镜的橘猫在海边" \
  --param resolution=2K --param aspectRatio=16:9 -o /tmp/cat.png

# 文生视频
python3 scripts/catsapi.py --generate --type video \
  --model seedance20 --prompt "a cat walking through a garden" \
  --param resolution=720p --param duration=5 --param aspectRatio=16:9 \
  -o /tmp/cat.mp4

# 费用预览
python3 scripts/catsapi.py --cost --type video --model seedance20 \
  --resolution 720p --duration 10

# 模型列表
python3 scripts/catsapi.py --list --type image
```

## 使用方式(挂到 Agent 后)

安装成功后,直接用自然语言跟 AI 助手对话就行:

- _"帮我画一只在公园里玩耍的小狗"_
- _"把这张图做成视频"_
- _"用 Nano Banana Pro 出一张 4K 竖屏海报"_
- _"我账上还有多少猫币?"_
- _"用 Seedance 2.0 做 10 秒 720p 的视频要多少钱?"_

Agent 会根据用户描述自动推断常见参数,比如横屏/竖屏、方图、4K、720p、5 秒/10 秒等,并按当前模型的合法参数调用脚本。

助手会自动选模型、走费用预览、提交任务、轮询结果,最后通过 `message` 工具把图/视频交付给你。

## 项目结构

```
.
├── README.md / README_en.md
├── LICENSE                         # Apache-2.0
├── SKILL.md                        # 技能定义(persona + 路由表 + 规则)
├── scripts/
│   ├── catsapi.py                  # API 客户端(--check / --list / --cost / --generate / --status)
│   └── build_capabilities.py       # 从后端 JSON 构建 capabilities.json
├── references/                     # 渐进式加载的详细文档
│   ├── api-key-setup.md
│   ├── image-models.md
│   ├── video-models.md
│   └── output-delivery.md
└── data/
    └── capabilities.json           # 模型参数目录(自动生成)
```

> 注:本 repo 采用**扁平结构**,repo 根即 skill 根,`SKILL.md` 就在最外层。
> 克隆到 `.cursor/skills/catsapi/` 或加为 submodule 后 Cursor 可直接识别。

## 重建 capabilities.json

当后端的 `image_models.json` / `abacus_video_models.json` 更新后:

```bash
python3 scripts/build_capabilities.py \
  --image-models /path/to/backend/app/image_models.json \
  --video-models /path/to/backend/app/abacus_video_models.json \
  -o data/capabilities.json
```

或者直接从已部署的后端拉(需要 `/api/models` 无鉴权可访问):

```bash
python3 scripts/build_capabilities.py \
  --from-api https://catsapi.com \
  -o data/capabilities.json
```

## 许可证

Apache License 2.0 — 见 [LICENSE](./LICENSE)。

## 相关项目

- [catsapi.com](https://catsapi.com) — 猫影工坊主站
- [Cursor Agent Skills 文档](https://cursor.com/docs/skills)
- [Agent Skills 开放标准](https://agentskills.io)
