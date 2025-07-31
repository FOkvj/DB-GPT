# API测试curl命令

## 1. 获取知识库映射配置
```bash
curl -X GET "http://localhost:5670/api/knowledge-mappings" \
  -H "Content-Type: application/json"
```

## 2. 保存知识库映射配置
#
#class KnowledgeBaseMappingConfig(BaseModel):
#    scan_config_name: str = None
#    knowledge_base_id: str = None
#    knowledge_base_name: str = None
#    enabled: bool = True
#
#class KnowledgeBaseMappingRequest(BaseModel):
#    mappings: List[KnowledgeBaseMappingConfig]
```bash
curl -X POST "http://localhost:5670/api/knowledge-mappings" \
  -H "Content-Type: application/json" \
  -d '{
  "mappings": [
    {
      "scan_config_name": "my_scan_config",
      "knowledge_base_id": "my_knowledge_base",
      "knowledge_base_name": "My Knowledge Base",
      "enabled": true
    }
  ]
  }'
```

## 3. 获取STT源类型的文件列表
```bash
curl -X GET "http://localhost:5670/api/files" \
  -H "Content-Type: application/json"
```

## 4. 删除STT源类型的文件
```bash
curl -X POST "http://localhost:5670/api/files/delete" \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["file_id_1", "file_id_2", "file_id_3"]
  }'
```

## 5. 重新处理指定文件
```bash
# 重新处理文件并发送到STT主题
curl -X POST "http://localhost:5670/api/files/reprocess" \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["file_id_1", "file_id_2"]
  }'

# 重新处理文件并发送到知识库
curl -X POST "http://localhost:5670/api/files/reprocess" \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["file_id_1", "file_id_2"],
    "target_topic": "to_knowledge"
  }'
```

## 6. 获取处理器状态
```bash
curl -X GET "http://localhost:5670/api/processors/status" \
  -H "Content-Type: application/json"
```

## 7. 控制处理器操作

### 启动所有处理器
```bash
curl -X POST "http://localhost:5670/api/processors/control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "start"
  }'
```

### 停止所有处理器
```bash
curl -X POST "http://localhost:5670/api/processors/control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "stop"
  }'
```

### 重启所有处理器
```bash
curl -X POST "http://localhost:5670/api/processors/control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "restart"
  }'
```

### 启动指定处理器
```bash
curl -X POST "http://localhost:5670/api/processors/control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "start",
    "processor_name": "knowledge_processor"
  }'
```

### 停止指定处理器
```bash
curl -X POST "http://localhost:5670/api/processors/control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "stop",
    "processor_name": "specific_processor_name"
  }'
```

### 重启指定处理器
```bash
curl -X POST "http://localhost:5670/api/processors/control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "restart",
    "processor_name": "specific_processor_name"
  }'
```

## 8. 获取处理统计信息
```bash
curl -X GET "http://localhost:5670/api/processing/statistics" \
  -H "Content-Type: application/json"
```

## 测试建议

1. **先测试GET请求**：从获取状态和文件列表开始
2. **获取实际的file_ids**：先调用`/files`接口获取真实的文件ID
3. **获取处理器名称**：先调用`/processors/status`获取实际的处理器名称
4. **查看响应格式**：所有响应都遵循`Result`格式，包含success/failed状态

## 响应格式示例
成功响应：
```json
{
  "success": true,
  "err_code": null,
  "err_msg": null,
  "data": {...}
}
```

失败响应：
```json
{
  "success": false,
  "err_code": "E500",
  "err_msg": "错误信息",
  "data": null
}
```