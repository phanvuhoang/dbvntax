import { useCategories } from '../api';
import { CATEGORIES, LOAI_LABELS } from '../types';

const LOAI_OPTIONS = ['LUAT', 'ND', 'TT', 'QD', 'NQ', 'VBHN', 'TTLT'] as const;

interface Props {
  selected: string;
  onSelect: (code: string) => void;
  loai: string;
  onLoaiChange: (loai: string) => void;
  hlFilter: string;
  onHlChange: (val: string) => void;
  dateAt: string;
  onDateAtChange: (val: string) => void;
}

export default function Sidebar({
  selected, onSelect,
  loai, onLoaiChange,
  hlFilter, onHlChange,
  dateAt, onDateAtChange,
}: Props) {
  const { data: apiCategories } = useCategories();

  const categories = apiCategories?.length
    ? apiCategories.map((c) => ({
        ...c,
        color: CATEGORIES.find((s) => s.code === c.code)?.color || 'gray',
      }))
    : CATEGORIES.map((c) => ({ ...c, count: 0 }));

  return (
    <aside className="w-48 min-w-[140px] bg-white border-r border-gray-200 overflow-y-auto flex-shrink-0 hidden md:block">
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

      {/* Loại VB */}
      <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider px-3 pt-4 pb-2">
        Loại văn bản
      </h3>
      <div className="px-3 pb-2 space-y-0.5">
        {LOAI_OPTIONS.map((code) => (
          <button
            key={code}
            onClick={() => onLoaiChange(loai === code ? '' : code)}
            className={`w-full text-left px-2 py-1 text-xs rounded transition
              ${loai === code ? 'bg-primary-light text-primary font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
          >
            {LOAI_LABELS[code]}
          </button>
        ))}
      </div>

      {/* Hiệu lực */}
      <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider px-3 pt-3 pb-2">
        Hiệu lực
      </h3>
      <div className="px-3 pb-2 space-y-0.5">
        {[
          { value: '', label: 'Tất cả' },
          { value: 'con_hieu_luc', label: 'Còn hiệu lực' },
          { value: 'het_hieu_luc', label: 'Hết hiệu lực' },
        ].map((opt) => (
          <label
            key={opt.value}
            className="flex items-center gap-1.5 px-2 py-1 text-xs text-gray-600 cursor-pointer hover:bg-gray-50 rounded"
          >
            <input
              type="radio"
              name="hl"
              checked={hlFilter === opt.value}
              onChange={() => onHlChange(opt.value)}
              className="accent-primary w-3 h-3"
            />
            {opt.label}
          </label>
        ))}
      </div>

      {/* Tại ngày */}
      <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider px-3 pt-3 pb-1">
        Tại ngày
      </h3>
      <div className="px-3 pb-3">
        <input
          type="date"
          value={dateAt}
          onChange={(e) => onDateAtChange(e.target.value)}
          className="w-full px-2 py-1 border border-gray-200 rounded bg-white text-xs text-gray-600 focus:border-primary focus:outline-none"
        />
        {dateAt && (
          <button
            onClick={() => onDateAtChange('')}
            className="text-[10px] text-gray-400 hover:text-primary mt-1"
          >
            ↺ Xóa ngày
          </button>
        )}
      </div>
    </aside>
  );
}
