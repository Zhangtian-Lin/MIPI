# Agent 编排与交接协议

> 版本：v1.0-draft

## 1. 流程

```text
Source Discovery → Crawl → Parse/OCR → Language/Translate
→ Extract → Normalize/Link → Cluster → Verify
→ Human Review → Publish Projection → Web/Search/Agent
```

## 2. 交接信封

每次交接包含：`run_id`、`task_id`、`parent_task_id`、`artifact_ids`、`contract_version`、`taxonomy_version`、`prompt_version`、`attempt`、`idempotency_key`、`created_at`、`producer`、`next_action`、`review_flags`。

## 3. 状态

`queued`、`running`、`succeeded`、`retryable_failed`、`dead_letter`、`needs_review`、`blocked`、`cancelled`。

同一幂等键只能产生一个有效成功结果；重复提交返回已有结果。

## 4. 重试

- 网络瞬时错误、429、5xx：指数退避并遵守 Retry-After；
- Schema 不合法、权限不足、恶意内容：不自动重试；
- 模型超时：最多按任务配置重试，保留每次输出；
- 超过上限进入 dead letter，不得无限循环。

## 5. 数据所有权

Crawl 只能写 L0–L2；领域模块写 L3；Publication 写 L4；Verification 负责 F 等级；Sources 负责 S 等级；任何 Agent 不得跨模块直接更新表。

## 6. 人工闸门

以下必须人工：S1/S2 关键冲突、政治争议、重大金额异常、政策法律效力、选举正式结果替换、实体不可逆合并、公开更正和隔离区释放。

## 7. 并发与锁

文档以 canonical URL + content hash 幂等；实体合并使用 entity lock；政策版本以 policy ID + source version 锁；发布以 projection ID + revision 锁。锁超时不等于任务失败，应安全重排队。

## 8. 完成报告

报告输入、输出、版本、耗时、成本、警告、重试、审核项和下一步。没有通过 Schema 校验不得标记 succeeded。

