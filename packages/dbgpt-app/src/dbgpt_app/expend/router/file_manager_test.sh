curl -X GET "http://localhost:5670/api/files"

# Delete Files
curl -X DELETE "http://localhost:5670/api/files" \
-H "Content-Type: application/json" \
-d '{"file_paths": ["/path/to/file1", "/path/to/file2"]}'

# Get Pipeline Status
curl -X GET "http://localhost:5670/api/pipeline/status"

# Control Pipeline (Start/Stop)
curl -X POST "http://localhost:5670/api/pipeline/control" \
-H "Content-Type: application/json" \
-d '{"action": "start"}'

curl -X POST "http://localhost:5670/api/pipeline/control" \
-H "Content-Type: application/json" \
-d '{"action": "stop"}'