export interface HieuLucEntry {
  pham_vi: string;
  tu_ngay: string | null;
  den_ngay: string | null;
  ghi_chu: string;
}

export interface HieuLucIndex {
  hieu_luc: HieuLucEntry[];
  van_ban_thay_the: string[];
  van_ban_sua_doi: string[];
  tom_tat_hieu_luc: string;
}

export interface Document {
  id: number;
  so_hieu: string;
  ten: string;
  loai: string;
  ngay_ban_hanh: string;
  tinh_trang: string;
  hl?: number;
  sac_thue: string[];
  category_name?: string;
  github_path?: string;
  snippet?: string;
  source?: string;
  score?: number;
  hieu_luc_index?: HieuLucIndex;
  noi_dung?: string;
  tom_tat?: string;
  keywords?: string[];
  p2?: string;
  p3?: string;
  doc_type?: string;
  importance?: number;
}

export interface CongVan {
  id: number;
  so_hieu: string;
  ten: string;
  co_quan?: string;
  ngay_ban_hanh: string;
  sac_thue: string[];
  nguon?: string;
  link_nguon?: string;
  tom_tat?: string;
  ket_luan?: string;
  noi_dung_day_du?: string;
}

export interface Category {
  code: string;
  name: string;
  count: number;
}

export interface SearchResponse {
  total: number;
  results: Document[];
  q: string;
  mode: string;
}

export interface CongVanResponse {
  total: number;
  items: CongVan[];
}

export interface HealthResponse {
  status: string;
  documents: number;
  cong_van: number;
  articles: number;
}

export type HieuLucStatus = 'active' | 'inactive' | 'partial';

export const CATEGORIES = [
  { code: 'QLT', name: 'Quản lý thuế', color: 'blue' },
  { code: 'CIT', name: 'Thuế TNDN', color: 'green' },
  { code: 'VAT', name: 'Thuế GTGT', color: 'teal' },
  { code: 'HDDT', name: 'Hóa đơn điện tử', color: 'purple' },
  { code: 'PIT', name: 'Thuế TNCN', color: 'orange' },
  { code: 'SCT', name: 'Thuế TTĐB', color: 'red' },
  { code: 'FCT', name: 'Thuế nhà thầu', color: 'yellow' },
  { code: 'TP', name: 'Giao dịch liên kết', color: 'indigo' },
  { code: 'HKD', name: 'Hộ kinh doanh', color: 'pink' },
] as const;

export const LOAI_LABELS: Record<string, string> = {
  LUAT: 'Luật',
  ND: 'Nghị định',
  TT: 'Thông tư',
  QD: 'Quyết định',
  NQ: 'Nghị quyết',
  VBHN: 'VB Hợp nhất',
  TTLT: 'Thông tư liên tịch',
  CV: 'Công văn',
  KHAC: 'Khác',
};

export const SAC_THUE_MAP: Record<string, string> = {
  QLT: 'Quản lý thuế',
  CIT: 'Thuế TNDN',
  TNDN: 'Thuế TNDN',
  VAT: 'Thuế GTGT',
  GTGT: 'Thuế GTGT',
  HDDT: 'Hóa đơn điện tử',
  HOA_DON: 'Hóa đơn',
  PIT: 'Thuế TNCN',
  TNCN: 'Thuế TNCN',
  SCT: 'Thuế TTĐB',
  TTDB: 'Thuế TTĐB',
  FCT: 'Thuế nhà thầu',
  NHA_THAU: 'Nhà thầu',
  TP: 'Giao dịch LK',
  GDLK: 'Giao dịch LK',
  HKD: 'Hộ KD',
};
