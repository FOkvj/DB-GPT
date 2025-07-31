import { apiInterceptors, postChatModeParamsList } from '@/client/api';
import {
  FTPServerConfig,
  FileTypeModel,
  FileTypeResponse,
  ScanConfigResponse,
  TaskDetailResponse,
  addFTPServer,
  addFileType,
  deleteScanConfig,
  executeScanAsync,
  getFileTypes,
  getScanConfigs,
  getTaskDetail,
  testFTPConnection,
  testScanConfigs,
  updateFileType,
  updateScanConfig,
  updateTask,
} from '@/client/api/expend/file-scan';
// 导入管道控制API
import {
  KnowledgeBaseMappingConfig,
  PipelineStatus,
  ProcessorsStatusResponse,
  controlProcessor,
  getKnowledgeBaseMappings,
  getProcessorsStatus,
  saveKnowledgeBaseMappings,
  reprocessFiles,
  deleteKnowledgeBaseMappings,
} from '@/client/api/expend/auto-pipeline';
import {
  FileProcessingResponse,
  FileProcessingStatistics,
  batchDeleteFileProcessing,
  clearAllFileProcessing,
  getFileProcessingList,
  getFileProcessingStatistics,
} from '@/client/api/expend/file-manage';
import { IDB } from '@/types/chat';
import {
  CaretRightOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FileOutlined,
  FilterOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  SettingOutlined,
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
  const [statistics, setStatistics] = useState<FileProcessingStatistics | null>(null);
  // 合并为一个文件列表
  const [allFiles, setAllFiles] = useState<FileProcessingResponse[]>([]);
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
  const [filesLoading, setFilesLoading] = useState(false);
  const [selectedFileKeys, setSelectedFileKeys] = useState<string[]>([]);

  const [processorsStatus, setProcessorsStatus] = useState<ProcessorsStatusResponse | null>(null);
  const [audioProcessorLoading, setAudioProcessorLoading] = useState(false);
  const [knowledgeProcessorLoading, setKnowledgeProcessorLoading] = useState(false);

  // 弹窗状态
  const [scanConfigModalVisible, setScanConfigModalVisible] = useState(false);
  const [configCenterModalVisible, setConfigCenterModalVisible] = useState(false);

  // 文件列表自动刷新
  const [filesAutoRefresh, setFilesAutoRefresh] = useState(false);

  const loadProcessorsStatus = useCallback(async () => {
    const [error, data] = await apiInterceptors(getProcessorsStatus());
    if (!error && data) {
      setProcessorsStatus(data);
    }
  }, []);

  // 语音配置
  const [voiceConfig, setVoiceConfig] = useState({
    enabled: false,
    language: 'auto',
    batchSize: 10,
  });

  // 文件过滤和排序状态
  const [fileFilters, setFileFilters] = useState({
    status: '',
    source_type: '',
    file_type: '',
    nameSearch: '',
  });
  const [fileSorting, setFileSorting] = useState({
    field: 'created_at',
    order: 'desc',
  });

  const [globalFileTypes, setGlobalFileTypes] = useState<FileTypeResponse[]>([]);
  const [originalFileTypes, setOriginalFileTypes] = useState<FileTypeResponse[]>([]);
  const [fileTypeModalVisible, setFileTypeModalVisible] = useState(false);
  const [fileTypeForm] = Form.useForm();

  // 知识库映射配置状态
  const [knowledgeBases, setKnowledgeBases] = useState<IDB[]>([]);
  const [knowledgeMappings, setKnowledgeMappings] = useState<KnowledgeBaseMappingConfig[]>([]);
  const [mappingForm] = Form.useForm();

  const handleOpenFileTypeModal = () => {
    setFileTypeModalVisible(true);
    // 延迟设置表单值，确保弹窗完全打开
    setTimeout(() => {
      fileTypeForm.setFieldsValue({
        fileTypes: globalFileTypes.filter(type => type.enabled).map(type => type.extension),
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

          operations.push(apiInterceptors(updateFileType(originalType.extension, updateData)));
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

        operations.push(apiInterceptors(addFileType(newFileType)));
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
                    <div>
                      主机: {data.host}:{data.port}
                    </div>
                    <div>用户: {data.username}</div>
                    <div style={{ color: '#52c41a' }}>状态: 连接成功</div>
                  </div>
                </div>

                {data.remote_dir_status && (
                  <div style={{ marginBottom: 16 }}>
                    <Text strong>远程目录状态:</Text>
                    <div
                      style={{
                        marginLeft: 16,
                        marginTop: 8,
                        color: data.remote_dir_status.includes('成功') ? '#52c41a' : '#ff4d4f',
                      }}
                    >
                      {data.remote_dir_status}
                    </div>
                  </div>
                )}

                {Array.isArray(data.root_files) && data.root_files.length > 0 && (
                  <div>
                    <Text strong>根目录文件 (前20个):</Text>
                    <div
                      style={{
                        marginLeft: 16,
                        marginTop: 8,
                        maxHeight: 200,
                        overflow: 'auto',
                        backgroundColor: '#f5f5f5',
                        padding: 8,
                        borderRadius: 4,
                        fontSize: 12,
                        fontFamily: 'monospace',
                      }}
                    >
                      {data.root_files.map((file, index) => (
                        <div key={index}>{file}</div>
                      ))}
                    </div>
                  </div>
                )}

                {typeof data.root_files === 'string' && (
                  <div>
                    <Text strong>文件列表错误:</Text>
                    <div
                      style={{
                        marginLeft: 16,
                        marginTop: 8,
                        color: '#ff4d4f',
                      }}
                    >
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
                    <div>
                      主机: {testConfig.host}:{testConfig.port}
                    </div>
                    <div>用户: {testConfig.username}</div>
                    <div style={{ color: '#ff4d4f' }}>状态: 连接失败</div>
                  </div>
                </div>

                <div>
                  <Text strong>错误信息:</Text>
                  <div
                    style={{
                      marginLeft: 16,
                      marginTop: 8,
                      color: '#ff4d4f',
                    }}
                  >
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
                  <div>
                    主机: {testConfig.host}:{testConfig.port}
                  </div>
                  <div>用户: {testConfig.username}</div>
                  <div style={{ color: '#ff4d4f' }}>状态: 连接失败</div>
                </div>
              </div>

              <div>
                <Text strong>错误信息:</Text>
                <div
                  style={{
                    marginLeft: 16,
                    marginTop: 8,
                    color: '#ff4d4f',
                  }}
                >
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
                <div>
                  主机: {testConfig.host}:{testConfig.port}
                </div>
                <div>用户: {testConfig.username}</div>
                <div style={{ color: '#ff4d4f' }}>状态: 连接异常</div>
              </div>
            </div>

            <div>
              <Text strong>错误信息:</Text>
              <div
                style={{
                  marginLeft: 16,
                  marginTop: 8,
                  color: '#ff4d4f',
                }}
              >
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

  // 加载知识库列表
  const loadKnowledgeBases = useCallback(async () => {
    const [error, data] = await apiInterceptors(postChatModeParamsList('chat_knowledge'));
    if (!error && data) {
      setKnowledgeBases(data);
      console.log(knowledgeBases);
    }
  }, []);

  // 加载知识库映射配置
  const loadKnowledgeMappings = useCallback(async () => {
    const [error, data] = await apiInterceptors(getKnowledgeBaseMappings());
    if (!error && data) {
      setKnowledgeMappings(data);
    }
  }, []);

  // 加载所有文件列表（合并FTP扫描和语音转换文件）
  const loadAllFiles = useCallback(async () => {
    setFilesLoading(true);
    try {
      // 同时获取FTP扫描文件和语音转换文件
      const [ftpError, ftpData] = await apiInterceptors(
        getFileProcessingList({
          page: 1,
          page_size: 100,
          source_type: 'ftp',
        }),
      );

      const [sttError, sttData] = await apiInterceptors(
        getFileProcessingList({
          page: 1,
          page_size: 100,
          source_type: 'stt',
        }),
      );

      const allFilesData = [];
      if (!ftpError && ftpData) {
        allFilesData.push(...ftpData.items);
      }
      if (!sttError && sttData) {
        allFilesData.push(...sttData.items);
      }

      setAllFiles(allFilesData);
    } catch (error) {
      console.error('加载文件列表失败:', error);
    } finally {
      setFilesLoading(false);
    }
  }, []);

  // 加载数据的函数
  const loadScanConfigs = useCallback(async () => {
    const [error, data] = await apiInterceptors(getScanConfigs());
    if (!error && data) {
      setScanConfigs(data);
    }
  }, []);

  const loadStatistics = useCallback(async () => {
    const [error, data] = await apiInterceptors(getFileProcessingStatistics());
    if (!error && data) {
      setStatistics(data);
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

  // 语音处理器控制
  const handleAudioProcessorControl = async (action: 'start' | 'stop') => {
    try {
      setAudioProcessorLoading(true);
      const [error, data] = await apiInterceptors(
        controlProcessor({
          action,
          processor_name: 'audio_to_text',
        }),
      );
      if (!error && data) {
        message.success(`语音转换处理器已${action === 'start' ? '启动' : '停止'}`);
        await loadProcessorsStatus();
      }
    } catch (error) {
      message.error(`${action === 'start' ? '启动' : '停止'}语音转换处理器失败`);
    } finally {
      setAudioProcessorLoading(false);
    }
  };

  // 知识库处理器控制
  const handleKnowledgeProcessorControl = async (action: 'start' | 'stop') => {
    try {
      setKnowledgeProcessorLoading(true);
      const [error, data] = await apiInterceptors(
        controlProcessor({
          action,
          processor_name: 'knowledge_processor',
        }),
      );
      if (!error && data) {
        message.success(`知识库处理器已${action === 'start' ? '启动' : '停止'}`);
        await loadProcessorsStatus();
      }
    } catch (error) {
      message.error(`${action === 'start' ? '启动' : '停止'}知识库处理器失败`);
    } finally {
      setKnowledgeProcessorLoading(false);
    }
  };

  // 初始化加载数据
  useEffect(() => {
    loadKnowledgeBases();
    loadKnowledgeMappings();
    loadScanConfigs();
    loadStatistics();
    loadAllFiles(); // 替换原有的两个文件加载函数
    loadTaskConfig();
    loadProcessorsStatus();
    loadGlobalFileTypes();
  }, [
    loadKnowledgeBases,
    loadKnowledgeMappings,
    loadScanConfigs,
    loadStatistics,
    loadAllFiles, // 更新依赖
    loadTaskConfig,
    loadProcessorsStatus,
    loadGlobalFileTypes,
  ]);

  // 文件列表自动刷新效果
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (filesAutoRefresh) {
      intervalId = setInterval(() => {
        loadAllFiles();
        loadStatistics();
        loadProcessorsStatus();
      }, refreshInterval);
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [filesAutoRefresh, refreshInterval, loadAllFiles, loadStatistics]);

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
          loadAllFiles(); // 替换原来的 loadProcessedFiles()
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

  // 处理文件删除
  const handleDeleteFiles = (fileIds: string[]) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除 ${fileIds.length} 个文件记录吗？此操作不可恢复。`,
      onOk: async () => {
        try {
          setFilesLoading(true);
          const [error, data] = await apiInterceptors(
            batchDeleteFileProcessing({
              file_ids: fileIds,
            }),
          );
          if (!error && data) {
            message.success(`成功删除 ${data} 个文件记录`);
            setSelectedFileKeys([]);
            await loadAllFiles();
          }
        } catch (error) {
          console.error('删除文件记录失败:', error);
          message.error('删除文件记录失败');
        } finally {
          setFilesLoading(false);
        }
      },
    });
  };

  // 处理重新处理文件（支持批量和单个）
  // 修改重新处理函数
  const handleBatchReprocess = async (fileIds?: string[]) => {
    const targetFileIds = fileIds || selectedFileKeys;
    
    if (targetFileIds.length === 0) {
      message.warning('请先选择要重新处理的文件');
      return;
    }
    
    try {
      setFilesLoading(true);
      const [error, data] = await apiInterceptors(reprocessFiles({ 
        file_ids: targetFileIds 
      }));
      
      if (!error && data) {
        // 处理响应结果
        const { success_count, failed_files, total_count } = data;
        
        if (failed_files.length === 0) {
          message.success(`已将 ${success_count} 个文件重新加入处理队列`);
        } else {
          message.warning(`成功处理 ${success_count} 个文件，${failed_files.length} 个文件处理失败`);
          
          // 可选：显示失败详情
          if (failed_files.length > 0) {
            console.warn('重新处理失败的文件:', failed_files);
          }
        }
        
        if (!fileIds) {
          // 如果是批量操作，清空选择
          setSelectedFileKeys([]);
        }
        await loadAllFiles();
      }
    } catch (error) {
      console.error('重新处理失败:', error);
      message.error('重新处理失败');
    } finally {
      setFilesLoading(false);
    }
  };

  const handleClearAllFiles = () => {
    confirm({
      title: '确认清空',
      content: '确定要清空所有文件记录吗？这将重置所有扫描和处理状态。',
      onOk: async () => {
        try {
          const [error] = await apiInterceptors(clearAllFileProcessing());
          if (!error) {
            message.success('已清空所有文件记录');
            loadAllFiles();
            loadStatistics();
          }
        } catch (error) {
          console.error('清空文件记录失败:', error);
        }
      },
    });
  };

  // 处理文件下载
  const handleDownloadFile = (file: FileProcessingResponse) => {
    message.info(`开始下载 ${file.file_name}`);
    // 实际应用中这里应该调用下载API
    // window.open(`/api/files/download/${encodeURIComponent(file.file_id)}`, '_blank');
  };

  // 处理知识库跳转 - 只对文本文件且状态为成功时可用
  const handleKnowledgeJump = (file: FileProcessingResponse) => {
    if (file.status === 'success' && isTextFile(file)) {
      window.open('/construct/knowledge', '_blank');
      message.success(`已打开知识库管理页面，可查看文件 "${file.file_name}" 的知识库内容`);
    } else if (!isTextFile(file)) {
      message.warning('只有文本文件才能跳转到知识库');
    } else {
      message.warning('文件处理完成后才能跳转到知识库');
    }
  };

  // 过滤和排序处理
  const getFilteredAndSortedFiles = () => {
    let filteredFiles = [...allFiles];

    // 应用过滤器
    if (fileFilters.status) {
      filteredFiles = filteredFiles.filter(file => file.status === fileFilters.status);
    }
    if (fileFilters.source_type) {
      filteredFiles = filteredFiles.filter(file => file.source_type === fileFilters.source_type);
    }
    if (fileFilters.file_type) {
      filteredFiles = filteredFiles.filter(file =>
        file.file_type?.toLowerCase().includes(fileFilters.file_type.toLowerCase()),
      );
    }
    if (fileFilters.nameSearch) {
      filteredFiles = filteredFiles.filter(file =>
        file.file_name.toLowerCase().includes(fileFilters.nameSearch.toLowerCase()),
      );
    }

    // 应用排序
    filteredFiles.sort((a, b) => {
      let aValue, bValue;

      switch (fileSorting.field) {
        case 'file_name':
          aValue = a.file_name.toLowerCase();
          bValue = b.file_name.toLowerCase();
          break;
        case 'size':
          aValue = a.size || 0;
          bValue = b.size || 0;
          break;
        case 'status':
          aValue = a.status;
          bValue = b.status;
          break;
        case 'source_type':
          aValue = a.source_type;
          bValue = b.source_type;
          break;
        case 'created_at':
          aValue = a.created_at ? new Date(a.created_at).getTime() : 0;
          bValue = b.created_at ? new Date(b.created_at).getTime() : 0;
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return fileSorting.order === 'asc' ? -1 : 1;
      if (aValue > bValue) return fileSorting.order === 'asc' ? 1 : -1;
      return 0;
    });

    return filteredFiles;
  };

  // 重置过滤器
  const resetFilters = () => {
    setFileFilters({
      status: '',
      source_type: '',
      file_type: '',
      nameSearch: '',
    });
    message.info('已重置所有过滤条件');
  };

  // 获取文件状态显示
  const getFileStatusDisplay = (status: string) => {
    const statusConfig = {
      wait: { color: 'default', text: '待处理' },
      processing: { color: 'processing', text: '处理中' },
      downloading: { color: 'processing', text: '下载中' },
      success: { color: 'success', text: '已完成' },
      failed: { color: 'error', text: '失败' },
      retrying: { color: 'warning', text: '重试中' },
    };
    return statusConfig[status] || statusConfig['wait'];
  };

  // 全选/反选处理
  const handleSelectAll = (checked: boolean) => {
    const filteredFiles = getFilteredAndSortedFiles();
    if (checked) {
      setSelectedFileKeys(filteredFiles.map(file => file.file_id));
    } else {
      setSelectedFileKeys([]);
    }
  };

  // 单个文件选择处理
  const handleFileSelect = (fileId: string, checked: boolean) => {
    if (checked) {
      setSelectedFileKeys([...selectedFileKeys, fileId]);
    } else {
      setSelectedFileKeys(selectedFileKeys.filter(key => key !== fileId));
    }
  };

  // 批量下载处理
  const handleBatchDownload = () => {
    if (selectedFileKeys.length === 0) {
      message.warning('请先选择要下载的文件');
      return;
    }
    selectedFileKeys.forEach(fileId => {
      const file = allFiles.find(f => f.file_id === fileId);
      if (file) handleDownloadFile(file);
    });
  };

  // 批量删除处理
  const handleBatchDelete = () => {
    if (selectedFileKeys.length === 0) {
      message.warning('请先选择要删除的文件');
      return;
    }
    handleDeleteFiles(selectedFileKeys);
  };

  // 判断文件是否为文本文件
  const isTextFile = (file: FileProcessingResponse) => {
    if (!file.file_type) return false;
    const textTypes = ['.txt', '.doc', '.docx', '.pdf', '.md', '.rtf', '.xlsx', '.csv'];
    return textTypes.some(type => file.file_type?.toLowerCase().includes(type.toLowerCase()));
  };

  // 判断文件是否为音频文件
  const isAudioFile = (file: FileProcessingResponse) => {
    if (!file.file_type) return false;
    const audioTypes = ['.wav', '.mp3', '.mp4', '.flac', '.aac', '.m4a', '.wma'];
    return audioTypes.some(type => file.file_type?.toLowerCase().includes(type.toLowerCase()));
  };

  // 获取来源标签
  const getSourceTag = (file: FileProcessingResponse) => {
    if (file.source_type === 'ftp') {
      return (
        <Tag color='blue' size='small'>
          FTP扫描
        </Tag>
      );
    } else if (file.source_type === 'stt') {
      return (
        <Tag color='green' size='small'>
          语音转换
        </Tag>
      );
    }
    return (
      <Tag color='default' size='small'>
        未知来源
      </Tag>
    );
  };

  // 统一文件列表表格配置
  const fileListColumns = [
    {
      title: (
        <Checkbox
          checked={
            selectedFileKeys.length === getFilteredAndSortedFiles().length && getFilteredAndSortedFiles().length > 0
          }
          indeterminate={selectedFileKeys.length > 0 && selectedFileKeys.length < getFilteredAndSortedFiles().length}
          onChange={e => handleSelectAll(e.target.checked)}
        >
          文件名
        </Checkbox>
      ),
      dataIndex: 'file_name',
      key: 'file_name',
      width: '400px',
      render: (text: string, record: FileProcessingResponse) => (
        <Space>
          <Checkbox
            checked={selectedFileKeys.includes(record.file_id)}
            onChange={e => handleFileSelect(record.file_id, e.target.checked)}
          />
          <FileOutlined />
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source_type',
      key: 'source_type',
      width: '300px',
      render: (sourceType: string, record: FileProcessingResponse) => (
        <Space direction='vertical' size={4}>
          {getSourceTag(record)}
          <Text type='secondary' style={{ fontSize: 11 }}>
            {record.source_id}
          </Text>
        </Space>
      ),
    },
    {
      title: '文件类型',
      dataIndex: 'file_type',
      key: 'file_type',
      width: '100px',
      render: (fileType: string, record: FileProcessingResponse) => {
        if (isAudioFile(record)) {
          return (
            <Tag color='purple' size='small'>
              音频
            </Tag>
          );
        } else if (isTextFile(record)) {
          return (
            <Tag color='orange' size='small'>
              文本
            </Tag>
          );
        }
        return (
          <Tag color='default' size='small'>
            {fileType || '其他'}
          </Tag>
        );
      },
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: '100px',
      render: (size: number) => {
        if (!size) return '-';
        if (size < 1024) return `${size}B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`;
        return `${(size / 1024 / 1024).toFixed(1)}MB`;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: '120px',
      render: (status: string, record: FileProcessingResponse) => {
        const statusDisplay = getFileStatusDisplay(status);

        // 特殊处理wait状态
        if (status === 'wait' && record.source_type === 'ftp') {
          return <Badge status='default' text='待转换' />;
        }

        return <Badge status={statusDisplay.color} text={statusDisplay.text} />;
      },
    },
    {
      title: '处理器/操作',
      key: 'actions',
      width: '400px',
      render: (_, record: FileProcessingResponse) => {
        const isText = isTextFile(record);
        const isAudio = isAudioFile(record);
        const isCompleted = record.status === 'success';
        const isSTT = record.source_type === 'stt';
        const isFTP = record.source_type === 'ftp';

        return (
          <Space direction='vertical' size={4}>
            {/* 处理器标签 */}
            <div>
              {/* FTP扫描文件 */}
              {isFTP && (
                <Tag size='small' color='blue'>
                  文件扫描
                </Tag>
              )}

              {/* 语音转换文件 - 音频类型 */}
              {isAudio && isSTT && (
                <Tag size='small' color='purple'>
                  语音转换
                </Tag>
              )}

              {/* 语音转换文件 - 文本类型，显示知识库处理状态 */}
              {isText && isSTT && (
                <Tag size='small' color='orange'>
                  知识库处理
                </Tag>
              )}
            </div>

            {/* 操作按钮 */}
            <Space size='small'>
              {/* 文本文件且已完成 - 显示知识库跳转按钮 */}
              {isText && isCompleted && (
                <Tooltip title='跳转到知识库'>
                  <Button
                    size='small'
                    type='primary'
                    icon={<DatabaseOutlined />}
                    onClick={() => handleKnowledgeJump(record)}
                    style={{
                      backgroundColor: '#52c41a',
                      borderColor: '#52c41a',
                    }}
                  >
                    知识库
                  </Button>
                </Tooltip>
              )}

              {/* 文本文件但未完成 - 显示禁用的知识库按钮 */}
              {isText && !isCompleted && (
                <Tooltip title='文件处理完成后可跳转知识库'>
                  <Button size='small' type='default' icon={<DatabaseOutlined />} disabled style={{ color: '#999' }}>
                    知识库
                  </Button>
                </Tooltip>
              )}

              {/* 下载按钮 - 所有文件都显示 */}
              <Tooltip title='下载文件'>
                <Button
                  size='small'
                  type='text'
                  icon={<DownloadOutlined />}
                  onClick={() => handleDownloadFile(record)}
                />
              </Tooltip>

              {/* 重新处理按钮 - 失败或等待状态的文件显示 */}
              {(record.status === 'failed' || record.status === 'wait') && (
                <Tooltip title='重新处理'>
                  <Button
                    size='small'
                    type='text'
                    icon={<ReloadOutlined />}
                    onClick={() => handleBatchReprocess([record.file_id])}
                    style={{ color: '#fa8c16' }}
                  />
                </Tooltip>
              )}
            </Space>
          </Space>
        );
      },
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: '200px',
      render: (time: string) => (time ? new Date(time).toLocaleString() : '-'),
    },
  ];

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
            {enabledFileTypes.slice(0, 3).map(type => (
              <Tag key={type.extension} size='small' style={{ marginBottom: 2 }}>
                {type.extension}
              </Tag>
            ))}
            {enabledFileTypes.length > 3 && (
              <Tooltip
                title={enabledFileTypes
                  .slice(3)
                  .map(t => t.extension)
                  .join(', ')}
              >
                <Tag size='small' style={{ marginBottom: 2 }}>
                  +{enabledFileTypes.length - 3}
                </Tag>
              </Tooltip>
            )}
            <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>(全局配置: {enabledFileTypes.length}个)</div>
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
      dataIndex: 'source_id',
      key: 'source_id',
      width: '400px',
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: '400px',
      render: (size: number) => {
        if (!size) return '-';
        if (size < 1024) return `${size}B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`;
        return `${(size / 1024 / 1024).toFixed(1)}MB`;
      },
    },
    {
      title: '扫描时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: '400px',
      render: (time: string) => (time ? new Date(time).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: '400px',
      render: (_: any, record: FileProcessingResponse) => (
        <Space size='small'>
          <Tooltip title='下载'>
            <Button size='small' type='text' icon={<DownloadOutlined />} onClick={() => handleDownloadFile(record)} />
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
          checked={
            selectedFileKeys.length === getFilteredAndSortedFiles().length && getFilteredAndSortedFiles().length > 0
          }
          indeterminate={selectedFileKeys.length > 0 && selectedFileKeys.length < getFilteredAndSortedFiles().length}
          onChange={e => handleSelectAll(e.target.checked)}
        >
          文件名
        </Checkbox>
      ),
      dataIndex: 'file_name',
      key: 'file_name',
      width: '500px',
      render: (text: string, record: FileProcessingResponse) => (
        <Space>
          <Checkbox
            checked={selectedFileKeys.includes(record.file_id)}
            onChange={e => handleFileSelect(record.file_id, e.target.checked)}
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
        if (!size) return '-';
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
      render: (status: string) => {
        const statusDisplay = getFileStatusDisplay(status);
        return <Badge status={statusDisplay.color} text={statusDisplay.text} />;
      },
    },
    {
      title: '处理器',
      dataIndex: 'source_type',
      key: 'source_type',
      width: '400px',
      render: (sourceType: string, record: FileProcessingResponse) => {
        if (sourceType === 'stt') {
          const isCompleted = record.status === 'success';
          return (
            <div>
              <Tag key='audio_to_text' size='small' style={{ marginBottom: 2 }}>
                语音转换
              </Tag>
              <Tag
                key='knowledge_processor'
                size='small'
                style={{
                  marginBottom: 2,
                  cursor: isCompleted ? 'pointer' : 'default',
                  backgroundColor: isCompleted ? '#f6ffed' : '#f5f5f5',
                  borderColor: isCompleted ? '#52c41a' : '#d9d9d9',
                  color: isCompleted ? '#52c41a' : '#666',
                }}
                onClick={() => {
                  if (isCompleted) {
                    handleKnowledgeJump(record);
                  }
                }}
                icon={<DatabaseOutlined />}
              >
                知识库{isCompleted && ' ↗'}
              </Tag>
            </div>
          );
        }
        return <Tag size='small'>文件扫描</Tag>;
      },
    },
    {
      title: '处理时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: '400px',
      render: (time: string) => (time ? new Date(time).toLocaleString() : '-'),
    },
  ];


  


  // 处理映射变更
    // 修改扫描配置选择
  const handleMappingScanConfigChange = (index: number, scanConfigName: string) => {
    setKnowledgeMappings(prev =>
      prev.map((mapping, i) => (i === index ? { ...mapping, scan_config_name: scanConfigName } : mapping)),
    );
  };

  // 保存映射配置
const handleSaveKnowledgeMappings = async () => {
  // 验证映射配置 - 移除enabled检查
  const invalidMappings = knowledgeMappings.filter(m => !m.scan_config_name || !m.knowledge_base_id);

  if (invalidMappings.length > 0) {
    message.warning('请完善所有映射配置信息');
    return;
  }

  // 检查是否有重复的扫描配置
  const scanConfigNames = knowledgeMappings
    .filter(m => m.scan_config_name)
    .map(m => m.scan_config_name);

  const duplicates = scanConfigNames.filter((name, index) => scanConfigNames.indexOf(name) !== index);

  if (duplicates.length > 0) {
    message.warning(`扫描配置 "${duplicates[0]}" 存在重复映射`);
    return;
  }

  try {
    setLoading(true);
    // 所有映射都设置为enabled: true
    const validMappings = knowledgeMappings
      .filter(m => m.scan_config_name && m.knowledge_base_id)
      .map(m => ({ ...m, enabled: true }));

    const [error] = await apiInterceptors(
      saveKnowledgeBaseMappings({
        mappings: validMappings,
      }),
    );

    if (!error) {
      message.success(`知识库映射配置保存成功 (${validMappings.length}个映射)`);
    }
  } catch (error) {
    console.error('保存映射配置失败:', error);
    message.error('保存映射配置失败');
  } finally {
    setLoading(false);
  }
};


// 1. 修改删除映射函数，调用后端接口
const handleRemoveMapping = async (index: number) => {
  const mapping = knowledgeMappings[index];
  
  // 如果映射有scan_config_name，说明可能已经保存到后端，需要调用删除接口
  if (mapping.scan_config_name) {
    try {
      setLoading(true);
      const [error] = await apiInterceptors(
        deleteKnowledgeBaseMappings({
          mappings: [mapping]
        })
      );
      
      if (!error) {
        message.success(`映射配置 "${mapping.scan_config_name}" 删除成功`);
        // 删除成功后从本地状态中移除
        setKnowledgeMappings(prev => prev.filter((_, i) => i !== index));
      }
    } catch (error) {
      console.error('删除映射配置失败:', error);
      message.error('删除映射配置失败');
    } finally {
      setLoading(false);
    }
  } else {
    // 如果没有scan_config_name，说明是新添加未保存的配置，直接从本地删除
    setKnowledgeMappings(prev => prev.filter((_, i) => i !== index));
    message.info('已删除未保存的映射配置');
  }
};

  // 修改扫描配置选择


  // 修改知识库选择
  const handleMappingKnowledgeBaseChange = (index: number, spaceId: number) => {
    const kb = knowledgeBases.find(k => k.space_id === spaceId);
    setKnowledgeMappings(prev =>
      prev.map((mapping, i) =>
        i === index
          ? {
              ...mapping,
              knowledge_base_id: spaceId.toString(), // 存储space_id到knowledge_base_id字段
              knowledge_base_name: kb?.param || '', // 存储param到knowledge_base_name字段
            }
          : mapping,
      ),
    );
  };

  const handleAddMapping = () => {
  setKnowledgeMappings(prev => [
    ...prev,
    {
      scan_config_name: '',
      knowledge_base_id: '',
      knowledge_base_name: '',
      enabled: true, // 默认设置为true
    },
  ]);
};


  return (
    <div style={{ padding: '0 24px' }}>
      <Title level={2} style={{ marginBottom: 24 }}>
        <ToolOutlined /> 自动化加工模块
      </Title>

      <Space direction='vertical' style={{ width: '100%' }} size={24}>
        {/* 统一文件列表 */}
        <Card
          title={
            <Space>
              <FileOutlined />
              <span>文件管理</span>
              <Tag color='blue'>{allFiles.length} 个文件</Tag>
              <Tag color='cyan'>{allFiles.filter(f => f.source_type === 'ftp').length} 个扫描文件</Tag>
              <Tag color='green'>{allFiles.filter(f => f.source_type === 'stt').length} 个转换文件</Tag>
            </Space>
          }
          size='small'
          extra={
            <Space>
              <Button size='small' icon={<SettingOutlined />} onClick={() => setScanConfigModalVisible(true)}>
                扫描配置
              </Button>
              <Button size='small' icon={<ToolOutlined />} onClick={() => setConfigCenterModalVisible(true)}>
                加工配置
              </Button>
              <Text type='secondary' style={{ fontSize: 12 }}>
                <ClockCircleOutlined /> FTP文件: {statistics?.source_type_statistics?.ftp || 0} | 转换文件:{' '}
                {statistics?.source_type_statistics?.stt || 0}
              </Text>
            </Space>
          }
          style={{ minHeight: 600 }}
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
                  <Button size='small' type='link' onClick={() => setTaskConfigVisible(true)} style={{ padding: 0 }}>
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

          {/* 语音转换控制 */}
          <div style={{ marginBottom: 16, padding: '12px 16px', backgroundColor: '#f0f8ff', borderRadius: 4 }}>
            <Row justify='space-between' align='middle'>
              <Col>
                <Space>
                  <SoundOutlined style={{ color: '#1890ff' }} />
                  <Text strong>语音转换处理器</Text>
                  <Badge
                    status={processorsStatus?.processors?.audio_to_text?.consuming ? 'processing' : 'default'}
                    text={processorsStatus?.processors?.audio_to_text?.consuming ? '运行中' : '已停止'}
                  />
                </Space>
              </Col>
              <Col>
                <Switch
                  checked={processorsStatus?.processors?.audio_to_text?.consuming || false}
                  onChange={checked => handleAudioProcessorControl(checked ? 'start' : 'stop')}
                  loading={audioProcessorLoading}
                  checkedChildren='运行'
                  unCheckedChildren='停止'
                />
              </Col>
            </Row>
          </div>

          {/* 知识库处理控制 */}
          <div style={{ marginBottom: 16, padding: '12px 16px', backgroundColor: '#f6ffed', borderRadius: 4 }}>
            <Row justify='space-between' align='middle'>
              <Col>
                <Space>
                  <DatabaseOutlined style={{ color: '#52c41a' }} />
                  <Text strong>知识库处理器</Text>
                  <Badge
                    status={processorsStatus?.processors?.knowledge_processor?.consuming ? 'processing' : 'default'}
                    text={processorsStatus?.processors?.knowledge_processor?.consuming ? '运行中' : '已停止'}
                  />
                </Space>
              </Col>
              <Col>
                <Switch
                  checked={processorsStatus?.processors?.knowledge_processor?.consuming || false}
                  onChange={checked => handleKnowledgeProcessorControl(checked ? 'start' : 'stop')}
                  loading={knowledgeProcessorLoading}
                  checkedChildren='运行'
                  unCheckedChildren='停止'
                />
              </Col>
            </Row>
          </div>

          {/* 文件统计信息 */}
          <div style={{ marginBottom: 16, padding: '12px 16px', backgroundColor: '#f5f5f5', borderRadius: 4 }}>
            <Row gutter={16}>
              <Col span={8}>
                <div style={{ textAlign: 'center', padding: '8px', backgroundColor: '#f0f9ff', borderRadius: 4 }}>
                  <div style={{ fontSize: 16, fontWeight: 'bold', color: '#1890ff' }}>
                    {statistics?.source_type_statistics?.ftp || 0}
                  </div>
                  <div style={{ fontSize: 12, color: '#666' }}>FTP扫描文件</div>
                </div>
              </Col>
              <Col span={8}>
                <div style={{ textAlign: 'center', padding: '8px', backgroundColor: '#f6ffed', borderRadius: 4 }}>
                  <div style={{ fontSize: 16, fontWeight: 'bold', color: '#52c41a' }}>
                    {statistics?.source_type_statistics?.stt || 0}
                  </div>
                  <div style={{ fontSize: 12, color: '#666' }}>语音转换文件</div>
                </div>
              </Col>
              <Col span={8}>
                <div style={{ textAlign: 'center', padding: '8px', backgroundColor: '#fff7e6', borderRadius: 4 }}>
                  <div style={{ fontSize: 16, fontWeight: 'bold', color: '#fa8c16' }}>
                    {statistics?.status_statistics?.success || 0}
                  </div>
                  <div style={{ fontSize: 12, color: '#666' }}>处理成功</div>
                </div>
              </Col>
            </Row>
          </div>

          {/* 文件操作栏 */}
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
                    onClick={handleClearAllFiles}
                    disabled={allFiles.length === 0}
                  >
                    清空记录 ({allFiles.length})
                  </Button>
                </Space>
              </Col>
              <Col>
                <Space>
                  <Button type='primary' size='small' icon={<DownloadOutlined />} onClick={handleBatchDownload}>
                    下载 ({selectedFileKeys.length})
                  </Button>
                  <Button type='default' size='small' icon={<ReloadOutlined />} onClick={handleBatchReprocess}>
                    重新处理 ({selectedFileKeys.length})
                  </Button>
                  <Button danger size='small' icon={<DeleteOutlined />} onClick={handleBatchDelete}>
                    删除 ({selectedFileKeys.length})
                  </Button>
                  <Button
                    size='small'
                    type={filesAutoRefresh ? 'primary' : 'default'}
                    icon={<SyncOutlined spin={filesAutoRefresh} />}
                    onClick={() => {
                      setFilesAutoRefresh(!filesAutoRefresh);
                      message.info(filesAutoRefresh ? '自动刷新已停止' : '自动刷新已启用 (1秒间隔)');
                    }}
                  >
                    {filesAutoRefresh ? '停止自动刷新' : '启用自动刷新'}
                  </Button>
                  <Button
                    size='small'
                    icon={<ReloadOutlined />}
                    onClick={() => {
                      loadScanConfigs();
                      loadStatistics();
                      loadAllFiles();
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

          {/* 过滤和排序控制 */}
          <div
            style={{
              marginBottom: 16,
              padding: '8px 12px',
              backgroundColor: '#f0f9ff',
              borderRadius: 4,
              border: '1px solid #bae6fd',
            }}
          >
            <Row gutter={8} align='middle'>
              <Col span={5}>
                <Input
                  size='small'
                  placeholder='搜索文件名'
                  prefix={<SearchOutlined />}
                  value={fileFilters.nameSearch}
                  onChange={e => setFileFilters(prev => ({ ...prev, nameSearch: e.target.value }))}
                  allowClear
                />
              </Col>
              <Col span={3}>
                <Select
                  size='small'
                  placeholder='状态筛选'
                  value={fileFilters.status}
                  onChange={value => setFileFilters(prev => ({ ...prev, status: value }))}
                  style={{ width: '100%' }}
                  allowClear
                >
                  <Option value='wait'>待处理</Option>
                  <Option value='processing'>处理中</Option>
                  <Option value='downloading'>下载中</Option>
                  <Option value='success'>已完成</Option>
                  <Option value='failed'>失败</Option>
                  <Option value='retrying'>重试中</Option>
                </Select>
              </Col>
              <Col span={3}>
                <Select
                  size='small'
                  placeholder='来源筛选'
                  value={fileFilters.source_type}
                  onChange={value => setFileFilters(prev => ({ ...prev, source_type: value }))}
                  style={{ width: '100%' }}
                  allowClear
                >
                  <Option value='ftp'>FTP扫描</Option>
                  <Option value='stt'>语音转换</Option>
                </Select>
              </Col>
              <Col span={3}>
                <Select
                  size='small'
                  placeholder='文件类型'
                  value={fileFilters.file_type}
                  onChange={value => setFileFilters(prev => ({ ...prev, file_type: value }))}
                  style={{ width: '100%' }}
                  allowClear
                >
                  <Option value='wav'>音频文件</Option>
                  <Option value='txt'>文本文件</Option>
                  <Option value='pdf'>PDF文档</Option>
                  <Option value='doc'>Word文档</Option>
                </Select>
              </Col>
              <Col span={4}>
                <Select
                  size='small'
                  placeholder='排序方式'
                  value={`${fileSorting.field}_${fileSorting.order}`}
                  onChange={value => {
                    const [field, order] = value.split('_');
                    setFileSorting({ field, order });
                  }}
                  style={{ width: '100%' }}
                >
                  <Option value='file_name_asc'>文件名 ↑</Option>
                  <Option value='file_name_desc'>文件名 ↓</Option>
                  <Option value='size_asc'>大小 ↑</Option>
                  <Option value='size_desc'>大小 ↓</Option>
                  <Option value='created_at_desc'>时间 ↓</Option>
                  <Option value='created_at_asc'>时间 ↑</Option>
                  <Option value='source_type_asc'>来源 ↑</Option>
                  <Option value='source_type_desc'>来源 ↓</Option>
                </Select>
              </Col>
              <Col span={2}>
                <Button size='small' icon={<FilterOutlined />} onClick={resetFilters} style={{ width: '100%' }}>
                  重置
                </Button>
              </Col>
              <Col span={4}>
                <Text type='secondary' style={{ fontSize: 11 }}>
                  共 {getFilteredAndSortedFiles().length} 条 | 已选 {selectedFileKeys.length} 条
                </Text>
              </Col>
            </Row>
          </div>

          <Table
            dataSource={getFilteredAndSortedFiles()}
            columns={fileListColumns}
            rowKey='file_id'
            size='small'
            pagination={{
              pageSize: 20,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条/共 ${total} 条`,
              pageSizeOptions: ['10', '20', '50', '100'],
            }}
            scroll={{ y: 400 }}
            loading={filesLoading}
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
              <Button
                icon={<ReloadOutlined />}
                onClick={() => {
                  loadScanConfigs();
                  loadAllFiles(); // 替换原来的多个加载函数
                  loadStatistics();
                }}
              >
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
    {/* 现有的文件类型支持 */}
    <Form.Item label='支持文件类型' style={{ marginBottom: 16 }}>
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

    {/* 扫描配置-知识库映射 */}
    <Form.Item
      label={
        <Space>
          <span>扫描配置-知识库映射</span>
          <Tag color='blue' size='small'>
            {knowledgeMappings.length}个映射配置
          </Tag>
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      {/* 映射列表 */}
      <div style={{ marginBottom: 8 }}>
        {knowledgeMappings.map((mapping, index) => (
          <div
            key={index}
            style={{
              display: 'flex',
              alignItems: 'center',
              marginBottom: 8,
              padding: '8px 12px',
              backgroundColor: '#f9f9f9',
              borderRadius: 4,
              border: '1px solid #e8e8e8',
            }}
          >
            <div style={{ flex: 1, marginRight: 8 }}>
              <Select
                placeholder='选择扫描配置'
                size='small'
                style={{ width: '100%' }}
                value={mapping.scan_config_name}
                onChange={value => handleMappingScanConfigChange(index, value)}
              >
                {scanConfigs.map(config => (
                  <Option key={config.name} value={config.name}>
                    <Space>
                      <Tag color={config.type === 'ftp' ? 'blue' : 'green'} size='small'>
                        {config.type === 'ftp' ? 'FTP' : '本地'}
                      </Tag>
                      <span>{config.name}</span>
                      {config.type === 'ftp' && config.config?.remote_dir && (
                        <span style={{ color: '#666', fontSize: '11px' }}>
                          ({config.config.remote_dir})
                        </span>
                      )}
                    </Space>
                  </Option>
                ))}
              </Select>
            </div>

            <div style={{ flex: 1, marginRight: 8 }}>
              <Select
                placeholder='选择知识库'
                size='small'
                style={{ width: '100%' }}
                value={mapping.knowledge_base_id ? parseInt(mapping.knowledge_base_id) : undefined}
                onChange={value => handleMappingKnowledgeBaseChange(index, value)}
              >
                {knowledgeBases.map(kb => (
                  <Option key={kb.space_id} value={kb.space_id}>
                    <Space>
                      <Tag size='small' color='geekblue'>
                        知识库
                      </Tag>
                      <span>{kb.param}</span>
                    </Space>
                  </Option>
                ))}
              </Select>
            </div>

            {/* 移除了启用开关，直接显示删除按钮 */}
            <Button
              size='small'
              type='text'
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleRemoveMapping(index)}
              loading={loading}
            />
          </div>
        ))}
      </div>

      {/* 添加映射按钮 */}
      <Button
        size='small'
        type='dashed'
        icon={<PlusOutlined />}
        onClick={handleAddMapping}
        style={{ width: '100%' }}
      >
        添加映射配置
      </Button>
    </Form.Item>

    {/* 保存配置按钮 */}
    <Form.Item style={{ marginBottom: 0 }}>
      <Row gutter={8}>
        <Col span={12}>
          <Button
            type='primary'
            size='small'
            onClick={handleSaveKnowledgeMappings}
            loading={loading}
            style={{ width: '100%' }}
            icon={<DatabaseOutlined />}
          >
            保存知识库配置
          </Button>
        </Col>
        <Col span={12}>
          <Button
            type='default'
            size='small'
            icon={<DatabaseOutlined />}
            onClick={() => {
              window.open('/construct/knowledge', '_blank');
            }}
            style={{ width: '100%' }}
          >
            打开知识库管理
          </Button>
        </Col>
      </Row>
    </Form.Item>
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
            fileTypes: globalFileTypes.filter(type => type.enabled).map(type => type.extension),
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
              <Button onClick={() => setFileTypeModalVisible(false)}>取消</Button>
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
            onFinish={handleSaveFtpConfig} // 统一使用这个函数
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
                    currentForm
                      .validateFields()
                      .then(values => {
                        handleTestSingleFtpConfig(values, true); // true表示来自表单数据
                      })
                      .catch(errorInfo => {
                        message.warning('请先完善FTP配置信息再进行测试');
                      });
                  }}
                  loading={loading}
                  type='dashed'
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
