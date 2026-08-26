# MIPI 文档索引与版本治理

> 文档体系版本：v1.0  
> 生效日期：2026-08-20  
> 状态：基线草案

## 1. 权威顺序

发生冲突时依次服从：用户当前明确要求、已批准任务验收标准、机器契约、最新 ADR、专项规范、概念文档、Agent 通用指引。Agent 必须报告实质冲突，不得静默选择。

## 2. 文档状态

- `draft`：可讨论，不作为自动发布依据；
- `reviewed`：已评审，可用于测试环境；
- `approved`：生产执行依据；
- `deprecated`：仍可追溯，不再用于新任务；
- `superseded`：已被指定版本替代。

## 3. 目录

| 目录 | 权威范围 |
|---|---|
| `product/` | MVP、用户任务和验收 |
| `data/` | 数据字典、分类、来源和状态机 |
| `agents/` | Agent 编排、输入输出和交接 |
| `contracts/` | Schema、OpenAPI 和兼容规则 |
| `quality/` | 评测、阈值和数据质量 |
| `operations/` | 审核、发布、部署、监控和恢复 |
| `security/` | 权限、威胁和非可信内容 |
| `compliance/` | 版权、隐私和保留 |
| `api/` | API 版本与错误码 |
| `design/` | 设计系统和页面原型 |
| `ai/` | 模型、提示词和成本治理 |

## 4. 当前文档清单

根目录五份概念与执行文档继续有效；`docs/` 下专项文档优先于根目录中的概括性表述。机器可读 YAML/JSON Schema 优先于 Markdown 示例字段。

| 文档 | 状态 | 负责人角色 |
|---|---|---|
| `product/MVP需求与验收标准.md` | draft | Product Owner |
| `product/贸易指标首条数据闭环.md` | draft | Product / Data Owner |
| `product/事件与证据首条闭环.md` | draft | Product / Editorial Owner |
| `product/公开搜索首条闭环.md` | draft | Product / Search Owner |
| `data/数据字典与状态机规范.md` | draft | Data Steward |
| `data/来源注册与评级规范.md` | draft | Source Admin |
| `data/分类体系与术语规范.md` | draft | Data Steward |
| `agents/Agent编排与交接协议.md` | draft | System Owner |
| `agents/data.gov.my首个采集连接器运行规范.md` | draft | Crawl Owner |
| `contracts/机器可执行契约规范.md` | draft | API/Data Owner |
| `operations/人工审核与发布更正SOP.md` | draft | Editorial Owner |
| `security/Agent安全与非可信内容处理规范.md` | draft | Security Owner |
| `security/身份权限与数据访问矩阵.md` | draft | Security Owner |
| `quality/Agent评测与发布门槛.md` | draft | Quality Owner |
| `quality/数据质量与可信度校准手册.md` | draft | Data Steward |
| `compliance/数据合规版权隐私与保留政策.md` | draft | Compliance Owner |
| `operations/部署与环境管理手册.md` | draft | Platform Owner |
| `operations/监控告警与事故响应手册.md` | draft | Platform Owner |
| `operations/备份恢复与灾难恢复手册.md` | draft | Platform Owner |
| `api/API版本兼容与错误码规范.md` | draft | API Owner |
| `design/品牌设计系统与页面原型规范.md` | draft | Design Owner |
| `ai/模型提示词与版本治理.md` | draft | AI/ML Owner |

## 5. 变更规则

任何破坏性字段、枚举、状态机、来源等级或权限变化必须：

1. 提交变更说明；
2. 更新版本号和生效日期；
3. 更新契约与黄金样本；
4. 提供迁移及回滚方案；
5. 由数据负责人和产品负责人批准；
6. 通知所有受影响 Agent。

## 6. Agent 读取要求

每次任务记录所使用的文档版本、契约版本、分类版本、模型版本和提示词版本。缺少必要输入时，Agent 只能进入准备或候选状态，不能发布。

## 7. 从 draft 到 approved

每份专项文档至少由负责人角色、一个受影响模块负责人和一个实际执行者评审。涉及安全、合规、删除、政治内容和生产发布的文档还需相应专项负责人批准。批准前只允许测试环境或人工监督运行。
