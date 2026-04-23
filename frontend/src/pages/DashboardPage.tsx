import { useEffect, useState } from 'react';
import { PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
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
const DAYS_RU = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

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

      {/* KPI cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Всего площадок" value={stats.total_sites} icon="📍" />
        <KpiCard label="Активные камеры" value={stats.active_cameras} icon="📷" accent="green" />
        <KpiCard label="Оповещения" value={stats.open_alerts} sub="Открыть" icon="🔔" accent="yellow" />
        <KpiCard label="Чистых площадок" value={`${stats.clean_percent}%`} icon="✅" accent="green" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Donut */}
        <div className="bg-white rounded-xl p-5 border border-gray-200">
          <h2 className="font-semibold text-gray-900 mb-1">Статус площадок</h2>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width={160} height={160}>
              <PieChart>
                <Pie data={pieData} dataKey="value" innerRadius={45} outerRadius={70} paddingAngle={2}>
                  {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {pieData.map((d) => (
                <div key={d.name} className="flex items-center gap-2 text-sm">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: d.color }} />
                  {d.name}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Weekly chart */}
        <div className="bg-white rounded-xl p-5 border border-gray-200">
          <h2 className="font-semibold text-gray-900 mb-1">Проблемы за последние 7 дней</h2>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={weekData}>
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="#dbeafe" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Monthly chart */}
      <div className="bg-white rounded-xl p-5 border border-gray-200">
        <h2 className="font-semibold text-gray-900 mb-1">Проблемы за последний месяц</h2>
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={monthData}>
            <XAxis dataKey="day" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="#dbeafe" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function KpiCard({ label, value, icon, sub, accent }: {
  label: string; value: string | number; icon: string; sub?: string; accent?: string;
}) {
  return (
    <div className="bg-white rounded-xl p-4 border border-gray-200">
      <div className="flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">{label}</div>
          <div className="text-2xl font-bold text-gray-900">{value}</div>
          {sub && <div className="text-xs text-blue-500 mt-1 cursor-pointer">{sub} ↗</div>}
        </div>
        <span className={`text-xl p-2 rounded-full ${accent === 'green' ? 'bg-green-50' : accent === 'yellow' ? 'bg-yellow-50' : 'bg-gray-50'}`}>{icon}</span>
      </div>
    </div>
  );
}
