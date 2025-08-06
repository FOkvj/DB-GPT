// ============ 新增：文件处理相关接口 ============
import { AxiosRequestConfig } from 'axios';
import { DELETE, GET, POST } from '../index';

// 文件处理请求模型
export interface FileProcessingRequest {
  file_id?: string;
  source_file_id?: string;
  file_name?: string;
  source_type?: 'ftp' | 'stt';
  source_id?: string;
  file_type?: string;
  size?: number;
  status?: string;
  start_time?: string;
  end_time?: string;
}

// 文件处理响应模型
export interface FileProcessingResponse {
  id: number;
  file_id: string;
  file_name: string;
  source_type: string;
  source_file_id?: string;
  source_id: string;
  file_type?: string;
  size?: number;
  status: string;
  start_time?: string;
  end_time?: string;
  created_at?: string;
  updated_at?: string;
}

// 分页查询请求模型
export interface FileProcessingPageRequest {
  page: number;
  page_size: number;
  file_id?: string;
  source_file_id?: string;
  file_name?: string;
  source_type?: string;
  source_id?: string;
  file_type?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
}

// 批量操作请求模型
export interface BatchRequest {
  file_ids: string[];
}

// 分页结果模型
export interface PaginationResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// 文件处理统计响应
export interface FileProcessingStatistics {
  status_statistics: Record<string, number>;
  source_type_statistics: Record<string, number>;
}

// 新增API接口函数
export const getFileProcessingList = (params: FileProcessingPageRequest, config?: AxiosRequestConfig) =>
  POST<FileProcessingPageRequest, PaginationResult<FileProcessingResponse>>(
    '/api/file-processing/list',
    params,
    config,
  );

export const getFileProcessingStatistics = (config?: AxiosRequestConfig) =>
  GET<void, FileProcessingStatistics>('/api/file-processing/statistics/all', undefined, config);

export const batchDeleteFileProcessing = (request: BatchRequest, config?: AxiosRequestConfig) =>
  POST<BatchRequest, number>('/api/file-processing/batch/delete', request, config);


export const clearAllFileProcessing = (config?: AxiosRequestConfig) =>
  DELETE<void, boolean>('/api/file-processing/clear', undefined, config);

export const getFileProcessingByFileId = (fileId: string, config?: AxiosRequestConfig) =>
  GET<void, FileProcessingResponse>(`/api/file-processing/file/${fileId}`, undefined, config);

export const createFileProcessing = (request: FileProcessingRequest, config?: AxiosRequestConfig) =>
  POST<FileProcessingRequest, FileProcessingResponse>('/api/file-processing', request, config);
