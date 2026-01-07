# 日志系统规范 (Log Specification)

本系统采用统一的 JSON 格式存储日志到 MongoDB。所有接入系统的程序必须遵循此规范。

## 1. 字段定义

| 字段名 | 类型 | 必填 | 描述 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `timestamp` | String | 是 | ISO 8601 格式的时间戳 (UTC) | `"2023-10-27T10:00:00.123Z"` |
| `service_name` | String | 是 | 产生日志的服务/程序名称 | `"payment-service"`, `"data-processor"` |
| `level` | String | 是 | 日志级别 (UPPERCASE) | `"INFO"`, `"ERROR"`, `"WARNING"`, `"DEBUG"` |
| `message` | String | 是 | 日志主要内容 | `"Payment processed successfully"` |
| `trace_id` | String | 否 | 用于链路追踪的唯一ID | `"a1b2c3d4-e5f6..."` |
| `file_path` | String | 否 | 产生日志的代码文件路径 | `"/app/src/payment.py"` |
| `line_number` | Integer | 否 | 代码行号 | `42` |
| `metadata` | Object | 否 | 结构化的额外信息 | `{"user_id": 123, "amount": 99.9}` |

## 2. MongoDB 存储结构

- **Database**: `log_monitor`
- **Collection**: `app_logs`
- **Index**:
  - `timestamp` (用于按时间范围查询)
  - `service_name` (用于按服务过滤)
  - `level` (用于筛选错误)
  - `trace_id` (用于追踪)

## 3. 示例 JSON

```json
{
  "timestamp": "2023-10-27T10:00:00.123Z",
  "service_name": "payment-service",
  "level": "ERROR",
  "message": "Database connection failed",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_path": "db_connector.py",
  "line_number": 88,
  "metadata": {
    "db_host": "192.168.1.10",
    "retry_count": 3
  }
}
```
