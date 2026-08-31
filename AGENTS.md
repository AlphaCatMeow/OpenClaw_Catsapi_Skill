# CatsAPI Agent Skill 维护说明

本仓库是 CatsAPI 主站的独立 Agent Skill / CLI 客户端，不再位于主站 `.cursor/skills/catsapi` 子模块内。

## 关联项目

- 主站：`/Users/yu/Developers/github_personal/personal_projects/ldc_gen_image`。
- 本仓库：`/Users/yu/Developers/github_personal/catsapi_relation/CatsAPI-Agent-Skill`；远端 `git@github.com:maodeyu180/CatsAPI-Agent-Skill.git`。
- 同级 ComfyUI 客户端：`/Users/yu/Developers/github_personal/catsapi_relation/ComfyUI_Catsapi`。
- 本地联合维护规则见上一层 `AGENTS.md`；涉及主站文件时先阅读主站 `AGENTS.md`。

## 同步入口

- `SKILL.md`：技能路由、调用约束、结果交付规则。
- `scripts/model_catalog.py`：客户端与构建脚本共用的模型名单、显示名、别名和执行限制。
- `scripts/catsapi.py`：schema 校验、鉴权、离线预检、费用保护、提交、恢复轮询及下载；不在 CLI 内额外调用 LLM。
- `scripts/build_capabilities.py`：从主站 schema 或只读模型 API 构建能力目录，复用集中支持名单。
- `data/capabilities.json`：生成的模型能力快照，优先运行构建脚本更新，不手工维护第二套参数表。
- `references/`、`README.md`、`README_en.md`：模型说明、密钥设置、参数推断和交付文档；随行为变化一起更新。

模型 schema 对应主站 `backend/app/image_models.json` / `backend/app/abacus_video_models.json`；启用名单和价格以 `backend/update_prices.py` 为准；请求和响应检查主站 `backend/app/schemas.py`、`backend/app/routers/tasks.py` 及 `backend/app/main.py` 中的 `/api/models`。执行限制还要核对 `backend/app/services/task_worker.py`：当前 Seedance schema 写 9 张参考图，但 worker 合并后最多保留 4 张，客户端按 4 张总上限处理。ComfyUI 是同级消费者，不是 schema 权威来源。

当前支持范围由 `scripts/model_catalog.py` 决定。主站新增模型不自动意味着 Skill 已支持；扩展时同时检查别名、文件输入、参数限制和参考文档。

## 开发与验证

- CLI 以 Python 标准库为主，不引入全局依赖，不调用 shell 来加载 API Key；不得把密钥写入输出、文档或生成结果。
- 优先使用项目内虚拟环境；当前联合工作区可用 `/Users/yu/Developers/github_personal/personal_projects/ldc_gen_image/backend/venv/bin/python` 做标准库检查，不向主站环境添加依赖。
- 修改后至少执行 Python 语法检查、`scripts/catsapi.py --help`、能力目录 JSON 校验，并离线核对支持名单、默认值与合法选项。行为变更使用 mock 检查请求和错误路径。
- 不把 `--check`、`--cost`、`--generate` 当作默认离线测试；它们会访问配置的 API，生成会消耗真实余额。
- `--list/--info --offline` 与 `--generate --dry-run` 可离线运行；回归使用 `python -m unittest discover -s tests -v`。超时和下载失败用 `--resume`，不得自动重提付费任务；费用预览保护不是原子锁价。
- 保留下载到本地后交付媒体的约定，检查任务失败、超时、退款相关状态的处理，不暴露内部结果 URL 或敏感信息。
- 中英文 README 同步维护。未经用户明确要求，不 commit、push、发布或操作主站生产环境。
