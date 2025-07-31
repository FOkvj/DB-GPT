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

// 知识库转换配置
export interface KnowledgeBaseMappingConfig {
  id: number;
  scan_config_name: string;
  knowledge_base_id: string;
  knowledge_base_name: string;
  enabled: boolean;
}

// 知识库映射配置
export interface KnowledgeBaseMappingRequest {
  mappings: KnowledgeBaseMappingConfig[];
}
// 处理器状态接口
export interface ProcessorInfo {
  name: string;
  topic: string;
  enabled: boolean;
  consuming: boolean;
}

export interface ProcessorsStatusResponse {
  processors: Record<string, ProcessorInfo>;
  total_processors: number;
}

// 处理器控制请求
export interface ProcessorControlRequest {
  action: 'start' | 'stop' | 'restart';
  processor_name?: string; // 可选，不传则控制所有处理器
}
// 修改重新处理文件的请求和响应接口
export interface ReprocessFilesRequest {
  file_ids: string[];
}

export interface ReprocessFilesResponse {
  reprocessed_files: string[];
  failed_files: Array<{
    file_id: string;
    error: string;
  }>;
  total_count: number;
  success_count: number;
}

// 修改API函数
export const reprocessFiles = (request: ReprocessFilesRequest, config?: AxiosRequestConfig) =>
  POST<ReprocessFilesRequest, ReprocessFilesResponse>('/api/pipeline/reprocess', request, config);

// 新增API函数
export const getProcessorsStatus = (config?: AxiosRequestConfig) =>
  GET<void, ProcessorsStatusResponse>('/api/processors/status', undefined, config);

export const controlProcessor = (request: ProcessorControlRequest, config?: AxiosRequestConfig) =>
  POST<ProcessorControlRequest, any>('/api/processors/control', request, config);
// 知识库映射配置管理
export const getKnowledgeBaseMappings = (config?: AxiosRequestConfig) =>
  GET<void, KnowledgeBaseMappingConfig[]>('/api/knowledge-mappings', undefined, config);

export const saveKnowledgeBaseMappings = (mappings: KnowledgeBaseMappingRequest, config?: AxiosRequestConfig) =>
  POST<KnowledgeBaseMappingRequest, { message: string }>('/api/knowledge-mappings', mappings, config);

export const deleteKnowledgeBaseMappings = (mappings: KnowledgeBaseMappingRequest, config?: AxiosRequestConfig) =>
  POST<KnowledgeBaseMappingRequest, { message: string }>('/api/knowledge-mappings/delete', mappings, config);
