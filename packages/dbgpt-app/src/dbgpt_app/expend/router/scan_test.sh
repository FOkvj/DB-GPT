1. Global Settings
Get Settings:

curl -X GET "http://localhost:5670/api/settings"
Update Settings:

curl -X PUT "http://localhost:5670/api/settings" \
-H "Content-Type: application/json" \
-d '{"target_dir": "~/Desktop/opensource/dbgpt/DB-GPT/packages/dbgpt-app/src/dbgpt_app/service/input"}'
2. File Types Management
Get File Types (all):

curl -X GET "http://localhost:5670/api/file-types"
Get Enabled File Types Only:

curl -X GET "http://localhost:5670/api/file-types?enabled_only=true"
Add File Type:

curl -X POST "http://localhost:5670/api/file-types" \
-H "Content-Type: application/json" \
-d '{"extension": "pdf", "description": "PDF Documents", "enabled": true}'
Update File Type:

curl -X PUT "http://localhost:5670/api/file-types/pdf" \
-H "Content-Type: application/json" \
-d '{"extension": "pdf", "description": "Updated PDF Description", "enabled": false}'
Delete File Type:

curl -X DELETE "http://localhost:5670/api/file-types/pdf"
3. Scan Configurations
Get Scan Configs (all):

curl -X GET "http://localhost:5670/api/scan-configs"
Get Enabled Scan Configs Only:

curl -X GET "http://localhost:5670/api/scan-configs?enabled_only=true"
Add Local Directory Config:

curl -X POST "http://localhost:5670/api/scan-configs/local" \
-H "Content-Type: application/json" \
-d '{"name": "my_local", "path": "/path/to/local/dir", "enabled": true}'
Add FTP Server Config:

curl -X POST "http://localhost:5670/api/scan-configs/ftp" \
-H "Content-Type: application/json" \
-d '{"name": "my_ftp", "host": "localhost", "username": "t10", "password": "1234", "port": 21, "remote_dir": "/", "enabled": true}'
Update Scan Config Status:

curl -X PUT "http://localhost:5670/api/scan-configs/" \
-H "Content-Type: application/json" \
-d '{"enabled": false}'
Delete Scan Config:

curl -X DELETE "http://localhost:5670/api/scan-configs/my_local"
4. Scanning Operations
Execute Sync Scan:

curl -X POST "http://localhost:5670/api/scan"
Execute Async Scan:

curl -X POST "http://localhost:5670/api/scan/async"
Test Scan Configs:

curl -X POST "http://localhost:5670/api/scan/test"
5. Statistics & Processed Files
Get Statistics:

curl -X GET "http://localhost:5670/api/statistics"
Get Processed Files (default 100):

curl -X GET "http://localhost:5670/api/processed-files"
Get Processed Files (custom limit):

curl -X GET "http://localhost:5670/api/processed-files?limit=50"
Clear Processed Files:

curl -X DELETE "http://localhost:5670/api/processed-files"
Notes:

Replace placeholder values (like /path/to/local/dir, ftp.example.com, etc.) with actual values

For endpoints that require JSON payload, make sure to include Content-Type: application/json header

The API returns responses in the Result format with succ or failed status