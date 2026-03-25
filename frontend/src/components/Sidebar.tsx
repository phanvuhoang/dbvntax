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

// DB code → canonical code (for accordion mode icon lookup)
const DB_TO_CANONICAL: Record<string, string> = {
  TNDN: 'CIT', GTGT: 'VAT', TNCN: 'PIT', HOA_DON: 'HDDT',
  TTDB: 'SCT', GDLK: 'TP', QLT: 'QLT', FCT: 'FCT', HKD: 'HKD', THUE_QT: 'THUE_QT',
};

// Icon abbreviations + colors for each canonical category code
const CATEGORY_ICONS: Record<string, { abbr: string; color: string }> = {
  CIT:     { abbr: 'CIT', color: 'bg-green-100 text-green-700' },
  VAT:     { abbr: 'VAT', color: 'bg-teal-100 text-teal-700' },
  PIT:     { abbr: 'PIT', color: 'bg-blue-100 text-blue-700' },
  SCT:     { abbr: 'SST', color: 'bg-orange-100 text-orange-700' },
  QLT:     { abbr: 'ADM', color: 'bg-gray-100 text-gray-600' },
  HDDT:    { abbr: 'INV', color: 'bg-yellow-100 text-yellow-700' },
  FCT:     { abbr: 'FCT', color: 'bg-purple-100 text-purple-700' },
  THUE_QT: { abbr: 'INT', color: 'bg-indigo-100 text-indigo-700' },
  TP:      { abbr: 'TP',  color: 'bg-pink-100 text-pink-700' },
  HKD:     { abbr: 'BH',  color: 'bg-lime-100 text-lime-700' },
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
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export default function Sidebar({
  selected, onSelect,
  dateFrom, dateTo, onDateRangeChange,
  tab,
  selectedChuDe = '',
  onChuDeSelect,
  collapsed,
  onToggleCollapse,
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
    <aside className={`h-full bg-white border-r border-gray-200 flex flex-col ${collapsed ? 'w-10 overflow-hidden' : 'w-full overflow-y-auto'}`}>

      {/* Toggle button + header */}
      <div className="flex items-center justify-between px-2 pt-2 pb-1 flex-shrink-0">
        {!collapsed && (
          <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">
            Sắc thuế
          </h3>
        )}
        <button
          onClick={onToggleCollapse}
          title={collapsed ? 'Mở rộng sidebar' : 'Thu gọn sidebar'}
          className="ml-auto p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition"
        >
          {collapsed ? (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          )}
        </button>
      </div>

      {/* Tất cả */}
      {collapsed ? (
        <button
          title="Tất cả"
          onClick={() => { onSelect(''); onChuDeSelect?.(''); }}
          className={`w-full flex justify-center items-center py-2 transition
            ${!selected ? 'bg-primary-light' : 'hover:bg-gray-50'}`}
        >
          <span className="text-[9px] font-bold px-1.5 py-1 rounded bg-gray-100 text-gray-500">ALL</span>
        </button>
      ) : (
        <button
          onClick={() => { onSelect(''); onChuDeSelect?.(''); }}
          className={`w-full flex justify-between items-center px-3 py-1.5 text-sm transition
            ${!selected ? 'bg-primary-light text-primary font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
        >
          <span>Tất cả</span>
        </button>
      )}

      {/* Category list */}
      <div className={collapsed ? '' : 'flex-1'}>
        {tab === 'vanban' ? (
          /* ── FLAT MODE (tab Văn Bản) ── */
          categories.map((cat) => {
            const icon = CATEGORY_ICONS[cat.code];
            const isSelected = cat.code === selected;
            if (collapsed) {
              return (
                <button
                  key={cat.code}
                  title={cat.name}
                  onClick={() => onSelect(isSelected ? '' : cat.code)}
                  className={`w-full flex justify-center items-center py-2 transition
                    ${isSelected ? 'bg-primary-light' : 'hover:bg-gray-50'}`}
                >
                  <span className={`text-[9px] font-bold px-1.5 py-1 rounded ${icon?.color || 'bg-gray-100 text-gray-500'}`}>
                    {icon?.abbr || cat.code.slice(0, 3)}
                  </span>
                </button>
              );
            }
            return (
              <button
                key={cat.code}
                onClick={() => onSelect(isSelected ? '' : cat.code)}
                className={`w-full flex items-center px-3 py-1.5 text-sm transition
                  ${isSelected ? 'bg-primary-light text-primary font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
              >
                {icon && (
                  <span className={`text-[9px] font-bold px-1 py-0.5 rounded mr-1.5 shrink-0 ${icon.color}`}>
                    {icon.abbr}
                  </span>
                )}
                <span className="flex-1 text-left truncate">{cat.name}</span>
                {cat.count > 0 && (
                  <span className={`text-[11px] rounded-full px-1.5 min-w-[20px] text-center
                    ${isSelected ? 'bg-primary text-white' : 'bg-gray-100 text-gray-500'}`}>
                    {cat.count}
                  </span>
                )}
              </button>
            );
          })
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
                const canonicalCode = DB_TO_CANONICAL[dbCode] ?? dbCode;
                const icon = CATEGORY_ICONS[canonicalCode];

                if (collapsed) {
                  return (
                    <button
                      key={dbCode}
                      title={displayName}
                      onClick={() => { onSelect(isSelected && !selectedChuDe ? '' : dbCode); onChuDeSelect?.(''); }}
                      className={`w-full flex justify-center items-center py-2 transition
                        ${isSelected ? 'bg-primary-light' : 'hover:bg-gray-50'}`}
                    >
                      <span className={`text-[9px] font-bold px-1.5 py-1 rounded ${icon?.color || 'bg-gray-100 text-gray-500'}`}>
                        {icon?.abbr || dbCode.slice(0, 3)}
                      </span>
                    </button>
                  );
                }

                return (
                  <div key={dbCode}>
                    <div className="flex items-center">
                      <button
                        onClick={() => {
                          onSelect(isSelected && !selectedChuDe ? '' : dbCode);
                          onChuDeSelect?.('');
                        }}
                        className={`flex-1 flex items-center px-3 py-1.5 text-sm transition text-left
                          ${isSelected ? 'bg-primary-light text-primary font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
                      >
                        {icon && (
                          <span className={`text-[9px] font-bold px-1 py-0.5 rounded mr-1.5 shrink-0 ${icon.color}`}>
                            {icon.abbr}
                          </span>
                        )}
                        <span className="flex-1 truncate">{displayName}</span>
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
                        <span className={`text-[10px] inline-block transition-transform duration-150 ${isExpanded ? 'rotate-90' : ''}`}>
                          ▶
                        </span>
                      </button>
                    </div>

                    {isExpanded && (
                      <div className="border-l-2 border-primary-light ml-3">
                        <button
                          onClick={() => { onSelect(dbCode); onChuDeSelect?.(''); }}
                          className={`w-full text-left px-3 py-1 text-xs transition
                            ${isSelected && !selectedChuDe ? 'text-primary font-semibold' : 'text-gray-500 hover:text-primary hover:bg-gray-50'}`}
                        >
                          — Tất cả
                        </button>
                        {items.slice(0, 12).map((item) => (
                          <button
                            key={item.chu_de}
                            onClick={() => { onSelect(dbCode); onChuDeSelect?.(item.chu_de); }}
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
      </div>

      {/* Giai đoạn ban hành — hidden when collapsed */}
      {!collapsed && (
        <div className="flex-shrink-0">
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
        </div>
      )}
    </aside>
  );
}
