# FinCredit Copilot

面向中国住房金融场景的智能授信辅助平台，覆盖贷前咨询、申请受理、材料核验、政策查询、风险分析、人工审批与管理分析。

项目以“融安住房金融（虚构演示机构）”为业务背景，使用合成申请数据和公开政策资料构建可本地运行的完整演示。系统只提供辅助分析，不自动批准或拒绝贷款，也不构成授信承诺、监管解释或法律意见。

## 核心能力

- **全流程业务工作台**：为借款人、客户经理、审批人员和管理人员提供差异化页面与操作权限。
- **申请材料智能核验**：识别身份证、收入证明、工资单和银行流水中的关键字段，展示置信度与人工复核入口。
- **跨材料一致性检查**：核对姓名、收入、证件信息等关键数据，标记缺失项和冲突项。
- **政策知识服务**：检索全国通用监管政策与成都市地方规则，回答中附带来源、版本、生效日期和官方链接。
- **风险辅助分析**：使用确定性程序计算债务收入比（DTI）和贷款成数（LTV），生成可解释的风险提示。
- **人工审批闭环**：系统生成待确认建议，最终授信决定必须由有权限的审批人员明确确认。
- **过程审计**：记录材料修订、政策检索、规则计算、模型调用与人工决策，支持问题追踪和流程复盘。

## 业务流程

```mermaid
flowchart LR
    A[贷款咨询] --> B[提交申请]
    B --> C[上传与识别材料]
    C --> D[完整性和一致性核验]
    D --> E[政策查询与风险计算]
    E --> F[客户经理补充材料]
    F --> G[审批人员复核]
    G --> H[人工确认决策]
    H --> I[审计记录与管理分析]
```

## 技术架构

| 层级     | 主要技术                                          |
| -------- | ------------------------------------------------- |
| 前端     | React 19、TypeScript、Vite、TanStack Router/Query |
| 后端     | FastAPI、Python 3.11、LangGraph、Pydantic         |
| 数据     | PostgreSQL 16、pgvector、SQLAlchemy、Alembic      |
| 模型     | 阿里云百炼兼容接口、Qwen 文本模型与向量模型       |
| 文件     | MinIO（S3 兼容对象存储）                          |
| 身份认证 | Keycloak OIDC（本地演示可关闭）                   |
| 可观测性 | MLflow、结构化日志、审计事件                      |
| 工程化   | Docker Compose、pnpm、uv、Turborepo               |

## 项目结构

```text
multi-agent-loan-origination/
├── config/                 # Agent 配置与身份认证配置
├── data/                   # 合成材料与政策数据
├── docs/                   # 架构、接口、评估与故障演练文档
├── evaluations/            # 政策检索评测集与评测脚本
├── packages/
│   ├── api/                # FastAPI 服务、Agent、检索和规则引擎
│   ├── db/                 # 数据模型与数据库迁移
│   ├── e2e/                # Playwright 端到端测试
│   └── ui/                 # React 前端
├── compose.yml             # 本地容器编排
└── .env.example            # 环境变量模板
```

## 快速启动

### 环境要求

- Docker Desktop
- Git
- 至少 16 GB 可用内存
- 阿里云百炼 API Key

### 1. 配置环境变量

将 `.env.example` 复制为 `.env`，填写模型服务密钥：

```powershell
Copy-Item .env.example .env
```

```dotenv
DASHSCOPE_API_KEY=你的_API_Key
```

`.env` 已被 Git 忽略，请勿将真实密钥提交到仓库。

### 2. 启动服务

```powershell
docker compose up -d --build
```

需要同时启动身份认证和可观测性服务时：

```powershell
docker compose --profile auth --profile observability up -d --build
```

### 3. 访问系统

| 服务         | 地址                         |
| ------------ | ---------------------------- |
| Web 应用     | <http://localhost:3000>      |
| API 文档     | <http://localhost:8000/docs> |
| MinIO 控制台 | <http://localhost:9091>      |

进入 Web 应用后点击“进入角色演示”，即可分别体验借款人、客户经理、审批人员和管理驾驶舱。

### 4. 停止服务

```powershell
docker compose down
```

## 本地开发

安装 Node.js 22、pnpm 9、Python 3.11 和 uv 后，可使用以下命令：

```powershell
pnpm install
pnpm build
pnpm dev
```

后端依赖和数据库迁移说明请参阅 [API 文档](packages/api/README.md) 与 [数据库文档](packages/db/README.md)。

## 测试与评估

```powershell
# 全部工作区测试
pnpm test

# 前端单元测试
pnpm --filter @mortgage-ai/ui test

# 后端测试
Set-Location packages/api
$env:AUTH_DISABLED="true"
uv run pytest -v

# 端到端测试
pnpm test:e2e
```

政策检索评测集位于 `evaluations/datasets/fincredit_policy_pilot.json`，覆盖直接问题、跨段组合问题、政策冲突与无答案问题。评测指标包括 Recall@5、MRR、引用正确率、无答案 F1、延迟和检索轮次。

## 设计边界

- 演示材料和申请数据均为合成数据，不对应真实个人或金融机构。
- 政策内容用于技术演示，正式业务应以监管部门和持牌金融机构的最新文件为准。
- DTI、LTV 与材料门禁由确定性程序计算，大模型不承担规则计算。
- 模型输出属于辅助建议，最终结论必须经过人工复核。
- 当前版本不包含真实征信、电子签章、银行流水验真和生产级灾备能力。

## 项目文档

- [系统架构](docs/fincredit-architecture.md)
- [评估说明](docs/evaluation-report.md)
- [故障演练](docs/failure-drills.md)
- [中国住房贷款测算说明](docs/china-housing-affordability-calculator.md)
- [许可证与归属说明](ATTRIBUTION.md)

## 许可证

本项目按照 Apache License 2.0 提供，详见 [LICENSE](LICENSE)。第三方代码来源及本项目修改范围见 [ATTRIBUTION.md](ATTRIBUTION.md)。
