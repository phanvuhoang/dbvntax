import { useCategories } from '../api';
import { CATEGORIES } from '../types';

interface Props {
  selected: string;
  onSelect: (code: string) => void;
  dateFrom: string;
  dateTo: string;
  onDateRangeChange: (from: string, to: string) => void;
}

export default function Sidebar({
  selected, onSelect,
  dateFrom, dateTo, onDateRangeChange,
}: Props) {
  const { data: apiCategories } = useCategories();

  const categories = apiCategories?.length
    ? apiCategories.map((c) => ({
        ...c,
        color: CATEGORIES.find((s) => s.code === c.code)?.color || 'gray',
      }))
    : CATEGORIES.map((c) => ({ ...c, count: 0 }));

  return (
    <aside className="w-full h-full bg-white border-r border-gray-200 overflow-y-auto">
      {/* Danh mục */}
      <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider px-3 pt-3 pb-2">
        Sắc thuế
      </h3>

      <button
        onClick={() => onSelect('')}
        className={`w-full flex justify-between items-center px-3 py-1.5 text-sm transition
          ${!selected ? 'bg-primary-light text-primary font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
      >
        <span>Tất cả</span>
      </button>

      {categories.map((cat) => (
        <button
          key={cat.code}
          onClick={() => onSelect(cat.code === selected ? '' : cat.code)}
          className={`w-full flex justify-between items-center px-3 py-1.5 text-sm transition
            ${cat.code === selected ? 'bg-primary-light text-primary font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
        >
          <span>{cat.name}</span>
          {cat.count > 0 && (
            <span
              className={`text-[11px] rounded-full px-1.5 min-w-[20px] text-center
                ${cat.code === selected ? 'bg-primary text-white' : 'bg-gray-100 text-gray-500'}`}
            >
              {cat.count}
            </span>
          )}
        </button>
      ))}

      {/* Giai đoạn ban hành */}
      <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider px-3 pt-4 pb-2">
        Giai đoạn ban hành
      </h3>
      <div className="px-3 pb-3 space-y-2">
        <div>
          <label className="text-[10px] text-gray-400 uppercase tracking-wide block mb-1">Từ ngày</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => onDateRangeChange(e.target.value, dateTo)}
            className="w-full px-2 py-1 border border-gray-200 rounded bg-white text-xs text-gray-600 focus:border-primary focus:outline-none"
          />
        </div>
        <div>
          <label className="text-[10px] text-gray-400 uppercase tracking-wide block mb-1">Đến ngày</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => onDateRangeChange(dateFrom, e.target.value)}
            className="w-full px-2 py-1 border border-gray-200 rounded bg-white text-xs text-gray-600 focus:border-primary focus:outline-none"
          />
        </div>
        {(dateFrom || dateTo) && (
          <button
            onClick={() => onDateRangeChange('', '')}
            className="w-full text-xs text-gray-400 hover:text-primary py-1 border border-gray-200 rounded hover:border-primary transition"
          >
            ↺ Reset bộ lọc
          </button>
        )}
      </div>
    </aside>
  );
}
