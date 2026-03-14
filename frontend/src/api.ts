import { useQuery } from '@tanstack/react-query';
import type {
  SearchResponse,
  CongVanResponse,
  Document,
  CongVan,
  HealthResponse,
  Category,
} from './types';

const BASE = '';

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE}${url}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// Search documents
export interface SearchParams {
  q?: string;
  type?: string;
  sac_thue?: string;
  loai?: string;
  year_from?: number;
  year_to?: number;
  tinh_trang?: string;
  hl?: number;
  date_at?: string;
  mode?: string;
  limit?: number;
  offset?: number;
}

function buildSearchURL(params: SearchParams): string {
  const p = new URLSearchParams();
  if (params.q) p.set('q', params.q);
  if (params.type && params.type !== 'all') p.set('type', params.type);
  if (params.sac_thue) p.set('sac_thue', params.sac_thue);
  if (params.loai) p.set('loai', params.loai);
  if (params.year_from) p.set('year_from', String(params.year_from));
  if (params.year_to) p.set('year_to', String(params.year_to));
  if (params.tinh_trang) p.set('tinh_trang', params.tinh_trang);
  if (params.hl !== undefined) p.set('hl', String(params.hl));
  if (params.date_at) p.set('date_at', params.date_at);
  if (params.mode) p.set('mode', params.mode);
  p.set('limit', String(params.limit ?? 20));
  p.set('offset', String(params.offset ?? 0));
  return `/api/search?${p}`;
}

export function useSearch(params: SearchParams) {
  return useQuery<SearchResponse>({
    queryKey: ['search', params],
    queryFn: () => fetchJSON<SearchResponse>(buildSearchURL(params)),
  });
}

// Document detail
export function useDocumentDetail(id: number | null) {
  return useQuery<Document>({
    queryKey: ['document', id],
    queryFn: () => fetchJSON<Document>(`/api/documents/${id}`),
    enabled: id !== null,
  });
}

// Cong van list
export interface CongVanParams {
  q?: string;
  sac_thue?: string;
  limit?: number;
  offset?: number;
}

function buildCongVanURL(params: CongVanParams): string {
  const p = new URLSearchParams();
  if (params.q) p.set('q', params.q);
  if (params.sac_thue) p.set('sac_thue', params.sac_thue);
  p.set('limit', String(params.limit ?? 20));
  p.set('offset', String(params.offset ?? 0));
  return `/api/cong-van?${p}`;
}

export function useCongVan(params: CongVanParams) {
  return useQuery<CongVanResponse>({
    queryKey: ['cong-van', params],
    queryFn: () => fetchJSON<CongVanResponse>(buildCongVanURL(params)),
  });
}

// Cong van detail
export function useCongVanDetail(id: number | null) {
  return useQuery<CongVan>({
    queryKey: ['cong-van-detail', id],
    queryFn: () => fetchJSON<CongVan>(`/api/cong_van/${id}`),
    enabled: id !== null,
  });
}

// Health / stats
export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: () => fetchJSON<HealthResponse>('/health'),
    staleTime: 300_000,
  });
}

// Categories
export function useCategories() {
  return useQuery<Category[]>({
    queryKey: ['categories'],
    queryFn: () => fetchJSON<Category[]>('/api/categories'),
    staleTime: 300_000,
  });
}

// Format date DD/MM/YYYY
export function formatDate(d: string | null | undefined): string {
  if (!d) return '';
  try {
    const parts = String(d).split('-');
    if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
    return d;
  } catch {
    return d;
  }
}
