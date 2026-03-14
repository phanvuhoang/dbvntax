#!/usr/bin/env python3
"""
reimport_corpus.py — Migration + reimport vn-tax-corpus vào dbvntax PostgreSQL
1. ALTER TABLE: thêm columns mới (importance, import_date, doc_type, keywords)
2. Xóa 296 docs cũ trong documents table
3. Reimport toàn bộ corpus với metadata đúng
4. CV (t='CV') → cong_van table; còn lại → documents table
"""

import json, re, subprocess, sys
from datetime import datetime

DB_CONTAINER = 'i11456c94loppyu9vzmgyb44'
CORPUS_INDEX = '/tmp/vntaxcorpus/index.json'

# ── Mapping loai ──────────────────────────────────────────────────────────────
TYPE_MAP = {
    'Luật': 'Luat', 'NĐ': 'ND', 'Nghị định': 'ND', 'TT': 'TT',
    'VBHN': 'VBHN', 'QĐ': 'QD', 'NQ': 'NQ', 'CV': 'CV',
    'QTr': 'QD', 'TB': 'Khac', 'CT': 'Khac', 'Khác': 'Khac', '': 'Khac'
}

# Importance mặc định theo loai
IMPORTANCE_MAP = {
    'ND': 1, 'TT': 1,
    'Luat': 2, 'VBHN': 2, 'NQ': 2,
    'QD': 3, 'CV': 4, 'Khac': 3
}

# Mapping tx → sac_thue
TX_MAP = {
    'QLT': 'QLT', 'GTGT': 'GTGT', 'TNDN': 'TNDN', 'TNCN': 'TNCN',
    'TTDB': 'TTDB', 'NhaThau': 'FCT', 'GDLK': 'GDLK', 'HoaDon': 'HOA_DON',
    'HKD': 'HKD', 'TaiNguyen': 'TAI_NGUYEN_DAT', 'TruocBa': 'MON_BAI_PHI',
    'MonBai': 'MON_BAI_PHI', 'PhiBVMT': 'MON_BAI_PHI', 'BVMT': 'MON_BAI_PHI',
    'LoiNhuan': 'TNDN', 'DauTuNN': 'TNDN', 'ODA': 'QLT',
}

# p3 folder → sac_thue fallback
P3_MAP = {
    'LUAT QLT': 'QLT', 'LUAT_QLT': 'QLT',
    'THUE GTGT': 'GTGT', 'THUE_GTGT': 'GTGT',
    'THUE TNDN': 'TNDN', 'THUE_TNDN': 'TNDN',
    'THUE TNCN': 'TNCN', 'THUE_TNCN': 'TNCN',
    'THUE TTDB': 'TTDB', 'THUE_TTDB': 'TTDB',
    'NHA THAU': 'FCT', 'NHA_THAU': 'FCT',
    'GDLK': 'GDLK', 'CHUYEN GIA': 'GDLK',
    'HOA DON': 'HOA_DON', 'HOA_DON': 'HOA_DON',
    'HO KINH DOANH': 'HKD', 'HKD': 'HKD',
    'XUAT NHAP KHAU': 'XNK', 'XNK': 'XNK', 'HAI QUAN': 'XNK',
    'TAI NGUYEN': 'TAI_NGUYEN_DAT', 'TIEN THUE DAT': 'TAI_NGUYEN_DAT',
    'MON BAI': 'MON_BAI_PHI', 'PHI LE PHI': 'MON_BAI_PHI',
}

# Taxonomy classify (inline từ taxonomy.py)
CLASSIFICATION_RULES = {
    "TNDN": ["thu nhập doanh nghiệp", "tndn", "cit", "chi phí được trừ", "ưu đãi thuế",
             "chuyển lỗ", "khấu hao", "quyết toán doanh nghiệp", "ebitda", "lãi vay", "chuyển giá doanh nghiệp"],
    "GTGT": ["giá trị gia tăng", "gtgt", "vat", "hóa đơn đầu vào", "khấu trừ thuế",
             "hoàn thuế gtgt", "thuế suất 0%", "thuế suất 5%", "thuế suất 10%", "giá tính thuế"],
    "TNCN": ["thu nhập cá nhân", "tncn", "pit", "giảm trừ gia cảnh", "quyết toán thuế tncn",
             "người phụ thuộc", "khấu trừ tại nguồn", "lao động nước ngoài", "183 ngày"],
    "TTDB": ["tiêu thụ đặc biệt", "ttđb", "ttdb", "sct", "rượu bia", "thuốc lá", "ô tô chịu thuế"],
    "FCT":  ["nhà thầu nước ngoài", "nhà thầu", "fct", "royalty", "bản quyền", "lãi vay nước ngoài", "thuế nhà thầu"],
    "GDLK": ["giao dịch liên kết", "chuyển giá", "transfer pricing", "apa", "bên liên kết", "nghị định 132", "cbcr"],
    "QLT":  ["quản lý thuế", "kê khai", "nộp thuế", "hoàn thuế", "thanh tra thuế",
             "kiểm tra thuế", "xử phạt", "mã số thuế", "gia hạn nộp thuế", "tiền chậm nộp", "đăng ký thuế"],
    "HOA_DON": ["hóa đơn điện tử", "hđđt", "xuất hóa đơn", "hóa đơn sai sót", "hóa đơn thay thế", "lập hóa đơn"],
    "HKD":  ["hộ kinh doanh", "cá nhân kinh doanh", "thuế khoán", "cho thuê nhà", "cho thuê tài sản", "sàn tmđt"],
    "XNK":  ["xuất nhập khẩu", "hải quan", "nhập khẩu", "xuất khẩu", "mã hs", "thông quan", "xuất xứ", "fta"],
    "TAI_NGUYEN_DAT": ["tài nguyên", "tiền thuê đất", "tiền sử dụng đất", "thuê mặt nước", "khoáng sản", "đất đai"],
    "MON_BAI_PHI": ["môn bài", "lệ phí môn bài", "trước bạ", "phí bảo vệ môi trường", "lệ phí hải quan"],
}

def classify_sac_thue(name, tx, p3):
    # 1. Từ tx field
    if tx and tx in TX_MAP:
        return [TX_MAP[tx]]
    # 2. Từ p3 folder (uppercase compare)
    p3_up = p3.upper() if p3 else ''
    for k, v in P3_MAP.items():
        if k in p3_up:
            return [v]
    # 3. Từ keywords trong name
    text = name.lower()
    result = [code for code, kws in CLASSIFICATION_RULES.items() if any(kw in text for kw in kws)]
    return result if result else ['QLT']

def parse_date(id_val):
    s = str(id_val) if id_val else ''
    if len(s) == 8:
        try:
            y, m, d = s[:4], s[4:6], s[6:]
            if 1990 <= int(y) <= 2030 and 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
                return f'{y}-{m}-{d}'
        except: pass
    elif len(s) == 4 and s.isdigit() and 1990 <= int(s) <= 2030:
        return f'{s}-01-01'
    return None

def extract_so_hieu(name):
    # Pattern: số/năm/loai hoặc số/loai
    m = re.search(r'(\d{1,5}/\d{4}/[\w\-]+|\d{1,5}/[\w\-]+)', name)
    if m:
        return m.group(1)
    # Pattern: "số năm" dạng "5189/TCT-CS (2020)"
    m2 = re.search(r'(\d{1,5}/[\w\-]+)\s*\(', name)
    if m2:
        return m2.group(1)
    return ''

def psql(sql):
    r = subprocess.run(
        ['docker', 'exec', DB_CONTAINER, 'psql', '-U', 'legaldb_user', '-d', 'postgres', '-c', sql],
        capture_output=True, text=True
    )
    if 'ERROR' in r.stderr:
        print(f'  SQL ERR: {r.stderr.strip()[:120]}')
        return False
    return True

def esc(s):
    if s is None: return 'NULL'
    return "'" + str(s).replace("'", "''") + "'"

def arr(lst):
    if not lst: return "'{}'::text[]"
    return "ARRAY[" + ",".join(f"'{x}'" for x in lst) + "]::text[]"

def arr_vc(lst):
    if not lst: return "'{}'::character varying(30)[]"
    return "ARRAY[" + ",".join(f"'{x}'" for x in lst) + "]::character varying(30)[]"

# ── STEP 1: ALTER TABLE ───────────────────────────────────────────────────────
print('='*60)
print('STEP 1: ALTER TABLE — thêm columns mới')
print('='*60)

migrations = [
    # documents table
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS doc_type VARCHAR(10) DEFAULT 'vanban'",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS importance SMALLINT DEFAULT 2",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS import_date TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS keywords TEXT[] DEFAULT '{}'",
    # Fix so_hieu size (hiện VARCHAR(100), cần 200)
    "ALTER TABLE documents ALTER COLUMN so_hieu TYPE VARCHAR(200)",
    # cong_van table
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS doc_type VARCHAR(10) DEFAULT 'congvan'",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS importance SMALLINT DEFAULT 4",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS import_date TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS keywords TEXT[] DEFAULT '{}'",
    "ALTER TABLE cong_van ALTER COLUMN so_hieu TYPE VARCHAR(200)",
    "ALTER TABLE cong_van ALTER COLUMN chu_de TYPE TEXT[]",
    # Update existing GDT records importance
    "UPDATE cong_van SET importance=4, doc_type='congvan' WHERE importance IS NULL OR doc_type IS NULL",
    "UPDATE documents SET doc_type='vanban' WHERE doc_type IS NULL",
]

for sql in migrations:
    ok = psql(sql)
    label = sql[:60] + '...' if len(sql) > 60 else sql
    print(f'  {"✅" if ok else "❌"} {label}')

# ── STEP 2: Xóa 296 docs cũ từ corpus (giữ lại GDT cong_van) ─────────────────
print()
print('='*60)
print('STEP 2: Xóa docs cũ trong documents table')
print('='*60)
psql("DELETE FROM documents")
print('  ✅ Cleared documents table')

# Xóa CV cũ từ corpus nếu có (nguon='corpus')
psql("DELETE FROM cong_van WHERE nguon='corpus'")
print('  ✅ Cleared corpus CVs from cong_van (GDT records kept)')

# ── STEP 3: Load corpus index ─────────────────────────────────────────────────
print()
print('='*60)
print('STEP 3: Reimport từ vn-tax-corpus')
print('='*60)

data = json.load(open(CORPUS_INDEX))
docs = [d for d in data if d.get('p') and d.get('n') != 'EBOOK THUE 2026.htm']
print(f'  Total docs in corpus: {len(docs)}')

# Classify
vanban_count = 0
congvan_count = 0
skip_count = 0
err_count = 0

for d in docs:
    name = d.get('n', '').strip()
    t_raw = d.get('t', '')
    loai = TYPE_MAP.get(t_raw, 'Khac')
    tx = d.get('tx', '')
    p3 = d.get('p3', '')
    id_val = d.get('id', '')
    github_path = d.get('p', '')

    so_hieu = extract_so_hieu(name)
    ngay = parse_date(id_val)
    sac_thue = classify_sac_thue(name, tx, p3)
    importance = IMPORTANCE_MAP.get(loai, 3)
    tinh_trang = 'con_hieu_luc'

    if loai == 'CV':
        # → cong_van table
        co_quan = 'Tổng cục Thuế'
        if '/CT' in so_hieu or 'CT-' in so_hieu:
            co_quan = 'Cục Thuế'
        elif '/BTC' in so_hieu:
            co_quan = 'Bộ Tài chính'

        sql = f"""INSERT INTO cong_van
            (so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, chu_de,
             noi_dung_day_du, nguon, link_nguon, doc_type, importance, import_date, keywords, github_path)
        VALUES (
            {esc(so_hieu or None)}, {esc(name)}, {esc(co_quan)},
            {esc(ngay) + '::date' if ngay else 'NULL'},
            {arr_vc(sac_thue)}, {arr(['Khac'])},
            NULL, 'corpus', {esc(github_path)},
            'congvan', {importance}, NOW(), '{{}}'::text[], {esc(github_path)}
        )"""
        ok = psql(sql)
        if ok: congvan_count += 1
        else: err_count += 1
    else:
        # → documents table
        sql = f"""INSERT INTO documents
            (so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue,
             github_path, doc_type, importance, import_date, keywords)
        VALUES (
            {esc(so_hieu or None)}, {esc(name)}, {esc(loai)},
            {esc(ngay) + '::date' if ngay else 'NULL'},
            {esc(tinh_trang)}, {arr_vc(sac_thue)},
            {esc(github_path)}, 'vanban', {importance}, NOW(), '{{}}'::text[]
        )"""
        ok = psql(sql)
        if ok: vanban_count += 1
        else: err_count += 1

print(f'  ✅ Văn bản imported: {vanban_count}')
print(f'  ✅ Công văn (corpus) imported: {congvan_count}')
print(f'  ❌ Errors: {err_count}')

# ── STEP 4: Stats ─────────────────────────────────────────────────────────────
print()
print('='*60)
print('STEP 4: Final stats')
print('='*60)

r = subprocess.run(
    ['docker', 'exec', DB_CONTAINER, 'psql', '-U', 'legaldb_user', '-d', 'postgres',
     '-c', """
SELECT 'documents' as tbl, loai, importance, COUNT(*) cnt
FROM documents GROUP BY loai, importance ORDER BY loai, importance
UNION ALL
SELECT 'cong_van', nguon, importance::text, COUNT(*)
FROM cong_van GROUP BY nguon, importance ORDER BY 1,2,3;
"""],
    capture_output=True, text=True
)
print(r.stdout)
