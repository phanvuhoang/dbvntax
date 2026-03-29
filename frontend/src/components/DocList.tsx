import { useState } from 'react';
import type { Document, CongVan } from '../types';
import { formatDate } from '../api';
import DocCard from './DocCard';

type SortOption = 'relevance' | 'date_desc' | 'date_asc';

function sortItems(items: (Document | CongVan)[], sort: SortOption): (Document | CongVan)[] {
  if (sort === 'relevance') return items; // already sorted by backend
  return [...items].sort((a, b) => {
    const da = a.ngay_ban_hanh ?? '';
    const db = b.ngay_ban_hanh ?? '';
    return sort === 'date_desc' ? db.localeCompare(da) : da.localeCompare(db);
  });
}

function Pagination({ page, totalPages, onPageChange }: {
  page: number; totalPages: number; onPageChange: (p: number) => void;
}) {
  const [jumpVal, setJumpVal] = useState('');

  const pages: (number | '...')[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    const start = Math.max(2, page - 2);
    const end = Math.min(totalPages - 1, page + 2);
    pages.push(1);
    if (start > 2) pages.push('...');
    for (let i = start; i <= end; i++) pages.push(i);
    if (end < totalPages - 1) pages.push('...');
    pages.push(totalPages);
  }

  const doJump = () => {
    const n = parseInt(jumpVal);
    if (!isNaN(n) && n >= 1 && n <= totalPages) {
      onPageChange(n);
      setJumpVal('');
    }
  };

  return (
    <div className="flex flex-col items-center gap-1.5 py-2 border-t border-gray-100 bg-white flex-shrink-0">
      <div className="flex items-center gap-1 flex-wrap justify-center">
        <button
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className="px-2 py-1 text-xs border border-gray-200 rounded text-gray-600 hover:border-primary hover:text-primary disabled:opacity-40 disabled:cursor-default"
        >←</button>
        {pages.map((p, i) =>
          p === '...' ? (
            <span key={`e${i}`} className="px-1 text-xs text-gray-400">…</span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p as number)}
              className={`w-7 h-7 text-xs rounded border transition ${
                p === page
                  ? 'bg-primary text-white border-primary font-medium'
                  : 'border-gray-200 text-gray-600 hover:border-primary hover:text-primary'
              }`}
            >{p}</button>
          )
        )}
        <button
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className="px-2 py-1 text-xs border border-gray-200 rounded text-gray-600 hover:border-primary hover:text-primary disabled:opacity-40 disabled:cursor-default"
        >→</button>
      </div>
      <div className="flex items-center gap-1">
        <span className="text-[10px] text-gray-400">Đến trang:</span>
        <input
          type="number"
          min={1}
          max={totalPages}
          value={jumpVal}
          onChange={(e) => setJumpVal(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && doJump()}
          className="w-12 px-1 py-0.5 text-xs border border-gray-200 rounded text-center focus:outline-none focus:border-primary"
        />
        <button
          onClick={doJump}
          className="px-2 py-0.5 text-[10px] border border-gray-200 rounded text-gray-500 hover:border-primary hover:text-primary transition"
        >Go</button>
      </div>
    </div>
  );
}

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
  isAdmin?: boolean;
  token?: string | null;
  onBulkDelete?: (ids: number[], source: 'documents' | 'cong_van') => void;
}

export default function DocList({
  items, total, page, limit, selectedId, tab, isLoading,
  onSelect, onPageChange,
  isAdmin, token, onBulkDelete,
}: Props) {
  const [deleteMode, setDeleteMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [sort, setSort] = useState<SortOption>('relevance');

  const totalPages = Math.max(1, Math.ceil(total / limit));

  const toggleId = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelectedIds(new Set(items.map(i => i.id)));
  const clearAll = () => setSelectedIds(new Set());

  const handleDelete = async () => {
    if (!window.confirm(`Xóa ${selectedIds.size} mục? Không thể hoàn tác!`)) return;
    const source = tab === 'vanban' ? 'documents' : 'cong_van';
    try {
      const res = await fetch('/api/admin/documents', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ ids: Array.from(selectedIds), source }),
      });
      const data = await res.json();
      if (res.ok) {
        alert(`Đã xóa ${data.count} mục`);
        setDeleteMode(false);
        setSelectedIds(new Set());
        onBulkDelete?.(Array.from(selectedIds), source);
      } else {
        alert(`Lỗi: ${data.detail || 'Không xóa được'}`);
      }
    } catch {
      alert('Lỗi khi xóa');
    }
  };

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
      <div className="px-3 py-2 text-xs text-gray-500 border-b border-gray-100 bg-white flex-shrink-0 flex items-center justify-between gap-1">
        <span className="shrink-0">{total} {tab === 'congvan' ? 'công văn' : 'kết quả'}</span>
        <div className="flex items-center gap-1 ml-auto">
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortOption)}
            className="text-[10px] border border-gray-200 rounded px-1 py-0.5 bg-white text-gray-500 focus:outline-none focus:border-primary cursor-pointer"
          >
            <option value="relevance">Liên quan nhất</option>
            <option value="date_desc">Mới nhất</option>
            <option value="date_asc">Cũ nhất</option>
          </select>
          {isAdmin && (
            <button
              onClick={() => { setDeleteMode(d => !d); setSelectedIds(new Set()); }}
              className={`text-xs px-2 py-1 rounded border transition ${
                deleteMode
                  ? 'bg-red-50 border-red-300 text-red-600'
                  : 'border-gray-200 text-gray-400 hover:border-red-300 hover:text-red-500'
              }`}
              title={deleteMode ? 'Hủy chọn' : 'Chọn để xóa'}
            >
              {deleteMode ? '✕ Hủy' : '🗑'}
            </button>
          )}
        </div>
      </div>

      {/* Results list */}
      <div className="flex-1 overflow-y-auto">
        {sortItems(items, sort).map((item) => {
          if (tab === 'congvan') {
            const cv = item as CongVan;
            return (
              <div
                key={cv.id}
                onClick={() => !deleteMode && onSelect(cv)}
                className={`px-3 py-2.5 border-b border-gray-100 cursor-pointer transition border-l-[3px]
                  ${cv.id === selectedId && !deleteMode
                    ? 'border-l-primary bg-primary-light'
                    : deleteMode && selectedIds.has(cv.id)
                      ? 'border-l-red-400 bg-red-50'
                      : 'border-l-transparent hover:bg-gray-50'}`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex items-baseline gap-2 min-w-0">
                    {deleteMode && (
                      <input
                        type="checkbox"
                        checked={selectedIds.has(cv.id)}
                        onChange={() => toggleId(cv.id)}
                        onClick={e => e.stopPropagation()}
                        className="accent-red-500 shrink-0"
                      />
                    )}
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
              isActive={doc.id === selectedId && !deleteMode}
              onClick={() => !deleteMode && onSelect(doc)}
              deleteMode={deleteMode}
              isSelected={selectedIds.has(doc.id)}
              onToggle={toggleId}
            />
          );
        })}
      </div>

      {/* Delete confirm bar */}
      {deleteMode && selectedIds.size > 0 && (
        <div className="sticky bottom-0 bg-red-50 border-t border-red-200 px-3 py-2 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-red-600 font-medium">Đã chọn {selectedIds.size}</span>
            <button onClick={selectAll} className="text-xs text-red-400 hover:text-red-600 underline">Tất cả</button>
            <button onClick={clearAll} className="text-xs text-gray-400 hover:text-gray-600 underline">Bỏ chọn</button>
          </div>
          <button
            onClick={handleDelete}
            className="px-3 py-1 bg-red-500 text-white text-xs font-medium rounded hover:bg-red-600 transition"
          >
            🗑 Xóa {selectedIds.size} mục
          </button>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} />
      )}
    </div>
  );
}
