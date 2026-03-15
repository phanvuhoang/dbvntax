import { useState, useRef, useEffect } from 'react';
import { authHeaders } from '../auth';

interface Props {
  token: string | null;
  onRequestLogin: () => void;
}

const EXAMPLES = [
  "Tiền thuê nhà trả cho cá nhân có được khấu trừ CIT không?",
  "Hộ kinh doanh doanh thu 500tr/năm phải nộp những loại thuế gì?",
  "Tổng hợp các thay đổi về thuế TNCN từ 2020–2026",
  "Nhà thầu nước ngoài cung cấp dịch vụ phần mềm qua internet chịu thuế gì?",
];

export default function QuickAnalysis({ token, onRequestLogin }: Props) {
  const [question, setQuestion] = useState('');
  const [output, setOutput] = useState('');
  const [citations, setCitations] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const outRef = useRef<HTMLDivElement>(null);

  const submit = async (q?: string) => {
    const query = q || question.trim();
    if (!query) return;
    if (!token) { onRequestLogin(); return; }

    setLoading(true);
    setOutput('');
    setCitations([]);
    setError('');
    if (q) setQuestion(q);

    try {
      const res = await fetch('/api/ai/quick-analysis', {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ question: query }),
      });
      if (res.status === 401) { onRequestLogin(); return; }
      if (res.status === 429) { setError('Đã hết lượt sử dụng AI.'); return; }
      if (!res.ok) throw new Error();

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
            if (d.type === 'citations') setCitations(d.docs || []);
            if (d.type === 'error') { setError(d.content); return; }
            if (d.type === 'done') break;
          } catch { /* partial */ }
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

  const copyOutput = () => {
    navigator.clipboard.writeText(output);
  };

  const downloadOutput = () => {
    const blob = new Blob([output], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `vntaxdb-ai-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-shrink-0 pb-3">
        <h3 className="text-sm font-bold text-gray-700 mb-2">💬 Hỏi AI về thuế</h3>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }}
          placeholder="Đặt câu hỏi về thuế..."
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded text-sm resize-none focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        />

        {/* Example prompts */}
        <div className="flex flex-wrap gap-1.5 mt-2">
          {EXAMPLES.map((ex, i) => (
            <button
              key={i}
              onClick={() => submit(ex)}
              className="text-[11px] px-2.5 py-1 bg-primary-light text-primary rounded-full hover:bg-primary hover:text-white transition truncate max-w-[200px]"
              title={ex}
            >
              {ex.length > 35 ? ex.slice(0, 35) + '...' : ex}
            </button>
          ))}
        </div>

        <div className="flex gap-2 mt-2">
          <button
            onClick={() => submit()}
            disabled={loading || !question.trim()}
            className="px-4 py-1.5 bg-primary text-white text-sm rounded hover:bg-primary-dark transition disabled:opacity-50"
          >
            {loading ? 'Đang phân tích...' : '🤖 Phân tích'}
          </button>
        </div>
      </div>

      {error && <p className="text-red-600 text-xs mb-2 flex-shrink-0">{error}</p>}

      {/* Citations */}
      {citations.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2 flex-shrink-0">
          <span className="text-xs text-gray-500">Nguồn:</span>
          {citations.map((c, i) => (
            <span key={i} className="text-[11px] px-2 py-0.5 bg-gray-100 border border-gray-200 rounded text-gray-600" title={c.ten}>
              {c.so_hieu}
            </span>
          ))}
        </div>
      )}

      {/* Output */}
      {output && (
        <>
          <div
            ref={outRef}
            className="flex-1 overflow-y-auto text-sm text-gray-700 leading-relaxed border-t border-gray-100 pt-3"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(output) }}
          />
          <div className="flex gap-2 pt-2 border-t border-gray-100 flex-shrink-0">
            <button onClick={copyOutput} className="text-xs px-3 py-1 border border-gray-200 rounded text-gray-500 hover:text-primary hover:border-primary transition">
              📋 Sao chép
            </button>
            <button onClick={downloadOutput} className="text-xs px-3 py-1 border border-gray-200 rounded text-gray-500 hover:text-primary hover:border-primary transition">
              💾 Tải .txt
            </button>
          </div>
        </>
      )}

      {!output && !loading && !token && (
        <div className="flex flex-col items-center justify-center flex-1 text-gray-400 text-sm gap-2">
          <span className="text-3xl">🔒</span>
          <span>Đăng nhập để sử dụng phân tích AI</span>
          <button onClick={onRequestLogin} className="px-4 py-2 bg-primary text-white text-sm rounded hover:bg-primary-dark transition mt-1">
            Đăng nhập
          </button>
        </div>
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
