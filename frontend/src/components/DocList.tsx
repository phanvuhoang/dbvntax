import type { Document, CongVan } from '../types';
import { formatDate } from '../api';
import DocCard from './DocCard';

interface Props {
  items: (Document | CongVan)[];
  total: number;
  page: number;
  limit: number;
  selectedId: number | null;
  tab: 'vanban' | 'congvan';
  isLoading: boolean;
  onSelect: (item: Document | CongVan) => void;
  onPageChange: (page: number) => void;
}

export default function DocList({
  items, total, page, limit, selectedId, tab, isLoading,
  onSelect, onPageChange,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / limit));

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        <svg className="animate-spin h-5 w-5 mr-2 text-primary" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Đang tải...
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-400 text-sm gap-2 p-8">
        <span className="text-4xl">📭</span>
        <span>Không tìm thấy kết quả</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Results header */}
      <div className="px-3 py-2 text-xs text-gray-500 border-b border-gray-100 bg-white flex-shrink-0">
        {total} {tab === 'congvan' ? 'công văn' : 'kết quả'}
      </div>

      {/* Results list */}
      <div className="flex-1 overflow-y-auto">
        {items.map((item) => {
          if (tab === 'congvan') {
            const cv = item as CongVan;
            return (
              <div
                key={cv.id}
                onClick={() => onSelect(cv)}
                className={`px-3 py-2.5 border-b border-gray-100 cursor-pointer transition border-l-[3px]
                  ${cv.id === selectedId
                    ? 'border-l-primary bg-primary-light'
                    : 'border-l-transparent hover:bg-gray-50'}`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex items-baseline gap-2 min-w-0">
                    <span className="text-primary font-semibold text-sm shrink-0">{cv.so_hieu || '—'}</span>
                    {cv.ngay_ban_hanh && (
                      <span className="text-[11px] text-gray-400 shrink-0">{formatDate(cv.ngay_ban_hanh)}</span>
                    )}
                  </div>
                  <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium shrink-0 ml-1">CV</span>
                </div>
                <p className="text-sm text-gray-700 mt-1 line-clamp-2 leading-snug select-text">{cv.ten}</p>
                {cv.co_quan && <p className="text-xs text-gray-400 mt-1 select-text">{cv.co_quan}</p>}
              </div>
            );
          }
          const doc = item as Document;
          return (
            <DocCard
              key={doc.id}
              doc={doc}
              isActive={doc.id === selectedId}
              onClick={() => onSelect(doc)}
            />
          );
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 py-2 border-t border-gray-100 bg-white flex-shrink-0">
          <button
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="px-3 py-1 text-xs border border-gray-200 rounded text-gray-600 hover:border-primary hover:text-primary disabled:opacity-40 disabled:cursor-default"
          >
            ← Trước
          </button>
          <span className="text-xs text-gray-500">{page}/{totalPages}</span>
          <button
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="px-3 py-1 text-xs border border-gray-200 rounded text-gray-600 hover:border-primary hover:text-primary disabled:opacity-40 disabled:cursor-default"
          >
            Sau →
          </button>
        </div>
      )}
    </div>
  );
}
