# Skill 交互改版说明

核对日期：2026-08-31。这里记录设计依据，不是运行时必须加载的指南；不安装或执行第三方 skill 的脚本。

## 参考实现

- [fal 社区 genmedia Skill](https://github.com/fal-ai-community/skills/blob/main/skills/genmedia/SKILL.md)：模型发现、schema 查询、执行、异步状态与下载分开；支持面向 Agent 的结构化输出。本次借鉴命令职责划分，不复制其安装脚本、模型端点或路由服务。
- [fal model-routing](https://github.com/fal-ai-community/skills/blob/main/skills/model-routing/SKILL.md)：将模型选择知识与执行客户端分开。本次保留 CatsAPI 自己的模型名单与参数，不照搬第三方的质量排名、价格判断或模型 key。
- [Gemini CLI Nano Banana](https://github.com/gemini-cli-extensions/nanobanana) 及其 [GEMINI.md](https://github.com/gemini-cli-extensions/nanobanana/blob/main/GEMINI.md)：区分生成/编辑意图、保留用户的数量与创作约束、在当前工作目录管理输出。本次借鉴这些交互约束，不引入 MCP server 或 Node 依赖。核对时仓库约 1.1k stars；这只是项目关注度，不代表效果评测或市场排名。
- [OpenClaw Skill 格式](https://docs.openclaw.ai/tools/skills)：homepage 可放在 `metadata.openclaw.homepage`。本次将原有顶层字段迁入该位置，同时保留 OpenClaw 展示元数据并通过通用 Skill 结构校验。

## 改版决策

- 仍是一个 `catsapi` Skill，入口只保留意图判断、按需读取、费用/提交边界和交付约束；模型表与完整命令放到 references。
- 不强制猫系话术、中文、编号选模型、逐步注册问答或固定 `message` / `NO_REPLY`。尊重宿主能力与用户语言。
- 支持名单集中在 `scripts/model_catalog.py`；能力快照从主站 schema 生成，参数校验与费用维度解析共用。
- 离线发现/预检不读 Key、不联网、不写文件；真实生成始终先预估，再检查余额及预算。
- 单次提交后立即输出任务 ID；状态查询、恢复等待和结果下载不会再次生成。不自动重试不确定的提交，也不自动补图。
- 保留既有 CLI 主要动作和文本结果标记；增加结构化生命周期输出。已有文件不覆盖。
- ComfyUI 保留一个模型一个公开节点及原有节点 key；新增参数只按主站真实支持项提供。

## 验证场景

离线校验新增模型的合法/非法字段；核对预览与生成使用相同尺寸、质量、时长和数量；模拟超预算、余额不足、坏报价、未知提交结果、超时、下载失败和恢复；验证不同宿主的交付规则及元数据结构。所有自动化验证均不调用生产生成 API。

本次执行结果：Skill 25 项、ComfyUI 14 项离线回归通过；另外将 163 个 CLI 枚举选项、12 个节点的下拉项/默认值与主站源 schema 逐项比较通过。能力快照与构建结果一致，Skill 格式和 Python 语法校验通过。宿主交付规则经过文档走查，未在各宿主实际发送附件，也未运行完整 ComfyUI 或付费生成。

## 刻意保留的限制

客户端共支持 8 个图片、4 个视频模型，不等于主站全量名单。Seedance 的图片总上限仍为 4（主站 worker 限制）；客户端尚未暴露视频/音频参考。费用上限是提交前检查，不是后端原子锁价。离线 mock 不替代真实 ComfyUI UI、tensor 或付费生成效果验收。
