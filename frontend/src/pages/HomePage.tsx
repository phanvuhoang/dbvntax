import { useState, useCallback, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { Document, CongVan } from '../types';
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

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return isMobile;
}

export default function HomePage() {
  const [tab, setTab] = useState<Tab>('vanban');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(1);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [selectedItem, setSelectedItem] = useState<Document | CongVan | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [showAI, setShowAI] = useState(false);
  const [selectedChuDe, setSelectedChuDe] = useState('');

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

  const searchResult = useSearch({
    q: query,
    sac_thue: category ? (CATEGORY_TO_DB[category] ?? category) : undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    mode: 'hybrid',
    limit: LIMIT,
    offset: (page - 1) * LIMIT,
  });

  const congVanResult = useCongVan({
    q: query,
    sac_thue: category ? (CATEGORY_TO_DB[category] ?? category) : undefined,
    chu_de: selectedChuDe,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
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

  const handleDateRangeChange = useCallback((from: string, to: string) => {
    setDateFrom(from); setDateTo(to); setPage(1);
  }, []);

  const requestLogin = useCallback(() => setShowAuth(true), []);

  const handleSidebarResize = useCallback((dx: number) => {
    setSidebarW((w) => Math.max(140, Math.min(400, w + dx)));
  }, []);

  const handleListResize = useCallback((dx: number) => {
    setListW((w) => Math.max(200, Math.min(500, w + dx)));
  }, []);

  // Mobile: when item selected, show fullscreen content
  const mobileContentFullscreen = isMobile && selectedItem !== null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 flex-shrink-0">
        <div className="flex items-center gap-3 px-4 h-12">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="md:hidden text-gray-500 hover:text-primary" aria-label="Menu">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <span className="text-lg font-bold text-primary whitespace-nowrap tracking-tight">⚖️ VNTaxDB</span>

          <div className="flex gap-0.5">
            {([
              ['vanban', 'Văn bản'],
              ['congvan', 'Công văn'],
              ['ask_ai', '🤖 Hỏi đáp AI'],
            ] as const).map(([t, label]) => (
              <button
                key={t}
                onClick={() => handleTabChange(t)}
                className={`px-3 py-1.5 text-sm font-medium rounded-t transition ${
                  tab === t
                    ? 'text-primary border-b-2 border-primary bg-primary-light'
                    : 'text-gray-500 hover:text-primary hover:bg-primary-light'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {health && (
            <span className="ml-auto text-xs text-gray-400 hidden sm:block">
              {health.documents} văn bản · {health.cong_van} công văn · {health.articles} bài viết
            </span>
          )}

          {/* AI button */}
          <button
            onClick={() => setShowAI(!showAI)}
            className={`px-3 py-1.5 text-sm font-medium rounded transition hidden sm:block ${
              showAI ? 'bg-primary text-white' : 'text-gray-500 hover:text-primary hover:bg-primary-light'
            }`}
          >
            🤖 Hỏi AI
          </button>

          {/* Admin button */}
          {auth.user?.role === 'admin' && (
            <button
              onClick={() => navigate('/admin')}
              className="px-3 py-1.5 text-sm font-medium rounded transition text-gray-500 hover:text-primary hover:bg-primary-light hidden sm:block"
            >
              ⚙️ Admin
            </button>
          )}

          {/* Auth */}
          <div className="flex items-center gap-2">
            {auth.isLoggedIn ? (
              <>
                <span className="text-xs text-primary font-medium hidden sm:block">
                  {auth.user?.ho_ten || auth.user?.email}
                </span>
                <button
                  onClick={auth.logout}
                  className="px-3 py-1 text-xs border border-gray-300 rounded text-gray-500 hover:border-primary hover:text-primary transition"
                >
                  Đăng xuất
                </button>
              </>
            ) : (
              <button
                onClick={() => setShowAuth(true)}
                className="px-3 py-1.5 text-sm bg-primary text-white rounded hover:bg-primary-dark transition"
              >
                Đăng nhập
              </button>
            )}
          </div>
        </div>

        <div className="px-4 py-1.5">
          <SearchBar value={query} onChange={handleSearch} />
        </div>
      </header>

      {/* Ask AI tab — full content area */}
      {tab === 'ask_ai' && (
        <div className="flex flex-1 overflow-hidden">
          <AskAIPage />
        </div>
      )}

      {/* Main Content — 3-panel layout (vanban / congvan tabs) */}
      {tab !== 'ask_ai' && <div className="flex flex-1 overflow-hidden relative select-none">
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
              dateFrom={dateFrom}
              dateTo={dateTo}
              onDateRangeChange={handleDateRangeChange}
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

        {/* Divider: Sidebar | DocList — hidden on mobile or when sidebar collapsed */}
        {!isMobile && !sidebarCollapsed && (
          <div className="hidden md:flex h-full flex-shrink-0">
            <Divider onResize={handleSidebarResize} />
          </div>
        )}

        {/* Doc List — hidden on mobile (replaced by bottom sheet) */}
        {!isMobile && (
          <div
            className="relative flex flex-col border-r border-gray-200 bg-gray-50 flex-shrink-0 overflow-hidden"
            style={{ width: listCollapsed ? 0 : listW, minWidth: listCollapsed ? 0 : 200, transition: 'width 0.15s' }}
          >
            {/* Collapse toggle button — floats on right edge */}
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

        {/* Divider: DocList | ContentPanel — hidden on mobile */}
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
            <div className="w-[380px] border-l border-gray-200 bg-white flex flex-col overflow-hidden flex-shrink-0">
              <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50 flex-shrink-0">
                <span className="text-sm font-semibold text-gray-700">Hỏi AI</span>
                <button onClick={() => setShowAI(false)} className="text-gray-400 hover:text-gray-600">✕</button>
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
            <div className="relative bg-white rounded-t-2xl shadow-2xl flex flex-col" style={{ height: '70vh' }}>
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
      </div>}

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
