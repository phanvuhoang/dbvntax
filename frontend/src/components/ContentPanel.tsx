import { useState } from 'react';
import type { Document, CongVan } from '../types';
import { LOAI_LABELS, SAC_THUE_MAP } from '../types';
import { useDocumentDetail, useCongVanDetail, formatDate } from '../api';
import HieuLucBadge from './HieuLucBadge';
import HieuLucDetail from './HieuLucDetail';
import AIAnalysis from './AIAnalysis';

function TomTatBox({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-200 rounded mb-4 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition text-left"
      >
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">📝 Tóm tắt</span>
        <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 py-2 text-sm text-gray-600 leading-relaxed">{text}</div>
      )}
    </div>
  );
}

interface Props {
  item: Document | CongVan | null;
  tab: 'vanban' | 'congvan';
  token: string | null;
  onRequestLogin: () => void;
}

export default function ContentPanel({ item, tab, token, onRequestLogin }: Props) {
  const [showAI, setShowAI] = useState(false);
  const [fontSize, setFontSize] = useState(14);
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
      {/* Header — compact 2 lines */}
      <div className="px-4 py-2 border-b border-gray-200 flex-shrink-0 bg-white">
        {/* Line 1: title + font controls */}
        <div className="flex items-start gap-2">
          <h2 className="font-semibold text-gray-800 text-sm leading-snug flex-1 min-w-0">
            {doc.ten || cv.ten}
          </h2>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={() => setFontSize(s => Math.max(11, s - 1))}
              className="px-1.5 py-0.5 text-xs border border-gray-300 rounded hover:bg-gray-100 font-mono"
              title="Giảm font"
            >A−</button>
            <span className="text-xs text-gray-400 w-6 text-center">{fontSize}</span>
            <button
              onClick={() => setFontSize(s => Math.min(20, s + 1))}
              className="px-1.5 py-0.5 text-xs border border-gray-300 rounded hover:bg-gray-100 font-mono"
              title="Tăng font"
            >A+</button>
          </div>
        </div>
        {/* Line 2: metadata in one row */}
        <div className="flex gap-2 mt-1 text-xs text-gray-500 items-center flex-wrap">
          {doc.ngay_ban_hanh && <span>{formatDate(doc.ngay_ban_hanh)}</span>}
          {doc.loai && (
            <>
              <span>•</span>
              <span>{LOAI_LABELS[doc.loai] || doc.loai}</span>
            </>
          )}
          {(doc.sac_thue ?? []).map((s) => (
            <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-primary-light text-primary font-medium">
              {SAC_THUE_MAP[s] || s}
            </span>
          ))}
          {tab === 'vanban' && <HieuLucBadge doc={doc} />}
          {(item as CongVan).co_quan && (
            <>
              <span>•</span>
              <span>{(item as CongVan).co_quan}</span>
            </>
          )}
        </div>
      </div>

      {/* Hiệu lực chi tiết — expandable, mặc định collapsed */}
      {tab === 'vanban' && doc.hieu_luc_index && (
        <div className="px-4 mt-2 flex-shrink-0">
          <HieuLucDetail index={doc.hieu_luc_index} />
        </div>
      )}

      {/* Tóm tắt — expandable, mặc định collapsed */}
      {(doc as Document).tom_tat && (
        <div className="px-4 flex-shrink-0">
          <TomTatBox text={(doc as Document).tom_tat!} />
        </div>
      )}

      {/* Ket luan (cong van) */}
      {tab === 'congvan' && cv.ket_luan && (
        <div className="px-4 mt-2 flex-shrink-0">
          <h3 className="text-sm font-semibold text-gray-700 mb-1">Kết luận</h3>
          <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{cv.ket_luan}</p>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {content ? (
          <div
            className="prose max-w-none text-gray-700 leading-relaxed
                       [&_table]:border-collapse [&_table]:w-full [&_table]:text-sm
                       [&_td]:border [&_td]:border-gray-300 [&_td]:p-2
                       [&_th]:border [&_th]:border-gray-300 [&_th]:p-2 [&_th]:bg-gray-50
                       [&_p]:mb-3 [&_h1]:text-base [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-bold
                       [&_h3]:text-sm [&_h3]:font-semibold [&_b]:font-semibold
                       [&_.NoiDungChiaSe]:!hidden
                       [&_.ulnhch]:!hidden
                       [&_.GgADS]:!hidden
                       [&_.LawNote]:!hidden
                       [&_.ykien]:!hidden
                       [&_.ttlq]:!hidden
                       [&_.download1]:!hidden
                       [&_#hd-save-doc]:!hidden
                       [&_#btTheoDoiHieuLuc]:!hidden
                       [&_#btnSoSanhThayThe]:!hidden
                       [&_#btnSongNgu]:!hidden
                       [&_#TVNDWidget]:!hidden
                       [&_.clr]:!hidden
                       [&_#divContentDoc]:!float-none [&_#divContentDoc]:!w-full [&_#divContentDoc]:!mr-0"
            style={{ fontSize: `${fontSize}px` }}
            dangerouslySetInnerHTML={{ __html: content ?? '' }}
          />
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
        {(doc as Document).tvpl_url && (
          <a
            href={(doc as Document).tvpl_url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 border border-gray-300 text-gray-600 text-xs rounded hover:border-primary hover:text-primary transition"
          >
            🔗 Xem trên TVPL ↗
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
