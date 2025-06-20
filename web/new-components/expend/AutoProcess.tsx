import {
  CaretRightOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FileOutlined,
  FolderOpenOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SettingOutlined,
  SoundOutlined,
  SyncOutlined,
  ToolOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import {
  Badge,
  Button,
  Card,
  Col,
  Collapse,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd';
import { useEffect, useState } from 'react';

const { Option } = Select;
const { Title, Text } = Typography;
const { confirm } = Modal;
const { Panel } = Collapse;

const AutoProcessModule = () => {
  // 状态管理
  const [scanConfig, setScanConfig] = useState({
    ftpHost: '',
    ftpPort: 21,
    ftpUser: '',
    ftpPassword: '',
    scanPath: '',
    interval: 60,
    fileTypes: ['.wav', '.mp3', '.mp4'],
  });
  const [voiceConfig, setVoiceConfig] = useState({
    enabled: false,
    language: 'auto',
    batchSize: 10,
  });
  const [knowledgeConfig, setKnowledgeConfig] = useState({
    enabled: false,
    fileTypes: ['.txt', '.doc', '.docx', '.pdf'],
    splitStrategy: 'paragraph',
  });
  const [fileList, setFileList] = useState([]);
  const [resultList, setResultList] = useState([]);
  const [isScanning, setIsScanning] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [cleanupTimer, setCleanupTimer] = useState(24);
  const [activePanel, setActivePanel] = useState(['1', '2', '3']);

  // 模拟数据
  useEffect(() => {
    setFileList([
      {
        id: 1,
        name: 'audio_001.wav',
        type: 'audio',
        size: '2.5MB',
        uploadTime: '2024-01-15 10:30:00',
        status: 'pending',
        progress: 0,
      },
      {
        id: 2,
        name: 'document_001.pdf',
        type: 'document',
        size: '1.2MB',
        uploadTime: '2024-01-15 11:00:00',
        status: 'completed',
        progress: 100,
      },
      {
        id: 3,
        name: 'audio_002.mp3',
        type: 'audio',
        size: '3.1MB',
        uploadTime: '2024-01-15 11:15:00',
        status: 'processing',
        progress: 65,
      },
    ]);

    setResultList([
      {
        id: 1,
        originalFile: 'audio_001.wav',
        fileName: 'audio_001_transcript.txt',
        type: 'transcript',
        size: '15KB',
        createTime: '2024-01-15 10:35:00',
        downloadUrl: '#',
      },
      {
        id: 2,
        originalFile: 'document_001.pdf',
        fileName: 'document_001_knowledge.json',
        type: 'knowledge',
        size: '28KB',
        createTime: '2024-01-15 11:05:00',
        downloadUrl: '#',
      },
    ]);
  }, []);

  // 文件列表列配置
  const fileColumns = [
    {
      title: '文件名',
      dataIndex: 'name',
      key: 'name',
      width: '30%',
      render: (text, record) => (
        <Space>
          <FileOutlined />
          <span>{text}</span>
          {record.status === 'completed' && (
            <Tag color='green' size='small'>
              已完成
            </Tag>
          )}
          {record.status === 'processing' && (
            <Tag color='blue' size='small'>
              处理中
            </Tag>
          )}
          {record.status === 'failed' && (
            <Tag color='red' size='small'>
              失败
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: '15%',
      render: type => (
        <Tag color={type === 'audio' ? 'blue' : 'green'} size='small'>
          {type === 'audio' ? '音频' : '文档'}
        </Tag>
      ),
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: '10%',
    },
    {
      title: '上传时间',
      dataIndex: 'uploadTime',
      key: 'uploadTime',
      width: '20%',
    },
    {
      title: '处理进度',
      dataIndex: 'progress',
      key: 'progress',
      width: '15%',
      render: (progress, record) =>
        record.status === 'processing' ? (
          <Progress percent={progress} size='small' />
        ) : record.status === 'completed' ? (
          <Text type='success'>完成</Text>
        ) : (
          <Text type='secondary'>等待</Text>
        ),
    },
    {
      title: '操作',
      key: 'action',
      width: '10%',
      render: (_, record) => (
        <Space size='small'>
          <Tooltip title='重命名'>
            <Button size='small' type='text' icon={<EditOutlined />} onClick={() => handleEditFileName(record)} />
          </Tooltip>
          <Tooltip title='删除'>
            <Button
              size='small'
              type='text'
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDeleteFile(record)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  // 结果文件列配置
  const resultColumns = [
    {
      title: '结果文件',
      dataIndex: 'fileName',
      key: 'fileName',
      width: '35%',
      render: text => (
        <Space>
          <FileOutlined />
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: '原文件',
      dataIndex: 'originalFile',
      key: 'originalFile',
      width: '25%',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: '15%',
      render: type => (
        <Tag color='orange' size='small'>
          {type === 'transcript' ? '转录文本' : '知识提取'}
        </Tag>
      ),
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: '10%',
    },
    {
      title: '创建时间',
      dataIndex: 'createTime',
      key: 'createTime',
      width: '15%',
    },
  ];

  // 事件处理函数
  const handleScanStart = () => {
    if (!scanConfig.ftpHost || !scanConfig.scanPath) {
      message.warning('请完善FTP配置信息');
      return;
    }
    setIsScanning(true);
    message.success('开始扫描FTP服务器');

    setTimeout(() => {
      message.info('发现 3 个新文件');
      setIsScanning(false);
    }, 3000);
  };

  const handleScanStop = () => {
    setIsScanning(false);
    message.info('已停止扫描');
  };

  const handleVoiceToggle = checked => {
    setVoiceConfig(prev => ({ ...prev, enabled: checked }));
    message.success(checked ? '语音自动加工已启用' : '语音自动加工已停用');
  };

  const handleKnowledgeToggle = checked => {
    setKnowledgeConfig(prev => ({ ...prev, enabled: checked }));
    message.success(checked ? '知识库自动加工已启用' : '知识库自动加工已停用');
  };

  const handleFileUpload = info => {
    if (info.file.status === 'done') {
      message.success(`${info.file.name} 上传成功`);
      const newFile = {
        id: Date.now(),
        name: info.file.name,
        type: info.file.name.includes('.wav') || info.file.name.includes('.mp3') ? 'audio' : 'document',
        size: `${(info.file.size / 1024 / 1024).toFixed(1)}MB`,
        uploadTime: new Date().toLocaleString(),
        status: 'pending',
        progress: 0,
      };
      setFileList(prev => [...prev, newFile]);
    } else if (info.file.status === 'error') {
      message.error(`${info.file.name} 上传失败`);
    }
  };

  const handleEditFileName = record => {
    Modal.confirm({
      title: '重命名文件',
      content: (
        <Input
          defaultValue={record.name}
          onPressEnter={e => {
            const newName = e.target.value;
            setFileList(prev => prev.map(file => (file.id === record.id ? { ...file, name: newName } : file)));
            message.success('文件名修改成功');
          }}
        />
      ),
      onOk: () => {},
    });
  };

  const handleDeleteFile = record => {
    confirm({
      title: '确认删除',
      content: `确定要删除文件 "${record.name}" 吗？`,
      onOk: () => {
        setFileList(prev => prev.filter(file => file.id !== record.id));
        message.success('文件删除成功');
      },
    });
  };

  const handleDownload = record => {
    message.success(`开始下载 ${record.fileName}`);
  };

  const handleDeleteResult = record => {
    confirm({
      title: '确认删除',
      content: `确定要删除结果文件 "${record.fileName}" 吗？`,
      onOk: () => {
        setResultList(prev => prev.filter(result => result.id !== record.id));
        setFileList(prev =>
          prev.map(file => (file.name === record.originalFile ? { ...file, status: 'pending' } : file)),
        );
        message.success('结果文件删除成功');
      },
    });
  };

  const handleBatchDelete = () => {
    if (selectedFiles.length === 0) {
      message.warning('请选择要删除的文件');
      return;
    }

    confirm({
      title: '批量删除',
      content: `确定要删除选中的 ${selectedFiles.length} 个文件吗？`,
      onOk: () => {
        setFileList(prev => prev.filter(file => !selectedFiles.includes(file.id)));
        setSelectedFiles([]);
        message.success('批量删除成功');
      },
    });
  };

  const handleStartProcessing = () => {
    const pendingFiles = fileList.filter(file => file.status === 'pending');
    if (pendingFiles.length === 0) {
      message.warning('没有待处理的文件');
      return;
    }

    setIsProcessing(true);
    message.success('开始批量处理文件');

    pendingFiles.forEach((file, index) => {
      setTimeout(() => {
        setFileList(prev => prev.map(f => (f.id === file.id ? { ...f, status: 'processing', progress: 0 } : f)));

        const progressInterval = setInterval(() => {
          setFileList(prev =>
            prev.map(f => {
              if (f.id === file.id && f.status === 'processing') {
                const newProgress = f.progress + 10;
                if (newProgress >= 100) {
                  clearInterval(progressInterval);
                  return { ...f, status: 'completed', progress: 100 };
                }
                return { ...f, progress: newProgress };
              }
              return f;
            }),
          );
        }, 200);
      }, index * 1000);
    });

    setTimeout(
      () => {
        setIsProcessing(false);
        message.success('批量处理完成');
      },
      (pendingFiles.length + 1) * 3000,
    );
  };

  const pendingCount = fileList.filter(file => file.status === 'pending').length;
  const processingCount = fileList.filter(file => file.status === 'processing').length;
  const completedCount = fileList.filter(file => file.status === 'completed').length;

  return (
    <div style={{ padding: '0 24px' }}>
      <Title level={2} style={{ marginBottom: 24 }}>
        <ToolOutlined /> 自动化加工模块
      </Title>

      <Row gutter={24}>
        {/* 左侧配置面板 */}
        <Col span={8}>
          <Space direction='vertical' style={{ width: '100%' }} size={16}>
            {/* 状态概览 */}
            <Card size='small' title='处理状态'>
              <Row gutter={16}>
                <Col span={8}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: '#1890ff' }}>{pendingCount}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>待处理</div>
                  </div>
                </Col>
                <Col span={8}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: '#52c41a' }}>{processingCount}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>处理中</div>
                  </div>
                </Col>
                <Col span={8}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 'bold', color: '#f5222d' }}>{completedCount}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>已完成</div>
                  </div>
                </Col>
              </Row>
            </Card>

            {/* 配置面板 */}
            <Card size='small' title='配置中心'>
              <Collapse
                activeKey={activePanel}
                onChange={setActivePanel}
                expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} />}
                size='small'
                ghost
              >
                {/* 定时扫描配置 */}
                <Panel
                  header={
                    <Space>
                      <SyncOutlined spin={isScanning} />
                      <span>定时扫描</span>
                      {isScanning && <Badge status='processing' />}
                    </Space>
                  }
                  key='1'
                >
                  <Form size='small' layout='vertical'>
                    <Form.Item label='FTP服务器' style={{ marginBottom: 8 }}>
                      <Input
                        placeholder='服务器地址'
                        value={scanConfig.ftpHost}
                        onChange={e => setScanConfig(prev => ({ ...prev, ftpHost: e.target.value }))}
                      />
                    </Form.Item>
                    <Row gutter={8}>
                      <Col span={12}>
                        <Form.Item label='端口' style={{ marginBottom: 8 }}>
                          <InputNumber
                            size='small'
                            min={1}
                            max={65535}
                            value={scanConfig.ftpPort}
                            onChange={value => setScanConfig(prev => ({ ...prev, ftpPort: value }))}
                            style={{ width: '100%' }}
                          />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item label='间隔(分)' style={{ marginBottom: 8 }}>
                          <InputNumber
                            size='small'
                            min={1}
                            value={scanConfig.interval}
                            onChange={value => setScanConfig(prev => ({ ...prev, interval: value }))}
                            style={{ width: '100%' }}
                          />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item label='扫描目录' style={{ marginBottom: 8 }}>
                      <Input
                        placeholder='/upload/audio'
                        value={scanConfig.scanPath}
                        onChange={e => setScanConfig(prev => ({ ...prev, scanPath: e.target.value }))}
                      />
                    </Form.Item>
                    <Form.Item style={{ marginBottom: 8 }}>
                      <Space>
                        <Button
                          size='small'
                          type='primary'
                          icon={isScanning ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                          loading={isScanning}
                          onClick={isScanning ? handleScanStop : handleScanStart}
                        >
                          {isScanning ? '停止' : '开始'}
                        </Button>
                        <Button size='small' icon={<SettingOutlined />}>
                          测试
                        </Button>
                      </Space>
                    </Form.Item>
                  </Form>
                </Panel>

                {/* 语音自动加工 */}
                <Panel
                  header={
                    <Space>
                      <SoundOutlined />
                      <span>语音加工</span>
                      {voiceConfig.enabled && <Badge status='success' />}
                    </Space>
                  }
                  key='2'
                >
                  <Form size='small' layout='vertical'>
                    <Form.Item style={{ marginBottom: 8 }}>
                      <Space align='center'>
                        <Switch size='small' checked={voiceConfig.enabled} onChange={handleVoiceToggle} />
                        <Text>启用自动转换</Text>
                      </Space>
                    </Form.Item>

                    <Row gutter={8}>
                      <Col span={12}>
                        <Form.Item label='语言' style={{ marginBottom: 8 }}>
                          <Select
                            size='small'
                            value={voiceConfig.language}
                            onChange={value => setVoiceConfig(prev => ({ ...prev, language: value }))}
                            disabled={!voiceConfig.enabled}
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
                            onChange={value => setVoiceConfig(prev => ({ ...prev, batchSize: value }))}
                            disabled={!voiceConfig.enabled}
                            style={{ width: '100%' }}
                          />
                        </Form.Item>
                      </Col>
                    </Row>
                  </Form>
                </Panel>

                {/* 知识库加工 */}
                <Panel
                  header={
                    <Space>
                      <DatabaseOutlined />
                      <span>知识库加工</span>
                      {knowledgeConfig.enabled && <Badge status='success' />}
                    </Space>
                  }
                  key='3'
                >
                  <Form size='small' layout='vertical'>
                    <Form.Item style={{ marginBottom: 8 }}>
                      <Space align='center'>
                        <Switch size='small' checked={knowledgeConfig.enabled} onChange={handleKnowledgeToggle} />
                        <Text>启用自动加工</Text>
                      </Space>
                    </Form.Item>

                    <Form.Item label='文件类型' style={{ marginBottom: 8 }}>
                      <Select
                        size='small'
                        mode='multiple'
                        value={knowledgeConfig.fileTypes}
                        onChange={value => setKnowledgeConfig(prev => ({ ...prev, fileTypes: value }))}
                        disabled={!knowledgeConfig.enabled}
                        placeholder='选择文件类型'
                      >
                        <Option value='.txt'>TXT</Option>
                        <Option value='.doc'>DOC</Option>
                        <Option value='.pdf'>PDF</Option>
                      </Select>
                    </Form.Item>

                    <Form.Item label='分割策略' style={{ marginBottom: 8 }}>
                      <Select
                        size='small'
                        value={knowledgeConfig.splitStrategy}
                        onChange={value => setKnowledgeConfig(prev => ({ ...prev, splitStrategy: value }))}
                        disabled={!knowledgeConfig.enabled}
                      >
                        <Option value='paragraph'>按段落</Option>
                        <Option value='sentence'>按句子</Option>
                        <Option value='fixed'>固定长度</Option>
                        <Option value='semantic'>语义分割</Option>
                      </Select>
                    </Form.Item>
                  </Form>
                </Panel>
              </Collapse>
            </Card>

            {/* 定时清理设置 */}
            <Card size='small' title='定时清理'>
              <Form size='small' layout='vertical'>
                <Row gutter={8}>
                  <Col span={12}>
                    <Form.Item label='清理间隔' style={{ marginBottom: 8 }}>
                      <InputNumber
                        size='small'
                        min={1}
                        max={168}
                        value={cleanupTimer}
                        onChange={setCleanupTimer}
                        addonAfter='小时'
                        style={{ width: '100%' }}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label='自动清理' style={{ marginBottom: 8 }}>
                      <Switch size='small' defaultChecked />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item style={{ marginBottom: 0 }}>
                  <Button size='small' type='primary' block icon={<DeleteOutlined />}>
                    立即清理
                  </Button>
                </Form.Item>
              </Form>
            </Card>
          </Space>
        </Col>

        {/* 右侧文件管理主视图 */}
        <Col span={16}>
          <Space direction='vertical' style={{ width: '100%' }} size={16}>
            {/* 文件操作栏 */}
            <Card size='small'>
              <Row justify='space-between' align='middle'>
                <Col>
                  <Space>
                    <Upload name='file' multiple showUploadList={false} onChange={handleFileUpload}>
                      <Button icon={<UploadOutlined />}>上传文件</Button>
                    </Upload>
                    <Button
                      type='primary'
                      icon={<PlayCircleOutlined />}
                      onClick={handleStartProcessing}
                      loading={isProcessing}
                      disabled={pendingCount === 0}
                    >
                      开始处理 ({pendingCount})
                    </Button>
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      onClick={handleBatchDelete}
                      disabled={selectedFiles.length === 0}
                    >
                      批量删除 ({selectedFiles.length})
                    </Button>
                  </Space>
                </Col>
                <Col>
                  <Space>
                    <Text type='secondary'>
                      总文件: {fileList.length} | 待处理: {pendingCount} | 处理中: {processingCount}
                    </Text>
                    <Button size='small' icon={<ReloadOutlined />} onClick={() => message.info('刷新文件列表')}>
                      刷新
                    </Button>
                  </Space>
                </Col>
              </Row>
            </Card>

            {/* 文件列表 */}
            <Card
              title={
                <Space>
                  <FolderOpenOutlined />
                  <span>扫描文件列表</span>
                  <Tag color='blue'>{fileList.length} 个文件</Tag>
                </Space>
              }
              size='small'
            >
              <Table
                dataSource={fileList}
                columns={fileColumns}
                rowKey='id'
                size='small'
                pagination={{ pageSize: 8, showSizeChanger: true, showQuickJumper: true }}
                rowSelection={{
                  selectedRowKeys: selectedFiles,
                  onChange: setSelectedFiles,
                }}
                scroll={{ y: 400 }}
              />
            </Card>

            {/* 处理结果列表 */}
            <Card
              title={
                <Space>
                  <CheckCircleOutlined />
                  <span>处理结果列表</span>
                  <Tag color='green'>{resultList.length} 个结果</Tag>
                </Space>
              }
              size='small'
              extra={
                <Space>
                  <Text type='secondary' style={{ fontSize: 12 }}>
                    <ClockCircleOutlined /> 定时清理: {cleanupTimer}小时后
                  </Text>
                </Space>
              }
            >
              <Table
                dataSource={resultList}
                columns={[
                  ...resultColumns,
                  {
                    title: '操作',
                    key: 'action',
                    width: '10%',
                    render: (_, record) => (
                      <Space size='small'>
                        <Tooltip title='下载'>
                          <Button
                            size='small'
                            type='text'
                            icon={<DownloadOutlined />}
                            onClick={() => handleDownload(record)}
                          />
                        </Tooltip>
                        <Tooltip title='删除'>
                          <Button
                            size='small'
                            type='text'
                            danger
                            icon={<DeleteOutlined />}
                            onClick={() => handleDeleteResult(record)}
                          />
                        </Tooltip>
                      </Space>
                    ),
                  },
                ]}
                rowKey='id'
                size='small'
                pagination={{ pageSize: 6, showSizeChanger: true }}
                scroll={{ y: 300 }}
              />
            </Card>
          </Space>
        </Col>
      </Row>
    </div>
  );
};

export default AutoProcessModule;
