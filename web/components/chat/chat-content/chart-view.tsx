import { GET } from '@/client/api';
import { AutoChart, BackEndChartType, getChartType } from '@/components/chart/autoChart';
import { formatSql } from '@/utils';
import { DownloadOutlined } from '@ant-design/icons';
import { Datum } from '@antv/ava';
import { Button, Table, Tabs, TabsProps, message } from 'antd';
import { CodePreview } from './code-preview';

const returnSqlVal = (val: string) => {
  const punctuationMap: any = {
    '，': ',',
    '。': '.',
    '？': '?',
    '！': '!',
    '：': ':',
    '；': ';',
    '“': '"',
    '”': '"',
    '‘': "'",
    '’': "'",
    '（': '(',
    '）': ')',
    '【': '[',
    '】': ']',
    '《': '<',
    '》': '>',
    '—': '-',
    '、': ',',
    '…': '...',
  };
  const regex = new RegExp(Object.keys(punctuationMap).join('|'), 'g');
  return val.replace(regex, match => punctuationMap[match]);
};

function ChartView({
  data,
  type,
  sql,
  uri,
  deleteAfterDownload = false, // 新增参数，控制下载后是否删除文件
}: {
  data: Datum[];
  type: BackEndChartType;
  sql: string;
  uri?: string;
  deleteAfterDownload?: boolean;
}) {
  // 下载文件的处理函数
  const handleDownload = async () => {
    if (!uri) {
      message.error('下载链接不存在');
      return;
    }

    try {
      message.loading({ content: '正在准备下载...', key: 'download' });

      // 使用新的通用下载接口
      const response = await GET<{ uri: string; delete_after_download: boolean }, Blob>(
        '/api/v1/download/file',
        {
          uri,
          delete_after_download: deleteAfterDownload,
        },
        { responseType: 'blob' },
      );

      // 创建下载链接
      const blob = new Blob([response.data]);

      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;

      // 从响应头中获取文件名，或使用默认名称
      const contentDisposition = response.headers['content-disposition'];
      let fileName = `data_export_${new Date().getTime()}`;

      if (contentDisposition) {
        const fileNameMatch = contentDisposition.match(/filename\*?=['"]?([^'"\s]+)['"]?/);
        if (fileNameMatch && fileNameMatch[1]) {
          fileName = decodeURIComponent(fileNameMatch[1]);
        }
      }

      // 如果没有从响应头获取到文件名，尝试从URI中提取
      if (!fileName || fileName.startsWith('data_export_')) {
        fileName = extractFileNameFromUri(uri) || `data_export_${new Date().getTime()}.xlsx`;
      }

      link.download = fileName;

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);

      const successMessage = deleteAfterDownload ? '下载完成，原文件已删除' : '下载完成';
      message.success({ content: successMessage, key: 'download' });
    } catch (error: any) {
      console.error('下载失败:', error);

      // 如果是 HTTP 错误，尝试解析错误信息
      let errorMessage = '下载失败，请重试';
      if (error.response?.data) {
        try {
          // 如果后端返回的是文本错误信息
          if (error.response.data instanceof Blob) {
            const text = await error.response.data.text();
            const errorData = JSON.parse(text);
            errorMessage = errorData.detail || errorMessage;
          } else if (typeof error.response.data === 'object') {
            errorMessage = error.response.data.detail || errorMessage;
          }
        } catch (parseError) {
          // 解析失败，使用默认错误信息
          console.error('解析错误响应失败:', parseError);
          errorMessage = '下载失败，请重试';
        }
      }

      message.error({ content: errorMessage, key: 'download' });
    }
  };

  // 从 URI 中提取文件名的辅助函数
  const extractFileNameFromUri = (uri: string): string | null => {
    try {
      // 尝试作为完整URL解析
      const url = new URL(uri);
      const pathname = url.pathname;
      const fileName = pathname.split('/').pop();
      return fileName && fileName.includes('.') ? fileName : null;
    } catch {
      // 如果不是完整URL，尝试从路径中提取
      const parts = uri.split('/');
      const fileName = parts[parts.length - 1];
      return fileName && fileName.includes('.') ? fileName : null;
    }
  };

  // 根据文件类型确定下载按钮文本
  const getDownloadButtonText = (): string => {
    if (!uri) return '下载文件';

    const fileName = extractFileNameFromUri(uri);
    if (!fileName) return '下载文件';

    const extension = fileName.split('.').pop()?.toLowerCase();

    switch (extension) {
      case 'xlsx':
      case 'xls':
        return '下载Excel';
      case 'pdf':
        return '下载PDF';
      case 'csv':
        return '下载CSV';
      case 'png':
      case 'jpg':
      case 'jpeg':
        return '下载图片';
      case 'md':
        return '下载Markdown';
      default:
        return '下载文件';
    }
  };

  // 保留原有的columns生成逻辑
  const columns = data?.[0]
    ? Object.keys(data?.[0])?.map(item => {
        return {
          title: item,
          dataIndex: item,
          key: item,
        };
      })
    : [];

  const ChartItem = {
    key: 'chart',
    label: 'Chart',
    children: <AutoChart data={data} chartType={getChartType(type)} />,
  };

  // 保留原有的SQL处理逻辑，包括returnSqlVal函数
  const SqlItem = {
    key: 'sql',
    label: 'SQL',
    children: <CodePreview code={formatSql(returnSqlVal(sql ?? ''), 'mysql') as string} language={'sql'} />,
  };

  // 保留原有的Table配置，包括scroll和virtual属性
  const DataItem = {
    key: 'data',
    label: 'Data',
    children: <Table dataSource={data} columns={columns} scroll={{ x: true }} virtual={true} />,
  };

  // 保留原有的TabItems逻辑
  const TabItems: TabsProps['items'] = type === 'response_table' ? [DataItem, SqlItem] : [ChartItem, SqlItem, DataItem];

  // 下载按钮组件
  const DownloadButton = uri ? (
    <Button type='primary' icon={<DownloadOutlined />} onClick={handleDownload} size='small'>
      {getDownloadButtonText()}
    </Button>
  ) : null;

  return (
    <Tabs
      defaultActiveKey={type === 'response_table' ? 'data' : 'chart'}
      items={TabItems}
      size='small'
      tabBarExtraContent={DownloadButton}
    />
  );
}

export default ChartView;
