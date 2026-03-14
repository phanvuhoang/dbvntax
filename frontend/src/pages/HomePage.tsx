import { useState, useCallback } from 'react';
import type { Document, CongVan } from '../types';
import { useSearch, useCongVan, useHealth } from '../api';
import Sidebar from '../components/Sidebar';
import SearchBar from '../components/SearchBar';
import DocList from '../components/DocList';
import DocDetail from '../components/DocDetail';

type Tab = 'vanban' | 'congvan';

const LIMIT = 20;

export default function HomePage() {
  const [tab, setTab] = useState<Tab>('vanban');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(1);
  const [loai, setLoai] = useState('');
  const [hlFilter, setHlFilter] = useState('');
  const [dateAt, setDateAt] = useState('');
  const [selectedItem, setSelectedItem] = useState<Document | CongVan | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { data: health } = useHealth();

  // Search documents
  const searchResult = useSearch({
    q: query,
    sac_thue: category,
    loai,
    tinh_trang: hlFilter,
    date_at: dateAt || undefined,
    mode: 'hybrid',
    limit: LIMIT,
    offset: (page - 1) * LIMIT,
  });

  // Cong van
  const congVanResult = useCongVan({
    q: query,
    sac_thue: category,
    limit: LIMIT,
    offset: (page - 1) * LIMIT,
  });

  const items = tab === 'vanban'
    ? (searchResult.data?.results ?? [])
    : (congVanResult.data?.results ?? []);
  const total = tab === 'vanban'
    ? (searchResult.data?.total ?? 0)
    : (congVanResult.data?.total ?? 0);
  const isLoading = tab === 'vanban' ? searchResult.isLoading : congVanResult.isLoading;

  const handleSearch = useCallback((q: string) => {
    setQuery(q);
    setPage(1);
    setSelectedItem(null);
  }, []);

  const handleCategorySelect = useCallback((code: string) => {
    setCategory(code);
    setPage(1);
    setSelectedItem(null);
  }, []);

  const handleTabChange = useCallback((t: Tab) => {
    setTab(t);
    setPage(1);
    setSelectedItem(null);
  }, []);

  const resetPage = useCallback(() => setPage(1), []);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 flex-shrink-0">
        <div className="flex items-center gap-3 px-4 h-12">
          {/* Mobile sidebar toggle */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="md:hidden text-gray-500 hover:text-primary"
            aria-label="Toggle sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Logo */}
          <span className="text-lg font-bold text-primary whitespace-nowrap tracking-tight">
            VNTaxDB
          </span>

          {/* Tabs */}
          <div className="flex gap-0.5">
            <button
              onClick={() => handleTabChange('vanban')}
              className={`px-3 py-1.5 text-sm font-medium rounded-t transition
                ${tab === 'vanban'
                  ? 'text-primary border-b-2 border-primary bg-primary-light'
                  : 'text-gray-500 hover:text-primary hover:bg-primary-light'}`}
            >
              Văn bản
            </button>
            <button
              onClick={() => handleTabChange('congvan')}
              className={`px-3 py-1.5 text-sm font-medium rounded-t transition
                ${tab === 'congvan'
                  ? 'text-primary border-b-2 border-primary bg-primary-light'
                  : 'text-gray-500 hover:text-primary hover:bg-primary-light'}`}
            >
              Công văn
            </button>
          </div>

          {/* Stats */}
          {health && (
            <span className="ml-auto text-xs text-gray-400 hidden sm:block">
              {health.documents} văn bản · {health.cong_van} công văn
            </span>
          )}
        </div>

        {/* Search */}
        <div className="px-4 py-1.5">
          <SearchBar value={query} onChange={handleSearch} />
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Mobile sidebar overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/30 z-30 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar — always visible on md+, slide-in on mobile */}
        <div className={`${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 transition-transform duration-200 fixed md:static z-40 md:z-auto h-full`}>
          <Sidebar
            selected={category}
            onSelect={(code) => { handleCategorySelect(code); setSidebarOpen(false); }}
            loai={loai}
            onLoaiChange={(v) => { setLoai(v); resetPage(); }}
            hlFilter={hlFilter}
            onHlChange={(v) => { setHlFilter(v); resetPage(); }}
            dateAt={dateAt}
            onDateAtChange={(v) => { setDateAt(v); resetPage(); }}
          />
        </div>

        {/* Doc List */}
        <div className="w-[340px] min-w-[220px] flex flex-col border-r border-gray-200 bg-gray-50 flex-shrink-0 overflow-hidden">
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

        {/* Detail Panel */}
        <DocDetail
          item={selectedItem}
          tab={tab}
          onClose={() => setSelectedItem(null)}
        />
      </div>
    </div>
  );
}
