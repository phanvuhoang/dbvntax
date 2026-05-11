import { useState, useRef, useEffect } from 'react';
import type { Document, CongVan } from '../types';
import { LOAI_LABELS, SAC_THUE_MAP } from '../types';
import { useDocumentDetail, useCongVanDetail, formatDate } from '../api';
import HieuLucBadge from './HieuLucBadge';
import HieuLucDetail from './HieuLucDetail';
import AIAnalysis from './AIAnalysis';

interface ChainData {
  predecessors: Array<{ so_hieu: string; ten: string; id?: number }>;
  successors: Array<{ so_hieu: string; ten: string; id?: number }>;
  amendments: Array<{ so_hieu: string; ten: string; id?: number }>;
}

interface ImplicationsData {
  summary?: string;
  tags?: string[];
  obligations?: string[];
  deadlines?: string[];
  rates?: string[];
  penalties?: string[];
  exemptions?: string[];
  compliance_actions?: string[];
}

interface CompareDoc {
  id: number;
  so_hieu: string;
  ten: string;
  source: 'documents' | 'cong_van';
}

function ImportanceStar({ importance }: { importance?: number | null }) {
  if (!importance) return null;
  // importance: 1 = most important (5 stars), 4 = least (2 stars)
  const stars = importance === 1 ? 5 : importance === 2 ? 4 : importance === 3 ? 3 : 2;
  return (
    <span className="text-yellow-500 text-xs" title={`Độ quan trọng: ${stars} sao`}>
      {'★'.repeat(stars)}{'☆'.repeat(5 - stars)}
    </span>
  );
}

function VersionChain({ chain }: { chain: ChainData }) {
  const hasContent = chain.predecessors.length > 0 || chain.successors.length > 0 || chain.amendments.length > 0;
  if (!hasContent) return null;

  return (
    <div className="mt-4">
      <h4 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">⛓ Chuỗi văn bản</h4>
      <div className="space-y-1.5">
        {chain.predecessors.map((doc, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-16 text-gray-400 shrink-0">Tiền nhiệm</span>
            <span className="font-mono text-primary">{doc.so_hieu}</span>
            <span className="text-gray-500 truncate">{doc.ten}</span>
          </div>
        ))}
        {chain.successors.map((doc, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-16 text-green-600 shrink-0">Kế nhiệm</span>
            <span className="font-mono text-primary">{doc.so_hieu}</span>
            <span className="text-gray-500 truncate">{doc.ten}</span>
          </div>
        ))}
        {chain.amendments.map((doc, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-16 text-orange-500 shrink-0">Sửa đổi</span>
            <span className="font-mono text-primary">{doc.so_hieu}</span>
            <span className="text-gray-500 truncate">{doc.ten}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ImplicationsBlock({ data }: { data: ImplicationsData }) {
  const sections: Array<{ key: keyof ImplicationsData; label: string; icon: string }> = [
    { key: 'tags', label: 'Từ khóa', icon: '🏷️' },
    { key: 'obligations', label: 'Nghĩa vụ', icon: '📌' },
    { key: 'deadlines', label: 'Thời hạn', icon: '⏰' },
    { key: 'rates', label: 'Mức thuế / Tỷ lệ', icon: '💰' },
    { key: 'penalties', label: 'Xử phạt', icon: '⚠️' },
    { key: 'exemptions', label: 'Miễn giảm', icon: '✅' },
    { key: 'compliance_actions', label: 'Hành động tuân thủ', icon: '📋' },
  ];

  return (
    <div className="mt-4 space-y-3">
      {data.summary && (
        <div className="bg-primary-light rounded-lg p-3 text-sm text-gray-700 leading-relaxed">
          {data.summary}
        </div>
      )}
      {sections.map(({ key, label, icon }) => {
        const items = data[key] as string[] | undefined;
        if (!items?.length) return null;
        return (
          <div key={key}>
            <p className="text-xs font-semibold text-gray-500 mb-1">{icon} {label}</p>
            <ul className="space-y-0.5">
              {items.map((item, i) => (
                <li key={i} className="text-xs text-gray-600 flex gap-1.5">
                  <span className="text-primary mt-0.5 shrink-0">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

interface Props {
  item: Document | CongVan | null;
  tab: 'vanban' | 'congvan';
  token: string | null;
  onRequestLogin: () => void;
  onBack?: () => void;
}

export default function ContentPanel({ item, tab, token, onRequestLogin, onBack }: Props) {
  const [showAI, setShowAI] = useState(false);
  const [fontSize, setFontSize] = useState(14);
  const [tomTatOpen, setTomTatOpen] = useState(false);
  const [hieuLucOpen, setHieuLucOpen] = useState(false);
  const [headerVisible, setHeaderVisible] = useState(true);
  const [chain, setChain] = useState<ChainData | null>(null);
  const [implications, setImplications] = useState<ImplicationsData | null>(null);
  const [implicationsLoading, setImplicationsLoading] = useState(false);
  const [showImplications, setShowImplications] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareQuery, setCompareQuery] = useState('');
  const [compareResults, setCompareResults] = useState<CompareDoc[]>([]);
  const [compareTarget, setCompareTarget] = useState<CompareDoc | null>(null);
  const [compareResult, setCompareResult] = useState('');
  const [compareLoading, setCompareLoading] = useState(false);
  const [metaOpen, setMetaOpen] = useState(true);

  const scrollRef = useRef<HTMLDivElement>(null);
  const lastScrollY = useRef(0);

  const docQuery = useDocumentDetail(tab === 'vanban' && item ? item.id : null);
  const cvQuery = useCongVanDetail(tab === 'congvan' && item ? item.id : null);

  // Auto-hide header on mobile scroll
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const handler = () => {
      const currentY = el.scrollTop;
      if (currentY < 10) {
        setHeaderVisible(true);
      } else if (currentY < lastScrollY.current) {
        setHeaderVisible(true);
      } else if (currentY > lastScrollY.current + 5) {
        setHeaderVisible(false);
      }
      lastScrollY.current = currentY;
    };
    el.addEventListener('scroll', handler, { passive: true });
    return () => el.removeEventListener('scroll', handler);
  }, [item]);

  // Reset scroll + state when item changes
  useEffect(() => {
    setHeaderVisible(true);
    setTomTatOpen(false);
    setHieuLucOpen(false);
    setChain(null);
    setImplications(null);
    setShowImplications(false);
    setCompareOpen(false);
    setCompareResult('');
    lastScrollY.current = 0;
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [item]);

  // Load version chain
  useEffect(() => {
    if (!item || tab !== 'vanban') return;
    fetch(`/api/v1/canonical/documents/${item.id}/chain`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setChain(data); })
      .catch(() => {});
  }, [item, tab]);

  // Load implications
  const loadImplications = () => {
    if (!item || implicationsLoading || implications) {
      setShowImplications(s => !s);
      return;
    }
    setImplicationsLoading(true);
    setShowImplications(true);
    fetch('/api/v1/ai/implications', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: tab === 'vanban' ? 'documents' : 'cong_van', id: item.id }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setImplications(data); })
      .catch(() => {})
      .finally(() => setImplicationsLoading(false));
  };

  // Compare search
  useEffect(() => {
    if (!compareQuery.trim()) { setCompareResults([]); return; }
    const t = setTimeout(() => {
      fetch(`/api/search?q=${encodeURIComponent(compareQuery)}&limit=10`)
        .then(r => r.ok ? r.json() : { results: [] })
        .then(data => {
          setCompareResults((data.results || []).map((d: Document) => ({
            id: d.id, so_hieu: d.so_hieu, ten: d.ten, source: 'documents' as const,
          })));
        })
        .catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [compareQuery]);

  const runCompare = async () => {
    if (!item || !compareTarget) return;
    setCompareLoading(true);
    setCompareResult('');
    try {
      const res = await fetch('/api/v1/ai/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_a: tab === 'vanban' ? 'documents' : 'cong_van',
          id_a: item.id,
          source_b: compareTarget.source,
          id_b: compareTarget.id,
        }),
      });
      if (!res.ok) { setCompareLoading(false); return; }
      const reader = res.body?.getReader();
      const dec = new TextDecoder();
      if (!reader) return;
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const ev = JSON.parse(line.slice(6));
              if (ev.content) setCompareResult(prev => prev + ev.content);
            } catch { /* ignore */ }
          }
        }
      }
    } catch { /* ignore */ }
    setCompareLoading(false);
  };

  const exportDoc = (format: 'md' | 'json' | 'html') => {
    if (!item) return;
    const url = `/api/v1/canonical/documents/${item.id}/export?format=${format}`;
    window.open(url, '_blank');
  };

  const copyLink = () => {
    if (!item) return;
    const url = `${window.location.origin}/?doc=${item.id}`;
    navigator.clipboard.writeText(url).then(() => {
      // brief feedback
    }).catch(() => {});
  };

  const copyFullText = () => {
    if (!content) return;
    const tmp = document.createElement('div');
    tmp.innerHTML = content;
    const text = tmp.textContent || tmp.innerText || '';
    navigator.clipboard.writeText(text).catch(() => {});
  };

  if (!item) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-300 gap-3 min-w-[300px]">
        <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center text-3xl">📄</div>
        <div className="text-center">
          <p className="text-sm font-medium text-gray-400">Chọn văn bản để xem</p>
          <p className="text-xs text-gray-300 mt-1">Nội dung sẽ hiển thị tại đây</p>
        </div>
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

  const openContentInNewTab = () => {
    if (!content) return;
    const html = `<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${(tab === 'vanban' ? doc.ten : cv.ten) || 'Văn bản'}</title>
  <style>
    body { font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; padding: 24px 40px; max-width: 900px; margin: 0 auto; color: #333; }
    table { border-collapse: collapse; width: 100%; }
    td, th { border: 1px solid #ccc; padding: 6px 10px; }
    p { margin-bottom: 10px; }
    .NoiDungChiaSe, .ulnhch, .GgADS, .LawNote, .ykien, .ttlq, .download1,
    #hd-save-doc, #btTheoDoiHieuLuc, #btnSoSanhThayThe, #btnSongNgu, #TVNDWidget, .clr { display: none !important; }
    #divContentDoc { float: none !important; width: 100% !important; margin: 0 !important; }
  </style>
</head>
<body>
${content}
</body>
</html>`;
    const blob = new Blob([html], { type: 'text/html; charset=utf-8' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
  };

  if (showAI) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden min-w-[300px]">
        <div className="px-4 py-2 border-b border-gray-200 flex items-center justify-between flex-shrink-0 bg-gray-50">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-gray-700">🤖 Phân tích AI</span>
            <span className="font-mono text-xs text-primary">{doc.so_hieu || cv.so_hieu}</span>
          </div>
          <button onClick={() => setShowAI(false)} className="text-xs text-gray-400 hover:text-primary transition">← Quay lại</button>
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
      {/* Sticky title bar */}
      <div
        className={`
          border-b border-gray-200 flex-shrink-0 bg-white
          transition-all duration-200 ease-in-out overflow-hidden
          md:max-h-none md:opacity-100
          ${headerVisible ? 'max-h-40 opacity-100' : 'max-h-0 opacity-0 border-b-0'}
        `}
      >
        {/* Line 1: back + title + font controls */}
        <div className="flex items-start gap-2 px-4 pt-2.5">
          {onBack && (
            <button
              onClick={onBack}
              className="shrink-0 text-xs text-primary hover:text-primary-dark font-medium mt-0.5 flex items-center gap-1"
            >
              ← Danh sách
            </button>
          )}
          <div className="flex items-center gap-1.5 flex-wrap min-w-0 flex-1">
            {doc.loai && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-medium shrink-0">
                {LOAI_LABELS[doc.loai] || doc.loai}
              </span>
            )}
            <span className="font-mono font-semibold text-primary text-sm shrink-0">
              {doc.so_hieu || cv.so_hieu || '—'}
            </span>
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button onClick={() => setFontSize(s => Math.max(11, s - 1))}
              className="px-1.5 py-0.5 text-xs border border-gray-200 rounded hover:bg-gray-100 font-mono transition" title="Giảm font">A−</button>
            <span className="text-xs text-gray-400 w-6 text-center">{fontSize}</span>
            <button onClick={() => setFontSize(s => Math.min(20, s + 1))}
              className="px-1.5 py-0.5 text-xs border border-gray-200 rounded hover:bg-gray-100 font-mono transition" title="Tăng font">A+</button>
          </div>
        </div>

        {/* Title */}
        <h2 className="px-4 mt-1 font-semibold text-gray-800 text-sm leading-snug select-text">
          {doc.ten || cv.ten}
        </h2>

        {/* Action buttons */}
        <div className="flex items-center gap-1.5 px-4 py-2 flex-wrap">
          <button
            onClick={() => setShowAI(true)}
            className="px-2.5 py-1 bg-primary text-white text-xs font-medium rounded-lg hover:bg-primary-dark transition flex items-center gap-1"
          >
            🤖 Phân tích AI
          </button>
          <button
            onClick={copyLink}
            className="px-2.5 py-1 border border-gray-200 text-gray-600 text-xs rounded-lg hover:border-primary hover:text-primary transition"
            title="Sao chép liên kết"
          >
            🔗 Sao chép link
          </button>
          {content && (
            <button
              onClick={openContentInNewTab}
              className="px-2.5 py-1 border border-gray-200 text-gray-600 text-xs rounded-lg hover:border-primary hover:text-primary transition"
            >
              ↗ Mở mới
            </button>
          )}
          {tab === 'vanban' && (
            <div className="relative group">
              <button className="px-2.5 py-1 border border-gray-200 text-gray-600 text-xs rounded-lg hover:border-primary hover:text-primary transition">
                ⬇ Xuất ▾
              </button>
              <div className="hidden group-hover:flex absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg flex-col z-10 min-w-[100px]">
                <button onClick={() => exportDoc('md')} className="px-3 py-1.5 text-xs text-gray-600 hover:bg-primary-light hover:text-primary text-left">Markdown</button>
                <button onClick={() => exportDoc('json')} className="px-3 py-1.5 text-xs text-gray-600 hover:bg-primary-light hover:text-primary text-left">JSON</button>
                <button onClick={() => exportDoc('html')} className="px-3 py-1.5 text-xs text-gray-600 hover:bg-primary-light hover:text-primary text-left">HTML</button>
              </div>
            </div>
          )}
          <button
            onClick={() => setCompareOpen(o => !o)}
            className={`px-2.5 py-1 border text-xs rounded-lg transition ${compareOpen ? 'border-primary text-primary bg-primary-light' : 'border-gray-200 text-gray-600 hover:border-primary hover:text-primary'}`}
          >
            ⚖ So sánh
          </button>
        </div>

        {/* Metadata row */}
        <div className="flex gap-2 px-4 pb-2 text-xs text-gray-500 items-center flex-wrap select-text">
          {doc.ngay_ban_hanh && <span>{formatDate(doc.ngay_ban_hanh)}</span>}
          {(doc.sac_thue ?? []).map((s) => (
            <span key={s} className="px-1.5 py-0.5 rounded bg-primary-light text-primary font-medium text-[10px]">
              {SAC_THUE_MAP[s] || s}
            </span>
          ))}
          {tab === 'vanban' && <HieuLucBadge doc={doc} />}
          {(item as CongVan).co_quan && (
            <><span>•</span><span>{(item as CongVan).co_quan}</span></>
          )}
          {tab === 'vanban' && (doc as Document).importance && (
            <ImportanceStar importance={(doc as Document).importance} />
          )}
        </div>
      </div>

      {/* Compare dialog */}
      {compareOpen && (
        <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 flex-shrink-0">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-gray-700">⚖ So sánh với văn bản khác</p>
            <button onClick={() => setCompareOpen(false)} className="text-gray-400 hover:text-gray-600 text-sm">✕</button>
          </div>
          <div className="relative">
            <input
              type="text"
              placeholder="Tìm văn bản để so sánh..."
              value={compareQuery}
              onChange={e => setCompareQuery(e.target.value)}
              className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-primary"
            />
            {compareResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
                {compareResults.map(doc => (
                  <button
                    key={doc.id}
                    onClick={() => { setCompareTarget(doc); setCompareResults([]); setCompareQuery(doc.so_hieu); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-primary-light text-left"
                  >
                    <span className="font-mono text-primary shrink-0">{doc.so_hieu}</span>
                    <span className="text-gray-600 truncate">{doc.ten}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {compareTarget && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-xs text-gray-500">Với: <strong>{compareTarget.so_hieu}</strong></span>
              <button
                onClick={runCompare}
                disabled={compareLoading}
                className="px-3 py-1 text-xs bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-50 transition"
              >
                {compareLoading ? 'Đang so sánh...' : 'So sánh'}
              </button>
            </div>
          )}
          {compareResult && (
            <div className="mt-3 text-xs text-gray-700 leading-relaxed whitespace-pre-wrap bg-white rounded-lg p-3 border border-gray-200 max-h-48 overflow-y-auto">
              {compareResult}
            </div>
          )}
        </div>
      )}

      {/* Ket luan (cong van) */}
      {tab === 'congvan' && cv.ket_luan && (
        <div className="px-4 py-2 bg-primary-light border-b border-primary/10 flex-shrink-0">
          <h3 className="text-xs font-semibold text-primary mb-1">Kết luận</h3>
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap select-text">{cv.ket_luan}</p>
        </div>
      )}

      {/* Collapsible metadata card */}
      {tab === 'vanban' && (doc as Document).tom_tat && (
        <div className="border-b border-gray-100 flex-shrink-0">
          <button
            onClick={() => setMetaOpen(o => !o)}
            className="w-full flex items-center justify-between px-4 py-1.5 bg-gray-50 hover:bg-gray-100 transition"
          >
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">📝 Tóm tắt</span>
            <span className="text-gray-300 text-xs">{metaOpen ? '▲' : '▼'}</span>
          </button>
          {metaOpen && (
            <div className="px-4 py-2 text-sm text-gray-600 leading-relaxed bg-white select-text">
              {(doc as Document).tom_tat}
            </div>
          )}
        </div>
      )}

      {/* Scroll area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 select-text">
        {content ? (
          <>
            <div
              className="prose prose-sm max-w-none text-gray-700 leading-relaxed select-text
                         [&_table]:border-collapse [&_table]:w-full [&_table]:text-sm
                         [&_td]:border [&_td]:border-gray-300 [&_td]:p-2
                         [&_th]:border [&_th]:border-gray-300 [&_th]:p-2 [&_th]:bg-gray-50
                         [&_p]:mb-3 [&_h1]:text-base [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-bold
                         [&_h3]:text-sm [&_h3]:font-semibold [&_b]:font-semibold
                         [&_.NoiDungChiaSe]:!hidden [&_.ulnhch]:!hidden [&_.GgADS]:!hidden
                         [&_.LawNote]:!hidden [&_.ykien]:!hidden [&_.ttlq]:!hidden
                         [&_.download1]:!hidden [&_#hd-save-doc]:!hidden
                         [&_#btTheoDoiHieuLuc]:!hidden [&_#btnSoSanhThayThe]:!hidden
                         [&_#btnSongNgu]:!hidden [&_#TVNDWidget]:!hidden [&_.clr]:!hidden
                         [&_.info-red]:!hidden [&_p:has(>.info-red)]:!hidden
                         [&_#divContentDoc]:!float-none [&_#divContentDoc]:!w-full [&_#divContentDoc]:!mr-0"
              style={{ fontSize: `${fontSize}px` }}
              dangerouslySetInnerHTML={{ __html: content }}
            />

            {/* Bottom sections */}
            <div className="mt-8 pt-6 border-t-2 border-dashed border-gray-200 space-y-4">
              {/* HieuLuc detail */}
              {tab === 'vanban' && doc.hieu_luc_index && (
                <div>
                  <button
                    onClick={() => setHieuLucOpen(o => !o)}
                    className="w-full flex items-center justify-between py-2 text-left group"
                  >
                    <span className="text-xs font-bold text-gray-400 uppercase tracking-widest group-hover:text-primary transition">
                      ⚡ Hiệu lực chi tiết
                    </span>
                    <span className="text-gray-300 text-xs">{hieuLucOpen ? '▲' : '▼'}</span>
                  </button>
                  {hieuLucOpen && (
                    <div className="mt-2">
                      <HieuLucDetail index={doc.hieu_luc_index} />
                    </div>
                  )}
                </div>
              )}

              {/* Version chain */}
              {chain && <VersionChain chain={chain} />}

              {/* AI Implications */}
              <div>
                <button
                  onClick={loadImplications}
                  className="flex items-center gap-2 text-xs font-bold text-gray-400 uppercase tracking-widest hover:text-primary transition py-2"
                >
                  🤖 Phân tích AI (Tags & Nghĩa vụ)
                  <span className="text-gray-300">{showImplications ? '▲' : '▼'}</span>
                </button>
                {showImplications && implicationsLoading && (
                  <div className="flex items-center gap-2 text-xs text-gray-400 py-2">
                    <svg className="animate-spin h-3 w-3 text-primary" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Đang phân tích...
                  </div>
                )}
                {showImplications && implications && <ImplicationsBlock data={implications} />}
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-300 gap-2">
            <span className="text-3xl">📝</span>
            <span className="text-sm">Chưa có nội dung văn bản</span>
          </div>
        )}
      </div>

      {/* Footer — Keywords + Actions */}
      <div className="border-t border-gray-100 flex-shrink-0">
        {(doc.keywords ?? []).length > 0 && (
          <div className="px-4 py-2 border-b border-gray-100 flex flex-wrap gap-1">
            {(doc.keywords ?? []).map((k, i) => (
              <span key={i} className="bg-gray-100 text-gray-500 text-[11px] px-2 py-0.5 rounded">{k}</span>
            ))}
          </div>
        )}

        <div className="px-4 py-2 flex gap-2 flex-wrap">
          {content && (
            <button
              onClick={copyFullText}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-primary hover:text-primary transition text-gray-500"
            >
              📋 Sao chép toàn văn
            </button>
          )}
          {(doc as Document).github_path && (
            <a
              href={`https://vntaxdoc.gpt4vn.com/docs/${(doc as Document).github_path}`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-2.5 py-1.5 border border-gray-200 text-gray-600 text-xs rounded-lg hover:border-primary hover:text-primary transition"
            >
              📄 Xem gốc ↗
            </a>
          )}
          {(doc as Document).tvpl_url && (
            <a
              href={(doc as Document).tvpl_url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-2.5 py-1.5 border border-gray-200 text-gray-600 text-xs rounded-lg hover:border-primary hover:text-primary transition"
            >
              🔗 TVPL ↗
            </a>
          )}
          {(item as CongVan).link_nguon && (
            <a
              href={(item as CongVan).link_nguon}
              target="_blank"
              rel="noopener noreferrer"
              className="px-2.5 py-1.5 border border-gray-200 text-gray-600 text-xs rounded-lg hover:border-primary hover:text-primary transition"
            >
              Xem nguồn ↗
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
