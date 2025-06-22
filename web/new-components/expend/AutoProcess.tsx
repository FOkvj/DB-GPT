import { apiInterceptors } from '@/client/api';
import {
  FTPServerConfig,
  ProcessedFileResponse,
  ScanConfigResponse,
  StatisticsResponse,
  TaskDetailResponse,
  addFTPServer,
  clearProcessedFiles,
  deleteScanConfig,
  executeScanAsync,
  getProcessedFiles,
  getScanConfigs,
  getStatistics,
  getTaskDetail,
  testScanConfigs,
  testFTPConnection,
  getFileTypes,
  addFileType,
  updateFileType,
  updateScanConfig,
  updateTask,
} from '@/client/api/expend/file-scan';
// 导入管道控制API
import {
  FileInfo,
  FileStatus,
  PipelineStatus,
  controlPipeline,
  deletePipelineFiles,
  getPipelineFiles,
  getPipelineStatus,
} from '@/client/api/expend/auto-pipeline';
import {
  CaretRightOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FileOutlined,
  FilterOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SearchOutlined,
  SettingOutlined,
  SortAscendingOutlined,
  SortDescendingOutlined,
  SoundOutlined,
  SyncOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  Collapse,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import { useCallback, useEffect, useState } from 'react';

const { Option } = Select;
const { Title, Text } = Typography;
const { confirm } = Modal;
const { Panel } = Collapse;

// 时间单位配置
const TIME_UNITS = [
  { label: '秒', value: 'seconds', multiplier: 1 },
  { label: '分钟', value: 'minutes', multiplier: 60 },
  { label: '小时', value: 'hours', multiplier: 3600 },
];

const AutoProcessModule = () => {
  // 状态管理
  const [scanConfigs, setScanConfigs] = useState<ScanConfigResponse[]>([]);
  const [ftpForm] = Form.useForm();
  const [taskConfigForm] = Form.useForm();
  const [statistics, setStatistics] = useState<StatisticsResponse | null>(null);
  const [processedFiles, setProcessedFiles] = useState<ProcessedFileResponse[]>([]);
  const [selectedFtpConfig, setSelectedFtpConfig] = useState<ScanConfigResponse | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [cleanupTimer, setCleanupTimer] = useState(24);
  const [activePanel, setActivePanel] = useState(['1', '2', '3']);
  const [loading, setLoading] = useState(false);
  const [isAddMode, setIsAddMode] = useState(false);
  const [addFtpForm] = Form.useForm();
  const [editFtpForm] = Form.useForm();
  const [taskDetail, setTaskDetail] = useState<TaskDetailResponse | null>(null);
  const [timeUnit, setTimeUnit] = useState<string>('seconds');
  const [timeValue, setTimeValue] = useState<number>(10);
  const [taskConfigVisible, setTaskConfigVisible] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(1000);

  // 管道状态管理
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [pipelineFiles, setPipelineFiles] = useState<FileInfo[]>([]);
  const [pipelineFilesLoading, setPipelineFilesLoading] = useState(false);
  const [selectedFileKeys, setSelectedFileKeys] = useState<string[]>([]);

  // 弹窗状态
  const [scanConfigModalVisible, setScanConfigModalVisible] = useState(false);
  const [configCenterModalVisible, setConfigCenterModalVisible] = useState(false);

  // 语音加工结果自动刷新
  const [pipelineAutoRefresh, setPipelineAutoRefresh] = useState(false);

  // 语音配置
  const [voiceConfig, setVoiceConfig] = useState({
    enabled: false,
    language: 'auto',
    batchSize: 10,
  });

  // 统一的自动加工控制
  const [autoProcessEnabled, setAutoProcessEnabled] = useState(false);

  // 语音加工结果过滤和排序状态
  const [pipelineFilters, setPipelineFilters] = useState({
    status: '',
    processor: '',
    nameSearch: '',
  });
  const [pipelineSorting, setPipelineSorting] = useState({
    field: 'last_processed',
    order: 'desc',
  });

  const [globalFileTypes, setGlobalFileTypes] = useState<FileTypeResponse[]>([]);
  const [originalFileTypes, setOriginalFileTypes] = useState<FileTypeResponse[]>([]); // 保存原始数据用于对比
  const [fileTypeModalVisible, setFileTypeModalVisible] = useState(false);
  const [fileTypeForm] = Form.useForm();

  const handleOpenFileTypeModal = () => {
    setFileTypeModalVisible(true);
    // 延迟设置表单值，确保弹窗完全打开
    setTimeout(() => {
      fileTypeForm.setFieldsValue({
        fileTypes: globalFileTypes.filter(type => type.enabled).map(type => type.extension)
      });
    }, 100);
  };

// 加载全局文件类型配置
const loadGlobalFileTypes = useCallback(async () => {
  try {
    const [error, data] = await apiInterceptors(getFileTypes(false)); // 获取所有文件类型，包括禁用的
    if (!error && data) {
      setGlobalFileTypes(data);
      setOriginalFileTypes(data.map(item => ({ ...item }))); // 深拷贝原始数据
    }
  } catch (error) {
    console.error('加载文件类型配置失败:', error);
    // 使用默认值
    const defaultTypes: FileTypeResponse[] = [
      { extension: '.wav', enabled: true, description: 'WAV 音频文件' },
      { extension: '.mp3', enabled: true, description: 'MP3 音频文件' },
      { extension: '.txt', enabled: true, description: 'TXT 文本文件' },
      { extension: '.pdf', enabled: true, description: 'PDF 文档文件' },
    ];
    setGlobalFileTypes(defaultTypes);
    setOriginalFileTypes(defaultTypes.map(item => ({ ...item })));
  }
}, []);

// 保存全局文件类型配置
// 智能保存全局文件类型配置
const handleSaveFileTypes = async (values: any) => {
  try {
    setLoading(true);
    const selectedExtensions: string[] = values.fileTypes || [];
    
    // 预定义的文件类型配置
    const fileTypeDefinitions: Record<string, { description: string; category?: string }> = {
      '.wav': { description: 'WAV 音频文件', category: 'audio' },
      '.mp3': { description: 'MP3 音频文件', category: 'audio' },
      '.mp4': { description: 'MP4 视频文件', category: 'video' },
      '.flac': { description: 'FLAC 音频文件', category: 'audio' },
      '.aac': { description: 'AAC 音频文件', category: 'audio' },
      '.txt': { description: 'TXT 文本文件', category: 'text' },
      '.doc': { description: 'DOC 文档文件', category: 'document' },
      '.docx': { description: 'DOCX 文档文件', category: 'document' },
      '.pdf': { description: 'PDF 文档文件', category: 'document' },
      '.xlsx': { description: 'XLSX 表格文件', category: 'document' },
      '.ppt': { description: 'PPT 演示文稿', category: 'document' },
      '.pptx': { description: 'PPTX 演示文稿', category: 'document' },
      '.jpg': { description: 'JPG 图片文件', category: 'image' },
      '.png': { description: 'PNG 图片文件', category: 'image' },
    };

    const operations = [];
    
    // 1. 处理原有的文件类型
    for (const originalType of originalFileTypes) {
      const isCurrentlySelected = selectedExtensions.includes(originalType.extension);
      
      if (originalType.enabled !== isCurrentlySelected) {
        // 状态发生变化，需要更新
        const updateData: FileTypeModel = {
          extension: originalType.extension,
          enabled: isCurrentlySelected,
          description: originalType.description,
        };
        
        operations.push(
          apiInterceptors(updateFileType(originalType.extension, updateData))
        );
      }
    }
    
    // 2. 处理新增的文件类型
    const originalExtensions = originalFileTypes.map(t => t.extension);
    const newExtensions = selectedExtensions.filter(ext => !originalExtensions.includes(ext));
    
    for (const extension of newExtensions) {
      const definition = fileTypeDefinitions[extension];
      const newFileType: FileTypeModel = {
        extension,
        enabled: true,
        description: definition?.description || `${extension} 文件`,
        category: definition?.category,
      };
      
      operations.push(
        apiInterceptors(addFileType(newFileType))
      );
    }
    
    // 3. 执行所有操作
    if (operations.length > 0) {
      const results = await Promise.all(operations);
      const errors = results.filter(([error]) => error);
      
      if (errors.length === 0) {
        message.success(`文件类型配置已保存 (${operations.length}个更新)`);
        setFileTypeModalVisible(false);
        await loadGlobalFileTypes(); // 重新加载最新数据
        loadScanConfigs(); // 重新加载扫描配置以反映变化
      } else {
        message.error(`保存失败: ${errors.length}个操作出错`);
        console.error('保存文件类型配置时出错:', errors);
      }
    } else {
      message.info('没有检测到配置变化');
      setFileTypeModalVisible(false);
    }
    
  } catch (error) {
    console.error('保存文件类型配置失败:', error);
    message.error('保存文件类型配置失败');
  } finally {
    setLoading(false);
  }
};

  // 测试单个FTP配置连接
// 通用的测试单个FTP配置函数
const handleTestSingleFtpConfig = async (config: ScanConfigResponse | any, isFormValues: boolean = false) => {
  try {
    setLoading(true);

    let testConfig;
    let configName;

    if (isFormValues) {
      // 来自表单的数据
      testConfig = {
        name: config.name,
        host: config.ftpHost,
        username: config.ftpUser,
        password: config.ftpPassword,
        port: config.ftpPort || 21,
        remote_dir: config.scanPath || '/',
      };
      configName = config.name || '新配置';
    } else {
      // 来自已保存的配置
      testConfig = {
        name: config.name,
        host: config.config.host,
        username: config.config.username,
        password: config.config.password,
        port: config.config.port || 21,
        remote_dir: config.config.remote_dir || '/',
      };
      configName = config.name;
    }

    console.log('测试FTP连接配置:', testConfig);

    const [error, data] = await apiInterceptors(testFTPConnection(testConfig));
    
    if (!error && data) {
      if (!data.error) {
        // 成功情况的Modal.info
        Modal.info({
          title: `FTP连接测试结果 - ${configName}`,
          width: 700,
          content: (
            <div>
              <div style={{ marginBottom: 16 }}>
                <Text strong>连接信息:</Text>
                <div style={{ marginLeft: 16, marginTop: 8 }}>
                  <div>主机: {data.host}:{data.port}</div>
                  <div>用户: {data.username}</div>
                  <div style={{ color: '#52c41a' }}>状态: 连接成功</div>
                </div>
              </div>

              {data.remote_dir_status && (
                <div style={{ marginBottom: 16 }}>
                  <Text strong>远程目录状态:</Text>
                  <div style={{ 
                    marginLeft: 16, 
                    marginTop: 8,
                    color: data.remote_dir_status.includes('成功') ? '#52c41a' : '#ff4d4f'
                  }}>
                    {data.remote_dir_status}
                  </div>
                </div>
              )}

              {Array.isArray(data.root_files) && data.root_files.length > 0 && (
                <div>
                  <Text strong>根目录文件 (前20个):</Text>
                  <div style={{ 
                    marginLeft: 16, 
                    marginTop: 8,
                    maxHeight: 200,
                    overflow: 'auto',
                    backgroundColor: '#f5f5f5',
                    padding: 8,
                    borderRadius: 4,
                    fontSize: 12,
                    fontFamily: 'monospace'
                  }}>
                    {data.root_files.map((file, index) => (
                      <div key={index}>{file}</div>
                    ))}
                  </div>
                </div>
              )}

              {typeof data.root_files === 'string' && (
                <div>
                  <Text strong>文件列表错误:</Text>
                  <div style={{ 
                    marginLeft: 16, 
                    marginTop: 8,
                    color: '#ff4d4f'
                  }}>
                    {data.root_files}
                  </div>
                </div>
              )}
            </div>
          ),
        });

        message.success('FTP连接测试成功');
      } else {
        // 失败情况的Modal.info
        Modal.info({
          title: `FTP连接测试结果 - ${configName}`,
          width: 700,
          content: (
            <div>
              <div style={{ marginBottom: 16 }}>
                <Text strong>连接信息:</Text>
                <div style={{ marginLeft: 16, marginTop: 8 }}>
                  <div>主机: {testConfig.host}:{testConfig.port}</div>
                  <div>用户: {testConfig.username}</div>
                  <div style={{ color: '#ff4d4f' }}>状态: 连接失败</div>
                </div>
              </div>

              <div>
                <Text strong>错误信息:</Text>
                <div style={{ 
                  marginLeft: 16, 
                  marginTop: 8,
                  color: '#ff4d4f'
                }}>
                  {data.message || data.error || '连接失败'}
                </div>
              </div>
            </div>
          ),
        });

        message.error(`FTP连接测试失败: ${data.message || data.error}`);
      }
    } else {
      // 请求失败的Modal.info
      Modal.info({
        title: `FTP连接测试结果 - ${configName}`,
        width: 700,
        content: (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Text strong>连接信息:</Text>
              <div style={{ marginLeft: 16, marginTop: 8 }}>
                <div>主机: {testConfig.host}:{testConfig.port}</div>
                <div>用户: {testConfig.username}</div>
                <div style={{ color: '#ff4d4f' }}>状态: 连接失败</div>
              </div>
            </div>

            <div>
              <Text strong>错误信息:</Text>
              <div style={{ 
                marginLeft: 16, 
                marginTop: 8,
                color: '#ff4d4f'
              }}>
                {error?.message || '连接测试失败'}
              </div>
            </div>
          </div>
        ),
      });

      message.error('FTP连接测试失败');
    }
  } catch (error) {
    console.error('测试FTP连接时出错:', error);
    
    // 异常情况的Modal.info
    Modal.info({
      title: `FTP连接测试结果 - ${configName}`,
      width: 700,
      content: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Text strong>连接信息:</Text>
            <div style={{ marginLeft: 16, marginTop: 8 }}>
              <div>主机: {testConfig.host}:{testConfig.port}</div>
              <div>用户: {testConfig.username}</div>
              <div style={{ color: '#ff4d4f' }}>状态: 连接异常</div>
            </div>
          </div>

          <div>
            <Text strong>错误信息:</Text>
            <div style={{ 
              marginLeft: 16, 
              marginTop: 8,
              color: '#ff4d4f'
            }}>
              连接测试出现异常
            </div>
          </div>
        </div>
      ),
    });

    message.error('测试连接时出现异常');
  } finally {
    setLoading(false);
  }
};

  // 加载数据的函数
  const loadScanConfigs = useCallback(async () => {
    const [error, data] = await apiInterceptors(getScanConfigs());
    if (!error && data) {
      setScanConfigs(data);
    }
  }, []);

  const loadStatistics = useCallback(async () => {
    const [error, data] = await apiInterceptors(getStatistics());
    if (!error && data) {
      setStatistics(data);
    }
  }, []);

  const loadProcessedFiles = useCallback(async () => {
    const [error, data] = await apiInterceptors(getProcessedFiles(100));
    if (!error && data) {
      setProcessedFiles(data);
    }
  }, []);

  const loadTaskConfig = useCallback(async () => {
    const [error, data] = await apiInterceptors(getTaskDetail('file_scan'));
    if (!error && data) {
      setTaskDetail(data);
    } else {
      setTaskDetail(null);
    }
  }, []);

  // 加载管道文件列表
  const loadPipelineFiles = useCallback(async () => {
    setPipelineFilesLoading(true);
    const [error, data] = await apiInterceptors(getPipelineFiles());
    if (!error && data) {
      setPipelineFiles(data);
    }
    setPipelineFilesLoading(false);
  }, []);

  // 加载管道状态
  const loadPipelineStatus = useCallback(async () => {
    const [error, data] = await apiInterceptors(getPipelineStatus());
    if (!error && data) {
      setPipelineStatus(data);
      setAutoProcessEnabled(data.running);
      setVoiceConfig(prev => ({ ...prev, enabled: data.running }));
    }
  }, []);

  // 初始化加载数据
  useEffect(() => {
    loadScanConfigs();
    loadStatistics();
    loadProcessedFiles();
    loadTaskConfig();
    loadPipelineStatus();
    loadPipelineFiles();
    loadGlobalFileTypes();
  }, [loadScanConfigs, loadStatistics, loadProcessedFiles, loadTaskConfig, loadPipelineStatus, loadPipelineFiles, loadGlobalFileTypes]);

  // 已处理文件自动刷新效果
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (autoRefresh) {
      intervalId = setInterval(() => {
        loadProcessedFiles();
        loadStatistics();
      }, refreshInterval);
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [autoRefresh, refreshInterval, loadProcessedFiles, loadStatistics]);

  // 语音加工结果自动刷新效果
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (pipelineAutoRefresh) {
      intervalId = setInterval(() => {
        loadPipelineStatus();
        loadPipelineFiles();
      }, refreshInterval);
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [pipelineAutoRefresh, refreshInterval, loadPipelineStatus, loadPipelineFiles]);

  useEffect(() => {
    if (taskConfigVisible && taskDetail) {
      taskConfigForm.resetFields();
      const apiSeconds = taskDetail.config.interval_seconds || 10;
      const apiEnabled = taskDetail.running || false;

      taskConfigForm.setFieldsValue({
        enabled: apiEnabled,
        timeValue: apiSeconds,
        timeUnit: 'seconds',
      });

      setTimeUnit('seconds');
      setTimeValue(apiSeconds);
    }
  }, [taskConfigVisible, taskDetail, taskConfigForm]);

  // 管道控制函数
  const handlePipelineControl = async (action: 'start' | 'stop') => {
    try {
      setPipelineLoading(true);
      const [error, data] = await apiInterceptors(controlPipeline({ action }));
      if (!error && data) {
        message.success(`自动加工管道已${action === 'start' ? '启动' : '停止'}`);
        await loadPipelineStatus();
      }
    } catch (error) {
      console.error('控制管道失败:', error);
      message.error(`${action === 'start' ? '启动' : '停止'}自动加工管道失败`);
    } finally {
      setPipelineLoading(false);
    }
  };

  // 统一的自动加工控制处理
  const handleAutoProcessToggle = async (checked: boolean) => {
    await handlePipelineControl(checked ? 'start' : 'stop');
  };

  // 更新定时任务配置
  const handleUpdateTaskConfig = async (values: any) => {
    try {
      setLoading(true);
      const unit = TIME_UNITS.find(u => u.value === values.timeUnit);
      const intervalSeconds = values.timeValue * (unit?.multiplier || 1);

      const requestData = {
        enabled: values.enabled,
        interval_seconds: intervalSeconds,
      };

      const [error] = await apiInterceptors(updateTask('file_scan', requestData));

      if (!error) {
        message.success('定时任务配置更新成功');
        setTaskConfigVisible(false);
        await loadTaskConfig();
      }
    } catch (error) {
      console.error('更新定时任务配置失败:', error);
      message.error('更新定时任务配置失败');
    } finally {
      setLoading(false);
    }
  };

  // 添加FTP配置弹窗处理
  const handleShowAddFtpModal = () => {
    setIsAddMode(true);
    setSelectedFtpConfig({} as ScanConfigResponse);
    addFtpForm.resetFields();
  };

  // 处理添加FTP配置
// 通用的FTP配置保存函数
const handleSaveFtpConfig = async (values: any) => {
  try {
    setLoading(true);

    const ftpConfig: FTPServerConfig = {
      name: values.name || (isAddMode ? `FTP-${Date.now()}` : selectedFtpConfig?.name || `FTP-${Date.now()}`),
      host: values.ftpHost,
      username: values.ftpUser,
      password: values.ftpPassword,
      port: values.ftpPort || 21,
      remote_dir: values.scanPath || '/',
      enabled: values.enabled !== undefined ? values.enabled : true,
    };

    const [error] = await apiInterceptors(addFTPServer(ftpConfig));
    if (!error) {
      message.success(`FTP配置${isAddMode ? '添加' : '保存'}成功`);
      setSelectedFtpConfig(null);
      setIsAddMode(false);
      loadScanConfigs();
    }
  } catch (error) {
    console.error(`${isAddMode ? '添加' : '保存'}FTP配置失败:`, error);
    message.error(`${isAddMode ? '添加' : '保存'}FTP配置失败`);
  } finally {
    setLoading(false);
  }
};

  // 处理编辑FTP配置
  const handleEditFtpConfig = (config: ScanConfigResponse) => {
    setIsAddMode(false);
    setSelectedFtpConfig(config);

    setTimeout(() => {
      editFtpForm.setFieldsValue({
        name: config.name,
        ftpHost: config.config?.host,
        ftpPort: config.config?.port || 21,
        scanPath: config.config?.remote_dir || '/',
        ftpUser: config.config?.username,
        ftpPassword: config.config?.password,
        fileTypes: config.config?.file_types || ['.wav', '.mp3', '.txt', '.pdf'],
        enabled: config.enabled,
      });
    }, 100);
  };

  // 切换定时任务启用状态
  const handleToggleTask = async (enabled: boolean) => {
    try {
      setLoading(true);

      const currentIntervalSeconds = taskDetail?.config.interval_seconds || 10;

      const [error] = await apiInterceptors(
        updateTask('file_scan', {
          enabled,
          interval_seconds: currentIntervalSeconds,
        }),
      );

      if (!error) {
        message.success(`定时扫描已${enabled ? '启用' : '停用'}`);
        await loadTaskConfig();
      }
    } catch (error) {
      console.error('切换定时任务状态失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderTaskStatus = () => {
    const isEnabled = taskDetail?.config.enabled || false;
    const isRunning = taskDetail?.running || false;

    if (!isEnabled) {
      return <Badge status='default' text='已停用' />;
    }

    if (isRunning) {
      return <Badge status='processing' text='运行中' />;
    }

    return <Badge status='warning' text='已启用但未运行' />;
  };

  // 渲染管道状态
  const renderPipelineStatus = () => {
    if (!pipelineStatus) return <Badge status='default' text='未知状态' />;

    const { running, queue_size, worker_count } = pipelineStatus;

    if (running) {
      return (
        <Space>
          <Badge status='processing' text='运行中' />
          <Text type='secondary' style={{ fontSize: 12 }}>
            (队列: {queue_size || 0}, 工作线程: {worker_count || 0})
          </Text>
        </Space>
      );
    }

    return <Badge status='default' text='已停止' />;
  };


  const handleTestConnection = async () => {
    try {
      setLoading(true);
      const [error, data] = await apiInterceptors(testScanConfigs());
      if (!error && data) {
        const { test_results } = data;
        let successCount = 0;
        let errorCount = 0;

        test_results.forEach(result => {
          if (result.status === 'success') {
            successCount++;
          } else {
            errorCount++;
          }
        });

        if (errorCount === 0) {
          message.success(`所有配置测试通过 (${successCount}个)`);
        } else {
          message.warning(`${successCount}个配置正常，${errorCount}个配置异常`);
        }

        Modal.info({
          title: '连接测试结果',
          width: 600,
          content: (
            <div>
              {test_results.map((result, index) => (
                <div key={index} style={{ marginBottom: 8 }}>
                  <Tag color={result.status === 'success' ? 'green' : 'red'}>
                    {result.name} ({result.type})
                  </Tag>
                  <span style={{ marginLeft: 8 }}>{result.message}</span>
                </div>
              ))}
            </div>
          ),
        });
      }
    } catch (error) {
      console.error('测试连接失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleScanStart = async () => {
    const enabledConfigs = scanConfigs.filter(c => c.enabled);
    if (enabledConfigs.length === 0) {
      message.warning('请先启用至少一个扫描配置才能开始扫描');
      return;
    }

    try {
      setIsScanning(true);
      const [error] = await apiInterceptors(executeScanAsync());
      if (!error) {
        message.success('扫描任务已启动');
        const interval = setInterval(() => {
          loadStatistics();
          loadProcessedFiles();
        }, 2000);

        setTimeout(() => {
          clearInterval(interval);
          setIsScanning(false);
          message.info('扫描任务执行完成');
        }, 10000);
      }
    } catch (error) {
      console.error('启动扫描失败:', error);
      setIsScanning(false);
    }
  };

  const handleScanStop = () => {
    setIsScanning(false);
    message.info('已停止扫描');
  };

  const handleToggleScanConfig = async (config: ScanConfigResponse) => {
    try {
      const [error] = await apiInterceptors(updateScanConfig(config.name, { enabled: !config.enabled }));
      if (!error) {
        message.success(`配置 ${config.name} 已${!config.enabled ? '启用' : '停用'}`);
        loadScanConfigs();
      }
    } catch (error) {
      console.error('更新扫描配置失败:', error);
    }
  };

  const handleDeleteScanConfig = (config: ScanConfigResponse) => {
    confirm({
      title: '确认删除',
      content: `确定要删除扫描配置 "${config.name}" 吗？`,
      onOk: async () => {
        try {
          const [error] = await apiInterceptors(deleteScanConfig(config.name));
          if (!error) {
            message.success('扫描配置删除成功');
            loadScanConfigs();
          }
        } catch (error) {
          console.error('删除扫描配置失败:', error);
        }
      },
    });
  };

  // 语音事件处理
  const handleVoiceToggle = (checked: boolean) => {
    setVoiceConfig(prev => ({ ...prev, enabled: checked }));
    message.success(checked ? '语音自动加工已启用' : '语音自动加工已停用');
  };

  // 处理文件下载
  const handleDownloadFile = (file: FileInfo) => {
    message.info(`开始下载 ${file.name}`);
    // 实际应用中这里应该调用下载API
    // window.open(`/api/files/download/${encodeURIComponent(file.path)}`, '_blank');
  };

  // 处理文件删除
  const handleDeletePipelineFiles = (filePaths: string[]) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除 ${filePaths.length} 个文件吗？此操作不可恢复。`,
      onOk: async () => {
        try {
          setPipelineFilesLoading(true);
          const [error, data] = await apiInterceptors(deletePipelineFiles({ file_paths: filePaths }));
          if (!error && data) {
            message.success(`成功删除 ${data.success_count} 个文件`);
            setSelectedFileKeys([]);
            await loadPipelineFiles();
          }
        } catch (error) {
          console.error('删除文件失败:', error);
          message.error('删除文件失败');
        } finally {
          setPipelineFilesLoading(false);
        }
      },
    });
  };

  // 处理知识库跳转
  const handleKnowledgeJump = (file: FileInfo) => {
    if (file.status === FileStatus.COMPLETED && file.processors.includes('knowledge_processor')) {
      window.open('/construct/knowledge', '_blank');
      message.success(`已打开知识库管理页面`);
    } else {
      message.warning('文件未完成知识库构建，无法跳转');
    }
  };

  // 过滤和排序处理
  const getFilteredAndSortedFiles = () => {
    let filteredFiles = [...pipelineFiles];

    // 应用过滤器
    if (pipelineFilters.status) {
      filteredFiles = filteredFiles.filter(file => file.status === pipelineFilters.status);
    }
    if (pipelineFilters.processor) {
      filteredFiles = filteredFiles.filter(file => file.processors.includes(pipelineFilters.processor));
    }
    if (pipelineFilters.nameSearch) {
      filteredFiles = filteredFiles.filter(file => 
        file.name.toLowerCase().includes(pipelineFilters.nameSearch.toLowerCase())
      );
    }

    // 应用排序
    filteredFiles.sort((a, b) => {
      let aValue, bValue;
      
      switch (pipelineSorting.field) {
        case 'name':
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
          break;
        case 'size':
          aValue = a.size;
          bValue = b.size;
          break;
        case 'status':
          aValue = a.status;
          bValue = b.status;
          break;
        case 'last_processed':
          aValue = a.last_processed ? new Date(a.last_processed).getTime() : 0;
          bValue = b.last_processed ? new Date(b.last_processed).getTime() : 0;
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return pipelineSorting.order === 'asc' ? -1 : 1;
      if (aValue > bValue) return pipelineSorting.order === 'asc' ? 1 : -1;
      return 0;
    });

    return filteredFiles;
  };

  // 重置过滤器
  const resetFilters = () => {
    setPipelineFilters({
      status: '',
      processor: '',
      nameSearch: '',
    });
    message.info('已重置所有过滤条件');
  };

  // 获取文件状态显示
  const getFileStatusDisplay = (status: FileStatus) => {
    const statusConfig = {
      [FileStatus.PENDING]: { color: 'default', text: '待处理' },
      [FileStatus.PROCESSING]: { color: 'processing', text: '处理中' },
      [FileStatus.COMPLETED]: { color: 'success', text: '已完成' },
      [FileStatus.FAILED]: { color: 'error', text: '失败' },
      [FileStatus.SKIPPED]: { color: 'warning', text: '已跳过' },
    };
    return statusConfig[status] || statusConfig[FileStatus.PENDING];
  };

  const handleClearProcessedFiles = () => {
    confirm({
      title: '确认清空',
      content: '确定要清空所有已处理文件记录吗？这将重置扫描状态。',
      onOk: async () => {
        try {
          const [error] = await apiInterceptors(clearProcessedFiles());
          if (!error) {
            message.success('已清空所有处理记录');
            loadProcessedFiles();
            loadStatistics();
          }
        } catch (error) {
          console.error('清空处理记录失败:', error);
        }
      },
    });
  };

  // 全选/反选处理
  const handleSelectAll = (checked: boolean) => {
    const filteredFiles = getFilteredAndSortedFiles();
    if (checked) {
      setSelectedFileKeys(filteredFiles.map(file => file.path));
    } else {
      setSelectedFileKeys([]);
    }
  };

  // 单个文件选择处理
  const handleFileSelect = (filePath: string, checked: boolean) => {
    if (checked) {
      setSelectedFileKeys([...selectedFileKeys, filePath]);
    } else {
      setSelectedFileKeys(selectedFileKeys.filter(key => key !== filePath));
    }
  };

  // 批量下载处理
  const handleBatchDownload = () => {
    if (selectedFileKeys.length === 0) {
      message.warning('请先选择要下载的文件');
      return;
    }
    selectedFileKeys.forEach(path => {
      const file = pipelineFiles.find(f => f.path === path);
      if (file) handleDownloadFile(file);
    });
  };

  // 批量删除处理
  const handleBatchDelete = () => {
    if (selectedFileKeys.length === 0) {
      message.warning('请先选择要删除的文件');
      return;
    }
    handleDeletePipelineFiles(selectedFileKeys);
  };

  // 扫描配置列表列配置
// 修改 scanConfigColumns 中的操作列
const scanConfigColumns = [
  {
    title: '配置名称',
    dataIndex: 'name',
    key: 'name',
    width: '20%',
  },
  {
    title: '类型',
    dataIndex: 'type',
    key: 'type',
    width: '10%',
    render: (type: string) => <Tag color={type === 'ftp' ? 'blue' : 'green'}>{type === 'ftp' ? 'FTP' : '本地'}</Tag>,
  },
  {
    title: '配置信息',
    dataIndex: 'config',
    key: 'config',
    width: '25%',
    render: (config: any, record: ScanConfigResponse) => {
      if (record.type === 'ftp') {
        return `${config.host}:${config.port || 21}${config.remote_dir || '/'}`;
      }
      return config.path || '-';
    },
  },
  {
    title: '文件类型',
    dataIndex: 'config',
    key: 'file_types',
    width: '25%',
    render: (config: any) => {
      // 显示启用的全局文件类型配置
      const enabledFileTypes = globalFileTypes.filter(type => type.enabled);
      if (enabledFileTypes.length === 0) return '-';
  
      return (
        <div>
          {enabledFileTypes.slice(0, 3).map((type) => (
            <Tag key={type.extension} size='small' style={{ marginBottom: 2 }}>
              {type.extension}
            </Tag>
          ))}
          {enabledFileTypes.length > 3 && (
            <Tooltip title={enabledFileTypes.slice(3).map(t => t.extension).join(', ')}>
              <Tag size='small' style={{ marginBottom: 2 }}>
                +{enabledFileTypes.length - 3}
              </Tag>
            </Tooltip>
          )}
          <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
            (全局配置: {enabledFileTypes.length}个)
          </div>
        </div>
      );
    },
  },
  {
    title: '状态',
    dataIndex: 'enabled',
    key: 'enabled',
    width: '10%',
    render: (enabled: boolean, record: ScanConfigResponse) => (
      <Switch size='small' checked={enabled} onChange={() => handleToggleScanConfig(record)} />
    ),
  },
  {
    title: '操作',
    key: 'action',
    width: '10%',
    render: (_: any, record: ScanConfigResponse) => (
      <Space size='small'>
        {/* 新增测试按钮，只对FTP配置显示 */}
        {record.type === 'ftp' && (
          <Tooltip title='测试连接'>
  <Button 
    size='small' 
    type='text' 
    icon={<SettingOutlined />} 
    onClick={() => handleTestSingleFtpConfig(record, false)} // false表示来自已保存的配置
    loading={loading}
  />
</Tooltip>
        )}
        <Tooltip title='编辑'>
          <Button size='small' type='text' icon={<EditOutlined />} onClick={() => handleEditFtpConfig(record)} />
        </Tooltip>
        <Tooltip title='删除'>
          <Button
            size='small'
            type='text'
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteScanConfig(record)}
          />
        </Tooltip>
      </Space>
    ),
  },
];

  // 已处理文件列配置
  const processedFileColumns = [
    {
      title: '文件名',
      dataIndex: 'file_name',
      key: 'file_name',
      width: '500px',
      render: (text: string) => (
        <Space>
          <FileOutlined />
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source_path',
      key: 'source_path',
      width: '400px',
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: '400px',
      render: (size: number) => {
        if (size < 1024) return `${size}B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`;
        return `${(size / 1024 / 1024).toFixed(1)}MB`;
      },
    },
    {
      title: '扫描时间',
      dataIndex: 'processed_at',
      key: 'processed_at',
      width: '400px',
    },
    {
      title: '操作',
      key: 'action',
      width: '400px',
      render: (_: any, record: ProcessedFileResponse) => (
        <Space size='small'>
          <Tooltip title='下载'>
            <Button
              size='small'
              type='text'
              icon={<DownloadOutlined />}
              onClick={() => message.info(`开始下载 ${record.file_name}`)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  // 语音加工结果列配置
  const pipelineFileColumns = [
    {
      title: (
        <Checkbox
          checked={selectedFileKeys.length === getFilteredAndSortedFiles().length && getFilteredAndSortedFiles().length > 0}
          indeterminate={selectedFileKeys.length > 0 && selectedFileKeys.length < getFilteredAndSortedFiles().length}
          onChange={(e) => handleSelectAll(e.target.checked)}
        >
          文件名
        </Checkbox>
      ),
      dataIndex: 'name',
      key: 'name',
      width: '500px',
      render: (text: string, record: FileInfo) => (
        <Space>
          <Checkbox
            checked={selectedFileKeys.includes(record.path)}
            onChange={(e) => handleFileSelect(record.path, e.target.checked)}
          />
          <FileOutlined />
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: '400px',
      render: (size: number) => {
        if (size < 1024) return `${size}B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`;
        return `${(size / 1024 / 1024).toFixed(1)}MB`;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: '400px',
      render: (status: FileStatus) => {
        const statusDisplay = getFileStatusDisplay(status);
        return <Badge status={statusDisplay.color} text={statusDisplay.text} />;
      },
    },
    {
      title: '处理器',
      dataIndex: 'processors',
      key: 'processors',
      width: '400px',
      render: (processors: string[], record: FileInfo) => (
        <div>
          {processors.map((processor) => {
            const isKnowledgeProcessor = processor === 'knowledge_processor';
            const canJump = isKnowledgeProcessor && record.status === FileStatus.COMPLETED;
            
            return (
              <Tag 
                key={processor} 
                size='small' 
                style={{ 
                  marginBottom: 2, 
                  cursor: canJump ? 'pointer' : 'default',
                  backgroundColor: isKnowledgeProcessor ? (canJump ? '#f6ffed' : '#f5f5f5') : undefined,
                  borderColor: isKnowledgeProcessor ? (canJump ? '#52c41a' : '#d9d9d9') : undefined,
                  color: isKnowledgeProcessor ? (canJump ? '#52c41a' : '#666') : undefined,
                }}
                onClick={() => {
                  if (canJump) {
                    handleKnowledgeJump(record);
                  }
                }}
                icon={isKnowledgeProcessor ? <DatabaseOutlined /> : undefined}
              >
                {processor === 'audio_to_text' ? '语音转换' : 
                 processor === 'knowledge_processor' ? '知识库' : processor}
                {canJump && ' ↗'}
              </Tag>
            );
          })}
        </div>
      ),
    },
    {
      title: '处理时间',
      dataIndex: 'last_processed',
      key: 'last_processed',
      width: '400px',
      render: (time: string) => time ? new Date(time).toLocaleString() : '-',
    },
  ];

  return (
    <div style={{ padding: '0 24px' }}>
      <Title level={2} style={{ marginBottom: 24 }}>
        <ToolOutlined /> 自动化加工模块
      </Title>

      <Space direction="vertical" style={{ width: '100%' }} size={24}>
        {/* 已处理文件列表 - 上半部分 */}
        <Card
          title={
            <Space>
              <CheckCircleOutlined />
              <span>已扫描文件列表</span>
              <Tag color='green'>{processedFiles.length} 个文件</Tag>
            </Space>
          }
          size='small'
          extra={
            <Space>
              <Button
                size='small'
                icon={<SettingOutlined />}
                onClick={() => setScanConfigModalVisible(true)}
              >
                扫描配置
              </Button>
              <Text type='secondary' style={{ fontSize: 12 }}>
                <ClockCircleOutlined /> 最后扫描: {statistics?.last_scan_time || '未扫描'}
              </Text>
            </Space>
          }
          style={{ minHeight: 400 }}
        >
          {/* 定时扫描任务控制 */}
          <div style={{ marginBottom: 16, padding: '12px 16px', backgroundColor: '#f5f5f5', borderRadius: 4 }}>
            <Row justify='space-between' align='middle'>
              <Col>
                <Space>
                  <ClockCircleOutlined />
                  <Text strong>定时扫描任务</Text>
                  {renderTaskStatus()}
                </Space>
              </Col>
              <Col>
                <Space>
                  <Switch
                    size='small'
                    checked={taskDetail?.running || false}
                    onChange={handleToggleTask}
                    loading={loading}
                    checkedChildren='运行'
                    unCheckedChildren='停止'
                  />
                  <Button
                    size='small'
                    type='link'
                    onClick={() => setTaskConfigVisible(true)}
                    style={{ padding: 0 }}
                  >
                    设置
                  </Button>
                </Space>
              </Col>
            </Row>
            {taskDetail?.config.enabled && taskDetail?.config.interval_seconds && (
              <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
                <Space split={<span style={{ color: '#d9d9d9' }}>|</span>}>
                  <span>间隔: {taskDetail.config.interval_seconds} 秒</span>
                  {taskDetail?.next_run && <span>下次运行: {new Date(taskDetail.next_run).toLocaleString()}</span>}
                </Space>
              </div>
            )}
          </div>
          
          {/* 集成的文件操作栏 */}
          <div style={{ marginBottom: 16, padding: '12px 16px', backgroundColor: '#f5f5f5', borderRadius: 4 }}>
            <Row justify='space-between' align='middle'>
              <Col>
                <Space>
                  <Tooltip
                    title={
                      !isScanning && scanConfigs.filter(c => c.enabled).length === 0
                        ? '请先在扫描配置列表中启用至少一个配置项'
                        : ''
                    }
                    placement='top'
                  >
                    <Button
                      type='primary'
                      icon={isScanning ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                      onClick={isScanning ? handleScanStop : handleScanStart}
                      loading={isScanning}
                      disabled={!isScanning && scanConfigs.filter(c => c.enabled).length === 0}
                    >
                      {isScanning ? '停止扫描' : '开始扫描'}
                    </Button>
                  </Tooltip>
                  <Button
                    danger
                    icon={<DeleteOutlined />}
                    onClick={handleClearProcessedFiles}
                    disabled={processedFiles.length === 0}
                  >
                    清空记录 ({processedFiles.length})
                  </Button>
                </Space>
              </Col>
              <Col>
                <Space>
                  <Button
                    size='small'
                    type={autoRefresh ? 'primary' : 'default'}
                    icon={<SyncOutlined spin={autoRefresh} />}
                    onClick={() => {
                      setAutoRefresh(!autoRefresh);
                      message.info(autoRefresh ? '自动刷新已停止' : '自动刷新已启用 (1秒间隔)');
                    }}
                  >
                    {autoRefresh ? '停止自动刷新' : '启用自动刷新'}
                  </Button>
                  <Button
                    size='small'
                    icon={<ReloadOutlined />}
                    onClick={() => {
                      loadScanConfigs();
                      loadStatistics();
                      loadProcessedFiles();
                      loadTaskConfig();
                      message.info('数据已刷新');
                    }}
                  >
                    手动刷新
                  </Button>
                </Space>
              </Col>
            </Row>
          </div>

          <Table
            dataSource={processedFiles}
            columns={processedFileColumns}
            rowKey='id'
            size='small'
            pagination={{ pageSize: 10, showSizeChanger: true }}
            scroll={{ y: 300 }}
            loading={loading}
          />
        </Card>

        {/* 语音加工结果 - 下半部分 */}
        <Card
          title={
            <Space>
              <SoundOutlined />
              <span>自动加工结果</span>
              <Tag color='blue'>{pipelineFiles.length} 个文件</Tag>
            </Space>
          }
          size='small'
          extra={
            <Space>
              <Button
                size='small'
                icon={<SettingOutlined />}
                onClick={() => setConfigCenterModalVisible(true)}
              >
                加工配置
              </Button>
              <Button
                type='primary'
                size='small'
                icon={<DownloadOutlined />}
                onClick={handleBatchDownload}
              >
                下载 ({selectedFileKeys.length})
              </Button>
              <Button
                danger
                size='small'
                icon={<DeleteOutlined />}
                onClick={handleBatchDelete}
              >
                删除 ({selectedFileKeys.length})
              </Button>
            </Space>
          }
          style={{ minHeight: 500 }}
        >
          {/* 自动加工管道控制 */}
          <div
            style={{
              marginBottom: 16,
              padding: '12px 16px',
              backgroundColor: '#f0f8ff',
              borderRadius: 4,
              border: '1px solid #d9f0ff',
            }}
          >
            <Row justify='space-between' align='middle'>
              <Col>
                <Space>
                  <ToolOutlined style={{ color: '#1890ff' }} />
                  <Text strong>自动加工管道</Text>
                  {renderPipelineStatus()}
                </Space>
              </Col>
              <Col>
                <Switch
                  checked={pipelineStatus?.running || false}
                  onChange={handleAutoProcessToggle}
                  loading={pipelineLoading}
                  checkedChildren='运行'
                  unCheckedChildren='停止'
                />
              </Col>
            </Row>
            {pipelineStatus?.running && (
              <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
                <Space split={<span style={{ color: '#d9d9d9' }}>|</span>}>
                  <span>队列: {pipelineStatus.queue_size || 0}</span>
                  <span>工作线程: {pipelineStatus.worker_count || 0}</span>
                  {pipelineStatus.watch_paths && pipelineStatus.watch_paths.length > 0 && (
                    <span>监控路径: {pipelineStatus.watch_paths.length}个</span>
                  )}
                </Space>
              </div>
            )}
          </div>
          
          {/* 转换结果统计（基于文件列表） */}
          <div style={{ marginBottom: 16, padding: '12px 16px', backgroundColor: '#f5f5f5', borderRadius: 4 }}>
            {/* 语音转换统计 */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 8, fontWeight: 'bold' }}>语音转换统计</div>
              <Row gutter={8}>
                <Col span={6}>
                  <div
                    style={{ textAlign: 'center', padding: '4px', backgroundColor: '#f0f8ff', borderRadius: 4 }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 'bold', color: '#1890ff' }}>
                      {pipelineFiles.filter(file => file.processors.includes('audio_to_text')).length}
                    </div>
                    <div style={{ fontSize: 10, color: '#666' }}>总计</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div
                    style={{ textAlign: 'center', padding: '4px', backgroundColor: '#f6ffed', borderRadius: 4 }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 'bold', color: '#52c41a' }}>
                      {pipelineFiles.filter(file => file.processors.includes('audio_to_text') && file.status === FileStatus.COMPLETED).length}
                    </div>
                    <div style={{ fontSize: 10, color: '#666' }}>成功</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div
                    style={{ textAlign: 'center', padding: '4px', backgroundColor: '#fff2f0', borderRadius: 4 }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 'bold', color: '#ff4d4f' }}>
                      {pipelineFiles.filter(file => file.processors.includes('audio_to_text') && file.status === FileStatus.FAILED).length}
                    </div>
                    <div style={{ fontSize: 10, color: '#666' }}>失败</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div
                    style={{ textAlign: 'center', padding: '4px', backgroundColor: '#fff7e6', borderRadius: 4 }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 'bold', color: '#fa8c16' }}>
                      {pipelineFiles.filter(file => file.processors.includes('audio_to_text') && file.status === FileStatus.SKIPPED).length}
                    </div>
                    <div style={{ fontSize: 10, color: '#666' }}>跳过</div>
                  </div>
                </Col>
              </Row>
            </div>

            {/* 知识库构建统计 */}
            <div>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 8, fontWeight: 'bold' }}>知识库自动构建统计</div>
              <Row gutter={8}>
                <Col span={6}>
                  <div
                    style={{ textAlign: 'center', padding: '4px', backgroundColor: '#f9f0ff', borderRadius: 4 }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 'bold', color: '#722ed1' }}>
                      {pipelineFiles.filter(file => file.processors.includes('knowledge_processor')).length}
                    </div>
                    <div style={{ fontSize: 10, color: '#666' }}>总计</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div
                    style={{ textAlign: 'center', padding: '4px', backgroundColor: '#f6ffed', borderRadius: 4 }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 'bold', color: '#52c41a' }}>
                      {pipelineFiles.filter(file => file.processors.includes('knowledge_processor') && file.status === FileStatus.COMPLETED).length}
                    </div>
                    <div style={{ fontSize: 10, color: '#666' }}>入库</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div
                    style={{ textAlign: 'center', padding: '4px', backgroundColor: '#fff2f0', borderRadius: 4 }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 'bold', color: '#ff4d4f' }}>
                      {pipelineFiles.filter(file => file.processors.includes('knowledge_processor') && file.status === FileStatus.FAILED).length}
                    </div>
                    <div style={{ fontSize: 10, color: '#666' }}>失败</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div
                    style={{ textAlign: 'center', padding: '4px', backgroundColor: '#fff7e6', borderRadius: 4 }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 'bold', color: '#fa8c16' }}>
                      {pipelineFiles.filter(file => file.processors.includes('knowledge_processor') && file.status === FileStatus.SKIPPED).length}
                    </div>
                    <div style={{ fontSize: 10, color: '#666' }}>跳过</div>
                  </div>
                </Col>
              </Row>
            </div>
          </div>

          {/* 语音加工结果刷新控制 */}
          <div style={{ marginBottom: 16, padding: '8px 12px', backgroundColor: '#f9f9f9', borderRadius: 4 }}>
            <Row justify='space-between' align='middle'>
              <Col>
                <Text type='secondary' style={{ fontSize: 12 }}>
                  管道状态: {renderPipelineStatus()}
                </Text>
              </Col>
              <Col>
                <Space>
                  <Button
                    size='small'
                    type={pipelineAutoRefresh ? 'primary' : 'default'}
                    icon={<SyncOutlined spin={pipelineAutoRefresh} />}
                    onClick={() => {
                      setPipelineAutoRefresh(!pipelineAutoRefresh);
                      message.info(pipelineAutoRefresh ? '自动刷新已停止' : '自动刷新已启用 (1秒间隔)');
                    }}
                  >
                    {pipelineAutoRefresh ? '停止自动刷新' : '启用自动刷新'}
                  </Button>
                  <Button
                    size='small'
                    icon={<ReloadOutlined />}
                    onClick={() => {
                      loadPipelineStatus();
                      loadPipelineFiles();
                      message.info('数据已刷新');
                    }}
                  >
                    手动刷新
                  </Button>
                </Space>
              </Col>
            </Row>
          </div>

          {/* 过滤和排序控制 */}
          <div style={{ marginBottom: 16, padding: '8px 12px', backgroundColor: '#f0f9ff', borderRadius: 4, border: '1px solid #bae6fd' }}>
            <Row gutter={8} align='middle'>
              <Col span={6}>
                <Input
                  size='small'
                  placeholder='搜索文件名'
                  prefix={<SearchOutlined />}
                  value={pipelineFilters.nameSearch}
                  onChange={(e) => setPipelineFilters(prev => ({ ...prev, nameSearch: e.target.value }))}
                  allowClear
                />
              </Col>
              <Col span={4}>
                <Select
                  size='small'
                  placeholder='状态筛选'
                  value={pipelineFilters.status}
                  onChange={(value) => setPipelineFilters(prev => ({ ...prev, status: value }))}
                  style={{ width: '100%' }}
                  allowClear
                >
                  <Option value={FileStatus.PENDING}>待处理</Option>
                  <Option value={FileStatus.PROCESSING}>处理中</Option>
                  <Option value={FileStatus.COMPLETED}>已完成</Option>
                  <Option value={FileStatus.FAILED}>失败</Option>
                  <Option value={FileStatus.SKIPPED}>已跳过</Option>
                </Select>
              </Col>
              <Col span={4}>
                <Select
                  size='small'
                  placeholder='处理器筛选'
                  value={pipelineFilters.processor}
                  onChange={(value) => setPipelineFilters(prev => ({ ...prev, processor: value }))}
                  style={{ width: '100%' }}
                  allowClear
                >
                  <Option value='audio_to_text'>语音转换</Option>
                  <Option value='knowledge_processor'>知识库</Option>
                </Select>
              </Col>
              <Col span={4}>
                <Select
                  size='small'
                  placeholder='排序方式'
                  value={`${pipelineSorting.field}_${pipelineSorting.order}`}
                  onChange={(value) => {
                    const [field, order] = value.split('_');
                    setPipelineSorting({ field, order });
                  }}
                  style={{ width: '100%' }}
                >
                  <Option value='name_asc'>名称 ↑</Option>
                  <Option value='name_desc'>名称 ↓</Option>
                  <Option value='size_asc'>大小 ↑</Option>
                  <Option value='size_desc'>大小 ↓</Option>
                  <Option value='last_processed_desc'>时间 ↓</Option>
                  <Option value='last_processed_asc'>时间 ↑</Option>
                </Select>
              </Col>
              <Col span={3}>
                <Button
                  size='small'
                  icon={<FilterOutlined />}
                  onClick={resetFilters}
                  style={{ width: '100%' }}
                >
                  重置
                </Button>
              </Col>
              <Col span={3}>
                <Text type='secondary' style={{ fontSize: 11 }}>
                  共 {getFilteredAndSortedFiles().length} 条
                </Text>
              </Col>
            </Row>
          </div>

          <Table
            dataSource={getFilteredAndSortedFiles()}
            columns={pipelineFileColumns}
            rowKey='path'
            size='small'
            pagination={{ 
              pageSize: 10, 
              showSizeChanger: true, 
              showQuickJumper: true,
              showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条/共 ${total} 条`
            }}
            scroll={{ y: 350 }}
            loading={pipelineFilesLoading}
          />
        </Card>
      </Space>

      {/* 以下弹窗组件保持不变 */}
      {/* 扫描配置弹窗 */}
      <Modal
        title={
          <Space>
            <SettingOutlined />
            <span>扫描配置列表</span>
            <Tag color='blue'>{scanConfigs.length} 个配置</Tag>
          </Space>
        }
        open={scanConfigModalVisible}
        onCancel={() => setScanConfigModalVisible(false)}
        footer={null}
        width={1000}
        destroyOnClose
      >
        <Space direction='vertical' style={{ width: '100%' }} size={16}>
          {/* 操作按钮区域 */}
{/* 操作按钮区域 */}
<div style={{ marginBottom: 16 }}>
  <Space>
    <Button type='primary' icon={<SyncOutlined />} onClick={handleShowAddFtpModal}>
      添加FTP配置
    </Button>
    <Button icon={<FileOutlined />} onClick={handleOpenFileTypeModal}>
  文件类型配置
</Button>
    <Button icon={<SettingOutlined />} onClick={handleTestConnection}>
      测试所有连接
    </Button>
    <Button icon={<ReloadOutlined />} onClick={loadScanConfigs}>
      刷新配置
    </Button>
  </Space>
</div>

          <Table
            dataSource={scanConfigs}
            columns={scanConfigColumns}
            rowKey='id'
            size='small'
            pagination={{ pageSize: 10, showSizeChanger: true, showQuickJumper: true }}
            scroll={{ y: 400 }}
            loading={loading}
          />
        </Space>
      </Modal>

      {/* 配置中心弹窗 */}
      <Modal
        title={
          <Space>
            <ToolOutlined />
            <span>配置中心</span>
          </Space>
        }
        open={configCenterModalVisible}
        onCancel={() => setConfigCenterModalVisible(false)}
        footer={null}
        width={800}
        destroyOnClose
      >
        <Space direction='vertical' style={{ width: '100%' }} size={16}>
          <Collapse
            activeKey={activePanel}
            onChange={setActivePanel}
            expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} />}
            size='small'
            ghost
          >
            {/* 语音自动加工 */}
            <Panel
              header={
                <Space>
                  <SoundOutlined />
                  <span>语音加工配置</span>
                  {pipelineStatus?.running && <Badge status='success' />}
                </Space>
              }
              key='1'
            >
              <Form size='small' layout='vertical'>
                <Row gutter={8}>
                  <Col span={12}>
                    <Form.Item label='语言' style={{ marginBottom: 8 }}>
                      <Select
                        size='small'
                        value={voiceConfig.language}
                        onChange={value => setVoiceConfig(prev => ({ ...prev, language: value }))}
                      >
                        <Option value='auto'>自动</Option>
                        <Option value='zh'>中文</Option>
                        <Option value='en'>英文</Option>
                        <Option value='yue'>粤语</Option>
                      </Select>
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label='批量数' style={{ marginBottom: 8 }}>
                      <InputNumber
                        size='small'
                        min={1}
                        max={100}
                        value={voiceConfig.batchSize}
                        onChange={value => setVoiceConfig(prev => ({ ...prev, batchSize: value || 10 }))}
                        style={{ width: '100%' }}
                      />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item style={{ marginBottom: 0 }}>
                  <Button
                    type='primary'
                    size='small'
                    onClick={() => {
                      message.success('语音配置已保存');
                    }}
                    style={{ width: '100%' }}
                  >
                    保存语音配置
                  </Button>
                </Form.Item>
              </Form>
            </Panel>

            {/* 知识库加工配置 */}
            <Panel
              header={
                <Space>
                  <DatabaseOutlined />
                  <span>知识库加工配置</span>
                  {pipelineStatus?.running && <Badge status='success' />}
                </Space>
              }
              key='2'
            >
              <Form size='small' layout='vertical'>
                <Form.Item label='支持文件类型' style={{ marginBottom: 8 }}>
                  <div style={{ padding: '8px 12px', backgroundColor: '#f5f5f5', borderRadius: 4 }}>
                    <Space wrap>
                      <Tag color='blue'>.txt</Tag>
                      <Tag color='blue'>.doc</Tag>
                      <Tag color='blue'>.docx</Tag>
                      <Tag color='blue'>.pdf</Tag>
                      <Tag color='green'>转换后的语音文本</Tag>
                    </Space>
                  </div>
                </Form.Item>

                <Form.Item label='分割策略' style={{ marginBottom: 8 }}>
                  <Select
                    size='small'
                    defaultValue='semantic'
                    style={{ width: '100%' }}
                    onChange={(value) => {
                      message.info(`分割策略已设置为: ${value === 'semantic' ? '智能语义分割' : value}`);
                    }}
                  >
                    <Option value='semantic'>智能语义分割</Option>
                    <Option value='paragraph'>按段落分割</Option>
                    <Option value='sentence'>按句子分割</Option>
                    <Option value='fixed'>固定长度分割</Option>
                  </Select>
                </Form.Item>

                <Row gutter={8}>
                  <Col span={12}>
                    <Form.Item label='管理操作' style={{ marginBottom: 0 }}>
                      <Button
                        type='primary'
                        icon={<DatabaseOutlined />}
                        onClick={() => {
                          window.open('/construct/knowledge', '_blank');
                        }}
                        style={{ width: '100%' }}
                      >
                        打开知识库管理
                      </Button>
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label='配置保存' style={{ marginBottom: 0 }}>
                      <Button
                        type='default'
                        onClick={() => {
                          message.success('知识库配置已保存');
                        }}
                        style={{ width: '100%' }}
                      >
                        保存配置
                      </Button>
                    </Form.Item>
                  </Col>
                </Row>
              </Form>
            </Panel>
          </Collapse>
        </Space>
      </Modal>
{/* 全局文件类型配置弹窗 */}
<Modal
  title={
    <Space>
      <FileOutlined />
      <span>全局文件类型配置</span>
    </Space>
  }
  open={fileTypeModalVisible}
  onCancel={() => {
    setFileTypeModalVisible(false);
    fileTypeForm.resetFields();
  }}
  footer={null}
  width={600}
  destroyOnClose
>
  <div style={{ marginBottom: 16, padding: '12px 16px', backgroundColor: '#f0f9ff', borderRadius: 4 }}>
    <Text type='secondary' style={{ fontSize: 12 }}>
      <FileOutlined style={{ marginRight: 4 }} />
      选择系统支持的文件类型。取消选择将禁用该文件类型，选择新类型将自动添加到配置中。
    </Text>
  </div>
  
  <Form
    form={fileTypeForm}
    layout='vertical'
    onFinish={handleSaveFileTypes}
    initialValues={{ 
      fileTypes: globalFileTypes.filter(type => type.enabled).map(type => type.extension) 
    }}
  >
    <Form.Item
      label={
        <Space>
          <span>支持的文件类型</span>
          <Text type='secondary' style={{ fontSize: 12 }}>
            (当前启用: {globalFileTypes.filter(type => type.enabled).length}个)
          </Text>
        </Space>
      }
      name='fileTypes'
      rules={[{ required: true, message: '请选择至少一种文件类型' }]}
    >
      <Select
        mode='multiple'
        placeholder='选择要启用的文件类型'
        style={{ width: '100%' }}
        optionLabelProp='label'
      >
        <Option value='.wav' label='WAV'>
          <Space>
            <SoundOutlined style={{ color: '#1890ff' }} />
            <span>WAV 音频</span>
          </Space>
        </Option>
        <Option value='.mp3' label='MP3'>
          <Space>
            <SoundOutlined style={{ color: '#1890ff' }} />
            <span>MP3 音频</span>
          </Space>
        </Option>
        <Option value='.mp4' label='MP4'>
          <Space>
            <SoundOutlined style={{ color: '#722ed1' }} />
            <span>MP4 视频</span>
          </Space>
        </Option>
        <Option value='.flac' label='FLAC'>
          <Space>
            <SoundOutlined style={{ color: '#1890ff' }} />
            <span>FLAC 音频</span>
          </Space>
        </Option>
        <Option value='.aac' label='AAC'>
          <Space>
            <SoundOutlined style={{ color: '#1890ff' }} />
            <span>AAC 音频</span>
          </Space>
        </Option>
        <Option value='.txt' label='TXT'>
          <Space>
            <FileOutlined style={{ color: '#52c41a' }} />
            <span>TXT 文本</span>
          </Space>
        </Option>
        <Option value='.doc' label='DOC'>
          <Space>
            <FileOutlined style={{ color: '#1890ff' }} />
            <span>DOC 文档</span>
          </Space>
        </Option>
        <Option value='.docx' label='DOCX'>
          <Space>
            <FileOutlined style={{ color: '#1890ff' }} />
            <span>DOCX 文档</span>
          </Space>
        </Option>
        <Option value='.pdf' label='PDF'>
          <Space>
            <FileOutlined style={{ color: '#f5222d' }} />
            <span>PDF 文档</span>
          </Space>
        </Option>
        <Option value='.xlsx' label='XLSX'>
          <Space>
            <FileOutlined style={{ color: '#52c41a' }} />
            <span>XLSX 表格</span>
          </Space>
        </Option>
        <Option value='.ppt' label='PPT'>
          <Space>
            <FileOutlined style={{ color: '#fa8c16' }} />
            <span>PPT 演示文稿</span>
          </Space>
        </Option>
        <Option value='.pptx' label='PPTX'>
          <Space>
            <FileOutlined style={{ color: '#fa8c16' }} />
            <span>PPTX 演示文稿</span>
          </Space>
        </Option>
        <Option value='.jpg' label='JPG'>
          <Space>
            <FileOutlined style={{ color: '#eb2f96' }} />
            <span>JPG 图片</span>
          </Space>
        </Option>
        <Option value='.png' label='PNG'>
          <Space>
            <FileOutlined style={{ color: '#eb2f96' }} />
            <span>PNG 图片</span>
          </Space>
        </Option>
      </Select>
    </Form.Item>

    <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
      <Space>
        <Button onClick={() => setFileTypeModalVisible(false)}>
          取消
        </Button>
        <Button type='primary' htmlType='submit' loading={loading}>
          保存配置
        </Button>
      </Space>
    </Form.Item>
  </Form>
</Modal>
      {/* 定时任务配置Modal */}
      <Modal
        title='定时扫描配置'
        open={taskConfigVisible}
        onCancel={() => {
          setTaskConfigVisible(false);
          taskConfigForm.resetFields();
        }}
        footer={null}
        width={500}
        destroyOnClose={true}
      >
        <Form
          form={taskConfigForm}
          layout='vertical'
          onFinish={handleUpdateTaskConfig}
          preserve={false}
          onValuesChange={(changedValues, allValues) => {
            console.log('表单值变化:', changedValues);
            console.log('当前所有表单值:', allValues);
          }}
        >
          <Form.Item name='enabled' valuePropName='checked' style={{ marginBottom: 16 }}>
            <Checkbox>启用定时扫描</Checkbox>
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name='timeValue'
                label='扫描间隔'
                rules={[
                  { required: true, message: '请输入扫描间隔' },
                  { type: 'number', min: 1, message: '间隔时间必须大于0' },
                ]}
              >
                <InputNumber min={1} max={9999} placeholder='请输入数值' style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name='timeUnit' label='时间单位'>
                <Select placeholder='选择单位'>
                  {TIME_UNITS.map(unit => (
                    <Option key={unit.value} value={unit.value}>
                      {unit.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          {/* 实时预览配置 */}
          <div style={{ padding: '12px 16px', backgroundColor: '#f5f5f5', borderRadius: 4, marginBottom: 16 }}>
            <Text type='secondary' style={{ fontSize: 12 }}>
              <Form.Item noStyle shouldUpdate>
                {() => {
                  const formTimeValue = taskConfigForm.getFieldValue('timeValue');
                  const formTimeUnit = taskConfigForm.getFieldValue('timeUnit');
                  const formEnabled = taskConfigForm.getFieldValue('enabled');

                  if (formTimeValue && formTimeUnit) {
                    const unitLabel = TIME_UNITS.find(u => u.value === formTimeUnit)?.label || '秒';
                    const totalSeconds =
                      formTimeValue * (TIME_UNITS.find(u => u.value === formTimeUnit)?.multiplier || 1);

                    return `配置预览: ${formEnabled ? '启用' : '停用'} | 每 ${formTimeValue} ${unitLabel} 执行一次扫描任务 (总计 ${totalSeconds} 秒)`;
                  }

                  return '配置预览: 加载中...';
                }}
              </Form.Item>
            </Text>
          </div>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setTaskConfigVisible(false)}>取消</Button>
              <Button type='primary' htmlType='submit' loading={loading}>
                保存配置
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 添加/编辑FTP配置的Modal */}
      {selectedFtpConfig && (
        <Modal
          title={isAddMode ? '添加FTP配置' : '编辑FTP配置'}
          open={!!selectedFtpConfig}
          onCancel={() => {
            setSelectedFtpConfig(null);
            setIsAddMode(false);
            addFtpForm.resetFields();
            editFtpForm.resetFields();
          }}
          footer={null}
          width={600}
        >
<Form
  form={isAddMode ? addFtpForm : editFtpForm}
  layout='vertical'
  onFinish={handleSaveFtpConfig}  // 统一使用这个函数
  initialValues={
    isAddMode
      ? {
          ftpPort: 21,
          scanPath: '/',
        }
      : undefined
  }
>
            <Form.Item label='配置名称' name='name' rules={[{ required: true, message: '请输入配置名称' }]}>
              <Input placeholder='FTP配置名称' />
            </Form.Item>

            <Form.Item label='FTP服务器' name='ftpHost' rules={[{ required: true, message: '请输入FTP服务器地址' }]}>
              <Input placeholder='服务器地址' />
            </Form.Item>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label='端口' name='ftpPort' rules={[{ required: true, message: '请输入端口' }]}>
                  <InputNumber min={1} max={65535} placeholder='21' style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label='远程目录' name='scanPath'>
                  <Input placeholder='/upload' />
                </Form.Item>
              </Col>
            </Row>

            {/* <Form.Item
              label='扫描文件类型'
              name='fileTypes'
              rules={[{ required: true, message: '请选择至少一种文件类型' }]}
            >
              <Select
                mode='multiple'
                placeholder='选择要扫描的文件类型'
                style={{ width: '100%' }}
                optionLabelProp='label'
              >
                <Option value='.wav' label='WAV'>
                  <Space>
                    <SoundOutlined style={{ color: '#1890ff' }} />
                    <span>WAV 音频</span>
                  </Space>
                </Option>
                <Option value='.mp3' label='MP3'>
                  <Space>
                    <SoundOutlined style={{ color: '#1890ff' }} />
                    <span>MP3 音频</span>
                  </Space>
                </Option>
                <Option value='.mp4' label='MP4'>
                  <Space>
                    <SoundOutlined style={{ color: '#722ed1' }} />
                    <span>MP4 视频</span>
                  </Space>
                </Option>
                <Option value='.flac' label='FLAC'>
                  <Space>
                    <SoundOutlined style={{ color: '#1890ff' }} />
                    <span>FLAC 音频</span>
                  </Space>
                </Option>
                <Option value='.aac' label='AAC'>
                  <Space>
                    <SoundOutlined style={{ color: '#1890ff' }} />
                    <span>AAC 音频</span>
                  </Space>
                </Option>
                <Option value='.txt' label='TXT'>
                  <Space>
                    <FileOutlined style={{ color: '#52c41a' }} />
                    <span>TXT 文本</span>
                  </Space>
                </Option>
                <Option value='.doc' label='DOC'>
                  <Space>
                    <FileOutlined style={{ color: '#1890ff' }} />
                    <span>DOC 文档</span>
                  </Space>
                </Option>
                <Option value='.docx' label='DOCX'>
                  <Space>
                    <FileOutlined style={{ color: '#1890ff' }} />
                    <span>DOCX 文档</span>
                  </Space>
                </Option>
                <Option value='.pdf' label='PDF'>
                  <Space>
                    <FileOutlined style={{ color: '#f5222d' }} />
                    <span>PDF 文档</span>
                  </Space>
                </Option>
                <Option value='.xlsx' label='XLSX'>
                  <Space>
                    <FileOutlined style={{ color: '#52c41a' }} />
                    <span>XLSX 表格</span>
                  </Space>
                </Option>
                <Option value='.ppt' label='PPT'>
                  <Space>
                    <FileOutlined style={{ color: '#fa8c16' }} />
                    <span>PPT 演示文稿</span>
                  </Space>
                </Option>
                <Option value='.pptx' label='PPTX'>
                  <Space>
                    <FileOutlined style={{ color: '#fa8c16' }} />
                    <span>PPTX 演示文稿</span>
                  </Space>
                </Option>
                <Option value='.jpg' label='JPG'>
                  <Space>
                    <FileOutlined style={{ color: '#eb2f96' }} />
                    <span>JPG 图片</span>
                  </Space>
                </Option>
                <Option value='.png' label='PNG'>
                  <Space>
                    <FileOutlined style={{ color: '#eb2f96' }} />
                    <span>PNG 图片</span>
                  </Space>
                </Option>
              </Select>
            </Form.Item> */}

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label='用户名' name='ftpUser' rules={[{ required: true, message: '请输入用户名' }]}>
                  <Input placeholder='FTP用户名' />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label='密码' name='ftpPassword' rules={[{ required: true, message: '请输入密码' }]}>
                  <Input.Password placeholder='FTP密码' />
                </Form.Item>
              </Col>
            </Row>

            {!isAddMode && (
              <Form.Item label='状态' name='enabled' valuePropName='checked'>
                <Switch />
              </Form.Item>
            )}

<Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
  <Space>
    {/* 测试连接按钮 - 对添加和编辑模式都显示 */}
    <Button
  block
  icon={<SettingOutlined />}
  onClick={() => {
    const currentForm = isAddMode ? addFtpForm : editFtpForm;
    currentForm.validateFields().then(values => {
      handleTestSingleFtpConfig(values, true); // true表示来自表单数据
    }).catch(errorInfo => {
      message.warning('请先完善FTP配置信息再进行测试');
    });
  }}
  loading={loading}
  type="dashed"
>
  测试FTP连接
</Button>
    <Button
      onClick={() => {
        setSelectedFtpConfig(null);
        setIsAddMode(false);
        addFtpForm.resetFields();
        editFtpForm.resetFields();
      }}
    >
      取消
    </Button>
    <Button type='primary' htmlType='submit' loading={loading}>
      {isAddMode ? '添加配置' : '保存修改'}
    </Button>
  </Space>
</Form.Item>
          </Form>
        </Modal>
      )}
    </div>
  );
};

export default AutoProcessModule;