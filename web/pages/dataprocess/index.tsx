import AutoProcessModule from '@/new-components/expend/AutoProcess';
import ExcelModule from '@/new-components/expend/Excel2Db';
import VoiceModule from '@/new-components/expend/Voice2Text';
import { FileExcelOutlined, SoundOutlined, ToolOutlined } from '@ant-design/icons';
import { Layout, Menu } from 'antd';
import { useState } from 'react';

const { Header, Content } = Layout;

const DataProcess = () => {
  // State for active menu item
  const [selectedKey, setSelectedKey] = useState('1');

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          background: '#e6f7ff',
          padding: '0',
          boxShadow: '0 1px 4px rgba(0,21,41,.08)',
        }}
      >
        <Menu
          mode='horizontal'
          selectedKeys={[selectedKey]}
          style={{ flex: 1, borderBottom: 'none', background: '#e6f7ff' }}
          onSelect={({ key }) => setSelectedKey(key)}
        >
          <Menu.Item key='1' icon={<FileExcelOutlined />}>
            Excel入库
          </Menu.Item>
          <Menu.Item key='2' icon={<SoundOutlined />}>
            语音转文字
          </Menu.Item>
          <Menu.Item key='3' icon={<ToolOutlined />}>
            自动化加工
          </Menu.Item>
        </Menu>
      </Header>
      <Layout>
        <Content
          style={{
            padding: 24,
            margin: 0,
            background: '#f0f2f5',
            minHeight: 'calc(100vh - 64px)', // 减去Header高度
            overflowY: 'auto', // 添加垂直滚动
          }}
        >
          {selectedKey === '1' && <ExcelModule />}
          {selectedKey === '2' && <VoiceModule />}
          {selectedKey === '3' && <AutoProcessModule />}
        </Content>
      </Layout>
    </Layout>
  );
};

export default DataProcess;
