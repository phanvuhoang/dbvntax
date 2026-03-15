import { useState, useRef, useEffect } from 'react';
import { authHeaders } from '../auth';

interface Props {
  token: string | null;
  docId?: number;
  docSource?: string;
  onRequestLogin: () => void;
}

type AnalysisType = 'short' | 'long' | 'explain';

export default function AIAnalysis({ token, docId, docSource, onRequestLogin }: Props) {
  const [type, setType] = useState<AnalysisType>('short');
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const outRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setOutput('');
    setError('');
  }, [docId]);

  const analyze = async () => {
    if (!token) { onRequestLogin(); return; }
    if (!docId) return;

    setLoading(true);
    setOutput('');
    setError('');

    try {
      const res = await fetch('/api/ai/analyze-document', {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ source: docSource || 'documents', id: docId }),
      });
      if (res.status === 401) { onRequestLogin(); return; }
      if (res.status === 429) { setError('Đã hết lượt sử dụng AI. Vui lòng nâng cấp.'); return; }
      if (!res.ok) throw new Error('API error');

      const reader = res.body!.getReader();
      const dec = new TextDecoder();
      let full = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const line of dec.decode(value).split('\n')) {
          if (!line.startsWith('data: ')) continue;
          try {
            const d = JSON.parse(line.slice(6));
            if (d.type === 'text') { full += d.content; setOutput(full); }
            if (d.type === 'error') { setError(d.content); return; }
            if (d.type === 'done') break;
          } catch { /* partial JSON */ }
        }
      }
    } catch {
      setError('Lỗi khi phân tích. Vui lòng thử lại.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (outRef.current) outRef.current.scrollTop = outRef.current.scrollHeight;
  }, [output]);

  if (!token) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-gray-400 text-sm gap-3">
        <span className="text-3xl">🔒</span>
        <span>Đăng nhập để sử dụng phân tích AI</span>
        <button onClick={onRequestLogin} className="px-4 py-2 bg-primary text-white text-sm rounded hover:bg-primary-dark transition">
          Đăng nhập
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Analysis type selector */}
      <div className="mb-3">
        <label className="text-xs font-semibold text-gray-500 block mb-1.5">Loại phân tích:</label>
        <div className="flex gap-2">
          {([
            { value: 'short', label: 'Tóm tắt ngắn' },
            { value: 'long', label: 'Memo đầy đủ' },
            { value: 'explain', label: 'Giải thích đơn giản' },
          ] as const).map(opt => (
            <label key={opt.value} className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
              <input
                type="radio"
                name="analysis-type"
                checked={type === opt.value}
                onChange={() => setType(opt.value)}
                className="accent-primary w-3 h-3"
              />
              {opt.label}
            </label>
          ))}
        </div>
      </div>

      <button
        onClick={analyze}
        disabled={loading || !docId}
        className="self-start px-4 py-2 bg-primary text-white text-sm font-medium rounded hover:bg-primary-dark transition disabled:opacity-50 mb-3"
      >
        {loading ? (
          <span className="flex items-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Đang phân tích...
          </span>
        ) : '🤖 Tạo phân tích'}
      </button>

      {error && <p className="text-red-600 text-xs mb-2">{error}</p>}

      {/* Output */}
      {output && (
        <div
          ref={outRef}
          className="flex-1 overflow-y-auto text-sm text-gray-700 leading-relaxed prose prose-sm max-w-none"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(output) }}
        />
      )}
    </div>
  );
}

function renderMarkdown(text: string): string {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^#### (.+)$/gm, '<h4 class="text-primary font-semibold mt-3 mb-1 text-sm">$1</h4>')
    .replace(/^### (.+)$/gm, '<h4 class="text-primary font-semibold mt-4 mb-1">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 class="text-primary font-bold mt-4 mb-2">$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 list-decimal">$1. $2</li>')
    .replace(/\n\n+/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}
