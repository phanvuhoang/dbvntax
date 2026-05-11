interface ChipProps {
  label: string;
  onRemove?: () => void;
  active?: boolean;
  color?: string;
  onClick?: () => void;
  className?: string;
}

export default function Chip({ label, onRemove, active, color, onClick, className = '' }: ChipProps) {
  const base = `inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition cursor-pointer select-none`;

  const style = color
    ? { backgroundColor: color + '22', color, borderColor: color + '44' }
    : undefined;

  const activeClass = active
    ? 'bg-primary text-white border border-primary'
    : 'bg-white text-gray-600 border border-gray-200 hover:border-primary hover:text-primary';

  return (
    <span
      className={`${base} ${color ? 'border' : activeClass} ${className}`}
      style={style}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
    >
      {label}
      {onRemove && (
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          className="ml-0.5 hover:text-red-500 transition"
          aria-label="Remove"
        >
          ✕
        </button>
      )}
    </span>
  );
}
