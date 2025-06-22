import { AxiosRequestConfig } from 'axios';
import { DELETE, GET, POST } from '../index';

// 文件状态枚举
export enum FileStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  SKIPPED = 'skipped',
}

// 文件信息接口
export interface FileInfo {
  path: string;
  name: string;
  size: number;
  created_time: string;
  modified_time: string;
  extension: string;
  status: FileStatus;
  processors: string[];
  last_processed?: string;
  error_message?: string;
}

// 删除文件请求
export interface DeleteFilesRequest {
  file_paths: string[];
}

// 删除文件响应
export interface DeleteFilesResponse {
  results: Record<string, boolean>;
  success_count: number;
  total_count: number;
}

// 处理器统计信息
export interface ProcessorStatistics {
  processed: number;
  success: number;
  failed: number;
  skipped: number;
}

// 管道状态 - 匹配实际API返回结构
export interface PipelineStatus {
  running: boolean;
  queue_size: number;
  worker_count: number;
  watch_paths: string[];
  processor_statistics: Record<string, ProcessorStatistics>;
  registered_processors: string[];
}

// 管道控制请求
export interface PipelineControlRequest {
  action: 'start' | 'stop';
}

// 管道控制响应
export interface PipelineControlResponse {
  action: string;
  status: string;
}

// API 接口函数

/**
 * 获取自动加工结果文件列表
 */
export const getPipelineFiles = (config?: AxiosRequestConfig) => GET<void, FileInfo[]>('/api/files', undefined, config);

/**
 * 批量删除文件
 */
export const deletePipelineFiles = (request: DeleteFilesRequest, config?: AxiosRequestConfig) =>
  POST<DeleteFilesRequest, DeleteFilesResponse>('/api/files', request, config);

/**
 * 获取管道状态
 */
export const getPipelineStatus = (config?: AxiosRequestConfig) =>
  GET<void, PipelineStatus>('/api/pipeline/status', undefined, config);

/**
 * 控制管道启动/停止
 */
export const controlPipeline = (request: PipelineControlRequest, config?: AxiosRequestConfig) =>
  POST<PipelineControlRequest, PipelineControlResponse>('/api/pipeline/control', request, config);
