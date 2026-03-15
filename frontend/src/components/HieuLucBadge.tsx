import { useState } from 'react';
import type { Document, HieuLucStatus } from '../types';

export function getHieuLucStatus(doc: Document): HieuLucStatus {
  if (!doc.hieu_luc_index) {
    if (doc.hl !== undefined) return doc.hl === 1 ? 'active' : 'inactive';
    const ts = doc.tinh_trang || '';
    if (ts === 'con_hieu_luc' || ts.toLowerCase().includes('còn hiệu lực')) return 'active';
    if (ts === 'het_hieu_luc' || ts.toLowerCase().includes('hết hiệu lực')) return 'inactive';
    return 'active';
  }
  const entries = doc.hieu_luc_index.hieu_luc ?? [];
  if (!entries.length) return doc.hl === 0 ? 'inactive' : 'active';
  const allExpired = entries.every(e => e.den_ngay !== null);
  if (allExpired || doc.hl === 0) return 'inactive';
  const hasExpired = entries.some(e => e.den_ngay !== null);
  if (hasExpired) return 'partial';
  return 'active';
}

const STATUS_CONFIG = {
  active: { bg: 'bg-green-100', text: 'text-green-800', label: 'Còn hiệu lực' },
  inactive: { bg: 'bg-red-100', text: 'text-red-800', label: 'Hết hiệu lực' },
  partial: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Hiệu lực một phần' },
} as const;

export default function HieuLucBadge({ doc, noTooltip }: { doc: Document; noTooltip?: boolean }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const status = getHieuLucStatus(doc);
  const config = STATUS_CONFIG[status];
  const summary = !noTooltip ? doc.hieu_luc_index?.tom_tat_hieu_luc : undefined;

  return (
    <span
      className={`relative inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}
      onMouseEnter={() => summary && setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {config.label}
      {showTooltip && summary && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2 bg-gray-900 text-white text-xs rounded shadow-lg z-50 whitespace-normal">
          {summary}
        </span>
      )}
    </span>
  );
}
