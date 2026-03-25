import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, authHeaders } from '../auth';

type AdminTab = 'corpus' | 'tvpl';

interface CorpusItem {
  github_path: string;
  name: string;
  so_hieu: string;
  loai: string;
  tx: string;
  date_id: string;
}

interface ImportResult {
  path: string;
  status: 'ok' | 'error';
  so_hieu?: string;
  ten?: string;
  msg?: string;
}

interface TVPLPreview {
  so_hieu: string;
  ten: string;
  loai: string;
  ngay_ban_hanh: string | null;
  sac_thue: string[];
}

const LOAI_OPTIONS = ['ND', 'TT', 'Luat', 'VBHN', 'QD', 'NQ', 'CV', 'Khac'];
const SAC_THUE_OPTIONS = ['TNDN', 'GTGT', 'TNCN', 'TTDB', 'FCT', 'GDLK', 'QLT', 'HOA_DON', 'HKD', 'XNK'];

export default function AdminPage() {
  const { user, token, isLoggedIn } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<AdminTab>('corpus');

  // Corpus tab state
  const [corpusSince, setCorpusSince] = useState('');
  const [corpusItems, setCorpusItems] = useState<CorpusItem[]>([]);
  const [corpusChecked, setCorpusChecked] = useState<Set<string>>(new Set());
  const [corpusSinceDate, setCorpusSinceDate] = useState('');
  const [corpusLoading, setCorpusLoading] = useState(false);
  const [corpusImporting, setCorpusImporting] = useState(false);
  const [corpusResults, setCorpusResults] = useState<ImportResult[]>([]);
  const [corpusError, setCorpusError] = useState('');

  // TVPL tab state
  const [tvplUrl, setTvplUrl] = useState('');
  const [tvplHtml, setTvplHtml] = useState('');
  const [tvplPreview, setTvplPreview] = useState<TVPLPreview | null>(null);
  const [tvplLoaiOverride, setTvplLoaiOverride] = useState('');
  const [tvplSacThueOverride, setTvplSacThueOverride] = useState<string[]>([]);
  const [tvplPreviewing, setTvplPreviewing] = useState(false);
  const [tvplImporting, setTvplImporting] = useState(false);
  const [tvplResult, setTvplResult] = useState<{ status: string; msg?: string; preview?: TVPLPreview } | null>(null);
  const [tvplFetchError, setTvplFetchError] = useState('');
  const [showHtmlPaste, setShowHtmlPaste] = useState(false);

  if (!isLoggedIn || user?.role !== 'admin') {
    return (
      <div className="h-full flex items-center justify-center flex-col gap-4">
        <p className="text-gray-500">Bạn không có quyền truy cập trang này.</p>
        <button onClick={() => navigate('/')} className="px-4 py-2 bg-primary text-white rounded text-sm">
          ← Về trang chủ
        </button>
      </div>
    );
  }

  const handleCorpusCheck = () => {
    setCorpusError('');
    setCorpusResults([]);
    setCorpusLoading(true);
    const params = corpusSince ? `?since=${corpusSince}` : '';
    fetch(`/api/admin/corpus-new${params}`, { headers: authHeaders(token) })
      .then(r => r.json())
      .then(data => {
        setCorpusItems(data.items || []);
        setCorpusSinceDate(data.since || '');
        const all = new Set<string>((data.items || []).map((i: CorpusItem) => i.github_path));
        setCorpusChecked(all);
      })
      .catch(e => setCorpusError(String(e)))
      .finally(() => setCorpusLoading(false));
  };

  const handleCorpusImport = () => {
    if (!corpusChecked.size) return;
    setCorpusImporting(true);
    setCorpusResults([]);
    fetch('/api/admin/corpus-import', {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ paths: [...corpusChecked] }),
    })
      .then(r => r.json())
      .then(data => setCorpusResults(data.results || []))
      .catch(e => setCorpusError(String(e)))
      .finally(() => setCorpusImporting(false));
  };

  const handleTvplPreview = () => {
    if (!tvplUrl) return;
    setTvplFetchError('');
    setTvplPreview(null);
    setTvplResult(null);
    setTvplPreviewing(true);
    fetch('/api/admin/tvpl-preview', {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({
        url: tvplUrl,
        html_content: tvplHtml || null,
        loai_override: tvplLoaiOverride || null,
        sac_thue_override: tvplSacThueOverride.length ? tvplSacThueOverride : null,
      }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.status === 'error') {
          setTvplFetchError(data.msg);
          setShowHtmlPaste(true);
        } else {
          setTvplPreview(data);
          setTvplLoaiOverride(data.loai || '');
          setTvplSacThueOverride(data.sac_thue || []);
        }
      })
      .catch(e => setTvplFetchError(String(e)))
      .finally(() => setTvplPreviewing(false));
  };

  const handleTvplImport = () => {
    if (!tvplUrl) return;
    setTvplImporting(true);
    setTvplResult(null);
    fetch('/api/admin/tvpl-import', {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({
        url: tvplUrl,
        html_content: tvplHtml || null,
        loai_override: tvplLoaiOverride || null,
        sac_thue_override: tvplSacThueOverride.length ? tvplSacThueOverride : null,
      }),
    })
      .then(r => r.json())
      .then(data => setTvplResult(data))
      .catch(e => setTvplResult({ status: 'error', msg: String(e) }))
      .finally(() => setTvplImporting(false));
  };

  const formatDateId = (id: string) => {
    if (!id || String(id).length !== 8) return '';
    const s = String(id);
    return `${s.slice(6)}/${s.slice(4, 6)}/${s.slice(0, 4)}`;
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 flex-shrink-0 px-4 h-12 flex items-center gap-4">
        <button onClick={() => navigate('/')} className="text-gray-400 hover:text-primary text-sm">← Về trang chủ</button>
        <span className="text-lg font-bold text-primary">⚙️ Admin Import</span>
      </header>

      {/* Tabs */}
      <div className="border-b border-gray-200 bg-white flex-shrink-0 px-4 flex gap-1 pt-2">
        {(['corpus', 'tvpl'] as AdminTab[]).map(t => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-4 py-1.5 text-sm font-medium rounded-t transition ${
              activeTab === t
                ? 'text-primary border-b-2 border-primary bg-primary-light'
                : 'text-gray-500 hover:text-primary hover:bg-primary-light'
            }`}
          >
            {t === 'corpus' ? '📦 Từ Corpus' : '🌐 Từ TVPL'}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
        {/* ── CORPUS TAB ── */}
        {activeTab === 'corpus' && (
          <div className="max-w-2xl space-y-4">
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h2 className="font-semibold text-gray-800 mb-1">📦 Import từ vn-tax-corpus</h2>
              <p className="text-xs text-gray-500 mb-3">Tìm văn bản mới được thêm vào corpus (so với lần import gần nhất).</p>

              <div className="flex gap-2 items-end">
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Từ ngày (tùy chọn, mặc định = ngày import gần nhất)</label>
                  <input
                    type="date"
                    value={corpusSince}
                    onChange={e => setCorpusSince(e.target.value)}
                    className="px-2 py-1.5 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none"
                  />
                </div>
                <button
                  onClick={handleCorpusCheck}
                  disabled={corpusLoading}
                  className="px-4 py-1.5 bg-primary text-white text-sm rounded hover:bg-primary-dark transition disabled:opacity-50"
                >
                  {corpusLoading ? 'Đang kiểm tra...' : '🔍 Kiểm tra văn bản mới'}
                </button>
              </div>

              {corpusError && <p className="mt-2 text-xs text-red-600">{corpusError}</p>}
            </div>

            {corpusItems.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-gray-700">
                    {corpusItems.length} văn bản mới {corpusSinceDate && <span className="text-gray-400">(từ {corpusSinceDate})</span>}
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setCorpusChecked(new Set(corpusItems.map(i => i.github_path)))}
                      className="text-xs text-primary hover:underline"
                    >
                      Chọn tất cả
                    </button>
                    <button
                      onClick={() => setCorpusChecked(new Set())}
                      className="text-xs text-gray-400 hover:underline"
                    >
                      Bỏ chọn
                    </button>
                  </div>
                </div>

                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {corpusItems.map(item => (
                    <label key={item.github_path} className="flex items-start gap-2 py-1 px-2 rounded hover:bg-gray-50 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={corpusChecked.has(item.github_path)}
                        onChange={e => {
                          const next = new Set(corpusChecked);
                          e.target.checked ? next.add(item.github_path) : next.delete(item.github_path);
                          setCorpusChecked(next);
                        }}
                        className="mt-0.5 accent-primary"
                      />
                      <div className="min-w-0">
                        <p className="text-sm text-gray-800 truncate">{item.name || item.github_path}</p>
                        <p className="text-xs text-gray-400">
                          {item.loai && <span className="mr-2">Loại: {item.loai}</span>}
                          {item.tx && <span className="mr-2">Sắc thuế: {item.tx}</span>}
                          {item.date_id && <span>{formatDateId(String(item.date_id))}</span>}
                        </p>
                      </div>
                    </label>
                  ))}
                </div>

                <button
                  onClick={handleCorpusImport}
                  disabled={corpusImporting || !corpusChecked.size}
                  className="mt-3 w-full py-2 bg-primary text-white text-sm rounded hover:bg-primary-dark transition disabled:opacity-50"
                >
                  {corpusImporting ? 'Đang import...' : `✅ Import đã chọn (${corpusChecked.size})`}
                </button>
              </div>
            )}

            {corpusItems.length === 0 && corpusSinceDate && !corpusLoading && (
              <p className="text-sm text-gray-500 bg-white rounded border p-4">Không có văn bản mới từ {corpusSinceDate}.</p>
            )}

            {corpusResults.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-2">Kết quả import:</h3>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {corpusResults.map((r, i) => (
                    <div key={i} className={`text-xs px-2 py-1 rounded ${r.status === 'ok' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                      {r.status === 'ok'
                        ? `✅ ${r.so_hieu || r.path} — ${r.ten}`
                        : `❌ ${r.path} — ${r.msg}`}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── TVPL TAB ── */}
        {activeTab === 'tvpl' && (
          <div className="max-w-2xl space-y-4">
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h2 className="font-semibold text-gray-800 mb-1">🌐 Import từ TVPL</h2>

              <div className="space-y-3">
                <div>
                  <label className="text-xs text-gray-500 block mb-1">URL văn bản TVPL</label>
                  <input
                    type="url"
                    value={tvplUrl}
                    onChange={e => { setTvplUrl(e.target.value); setTvplPreview(null); setTvplResult(null); }}
                    placeholder="https://thuvienphapluat.vn/van-ban/..."
                    className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none"
                  />
                </div>

                <button
                  onClick={handleTvplPreview}
                  disabled={!tvplUrl || tvplPreviewing}
                  className="px-4 py-1.5 bg-primary text-white text-sm rounded hover:bg-primary-dark transition disabled:opacity-50"
                >
                  {tvplPreviewing ? 'Đang preview...' : '🔍 Preview'}
                </button>

                {tvplFetchError && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded p-3 text-xs text-yellow-800">
                    ⚠️ {tvplFetchError}
                  </div>
                )}

                {(showHtmlPaste || tvplHtml) && (
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">
                      Paste HTML source vào đây (View Source từ trình duyệt):
                    </label>
                    <textarea
                      value={tvplHtml}
                      onChange={e => setTvplHtml(e.target.value)}
                      rows={6}
                      placeholder="Paste toàn bộ HTML source của trang TVPL..."
                      className="w-full px-3 py-2 border border-gray-300 rounded text-xs font-mono focus:border-primary focus:outline-none resize-y"
                    />
                    {tvplHtml && (
                      <button
                        onClick={handleTvplPreview}
                        disabled={tvplPreviewing}
                        className="mt-1 px-3 py-1 bg-primary text-white text-xs rounded hover:bg-primary-dark transition disabled:opacity-50"
                      >
                        🔍 Preview lại với HTML này
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>

            {tvplPreview && (
              <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
                <h3 className="text-sm font-semibold text-gray-700 border-b pb-2">Preview</h3>

                <div className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-2 text-sm">
                  <span className="text-gray-500">Số hiệu:</span>
                  <span className="font-medium">{tvplPreview.so_hieu || '(chưa tìm thấy)'}</span>
                  <span className="text-gray-500">Tiêu đề:</span>
                  <span className="text-gray-700">{tvplPreview.ten}</span>
                  <span className="text-gray-500">Ngày:</span>
                  <span>{tvplPreview.ngay_ban_hanh || '(chưa tìm thấy)'}</span>
                </div>

                <div className="flex gap-4 items-start">
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">Loại văn bản</label>
                    <select
                      value={tvplLoaiOverride}
                      onChange={e => setTvplLoaiOverride(e.target.value)}
                      className="px-2 py-1 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none"
                    >
                      {LOAI_OPTIONS.map(l => <option key={l} value={l}>{l}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">Sắc thuế</label>
                    <div className="flex flex-wrap gap-1">
                      {SAC_THUE_OPTIONS.map(s => (
                        <label key={s} className="flex items-center gap-1 text-xs cursor-pointer">
                          <input
                            type="checkbox"
                            checked={tvplSacThueOverride.includes(s)}
                            onChange={e => {
                              setTvplSacThueOverride(prev =>
                                e.target.checked ? [...prev, s] : prev.filter(x => x !== s)
                              );
                            }}
                            className="accent-primary"
                          />
                          {s}
                        </label>
                      ))}
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleTvplImport}
                  disabled={tvplImporting}
                  className="w-full py-2 bg-primary text-white text-sm rounded hover:bg-primary-dark transition disabled:opacity-50"
                >
                  {tvplImporting ? 'Đang import...' : '✅ Import vào DB'}
                </button>
              </div>
            )}

            {tvplResult && (
              <div className={`rounded-lg border p-4 text-sm ${
                tvplResult.status === 'ok' ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-700'
              }`}>
                {tvplResult.status === 'ok' ? (
                  <>
                    <p className="font-semibold">✅ Import thành công!</p>
                    {tvplResult.preview && (
                      <p className="mt-1 text-xs">{tvplResult.preview.so_hieu} — {tvplResult.preview.ten}</p>
                    )}
                  </>
                ) : (
                  <p>❌ Lỗi: {tvplResult.msg}</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
