import { useState, useCallback } from 'react';
import type { Document, CongVan } from '../types';
import { useSearch, useCongVan, useHealth } from '../api';
import { useAuth } from '../auth';
import Sidebar from '../components/Sidebar';
import SearchBar from '../components/SearchBar';
import DocList from '../components/DocList';
import ContentPanel from '../components/ContentPanel';
import AuthModal from '../components/AuthModal';
import QuickAnalysis from '../components/QuickAnalysis';
import Divider from '../components/Divider';

type Tab = 'vanban' | 'congvan';

const LIMIT = 20;

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

  const auth = useAuth();
  const { data: health } = useHealth();

  const searchResult = useSearch({
    q: query,
    sac_thue: category,
    year_from: dateFrom ? parseInt(dateFrom.split('-')[0]) : undefined,
    year_to: dateTo ? parseInt(dateTo.split('-')[0]) : undefined,
    mode: 'hybrid',
    limit: LIMIT,
    offset: (page - 1) * LIMIT,
  });

  const congVanResult = useCongVan({
    q: query,
    sac_thue: category,
    chu_de: selectedChuDe,
    year_from: dateFrom ? parseInt(dateFrom.split('-')[0]) : undefined,
    year_to: dateTo ? parseInt(dateTo.split('-')[0]) : undefined,
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
    setSelectedChuDe('');
    setCategory('');  // reset category khi đổi tab (tránh mismatch CIT vs TNDN)
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
            {(['vanban', 'congvan'] as const).map((t) => (
              <button
                key={t}
                onClick={() => handleTabChange(t)}
                className={`px-3 py-1.5 text-sm font-medium rounded-t transition ${
                  tab === t
                    ? 'text-primary border-b-2 border-primary bg-primary-light'
                    : 'text-gray-500 hover:text-primary hover:bg-primary-light'
                }`}
              >
                {t === 'vanban' ? 'Văn bản' : 'Công văn'}
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

      {/* Main Content — 3-panel resizable layout */}
      <div className="flex flex-1 overflow-hidden relative select-none">
        {sidebarOpen && (
          <div className="fixed inset-0 bg-black/30 z-30 md:hidden" onClick={() => setSidebarOpen(false)} />
        )}

        {/* Sidebar */}
        <div
          className={`${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 transition-transform duration-200 fixed md:static z-40 md:z-auto h-full flex-shrink-0`}
          style={{ width: sidebarW }}
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
          />
        </div>

        {/* Divider: Sidebar | DocList */}
        <div className="hidden md:flex h-full flex-shrink-0">
          <Divider onResize={handleSidebarResize} />
        </div>

        {/* Doc List */}
        <div
          className="flex flex-col border-r border-gray-200 bg-gray-50 flex-shrink-0 overflow-hidden"
          style={{ width: listW, minWidth: 200 }}
        >
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
          />
        </div>

        {/* Divider: DocList | ContentPanel */}
        <Divider onResize={handleListResize} />

        {/* Content Panel + optional Quick AI panel */}
        <div className="flex flex-1 overflow-hidden">
          <ContentPanel
            item={selectedItem}
            tab={tab}
            token={auth.token}
            onRequestLogin={requestLogin}
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
      </div>

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
