#!/usr/bin/env python3
"""
sync_corpus.py — Sync vn-tax-corpus → dbvntax PostgreSQL
Mode: UPSERT (không xóa, chỉ insert mới hoặc update nếu có thay đổi)

Usage:
  python3 sync_corpus.py              # full sync
  python3 sync_corpus.py --dry-run    # chỉ in, không write DB
  python3 sync_corpus.py --since 7    # chỉ docs thay đổi trong 7 ngày (git log)

Chạy từ VPS (cần docker exec quyền vào container DB).
Source: github.com/phanvuhoang/vn-tax-corpus (clone/pull vào /tmp/vntaxcorpus)
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


# ── HTML → plain text ─────────────────────────────────────────────────────────
class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'header', 'footer'):
            self._skip = True
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'header', 'footer'):
            self._skip = False
    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

def html_to_text(html: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    return re.sub(r'\s+', ' ', ' '.join(p._text)).strip()

def read_html_content(github_path: str) -> str:
    """Đọc HTML file từ corpus và convert sang plain text."""
    fpath = Path(CORPUS_DIR) / 'docs' / github_path
    if not fpath.exists():
        return ''
    try:
        html = fpath.read_text(encoding='utf-8', errors='ignore')
        return html_to_text(html)
    except Exception:
        return ''

# ── Config ────────────────────────────────────────────────────────────────────
DB_CONTAINER  = 'i11456c94loppyu9vzmgyb44'
CORPUS_DIR    = '/tmp/vntaxcorpus'
CORPUS_REPO   = 'https://github.com/phanvuhoang/vn-tax-corpus'
CORPUS_INDEX  = f'{CORPUS_DIR}/index.json'
TELEGRAM_TOKEN = ''   # optional — set nếu muốn notify
TELEGRAM_CHAT  = ''

# ── Mappings ──────────────────────────────────────────────────────────────────
TYPE_MAP = {
    'Luật': 'Luat', 'NĐ': 'ND', 'Nghị định': 'ND', 'TT': 'TT',
    'VBHN': 'VBHN', 'QĐ': 'QD', 'NQ': 'NQ', 'CV': 'CV',
    'QTr': 'QD', 'TB': 'Khac', 'CT': 'Khac', 'Khác': 'Khac', '': 'Khac'
}
IMPORTANCE_MAP = {
    'ND': 1, 'TT': 1, 'Luat': 2, 'VBHN': 2, 'NQ': 2, 'QD': 3, 'CV': 4, 'Khac': 3
}
TX_MAP = {
    'QLT': 'QLT', 'GTGT': 'GTGT', 'TNDN': 'TNDN', 'TNCN': 'TNCN',
    'TTDB': 'TTDB', 'NhaThau': 'FCT', 'GDLK': 'GDLK', 'HoaDon': 'HOA_DON',
    'HKD': 'HKD', 'TaiNguyen': 'TAI_NGUYEN_DAT', 'TruocBa': 'MON_BAI_PHI',
    'MonBai': 'MON_BAI_PHI', 'PhiBVMT': 'MON_BAI_PHI', 'BVMT': 'MON_BAI_PHI',
    'LoiNhuan': 'TNDN', 'DauTuNN': 'TNDN', 'ODA': 'QLT',
}
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
CLASSIFICATION_RULES = {
    'TNDN': ['thu nhập doanh nghiệp','tndn','cit','chi phí được trừ','ưu đãi thuế','khấu hao','ebitda','lãi vay'],
    'GTGT': ['giá trị gia tăng','gtgt','vat','hoàn thuế gtgt','khấu trừ thuế','thuế suất 0%','thuế suất 5%','thuế suất 10%'],
    'TNCN': ['thu nhập cá nhân','tncn','pit','giảm trừ gia cảnh','quyết toán thuế tncn','người phụ thuộc','183 ngày'],
    'TTDB': ['tiêu thụ đặc biệt','ttđb','ttdb','sct','rượu bia','thuốc lá'],
    'FCT':  ['nhà thầu nước ngoài','nhà thầu','fct','royalty','bản quyền','lãi vay nước ngoài'],
    'GDLK': ['giao dịch liên kết','chuyển giá','transfer pricing','bên liên kết','nghị định 132','cbcr'],
    'QLT':  ['quản lý thuế','kê khai','nộp thuế','hoàn thuế','thanh tra thuế','kiểm tra thuế','xử phạt','mã số thuế','gia hạn nộp thuế','tiền chậm nộp'],
    'HOA_DON': ['hóa đơn điện tử','hđđt','xuất hóa đơn','hóa đơn sai sót','hóa đơn thay thế'],
    'HKD':  ['hộ kinh doanh','cá nhân kinh doanh','thuế khoán','cho thuê nhà','sàn tmđt'],
    'XNK':  ['xuất nhập khẩu','hải quan','nhập khẩu','xuất khẩu','mã hs','thông quan','xuất xứ','fta'],
    'TAI_NGUYEN_DAT': ['tài nguyên','tiền thuê đất','tiền sử dụng đất','thuê mặt nước','khoáng sản','đất đai'],
    'MON_BAI_PHI': ['môn bài','lệ phí môn bài','trước bạ','phí bảo vệ môi trường','lệ phí hải quan'],
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def classify_sac_thue(name, tx, p3):
    if tx and tx in TX_MAP:
        return [TX_MAP[tx]]
    p3_up = (p3 or '').upper()
    for k, v in P3_MAP.items():
        if k in p3_up:
            return [v]
    text = name.lower()
    result = [code for code, kws in CLASSIFICATION_RULES.items() if any(kw in text for kw in kws)]
    return result if result else ['QLT']

def parse_date(id_val):
    """Parse YYYYMMDD → YYYY-MM-DD. Returns None if invalid."""
    s = str(id_val) if id_val else ''
    if len(s) == 8:
        try:
            y, m, d = s[:4], s[4:6], s[6:]
            if 1990 <= int(y) <= 2030 and 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
                return f'{y}-{m}-{d}'
        except Exception:
            pass
    return None

def extract_so_hieu(name):
    m = re.search(r'(\d{1,5}/\d{4}/[\w\-]+|\d{1,5}/[\w\-]+)', name)
    if m:
        return m.group(1)
    m2 = re.search(r'(\d{1,5}/[\w\-]+)\s*\(', name)
    if m2:
        return m2.group(1)
    return ''

def esc(s):
    if s is None:
        return 'NULL'
    return "'" + str(s).replace("'", "''") + "'"

def pg_arr(lst, cast='character varying(30)'):
    if not lst:
        return f"ARRAY[]::varchar[]"
    vals = ','.join(f"'{x}'" for x in lst)
    return f'ARRAY[{vals}]::{cast}[]'

def pg_text_arr(lst):
    if not lst:
        return "'{}'::text[]"
    vals = ','.join(f"'{x}'" for x in lst)
    return f'ARRAY[{vals}]::text[]'

def psql(sql, dry_run=False):
    if dry_run:
        return True, ''
    r = subprocess.run(
        ['docker', 'exec', DB_CONTAINER,
         'psql', '-U', 'legaldb_user', '-d', 'postgres', '-c', sql],
        capture_output=True, text=True
    )
    has_error = 'ERROR' in r.stderr and 'NOTICE' not in r.stderr
    return not has_error, r.stderr.strip()[:120]

# ── Git helpers ───────────────────────────────────────────────────────────────
def git_pull_or_clone():
    import os
    if os.path.exists(f'{CORPUS_DIR}/.git'):
        r = subprocess.run(['git', '-C', CORPUS_DIR, 'pull', '--ff-only'],
                           capture_output=True, text=True)
        print(f'  git pull: {r.stdout.strip() or r.stderr.strip()}')
        return True
    else:
        print(f'  Cloning {CORPUS_REPO} ...')
        r = subprocess.run(['git', 'clone', '--depth=1', CORPUS_REPO, CORPUS_DIR],
                           capture_output=True, text=True)
        print(f'  {r.stdout.strip() or r.stderr.strip()}')
        return r.returncode == 0

def get_changed_paths(since_days):
    """Return set of file paths changed in last N days in corpus."""
    r = subprocess.run(
        ['git', '-C', CORPUS_DIR, 'log', f'--since={since_days} days ago',
         '--name-only', '--pretty=format:'],
        capture_output=True, text=True
    )
    paths = {line.strip() for line in r.stdout.splitlines() if line.strip()}
    return paths

# ── Main sync ─────────────────────────────────────────────────────────────────
def sync(dry_run=False, since_days=None):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f'\n{"="*60}')
    print(f'vn-tax-corpus sync — {now}')
    print(f'dry_run={dry_run}, since_days={since_days}')
    print(f'{"="*60}')

    # 1. Pull latest corpus
    print('\n[1] Git pull corpus...')
    if not git_pull_or_clone():
        print('  ERROR: git failed, aborting')
        sys.exit(1)

    # 2. Load index
    print('\n[2] Load index.json...')
    data = json.load(open(CORPUS_INDEX))
    docs = [d for d in data if d.get('p') and d.get('n') != 'EBOOK THUE 2026.htm']
    print(f'  Total in corpus: {len(docs)}')

    # 3. Filter by changed paths if --since
    if since_days:
        changed = get_changed_paths(since_days)
        if changed:
            docs = [d for d in docs if d.get('p') in changed or d.get('fn') in changed]
            print(f'  Filtered to {len(docs)} changed docs (last {since_days} days)')
        else:
            print(f'  No changes in last {since_days} days — nothing to sync')
            return {'docs_upserted': 0, 'cvs_upserted': 0, 'errors': 0}

    # 4. Upsert
    print('\n[3] Upserting...')
    doc_ok = doc_err = cv_ok = cv_err = 0

    for d in docs:
        name      = (d.get('n') or '').strip()
        t_raw     = d.get('t', '')
        loai      = TYPE_MAP.get(t_raw, 'Khac')
        tx        = d.get('tx', '')
        p3        = d.get('p3', '')
        id_val    = d.get('id', '')
        github_p  = d.get('p', '')

        so_hieu   = extract_so_hieu(name) or None
        ngay      = parse_date(id_val)
        sac_thue  = classify_sac_thue(name, tx, p3)
        importance = IMPORTANCE_MAP.get(loai, 3)

        ngay_sql  = esc(ngay) + '::date' if ngay else 'NULL'

        if loai == 'CV':
            # → cong_van table, upsert by github_path
            co_quan = 'Cục Thuế' if '/CT' in (so_hieu or '') else 'Tổng cục Thuế'
            sql = f"""
INSERT INTO cong_van
    (so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, chu_de,
     nguon, link_nguon, github_path, doc_type, importance, import_date, keywords)
VALUES
    ({esc(so_hieu)}, {esc(name)}, {esc(co_quan)}, {ngay_sql},
     {pg_arr(sac_thue)}, {pg_text_arr(['Khac'])},
     'corpus', {esc(github_p)}, {esc(github_p)},
     'congvan', {importance}, NOW(), '{{}}'::text[])
ON CONFLICT (link_nguon) DO UPDATE SET
    so_hieu       = EXCLUDED.so_hieu,
    ten           = EXCLUDED.ten,
    co_quan       = EXCLUDED.co_quan,
    ngay_ban_hanh = EXCLUDED.ngay_ban_hanh,
    sac_thue      = EXCLUDED.sac_thue,
    importance    = CASE WHEN cong_van.importance = 4 THEN EXCLUDED.importance
                         ELSE cong_van.importance END
"""
            ok, err = psql(sql, dry_run)
            if ok: cv_ok += 1
            else:  cv_err += 1; print(f'  CV ERR: {name[:50]} | {err}')
        else:
            # → documents table, upsert by github_path
            noi_dung = read_html_content(github_p) if not dry_run else ''
            sql = f"""
INSERT INTO documents
    (so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue,
     github_path, doc_type, importance, import_date, keywords, noi_dung)
VALUES
    ({esc(so_hieu)}, {esc(name)}, {esc(loai)}, {ngay_sql},
     'con_hieu_luc', {pg_arr(sac_thue)},
     {esc(github_p)}, 'vanban', {importance}, NOW(), '{{}}'::text[], {esc(noi_dung)})
ON CONFLICT (github_path) DO UPDATE SET
    so_hieu       = EXCLUDED.so_hieu,
    ten           = EXCLUDED.ten,
    loai          = EXCLUDED.loai,
    ngay_ban_hanh = EXCLUDED.ngay_ban_hanh,
    sac_thue      = EXCLUDED.sac_thue,
    importance    = CASE WHEN documents.importance = EXCLUDED.importance THEN documents.importance
                         ELSE EXCLUDED.importance END,
    noi_dung      = CASE WHEN (documents.noi_dung IS NULL OR documents.noi_dung = '')
                         THEN EXCLUDED.noi_dung
                         ELSE documents.noi_dung END
"""
            ok, err = psql(sql, dry_run)
            if ok: doc_ok += 1
            else:  doc_err += 1; print(f'  DOC ERR: {name[:50]} | {err}')

    result = {'docs_upserted': doc_ok, 'cvs_upserted': cv_ok,
              'errors': doc_err + cv_err}

    print(f'\n[4] Results:')
    print(f'  documents upserted : {doc_ok}  errors: {doc_err}')
    print(f'  cong_van  upserted : {cv_ok}   errors: {cv_err}')

    if not dry_run:
        # Final counts
        r = subprocess.run(
            ['docker', 'exec', DB_CONTAINER,
             'psql', '-U', 'legaldb_user', '-d', 'postgres', '-c',
             "SELECT 'documents' tbl, COUNT(*) FROM documents "
             "UNION ALL SELECT 'cong_van', COUNT(*) FROM cong_van;"],
            capture_output=True, text=True)
        print(f'\n{r.stdout}')

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--since', type=int, default=None,
                        help='Only sync docs changed in last N days')
    args = parser.parse_args()
    sync(dry_run=args.dry_run, since_days=args.since)
