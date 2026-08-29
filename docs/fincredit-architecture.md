# FinCredit Copilot 二次开发架构

## 设计目标

P0 聚焦“材料可信、政策有据、计算确定、结论人工、过程可追溯”。系统辅助住房贷款受理和审批，不把大模型当作规则计算器，也不允许 Agent 直接写入最终授信结论。

## 从上游原型到 FinCredit Copilot

```mermaid
flowchart LR
    subgraph U[上游参考原型]
        U1[英文住房贷款流程] --> U2[美国合规模拟知识库]
        U2 --> U3[单路向量检索]
        U3 --> U4[Agent 风险工具]
        U4 --> U5[角色工作台]
    end

    subgraph F[FinCredit Copilot P0]
        F1[中文身份证/收入证明/银行流水] --> F2[逐页文本+视觉提取]
        F2 --> F3[证据坐标/置信度/人工修订]
        F3 --> F4[姓名与收入跨材料核验]
        F4 --> F5[全国+成都版本化政策库]
        F5 --> F6[混合检索+RRF]
        F6 --> F7{证据充分?}
        F7 -- 否 --> F8[最多一次受控查询改写]
        F8 --> F7
        F7 -- 是 --> F9[带引用的 Agent 建议]
        F7 -- 仍不足 --> F10[拒答/转人工]
        F4 --> F11[确定性 DTI/LTV 与材料门禁]
        F9 --> F12[人工两阶段确认]
        F11 --> F12
        F12 --> F13[trace_id + 哈希链 + MLflow]
    end

    U5 -->|Apache-2.0 二次开发| F1
```

## 运行时主链路

```mermaid
sequenceDiagram
    actor Human as 客户经理/审批人员
    participant UI as React 工作台
    participant Agent as 角色 Agent
    participant Extract as 材料提取与核验
    participant RAG as 受控 Agentic RAG
    participant Rules as 确定性规则引擎
    participant Audit as 审计与 MLflow

    Human->>UI: 上传合成材料
    UI->>Extract: 逐页解析
    Extract-->>Human: 字段、页码、证据、置信度
    Human->>Extract: 修订低置信度字段
    Extract->>Audit: 追加式修订记录
    Human->>Agent: 查询适用政策
    Agent->>RAG: 全国/成都过滤 + 混合检索
    RAG-->>Agent: 引用、版本、生效日期
    Agent-->>Human: 有证据的辅助回答
    Human->>Rules: 输入拟申请月供
    Rules-->>Human: DTI/LTV、材料门禁、辅助建议
    Human->>Agent: 发起决策提案
    Agent-->>Human: 提案 UUID，等待明确确认
    Human->>Agent: 确认最终人工决策
    Agent->>Audit: 写入决策与 trace_id
```

## 关键安全边界

- 政策时间截点为 2026-08-25。失效或未来政策不能被当作当前依据。
- 全国规则与成都市地方规则按辖区和层级过滤；内部演示阈值必须显式标注，不能冒充监管规则。
- 查询改写最多一次；证据仍不足时拒答或转人工。
- DTI、LTV、材料完整性与一致性门禁由确定性代码计算，并保存输入、公式和规则版本。
- Agent 只能生成建议和待确认提案，最终决策需要有权限的人工确认。
- 每次模型调用、检索、计算、修订和决策均可通过 trace_id 关联查询。

## P0 外范围

P0 不承诺生产级灾备、真实征信接入、电子签章、真实银行流水验真、正式监管法律意见、付费模型压测结果或 OpenShift 生产验收。Helm/OpenShift 配置保留兼容性，但本次验收以 Windows + Docker Desktop 本地演示为准。
