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
  id?: number;
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
          return <p key={i} className="font-semibold text-gray-900 mt-3">{text}</p>;
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
  const [selectedSacThue, setSelectedSacThue] = useState<string[]>([]);

  const SAC_THUE_OPTIONS = [
    { code: 'GTGT',    label: 'GTGT' },
    { code: 'TNDN',    label: 'TNDN' },
    { code: 'TNCN',    label: 'TNCN' },
    { code: 'TTDB',    label: 'TTDB' },
    { code: 'FCT',     label: 'FCT' },
    { code: 'GDLK',    label: 'GDLK' },
    { code: 'HOA_DON', label: 'Hóa đơn' },
    { code: 'HKD',     label: 'HKD' },
    { code: 'XNK',     label: 'XNK' },
    { code: 'QLT',     label: 'QLT' },
    { code: 'THUE_QT', label: 'Thuế QT' },
  ];

  const toggleSacThue = (code: string) => {
    setSelectedSacThue(prev => {
      if (prev.includes(code)) return prev.filter(c => c !== code);
      if (prev.length >= 3) return prev;
      return [...prev, code];
    });
  };

  const MODEL_OPTIONS = [
    { value: 'claudible/claude-haiku-4.5',  label: '⚡ Haiku 4.5 (nhanh, rẻ)', badge: 'Nhanh' },
    { value: 'claudible/claude-sonnet-4.6', label: '🎯 Sonnet 4.6 Claudible (chất lượng cao)', badge: 'Tốt nhất' },
    { value: 'deepseek/deepseek-reasoner',  label: '🧠 DeepSeek Reasoner (thinking mode)', badge: 'Suy luận' },
    { value: 'google/gemini-2.0-flash',     label: '✨ Gemini 2.0 Flash (nhanh, chi tiết)', badge: '' },
    { value: 'anthropic/claude-sonnet-4-6', label: '💎 Claude Sonnet 4.6 Anthropic', badge: 'Đắt' },
    { value: 'openai/gpt-4o-mini',          label: '🔹 GPT-4o Mini (nhanh, rẻ)', badge: '' },
    { value: 'openai/gpt-4o',               label: '🔷 GPT-4o (chậm, đắt)', badge: '' },
  ];

  const ask = async (q: string) => {
    if (!q.trim() || loading) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const payload: Record<string, unknown> = {
        question: q.trim(),
        top_k: 15,
        model: selectedModel,
      };
      if (selectedSacThue.length > 0) {
        payload.sac_thue_override = selectedSacThue.slice(0, 3);
        payload.use_intent = false;
      }
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
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
        <div className="max-w-3xl mx-auto px-4 py-6 w-full">

          {/* Welcome / example questions */}
          {!result && !loading && (
            <div className="mb-6">
              <div className="text-center mb-6">
                <div className="w-12 h-12 rounded-full bg-primary-light flex items-center justify-center text-2xl mx-auto mb-3">🤖</div>
                <h2 className="text-lg font-semibold text-gray-800">Hỏi đáp AI về thuế</h2>
                <p className="text-sm text-gray-500 mt-1">Câu hỏi được trả lời dựa trên văn bản pháp luật thuế Việt Nam</p>
              </div>

              <p className="text-[11px] text-gray-400 mb-2.5 font-semibold uppercase tracking-wider">
                Câu hỏi gợi ý
              </p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => { setQuestion(q); ask(q); }}
                    className="text-xs px-3 py-2 rounded-xl border border-gray-200 text-gray-600 hover:border-primary hover:text-primary hover:bg-primary-light transition text-left leading-snug"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex items-start gap-4 py-6">
              <div className="w-8 h-8 rounded-full bg-primary-light flex items-center justify-center shrink-0">
                <svg className="animate-spin h-4 w-4 text-primary" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700">Đang tìm kiếm và phân tích...</p>
                <p className="text-xs text-gray-400 mt-1">Tìm văn bản pháp luật liên quan · Tổng hợp câu trả lời</p>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 mb-4">
              ⚠️ {error}
            </div>
          )}

          {/* Result */}
          {result && (
            <div className="space-y-4">
              {/* Question echo */}
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-sm shrink-0">👤</div>
                <div className="bg-gray-50 border border-gray-100 rounded-xl rounded-tl-none px-4 py-3 text-sm text-gray-700 flex-1">
                  {result.question}
                </div>
              </div>

              {/* Intent chip */}
              {result.intent?.chu_de && (
                <div className="flex items-center gap-2 flex-wrap px-2">
                  <span className="text-[11px] text-gray-400">🎯 Chủ đề:</span>
                  <span className="text-[11px] bg-primary-light text-primary px-2 py-0.5 rounded-full font-medium">{result.intent.chu_de}</span>
                  {result.intent.sac_thue?.map(s => (
                    <span key={s} className="text-[11px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{s}</span>
                  ))}
                </div>
              )}

              {/* Answer */}
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-primary-light flex items-center justify-center text-sm shrink-0">🤖</div>
                <div className="bg-white border border-gray-200 rounded-xl rounded-tl-none px-4 py-3 flex-1 shadow-sm">
                  {result.is_timeline && (
                    <div className="inline-flex items-center gap-1.5 text-[11px] font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2.5 py-1 mb-3">
                      ⏱️ Câu hỏi đa giai đoạn
                    </div>
                  )}
                  {renderAnswer(result.answer)}
                  <div className="text-[10px] text-gray-400 mt-3 pt-2 border-t border-gray-100 flex items-center gap-2 flex-wrap">
                    {(result.anchor_count ?? 0) > 0 && <span>⭐ {result.anchor_count} VB anchor</span>}
                    <span>📜 {result.docs_count ?? 0} văn bản</span>
                    <span>📨 {result.cv_count ?? 0} công văn</span>
                    <span className="ml-auto">🤖 {result.model_used}</span>
                  </div>
                </div>
              </div>

              {/* Sources — grouped */}
              {(result.sources?.length ?? 0) > 0 && (() => {
                const docSources = result.sources.filter(s => s.source_type === 'document');
                const cvSources = result.sources.filter(s => s.source_type === 'cong_van');
                const renderSource = (src: AskSource, i: number) => {
                  const href = src.link_nguon || src.tvpl_url || (src.id ? `/?doc=${src.id}` : null);
                  const El = href ? 'a' : 'div';
                  const linkProps = href ? { href, target: href.startsWith('/') ? undefined : '_blank', rel: 'noopener noreferrer' } : {};
                  return (
                    <El
                      key={i}
                      {...linkProps}
                      className={`flex items-start justify-between gap-3 border rounded-xl px-3 py-2.5 hover:border-primary hover:bg-primary-light transition group no-underline cursor-pointer ${src.is_anchor ? 'border-yellow-300 bg-yellow-50/50' : 'border-gray-200 bg-white'}`}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono font-semibold text-primary text-sm group-hover:underline">
                            {src.so_hieu || '—'}
                          </span>
                          {src.is_anchor && (
                            <span className="text-[10px] bg-yellow-100 text-yellow-700 px-1.5 rounded-full border border-yellow-200">⭐ Anchor</span>
                          )}
                          {src.loai && (
                            <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">{src.loai}</span>
                          )}
                          {src.tinh_trang && (
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                              src.tinh_trang.toLowerCase().includes('còn') || src.tinh_trang.toLowerCase().includes('hiệu lực')
                                ? 'bg-green-100 text-green-700'
                                : src.tinh_trang.toLowerCase().includes('hết')
                                  ? 'bg-red-100 text-red-600'
                                  : 'bg-gray-100 text-gray-500'
                            }`}>{src.tinh_trang}</span>
                          )}
                        </div>
                        <p className="text-xs text-gray-600 mt-0.5 line-clamp-2 leading-snug">{src.ten}</p>
                        {(src.hieu_luc_tu || src.het_hieu_luc_tu) && (
                          <p className="text-[10px] text-gray-400 mt-0.5">
                            {src.hieu_luc_tu && <>Từ {formatDate(src.hieu_luc_tu)}</>}
                            {src.het_hieu_luc_tu && <> — Đến {formatDate(src.het_hieu_luc_tu)}</>}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        {src.ngay_ban_hanh && (
                          <span className="text-[10px] text-gray-400 whitespace-nowrap">{formatDate(src.ngay_ban_hanh)}</span>
                        )}
                        {src.score > 0 && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                            src.score >= 0.7 ? 'bg-green-100 text-green-700' :
                            src.score >= 0.5 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
                          }`}>{Math.round(src.score * 100)}%</span>
                        )}
                      </div>
                    </El>
                  );
                };
                return (
                  <div className="space-y-3 pl-11">
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

              <div className="pl-11">
                <button
                  onClick={() => { setResult(null); setQuestion(''); }}
                  className="text-xs text-gray-400 hover:text-primary transition flex items-center gap-1"
                >
                  ← Câu hỏi mới
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 border-t border-gray-100 bg-white px-4 py-3 shadow-[0_-2px_8px_rgba(0,0,0,0.04)]">
        <div className="max-w-3xl mx-auto space-y-2.5">

          {/* Sắc thuế filter chips */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] text-gray-400 shrink-0">Sắc thuế (≤3):</span>
            {SAC_THUE_OPTIONS.map(opt => {
              const selected = selectedSacThue.includes(opt.code);
              const disabled = !selected && selectedSacThue.length >= 3;
              return (
                <button
                  key={opt.code}
                  onClick={() => !disabled && toggleSacThue(opt.code)}
                  className={`text-[11px] px-2.5 py-1 rounded-full border transition font-medium ${
                    selected
                      ? 'bg-primary text-white border-primary'
                      : disabled
                        ? 'bg-gray-50 text-gray-300 border-gray-100 cursor-not-allowed'
                        : 'bg-white text-gray-600 border-gray-200 hover:border-primary hover:text-primary'
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
            {selectedSacThue.length > 0 && (
              <button onClick={() => setSelectedSacThue([])}
                className="text-[11px] text-gray-400 hover:text-red-500 transition ml-1 flex items-center gap-0.5">
                ✕ bỏ lọc
              </button>
            )}
          </div>

          {/* Model selector — pill style */}
          <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-0.5">
            <span className="text-[11px] text-gray-400 shrink-0">Model:</span>
            {MODEL_OPTIONS.slice(0, 4).map(m => (
              <button
                key={m.value}
                onClick={() => setSelectedModel(m.value)}
                className={`text-[11px] px-3 py-1 rounded-full border transition whitespace-nowrap shrink-0 ${
                  selectedModel === m.value
                    ? 'bg-primary text-white border-primary font-medium'
                    : 'bg-white text-gray-500 border-gray-200 hover:border-primary hover:text-primary'
                }`}
              >
                {m.label.split(' (')[0]}
              </button>
            ))}
            <select
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
              className="text-[11px] border border-gray-200 rounded-full px-2 py-1 bg-white text-gray-500 focus:border-primary focus:outline-none cursor-pointer shrink-0"
            >
              {MODEL_OPTIONS.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            {selectedSacThue.length > 0 && (
              <span className="text-[11px] text-amber-600 bg-amber-50 border border-amber-200 rounded-full px-2.5 py-1 shrink-0">
                🎯 {selectedSacThue.join(', ')}
              </span>
            )}
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
              placeholder="Nhập câu hỏi thuế... (Enter để gửi, Shift+Enter xuống dòng)"
              rows={2}
              className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm resize-none focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition shadow-sm"
            />
            <button
              onClick={() => ask(question)}
              disabled={loading || !question.trim()}
              className="px-4 py-2.5 bg-primary text-white text-sm font-medium rounded-xl hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-2 whitespace-nowrap shadow-sm"
            >
              {loading ? (
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : '🤖'}
              Hỏi
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
