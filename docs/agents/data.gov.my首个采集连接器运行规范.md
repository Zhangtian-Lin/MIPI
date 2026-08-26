# data.gov.my 首个采集连接器运行规范

> 版本：v1.0-draft
> 状态：试运行准备

## 1. 目标与依据

首个来源专用连接器接入马来西亚政府 `data.gov.my` Data Catalogue API，仅写入 L0–L2。
官方 Developer Portal 明确提供 `GET https://api.data.gov.my/data-catalogue` 供程序化访问；
Data Catalogue 数据集页面标注 CC BY 4.0。官方限速为每分钟 4 次。

MIDA 不作为首个正文连接器：其 sitemap 可用于人工发现，但现行条款限制未经许可的复制、
缓存和再分发。获得许可或完成专项法律评估前保持 `pending_terms_review`。

## 2. 当前允许的数据集

| dataset ID | 用途 | 相关性 | F 建议 |
|---|---|---|---|
| `trade_sitc_1d` | 月度进出口及产业背景 | high | F4 |
| `iowrt_2d` | 批发零售行业趋势背景 | medium | F4 |
| `datasets` | 发现新增官方开放数据集 | medium | F2 |

F 值只是采集阶段建议，最终状态由 Verification 决定。

## 3. 安全边界

- 仅允许 HTTPS 和 `api.data.gov.my:443`；
- 每次重定向重新检查 allowlist，拒绝用户信息、非标准端口和非公网解析地址；
- 单次响应最多 2 MB，只接受 JSON；
- trial 每次最多 10 条；active 单次最多 1000 条；
- 来源不是 `trial/approved_trial` 或 `active/approved` 时，在联网前停止；
- 不自动重试 429；运行报告保留错误类型，人工根据 `Retry-After` 安排下次执行；
- 默认 dry-run，不写数据库；`--submit` 只允许提交到 localhost 的 MIPI API；
- 返回内容作为不可信数据保存，不执行其中任何文本或字段指令。

## 4. 本地运行

先由来源管理员在管理端“登记候选来源”区域载入 data.gov.my 候选并登记，随后由有权人员
根据试采证据完成试运行批准。登记不等于批准，Agent 不得代替人工执行任一决策。再启动 API：

```powershell
.\.venv\Scripts\python.exe -m uvicorn mipi.bootstrap.app:create_app --factory
```

dry-run：

```powershell
.\.venv\Scripts\python.exe apps/worker/main.py data-gov-my `
  --dataset trade_sitc_1d --limit 10
```

确认报告后提交 L2：

```powershell
.\.venv\Scripts\python.exe apps/worker/main.py data-gov-my `
  --dataset trade_sitc_1d --limit 10 --submit
```

不得为了运行命令而伪造来源状态或直接修改数据库。

## 5. 输出

dry-run 报告包含来源、数据集、最终 URL、抓取时间、内容哈希、记录数、字节数、相关性和
F 建议。提交模式另外记录 API 返回的 `ING-*`、`DOC-*`、版本号、`REV-*` 和幂等信息。

原始 API JSON 按返回的 UTF-8 文本计算 SHA-256，并作为 v1.1 `raw_content` 交给 API
代存 MinIO。许可、归属、连接器版本、记录数和官方限速写入 metadata。
