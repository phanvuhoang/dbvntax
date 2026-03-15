import type { Document } from '../types';
import { LOAI_LABELS, SAC_THUE_MAP } from '../types';
import { formatDate } from '../api';
import HieuLucBadge from './HieuLucBadge';

interface Props {
  doc: Document;
  isActive: boolean;
  onClick: () => void;
}

const SAC_COLORS: Record<string, string> = {
  QLT: '#607d8b', CIT: '#2e7d32', TNDN: '#2e7d32', VAT: '#1565c0', GTGT: '#1565c0',
  HDDT: '#7b1fa2', HOA_DON: '#ef6c00', PIT: '#6a1b9a', TNCN: '#6a1b9a',
  SCT: '#c62828', TTDB: '#c62828', FCT: '#00838f', NHA_THAU: '#00838f',
  TP: '#4527a0', GDLK: '#4527a0', HKD: '#2e7d32',
};

export default function DocCard({ doc, isActive, onClick }: Props) {
  const loaiLabel = LOAI_LABELS[doc.loai] || doc.loai || '';

  return (
    <div
      onClick={onClick}
      className={`px-3 py-2.5 border-b border-gray-100 cursor-pointer transition border-l-[3px]
        ${isActive
          ? 'border-l-primary bg-primary-light'
          : 'border-l-transparent hover:bg-gray-50'}`}
    >
      {/* Top row: so_hieu + loai badge */}
      <div className="flex justify-between items-start gap-2">
        <span className="text-primary font-semibold text-sm">{doc.so_hieu || '—'}</span>
        {loaiLabel && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-600 flex-shrink-0">
            {loaiLabel}
          </span>
        )}
      </div>

      {/* Title */}
      <p className="text-sm text-gray-700 mt-1 line-clamp-2 leading-snug">
        {doc.ten || '—'}
      </p>

      {/* Meta row */}
      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
        {doc.ngay_ban_hanh && (
          <span className="text-gray-400 text-xs">
            {formatDate(doc.ngay_ban_hanh)}
          </span>
        )}
        <HieuLucBadge doc={doc} />
        {(doc.sac_thue || []).map((s) => (
          <span
            key={s}
            className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium text-white"
            style={{ backgroundColor: SAC_COLORS[s] || '#666' }}
          >
            {SAC_THUE_MAP[s] || s}
          </span>
        ))}
      </div>

      {/* Snippet */}
      {doc.snippet && (
        <p className="text-xs text-gray-500 mt-1 line-clamp-2 leading-relaxed">
          {doc.snippet}
        </p>
      )}
    </div>
  );
}
