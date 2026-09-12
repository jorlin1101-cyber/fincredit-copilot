# 上游来源与贡献边界

FinCredit Copilot 是 Red Hat AI Quickstart 开源项目
[`rh-ai-quickstart/multi-agent-loan-origination`](https://github.com/rh-ai-quickstart/multi-agent-loan-origination)
的**二次开发**项目，遵循 [Apache License 2.0](LICENSE) 发布。

## 上游信息

| 项 | 值 |
| --- | --- |
| 上游仓库 | https://github.com/rh-ai-quickstart/multi-agent-loan-origination |
| 上游许可证 | Apache License 2.0 |
| 基线 commit | `1e50e51c334c1b6ed854d81a3f28fd324792f481` |
| 基线核验日期 | 2026-07-16 |
| 导入快照提交 | `804da87` — `chore: import upstream snapshot`（645 个文件） |
| 本仓库许可证 | 完整保留上游 `LICENSE`，以及上游源码中仍然适用的版权、专利与商标声明 |

上游项目提供住房贷款全流程的多角色 Agent 编排基础架构、平台骨架、企业集成与端到端演示框架。
本仓库保留该基线作为可追溯的起点，其后所有提交均为面向中国住房金融场景的改造。

## 贡献边界（可复现）

以下数据可通过 git 直接复现（把 `072aa08` 换成任意提交，即可得到该提交口径下的数字）：

```bash
git diff --name-status 804da87 072aa08      # 逐文件状态
git diff --shortstat   804da87 072aa08      # 行级增删
```

**以下统计截至提交 `072aa08`**（本归属说明所在提交；其后新增提交会使其变化，请以命令输出为准）：

| 分类 | 文件数 | 说明 |
| --- | ---: | --- |
| 与上游**逐字节相同** | 392 | 未改动的上游代码与脚手架 |
| 已修改 | 229 | 在上游实现基础上改造 |
| 已删除 | 24 | 移除与中国场景无关的上游企业集成与美国监管样例 |
| 新增 | 100 | 基线中原本不存在的文件 |

- 基线文件数：645 → 截至 `072aa08` 的文件数：721
- 行级差异：`353 files changed, 25,708 insertions(+), 15,070 deletions(-)`
- 校验：392 + 229 + 24 = 645，等于上游基线的文件总数

未改动的文件主要位于 `packages/`（上游核心应用代码），其余为 `.claude/`、`.codex/`、`deploy/`、
`evaluations/` 等脚手架与配置。

> 说明：以上数字为本文件引入时的快照。若后续继续提交，请用上面的命令重新计算，
> 并让 README、CONTRIBUTIONS.md 与本文件的统计口径保持一致。

## 本项目新增或改造的主要内容

- **模型链路**：接入阿里云百炼通义千问文本、视觉（Qwen-VL）与 embedding 三条链路，并校验 768 维向量契约。
- **中文材料处理**：身份证、收入证明、银行流水的领域模型、数据库迁移、页级文本/视觉抽取、严格 JSON 与证据校验、低置信度人工复核与追加式修订审计。
- **跨材料一致性核验**：姓名与收入一致性检查，输出冲突证据而非让模型猜测。
- **政策知识库**：全国通用监管政策、成都市地方规则与内部演示规则的版本化语料，含来源、版本与生效期管理。
- **受控型 Agentic RAG**：中文分词、PostgreSQL 全文检索、向量检索、RRF 融合、最多一次受控查询改写、证据充分性门禁、引用验证、拒答与转人工。
- **确定性风控**：DTI / LTV 由确定性程序计算，含材料门禁与规则版本；模型不承担数值推理，也不能自动批准或拒绝贷款。
- **审计与可观测**：`trace_id` 贯穿模型调用、检索、规则计算、材料修订与人工决策。
- **评测**：30 条政策问答评测集（A/B/C 三组对照）、故障演练、前端单元测试、后端 pytest 与 Playwright E2E。

逐项的文件级对照见 [CONTRIBUTIONS.md](CONTRIBUTIONS.md)。

## 已移除的上游非中国场景内容

以下内容继承自上游基线 `804da87`，属于美国住房金融监管语境，已从本项目移除：

- `data/compliance-kb/tier1-federal/` — ATR/QM、ECOA、FCRA、HMDA、TRID（5 个文件）
- `data/compliance-kb/tier2-agency/` — Fannie Mae、FHA（2 个文件）

移除原因：这些材料属于美国监管语境，与面向中国住房贷款的业务场景无关。
其内容仍完整保留在基线提交 `804da87` 中，可随时追溯。

知识库导入器仅加载 `tier1-national`、`tier2-chengdu`、`tier3-internal-demo` 三个目录
（见 `packages/api/src/services/compliance/knowledge_base/ingestion.py`），
因此上述移除不影响检索与评测流程。

## 数据集与声明边界

- 全部申请材料为**合成数据**（`data/demo-documents`，30 份带水印 PDF），不对应任何真实个人或机构。
- 政策文本来自公开监管资料，仅用于技术演示；`data/compliance-kb/tier3-internal-demo/` 下的机构规则为**演示用合成规则**，不冒充真实银行制度。
- 「融安住房金融」为虚构演示机构。
- 开发过程中使用了 AI 辅助工具；所有生成代码、政策摘要、测试与演示材料均应由维护者复核后再用于更高风险环境。

## 非背书声明

本项目与 Red Hat、上游项目贡献者、任何金融机构或监管部门**无隶属或背书关系**。
本项目仅用于技术演示与学习，不构成授信承诺、监管解释或法律意见。
产品名称与商标归各自所有者所有。
