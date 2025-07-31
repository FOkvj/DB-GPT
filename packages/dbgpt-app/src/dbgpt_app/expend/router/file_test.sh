# FileProcessing API 测试 Curl 命令

## 1. 基础 CRUD 操作

### 创建文件处理记录
```bash
curl -X POST "http://localhost:5670/api/file-processing" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "file_001",
    "file_name": "test_document.pdf",
    "source_type": "ftp",
    "source_id": "source_001",
    "source_file_id": "sf_001",
    "file_type": "pdf",
    "size": 1024000,
    "status": "wait"
  }'
```

### 根据ID获取文件处理记录
```bash
curl -X GET "http://localhost:5670/api/file-processing/1"
```

### 根据文件ID获取文件处理记录
```bash
curl -X GET "http://localhost:5670/api/file-processing/file/file_001"
```

### 更新文件处理记录（按记录ID）
```bash
curl -X PUT "http://localhost:5670/api/file-processing/1" \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "updated_document.pdf",
    "status": "processing"
  }'
```

### 更新文件处理记录（按文件ID）
```bash
curl -X PUT "http://localhost:5670/api/file-processing/file/file_001" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "success"
  }'
```

### 删除文件处理记录（按记录ID）
```bash
curl -X DELETE "http://localhost:5670/api/file-processing/1"
```

### 删除文件处理记录（按文件ID）
```bash
curl -X DELETE "http://localhost:5670/api/file-processing/file/file_001"
```

## 2. 查询操作

### 获取文件处理记录列表（带过滤）
```bash
# 获取所有记录
curl -X GET "http://localhost:5670/api/file-processing"

# 按源类型过滤
curl -X GET "http://localhost:5670/api/file-processing?source_type=ftp"

# 按状态过滤
curl -X GET "http://localhost:5670/api/file-processing?status=processing"

# 多条件过滤
curl -X GET "http://localhost:5670/api/file-processing?source_type=ftp&status=wait&file_type=pdf"
```

### 按源类型获取文件列表
```bash
curl -X GET "http://localhost:5670/api/file-processing/source-type/ftp"
curl -X GET "http://localhost:5670/api/file-processing/source-type/stt"
```

### 按源ID获取文件列表
```bash
curl -X GET "http://localhost:5670/api/file-processing/source-id/source_001"
```

### 按源文件ID获取文件列表
```bash
curl -X GET "http://localhost:5670/api/file-processing/source-file-id/sf_001"
```

### 按状态获取文件列表
```bash
curl -X GET "http://localhost:5670/api/file-processing/status/wait"
curl -X GET "http://localhost:5670/api/file-processing/status/processing"
curl -X GET "http://localhost:5670/api/file-processing/status/success"
curl -X GET "http://localhost:5670/api/file-processing/status/failed"
```

### 获取特定状态的文件
```bash
# 获取正在处理的文件
curl -X GET "http://localhost:5670/api/file-processing/status/processing"

# 获取处理失败的文件
curl -X GET "http://localhost:5670/api/file-processing/status/failed"

# 获取等待处理的文件
curl -X GET "http://localhost:5670/api/file-processing/status/waiting"
```

### 分页查询
```bash
curl -X POST "http://localhost:5670/api/file-processing/list" \
  -H "Content-Type: application/json" \
  -d '{
    "page": 1,
    "page_size": 10
  }'
```

### 获取记录数量
```bash
curl -X POST "http://localhost:5670/api/file-processing/count" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "ftp",
    "status": "wait"
  }'
```

## 3. 状态管理

### 更新文件处理状态
```bash
curl -X POST "http://localhost:5670/api/file-processing/status/update" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "file_001",
    "status": "processing",
    "start_time": "2025-07-13T10:00:00"
  }'
```

### 开始处理文件
```bash
curl -X POST "http://localhost:5670/api/file-processing/start/file_001"
```

### 完成文件处理
```bash
# 成功完成
curl -X POST "http://localhost:5670/api/file-processing/complete/file_001?success=true"

# 失败完成
curl -X POST "http://localhost:5670/api/file-processing/complete/file_001?success=false"
```

### 重试处理文件
```bash
curl -X POST "http://localhost:5670/api/file-processing/retry/file_001"
```

## 4. 批量操作

### 批量更新状态
```bash
curl -X POST "http://localhost:5670/api/file-processing/batch/status" \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["file_001", "file_002", "file_003"],
    "status": "processing"
  }'
```

### 批量删除记录
```bash
curl -X POST "http://localhost:5670/api/file-processing/batch/delete" \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["file_001", "file_002", "file_003"]
  }'
```

### 重新处理文件
```bash
curl -X POST "http://localhost:5670/api/file-processing/reprocess" \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["file_001", "file_002", "file_003"]
  }'
```

## 5. 统计信息

### 获取状态统计
```bash
curl -X GET "http://localhost:5670/api/file-processing/statistics/status"
```

### 获取源类型统计
```bash
curl -X GET "http://localhost:5670/api/file-processing/statistics/source-type"
```

### 获取所有统计信息
```bash
curl -X GET "http://localhost:5670/api/file-processing/statistics/all"
```

## 6. 管理操作

### 清空所有记录
```bash
curl -X DELETE "http://localhost:5670/api/file-processing/clear"
```

## 测试脚本示例

### 创建多个测试数据
```bash
# 创建测试数据1
curl -X POST "http://localhost:5670/api/file-processing" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "test_001",
    "file_name": "document1.pdf",
    "source_type": "ftp",
    "source_id": "ftp_source_001",
    "file_type": "pdf",
    "size": 1024000
  }'

# 创建测试数据2
curl -X POST "http://localhost:5670/api/file-processing" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "test_002",
    "file_name": "audio1.wav",
    "source_type": "stt",
    "source_id": "stt_source_001",
    "file_type": "wav",
    "size": 2048000
  }'

# 创建测试数据3
curl -X POST "http://localhost:5670/api/file-processing" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "test_003",
    "file_name": "document2.docx",
    "source_type": "ftp",
    "source_id": "ftp_source_002",
    "file_type": "docx",
    "size": 512000
  }'
```

### 测试处理流程
```bash
# 1. 开始处理
curl -X POST "http://localhost:5670/api/file-processing/start/test_001"

# 2. 检查状态
curl -X GET "http://localhost:5670/api/file-processing/file/test_001"

# 3. 完成处理
curl -X POST "http://localhost:5670/api/file-processing/complete/test_001?success=true"

# 4. 查看统计
curl -X GET "http://localhost:5670/api/file-processing/statistics/all"
```

## 注意事项

1. **枚举值**：
   - `source_type`: "ftp" 或 "stt"
   - `status`: "wait", "processing", "success", "failed", "retrying", "downloading"

2. **时间格式**：使用 ISO 8601 格式，如 "2025-07-13T10:00:00"

3. **分页参数**：
   - `page`: 页码（从1开始）
   - `page_size`: 每页大小（1-100）

4. **响应格式**：所有响应都使用 `Result` 包装器格式：
   ```json
   {
     "success": true,
     "err_code": null,
     "err_msg": null,
     "data": { ... }
   }
   ```

5. **错误处理**：失败时返回：
   ```json
   {
     "success": false,
     "err_code": "E500",
     "err_msg": "错误信息",
     "data": null
   }
   ```