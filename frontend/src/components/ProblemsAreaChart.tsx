import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ProblemsPoint } from '../lib/types';

interface Props {
  data: ProblemsPoint[];
  height?: number;
  xTickFontSize?: number;
}

export default function ProblemsAreaChart({ data, height = 180, xTickFontSize = 11 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <XAxis dataKey="day" tick={{ fontSize: xTickFontSize }} />
        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip />
        <Area
          type="monotone"
          dataKey="count"
          stroke="#3b82f6"
          fill="#dbeafe"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
