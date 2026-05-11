import type { Document } from '../types';
import { LOAI_LABELS, SAC_THUE_MAP } from '../types';
import { formatDate } from '../api';
import HieuLucBadge from './HieuLucBadge';

interface Props {
  doc: Document;
  isActive: boolean;
  onClick: () => void;
  deleteMode?: boolean;
  isSelected?: boolean;
  onToggle?: (id: number) => void;
}

const SAC_COLORS: Record<string, string> = {
  QLT: '#607d8b', CIT: '#2e7d32', TNDN: '#2e7d32', VAT: '#1565c0', GTGT: '#1565c0',
  HDDT: '#7b1fa2', HOA_DON: '#ef6c00', PIT: '#6a1b9a', TNCN: '#6a1b9a',
  SCT: '#c62828', TTDB: '#c62828', FCT: '#00838f', NHA_THAU: '#00838f',
  TP: '#4527a0', GDLK: '#4527a0', HKD: '#2e7d32',
};

export default function DocCard({ doc, isActive, onClick, deleteMode, isSelected, onToggle }: Props) {
  const loaiLabel = LOAI_LABELS[doc.loai] || doc.loai || '';
  const hasSource = !!(doc.tvpl_url || doc.source);

  return (
    <div
      onClick={onClick}
      className={`
        px-3 py-3 border-b border-gray-100 cursor-pointer transition-all duration-150
        border-l-[3px] group
        ${isActive
          ? 'border-l-primary bg-primary-light shadow-sm'
          : deleteMode && isSelected
            ? 'border-l-red-400 bg-red-50'
            : 'border-l-transparent hover:bg-gray-50 hover:shadow-sm hover:border-l-gray-200'
        }
      `}
    >
      {/* Top row: checkbox (delete mode) + type icon + so_hieu + loai badge */}
      <div className="flex justify-between items-start gap-2">
        <div className="flex items-start gap-2 min-w-0">
          {deleteMode && (
            <input
              type="checkbox"
              checked={!!isSelected}
              onChange={e => { e.stopPropagation(); onToggle?.(doc.id); }}
              onClick={e => e.stopPropagation()}
              className="mt-0.5 accent-red-500 shrink-0"
            />
          )}
          <span className="font-mono font-semibold text-xs text-primary tracking-tight shrink-0">
            {doc.so_hieu || '—'}
          </span>
          {(doc as Document).is_anchor && (
            <span className="text-yellow-500 text-xs shrink-0" title="Văn bản quan trọng">⭐</span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {hasSource && (
            <span className="text-[9px] px-1 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-100 font-medium">
              {doc.source === 'upload' ? 'UP' : doc.source === 'manual' ? 'MN' : doc.tvpl_url ? 'TVPL' : doc.source?.toUpperCase() || 'EXT'}
            </span>
          )}
          {loaiLabel && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-500">
              {loaiLabel}
            </span>
          )}
        </div>
      </div>

      {/* Title */}
      <p className="text-sm text-gray-700 mt-1.5 line-clamp-2 leading-snug font-medium">
        {doc.ten || '—'}
      </p>

      {/* Meta row */}
      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
        {doc.ngay_ban_hanh && (
          <span className="text-gray-400 text-[11px]">
            {formatDate(doc.ngay_ban_hanh)}
          </span>
        )}
        <HieuLucBadge doc={doc} noTooltip />
        {(doc.sac_thue || []).slice(0, 3).map((s) => (
          <span
            key={s}
            className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium text-white"
            style={{ backgroundColor: SAC_COLORS[s] || '#666' }}
          >
            {SAC_THUE_MAP[s] || s}
          </span>
        ))}
        {(doc.sac_thue || []).length > 3 && (
          <span className="text-[10px] text-gray-400">+{(doc.sac_thue || []).length - 3}</span>
        )}
      </div>

      {/* Snippet */}
      {doc.snippet && (
        <p className="text-xs text-gray-400 mt-1.5 line-clamp-2 leading-relaxed">
          {doc.snippet}
        </p>
      )}
    </div>
  );
}
