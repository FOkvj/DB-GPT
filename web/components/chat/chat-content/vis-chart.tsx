import { BackEndChartType } from '@/components/chart';
import { Datum } from '@antv/ava';
import ChartView from './chart-view';
console.log('VisChart file loaded'); // 文件被加载时就会输出
interface Props {
  data: {
    data: Datum[];
    describe: string;
    title: string;
    type: BackEndChartType;
    sql: string;
    uri?: string;
  };
}

function VisChart({ data }: Props) {
  console.log('shit:', data);
  if (!data) {
    return null;
  }
  return <ChartView data={data?.data} type={data?.type} sql={data?.sql} uri={data?.uri} />;
}

export default VisChart;
