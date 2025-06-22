
1. Get All Tasks

curl -X GET "http://localhost:5670/api/tasks"
2. Get Single Task Details

curl -X GET "http://localhost:5670/api/tasks/{task_id}"
Example:


curl -X GET "http://localhost:5670/api/tasks/task_123"
3. Update Task Configuration

curl -X PUT "http://localhost:5670/api/tasks/{task_id}" \
-H "Content-Type: application/json" \
-d '{"enabled": true, "interval_seconds": 3600}'
Example:


curl -X PUT "http://localhost:5670/api/tasks/file_scan" \
-H "Content-Type: application/json" \
-d '{"enabled": true, "interval_seconds": 20}'
4. Start a Task

curl -X POST "http://localhost:5670/api/tasks/{task_id}/start"
Example:


curl -X POST "http://localhost:5670/api/tasks/task_123/start"
5. Stop a Task

curl -X POST "http://localhost:5670/api/tasks/file_scan/stop"
Example:


curl -X POST "http://localhost:5670/api/tasks/task_123/stop"
6. Get Task Execution History

curl -X GET "http://localhost:5670/api/tasks/{task_id}/executions?limit={limit}"
Examples:


# Get default 50 executions
curl -X GET "http://localhost:5670/api/tasks/task_123/executions"

# Get 10 executions
curl -X GET "http://localhost:5670/api/tasks/task_123/executions?limit=10"