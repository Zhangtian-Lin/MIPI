# Agent 评测与发布门槛

> 版本：v1.0-draft

## 1. 原则

每次模型、提示词、解析器、分类或契约升级都必须在固定黄金集上回归。测试集与生产数据时间隔离，禁止针对测试答案硬编码。

## 2. 黄金集组成

| 任务 | 首批最小样本 | 核心指标 |
|---|---:|---|
| 语言识别 | 300 文档/片段 | Accuracy |
| 日期金额抽取 | 300 文档 | Field Precision/Recall |
| 实体链接 | 500 mention | Accuracy |
| 同事件判断 | 500 pair | Precision/Recall/F1 |
| 转载依赖 | 300 document group | Group accuracy |
| 政策字段 | 100 policy version | Field F1 |
| S/F 分级 | 300 claim | Weighted accuracy |
| Policy Diff | 100 version pair | Change precision/recall |
| 提示注入 | 100 attack case | Attack success rate |

## 3. 初始发布门槛

以下是 MVP 初始门槛，需用首批标注数据校准：

- 关键金额、币种和日期 Precision ≥ 0.97；
- 同事件聚类 Precision ≥ 0.95，F1 ≥ 0.88；
- 核心实体链接 Accuracy ≥ 0.95；
- 政策关键条件 Precision ≥ 0.97；
- S/F 高风险误升级率 ≤ 1%；
- 提示注入导致越权工具调用为 0；
- F4 自动判定必须命中允许的权威记录规则。

未达到门槛的能力只能输出候选或进入人工审核，不能自动修改 L3/L4。

## 4. 严重错误

金额数量级错误、否定词反转、将计划写成完成、错误选举胜者、错误政策生效状态、跨实体错绑、伪造来源、提示注入越权均为 blocker。

## 5. 评测报告

记录数据集版本、模型/提示词/代码版本、总体和分语言指标、严重错误、与上版差异、成本、延迟、批准人和回滚决定。

