import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  InboxOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Divider,
  Form,
  Input,
  InputNumber,
  Progress,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
  UploadFile,
  message,
} from 'antd';
import React, { useState } from 'react';

// 导入 API 函数和 apiInterceptors
import { apiInterceptors } from '@/client/api';
import { DbProcessResult, postProcessExcelToDb } from '@/client/api/expend/excel2db';

const { Text } = Typography;
const { Dragger } = Upload;
const { Option } = Select;

// 表单值类型定义
interface FormValues {
  dbType: string;
  dbHost: string;
  dbPort: number; // 新增端口字段
  dbName: string;
  dbUser: string;
  dbPassword: string;
  autoCreate: string;
  sheetNames?: string;
  tablePrefix?: string;
  tableMapping?: string;
  chunkSize: string;
  ifExists: string;
  columnMapping?: string;
}

// 数据库类型选项
const DB_TYPE_OPTIONS = [
  { label: 'MySQL', value: 'mysql' },
  { label: 'PostgreSQL', value: 'postgresql' },
  { label: 'SQL Server', value: 'sqlserver' },
  { label: 'Oracle', value: 'oracle' },
  { label: 'SQLite', value: 'sqlite' },
];

const ExcelModule: React.FC = () => {
  // States for Excel to Database module
  const [excelFiles, setExcelFiles] = useState<UploadFile[]>([]);
  const [dbProcessing, setDbProcessing] = useState<boolean>(false);
  const [dbProcessResult, setDbProcessResult] = useState<DbProcessResult | null>(null);
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm();
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});

  // Excel file upload props
  const excelProps = {
    name: 'file',
    multiple: true,
    accept: '.xlsx,.xls,.csv',
    beforeUpload: (file: UploadFile): boolean => {
      setExcelFiles(prev => [...prev, file]);
      return false; // Prevent auto upload
    },
    onRemove: (file: UploadFile): void => {
      setExcelFiles(prev => prev.filter(item => item.uid !== file.uid));
      // Also remove progress tracking
      setUploadProgress(prev => {
        const newProgress = { ...prev };
        delete newProgress[file.uid];
        return newProgress;
      });
    },
    fileList: excelFiles,
  };

  // Clear all Excel files
  const clearAllExcelFiles = (): void => {
    setExcelFiles([]);
    setDbProcessResult(null);
    setUploadProgress({});
    message.success('已清除所有Excel文件');
  };

  // Handle database process with integrated file upload
  const handleDbProcess = async (values: FormValues): Promise<void> => {
    if (excelFiles.length === 0) {
      messageApi.error('请先上传Excel文件');
      return;
    }

    setDbProcessing(true);

    try {
      // 处理进度消息
      messageApi.loading({
        content: `正在处理 ${excelFiles.length} 个Excel文件...`,
        key: 'db-process',
        duration: 0,
      });

      // 创建FormData用于文件上传和敏感信息传输
      const formData = new FormData();

      // 添加所有Excel文件到FormData - 使用正确的字段名 'files'
      excelFiles.forEach(file => {
        formData.append('files', file as any);
      });

      // 为每个文件添加初始进度
      const initialProgress: Record<string, number> = {};
      excelFiles.forEach(file => {
        initialProgress[file.uid] = 0;
      });
      setUploadProgress(initialProgress);

      // 调用处理API，集成文件上传
      const [err, data] = await apiInterceptors(
        postProcessExcelToDb({
          ...values,
          fileData: formData,
          config: {
            timeout: 1000 * 60 * 60, // 1小时超时
            onUploadProgress: (progressEvent: any): void => {
              const progress = Math.ceil((progressEvent.loaded / (progressEvent.total || 0)) * 100);

              // 更新所有文件的进度
              const updatedProgress: Record<string, number> = {};
              excelFiles.forEach(file => {
                updatedProgress[file.uid] = progress;
              });
              setUploadProgress(updatedProgress);

              // 更新加载消息
              messageApi.loading({
                content: `正在处理文件... ${progress}%`,
                key: 'db-process',
                duration: 0,
              });
            },
          },
        }),
      );

      // 关闭处理消息
      messageApi.destroy('db-process');

      if (err) {
        messageApi.error(`处理数据导入失败: ${err.message}`);
        // 创建一个用于错误显示的回退结果对象
        const fallbackResult: DbProcessResult = {
          fileCount: excelFiles.length,
          totalRows: 0,
          processedRows: 0,
          failedRows: 0,
          files: excelFiles.map(file => ({
            fileName: file.name,
            filePath: '',
            bucket: '',
            totalRows: 0,
            processedRows: 0,
            failedRows: 0,
            success: false,
            error: err.message || '处理失败',
          })),
          tableData: [],
          dbInfo: {
            dbName: values.dbName,
            tables: [],
          },
        };
        setDbProcessResult(fallbackResult);
        return;
      }

      // 处理成功
      const processResult = data as DbProcessResult;
      setDbProcessResult(processResult);

      // 显示结果消息
      if (processResult.failedRows === 0) {
        messageApi.success(`已成功处理 ${processResult.fileCount} 个Excel文件！`);
      } else if (processResult.processedRows > 0) {
        messageApi.warning(
          `已处理 ${processResult.fileCount} 个Excel文件，成功 ${processResult.processedRows} 行，失败 ${processResult.failedRows} 行`,
        );
      } else {
        messageApi.error(`所有数据处理失败`);
      }
    } catch (error: any) {
      console.error('Processing error:', error);
      messageApi.error(`处理Excel文件时出错: ${error.message}`);

      // 创建一个用于错误显示的回退结果
      const fallbackResult: DbProcessResult = {
        fileCount: excelFiles.length,
        totalRows: 0,
        processedRows: 0,
        failedRows: 0,
        files: excelFiles.map(file => ({
          fileName: file.name,
          filePath: '',
          bucket: '',
          totalRows: 0,
          processedRows: 0,
          failedRows: 0,
          success: false,
          error: error.message || '处理失败',
        })),
        tableData: [],
        dbInfo: {
          dbName: '',
          tables: [],
        },
      };
      setDbProcessResult(fallbackResult);
    } finally {
      setDbProcessing(false);
    }
  };

  // Table columns for Excel mapping preview
  const mappingColumns = [
    { title: '列名', dataIndex: 'column', key: 'column' },
    { title: '数据类型', dataIndex: 'type', key: 'type' },
    { title: '映射字段', dataIndex: 'mapped', key: 'mapped' },
  ];

  // Table columns for Excel files
  const excelFilesColumns = [
    {
      title: '文件名',
      dataIndex: 'fileName',
      key: 'fileName',
      render: (_: string, record: UploadFile) => record.name,
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      render: (_: string, record: UploadFile) => `${((record.size as number) / 1024).toFixed(2)} KB`,
    },
    {
      title: '上传进度',
      key: 'progress',
      render: (_: string, record: UploadFile) => {
        const progress = uploadProgress[record.uid] || 0;
        return dbProcessing ? <Progress percent={progress} size='small' /> : <Tag color='blue'>等待处理</Tag>;
      },
    },
  ];

  // Table columns for processed files result
  const processResultColumns = [
    {
      title: '文件名',
      dataIndex: 'fileName',
      key: 'fileName',
    },
    {
      title: '状态',
      key: 'status',
      render: (record: any) =>
        record.success ? (
          <Tag color='green' icon={<CheckCircleOutlined />}>
            成功
          </Tag>
        ) : (
          <Tag color='red' icon={<CloseCircleOutlined />}>
            失败
          </Tag>
        ),
    },
    {
      title: '总行数',
      dataIndex: 'totalRows',
      key: 'totalRows',
    },
    {
      title: '处理成功',
      dataIndex: 'processedRows',
      key: 'processedRows',
    },
    {
      title: '处理失败',
      dataIndex: 'failedRows',
      key: 'failedRows',
    },
    {
      title: '详情',
      key: 'details',
      render: (_: string, record: any) =>
        record.success ? <Text type='success'>处理成功</Text> : <Text type='danger'>{record.error || '未知错误'}</Text>,
    },
  ];

  // 数据库表和字段信息的列定义
  const dbTableColumns = [
    {
      title: '表名',
      dataIndex: 'tableName',
      key: 'tableName',
    },
    {
      title: '字段数',
      dataIndex: 'columns',
      key: 'columnCount',
      render: (columns: any[]) => columns.length,
    },
  ];

  // 表字段结构列定义
  const dbColumnsColumns = [
    {
      title: '字段名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '数据类型',
      dataIndex: 'type',
      key: 'type',
    },
    {
      title: '允许为空',
      dataIndex: 'nullable',
      key: 'nullable',
      render: (nullable: boolean) => (nullable ? '是' : '否'),
    },
  ];

  return (
    <div>
      {contextHolder}
      <Card
        title='上传Excel文件'
        bordered={true}
        style={{
          borderRadius: 4,
          marginBottom: 16,
          boxShadow: 'none',
        }}
        extra={
          excelFiles.length > 0 && (
            <Button icon={<DeleteOutlined />} onClick={clearAllExcelFiles}>
              清除全部
            </Button>
          )
        }
      >
        <Dragger {...excelProps}>
          <p className='ant-upload-drag-icon'>
            <InboxOutlined />
          </p>
          <p className='ant-upload-text'>点击或拖拽多个Excel文件到此区域上传</p>
          <p className='ant-upload-hint'>支持 .xlsx, .xls, .csv 格式的Excel文件（可多选）</p>
        </Dragger>

        {excelFiles.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <Text strong>已选择 {excelFiles.length} 个文件：</Text>
            <Table
              dataSource={excelFiles}
              columns={excelFilesColumns}
              rowKey='uid'
              size='small'
              style={{ marginTop: 8 }}
              pagination={excelFiles.length > 5 ? { pageSize: 5 } : false}
            />
          </div>
        )}
      </Card>

      <Card
        title='Excel导入配置'
        bordered={true}
        style={{
          borderRadius: 4,
          marginBottom: 16,
          boxShadow: 'none',
        }}
      >
        <Form
          form={form}
          layout='vertical'
          onFinish={handleDbProcess}
          initialValues={{
            dbType: 'mysql',
            dbHost: 'localhost',
            dbPort: 3306, // 默认端口
            dbName: 'mydb',
            dbUser: 'root',
            autoCreate: '是',
            chunkSize: '1000',
            ifExists: 'replace',
          }}
        >
          <div style={{ marginBottom: 8 }}>
            <Text type='secondary'>请配置数据库和Excel导入的相关选项</Text>
          </div>

          {/* Database Configuration */}
          <Divider orientation='left'>数据库配置</Divider>
          <Form.Item label='数据库类型' name='dbType' rules={[{ required: true }]}>
            <Select placeholder='选择数据库类型'>
              {DB_TYPE_OPTIONS.map(option => (
                <Option key={option.value} value={option.value}>
                  {option.label}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item label='数据库主机' name='dbHost' rules={[{ required: true }]}>
            <Input placeholder='数据库主机地址' />
          </Form.Item>

          {/* 新增的数据库端口配置 */}
          <Form.Item
            label='数据库端口'
            name='dbPort'
            rules={[{ required: true }]}
            tooltip='MySQL默认端口为3306，PostgreSQL默认端口为5432'
          >
            <InputNumber style={{ width: '100%' }} min={1} max={65535} placeholder='数据库端口' />
          </Form.Item>

          <Form.Item label='数据库名称' name='dbName' rules={[{ required: true }]}>
            <Input placeholder='数据库名称' />
          </Form.Item>
          <Form.Item label='用户名' name='dbUser' rules={[{ required: true }]}>
            <Input placeholder='数据库用户名' />
          </Form.Item>
          <Form.Item label='密码' name='dbPassword' rules={[{ required: true }]}>
            <Input.Password placeholder='数据库密码' />
          </Form.Item>

          <Divider orientation='left'>导入配置</Divider>

          <Form.Item label='自动创建库或表' name='autoCreate' rules={[{ required: true }]}>
            <Select>
              <Option value='是'>是</Option>
              <Option value='否'>否</Option>
            </Select>
          </Form.Item>

          <Form.Item label='工作表名称' name='sheetNames'>
            <Input placeholder='输入工作表（sheet）名称，多个名称用逗号分隔' />
          </Form.Item>

          <Form.Item label='表前缀' name='tablePrefix'>
            <Input placeholder='输入表前缀' />
          </Form.Item>

          <Form.Item label='表映射' name='tableMapping'>
            <Input.TextArea rows={4} placeholder='输入表映射关系，JSON格式' />
          </Form.Item>

          <Form.Item label='数据块大小' name='chunkSize'>
            <Input placeholder='输入数据块大小' />
          </Form.Item>

          <Form.Item label='如果已存在' name='ifExists'>
            <Select>
              <Option value='replace'>替换</Option>
              <Option value='append'>追加</Option>
              <Option value='fail'>失败</Option>
            </Select>
          </Form.Item>

          <Form.Item label='列映射' name='columnMapping'>
            <Input.TextArea rows={4} placeholder='输入列映射关系，JSON格式' />
          </Form.Item>

          <Form.Item>
            <Button
              type='primary'
              htmlType='submit'
              icon={<CloudUploadOutlined />}
              loading={dbProcessing}
              disabled={excelFiles.length === 0}
            >
              开始处理数据
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {dbProcessResult && (
        <Card
          title='处理结果'
          bordered={true}
          style={{
            borderRadius: 4,
            marginBottom: 16,
            boxShadow: 'none',
          }}
        >
          <Space direction='vertical' style={{ width: '100%' }}>
            <div>
              <Text strong>文件总数：</Text>
              <Text>{dbProcessResult.fileCount} 个文件</Text>
            </div>
            <div>
              <Text strong>总行数：</Text>
              <Text>{dbProcessResult.totalRows}</Text>
            </div>
            <div>
              <Text strong>处理成功：</Text>
              <Text type='success'>{dbProcessResult.processedRows} 行</Text>
            </div>
            <div>
              <Text strong>处理失败：</Text>
              <Text type='danger'>{dbProcessResult.failedRows} 行</Text>
            </div>

            <div style={{ marginTop: 16 }}>
              <Text strong>完成进度：</Text>
              <Progress
                percent={100}
                status={dbProcessResult.failedRows > 0 ? 'exception' : 'success'}
                style={{ marginTop: 8 }}
              />
            </div>

            <div style={{ marginTop: 16 }}>
              <Text strong>文件处理详情：</Text>
              <Table
                columns={processResultColumns}
                dataSource={dbProcessResult.files}
                rowKey='fileName'
                pagination={false}
                style={{ marginTop: 8 }}
              />
            </div>

            {dbProcessResult.dbInfo && dbProcessResult.dbInfo.tables.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <Text strong>数据库信息：</Text>
                <div style={{ marginBottom: 8, marginTop: 8 }}>
                  <Text>数据库名称：</Text>
                  <Text strong>{dbProcessResult.dbInfo.dbName}</Text>
                </div>
                <Table
                  columns={dbTableColumns}
                  dataSource={dbProcessResult.dbInfo.tables}
                  rowKey='tableName'
                  pagination={false}
                  expandable={{
                    expandedRowRender: record => (
                      <div style={{ margin: 0 }}>
                        <Text strong>字段列表：</Text>
                        <Table
                          columns={dbColumnsColumns}
                          dataSource={record.columns}
                          rowKey='name'
                          pagination={false}
                          size='small'
                        />
                      </div>
                    ),
                  }}
                  size='small'
                  style={{ marginTop: 8 }}
                />
              </div>
            )}

            {/* {dbProcessResult.tableData.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <Text strong>字段映射：</Text>
                <Table
                  columns={mappingColumns}
                  dataSource={dbProcessResult.tableData}
                  pagination={false}
                  size='small'
                  style={{ marginTop: 8 }}
                />
              </div>
            )} */}
          </Space>
        </Card>
      )}
    </div>
  );
};

export default ExcelModule;
