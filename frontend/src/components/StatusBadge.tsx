const COLORS: Record<string, { bg: string; text: string; label: string }> = {
  clean: { bg: 'bg-green-100', text: 'text-green-700', label: 'Чисто' },
  overflow: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Переполнение' },
  contamination: { bg: 'bg-red-100', text: 'text-red-700', label: 'Загрязнение' },
  new: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Новый' },
  accepted: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Принят' },
  resolved: { bg: 'bg-green-100', text: 'text-green-700', label: 'Решён' },
};

export default function StatusBadge({ value }: { value: string }) {
  const c = COLORS[value] || { bg: 'bg-gray-100', text: 'text-gray-700', label: value };
  return (
    <span
      className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${c.bg} ${c.text}`}
    >
      {c.label}
    </span>
  );
}
