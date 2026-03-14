import { LOAI_LABELS } from '../types';

interface Filters {
  loai: string;
  tinh_trang: string;
  dateAt: string;
}

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
}

const LOAI_OPTIONS = ['LUAT', 'ND', 'TT', 'QD', 'NQ', 'VBHN', 'TTLT'];

export default function FilterPanel({ filters, onChange }: Props) {
  const set = (key: keyof Filters, val: string) =>
    onChange({ ...filters, [key]: val });

  return (
    <div className="flex items-center gap-2 flex-wrap text-sm">
      {/* Loại VB */}
      <select
        value={filters.loai}
        onChange={(e) => set('loai', e.target.value)}
        className="px-2 py-1.5 border border-gray-300 rounded bg-white text-xs text-gray-600 focus:border-primary focus:outline-none"
      >
        <option value="">Loại VB</option>
        {LOAI_OPTIONS.map((k) => (
          <option key={k} value={k}>{LOAI_LABELS[k] || k}</option>
        ))}
      </select>

      {/* Hiệu lực */}
      <select
        value={filters.tinh_trang}
        onChange={(e) => set('tinh_trang', e.target.value)}
        className="px-2 py-1.5 border border-gray-300 rounded bg-white text-xs text-gray-600 focus:border-primary focus:outline-none"
      >
        <option value="">Hiệu lực</option>
        <option value="con_hieu_luc">Còn hiệu lực</option>
        <option value="het_hieu_luc">Hết hiệu lực</option>
      </select>

      {/* Date picker */}
      <input
        type="date"
        value={filters.dateAt}
        onChange={(e) => set('dateAt', e.target.value)}
        className="px-2 py-1.5 border border-gray-300 rounded bg-white text-xs text-gray-600 focus:border-primary focus:outline-none"
        title="Hiệu lực tại ngày"
      />

      {/* Reset */}
      {(filters.loai || filters.tinh_trang || filters.dateAt) && (
        <button
          onClick={() => onChange({ loai: '', tinh_trang: '', dateAt: '' })}
          className="text-xs text-gray-400 hover:text-primary"
        >
          ↺ Reset
        </button>
      )}
    </div>
  );
}
