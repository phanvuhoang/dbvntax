import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, authHeaders } from '../auth';

type AdminTab = 'corpus' | 'tvpl' | 'documents' | 'watchlist';

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
const TINH_TRANG_OPTIONS = ['con_hieu_luc', 'het_hieu_luc', 'chua_hieu_luc'];
const IMPORTANCE_OPTIONS = [{ v: 1, l: 'Rất quan trọng' }, { v: 2, l: 'Quan trọng' }, { v: 3, l: 'Bình thường' }];
const RELATION_TYPES = ['huong_dan','duoc_huong_dan','sua_doi','bi_sua_doi','thay_the','bi_thay_the','hop_nhat','can_cu','dinh_chinh','lien_quan'];

interface AdminDoc {
  id: number; so_hieu: string; ten: string; loai: string;
  co_quan: string | null; nguoi_ky: string | null;
  ngay_ban_hanh: string | null; hieu_luc_tu: string | null;
  het_hieu_luc_tu: string | null; tinh_trang: string | null;
  sac_thue: string[]; importance: number | null; is_anchor: boolean;
  ngay_cong_bao: string | null; so_cong_bao: string | null; tom_tat: string | null;
}
interface DocRelation {
  id: number; source_id: number; target_so_hieu: string; target_id: number | null;
  target_ten: string | null; target_loai: string | null;
  relation_type: string; ghi_chu: string | null; verified: boolean;
}
interface MissingDoc {
  id: number; so_hieu: string; ten: string | null; loai: string | null;
  mentioned_in_ids: number[] | null; relation_types: string[] | null;
  priority: number; status: string; tvpl_url: string | null; notes: string | null;
}

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

  // Documents tab state
  const [docQuery, setDocQuery] = useState('');
  const [docLoai, setDocLoai] = useState('');
  const [docSacThue, setDocSacThue] = useState('');
  const [docAnchorOnly, setDocAnchorOnly] = useState(false);
  const [docItems, setDocItems] = useState<AdminDoc[]>([]);
  const [docTotal, setDocTotal] = useState(0);
  const [docLoading, setDocLoading] = useState(false);
  const [docOffset, setDocOffset] = useState(0);
  const [editDoc, setEditDoc] = useState<AdminDoc | null>(null);
  const [editForm, setEditForm] = useState<Partial<AdminDoc>>({});
  const [editSaving, setEditSaving] = useState(false);
  const [relationsDoc, setRelationsDoc] = useState<AdminDoc | null>(null);
  const [relations, setRelations] = useState<DocRelation[]>([]);
  const [relLoading, setRelLoading] = useState(false);
  const [extractLoading, setExtractLoading] = useState(false);
  const [extractResult, setExtractResult] = useState<{ relations_found: DocRelation[]; missing_docs: { so_hieu: string; relation_type: string }[] } | null>(null);
  const [extractChecked, setExtractChecked] = useState<Set<number>>(new Set());
  const [newRelForm, setNewRelForm] = useState({ target_so_hieu: '', relation_type: 'lien_quan', ghi_chu: '' });
  const [addingRel, setAddingRel] = useState(false);

  // Watchlist tab state
  const [wlItems, setWlItems] = useState<MissingDoc[]>([]);
  const [wlLoading, setWlLoading] = useState(false);
  const [wlStatus, setWlStatus] = useState('missing');
  const [wlPriority, setWlPriority] = useState('');

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

  const loadDocs = (offset = 0) => {
    setDocLoading(true);
    const p = new URLSearchParams({ limit: '50', offset: String(offset) });
    if (docQuery) p.set('q', docQuery);
    if (docLoai) p.set('loai', docLoai);
    if (docSacThue) p.set('sac_thue', docSacThue);
    if (docAnchorOnly) p.set('anchor_only', 'true');
    fetch(`/api/admin/documents-list?${p}`, { headers: authHeaders(token) })
      .then(r => r.json()).then(d => { setDocItems(d.items || []); setDocTotal(d.total || 0); setDocOffset(offset); })
      .catch(() => {}).finally(() => setDocLoading(false));
  };

  const saveEditDoc = () => {
    if (!editDoc) return;
    setEditSaving(true);
    fetch(`/api/admin/documents/${editDoc.id}`, {
      method: 'PUT', headers: authHeaders(token),
      body: JSON.stringify(editForm),
    }).then(r => r.json()).then(() => {
      setEditDoc(null); loadDocs(docOffset);
    }).catch(() => {}).finally(() => setEditSaving(false));
  };

  const loadRelations = (doc: AdminDoc) => {
    setRelationsDoc(doc); setRelations([]); setExtractResult(null);
    setRelLoading(true);
    fetch(`/api/admin/documents/${doc.id}/relations`, { headers: authHeaders(token) })
      .then(r => r.json()).then(setRelations).catch(() => {}).finally(() => setRelLoading(false));
  };

  const deleteRelation = (relId: number) => {
    if (!window.confirm('Xóa quan hệ này?')) return;
    fetch(`/api/admin/relations/${relId}`, { method: 'DELETE', headers: authHeaders(token) })
      .then(() => relationsDoc && loadRelations(relationsDoc));
  };

  const addRelation = () => {
    if (!relationsDoc || !newRelForm.target_so_hieu) return;
    setAddingRel(true);
    fetch('/api/admin/relations', {
      method: 'POST', headers: authHeaders(token),
      body: JSON.stringify({ source_id: relationsDoc.id, ...newRelForm }),
    }).then(r => r.json()).then(() => {
      setNewRelForm({ target_so_hieu: '', relation_type: 'lien_quan', ghi_chu: '' });
      loadRelations(relationsDoc!);
    }).catch(() => {}).finally(() => setAddingRel(false));
  };

  const extractRelations = () => {
    if (!relationsDoc) return;
    setExtractLoading(true); setExtractResult(null);
    fetch(`/api/admin/documents/${relationsDoc.id}/extract-relations`, { method: 'POST', headers: authHeaders(token) })
      .then(r => r.json()).then(d => {
        setExtractResult(d);
        setExtractChecked(new Set(d.relations_found.map((_: unknown, i: number) => i)));
      }).catch(() => {}).finally(() => setExtractLoading(false));
  };

  const saveExtractedRelations = () => {
    if (!relationsDoc || !extractResult) return;
    const rels = extractResult.relations_found.filter((_, i) => extractChecked.has(i));
    fetch(`/api/admin/documents/${relationsDoc.id}/save-relations`, {
      method: 'POST', headers: authHeaders(token),
      body: JSON.stringify({ relations: rels, missing_docs: extractResult.missing_docs }),
    }).then(r => r.json()).then(() => {
      setExtractResult(null); loadRelations(relationsDoc!);
    }).catch(() => {});
  };

  const loadWatchlist = () => {
    setWlLoading(true);
    const p = new URLSearchParams();
    if (wlStatus) p.set('status', wlStatus);
    if (wlPriority) p.set('priority', wlPriority);
    fetch(`/api/admin/missing-docs?${p}`, { headers: authHeaders(token) })
      .then(r => r.json()).then(setWlItems).catch(() => {}).finally(() => setWlLoading(false));
  };

  const updateMissingDoc = (id: number, updates: object) => {
    fetch(`/api/admin/missing-docs/${id}`, {
      method: 'PUT', headers: authHeaders(token),
      body: JSON.stringify(updates),
    }).then(() => loadWatchlist()).catch(() => {});
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 flex-shrink-0 px-4 h-12 flex items-center gap-4">
        <button onClick={() => navigate('/')} className="text-gray-400 hover:text-primary text-sm">← Về trang chủ</button>
        <span className="text-lg font-bold text-primary">⚙️ Admin Import</span>
      </header>

      {/* Tabs */}
      <div className="border-b border-gray-200 bg-white flex-shrink-0 px-4 flex gap-1 pt-2 flex-wrap">
        {([
          ['corpus', '📦 Từ Corpus'],
          ['tvpl', '🌐 Từ TVPL'],
          ['documents', '📋 Văn bản'],
          ['watchlist', '🔍 VB Thiếu'],
        ] as [AdminTab, string][]).map(([t, label]) => (
          <button
            key={t}
            onClick={() => {
              setActiveTab(t);
              if (t === 'documents') loadDocs(0);
              if (t === 'watchlist' && wlItems.length === 0) loadWatchlist();
            }}
            className={`px-4 py-1.5 text-sm font-medium rounded-t transition ${
              activeTab === t
                ? 'text-primary border-b-2 border-primary bg-primary-light'
                : 'text-gray-500 hover:text-primary hover:bg-primary-light'
            }`}
          >
            {label}
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

        {/* ── DOCUMENTS TAB ── */}
        {activeTab === 'documents' && (
          <div className="space-y-4">
            {/* Filter bar */}
            <div className="bg-white rounded-lg border border-gray-200 p-3 flex flex-wrap gap-2 items-end">
              <input
                type="text"
                placeholder="Tìm số hiệu / tên..."
                value={docQuery}
                onChange={e => setDocQuery(e.target.value)}
                className="px-2 py-1.5 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none"
              />
              <select value={docLoai} onChange={e => setDocLoai(e.target.value)}
                className="px-2 py-1.5 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none bg-white">
                <option value="">Loại</option>
                {LOAI_OPTIONS.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
              <select value={docSacThue} onChange={e => setDocSacThue(e.target.value)}
                className="px-2 py-1.5 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none bg-white">
                <option value="">Sắc thuế</option>
                {SAC_THUE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <label className="flex items-center gap-1 text-sm cursor-pointer select-none">
                <input type="checkbox" checked={docAnchorOnly}
                  onChange={e => setDocAnchorOnly(e.target.checked)}
                  className="w-3.5 h-3.5" />
                <span>⭐ Chỉ Anchor</span>
              </label>
              <button onClick={() => loadDocs(0)} disabled={docLoading}
                className="px-3 py-1.5 bg-primary text-white text-sm rounded hover:bg-primary-dark disabled:opacity-50 transition">
                {docLoading ? 'Đang tải...' : '🔍 Tìm'}
              </button>
              <span className="text-xs text-gray-400 ml-auto">{docTotal} văn bản</span>
            </div>

            {/* Table */}
            {docItems.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Số hiệu</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Tên văn bản</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Loại</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Ngày</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Tình trạng</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Thao tác</th>
                      </tr>
                    </thead>
                    <tbody>
                      {docItems.map(doc => (
                        <tr key={doc.id} className="border-b border-gray-100 hover:bg-gray-50">
                          <td className="px-3 py-2 font-medium text-primary whitespace-nowrap">
                            {doc.so_hieu}
                            {doc.is_anchor && (
                              <span className="ml-1 px-1 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded">⭐ Anchor</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-gray-700 max-w-xs">
                            <p className="truncate" title={doc.ten}>{doc.ten}</p>
                          </td>
                          <td className="px-3 py-2 text-gray-500">{doc.loai}</td>
                          <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{doc.ngay_ban_hanh?.slice(0, 10) || ''}</td>
                          <td className="px-3 py-2">
                            <span className={`text-[11px] px-1.5 py-0.5 rounded font-medium ${
                              doc.tinh_trang === 'con_hieu_luc' ? 'bg-green-100 text-green-700' :
                              doc.tinh_trang === 'het_hieu_luc' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-500'
                            }`}>{doc.tinh_trang || '—'}</span>
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex gap-1">
                              <button onClick={() => { setEditDoc(doc); setEditForm({ ...doc }); }}
                                className="px-2 py-1 text-xs border border-gray-200 rounded hover:border-primary hover:text-primary transition">
                                ✏️ Sửa
                              </button>
                              <button onClick={() => loadRelations(doc)}
                                className="px-2 py-1 text-xs border border-gray-200 rounded hover:border-primary hover:text-primary transition">
                                🔗 QH
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center gap-3 px-3 py-2 border-t border-gray-100 bg-gray-50">
                  <button disabled={docOffset === 0} onClick={() => loadDocs(Math.max(0, docOffset - 50))}
                    className="px-3 py-1 text-xs border border-gray-200 rounded disabled:opacity-40">← Trước</button>
                  <span className="text-xs text-gray-500">{docOffset + 1}–{Math.min(docOffset + 50, docTotal)} / {docTotal}</span>
                  <button disabled={docOffset + 50 >= docTotal} onClick={() => loadDocs(docOffset + 50)}
                    className="px-3 py-1 text-xs border border-gray-200 rounded disabled:opacity-40">Sau →</button>
                </div>
              </div>
            )}

            {/* Edit Modal */}
            {editDoc && (
              <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
                  <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
                    <h3 className="font-semibold text-gray-800">Sửa văn bản: {editDoc.so_hieu}</h3>
                    <button onClick={() => setEditDoc(null)} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
                  </div>
                  <div className="p-5 space-y-3">
                    {([
                      ['so_hieu', 'Số hiệu', 'text'],
                      ['co_quan', 'Cơ quan', 'text'],
                      ['nguoi_ky', 'Người ký', 'text'],
                      ['ngay_ban_hanh', 'Ngày ban hành', 'date'],
                      ['hieu_luc_tu', 'Hiệu lực từ', 'date'],
                      ['het_hieu_luc_tu', 'Hết hiệu lực từ', 'date'],
                      ['ngay_cong_bao', 'Ngày công báo', 'date'],
                      ['so_cong_bao', 'Số công báo', 'text'],
                    ] as [string, string, string][]).map(([k, label, type]) => (
                      <div key={k} className="flex gap-3 items-start">
                        <label className="text-xs text-gray-500 w-32 shrink-0 pt-1.5">{label}</label>
                        <input type={type} value={(editForm as Record<string, string>)[k] || ''}
                          onChange={e => setEditForm(f => ({ ...f, [k]: e.target.value }))}
                          className="flex-1 px-2 py-1.5 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none" />
                      </div>
                    ))}
                    <div className="flex gap-3 items-start">
                      <label className="text-xs text-gray-500 w-32 shrink-0 pt-1.5">Tên văn bản</label>
                      <textarea value={editForm.ten || ''}
                        onChange={e => setEditForm(f => ({ ...f, ten: e.target.value }))}
                        rows={3}
                        className="flex-1 px-2 py-1.5 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none resize-y" />
                    </div>
                    <div className="flex gap-3 items-start">
                      <label className="text-xs text-gray-500 w-32 shrink-0 pt-1.5">Loại VB</label>
                      <select value={editForm.loai || ''}
                        onChange={e => setEditForm(f => ({ ...f, loai: e.target.value }))}
                        className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white focus:border-primary focus:outline-none">
                        {LOAI_OPTIONS.map(l => <option key={l} value={l}>{l}</option>)}
                      </select>
                    </div>
                    <div className="flex gap-3 items-start">
                      <label className="text-xs text-gray-500 w-32 shrink-0 pt-1.5">Tình trạng</label>
                      <select value={editForm.tinh_trang || ''}
                        onChange={e => setEditForm(f => ({ ...f, tinh_trang: e.target.value }))}
                        className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white focus:border-primary focus:outline-none">
                        {TINH_TRANG_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                    <div className="flex gap-3 items-start">
                      <label className="text-xs text-gray-500 w-32 shrink-0 pt-1.5">Sắc thuế</label>
                      <div className="flex flex-wrap gap-1">
                        {SAC_THUE_OPTIONS.map(s => (
                          <label key={s} className="flex items-center gap-1 text-xs cursor-pointer">
                            <input type="checkbox"
                              checked={(editForm.sac_thue || []).includes(s)}
                              onChange={e => setEditForm(f => ({
                                ...f,
                                sac_thue: e.target.checked
                                  ? [...(f.sac_thue || []), s]
                                  : (f.sac_thue || []).filter(x => x !== s)
                              }))}
                              className="accent-primary" />
                            {s}
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-3 items-start">
                      <label className="text-xs text-gray-500 w-32 shrink-0 pt-1.5">Độ quan trọng</label>
                      <select value={editForm.importance || 3}
                        onChange={e => setEditForm(f => ({ ...f, importance: parseInt(e.target.value) }))}
                        className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white focus:border-primary focus:outline-none">
                        {IMPORTANCE_OPTIONS.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
                      </select>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <input
                        type="checkbox"
                        id="is_anchor"
                        checked={editForm.is_anchor || false}
                        onChange={e => setEditForm(f => ({ ...f, is_anchor: e.target.checked }))}
                        className="w-4 h-4 text-primary"
                      />
                      <label htmlFor="is_anchor" className="text-sm font-medium">
                        ⭐ Anchor — VB nền tảng (RAG luôn load full text)
                      </label>
                    </div>
                    <div className="flex gap-3 items-start">
                      <label className="text-xs text-gray-500 w-32 shrink-0 pt-1.5">Tóm tắt</label>
                      <textarea value={editForm.tom_tat || ''}
                        onChange={e => setEditForm(f => ({ ...f, tom_tat: e.target.value }))}
                        rows={3}
                        className="flex-1 px-2 py-1.5 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none resize-y" />
                    </div>
                  </div>
                  <div className="px-5 pb-4 flex gap-2 justify-end">
                    <button onClick={() => setEditDoc(null)}
                      className="px-4 py-1.5 border border-gray-300 text-sm rounded text-gray-600 hover:bg-gray-50 transition">
                      Hủy
                    </button>
                    <button onClick={saveEditDoc} disabled={editSaving}
                      className="px-4 py-1.5 bg-primary text-white text-sm rounded hover:bg-primary-dark disabled:opacity-50 transition">
                      {editSaving ? 'Đang lưu...' : '✅ Lưu'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Relations Panel */}
            {relationsDoc && (
              <div className="fixed inset-0 bg-black/40 z-50 flex items-start justify-end p-4">
                <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl h-[90vh] flex flex-col">
                  <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                    <h3 className="font-semibold text-gray-800">🔗 Quan hệ: {relationsDoc.so_hieu}</h3>
                    <button onClick={() => { setRelationsDoc(null); setExtractResult(null); }} className="text-gray-400 hover:text-gray-600">✕</button>
                  </div>
                  <div className="flex-1 overflow-y-auto p-5 space-y-4">
                    {/* Add new relation */}
                    <div className="bg-gray-50 rounded-lg p-3 space-y-2">
                      <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider">+ Thêm quan hệ</p>
                      <div className="flex gap-2 flex-wrap">
                        <input type="text" placeholder="Số hiệu VB liên quan"
                          value={newRelForm.target_so_hieu}
                          onChange={e => setNewRelForm(f => ({ ...f, target_so_hieu: e.target.value }))}
                          className="flex-1 min-w-[160px] px-2 py-1.5 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none" />
                        <select value={newRelForm.relation_type}
                          onChange={e => setNewRelForm(f => ({ ...f, relation_type: e.target.value }))}
                          className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white focus:border-primary focus:outline-none">
                          {RELATION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                        </select>
                        <input type="text" placeholder="Ghi chú (tùy chọn)"
                          value={newRelForm.ghi_chu}
                          onChange={e => setNewRelForm(f => ({ ...f, ghi_chu: e.target.value }))}
                          className="flex-1 min-w-[120px] px-2 py-1.5 border border-gray-300 rounded text-sm focus:border-primary focus:outline-none" />
                        <button onClick={addRelation} disabled={addingRel || !newRelForm.target_so_hieu}
                          className="px-3 py-1.5 bg-primary text-white text-sm rounded hover:bg-primary-dark disabled:opacity-50 transition">
                          + Thêm
                        </button>
                      </div>
                    </div>

                    {/* Existing relations */}
                    {relLoading ? <p className="text-sm text-gray-400">Đang tải...</p> : (
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Quan hệ hiện có ({relations.length})</p>
                        {relations.length === 0 ? (
                          <p className="text-xs text-gray-400 italic">Chưa có quan hệ nào</p>
                        ) : (
                          <table className="w-full text-xs">
                            <thead><tr className="bg-gray-50">
                              <th className="px-2 py-1 text-left text-gray-500">Loại</th>
                              <th className="px-2 py-1 text-left text-gray-500">Văn bản</th>
                              <th className="px-2 py-1 text-left text-gray-500">Ghi chú</th>
                              <th className="px-2 py-1 text-gray-500">✓</th>
                              <th className="px-2 py-1"></th>
                            </tr></thead>
                            <tbody>
                              {relations.map(rel => (
                                <tr key={rel.id} className="border-b border-gray-100">
                                  <td className="px-2 py-1">
                                    <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-[10px]">{rel.relation_type}</span>
                                  </td>
                                  <td className="px-2 py-1">
                                    <span className="font-medium text-primary">{rel.target_so_hieu}</span>
                                    {rel.target_ten && <span className="text-gray-400 ml-1 truncate max-w-[120px] inline-block">{rel.target_ten}</span>}
                                  </td>
                                  <td className="px-2 py-1 text-gray-400">{rel.ghi_chu || '—'}</td>
                                  <td className="px-2 py-1 text-center">{rel.verified ? '✅' : '⬜'}</td>
                                  <td className="px-2 py-1">
                                    <button onClick={() => deleteRelation(rel.id)} className="text-red-400 hover:text-red-600">✕</button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    )}

                    {/* AI Extract */}
                    <div className="border-t border-gray-200 pt-3">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider">🤖 Trích xuất bằng AI</p>
                        <button onClick={extractRelations} disabled={extractLoading}
                          className="px-3 py-1 text-xs bg-primary text-white rounded hover:bg-primary-dark disabled:opacity-50 transition">
                          {extractLoading ? 'Đang phân tích...' : 'Extract từ AI'}
                        </button>
                      </div>
                      {extractResult && (
                        <div className="space-y-2">
                          <p className="text-xs text-gray-500">{extractResult.relations_found.length} quan hệ tìm thấy · {extractResult.missing_docs.length} VB thiếu</p>
                          <div className="space-y-1 max-h-48 overflow-y-auto">
                            {extractResult.relations_found.map((rel, i) => (
                              <label key={i} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-gray-50 px-2 py-1 rounded">
                                <input type="checkbox" checked={extractChecked.has(i)}
                                  onChange={e => setExtractChecked(prev => {
                                    const n = new Set(prev); e.target.checked ? n.add(i) : n.delete(i); return n;
                                  })} className="accent-primary" />
                                <span className="bg-blue-100 text-blue-700 px-1 py-0.5 rounded text-[10px]">{rel.relation_type}</span>
                                <span className="font-medium text-primary">{rel.target_so_hieu}</span>
                                {!rel.target_id && <span className="text-red-400 text-[10px]">❌ Thiếu</span>}
                                {rel.ghi_chu && <span className="text-gray-400">{rel.ghi_chu}</span>}
                              </label>
                            ))}
                          </div>
                          <button onClick={saveExtractedRelations} disabled={extractChecked.size === 0}
                            className="w-full py-1.5 bg-primary text-white text-xs rounded hover:bg-primary-dark disabled:opacity-50 transition">
                            ✅ Lưu {extractChecked.size} quan hệ đã chọn
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── WATCHLIST TAB ── */}
        {activeTab === 'watchlist' && (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border border-gray-200 p-3 flex flex-wrap gap-2 items-end">
              <select value={wlStatus} onChange={e => setWlStatus(e.target.value)}
                className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white focus:border-primary focus:outline-none">
                <option value="">Tất cả trạng thái</option>
                <option value="missing">Còn thiếu</option>
                <option value="imported">Đã nhập</option>
                <option value="ignored">Bỏ qua</option>
              </select>
              <select value={wlPriority} onChange={e => setWlPriority(e.target.value)}
                className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white focus:border-primary focus:outline-none">
                <option value="">Tất cả ưu tiên</option>
                <option value="1">🔴 Cao</option>
                <option value="2">🟡 Trung bình</option>
                <option value="3">⚪ Thấp</option>
              </select>
              <button onClick={loadWatchlist} disabled={wlLoading}
                className="px-3 py-1.5 bg-primary text-white text-sm rounded hover:bg-primary-dark disabled:opacity-50 transition">
                {wlLoading ? 'Đang tải...' : '🔍 Lọc'}
              </button>
              <span className="text-xs text-gray-400 ml-auto">{wlItems.length} mục</span>
            </div>

            {wlItems.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Số hiệu</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Được đề cập trong</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Loại QH</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Ưu tiên</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Trạng thái</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Thao tác</th>
                      </tr>
                    </thead>
                    <tbody>
                      {wlItems.map(item => (
                        <tr key={item.id} className="border-b border-gray-100 hover:bg-gray-50">
                          <td className="px-3 py-2 font-medium text-primary">{item.so_hieu}</td>
                          <td className="px-3 py-2 text-xs text-gray-500">
                            {(item.mentioned_in_ids || []).length} văn bản
                          </td>
                          <td className="px-3 py-2 text-xs text-gray-400">
                            {(item.relation_types || []).join(', ')}
                          </td>
                          <td className="px-3 py-2">
                            <span className={`text-xs font-medium ${
                              item.priority === 1 ? 'text-red-600' : item.priority === 2 ? 'text-yellow-600' : 'text-gray-400'
                            }`}>
                              {item.priority === 1 ? '🔴 Cao' : item.priority === 2 ? '🟡 TB' : '⚪ Thấp'}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            <span className={`text-[11px] px-1.5 py-0.5 rounded ${
                              item.status === 'imported' ? 'bg-green-100 text-green-700' :
                              item.status === 'ignored' ? 'bg-gray-100 text-gray-500' : 'bg-yellow-100 text-yellow-700'
                            }`}>{item.status}</span>
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex gap-1">
                              {item.status !== 'imported' && (
                                <button onClick={() => updateMissingDoc(item.id, { status: 'imported' })}
                                  className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 transition">
                                  Đã có
                                </button>
                              )}
                              {item.status !== 'ignored' && (
                                <button onClick={() => updateMissingDoc(item.id, { status: 'ignored' })}
                                  className="px-2 py-0.5 text-xs bg-gray-100 text-gray-500 rounded hover:bg-gray-200 transition">
                                  Bỏ qua
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {wlItems.length === 0 && !wlLoading && (
              <div className="bg-white rounded-lg border border-gray-200 p-8 text-center text-sm text-gray-400">
                Không có văn bản nào trong danh sách theo dõi
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
