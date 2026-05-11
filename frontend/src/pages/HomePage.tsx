import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { Document, CongVan } from '../types';
import { CATEGORIES, LOAI_LABELS } from '../types';
import { useSearch, useCongVan, useHealth } from '../api';
import { useAuth } from '../auth';
import Sidebar, { CATEGORY_TO_DB } from '../components/Sidebar';
import SearchBar from '../components/SearchBar';
import DocList from '../components/DocList';
import ContentPanel from '../components/ContentPanel';
import AuthModal from '../components/AuthModal';
import QuickAnalysis from '../components/QuickAnalysis';
import Divider from '../components/Divider';
import AskAIPage from './AskAIPage';

type Tab = 'vanban' | 'congvan' | 'ask_ai';

const LIMIT = 20;

const TINH_TRANG_LABELS: Record<string, string> = {
  con_hieu_luc: 'Còn hiệu lực',
  het_hieu_luc: 'Hết hiệu lực',
  chua_hieu_luc: 'Chưa hiệu lực',
};

const SOURCE_LABELS: Record<string, string> = {
  dbvntax: 'DB VNTax',
  tvpl: 'TVPL',
  luatvietnam: 'LuatVN',
  upload: 'Upload',
  manual: 'Thủ công',
};

const LOAI_OPTIONS = ['LUAT', 'ND', 'TT', 'QD', 'NQ', 'VBHN', 'CV'];

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return isMobile;
}

interface ActiveFilters {
  loai?: string;
  sacThue?: string;
  tinhTrang?: string;
  anchorOnly?: boolean;
  source?: string;
  dateFrom?: string;
  dateTo?: string;
}

interface DatePopoverProps {
  dateFrom: string;
  dateTo: string;
  onChange: (from: string, to: string) => void;
  onClose: () => void;
}

function DatePopover({ dateFrom, dateTo, onChange, onClose }: DatePopoverProps) {
  const [from, setFrom] = useState(dateFrom);
  const [to, setTo] = useState(dateTo);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  return (
    <div ref={ref} className="absolute top-full left-0 mt-2 bg-white border border-gray-200 rounded-xl shadow-xl p-4 z-50 w-64">
      <p className="text-xs font-semibold text-gray-600 mb-3">Giai đoạn ban hành</p>
      <div className="space-y-2">
        <div>
          <label className="text-[10px] text-gray-400 uppercase tracking-wide block mb-1">Từ ngày</label>
          <input type="date" value={from} onChange={e => setFrom(e.target.value)}
            className="w-full px-2 py-1 border border-gray-200 rounded-lg text-xs focus:outline-none focus:border-primary" />
        </div>
        <div>
          <label className="text-[10px] text-gray-400 uppercase tracking-wide block mb-1">Đến ngày</label>
          <input type="date" value={to} onChange={e => setTo(e.target.value)}
            className="w-full px-2 py-1 border border-gray-200 rounded-lg text-xs focus:outline-none focus:border-primary" />
        </div>
        <div className="flex gap-2 pt-1">
          <button onClick={() => { onChange(from, to); onClose(); }}
            className="flex-1 py-1.5 bg-primary text-white text-xs rounded-lg hover:bg-primary-dark transition">
            Áp dụng
          </button>
          <button onClick={() => { setFrom(''); setTo(''); onChange('', ''); onClose(); }}
            className="px-3 py-1.5 border border-gray-200 text-gray-500 text-xs rounded-lg hover:border-primary hover:text-primary transition">
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}

function FilterChipRow({
  tab,
  filters,
  onChange,
  onReset,
}: {
  tab: Tab;
  filters: ActiveFilters;
  onChange: (f: ActiveFilters) => void;
  onReset: () => void;
}) {
  const [openLoai, setOpenLoai] = useState(false);
  const [openSacThue, setOpenSacThue] = useState(false);
  const [openTinhTrang, setOpenTinhTrang] = useState(false);
  const [openSource, setOpenSource] = useState(false);
  const [openDate, setOpenDate] = useState(false);

  const hasFilters = !!(filters.loai || filters.sacThue || filters.tinhTrang || filters.anchorOnly || filters.source || filters.dateFrom || filters.dateTo);

  if (tab === 'ask_ai') return null;

  return (
    <div className="border-b border-gray-100 bg-white px-4 py-2 flex-shrink-0">
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-0.5">
        {/* Loai VB */}
        <div className="relative flex-shrink-0">
          <button
            onClick={() => { setOpenLoai(o => !o); setOpenSacThue(false); setOpenTinhTrang(false); setOpenSource(false); setOpenDate(false); }}
            className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition ${
              filters.loai ? 'bg-primary text-white border-primary' : 'bg-white text-gray-600 border-gray-200 hover:border-primary hover:text-primary'
            }`}
          >
            {filters.loai ? LOAI_LABELS[filters.loai] || filters.loai : 'Loại VB'}
            {filters.loai ? (
              <span className="ml-0.5" onClick={(e) => { e.stopPropagation(); onChange({ ...filters, loai: undefined }); }}>✕</span>
            ) : <span className="text-[10px]">▾</span>}
          </button>
          {openLoai && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-50 min-w-[120px] py-1">
              <button onClick={() => { onChange({ ...filters, loai: undefined }); setOpenLoai(false); }}
                className="w-full text-left px-3 py-1.5 text-xs text-gray-400 hover:bg-primary-light">Tất cả</button>
              {LOAI_OPTIONS.map(l => (
                <button key={l} onClick={() => { onChange({ ...filters, loai: l }); setOpenLoai(false); }}
                  className={`w-full text-left px-3 py-1.5 text-xs hover:bg-primary-light hover:text-primary ${filters.loai === l ? 'text-primary font-semibold bg-primary-light' : 'text-gray-600'}`}>
                  {LOAI_LABELS[l] || l}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Sắc thuế */}
        <div className="relative flex-shrink-0">
          <button
            onClick={() => { setOpenSacThue(o => !o); setOpenLoai(false); setOpenTinhTrang(false); setOpenSource(false); setOpenDate(false); }}
            className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition ${
              filters.sacThue ? 'bg-primary text-white border-primary' : 'bg-white text-gray-600 border-gray-200 hover:border-primary hover:text-primary'
            }`}
          >
            {filters.sacThue ? CATEGORIES.find(c => c.code === filters.sacThue)?.name || filters.sacThue : 'Sắc thuế'}
            {filters.sacThue ? (
              <span className="ml-0.5" onClick={(e) => { e.stopPropagation(); onChange({ ...filters, sacThue: undefined }); }}>✕</span>
            ) : <span className="text-[10px]">▾</span>}
          </button>
          {openSacThue && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-50 min-w-[160px] py-1 max-h-56 overflow-y-auto">
              <button onClick={() => { onChange({ ...filters, sacThue: undefined }); setOpenSacThue(false); }}
                className="w-full text-left px-3 py-1.5 text-xs text-gray-400 hover:bg-primary-light">Tất cả</button>
              {CATEGORIES.map(cat => (
                <button key={cat.code} onClick={() => { onChange({ ...filters, sacThue: cat.code }); setOpenSacThue(false); }}
                  className={`w-full text-left px-3 py-1.5 text-xs hover:bg-primary-light hover:text-primary ${filters.sacThue === cat.code ? 'text-primary font-semibold bg-primary-light' : 'text-gray-600'}`}>
                  {cat.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Tình trạng */}
        <div className="relative flex-shrink-0">
          <button
            onClick={() => { setOpenTinhTrang(o => !o); setOpenLoai(false); setOpenSacThue(false); setOpenSource(false); setOpenDate(false); }}
            className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition ${
              filters.tinhTrang ? 'bg-primary text-white border-primary' : 'bg-white text-gray-600 border-gray-200 hover:border-primary hover:text-primary'
            }`}
          >
            {filters.tinhTrang ? TINH_TRANG_LABELS[filters.tinhTrang] || filters.tinhTrang : 'Tình trạng'}
            {filters.tinhTrang ? (
              <span className="ml-0.5" onClick={(e) => { e.stopPropagation(); onChange({ ...filters, tinhTrang: undefined }); }}>✕</span>
            ) : <span className="text-[10px]">▾</span>}
          </button>
          {openTinhTrang && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-50 min-w-[160px] py-1">
              <button onClick={() => { onChange({ ...filters, tinhTrang: undefined }); setOpenTinhTrang(false); }}
                className="w-full text-left px-3 py-1.5 text-xs text-gray-400 hover:bg-primary-light">Tất cả</button>
              {Object.entries(TINH_TRANG_LABELS).map(([v, l]) => (
                <button key={v} onClick={() => { onChange({ ...filters, tinhTrang: v }); setOpenTinhTrang(false); }}
                  className={`w-full text-left px-3 py-1.5 text-xs hover:bg-primary-light hover:text-primary ${filters.tinhTrang === v ? 'text-primary font-semibold bg-primary-light' : 'text-gray-600'}`}>
                  {l}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Anchor only toggle */}
        <button
          onClick={() => onChange({ ...filters, anchorOnly: !filters.anchorOnly })}
          className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition flex-shrink-0 ${
            filters.anchorOnly ? 'bg-yellow-500 text-white border-yellow-500' : 'bg-white text-gray-600 border-gray-200 hover:border-yellow-400 hover:text-yellow-600'
          }`}
        >
          ⭐ Quan trọng
          {filters.anchorOnly && <span onClick={(e) => { e.stopPropagation(); onChange({ ...filters, anchorOnly: false }); }}>✕</span>}
        </button>

        {/* Source */}
        <div className="relative flex-shrink-0">
          <button
            onClick={() => { setOpenSource(o => !o); setOpenLoai(false); setOpenSacThue(false); setOpenTinhTrang(false); setOpenDate(false); }}
            className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition ${
              filters.source ? 'bg-primary text-white border-primary' : 'bg-white text-gray-600 border-gray-200 hover:border-primary hover:text-primary'
            }`}
          >
            {filters.source ? SOURCE_LABELS[filters.source] || filters.source : 'Nguồn'}
            {filters.source ? (
              <span className="ml-0.5" onClick={(e) => { e.stopPropagation(); onChange({ ...filters, source: undefined }); }}>✕</span>
            ) : <span className="text-[10px]">▾</span>}
          </button>
          {openSource && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-50 min-w-[120px] py-1">
              <button onClick={() => { onChange({ ...filters, source: undefined }); setOpenSource(false); }}
                className="w-full text-left px-3 py-1.5 text-xs text-gray-400 hover:bg-primary-light">Tất cả</button>
              {Object.entries(SOURCE_LABELS).map(([v, l]) => (
                <button key={v} onClick={() => { onChange({ ...filters, source: v }); setOpenSource(false); }}
                  className={`w-full text-left px-3 py-1.5 text-xs hover:bg-primary-light hover:text-primary ${filters.source === v ? 'text-primary font-semibold bg-primary-light' : 'text-gray-600'}`}>
                  {l}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Date range */}
        <div className="relative flex-shrink-0">
          <button
            onClick={() => { setOpenDate(o => !o); setOpenLoai(false); setOpenSacThue(false); setOpenTinhTrang(false); setOpenSource(false); }}
            className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition ${
              (filters.dateFrom || filters.dateTo) ? 'bg-primary text-white border-primary' : 'bg-white text-gray-600 border-gray-200 hover:border-primary hover:text-primary'
            }`}
          >
            📅 {filters.dateFrom || filters.dateTo
              ? `${filters.dateFrom || '...'} → ${filters.dateTo || '...'}`
              : 'Ngày ban hành'}
            {(filters.dateFrom || filters.dateTo) && (
              <span className="ml-0.5" onClick={(e) => { e.stopPropagation(); onChange({ ...filters, dateFrom: undefined, dateTo: undefined }); }}>✕</span>
            )}
          </button>
          {openDate && (
            <DatePopover
              dateFrom={filters.dateFrom || ''}
              dateTo={filters.dateTo || ''}
              onChange={(from, to) => onChange({ ...filters, dateFrom: from || undefined, dateTo: to || undefined })}
              onClose={() => setOpenDate(false)}
            />
          )}
        </div>

        {/* Reset */}
        {hasFilters && (
          <button
            onClick={onReset}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border border-red-200 text-red-500 hover:bg-red-50 transition flex-shrink-0"
          >
            ↺ Reset
          </button>
        )}
      </div>
    </div>
  );
}

export default function HomePage() {
  const [tab, setTab] = useState<Tab>('vanban');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(1);
  const [selectedItem, setSelectedItem] = useState<Document | CongVan | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [showAI, setShowAI] = useState(false);
  const [selectedChuDe, setSelectedChuDe] = useState('');
  const [filters, setFilters] = useState<ActiveFilters>({});

  // Resizable panel widths
  const [sidebarW, setSidebarW] = useState(200);
  const [listW, setListW] = useState(280);

  // Collapsible panels
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [listCollapsed, setListCollapsed] = useState(false);

  // Mobile state
  const [mobileListOpen, setMobileListOpen] = useState(false);
  const isMobile = useIsMobile();

  const auth = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { data: health } = useHealth();

  // Deep link: ?doc=<id> → auto-open document
  useEffect(() => {
    const docId = searchParams.get('doc');
    if (!docId) return;
    fetch(`/api/documents/${docId}`)
      .then(r => r.ok ? r.json() : null)
      .then(doc => {
        if (doc) {
          setSelectedItem(doc);
          setTab('vanban');
        }
      })
      .catch(() => {});
  }, [searchParams]);

  // Determine the sac_thue filter — sidebar category takes priority over chip filter
  const effectiveSacThue = category
    ? (CATEGORY_TO_DB[category] ?? category)
    : filters.sacThue
      ? (CATEGORY_TO_DB[filters.sacThue] ?? filters.sacThue)
      : undefined;

  const searchResult = useSearch({
    q: query,
    sac_thue: effectiveSacThue,
    loai: filters.loai,
    tinh_trang: filters.tinhTrang,
    hl: filters.anchorOnly ? 1 : undefined,
    date_from: filters.dateFrom || undefined,
    date_to: filters.dateTo || undefined,
    mode: 'hybrid',
    limit: LIMIT,
    offset: (page - 1) * LIMIT,
  });

  const congVanResult = useCongVan({
    q: query,
    sac_thue: effectiveSacThue,
    chu_de: selectedChuDe,
    date_from: filters.dateFrom || undefined,
    date_to: filters.dateTo || undefined,
    mode: query ? 'semantic' : undefined,
    limit: LIMIT,
    offset: (page - 1) * LIMIT,
  });

  const items = tab === 'vanban'
    ? (searchResult.data?.results ?? [])
    : (congVanResult.data?.items ?? []);
  const total = tab === 'vanban'
    ? (searchResult.data?.total ?? 0)
    : (congVanResult.data?.total ?? 0);
  const isLoading = tab === 'vanban' ? searchResult.isLoading : congVanResult.isLoading;

  const handleSearch = useCallback((q: string) => {
    setQuery(q); setPage(1); setSelectedItem(null);
  }, []);

  const handleCategorySelect = useCallback((code: string) => {
    setCategory(code); setPage(1); setSelectedItem(null);
    setSelectedChuDe('');
  }, []);

  const handleTabChange = useCallback((t: Tab) => {
    setTab(t); setPage(1); setSelectedItem(null);
    setSelectedChuDe(''); setCategory('');
  }, []);

  const requestLogin = useCallback(() => setShowAuth(true), []);

  const handleSidebarResize = useCallback((dx: number) => {
    setSidebarW((w) => Math.max(140, Math.min(400, w + dx)));
  }, []);

  const handleListResize = useCallback((dx: number) => {
    setListW((w) => Math.max(200, Math.min(500, w + dx)));
  }, []);

  const handleFiltersChange = useCallback((f: ActiveFilters) => {
    setFilters(f);
    setPage(1);
    setSelectedItem(null);
  }, []);

  const handleFiltersReset = useCallback(() => {
    setFilters({});
    setPage(1);
    setSelectedItem(null);
  }, []);

  // Mobile: when item selected, show fullscreen content
  const mobileContentFullscreen = isMobile && selectedItem !== null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 flex-shrink-0 shadow-sm">
        <div className="flex items-center gap-2 px-4 h-12">
          {/* Mobile menu button */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="md:hidden text-gray-400 hover:text-primary transition"
            aria-label="Menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Logo */}
          <span className="text-base font-bold text-primary whitespace-nowrap tracking-tight">
            ⚖️ VNTaxDB
          </span>

          {/* Tabs — hidden on mobile when content fullscreen */}
          {!mobileContentFullscreen && (
            <div className="hidden md:flex gap-0.5 ml-2">
              {([
                ['vanban', 'Văn bản'],
                ['congvan', 'Công văn'],
                ['ask_ai', '🤖 Hỏi đáp AI'],
              ] as const).map(([t, label]) => (
                <button
                  key={t}
                  onClick={() => handleTabChange(t)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-lg transition ${
                    tab === t
                      ? 'text-primary bg-primary-light'
                      : 'text-gray-500 hover:text-primary hover:bg-gray-50'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* Mobile tabs */}
          {!mobileContentFullscreen && (
            <div className="flex md:hidden gap-0.5 ml-1 overflow-x-auto no-scrollbar">
              {([
                ['vanban', 'VB'],
                ['congvan', 'CV'],
                ['ask_ai', '🤖'],
              ] as const).map(([t, label]) => (
                <button
                  key={t}
                  onClick={() => handleTabChange(t)}
                  className={`px-2.5 py-1.5 text-xs font-medium rounded-lg transition shrink-0 ${
                    tab === t
                      ? 'text-primary bg-primary-light'
                      : 'text-gray-500 hover:text-primary hover:bg-gray-50'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* Stats — desktop only */}
          {health && (
            <span className="ml-auto text-xs text-gray-300 hidden lg:block shrink-0">
              {health.documents.toLocaleString()} VB · {health.cong_van.toLocaleString()} CV
            </span>
          )}

          {/* AI sidebar toggle */}
          <button
            onClick={() => setShowAI(!showAI)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition hidden sm:block ml-auto ${
              showAI ? 'bg-primary text-white' : 'text-gray-500 hover:text-primary hover:bg-primary-light'
            }`}
          >
            🤖 Hỏi AI
          </button>

          {/* Admin button */}
          {auth.user?.role === 'admin' && (
            <button
              onClick={() => navigate('/admin')}
              className="px-3 py-1.5 text-xs font-medium rounded-lg transition text-gray-500 hover:text-primary hover:bg-primary-light hidden sm:block"
            >
              ⚙️ Admin
            </button>
          )}

          {/* Auth */}
          <div className="flex items-center gap-2 shrink-0">
            {auth.isLoggedIn ? (
              <>
                <span className="text-xs text-primary font-medium hidden sm:block max-w-[100px] truncate">
                  {auth.user?.ho_ten || auth.user?.email}
                </span>
                <button
                  onClick={auth.logout}
                  className="px-2.5 py-1 text-xs border border-gray-200 rounded-lg text-gray-500 hover:border-primary hover:text-primary transition"
                >
                  Đăng xuất
                </button>
              </>
            ) : (
              <button
                onClick={() => setShowAuth(true)}
                className="px-3 py-1.5 text-xs bg-primary text-white rounded-lg hover:bg-primary-dark transition font-medium"
              >
                Đăng nhập
              </button>
            )}
          </div>
        </div>

        {/* Search bar */}
        {tab !== 'ask_ai' && (
          <div className="px-4 py-2">
            <SearchBar value={query} onChange={handleSearch} />
          </div>
        )}
      </header>

      {/* Filter chip row — under search, above content */}
      {tab !== 'ask_ai' && (
        <FilterChipRow
          tab={tab}
          filters={filters}
          onChange={handleFiltersChange}
          onReset={handleFiltersReset}
        />
      )}

      {/* Ask AI tab — full content area */}
      {tab === 'ask_ai' && (
        <div className="flex flex-1 overflow-hidden">
          <AskAIPage />
        </div>
      )}

      {/* Main Content — 3-panel layout (vanban / congvan tabs) */}
      {tab !== 'ask_ai' && (
        <div className="flex flex-1 overflow-hidden relative select-none">
          {sidebarOpen && (
            <div className="fixed inset-0 bg-black/30 z-30 md:hidden" onClick={() => setSidebarOpen(false)} />
          )}

          {/* Sidebar — hidden on mobile when content is fullscreen */}
          {!mobileContentFullscreen && (
            <div
              className={`${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 transition-transform duration-200 fixed md:static z-40 md:z-auto h-full flex-shrink-0`}
              style={{ width: sidebarCollapsed ? 40 : sidebarW }}
            >
              <Sidebar
                selected={category}
                onSelect={(code) => { handleCategorySelect(code); setSidebarOpen(false); }}
                dateFrom={filters.dateFrom || ''}
                dateTo={filters.dateTo || ''}
                onDateRangeChange={(from, to) => handleFiltersChange({ ...filters, dateFrom: from || undefined, dateTo: to || undefined })}
                tab={tab}
                selectedChuDe={selectedChuDe}
                onChuDeSelect={(cd) => {
                  setSelectedChuDe(cd);
                  setPage(1);
                  setSelectedItem(null);
                  setSidebarOpen(false);
                }}
                collapsed={sidebarCollapsed}
                onToggleCollapse={() => setSidebarCollapsed(c => !c)}
              />
            </div>
          )}

          {/* Divider: Sidebar | DocList */}
          {!isMobile && !sidebarCollapsed && (
            <div className="hidden md:flex h-full flex-shrink-0">
              <Divider onResize={handleSidebarResize} />
            </div>
          )}

          {/* Doc List — hidden on mobile */}
          {!isMobile && (
            <div
              className="relative flex flex-col border-r border-gray-100 bg-gray-50 flex-shrink-0 overflow-hidden"
              style={{ width: listCollapsed ? 0 : listW, minWidth: listCollapsed ? 0 : 200, transition: 'width 0.15s' }}
            >
              {/* Collapse toggle */}
              <button
                onClick={() => setListCollapsed(c => !c)}
                title={listCollapsed ? 'Mở danh sách' : 'Thu gọn danh sách'}
                className="absolute right-0 top-1/2 z-10 bg-white border border-gray-200 rounded-l shadow-sm px-0.5 py-3 hover:bg-gray-50 hover:text-primary transition text-gray-400"
                style={{ transform: 'translateY(-50%) translateX(100%)' }}
              >
                <svg className={`w-3 h-3 transition-transform ${listCollapsed ? 'rotate-180' : ''}`}
                     fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>

              {!listCollapsed && (
                <DocList
                  items={items}
                  total={total}
                  page={page}
                  limit={LIMIT}
                  selectedId={selectedItem?.id ?? null}
                  tab={tab}
                  isLoading={isLoading}
                  onSelect={(item) => setSelectedItem(item)}
                  onPageChange={setPage}
                  isAdmin={auth.user?.role === 'admin'}
                  token={auth.token}
                  onBulkDelete={(ids) => {
                    setPage(1);
                    if (selectedItem && ids.includes(selectedItem.id)) setSelectedItem(null);
                    searchResult.refetch?.();
                    congVanResult.refetch?.();
                  }}
                />
              )}
            </div>
          )}

          {/* Divider: DocList | ContentPanel */}
          {!isMobile && <Divider onResize={handleListResize} />}

          {/* Content Panel + optional Quick AI panel */}
          <div className={`flex flex-1 overflow-hidden ${mobileContentFullscreen ? 'w-full' : ''}`}>
            <ContentPanel
              item={selectedItem}
              tab={tab as 'vanban' | 'congvan'}
              token={auth.token}
              onRequestLogin={requestLogin}
              onBack={mobileContentFullscreen ? () => setSelectedItem(null) : undefined}
            />

            {/* Quick Analysis panel */}
            {showAI && (
              <div className="w-[380px] border-l border-gray-100 bg-white flex flex-col overflow-hidden flex-shrink-0">
                <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50 flex-shrink-0">
                  <span className="text-sm font-semibold text-gray-700">Hỏi AI</span>
                  <button onClick={() => setShowAI(false)} className="text-gray-400 hover:text-gray-600 transition">✕</button>
                </div>
                <div className="flex-1 overflow-hidden p-3">
                  <QuickAnalysis token={auth.token} onRequestLogin={requestLogin} />
                </div>
              </div>
            )}
          </div>

          {/* Mobile: floating DocList button */}
          {isMobile && !mobileContentFullscreen && (
            <button
              onClick={() => setMobileListOpen(true)}
              className="fixed bottom-4 left-4 z-50 bg-primary text-white rounded-full shadow-lg px-4 py-2 text-sm font-medium flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16" />
              </svg>
              {total > 0 ? `${total} kết quả` : 'Danh sách'}
            </button>
          )}

          {/* Mobile: DocList bottom sheet */}
          {isMobile && mobileListOpen && (
            <div className="fixed inset-0 z-50 flex flex-col justify-end">
              <div className="bg-black/40 absolute inset-0" onClick={() => setMobileListOpen(false)} />
              <div className="relative bg-white rounded-t-2xl shadow-2xl flex flex-col" style={{ height: '75vh' }}>
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                  <span className="text-sm font-semibold text-gray-700">
                    {tab === 'vanban' ? 'Văn bản' : 'Công văn'} ({total})
                  </span>
                  <button onClick={() => setMobileListOpen(false)} className="text-gray-400 hover:text-gray-600">✕</button>
                </div>
                <div className="flex-1 overflow-hidden">
                  <DocList
                    items={items}
                    total={total}
                    page={page}
                    limit={LIMIT}
                    selectedId={selectedItem?.id ?? null}
                    tab={tab}
                    isLoading={isLoading}
                    onSelect={(item) => { setSelectedItem(item); setMobileListOpen(false); }}
                    onPageChange={setPage}
                    isAdmin={auth.user?.role === 'admin'}
                    token={auth.token}
                    onBulkDelete={(ids) => {
                      setPage(1);
                      setMobileListOpen(false);
                      if (selectedItem && ids.includes(selectedItem.id)) setSelectedItem(null);
                      searchResult.refetch?.();
                      congVanResult.refetch?.();
                    }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Auth modal */}
      <AuthModal
        open={showAuth}
        onClose={() => setShowAuth(false)}
        onLogin={auth.login}
        onRegister={auth.register}
      />
    </div>
  );
}
