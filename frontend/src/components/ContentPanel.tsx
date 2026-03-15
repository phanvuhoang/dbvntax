import { useState } from 'react';
import type { Document, CongVan } from '../types';
import { LOAI_LABELS, SAC_THUE_MAP } from '../types';
import { useDocumentDetail, useCongVanDetail, formatDate } from '../api';
import HieuLucBadge from './HieuLucBadge';
import HieuLucDetail from './HieuLucDetail';
import AIAnalysis from './AIAnalysis';

interface Props {
  item: Document | CongVan | null;
  tab: 'vanban' | 'congvan';
  token: string | null;
  onRequestLogin: () => void;
}

export default function ContentPanel({ item, tab, token, onRequestLogin }: Props) {
  const [showAI, setShowAI] = useState(false);
  const docQuery = useDocumentDetail(tab === 'vanban' && item ? item.id : null);
  const cvQuery = useCongVanDetail(tab === 'congvan' && item ? item.id : null);

  if (!item) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-400 gap-2 min-w-[300px]">
        <span className="text-4xl">📄</span>
        <span className="text-sm">Chọn văn bản để xem nội dung</span>
      </div>
    );
  }

  const isLoading = tab === 'vanban' ? docQuery.isLoading : cvQuery.isLoading;
  const detail = tab === 'vanban' ? docQuery.data : cvQuery.data;
  const doc = detail ? { ...item, ...detail } as Document : (item as Document);
  const cv = detail ? { ...item, ...detail } as CongVan : (item as CongVan);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm min-w-[300px]">
        <svg className="animate-spin h-5 w-5 mr-2 text-primary" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Đang tải...
      </div>
    );
  }

  const content = tab === 'vanban' ? doc.noi_dung : cv.noi_dung_day_du;

  if (showAI) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden min-w-[300px]">
        <div className="px-4 py-2 border-b border-gray-200 flex items-center justify-between flex-shrink-0 bg-gray-50">
          <span className="text-sm font-semibold text-gray-700">🤖 Phân tích AI — {doc.so_hieu || cv.so_hieu}</span>
          <button onClick={() => setShowAI(false)} className="text-xs text-gray-400 hover:text-primary">← Quay lại</button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <AIAnalysis
            token={token}
            docId={item.id}
            docSource={tab === 'congvan' ? 'cong_van' : 'documents'}
            onRequestLogin={onRequestLogin}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden min-w-[300px]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 flex-shrink-0 bg-white">
        <h2 className="font-semibold text-gray-800 text-sm leading-snug">{doc.ten || cv.ten}</h2>
        <div className="flex gap-3 mt-1 text-xs text-gray-500 items-center flex-wrap">
          {doc.ngay_ban_hanh && <span>{formatDate(doc.ngay_ban_hanh)}</span>}
          {doc.loai && (
            <>
              <span>•</span>
              <span>{LOAI_LABELS[doc.loai] || doc.loai}</span>
            </>
          )}
          {(item as CongVan).co_quan && (
            <>
              <span>•</span>
              <span>{(item as CongVan).co_quan}</span>
            </>
          )}
          {tab === 'vanban' && <HieuLucBadge doc={doc} />}
        </div>

        {(doc.sac_thue ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {(doc.sac_thue ?? []).map((s) => (
              <span key={s} className="text-[11px] px-2 py-0.5 rounded bg-primary-light text-primary font-medium">
                {SAC_THUE_MAP[s] || s}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Hieu luc section */}
      {tab === 'vanban' && (
        <div className="px-4 flex-shrink-0">
          {doc.hieu_luc_index && (doc.hieu_luc_index.hieu_luc ?? []).length > 0 ? (
            <HieuLucDetail index={doc.hieu_luc_index} />
          ) : (
            <div className="mt-3 p-3 bg-gray-50 rounded text-sm text-gray-400 italic">
              Chưa có thông tin hiệu lực chi tiết
            </div>
          )}
        </div>
      )}

      {/* Tom tat */}
      {doc.tom_tat && (
        <div className="px-4 mt-3 flex-shrink-0">
          <div className="bg-gray-50 border-l-[3px] border-primary p-3 rounded text-sm text-gray-600 leading-relaxed">
            <strong className="text-gray-700">Tóm tắt:</strong> {doc.tom_tat}
          </div>
        </div>
      )}

      {/* Ket luan (cong van) */}
      {tab === 'congvan' && cv.ket_luan && (
        <div className="px-4 mt-3 flex-shrink-0">
          <h3 className="text-sm font-semibold text-gray-700 mb-1">Kết luận</h3>
          <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{cv.ket_luan}</p>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {content ? (
          <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 leading-relaxed">
            {content}
          </pre>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-300 gap-2">
            <span className="text-3xl">📝</span>
            <span className="text-sm">Chưa có nội dung văn bản</span>
          </div>
        )}
      </div>

      {/* Keywords */}
      {(doc.keywords ?? []).length > 0 && (
        <div className="px-4 py-2 border-t border-gray-100 flex flex-wrap gap-1 flex-shrink-0">
          {(doc.keywords ?? []).map((k, i) => (
            <span key={i} className="bg-gray-100 text-gray-500 text-[11px] px-2 py-0.5 rounded">{k}</span>
          ))}
        </div>
      )}

      {/* Footer actions */}
      <div className="px-4 py-2 border-t border-gray-100 flex gap-2 flex-shrink-0">
        <button
          onClick={() => setShowAI(true)}
          className="px-3 py-1.5 bg-primary text-white text-xs font-medium rounded hover:bg-primary-dark transition"
        >
          🤖 Phân tích AI
        </button>
        {(doc as Document).github_path && (
          <a
            href={`https://vntaxdoc.gpt4vn.com/docs/${(doc as Document).github_path}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 border border-gray-300 text-gray-600 text-xs rounded hover:border-primary hover:text-primary transition"
          >
            📄 Xem gốc ↗
          </a>
        )}
        {(item as CongVan).link_nguon && (
          <a
            href={(item as CongVan).link_nguon}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 border border-gray-300 text-gray-600 text-xs rounded hover:border-primary hover:text-primary transition"
          >
            Xem nguồn ↗
          </a>
        )}
      </div>
    </div>
  );
}
