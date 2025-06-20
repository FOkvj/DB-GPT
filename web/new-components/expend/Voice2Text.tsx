import {
  CheckCircleOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  LoadingOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  SoundOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  Avatar,
  Button,
  Card,
  Col,
  Input,
  List,
  Modal,
  Progress,
  Row,
  Select,
  Slider,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table/interface';
import type { UploadFile, UploadProps } from 'antd/es/upload/interface';
import React, { useEffect, useRef, useState } from 'react';

// Import API functions and apiInterceptors
import { apiInterceptors } from '@/client/api';
import {
  VoiceProcessResultFile,
  VoiceProfile,
  VoiceSample,
  addVoiceSample,
  batchRegisterVoiceProfiles,
  clearVoiceProfiles,
  createVoiceProfile,
  deleteVoiceProfile,
  deleteVoiceSample,
  getVoiceProfiles,
  getVoiceSample,
  postProcessVoiceToText,
  updateVoiceProfile,
} from '@/client/api/expend/voice';

const { Text } = Typography;
const { Dragger } = Upload;
const { Option } = Select;

// Available language options
const languageOptions = [
  { value: 'zh-CN', label: '中文 (简体)' },
  { value: 'en-US', label: '英语 (美国)' },
];

// Available model options
const modelOptions = [
  { value: 'default', label: '默认模型' },
  { value: 'paraformer-zh', label: '中文专用模型' },
];

const VoiceModule: React.FC = () => {
  // State for Voice to Text module
  const [audioFiles, setAudioFiles] = useState<UploadFile[]>([]);
  const [voiceProcessing, setVoiceProcessing] = useState<boolean>(false);
  const [voiceProcessResults, setVoiceProcessResults] = useState<VoiceProcessResultFile[]>([]);
  const [voiceProfiles, setVoiceProfiles] = useState<VoiceProfile[]>([]);
  const [activeVoiceTab, setActiveVoiceTab] = useState<string>('1');
  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState<string>('');
  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([]);
  const [playingSampleId, setPlayingSampleId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [messageApi, contextHolder] = message.useMessage();
  const audioRef = useRef<HTMLAudioElement>(null);

  // Configuration states
  const [language, setLanguage] = useState<string>('zh-CN');
  const [model, setModel] = useState<string>('default');
  const [enablePunctuation, setEnablePunctuation] = useState<boolean>(true);
  const [speakerDiarization, setSpeakerDiarization] = useState<boolean>(true);
  const [autoRegister, setAutoRegister] = useState<boolean>(true);
  const [matchingThreshold, setMatchingThreshold] = useState<number>(0.5);
  const [hotwords, setHotwords] = useState<string>('');
  const [batchRegisterPath, setBatchRegisterPath] = useState<string>('');
  const [isBatchModalVisible, setIsBatchModalVisible] = useState<boolean>(false);

  // Fetch voice profiles on component mount
  useEffect(() => {
    fetchVoiceProfiles();
  }, []);

  // Fetch voice profiles from API
  const fetchVoiceProfiles = async () => {
    const [err, data] = await apiInterceptors(getVoiceProfiles(true));

    if (err) {
      messageApi.error(`获取声纹列表失败: ${err.message}`);
      return;
    }

    if (data && data.profiles) {
      setVoiceProfiles(data.profiles);
    }
  };

  // Audio file upload props
  const audioProps: UploadProps = {
    name: 'audio',
    multiple: true,
    accept: '.mp3,.wav,.ogg,.m4a',
    beforeUpload: (file: UploadFile) => {
      setAudioFiles(prev => [...prev, file]);
      // Initialize upload progress
      setUploadProgress(prev => ({
        ...prev,
        [file.uid]: 0,
      }));
      return false;
    },
    onRemove: (file: UploadFile) => {
      setAudioFiles(prev => prev.filter(item => item.uid !== file.uid));
      setVoiceProcessResults(prev => prev.filter(item => item.fileUid !== file.uid));
      // Remove progress tracking
      setUploadProgress(prev => {
        const newProgress = { ...prev };
        delete newProgress[file.uid];
        return newProgress;
      });
    },
    fileList: audioFiles,
  };

  // 清除所有音频文件
  const clearAllAudioFiles = (): void => {
    setAudioFiles([]);
    setVoiceProcessResults([]);
    setUploadProgress({});
    messageApi.success('已清除所有音频文件');
  };

  // Process voice to text with API integration
  const handleVoiceProcess = async (): Promise<void> => {
    if (audioFiles.length === 0) {
      messageApi.error('请先上传音频文件');
      return;
    }

    setVoiceProcessing(true);

    try {
      // Processing progress message
      messageApi.loading({
        content: `正在处理 ${audioFiles.length} 个音频文件...`,
        key: 'voice-process',
        duration: 0,
      });

      // Create FormData for file upload
      const formData = new FormData();

      // Add all audio files to FormData
      audioFiles.forEach(file => {
        formData.append('files', file as any);
      });

      // Initialize progress for each file
      const initialProgress: Record<string, number> = {};
      audioFiles.forEach(file => {
        initialProgress[file.uid] = 0;
      });
      setUploadProgress(initialProgress);

      // Call processing API with file upload
      const [err, data] = await apiInterceptors(
        postProcessVoiceToText({
          language: language,
          model: model,
          enablePunctuation: enablePunctuation,
          speakerDiarization: speakerDiarization,
          auto_register: autoRegister,
          threshold: matchingThreshold,
          hotword: hotwords,
          fileData: formData,
          config: {
            timeout: 1000 * 60 * 5, // 5 minutes timeout
            onUploadProgress: (progressEvent: any): void => {
              const progress = Math.ceil((progressEvent.loaded / (progressEvent.total || 0)) * 100);

              // Update progress for all files
              const updatedProgress: Record<string, number> = {};
              audioFiles.forEach(file => {
                updatedProgress[file.uid] = progress;
              });
              setUploadProgress(updatedProgress);

              // Update loading message
              messageApi.loading({
                content: `正在处理文件... ${progress}%`,
                key: 'voice-process',
                duration: 0,
              });
            },
          },
        }),
      );

      // Close processing message
      messageApi.destroy('voice-process');

      if (err) {
        messageApi.error(`处理语音转文字失败: ${err.message}`);
        // Create fallback result for error display
        const fallbackResults: VoiceProcessResultFile[] = audioFiles.map(file => ({
          fileUid: file.uid,
          fileName: file.name || '',
          text: '',
          processingTime: 0,
          success: false,
          error: err.message || '处理失败',
        }));
        setVoiceProcessResults(fallbackResults);
        return;
      }

      // Processing success
      if (data) {
        setVoiceProcessResults(data.files);

        // Check if new voice profiles were auto-registered
        if (data.autoRegisteredSpeakers && data.autoRegisteredSpeakers > 0) {
          messageApi.success(`已自动注册 ${data.autoRegisteredSpeakers} 个新声纹`);
          // Refresh voice profiles list
          fetchVoiceProfiles();
        }

        // Display result message
        if (data.failedFiles === 0) {
          messageApi.success(`已成功处理 ${data.fileCount} 个音频文件！`);
        } else if (data.processedFiles > 0) {
          messageApi.warning(
            `已处理 ${data.fileCount} 个音频文件，成功 ${data.processedFiles} 个，失败 ${data.failedFiles} 个`,
          );
        } else {
          messageApi.error(`所有音频处理失败`);
        }
      }
    } catch (error: any) {
      console.error('Processing error:', error);
      messageApi.error(`处理音频文件时出错: ${error.message}`);

      // Create fallback results for error display
      const fallbackResults: VoiceProcessResultFile[] = audioFiles.map(file => ({
        fileUid: file.uid,
        fileName: file.name || '',
        text: '',
        processingTime: 0,
        success: false,
        error: error.message || '处理失败',
      }));
      setVoiceProcessResults(fallbackResults);
    } finally {
      setVoiceProcessing(false);
    }
  };

  // Download text result for a specific file
  const downloadTextResult = (result: VoiceProcessResultFile | undefined): void => {
    if (!result) return;

    const element: HTMLAnchorElement = document.createElement('a');
    const file: Blob = new Blob([result.text], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = `${result.fileName}-转换结果.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);

    messageApi.success('文本文件下载成功！');
  };

  // Download all text results
  const downloadAllTextResults = (): void => {
    if (voiceProcessResults.length === 0) return;

    // Create a zip-like text file with all results
    const allTexts = voiceProcessResults.map(result => `=== ${result.fileName} ===\n${result.text}\n\n`).join('');

    const element: HTMLAnchorElement = document.createElement('a');
    const file: Blob = new Blob([allTexts], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = `所有语音转换结果.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);

    messageApi.success('所有转换结果已下载');
  };

  // Voice profile management - Add new profile
  const addNewVoiceProfile = async (): Promise<void> => {
    try {
      const newName = `用户${voiceProfiles.length + 1}`;
      const [err, data] = await apiInterceptors(createVoiceProfile(newName));

      if (err) {
        messageApi.error(`添加声纹失败: ${err.message}`);
        return;
      }

      if (data) {
        setVoiceProfiles([...voiceProfiles, data]);
        messageApi.success('已添加新声纹');
      }
    } catch (error: any) {
      messageApi.error(`添加声纹时出错: ${error.message}`);
    }
  };

  // Start editing profile name
  const startEditingProfileName = (profile: VoiceProfile): void => {
    setEditingProfileId(profile.id);
    setEditingName(profile.name);
  };

  // Save profile name
  const saveProfileName = async (): Promise<void> => {
    if (editingProfileId !== null) {
      try {
        const [err, data] = await apiInterceptors(updateVoiceProfile(editingProfileId, editingName));

        if (err) {
          messageApi.error(`更新声纹名称失败: ${err.message}`);
          return;
        }

        if (data) {
          setVoiceProfiles(voiceProfiles.map(profile => (profile.id === editingProfileId ? data : profile)));
          messageApi.success('名称已更新');
        }
      } catch (error: any) {
        messageApi.error(`更新声纹名称时出错: ${error.message}`);
      } finally {
        setEditingProfileId(null);
        setEditingName('');
      }
    }
  };

  // Cancel editing profile name
  const cancelEditingProfileName = (): void => {
    setEditingProfileId(null);
    setEditingName('');
  };

  // Delete voice profile
  const deleteProfile = (profileId: string): void => {
    Modal.confirm({
      title: '删除声纹',
      content: '确定要删除这个声纹吗？此操作不可撤销。',
      onOk: async () => {
        try {
          const [err, data] = await apiInterceptors(deleteVoiceProfile(profileId));

          if (err) {
            messageApi.error(`删除声纹失败: ${err.message}`);
            return;
          }

          if (data && data.success) {
            setVoiceProfiles(voiceProfiles.filter(profile => profile.id !== profileId));
            messageApi.success('声纹已删除');
          }
        } catch (error: any) {
          messageApi.error(`删除声纹时出错: ${error.message}`);
        }
      },
    });
  };

  // Delete voice sample
  const deleteSample = async (sampleId: string): Promise<void> => {
    try {
      const [err, data] = await apiInterceptors(deleteVoiceSample(sampleId));

      if (err) {
        messageApi.error(`删除声纹样本失败: ${err.message}`);
        return;
      }

      if (data && data.success) {
        // Update the profiles list by removing the deleted sample
        setVoiceProfiles(
          voiceProfiles.map(profile => ({
            ...profile,
            samples: profile.samples.filter(s => s.id !== sampleId),
          })),
        );
        messageApi.success('声纹样本已删除');
      }
    } catch (error: any) {
      messageApi.error(`删除声纹样本时出错: ${error.message}`);
    }
  };

  // Add voice sample
  const handleAddSample = (profileId: string, file: UploadFile): void => {
    Modal.confirm({
      title: '添加声纹样本',
      content: `确定要将文件 ${file.name} 添加为声纹样本吗？`,
      onOk: async () => {
        try {
          // Create FormData for file upload
          const formData = new FormData();
          formData.append('file', file as any);

          const [err, data] = await apiInterceptors(addVoiceSample(profileId, formData));

          if (err) {
            messageApi.error(`添加声纹样本失败: ${err.message}`);
            return;
          }

          if (data) {
            // Update the profiles list with the new sample
            setVoiceProfiles(
              voiceProfiles.map(profile =>
                profile.id === profileId ? { ...profile, samples: [...profile.samples, data] } : profile,
              ),
            );
            messageApi.success('声纹样本已添加');
          }
        } catch (error: any) {
          messageApi.error(`添加声纹样本时出错: ${error.message}`);
        }
      },
    });
  };

  // Clear all voice profiles
  const handleClearAllProfiles = (): void => {
    Modal.confirm({
      title: '清除所有声纹',
      content: '确定要删除所有声纹数据吗？此操作不可撤销。',
      onOk: async () => {
        try {
          const [err, data] = await apiInterceptors(clearVoiceProfiles());

          if (err) {
            messageApi.error(`清除声纹失败: ${err.message}`);
            return;
          }

          if (data && data.success) {
            setVoiceProfiles([]);
            messageApi.success('所有声纹已清除');
          }
        } catch (error: any) {
          messageApi.error(`清除声纹时出错: ${error.message}`);
        }
      },
    });
  };

  // Batch register voice profiles
  const handleBatchRegisterProfiles = async (): Promise<void> => {
    if (!batchRegisterPath) {
      messageApi.error('请输入目录路径');
      return;
    }

    try {
      const [err, data] = await apiInterceptors(batchRegisterVoiceProfiles(batchRegisterPath));

      if (err) {
        messageApi.error(`批量注册声纹失败: ${err.message}`);
        return;
      }

      if (data && data.success) {
        fetchVoiceProfiles();
        messageApi.success(`已成功注册 ${Object.keys(data.registeredVoices || {}).length} 个声纹`);
        setIsBatchModalVisible(false);
      }
    } catch (error: any) {
      messageApi.error(`批量注册声纹时出错: ${error.message}`);
    }
  };

  // Play sample
  const playSample = (sampleId: string): void => {
    if (playingSampleId === sampleId) {
      // Stop playing
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      setPlayingSampleId(null);
      messageApi.info('停止播放');
    } else {
      // Get direct sample URL from the API
      const sampleUrl = getVoiceSample(sampleId);

      if (!sampleUrl) {
        messageApi.error('无法播放：样本URL未找到');
        return;
      }

      // Set audio source and play
      if (audioRef.current) {
        audioRef.current.src = sampleUrl;
        audioRef.current.onloadedmetadata = () => {
          if (audioRef.current) {
            audioRef.current
              .play()
              .then(() => {
                setPlayingSampleId(sampleId);
                messageApi.info('正在播放声纹样本');
              })
              .catch(error => {
                messageApi.error(`播放失败: ${error.message}`);
              });
          }
        };

        // Handle play ending
        audioRef.current.onended = () => {
          setPlayingSampleId(null);
        };
      }
    }
  };

  // 声纹样本表格列定义
  const sampleColumns: ColumnsType<VoiceSample> = [
    {
      title: '样本名称',
      dataIndex: 'name',
      key: 'name',
      width: '40%',
    },
    {
      title: '时长',
      dataIndex: 'duration',
      key: 'duration',
      width: '15%',
      align: 'center',
    },
    {
      title: '上传日期',
      dataIndex: 'uploadDate',
      key: 'uploadDate',
      width: '25%',
      align: 'center',
    },
    {
      title: '操作',
      key: 'action',
      width: '20%',
      align: 'center',
      render: (_, sample) => (
        <Space size='small'>
          <Button
            type='link'
            size='small'
            icon={playingSampleId === sample.id ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={() => playSample(sample.id)}
            style={{ padding: '4px 8px' }}
          >
            {playingSampleId === sample.id ? '停止' : '播放'}
          </Button>
          <Button
            type='link'
            size='small'
            danger
            icon={<DeleteOutlined />}
            onClick={() => deleteSample(sample.id)}
            style={{ padding: '4px 8px' }}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  // 用户列表表格列定义
  const profileColumns: ColumnsType<VoiceProfile> = [
    {
      title: '用户',
      key: 'user',
      width: '60%',
      render: (_, record) => (
        <Space align='center' style={{ width: '100%' }}>
          <Avatar icon={<UserOutlined />} />
          {editingProfileId === record.id ? (
            <Input
              value={editingName}
              onChange={e => setEditingName(e.target.value)}
              onPressEnter={saveProfileName}
              style={{ width: 200 }}
            />
          ) : (
            <div style={{ flex: 1 }}>
              <div>{record.name}</div>
              <Text type='secondary' style={{ fontSize: 12 }}>
                {record.samples.length} 个声纹样本
                {record.type === 'unnamed' && (
                  <Tag color='orange' style={{ marginLeft: 8 }}>
                    自动注册
                  </Tag>
                )}
              </Text>
            </div>
          )}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: '40%',
      align: 'center',
      render: (_, record) => (
        <Space size='small'>
          {editingProfileId === record.id ? (
            <>
              <Button type='link' size='small' onClick={saveProfileName}>
                保存
              </Button>
              <Button type='link' size='small' onClick={cancelEditingProfileName}>
                取消
              </Button>
            </>
          ) : (
            <Button type='link' size='small' icon={<EditOutlined />} onClick={() => startEditingProfileName(record)}>
              编辑
            </Button>
          )}
          <Button type='link' size='small' danger onClick={() => deleteProfile(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  // Upload props for voice samples
  const sampleUploadProps = {
    name: 'audio',
    multiple: false,
    accept: '.mp3,.wav,.ogg,.m4a',
    showUploadList: false,
    beforeUpload: (_file: UploadFile, _fileList: UploadFile[]) => {
      return false;
    },
  };

  const expandedRowRender = (record: VoiceProfile) => {
    return (
      <>
        <div
          style={{
            padding: '16px 40px',
            backgroundColor: '#f5f5f5',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Text style={{ fontSize: 16, fontWeight: 500 }}>声纹样本列表</Text>
          <Upload
            {...sampleUploadProps}
            onChange={info => {
              if (info.file.status !== 'uploading') {
                handleAddSample(record.id, info.file);
              }
            }}
          >
            <Button size='small' icon={<SoundOutlined />}>
              添加样本
            </Button>
          </Upload>
        </div>
        <Table
          columns={sampleColumns}
          dataSource={record.samples}
          rowKey='id'
          size='small'
          pagination={false}
          style={{
            backgroundColor: '#fff',
          }}
          tableLayout='fixed'
        />
      </>
    );
  };

  // Render configuration panel for voice processing
  const renderConfigurationPanel = () => {
    return (
      <Card
        title='识别配置'
        bordered={true}
        style={{
          borderRadius: 4,
          marginBottom: 16,
          boxShadow: 'none',
        }}
      >
        <Row gutter={[16, 16]}>
          <Col span={12}>
            <div style={{ marginBottom: 16 }}>
              <Text strong>识别语言：</Text>
              <Select
                value={language}
                onChange={value => setLanguage(value)}
                style={{ width: '100%', marginTop: 8 }}
                disabled={voiceProcessing}
              >
                {languageOptions.map(option => (
                  <Option key={option.value} value={option.value}>
                    {option.label}
                  </Option>
                ))}
              </Select>
            </div>
          </Col>

          <Col span={12}>
            <div style={{ marginBottom: 16 }}>
              <Text strong>识别模型：</Text>
              <Select
                value={model}
                onChange={value => setModel(value)}
                style={{ width: '100%', marginTop: 8 }}
                disabled={voiceProcessing}
              >
                {modelOptions.map(option => (
                  <Option key={option.value} value={option.value}>
                    {option.label}
                  </Option>
                ))}
              </Select>
            </div>
          </Col>

          <Col span={12}>
            <div style={{ marginBottom: 16 }}>
              <Text strong>启用标点符号：</Text>
              <div style={{ marginTop: 8 }}>
                <Switch
                  checked={enablePunctuation}
                  onChange={value => setEnablePunctuation(value)}
                  disabled={voiceProcessing}
                />
                <Text style={{ marginLeft: 8 }}>{enablePunctuation ? '开启' : '关闭'}</Text>
              </div>
            </div>
          </Col>

          <Col span={12}>
            <div style={{ marginBottom: 16 }}>
              <Text strong>启用说话人分离：</Text>
              <div style={{ marginTop: 8 }}>
                <Switch
                  checked={speakerDiarization}
                  onChange={value => {
                    setSpeakerDiarization(value);
                    if (!value) {
                      setAutoRegister(false);
                    }
                  }}
                  disabled={voiceProcessing}
                />
                <Text style={{ marginLeft: 8 }}>{speakerDiarization ? '开启' : '关闭'}</Text>
              </div>
            </div>
          </Col>

          <Col span={12}>
            <div style={{ marginBottom: 16 }}>
              <Text strong>是否自动注册声纹：</Text>
              <div style={{ marginTop: 8 }}>
                <Switch
                  checked={autoRegister}
                  onChange={value => setAutoRegister(value)}
                  disabled={voiceProcessing || !speakerDiarization}
                />
                <Text style={{ marginLeft: 8 }}>
                  {autoRegister ? '开启（自动注册未知声音）' : '关闭（仅识别已有声纹）'}
                </Text>
              </div>
            </div>
          </Col>

          <Col span={12}>
            <div style={{ marginBottom: 16 }}>
              <Text strong>声纹匹配阈值：</Text>
              <div style={{ display: 'flex', alignItems: 'center', marginTop: 8 }}>
                <Slider
                  min={0}
                  max={1}
                  step={0.01}
                  value={matchingThreshold}
                  onChange={value => setMatchingThreshold(value)}
                  style={{ flex: 1 }}
                  disabled={voiceProcessing}
                />
                <div style={{ width: 60, marginLeft: 16 }}>
                  <Input
                    value={matchingThreshold}
                    onChange={e => {
                      const value = parseFloat(e.target.value);
                      if (!isNaN(value) && value >= 0 && value <= 1) {
                        setMatchingThreshold(value);
                      }
                    }}
                    disabled={voiceProcessing}
                  />
                </div>
              </div>
              <Text type='secondary' style={{ fontSize: 12 }}>
                值越高，匹配要求越严格（0-1之间）
              </Text>
            </div>
          </Col>

          <Col span={24}>
            <div>
              <Text strong>热词列表：</Text>
              <Input.TextArea
                value={hotwords}
                onChange={e => setHotwords(e.target.value)}
                placeholder='请输入热词，多个热词用空格分隔'
                style={{ marginTop: 8 }}
                autoSize={{ minRows: 2, maxRows: 4 }}
                disabled={voiceProcessing}
              />
              <Text type='secondary' style={{ fontSize: 12 }}>
                添加与录音内容相关的关键词可提高识别准确率
              </Text>
            </div>
          </Col>
        </Row>
      </Card>
    );
  };

  // Batch register modal
  const renderBatchRegisterModal = () => {
    return (
      <Modal
        title='批量注册声纹'
        open={isBatchModalVisible}
        onOk={handleBatchRegisterProfiles}
        onCancel={() => setIsBatchModalVisible(false)}
      >
        <div style={{ marginBottom: 16 }}>
          <Text>输入包含音频文件的服务器目录路径：</Text>
          <Input
            value={batchRegisterPath}
            onChange={e => setBatchRegisterPath(e.target.value)}
            placeholder='/path/to/audio/files'
            style={{ marginTop: 8 }}
          />
          <Text type='secondary' style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
            目录中的每个子文件夹将作为一个声纹，文件夹名称将作为声纹名称
          </Text>
        </div>
      </Modal>
    );
  };

  return (
    <div>
      {contextHolder}
      <div style={{ marginBottom: 16 }}>
        <Button.Group>
          <Button
            type={activeVoiceTab === '1' ? 'primary' : 'default'}
            ghost={activeVoiceTab === '1'}
            onClick={() => setActiveVoiceTab('1')}
          >
            语音转换
          </Button>
          <Button
            type={activeVoiceTab === '2' ? 'primary' : 'default'}
            ghost={activeVoiceTab === '2'}
            onClick={() => setActiveVoiceTab('2')}
          >
            声纹管理
          </Button>
        </Button.Group>
      </div>

      {activeVoiceTab === '1' ? (
        <>
          {/* 添加配置面板 */}
          {renderConfigurationPanel()}

          <Card
            title='上传音频文件'
            bordered={true}
            style={{
              borderRadius: 4,
              marginBottom: 16,
              boxShadow: 'none',
            }}
            extra={
              audioFiles.length > 0 && (
                <Button icon={<DeleteOutlined />} onClick={clearAllAudioFiles}>
                  清除全部
                </Button>
              )
            }
          >
            <Dragger {...audioProps}>
              <p className='ant-upload-drag-icon'>
                <SoundOutlined />
              </p>
              <p className='ant-upload-text'>点击或拖拽多个音频文件到此区域上传</p>
              <p className='ant-upload-hint'>支持 .mp3, .wav, .ogg, .m4a 格式的音频文件（可多选）</p>
            </Dragger>

            {audioFiles.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text strong>已选择 {audioFiles.length} 个文件：</Text>
                  <Button
                    type='primary'
                    onClick={handleVoiceProcess}
                    loading={voiceProcessing}
                    icon={<SoundOutlined />}
                    disabled={audioFiles.length === 0}
                  >
                    开始转换全部
                  </Button>
                </div>
                <List
                  style={{ marginTop: 8 }}
                  size='small'
                  bordered
                  dataSource={audioFiles}
                  renderItem={(file: UploadFile) => {
                    const isProcessed = voiceProcessResults.some(r => r.fileUid === file.uid);
                    const progress = uploadProgress[file.uid] || 0;

                    return (
                      <List.Item
                        actions={[
                          voiceProcessing ? (
                            <Progress percent={progress} size='small' style={{ width: 80 }} />
                          ) : isProcessed ? (
                            <Tag color='green'>已转换</Tag>
                          ) : (
                            <Tag>未处理</Tag>
                          ),
                        ]}
                      >
                        <Text>{file.name}</Text>
                        <Text type='secondary' style={{ marginLeft: 8 }}>
                          ({(file.size ? file.size / 1024 : 0).toFixed(2)} KB)
                        </Text>
                      </List.Item>
                    );
                  }}
                />
              </div>
            )}
          </Card>

          {voiceProcessing && (
            <Card
              bordered={true}
              style={{
                borderRadius: 4,
                marginBottom: 16,
                boxShadow: 'none',
              }}
            >
              <div style={{ textAlign: 'center', padding: 24 }}>
                <LoadingOutlined style={{ fontSize: 32 }} />
                <p style={{ marginTop: 16 }}>正在处理 {audioFiles.length} 个音频文件，请稍候...</p>
                <Progress percent={75} status='active' />
              </div>
            </Card>
          )}

          {voiceProcessResults.length > 0 && !voiceProcessing && (
            <Card
              title='转换结果'
              bordered={true}
              style={{
                borderRadius: 4,
                marginBottom: 16,
                boxShadow: 'none',
              }}
              extra={
                <Button type='primary' icon={<DownloadOutlined />} onClick={downloadAllTextResults}>
                  下载全部结果
                </Button>
              }
            >
              <div style={{ marginBottom: 16 }}>
                <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
                <Text type='success'>已成功转换 {voiceProcessResults.filter(r => r.success).length} 个文件！</Text>
                {voiceProcessResults.some(r => !r.success) && (
                  <Text type='danger' style={{ marginLeft: 16 }}>
                    {voiceProcessResults.filter(r => !r.success).length} 个文件处理失败
                  </Text>
                )}
              </div>

              {voiceProcessResults.map((result, index) => (
                <Card
                  key={index}
                  type='inner'
                  title={`文件名：${result.fileName}`}
                  style={{ marginBottom: 16 }}
                  extra={
                    result.success ? (
                      <Button type='link' icon={<DownloadOutlined />} onClick={() => downloadTextResult(result)}>
                        下载文本
                      </Button>
                    ) : null
                  }
                >
                  {result.success ? (
                    <>
                      <div
                        style={{
                          background: '#f5f5f5',
                          padding: 16,
                          borderRadius: 4,
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {result.text}
                      </div>
                      <div style={{ marginTop: 8 }}>
                        <Text type='secondary'>处理用时: {result.processingTime} 秒</Text>
                        {result.duration && (
                          <Text type='secondary' style={{ marginLeft: 16 }}>
                            音频时长: {Math.floor(result.duration / 60)}:
                            {Math.floor(result.duration % 60)
                              .toString()
                              .padStart(2, '0')}
                          </Text>
                        )}
                        {result.autoRegisteredSpeakers && result.autoRegisteredSpeakers > 0 && (
                          <Tag color='blue' style={{ marginLeft: 16 }}>
                            自动注册了 {result.autoRegisteredSpeakers} 个新声纹
                          </Tag>
                        )}
                      </div>
                    </>
                  ) : (
                    <div
                      style={{
                        background: '#fff2f0',
                        padding: 16,
                        borderRadius: 4,
                        border: '1px solid #ffccc7',
                      }}
                    >
                      <Text type='danger'>处理失败: {result.error || '未知错误'}</Text>
                    </div>
                  )}
                </Card>
              ))}
            </Card>
          )}
        </>
      ) : (
        <Card
          bordered={true}
          style={{
            borderRadius: 4,
            marginBottom: 16,
            boxShadow: 'none',
          }}
        >
          <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text>管理您的声纹样本，提高识别准确度</Text>
            <Space>
              <Button onClick={() => setIsBatchModalVisible(true)}>批量注册声纹</Button>
              <Button type='primary' icon={<UserOutlined />} onClick={addNewVoiceProfile}>
                添加新声纹
              </Button>
              {voiceProfiles.length > 0 && (
                <Button type='default' danger icon={<DeleteOutlined />} onClick={handleClearAllProfiles}>
                  清除所有声纹
                </Button>
              )}
            </Space>
          </div>

          <Table
            dataSource={voiceProfiles}
            columns={profileColumns}
            rowKey='id'
            expandable={{
              expandedRowKeys,
              onExpand: (expanded, record) => {
                if (expanded) {
                  setExpandedRowKeys([...expandedRowKeys, record.id]);
                } else {
                  setExpandedRowKeys(expandedRowKeys.filter(key => key !== record.id));
                }
              },
              expandedRowRender,
              expandedRowClassName: () => 'voice-expanded-row',
              expandRowByClick: false,
              expandIcon: ({ expanded, onExpand, record }) =>
                expanded ? (
                  <span
                    onClick={e => onExpand(record, e)}
                    style={{
                      cursor: 'pointer',
                      marginRight: 8,
                      fontSize: 18,
                      lineHeight: 1,
                    }}
                  >
                    −
                  </span>
                ) : (
                  <span
                    onClick={e => onExpand(record, e)}
                    style={{
                      cursor: 'pointer',
                      marginRight: 8,
                      fontSize: 18,
                      lineHeight: 1,
                    }}
                  >
                    +
                  </span>
                ),
              indentSize: 0,
            }}
            pagination={false}
            style={{ width: '100%' }}
            tableLayout='fixed'
            locale={{ emptyText: '暂无声纹数据，请添加新声纹' }}
          />
        </Card>
      )}

      {/* Render modals */}
      {renderBatchRegisterModal()}

      <audio ref={audioRef} style={{ display: 'none' }} onEnded={() => setPlayingSampleId(null)} />
    </div>
  );
};
export default VoiceModule;
