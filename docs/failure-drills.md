# FinCredit Copilot P0 故障演练记录

> 范围：合成数据与公开政策的本地演示环境。每项均按“症状—日志/Trace—根因—修复—回归测试”记录，不代表生产 SLA。

## 1. Qwen 429 / 请求超时

- 症状：文本生成、查询改写或材料抽取无法在时限内完成。
- 日志/Trace：结构化错误保留 `MODEL_RATE_LIMITED` 或 `MODEL_TIMEOUT`、`retryable`、模型名、HTTP 状态和 `trace_id`，不记录 API Key。
- 根因：百炼限流、网络波动或提供方响应超时。
- 修复：OpenAI 兼容客户端限定 `max_retries=1`、`timeout=60s`；失败后返回可诊断错误，由上层转人工，不进行无限重试。
- 回归测试：`test_inference_failures.py::test_qwen_429_becomes_structured_retryable_error_with_trace`、`test_qwen_timeout_becomes_structured_error`。

## 2. 模型返回非法 JSON

- 症状：抽取结果不是 JSON，或字段结构不符合三类材料 Schema。
- 日志/Trace：记录抽取失败/修复状态、模型与 Prompt 版本、材料页码；不把无效内容直接写成可信字段。
- 根因：模型输出夹带说明文字、缺字段或类型错误。
- 修复：Pydantic/JSON Schema 严格校验，只允许一次修复；仍失败则材料进入人工处理。
- 回归测试：`test_extraction.py::TestStructuredExtraction::test_extract_via_llm_handles_malformed_json`、`test_invalid_schema_is_repaired_once`。

## 3. Embedding 不是 768 维

- 症状：向量无法写入 `Vector(768)`，可能在数据库侧产生维度错误。
- 日志/Trace：诊断明确显示期望维度、实际维度和向量序号。
- 根因：模型切换、提供方默认维度变化或环境变量误配。
- 修复：请求显式传 `dimensions=768`，并在入库前逐条校验，错误向量不会到达 pgvector。
- 回归测试：`test_embeddings.py::TestValidateEmbeddingDimensions::test_rejects_wrong_dimension`。

## 4. 检索不到足够政策证据

- 症状：首次 Hybrid Search 无结果、相关性不足或官方来源缺 URL。
- 日志/Trace：审计保存原问题、改写问题、检索次数、模型、Prompt 版本、引用编号和证据不足原因。
- 根因：问题超出“全国住房贷款 + 成都地方规则”语料范围，或表述过于模糊。
- 修复：Qwen 只做一次查询改写并只重试一次；仍不足时拒绝生成确定结论并转人工。
- 回归测试：`test_controlled_retrieval.py::test_second_insufficient_search_fails_closed`、`test_invalid_rewrite_stops_without_unbounded_retry`。

## 5. 命中过期政策

- 症状：新申请可能错误引用成都 2023 历史规则或已结束的 2026 阶段性规则。
- 日志/Trace：引用包含发布、生效、失效、版本和适用日期；历史版本仍可按历史日期回放。
- 根因：仅按相似度排序，未把申请日期加入过滤。
- 修复：向量与关键词两路 SQL 均执行 `effective_date <= as_of <= expires_at`；纯函数测试覆盖边界日与次日。
- 回归测试：`test_inference_failures.py::test_expired_policy_is_excluded_on_next_day`、`test_kb_search.py::test_passes_date_and_provenance_filters_to_both_retrievers`。

## 6. 文档字段置信度低

- 症状：扫描模糊或证据不足导致关键字段置信度低于 0.8。
- 日志/Trace：保存字段、页码、证据文本、抽取方法、置信度与 `low_confidence` 标记。
- 根因：图片质量、版式或模型识别不确定。
- 修复：材料状态改为 `PENDING_REVIEW`，阻止自动推进；人工更正以追加记录保存修改前后值、操作者和原因。
- 回归测试：`test_extraction.py::TestDocumentProcessing::test_low_confidence_field_requires_human_review`、`test_extraction_review.py`。

## 运行命令

```powershell
cd packages/api
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider `
  tests/test_inference_failures.py `
  tests/test_controlled_retrieval.py `
  tests/test_embeddings.py `
  tests/test_extraction.py `
  tests/test_extraction_review.py `
  tests/test_kb_search.py -q
```

完整演练产生的 `trace_id` 可通过 `GET /api/audit/trace/{trace_id}` 回放；本地 MLflow 使用 `docker compose --profile observability up -d` 启动。
