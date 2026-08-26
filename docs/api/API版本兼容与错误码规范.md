# API 版本兼容与错误码规范

> 版本：v1.0-draft

## 1. 版本

路径使用 `/v1`。新增可选字段保持兼容；删除、改名、改变含义或收紧必填属于破坏性变化，需要新主版本或正式弃用流程。

## 2. 响应包络

```json
{
  "data": {},
  "meta": {"request_id": "...", "contract_version": "1.0"},
  "error": null
}
```

错误时 `data=null`，包含稳定 code、用户安全 message、字段 details、request_id 和 retryable。

## 3. 错误码

| Code | HTTP | 含义 | 可重试 |
|---|---:|---|---|
| VALIDATION_ERROR | 422 | 输入或 Schema 错误 | 否 |
| CONTENT_HASH_MISMATCH | 422 | 原文复算摘要与提交值不同 | 否 |
| SOURCE_NOT_FOUND | 404 | 采集包引用的来源未登记 | 否 |
| SOURCE_CONFLICT | 409 | 同一来源 ID 的登记字段不一致 | 否 |
| IDEMPOTENCY_CONFLICT | 409 | 同一幂等键对应不同输入 | 否 |
| REVIEW_TASK_NOT_FOUND | 404 | 审核任务不存在 | 否 |
| REVIEW_CONFLICT | 409 | 任务已完成或同一审核人重复决定 | 否 |
| REVIEW_PERMISSION_DENIED | 403 | 当前角色不能执行该审核决定 | 否 |
| INVALID_REVIEW_DECISION | 422 | 理由、限制条件或状态不符合规则 | 否 |
| REVIEW_AUTH_NOT_CONFIGURED | 503 | 生产审核身份系统尚未配置 | 是 |
| SOURCE_TRANSITION_CONFLICT | 409 | 当前来源状态不允许所请求的转换 | 否 |
| INVALID_SOURCE_DECISION | 422 | 来源检查、robots 或试采证据不满足门槛 | 否 |
| SOURCE_ADMIN_AUTH_NOT_CONFIGURED | 503 | 当前环境未配置来源管理员身份系统 | 是 |
| SOURCE_DECISION_IDEMPOTENCY_CONFLICT | 409 | 同一来源决定幂等键对应不同请求 | 否 |
| UNAUTHORIZED | 401 | 未认证 | 条件 |
| FORBIDDEN | 403 | 无权限 | 否 |
| NOT_FOUND | 404 | 对象不存在 | 否 |
| CONFLICT | 409 | 版本、幂等或状态冲突 | 条件 |
| RATE_LIMITED | 429 | 超过限额 | 是 |
| UPSTREAM_UNAVAILABLE | 502 | 上游失败 | 是 |
| TEMPORARILY_UNAVAILABLE | 503 | 服务暂不可用 | 是 |
| INTERNAL_ERROR | 500 | 未分类内部错误 | 条件 |

## 4. 分页与筛选

大列表使用 cursor；排序字段白名单；筛选参数写入 URL；所有时间为带时区 ISO 8601；金额返回原值、币种、口径和可选换算。

## 5. 幂等

写接口接收 `Idempotency-Key`。相同键和相同请求返回原结果；相同键不同请求返回 409。

## 6. 缓存

公开实体页允许 ETag/Cache-Control；审核、用户工作区和隔离数据禁止公共缓存。更正或撤回必须使相关缓存失效。

## 7. 弃用

响应头和文档公布弃用日期、替代接口和迁移说明；至少覆盖一个客户端发布周期。安全问题可加速，但必须提供通知和兼容处理。
