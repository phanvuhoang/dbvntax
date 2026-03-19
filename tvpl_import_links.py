#!/usr/bin/env python3
"""
tvpl_import_links.py — Import công văn từ danh sách TVPL links vào PostgreSQL

Kiến trúc 2-phase (do TVPL block VPS Hostinger):
  Phase 1 (OpenClaw): Fetch HTML + parse → save /tmp/tvpl_batch_YYYYMMDD_HHMMSS.json
  Phase 2 (VPS):      Load JSON → insert vào PostgreSQL

Usage:
    # Phase 1 - chạy trên OpenClaw container (fetch HTML)
    python3 tvpl_import_links.py fetch --inline URL1 URL2 ...
    python3 tvpl_import_links.py fetch --links links.txt
    python3 tvpl_import_links.py fetch --inline URL1 URL2 ... --out /tmp/batch.json

    # Phase 2 - chạy trên VPS (insert DB)
    python3 tvpl_import_links.py insert --json /tmp/tvpl_batch_*.json

    # Dry run (fetch only, no save)
    python3 tvpl_import_links.py fetch --inline URL1 --dry-run
"""

import argparse
import re
import time
import urllib.request
import urllib.error
import json
import sys
import os
from datetime import datetime

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# ─── DB config ───────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "10.0.1.11",
    "port": 5432,
    "database": "postgres",
    "user": "legaldb_user",
    "password": "PbSV8bfxQdta4ljBsDVtZEe74yjMG6l7uW3dSczT8Iaajm9MKX07wHqyf0xBTTMF",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

# ─── Sắc thuế & Chu đề classification ───────────────────────────────────────
# Mỗi rule: (keywords, sac_thue_code)
# Một CV có thể match NHIỀU rules → trả list
SAC_THUE_RULES = [
    (["gtgt", "gia tri gia tang", "vat", "thue suat gtgt", "hoan thue gtgt", "khau tru thue"], "GTGT"),
    (["tndn", "thu nhap doanh nghiep", "cit", "uu dai thue tndn", "mien thue tndn", "chi phi duoc tru"], "TNDN"),
    (["tncn", "thu nhap ca nhan", "pit", "tien luong", "tien cong", "quyet toan thue tncn",
      "quyet toan thue thu nhap ca nhan", "khau tru thue tncn"], "TNCN"),
    (["hoa don", "hoa don dien tu", "hddt", "invoice", "xuat hoa don", "ky hieu hoa don"], "HOA_DON"),
    (["xuat nhap khau", "xnk", "hai quan", "customs", "chq", "nvthq", "thue xuat khau", "thue nhap khau"], "XNK"),
    (["ttdb", "tieu thu dac biet", "special consumption", "thue tieu thu dac biet"], "TTDB"),
    (["nha thau nuoc ngoai", "nha thau", "fct", "foreign contractor", "thue nha thau"], "FCT"),
    (["lien ket", "lien ket", "chuyen gia", "transfer pricing", "gdlk", "giao dich lien ket",
      "gia chuyen nhuong"], "GDLK"),
    (["ho kinh doanh", "hkd", "thue khoan", "khai thue nop thue thay cho ho kinh doanh",
      "ca nhan kinh doanh"], "HKD"),
    (["hiep dinh thue", "thue quoc te", "pillar", "beps", "dta", "tranh danh thue hai lan",
      "nen thue toi thieu"], "THUE_QT"),
    (["mon bai", "le phi mon bai", "thue mon bai"], "MON_BAI_PHI"),
    (["dat dai", "tien thue dat", "tien su dung dat", "su dung dat", "phi tham dinh",
      "tai nguyen", "thue tai nguyen"], "TAI_NGUYEN_DAT"),
    # QLT là fallback — chỉ add nếu không match gì khác, HOẶC match keyword rõ ràng
    (["quan ly thue", "gia han nop thue", "mien giam thue", "xu phat vi pham thue",
      "kiem tra thue", "thanh tra thue", "hoan thue", "khai thue", "nop thue",
      "dang ky thue", "ma so thue"], "QLT"),
]

# Chu đề taxonomy — map sac_thue → danh sách chu_de phổ biến
CHU_DE_RULES = {
    "GTGT": [
        (["khau tru", "khau tru thue"], "Khấu trừ thuế GTGT"),
        (["hoan thue", "hoan thue gtgt"], "Hoàn thuế GTGT"),
        (["thue suat", "thue suat gtgt", "0%", "5%", "10%"], "Thuế suất GTGT"),
        (["doi tuong chiu thue", "doi tuong khong chiu thue"], "Đối tượng chịu thuế"),
        (["khai thue", "khai thue gtgt", "ke khai"], "Kê khai thuế GTGT"),
        (["xuat khau", "dich vu xuat khau"], "Thuế GTGT hàng xuất khẩu"),
    ],
    "TNDN": [
        (["chi phi duoc tru", "chi phi hop ly"], "Chi phí được trừ"),
        (["uu dai thue", "mien thue", "giam thue", "uu dai"], "Ưu đãi thuế TNDN"),
        (["khau hao", "tai san co dinh"], "Khấu hao tài sản"),
        (["quyet toan thue", "quyet toan tndn"], "Quyết toán thuế TNDN"),
        (["chuyen nhuong von", "chuyen nhuong co phan"], "Chuyển nhượng vốn/cổ phần"),
        (["co so thuong tru", "cstt"], "Cơ sở thường trú"),
        (["thu nhap chiu thue", "thu nhap mien thue"], "Xác định thu nhập chịu thuế"),
    ],
    "TNCN": [
        (["quyet toan thue tncn", "quyet toan"], "Quyết toán thuế TNCN"),
        (["khau tru thue tncn", "khau tru tai nguon"], "Khấu trừ tại nguồn"),
        (["giam tru gia canh", "nguoi phu thuoc"], "Giảm trừ gia cảnh"),
        (["tien luong tien cong", "thu nhap tu tien luong"], "Thu nhập từ tiền lương"),
        (["chuyen nhuong chung khoan", "chuyen nhuong bat dong san"], "Chuyển nhượng BĐS/CK"),
        (["ca nhan cu tru", "ca nhan khong cu tru"], "Cá nhân cư trú/không cư trú"),
    ],
    "HOA_DON": [
        (["xuat hoa don", "thoi diem xuat hoa don"], "Thời điểm xuất hóa đơn"),
        (["hoa don dien tu", "hddt"], "Hóa đơn điện tử"),
        (["dieu chinh hoa don", "huy hoa don"], "Điều chỉnh/hủy hóa đơn"),
        (["ky hieu hoa don", "mau hoa don"], "Ký hiệu mẫu hóa đơn"),
        (["xu phat hoa don", "vi pham hoa don"], "Vi phạm về hóa đơn"),
    ],
    "QLT": [
        (["gia han nop thue", "gia han"], "Gia hạn nộp thuế"),
        (["mien giam thue", "mien thue", "giam thue"], "Miễn giảm thuế"),
        (["hoan thue", "thu tuc hoan thue"], "Hoàn thuế"),
        (["xu phat", "xu phat vi pham", "tien cham nop"], "Xử phạt vi phạm"),
        (["kiem tra thue", "thanh tra thue"], "Kiểm tra/thanh tra thuế"),
        (["dang ky thue", "ma so thue"], "Đăng ký thuế/MST"),
        (["khai thue", "to khai"], "Kê khai thuế"),
        (["khieu nai thue", "giai quyet khieu nai"], "Khiếu nại thuế"),
    ],
    "FCT": [
        (["nha thau nuoc ngoai", "nha thau"], "Thuế nhà thầu nước ngoài"),
        (["phuong phap tinh thue nha thau"], "Phương pháp tính thuế nhà thầu"),
        (["dich vu nuoc ngoai", "cung cap dich vu"], "Dịch vụ cung cấp từ nước ngoài"),
    ],
    "GDLK": [
        (["giao dich lien ket", "gia chuyen nhuong"], "Giao dịch liên kết"),
        (["xac dinh gia thi truong", "arm's length"], "Xác định giá thị trường"),
        (["ho so chuyen gia", "tai lieu chuyen gia"], "Hồ sơ xác định giá"),
        (["ket qua kinh doanh", "ngan sach"], "Phân bổ lợi nhuận"),
    ],
    "XNK": [
        (["thue xuat khau", "thue nhap khau"], "Thuế xuất nhập khẩu"),
        (["mien thue xnk", "uu dai thue xnk"], "Miễn/ưu đãi thuế XNK"),
        (["tri gia hai quan", "xac dinh tri gia"], "Trị giá hải quan"),
        (["ma hs", "phan loai hang hoa"], "Phân loại hàng hóa/mã HS"),
    ],
}

def _remove_accents(text: str) -> str:
    """Simple diacritic removal for Vietnamese."""
    text = text.lower()
    replacements = [
        ("ắ","a"),("ặ","a"),("ầ","a"),("ấ","a"),("ậ","a"),("ẫ","a"),("ẵ","a"),
        ("ă","a"),("â","a"),("đ","d"),
        ("ề","e"),("ế","e"),("ệ","e"),("ễ","e"),("ể","e"),("ê","e"),
        ("ồ","o"),("ố","o"),("ộ","o"),("ỗ","o"),("ổ","o"),("ô","o"),
        ("ờ","o"),("ớ","o"),("ợ","o"),("ỡ","o"),("ở","o"),("ơ","o"),
        ("ừ","u"),("ứ","u"),("ự","u"),("ữ","u"),("ử","u"),("ư","u"),
        ("à","a"),("á","a"),("ả","a"),("ã","a"),("ạ","a"),
        ("è","e"),("é","e"),("ẻ","e"),("ẽ","e"),("ẹ","e"),
        ("ì","i"),("í","i"),("ỉ","i"),("ĩ","i"),("ị","i"),
        ("ò","o"),("ó","o"),("ỏ","o"),("õ","o"),("ọ","o"),
        ("ù","u"),("ú","u"),("ủ","u"),("ũ","u"),("ụ","u"),
        ("ỳ","y"),("ý","y"),("ỷ","y"),("ỹ","y"),("ỵ","y"),
    ]
    for v, a in replacements:
        text = text.replace(v, a)
    return text

def classify_sac_thue_multi(url: str, title: str) -> list:
    """
    Classify sắc thuế từ URL + title → trả LIST (có thể nhiều sắc thuế).
    VD: CV về 'chi phí được trừ và hóa đơn' → ['TNDN', 'HOA_DON']
    """
    text = _remove_accents(url + " " + title)
    matched = []
    for keywords, sac_thue in SAC_THUE_RULES:
        if sac_thue == "QLT":
            continue  # QLT xử lý riêng bên dưới
        if any(k in text for k in keywords):
            if sac_thue not in matched:
                matched.append(sac_thue)

    # QLT: add nếu match keyword rõ ràng, HOẶC không match gì khác
    qlt_keywords = SAC_THUE_RULES[-1][0]
    if any(k in text for k in qlt_keywords) or not matched:
        if "QLT" not in matched:
            matched.append("QLT")

    return matched

def classify_chu_de_multi(title: str, sac_thue_list: list) -> list:
    """
    Classify chu_de từ title dựa trên sac_thue_list → trả LIST.
    VD: ['TNDN', 'HOA_DON'] → ['Chi phí được trừ', 'Hóa đơn điện tử']
    """
    text = _remove_accents(title)
    matched = []
    for st in sac_thue_list:
        rules = CHU_DE_RULES.get(st, [])
        for keywords, chu_de in rules:
            if any(k in text for k in keywords):
                if chu_de not in matched:
                    matched.append(chu_de)
    return matched

def fetch_url(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    return ""

def extract_so_hieu_from_url(url: str) -> str:
    """Extract short so_hieu like 1233/CT-CS from URL."""
    # /Cong-van-1233-CT-CS-2026-...
    m = re.search(r'/[Cc]ong-van-(\d+)-([A-Z0-9]+)-([A-Z0-9]+)-\d{4}[-/]', url)
    if m:
        return f"{m.group(1)}/{m.group(2)}-{m.group(3)}"
    # fallback: /Cong-van-13658-CHQ-NVTHQ-2026
    m2 = re.search(r'/[Cc]ong-van-(\d+)-([A-Z0-9]+)-([A-Z0-9]+)', url)
    if m2:
        return f"{m2.group(1)}/{m2.group(2)}-{m2.group(3)}"
    return None

def extract_metadata(html: str, url: str) -> dict:
    result = {
        "link_nguon": url,
        "nguon": "tvpl_manual",
        "so_hieu": None,
        "ten": None,
        "co_quan": None,
        "ngay_ban_hanh": None,
        "tinh_trang": "Còn hiệu lực",
        "sac_thue": None,
        "chu_de": None,
        "noi_dung_day_du": None,
    }

    # Title from og:title
    og_m = re.search(r'property="og:title"\s+content="([^"]+)"', html)
    if not og_m:
        og_m = re.search(r'content="([^"]+)"\s+property="og:title"', html)
    if og_m:
        result["ten"] = og_m.group(1).strip()
    else:
        t_m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
        if t_m:
            result["ten"] = t_m.group(1).strip()

    # Content HTML
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        content_div = soup.find(id="ctl00_Content_ThongTinVB_pnlDocContent")
        if content_div:
            result["noi_dung_day_du"] = str(content_div)
    else:
        m = re.search(
            r'id=["\']ctl00_Content_ThongTinVB_pnlDocContent["\']>(.*?)(?=<div[^>]*id=["\']ctl00_Content_ThongTinVB_div[A-Z]|</form>)',
            html, re.DOTALL
        )
        if m:
            result["noi_dung_day_du"] = m.group(1)

    # so_hieu — try from content first (more accurate)
    so_hieu_m = re.search(r'Số:\s*([\d]+/[\w\-]+)', html[:20000])
    if so_hieu_m:
        result["so_hieu"] = so_hieu_m.group(1).strip()
    else:
        result["so_hieu"] = extract_so_hieu_from_url(url)

    # Ngay ban hanh — from document body
    ngay_m = re.search(r'ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})', html[:30000])
    if ngay_m:
        d, mo, y = ngay_m.groups()
        result["ngay_ban_hanh"] = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    else:
        pub_m = re.search(r'"article:published_time"\s+content="(\d{4}-\d{2}-\d{2})', html)
        if not pub_m:
            pub_m = re.search(r'content="(\d{4}-\d{2}-\d{2})T', html)
        if pub_m:
            result["ngay_ban_hanh"] = pub_m.group(1)

    # Co quan
    co_quan_m = re.search(
        r'(TỔNG CỤC THUẾ|TỔNG CỤC HẢI QUAN|CỤC THUẾ[^\n<]{0,30}|CỤC HẢI QUAN[^\n<]{0,20}|BỘ TÀI CHÍNH|SỞ TÀI CHÍNH[^\n<]{0,20}|UBND[^\n<]{0,20})',
        html[:10000]
    )
    if co_quan_m:
        result["co_quan"] = co_quan_m.group(1).strip()

    # Multi-value classification
    sac_thue_list = classify_sac_thue_multi(url, result["ten"] or "")
    result["sac_thue"] = sac_thue_list
    result["chu_de"] = classify_chu_de_multi(result["ten"] or "", sac_thue_list)

    if "hết hiệu lực" in html[:5000].lower():
        result["tinh_trang"] = "Hết hiệu lực"

    return result


# ─── Phase 1: Fetch ──────────────────────────────────────────────────────────

def cmd_fetch(args):
    links = []
    if args.inline:
        links = [u.strip() for u in args.inline if u.strip()]
    elif args.links:
        with open(args.links) as f:
            links = [l.strip() for l in f if l.strip().startswith("http")]
    
    if not links:
        print("No links provided.")
        sys.exit(1)

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Fetching {len(links)} links...\n")
    results = []

    for i, url in enumerate(links, 1):
        print(f"[{i}/{len(links)}] {url.split('/')[-1][:65]}...")
        try:
            html = fetch_url(url)
            if not html:
                print(f"  ❌ Empty response")
                continue
            rec = extract_metadata(html, url)
            results.append(rec)
            print(f"  ✅ {rec['so_hieu']} | {rec['ngay_ban_hanh']} | sac_thue={rec['sac_thue']} | chu_de={rec['chu_de']} | content={len(rec['noi_dung_day_du'] or '')} chars")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        if i < len(links):
            time.sleep(args.delay)

    print(f"\n{'─'*60}")
    print(f"Fetched: {len(results)}/{len(links)}")

    if args.dry_run:
        if results:
            print("\nSample (first record, no content):")
            r = {k: v for k, v in results[0].items() if k != "noi_dung_day_du"}
            print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    # Save to JSON
    out_path = args.out or f"/tmp/tvpl_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved {len(results)} records → {out_path}")
    print(f"\nNext step — on VPS:")
    print(f"  python3 /opt/dbvntax/tvpl_import_links.py insert --json {out_path}")


# ─── Phase 2: Insert ─────────────────────────────────────────────────────────

def cmd_insert(args):
    if not psycopg2:
        print("ERROR: pip3 install psycopg2-binary")
        sys.exit(1)

    all_records = []
    for json_path in args.json:
        with open(json_path, encoding="utf-8") as f:
            records = json.load(f)
        print(f"Loaded {len(records)} records from {json_path}")
        all_records.extend(records)

    print(f"\nTotal: {len(all_records)} records → inserting to PostgreSQL...")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    inserted = skipped = errors = 0

    for rec in all_records:
        try:
            # Duplicate check: link_nguon OR (so_hieu + ngay_ban_hanh)
            cur.execute("""
                SELECT id FROM cong_van 
                WHERE link_nguon = %s
                   OR (so_hieu IS NOT NULL AND so_hieu = %s
                       AND ngay_ban_hanh IS NOT NULL AND ngay_ban_hanh = %s)
                LIMIT 1
            """, (rec["link_nguon"], rec.get("so_hieu"), rec.get("ngay_ban_hanh")))
            if cur.fetchone():
                skipped += 1
                continue

            # sac_thue: đã là list từ phase 1
            sac_thue_val = rec.get("sac_thue") or []
            if isinstance(sac_thue_val, str):
                sac_thue_val = [sac_thue_val]

            # chu_de: đã là list từ phase 1
            chu_de_val = rec.get("chu_de") or []
            if isinstance(chu_de_val, str):
                chu_de_val = [chu_de_val]

            cur.execute("""
                INSERT INTO cong_van (
                    so_hieu, ten, co_quan, ngay_ban_hanh, tinh_trang,
                    sac_thue, chu_de, noi_dung_day_du, link_nguon, nguon
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            """, (
                rec.get("so_hieu"),
                rec.get("ten"),
                rec.get("co_quan"),
                rec.get("ngay_ban_hanh"),
                rec.get("tinh_trang", "Còn hiệu lực"),
                sac_thue_val,
                chu_de_val,
                rec.get("noi_dung_day_du"),
                rec.get("link_nguon"),
                rec.get("nguon", "tvpl_manual"),
            ))
            inserted += 1
            if inserted % 50 == 0:
                conn.commit()
                print(f"  ... {inserted} inserted so far")
        except Exception as e:
            print(f"  ❌ {rec.get('so_hieu','?')}: {e}")
            errors += 1
            conn.rollback()

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ Inserted: {inserted}")
    print(f"⏭️  Skipped (duplicate): {skipped}")
    if errors:
        print(f"❌ Errors: {errors}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Import TVPL công văn links to PostgreSQL (2-phase)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # fetch subcommand
    f = sub.add_parser("fetch", help="Phase 1: Fetch HTML from TVPL (run on OpenClaw)")
    f.add_argument("--inline", nargs="+", help="URLs inline")
    f.add_argument("--links", help="File with URLs (one per line)")
    f.add_argument("--out", help="Output JSON file path")
    f.add_argument("--dry-run", action="store_true", help="Parse only, don't save")
    f.add_argument("--delay", type=float, default=1.5, help="Delay between requests (sec)")

    # insert subcommand
    i = sub.add_parser("insert", help="Phase 2: Insert JSON records to PostgreSQL (run on VPS)")
    i.add_argument("--json", nargs="+", required=True, help="JSON file(s) from fetch phase")

    args = parser.parse_args()
    if args.cmd == "fetch":
        cmd_fetch(args)
    elif args.cmd == "insert":
        cmd_insert(args)


if __name__ == "__main__":
    main()
