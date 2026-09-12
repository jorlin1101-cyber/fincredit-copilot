# 功能贡献说明

本文件说明 FinCredit Copilot 相对上游项目的功能贡献边界。
上游来源、基线提交与可复现的统计见 [UPSTREAM.md](UPSTREAM.md)。

## 统计摘要

以 `804da87`（上游快照，645 个文件）为基线：

| 分类 | 文件数 |
| --- | ---: |
| 与上游逐字节相同 | 392 |
| 已修改 | 229 |
| 已删除 | 24 |
| 新增 | 99 |

行级差异：`352 files changed, 25,573 insertions(+), 15,070 deletions(-)`

复现命令：`git diff --name-status 804da87 HEAD`、`git diff --shortstat 804da87 HEAD`

## 逐能力对照矩阵

| 能力 | 上游已有 | 本项目新增或改造 | 主要文件 |
| --- | --- | --- | --- |
| 模型链路 | 多 provider 抽象与模型路由 | 阿里云百炼通义千问文本 / Qwen-VL / embedding 三链路配置，768 维向量契约校验 | `packages/api/src/inference/client.py`(改)、`inference/config.py`(改)、`inference/embeddings.py`(改)、`config/models.yaml`(改) |
| 中文材料抽取 | 英文文档抽取流水线 | 中文身份证 / 收入证明 / 银行流水领域模型、页级文本与视觉抽取、严格 JSON 与证据校验、低置信度人工复核、追加式修订审计 | `packages/api/src/schemas/chinese_document.py`(新)、`services/extraction_normalization.py`(新)、`services/extraction_review.py`(新)、`services/extraction_prompts.py`(改) |
| 跨材料一致性核验 | 无 | 姓名与收入一致性比对，标记缺失项与冲突项，输出冲突证据 | `packages/api/src/schemas/consistency.py`(新)、`services/consistency.py`(新)、`routes/consistency.py`(新)、`tests/test_consistency.py`(新)、`tests/test_consistency_route.py`(新) |
| 政策知识库语料 | 美国联邦住房合规语料（ATR-QM / ECOA / FCRA / HMDA / TRID、Fannie Mae、FHA） | 全国通用监管政策、成都市地方规则与内部演示规则的版本化语料 | `data/compliance-kb/tier1-national/*`(新)、`tier2-chengdu/*`(新)、`tier3-internal-demo/*`(新)、`data/compliance-kb/README.md`(新) |
| 混合检索 | 基础知识库检索 | 中文分词、PostgreSQL 全文检索、pgvector 向量检索、RRF 融合排序 | `services/compliance/knowledge_base/search.py`(改)、`services/compliance/knowledge_base/controlled_retrieval.py`(新)、`alembic/..._add_hybrid_kb_search.py`(新) |
| 受控型 Agentic RAG | 无 | 最多一次受控查询改写、证据充分性门禁、引用验证、证据不足拒答与转人工 | `services/compliance/knowledge_base/controlled_retrieval.py`(新)、`alembic/..._add_policy_version_governance.py`(新)、`tests/test_controlled_retrieval.py`(新) |
| 确定性风控 | 无 | DTI / LTV 确定性计算、材料门禁、规则版本、仅供人工参考的建议状态 | `schemas/deterministic_assessment.py`(新)、`services/deterministic_assessment.py`(新)、`alembic/..._add_deterministic_credit_assessment.py`(新)、`tests/test_deterministic_assessment.py`(新) |
| 人工审批闭环 | 审批角色与流程骨架 | 带 UUID 的两阶段人工决策确认，模型无法自动批准或拒绝贷款 | `services/decision.py`(改)、`services/audit.py`(改)、`routes/underwriting.py`(改) |
| 审计与可观测 | MLflow 与结构化日志骨架 | `trace_id` 跨模型调用、检索、规则计算、材料修订与人工决策聚合 | `services/audit.py`(改)、`routes/audit.py`(改)、`schemas/audit.py`(改) |
| 中国市场本地化 | 美国房贷流程与英文文案 | 中国住房贷款流程、中文界面、成都公积金 / 首付 / 商转公规则、中国住房贷款测算 | `docs/china-housing-affordability-calculator.md`(新)、`packages/ui/src/lib/labels.ts`(改)、`lib/company.ts`(改)、`lib/staff-names.ts`(改) |
| 评测体系 | 上游评测脚手架 | 30 条政策问答评测集（A/B/C 三组对照：纯向量 / Hybrid+RRF / 受控 Agentic RAG）、评测脚本、故障演练 | `evaluations/datasets/fincredit_policy_pilot.json`(新)、`evaluations/run_policy_rag_eval.py`(新)、`docs/evaluation-report.md`(新)、`docs/failure-drills.md`(新) |
| 合成数据 | 上游演示数据 | 30 份带水印中文合成 PDF（身份证 / 收入证明 / 银行流水各 10 份）与清单 | `data/demo-documents/**`(新，32 个文件)、`scripts/generate_synthetic_documents.py`(新)、`data/schema-samples/*`(新) |
| 工程质量 | 上游 CI 与构建 | 前端单元测试、后端 pytest、Playwright E2E、CI 工作流调整 | `.github/workflows/ci.yml`(新)、`packages/ui/src/lib/labels.test.ts`(新)、`packages/api/tests/*`(新增多个测试模块) |
| 中国合规检查 | 美国合规检查逻辑 | 中国场景材料与政策一致性检查 | `packages/api/src/services/compliance/china_checks.py`(新)、`tests/test_china_compliance.py`(新) |
| 公网演示部署 | 本地容器编排 | Render 部署配置、演示访问保护、冷启动唤醒与聊天重连 | `render.yaml`(新)、`deploy/render-api-start.sh`(新)、`packages/api/src/middleware/demo_access.py`(新)、`packages/ui/src/lib/wake-service.ts`(新) |

## 已删除的上游内容

共移除 24 个与中国场景无关的上游文件：

**美国监管样例（7 个，见 [UPSTREAM.md](UPSTREAM.md)）**

- `data/compliance-kb/tier1-federal/` — ATR/QM、ECOA、FCRA、HMDA、TRID
- `data/compliance-kb/tier2-agency/` — Fannie Mae、FHA

**上游企业集成（17 个）**

- `deploy/helm/mortgage-ai/templates/nemo-guardrails-*.yaml`（5 个）
- `evaluations/evalhub/**` 与 `evaluations/eval-*.yaml`（11 个）
- `scripts/test-guardrails.sh`

这些文件的内容仍完整保留在基线提交 `804da87` 中，可随时追溯。

## 声明

开发中使用了 AI 辅助工具；所有生成代码、政策摘要、测试和演示材料均需由维护者审阅后再用于更高风险环境。
本项目仅使用合成数据，不用于真实授信决策。
