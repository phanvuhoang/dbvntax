import type { Document, CongVan } from '../types';
import { LOAI_LABELS } from '../types';
import { useDocumentDetail, useCongVanDetail, formatDate } from '../api';
import HieuLucBadge from './HieuLucBadge';
import HieuLucDetail from './HieuLucDetail';

interface Props {
  item: Document | CongVan | null;
  tab: 'vanban' | 'congvan';
  onClose: () => void;
}

export default function DocDetail({ item, tab, onClose }: Props) {
  const docQuery = useDocumentDetail(tab === 'vanban' && item ? item.id : null);
  const cvQuery = useCongVanDetail(tab === 'congvan' && item ? item.id : null);

  if (!item) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-300 min-w-[280px]">
        <span className="text-5xl mb-3">📄</span>
        <span className="text-sm">Chọn một văn bản để xem nội dung</span>
      </div>
    );
  }

  const isLoading = tab === 'vanban' ? docQuery.isLoading : cvQuery.isLoading;
  const detail = tab === 'vanban' ? docQuery.data : cvQuery.data;
  const doc = detail ? { ...item, ...detail } as Document : (item as Document);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm min-w-[280px]">
        <svg className="animate-spin h-5 w-5 mr-2 text-primary" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Đang tải...
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden min-w-[280px]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-start gap-3 flex-shrink-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base font-bold text-gray-800">{doc.so_hieu || '—'}</h2>
            {tab === 'vanban' && <HieuLucBadge doc={doc} />}
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-lg leading-none flex-shrink-0 mt-0.5"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Title */}
        <p className="text-sm text-gray-800 font-medium leading-relaxed mb-3">
          {doc.ten}
        </p>

        {/* Meta */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 mb-4">
          {doc.ngay_ban_hanh && <span>Ngày: {formatDate(doc.ngay_ban_hanh)}</span>}
          {doc.loai && <span>Loại: {LOAI_LABELS[doc.loai] || doc.loai}</span>}
          {(doc as Document).category_name && <span>Danh mục: {(doc as Document).category_name}</span>}
          {(item as CongVan).co_quan && <span>Cơ quan: {(item as CongVan).co_quan}</span>}
        </div>

        {/* Tom tat */}
        {(doc as Document).tom_tat && (
          <div className="bg-gray-50 border-l-3 border-primary p-3 rounded text-sm text-gray-600 leading-relaxed mb-4">
            <strong className="text-gray-700">Tóm tắt:</strong> {(doc as Document).tom_tat}
          </div>
        )}

        {/* Hieu luc detail */}
        {tab === 'vanban' && doc.hieu_luc_index && (
          <HieuLucDetail index={doc.hieu_luc_index} />
        )}

        {/* Cong van specific */}
        {tab === 'congvan' && (detail as CongVan)?.ket_luan && (
          <div className="mt-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-1">Kết luận</h3>
            <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
              {(detail as CongVan).ket_luan}
            </p>
          </div>
        )}

        {/* Keywords */}
        {(doc as Document).keywords?.length ? (
          <div className="mt-4 flex flex-wrap gap-1">
            {(doc as Document).keywords!.map((k, i) => (
              <span key={i} className="bg-gray-100 text-gray-500 text-[11px] px-2 py-0.5 rounded">
                {k}
              </span>
            ))}
          </div>
        ) : null}

        {/* Links */}
        <div className="mt-6 flex gap-2">
          {(doc as Document).github_path && (
            <a
              href={`https://vntaxdoc.gpt4vn.com/docs/${(doc as Document).github_path}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-4 py-2 bg-primary text-white text-sm font-medium rounded hover:bg-primary-dark transition"
            >
              Xem văn bản gốc ↗
            </a>
          )}
          {(item as CongVan).link_nguon && (
            <a
              href={(item as CongVan).link_nguon}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-4 py-2 border border-gray-300 text-gray-600 text-sm rounded hover:border-primary hover:text-primary transition"
            >
              Xem nguồn ↗
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
