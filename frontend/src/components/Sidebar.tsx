import { useState } from 'react';
import { useCategories, useCongVanTaxonomy } from '../api';
import { CATEGORIES, SAC_THUE_MAP } from '../types';

// Mapping từ CATEGORIES codes (CIT/VAT) sang DB codes (TNDN/GTGT)
export const CATEGORY_TO_DB: Record<string, string> = {
  CIT:     'TNDN',
  VAT:     'GTGT',
  PIT:     'TNCN',
  HDDT:    'HOA_DON',
  SCT:     'TTDB',
  TP:      'GDLK',
  QLT:     'QLT',
  FCT:     'FCT',
  HKD:     'HKD',
  THUE_QT: 'THUE_QT',
};

// DB code → display name
const DB_TO_NAME: Record<string, string> = {
  TNDN:           'Thuế TNDN',
  GTGT:           'Thuế GTGT',
  TNCN:           'Thuế TNCN',
  HOA_DON:        'Hóa đơn',
  TTDB:           'Thuế TTĐB',
  GDLK:           'Giao dịch LK',
  QLT:            'Quản lý thuế',
  FCT:            'Thuế nhà thầu',
  HKD:            'Hộ kinh doanh',
  THUE_QT:        'Thuế Quốc tế',
  XNK:            'Xuất nhập khẩu',
  TAI_NGUYEN_DAT: 'Tài nguyên/Đất',
  MON_BAI_PHI:    'Môn bài/Phí',
};

interface Props {
  selected: string;
  onSelect: (code: string) => void;
  dateFrom: string;
  dateTo: string;
  onDateRangeChange: (from: string, to: string) => void;
  tab: 'vanban' | 'congvan';
  selectedChuDe?: string;
  onChuDeSelect?: (chuDe: string) => void;
}

export default function Sidebar({
  selected, onSelect,
  dateFrom, dateTo, onDateRangeChange,
  tab,
  selectedChuDe = '',
  onChuDeSelect,
}: Props) {
  const { data: apiCategories } = useCategories();
  const { data: taxonomy } = useCongVanTaxonomy();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const categories = apiCategories?.length
    ? apiCategories.map((c) => ({
        ...c,
        color: CATEGORIES.find((s) => s.code === c.code)?.color || 'gray',
      }))
    : CATEGORIES.map((c) => ({ ...c, count: 0 }));

  const toggleExpand = (code: string) => {
    setExpanded((prev) => ({ ...prev, [code]: !prev[code] }));
  };

  return (
    <aside className="w-full h-full bg-white border-r border-gray-200 overflow-y-auto">
      <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider px-3 pt-3 pb-2">
        Sắc thuế
      </h3>

      {/* Tất cả */}
      <button
        onClick={() => { onSelect(''); onChuDeSelect?.(''); }}
        className={`w-full flex justify-between items-center px-3 py-1.5 text-sm transition
          ${!selected ? 'bg-primary-light text-primary font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
      >
        <span>Tất cả</span>
      </button>

      {tab === 'vanban' ? (
        /* ── FLAT MODE (tab Văn Bản) ── */
        categories.map((cat) => (
          <button
            key={cat.code}
            onClick={() => onSelect(cat.code === selected ? '' : cat.code)}
            className={`w-full flex justify-between items-center px-3 py-1.5 text-sm transition
              ${cat.code === selected
                ? 'bg-primary-light text-primary font-semibold'
                : 'text-gray-600 hover:bg-gray-50'}`}
          >
            <span>{cat.name}</span>
            {cat.count > 0 && (
              <span className={`text-[11px] rounded-full px-1.5 min-w-[20px] text-center
                ${cat.code === selected ? 'bg-primary text-white' : 'bg-gray-100 text-gray-500'}`}>
                {cat.count}
              </span>
            )}
          </button>
        ))
      ) : (
        /* ── ACCORDION MODE (tab Công Văn) ── */
        <>
          {Object.entries(taxonomy ?? {})
            .sort(([, a], [, b]) => {
              const sumA = a.reduce((s, i) => s + i.count, 0);
              const sumB = b.reduce((s, i) => s + i.count, 0);
              return sumB - sumA;
            })
            .map(([dbCode, items]) => {
              const isSelected = selected === dbCode;
              const isExpanded = expanded[dbCode];
              const totalCount = items.reduce((s, i) => s + i.count, 0);
              const displayName = DB_TO_NAME[dbCode] ?? SAC_THUE_MAP[dbCode] ?? dbCode;

              return (
                <div key={dbCode}>
                  {/* Header sắc thuế */}
                  <div className="flex items-center">
                    <button
                      onClick={() => {
                        onSelect(isSelected && !selectedChuDe ? '' : dbCode);
                        onChuDeSelect?.('');
                      }}
                      className={`flex-1 flex justify-between items-center px-3 py-1.5 text-sm transition text-left
                        ${isSelected
                          ? 'bg-primary-light text-primary font-semibold'
                          : 'text-gray-600 hover:bg-gray-50'}`}
                    >
                      <span>{displayName}</span>
                      {totalCount > 0 && (
                        <span className={`text-[11px] rounded-full px-1.5 min-w-[20px] text-center mr-1
                          ${isSelected ? 'bg-primary text-white' : 'bg-gray-100 text-gray-500'}`}>
                          {totalCount}
                        </span>
                      )}
                    </button>

                    <button
                      onClick={() => toggleExpand(dbCode)}
                      className="px-2 py-1.5 text-gray-400 hover:text-primary transition flex-shrink-0"
                      aria-label={isExpanded ? 'Thu gọn' : 'Mở rộng'}
                    >
                      <span className={`text-[10px] inline-block transition-transform duration-150
                        ${isExpanded ? 'rotate-90' : ''}`}>
                        ▶
                      </span>
                    </button>
                  </div>

                  {/* Chu_de items */}
                  {isExpanded && (
                    <div className="border-l-2 border-primary-light ml-3">
                      <button
                        onClick={() => { onSelect(dbCode); onChuDeSelect?.(''); }}
                        className={`w-full text-left px-3 py-1 text-xs transition
                          ${isSelected && !selectedChuDe
                            ? 'text-primary font-semibold'
                            : 'text-gray-500 hover:text-primary hover:bg-gray-50'}`}
                      >
                        — Tất cả
                      </button>

                      {items.slice(0, 12).map((item) => (
                        <button
                          key={item.chu_de}
                          onClick={() => {
                            onSelect(dbCode);
                            onChuDeSelect?.(item.chu_de);
                          }}
                          className={`w-full flex justify-between items-center px-3 py-1 text-xs transition
                            ${selectedChuDe === item.chu_de && isSelected
                              ? 'text-primary font-semibold bg-primary-light'
                              : 'text-gray-500 hover:text-primary hover:bg-gray-50'}`}
                        >
                          <span className="truncate pr-1">{item.chu_de}</span>
                          <span className="text-[10px] text-gray-400 flex-shrink-0">{item.count}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
        </>
      )}

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
