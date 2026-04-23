import { useEffect, useState } from 'react';
import { MapPin, Camera as CameraIcon, Bell, CheckCircle2, ArrowUpRight } from 'lucide-react';
import { PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
import { getDashboardStats, getProblemsWeek, getProblemsMonth } from '../lib/api';

const PIE_COLORS: Record<string, string> = {
  clean: '#22c55e',
  overflow: '#eab308',
  contamination: '#ef4444',
};
const PIE_LABELS: Record<string, string> = {
  clean: 'Чисто',
  overflow: 'Переполнение',
  contamination: 'Загрязнение',
};

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [weekData, setWeekData] = useState<any[]>([]);
  const [monthData, setMonthData] = useState<any[]>([]);

  useEffect(() => {
    getDashboardStats().then(setStats);
    getProblemsWeek().then(setWeekData);
    getProblemsMonth().then(setMonthData);
  }, []);

  if (!stats) return <div className="text-gray-400 p-4">Загрузка...</div>;

  const pieData = Object.entries(stats.status_counts).map(([k, v]) => ({
    name: PIE_LABELS[k] || k,
    value: v as number,
    color: PIE_COLORS[k] || '#94a3b8',
  }));

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Панель управления</h1>
      <p className="text-sm text-gray-500 mb-6">Обзор состояния контейнерных площадок</p>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Всего площадок" value={stats.total_sites} Icon={MapPin} tint="slate" />
        <KpiCard label="Активные камеры" value={stats.active_cameras} Icon={CameraIcon} tint="green" />
        <KpiCard label="Оповещения" value={stats.open_alerts} sub="Открыть" Icon={Bell} tint="amber" />
        <KpiCard label="Чистых площадок" value={`${stats.clean_percent}%`} Icon={CheckCircle2} tint="green" />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card title="Статус площадок" subtitle="Распределение по состоянию">
          <div className="flex items-center gap-6 pt-2">
            <ResponsiveContainer width={160} height={160}>
              <PieChart>
                <Pie data={pieData} dataKey="value" innerRadius={48} outerRadius={72} paddingAngle={2}>
                  {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {pieData.map((d) => (
                <div key={d.name} className="flex items-center gap-2 text-sm">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: d.color }} />
                  <span className="text-gray-700">{d.name}</span>
                  <span className="text-gray-400 ml-auto font-mono">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card title="Проблемы за последние 7 дней" subtitle="Ежедневная динамика">
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={weekData}>
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="#dbeafe" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="Проблемы за последний месяц" subtitle="Ежедневная динамика">
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={monthData}>
            <XAxis dataKey="day" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="#dbeafe" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}

const TINTS: Record<string, { bg: string; fg: string }> = {
  slate: { bg: 'bg-slate-50', fg: 'text-slate-600' },
  green: { bg: 'bg-green-50', fg: 'text-green-600' },
  amber: { bg: 'bg-amber-50', fg: 'text-amber-600' },
};

function KpiCard({
  label, value, sub, Icon, tint = 'slate',
}: {
  label: string;
  value: string | number;
  sub?: string;
  Icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  tint?: keyof typeof TINTS;
}) {
  const t = TINTS[tint];
  return (
    <div className="bg-white rounded-xl p-4 border border-gray-200">
      <div className="flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">{label}</div>
          <div className="text-2xl font-bold text-gray-900">{value}</div>
          {sub && (
            <div className="text-xs text-sky-500 mt-1 inline-flex items-center gap-0.5 cursor-pointer">
              {sub} <ArrowUpRight size={12} />
            </div>
          )}
        </div>
        <span className={`p-2 rounded-full ${t.bg} ${t.fg}`}>
          <Icon size={18} strokeWidth={2} />
        </span>
      </div>
    </div>
  );
}

function Card({
  title, subtitle, children,
}: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl p-5 border border-gray-200">
      <h2 className="font-semibold text-gray-900">{title}</h2>
      {subtitle && <p className="text-xs text-gray-500 mb-2">{subtitle}</p>}
      {children}
    </div>
  );
}
