import { useState } from 'react';
import { formatDate } from '../api';

const EXAMPLE_QUESTIONS = [
  'Dịch vụ xuất khẩu nào được thuế suất GTGT 0%?',
  'Chi phí trả phí dịch vụ cho công ty mẹ nước ngoài có được trừ không?',
  'Điều kiện để được ưu đãi thuế TNDN cho dự án đầu tư mới?',
  'Thuế nhà thầu áp dụng khi nào? Cách tính như thế nào?',
  'Transfer pricing — hồ sơ xác định giá giao dịch liên kết cần gì?',
];

interface AskSource {
  source_type: 'document' | 'cong_van';
  is_anchor: boolean;
  so_hieu: string;
  ten: string;
  ngay_ban_hanh: string;
  link_nguon?: string;
  tvpl_url?: string;
  score: number;
  loai?: string;
  hieu_luc_tu?: string;
  het_hieu_luc_tu?: string;
  tinh_trang?: string;
}

interface AskIntent {
  sac_thue: string[];
  chu_de: string;
  search_queries: string[];
  is_timeline: boolean;
}

interface AskResponse {
  question: string;
  answer: string;
  model_used: string;
  sources_count: number;
  is_timeline: boolean;
  intent: AskIntent | null;
  anchor_count: number;
  docs_count: number;
  cv_count: number;
  sources: AskSource[];
}

function renderAnswer(text: string) {
  const lines = text.split('\n');
  return (
    <div className="space-y-1 text-sm text-gray-800 leading-relaxed">
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-2" />;
        const renderInline = (s: string) =>
          s.split(/(\*\*[^*]+\*\*)/g).map((p, j) =>
            p.startsWith('**') && p.endsWith('**')
              ? <strong key={j} className="font-semibold">{p.slice(2, -2)}</strong>
              : p
          );
        if (line.startsWith('- ') || line.startsWith('• ')) {
          return (
            <div key={i} className="flex gap-2 ml-2">
              <span className="shrink-0 text-primary mt-0.5">•</span>
              <span>{renderInline(line.replace(/^[-•]\s+/, ''))}</span>
            </div>
          );
        }
        if (/^\d+\.\s/.test(line)) {
          const match = line.match(/^(\d+)\.\s+(.*)$/);
          if (match) {
            return (
              <div key={i} className="flex gap-2 ml-2">
                <span className="shrink-0 text-primary font-medium w-5">{match[1]}.</span>
                <span>{renderInline(match[2])}</span>
              </div>
            );
          }
        }
        if (line.startsWith('###') || line.startsWith('##') || line.startsWith('#')) {
          const text = line.replace(/^#+\s*/, '');
          return <p key={i} className="font-semibold text-gray-900 mt-2">{text}</p>;
        }
        return <p key={i}>{renderInline(line)}</p>;
      })}
    </div>
  );
}

export default function AskAIPage() {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState('');
  const [selectedModel, setSelectedModel] = useState('claudible/claude-haiku-4.5');

  const MODEL_OPTIONS = [
    { value: 'claudible/claude-haiku-4.5',  label: '⚡ Claudible/claude-haiku-4.5 (nhanh, rẻ)' },
    { value: 'anthropic/claude-sonnet-4-6', label: '🧠 Claude Sonnet 4.6 (lâu, chính xác, tốn kém)' },
    { value: 'openai/gpt-4o-mini',          label: '🔹 GPT-4o Mini (nhanh, rẻ)' },
    { value: 'openai/gpt-4o',               label: '🔷 GPT-4o (chậm, đắt)' },
    { value: 'google/gemini-2.0-flash',     label: '✨ Gemini Flash 2.0' },
  ];

  const ask = async (q: string) => {
    if (!q.trim() || loading) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q.trim(), top_k: 15, model: selectedModel }),
      });
      if (!res.ok) throw new Error(`Lỗi ${res.status}: ${res.statusText}`);
      const data: AskResponse = await res.json();
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không thể kết nối. Vui lòng thử lại.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-white">
      {/* Scroll area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-4 w-full">

          {/* Example questions — shown when no result */}
          {!result && !loading && (
            <div className="mb-6">
              <p className="text-[11px] text-gray-400 mb-2 font-semibold uppercase tracking-wider">
                Câu hỏi mẫu
              </p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => { setQuestion(q); ask(q); }}
                    className="text-xs px-3 py-1.5 rounded-full border border-gray-200 text-gray-600 hover:border-primary hover:text-primary hover:bg-primary-light transition"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex items-center gap-3 py-10 text-gray-500">
              <svg className="animate-spin h-5 w-5 text-primary" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-sm">Đang tìm kiếm và phân tích văn bản pháp luật...</span>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-4">
              ⚠️ {error}
            </div>
          )}

          {/* Result */}
          {result && (
            <div className="space-y-4">
              {/* Question echo */}
              <div className="bg-primary-light border border-primary/20 rounded-lg px-4 py-2.5 text-sm">
                <span className="font-semibold text-primary">Câu hỏi: </span>
                <span className="text-gray-700">{result.question}</span>
              </div>

              {/* Intent chip */}
              {result.intent?.chu_de && (
                <p className="text-[11px] text-gray-400">
                  🎯 Chủ đề: <span className="text-gray-500">{result.intent.chu_de}</span>
                  {result.intent.sac_thue?.length > 0 && (
                    <>&nbsp;&bull;&nbsp;Loại thuế: <span className="text-gray-500">{result.intent.sac_thue.join(', ')}</span></>
                  )}
                </p>
              )}

              {/* Answer */}
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                {result.is_timeline && (
                  <div className="inline-flex items-center gap-1.5 text-[11px] font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2.5 py-1 mb-3">
                    ⏱️ Câu hỏi đa giai đoạn
                  </div>
                )}
                {renderAnswer(result.answer)}
                {/* Stats bar */}
                <p className="text-[10px] text-gray-400 mt-3 border-t border-gray-100 pt-2">
                  {(result.anchor_count ?? 0) > 0 && <>⭐ {result.anchor_count} VB anchor &bull; </>}
                  📜 {result.docs_count ?? 0} văn bản &bull; 📨 {result.cv_count ?? 0} công văn &bull; 🤖 {result.model_used}
                </p>
              </div>

              {/* Sources — grouped */}
              {(result.sources?.length ?? 0) > 0 && (() => {
                const docSources = result.sources.filter(s => s.source_type === 'document');
                const cvSources = result.sources.filter(s => s.source_type === 'cong_van');
                const renderSource = (src: AskSource, i: number) => (
                  <a
                    key={i}
                    href={src.tvpl_url || src.link_nguon || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`flex items-start justify-between gap-3 border rounded-lg px-3 py-2.5 hover:border-primary hover:bg-primary-light transition group no-underline ${src.is_anchor ? 'border-yellow-300 bg-yellow-50' : 'border-gray-200'}`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-primary text-sm group-hover:underline">
                          {src.so_hieu || '—'}
                        </span>
                        {src.is_anchor && (
                          <span className="text-xs bg-yellow-100 text-yellow-700 px-1 rounded">⭐ Anchor</span>
                        )}
                        {src.loai && (
                          <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                            {src.loai}
                          </span>
                        )}
                        {src.tinh_trang && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                            src.tinh_trang.toLowerCase().includes('còn') || src.tinh_trang.toLowerCase().includes('hiệu lực')
                              ? 'bg-green-100 text-green-700'
                              : src.tinh_trang.toLowerCase().includes('hết')
                                ? 'bg-red-100 text-red-600'
                                : 'bg-gray-100 text-gray-500'
                          }`}>
                            {src.tinh_trang}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-600 mt-0.5 line-clamp-2 leading-snug">
                        {src.ten}
                      </p>
                      {(src.hieu_luc_tu || src.het_hieu_luc_tu) && (
                        <p className="text-[10px] text-gray-400 mt-0.5">
                          {src.hieu_luc_tu && <>Từ {formatDate(src.hieu_luc_tu)}</>}
                          {src.het_hieu_luc_tu && <> — Đến {formatDate(src.het_hieu_luc_tu)}</>}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      {src.ngay_ban_hanh && (
                        <span className="text-[10px] text-gray-400 whitespace-nowrap">
                          {formatDate(src.ngay_ban_hanh)}
                        </span>
                      )}
                      {src.score > 0 && (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                          src.score >= 0.7
                            ? 'bg-green-100 text-green-700'
                            : src.score >= 0.5
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-gray-100 text-gray-500'
                        }`}>
                          {Math.round(src.score * 100)}%
                        </span>
                      )}
                    </div>
                  </a>
                );
                return (
                  <div className="space-y-3">
                    {docSources.length > 0 && (
                      <div>
                        <p className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider mb-2">
                          📜 Văn bản pháp luật ({docSources.length})
                        </p>
                        <div className="space-y-2">{docSources.map(renderSource)}</div>
                      </div>
                    )}
                    {cvSources.length > 0 && (
                      <div>
                        <p className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider mb-2">
                          📨 Công văn hướng dẫn ({cvSources.length})
                        </p>
                        <div className="space-y-2">{cvSources.map(renderSource)}</div>
                      </div>
                    )}
                  </div>
                );
              })()}

              <button
                onClick={() => { setResult(null); setQuestion(''); }}
                className="text-xs text-gray-400 hover:text-primary transition"
              >
                ← Câu hỏi mới
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 border-t border-gray-200 bg-white px-4 py-3">
        <div className="max-w-3xl mx-auto space-y-2">
          {/* Model selector */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-gray-400 whitespace-nowrap">Model AI:</span>
            <select
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
              className="text-xs px-2 py-1 border border-gray-200 rounded bg-white text-gray-700 focus:border-primary focus:outline-none"
            >
              {MODEL_OPTIONS.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>
          {/* Question input */}
          <div className="flex gap-2 items-end">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                ask(question);
              }
            }}
            placeholder="Nhập câu hỏi thuế... ví dụ: Dịch vụ xuất khẩu nào được thuế suất GTGT 0%?"
            rows={2}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition"
          />
          <button
            onClick={() => ask(question)}
            disabled={loading || !question.trim()}
            className="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-2 whitespace-nowrap"
          >
            {loading ? (
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <span>🤖</span>
            )}
            Hỏi
          </button>
          </div>
        </div>
        <p className="text-[10px] text-gray-400 text-center mt-1">Enter để hỏi · Shift+Enter xuống dòng</p>
      </div>
    </div>
  );
}
