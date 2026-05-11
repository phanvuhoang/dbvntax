interface EmptyStateProps {
  title?: string;
  hint?: string;
  icon?: string;
}

export default function EmptyState({
  title = 'Không tìm thấy kết quả',
  hint = 'Hãy thử từ khóa khác, hoặc chọn sắc thuế ở sidebar',
  icon = '📭',
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-6 text-center gap-3">
      <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center text-2xl">
        {icon}
      </div>
      <div>
        <p className="text-sm font-medium text-gray-600">{title}</p>
        {hint && (
          <p className="text-xs text-gray-400 mt-1 max-w-[240px]">{hint}</p>
        )}
      </div>
    </div>
  );
}
