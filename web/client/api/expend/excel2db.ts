// @/client/api/expend.ts 修改后的文件内容

import { AxiosRequestConfig } from 'axios';
import { ApiResponse, POST } from '..';

// 表结构信息
export interface DbColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
}

export interface DbTableInfo {
  tableName: string;
  columns: DbColumnInfo[];
}

export interface DbInfo {
  dbName: string;
  tables: DbTableInfo[];
}

// Excel处理结果文件信息
export interface DbProcessResultFile {
  fileName: string;
  filePath: string;
  bucket: string;
  totalRows: number;
  processedRows: number;
  failedRows: number;
  success: boolean;
  error?: string;
}

// Excel处理结果
export interface DbProcessResult {
  fileCount: number;
  totalRows: number;
  processedRows: number;
  failedRows: number;
  files: DbProcessResultFile[];
  tableData: {
    key: string;
    column: string;
    type: string;
    mapped: string;
  }[];
  dbInfo: DbInfo;
}

// Excel处理相关接口参数类型
export interface ProcessExcelToDbParams {
  // 数据库配置
  dbType: string;
  dbHost: string;
  dbPort: number; // 新增端口参数
  dbName: string;
  dbUser: string;
  dbPassword: string;
  autoCreate: string;

  // 导入配置
  sheetNames?: string;
  tablePrefix?: string;
  tableMapping?: string;
  chunkSize: string;
  ifExists: string;
  columnMapping?: string;

  // 文件数据，使用FormData方式直接上传
  fileData: FormData;
}

const buildUrl = (baseUrl: string, params: any) => {
  const queryString = Object.keys(params)
    .filter(key => params[key] !== undefined) //
    .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join('&');

  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

/**
 * 处理Excel到数据库的数据导入，直接上传文件并处理
 * @param params 处理参数和配置
 * @returns 处理结果Promise
 */
export const postProcessExcelToDb = ({
  dbType,
  dbHost,
  dbPort, // 新增端口参数
  dbName,
  dbUser,
  dbPassword,
  autoCreate,
  sheetNames,
  tablePrefix,
  tableMapping,
  chunkSize,
  ifExists,
  columnMapping,
  fileData,
  config,
}: ProcessExcelToDbParams & {
  config?: AxiosRequestConfig;
}): Promise<ApiResponse<DbProcessResult, any>> => {
  const baseUrl = '/api/v1/expand/dataprocess/excel2db';

  // 将非敏感参数放入URL查询参数
  const urlParams: Record<string, any> = {
    dbType,
    dbHost,
    dbPort, // 添加端口参数
    dbName,
    dbUser,
    autoCreate,
    chunkSize,
    ifExists,
  };

  // 添加可选的非敏感URL参数
  if (sheetNames) urlParams.sheetNames = sheetNames;
  if (tablePrefix) urlParams.tablePrefix = tablePrefix;
  if (tableMapping) urlParams.tableMapping = tableMapping;
  if (columnMapping) urlParams.columnMapping = columnMapping;

  // 使用buildUrl工具函数构建带有查询参数的URL
  const url = buildUrl(baseUrl, urlParams);

  // 将敏感信息添加到FormData中（而不是URL中）
  fileData.append('dbPassword', dbPassword);

  return POST<FormData, DbProcessResult>(url, fileData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...config,
  });
};
