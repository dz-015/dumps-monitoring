/** Full-area load failure with a retry button — replaces silent infinite "Загрузка...". */
export default function LoadError({
  message = 'Не удалось загрузить данные',
  onRetry,
}: {
  message?: string;
  onRetry: () => void;
}) {
  return (
    <div className="p-10 text-center">
      <p className="text-gray-500 mb-4">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="bg-sky-500 hover:bg-sky-600 text-white text-sm font-medium px-4 py-2 rounded-lg"
      >
        Повторить
      </button>
    </div>
  );
}

/** Inline (non-blocking) error banner for partial failures and failed actions. */
export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2.5 mb-4">
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="font-medium hover:underline whitespace-nowrap"
        >
          Повторить
        </button>
      )}
    </div>
  );
}
