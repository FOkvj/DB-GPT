import { AxiosRequestConfig } from 'axios';
import { DELETE, GET, POST, PUT } from '../index';

// 文件类型配置
export interface FileTypeModel {
  extension: string;
  description: string;
  enabled: boolean;
}

export interface FileTypeResponse extends FileTypeModel {
  id?: number;
}

// 扫描配置
export interface LocalDirectoryConfig {
  name: string;
  path: string;
  enabled: boolean;
}

export interface FTPServerConfig {
  name: string;
  host: string;
  username: string;
  password: string;
  port: number;
  remote_dir: string;
  enabled: boolean;
  file_types?: string[]; // 扫描的文件类型
  scan_interval?: number; // 扫描间隔（分钟）
}

export interface ScanConfigUpdate {
  enabled: boolean;
}

export interface ScanConfigResponse {
  id: number;
  name: string;
  type: 'local' | 'ftp';
  enabled: boolean;
  config: Record<string, any>;
  created_at: string;
  updated_at: string;
}

// 全局设置
export interface GlobalSettingModel {
  target_dir: string;
}

// 扫描结果
export interface ScanResult {
  scanned_files: number;
  new_files: number;
  processed_files: number;
  failed_files: number;
  scan_time: string;
}

// 统计信息
export interface StatisticsResponse {
  total_configs: number;
  enabled_configs: number;
  total_file_types: number;
  enabled_file_types: number;
  total_scanned_files: number;
  last_scan_time?: string;
}

// 已处理文件
export interface ProcessedFileResponse {
  id: number;
  file_path: string;
  file_name: string;
  file_size: number;
  processed_at: string;
  source_type: string;
  source_path: string;
}

// 定时任务相关接口类型
export interface TaskConfig {
  task_id: string;
  enabled: boolean;
  interval_seconds: number;
  running: boolean;
  next_run?: string;
}

// 新增：定时任务详情响应类型（匹配实际API返回）
export interface TaskDetailResponse {
  config: {
    id: number;
    task_id: string;
    task_name: string;
    description: string;
    enabled: boolean;
    interval_seconds: number | null; // 注意：API返回的字段名是 interval_secon
    created_at: string;
    updated_at: string;
  };
  running: boolean;
  next_run: string;
}

export interface TaskExecution {
  id: number;
  task_id: string;
  start_time: string;
  end_time?: string;
  status: 'running' | 'success' | 'failed';
  result?: string;
  error?: string;
}

export interface TaskUpdateRequest {
  enabled?: boolean;
  interval_seconds?: number;
}

// 新增：FTP测试响应类型
export interface FTPTestResponse {
  host: string;
  port: number;
  username: string;
  connected: boolean;
  error: string | null;
  root_files: string[] | string;
  remote_dir_status: string | null;
}

// API接口函数

// 全局设置
export const getSettings = (config?: AxiosRequestConfig) =>
  GET<void, { target_dir: string }>('/api/settings', undefined, config);

export const updateSettings = (settings: GlobalSettingModel, config?: AxiosRequestConfig) =>
  PUT<GlobalSettingModel, { message: string; target_dir: string }>('/api/settings', settings, config);

// 文件类型管理
export const getFileTypes = (enabledOnly: boolean = false, config?: AxiosRequestConfig) =>
  GET<{ enabled_only: boolean }, FileTypeResponse[]>('/api/file-types', { enabled_only: enabledOnly }, config);

export const addFileType = (fileType: FileTypeModel, config?: AxiosRequestConfig) =>
  POST<FileTypeModel, { message: string }>('/api/file-types', fileType, config);

export const updateFileType = (extension: string, fileType: FileTypeModel, config?: AxiosRequestConfig) =>
  PUT<FileTypeModel, { message: string }>(`/api/file-types/${extension}`, fileType, config);

export const deleteFileType = (extension: string, config?: AxiosRequestConfig) =>
  DELETE<void, { message: string }>(`/api/file-types/${extension}`, undefined, config);

// 扫描配置管理
export const getScanConfigs = (enabledOnly: boolean = false, config?: AxiosRequestConfig) =>
  GET<{ enabled_only: boolean }, ScanConfigResponse[]>('/api/scan-configs', { enabled_only: enabledOnly }, config);

export const addLocalDirectory = (localConfig: LocalDirectoryConfig, config?: AxiosRequestConfig) =>
  POST<LocalDirectoryConfig, { message: string }>('/api/scan-configs/local', localConfig, config);

export const addFTPServer = (ftpConfig: FTPServerConfig, config?: AxiosRequestConfig) =>
  POST<FTPServerConfig, { message: string }>('/api/scan-configs/ftp', ftpConfig, config);

export const updateScanConfig = (name: string, update: ScanConfigUpdate, config?: AxiosRequestConfig) =>
  PUT<ScanConfigUpdate, { message: string }>(`/api/scan-configs/${name}`, update, config);

export const deleteScanConfig = (name: string, config?: AxiosRequestConfig) =>
  DELETE<void, { message: string }>(`/api/scan-configs/${name}`, undefined, config);

// 扫描执行
export const executeScan = (config?: AxiosRequestConfig) => POST<void, ScanResult>('/api/scan', undefined, config);

export const executeScanAsync = (config?: AxiosRequestConfig) =>
  POST<void, { message: string }>('/api/scan/async', undefined, config);

export const testScanConfigs = (config?: AxiosRequestConfig) =>
  POST<
    void,
    {
      test_results: Array<{
        name: string;
        type: string;
        status: 'success' | 'error';
        message: string;
      }>;
    }
  >('/api/scan/test', undefined, config);

// 新增：FTP连接测试
export const testFTPConnection = (ftpConfig: FTPServerConfig, config?: AxiosRequestConfig) =>
  POST<FTPServerConfig, FTPTestResponse>('/api/test-ftp', ftpConfig, config);

// 统计和文件管理
export const getStatistics = (config?: AxiosRequestConfig) =>
  GET<void, StatisticsResponse>('/api/statistics', undefined, config);

export const getProcessedFiles = (limit: number = 100, config?: AxiosRequestConfig) =>
  GET<{ limit: number }, ProcessedFileResponse[]>('/api/processed-files', { limit }, config);

export const clearProcessedFiles = (config?: AxiosRequestConfig) =>
  DELETE<void, { message: string }>('/api/processed-files', undefined, config);

// 定时任务管理接口
export const getTaskStatus = (config?: AxiosRequestConfig) =>
  GET<void, Record<string, TaskConfig>>('/api/tasks', undefined, config);

// 修改：getTaskDetail 返回类型改为 TaskDetailResponse
export const getTaskDetail = (taskId: string, config?: AxiosRequestConfig) =>
  GET<void, TaskDetailResponse>(`/api/tasks/${taskId}`, undefined, config);

export const updateTask = (taskId: string, data: TaskUpdateRequest, config?: AxiosRequestConfig) =>
  PUT<TaskUpdateRequest, string>(`/api/tasks/${taskId}`, data, config);

export const startTask = (taskId: string, config?: AxiosRequestConfig) =>
  POST<void, string>(`/api/tasks/${taskId}/start`, undefined, config);

export const stopTask = (taskId: string, config?: AxiosRequestConfig) =>
  OST<void, string>(`/api/tasks/${taskId}/stop`, undefined, config);

export const getTaskExecutions = (taskId: string, limit: number = 50, config?: AxiosRequestConfig) =>
  GET<{ limit: number }, TaskExecution[]>(`/api/tasks/${taskId}/executions`, { limit }, config);
