import re
import csv
import glob
import os
from datetime import datetime
from html import unescape
from typing import Dict, List, Optional, Sequence, Tuple

DATE_RE = re.compile(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")

KNOWN_HEADERS = {
    "승인일", "승인시각", "카드구분", "카드종류", "가맹점명", "승인금액",
    "이용구분", "할부개월", "승인번호", "취소일", "승인구분",
}

HTML_TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.DOTALL | re.IGNORECASE)
TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
TD_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")

# Map masked numbers to owners
OWNER_MAP = {
    "4***-****-****-670*": "taewoo",
    "4***-****-****-342*": "taewoo",
    "9***-****-****-800*": "chaeyoung",
    "4***-****-****-931*": "chaeyoung",
}

def _normalize_header(value: object) -> str:
    text = str(value).strip()
    return re.sub(r"\s+", "", text)

def _read_xls_rows(path: str) -> Tuple[List[List[object]], Optional[int]]:
    try:
        import xlrd
    except ImportError as exc:
        raise ImportError("xlrd가 설치되어 있지 않습니다. `pip install xlrd` 후 다시 실행해주세요.") from exc

    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    rows: List[List[object]] = []
    for r in range(sheet.nrows):
        rows.append([sheet.cell_value(r, c) for c in range(sheet.ncols)])
    return rows, book.datemode

def _detect_header(rows: List[List[object]]) -> Tuple[int, List[str]]:
    best_idx = -1
    best_score = 0
    best_header: List[str] = []
    for idx, row in enumerate(rows[:30]):
        normalized = [_normalize_header(c) for c in row]
        score = sum(1 for cell in normalized if cell in KNOWN_HEADERS)
        if score > best_score:
            best_score = score
            best_idx = idx
            best_header = normalized
    if best_idx == -1:
        return -1, []
    return best_idx, best_header

def _parse_excel_datetime(value: object, datemode: Optional[int]) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)) and datemode is not None:
        try:
            import xlrd
            return xlrd.xldate_as_datetime(value, datemode)
        except Exception:
            return None
    if isinstance(value, str):
        date_match = DATE_RE.search(value)
        time_match = TIME_RE.search(value)
        if date_match:
            year, month, day = map(int, date_match.groups())
            hour = int(time_match.group(1)) if time_match else 0
            minute = int(time_match.group(2)) if time_match else 0
            second = int(time_match.group(3)) if time_match and time_match.group(3) else 0
            try:
                return datetime(year, month, day, hour, minute, second)
            except ValueError:
                return None
    return None

def _parse_amount(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d\-]", "", value)
        if cleaned in ("", "-"):
            return None
        try:
            return int(cleaned)
        except ValueError:
            return None
    return None

def _pick_first(row: Dict[str, object], keys: Sequence[str]) -> Optional[object]:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None

def _clean_html(text: str) -> str:
    return unescape(TAG_RE.sub("", text)).strip()

def _parse_korean_date(text: str) -> Optional[str]:
    m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if not m:
        return None
    year, month, day = map(int, m.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"

def _parse_card_html(html: str) -> List[Dict[str, object]]:
    table_match = HTML_TABLE_RE.search(html)
    if not table_match:
        return []
    table_html = table_match.group(1)
    rows = TR_RE.findall(table_html)
    if not rows:
        return []

    header_idx = -1
    for idx, row_html in enumerate(rows):
        cells = [_clean_html(c) for c in TD_RE.findall(row_html)]
        # Check if at least 6 cells match known headers (more lenient)
        if cells and sum(1 for cell in cells if cell in KNOWN_HEADERS) >= 6:
            header_idx = idx
            break

    result: List[Dict[str, object]] = []
    if header_idx == -1:
        return result

    for row_html in rows[header_idx + 1 :]:
        cells = [_clean_html(c) for c in TD_RE.findall(row_html)]
        if len(cells) < 11:
            continue
        date_str = _parse_korean_date(cells[0]) or cells[0]
        time_str = cells[1]
        amount = _parse_amount(cells[5])
        if not date_str or not time_str or amount is None:
            continue
        status_text = cells[10]
        
        card_no = cells[3]
        owner = OWNER_MAP.get(card_no, "unknown")

        result.append({
            "날짜": date_str,
            "시간": time_str if len(time_str) == 8 else f"{time_str}:00",
            "가맹점명": cells[4],
            "승인금액": amount,
            "승인구분": status_text,
            "카드종류": card_no,
            "owner": owner,
        })
    return result

def parse(path: str, owner: Optional[str] = None) -> List[Dict[str, object]]:
    """
    Parses Hyundai Card XLS/HTML files.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    if "<table" in text.lower():
        rows = _parse_card_html(text)
        if owner:
            return [r for r in rows if r["owner"] == owner]
        return rows

    rows, datemode = _read_xls_rows(path)
    header_idx, headers = _detect_header(rows)
    if header_idx == -1:
        return []

    result: List[Dict[str, object]] = []
    for row in rows[header_idx + 1 :]:
        if all(str(cell).strip() == "" for cell in row):
            continue
        row_map: Dict[str, object] = {}
        for idx, header in enumerate(headers):
            if not header: continue
            if idx >= len(row): continue
            row_map[header] = row[idx]

        date_value = _pick_first(row_map, ["승인일"])
        time_value = _pick_first(row_map, ["승인시각"])
        dt = _parse_excel_datetime(date_value, datemode)
        if dt is None and time_value is not None:
            dt = _parse_excel_datetime(f"{date_value} {time_value}", datemode)
        if dt is None:
            continue

        amount = _parse_amount(_pick_first(row_map, ["승인금액"]))
        if amount is None:
            continue

        status_text = str(_pick_first(row_map, ["승인구분"]) or "").strip()
        card_no = str(_pick_first(row_map, ["카드종류"]) or "").strip()
        
        row_owner = owner or OWNER_MAP.get(card_no, "unknown")

        result.append({
            "날짜": dt.strftime("%Y-%m-%d"),
            "시간": dt.strftime("%H:%M:%S"),
            "가맹점명": str(_pick_first(row_map, ["가맹점명"]) or "").strip(),
            "승인금액": amount,
            "승인구분": status_text,
            "카드종류": card_no,
            "owner": row_owner,
        })

    return result

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Hyundai Card XLS/HTML Parser")
    parser.add_argument("input", help="Input file path or pattern")
    parser.add_argument("--owner", help="Owner name (taewoo or chaeyoung)")
    parser.add_argument("--output", help="Output CSV path", default="hyundai_card.csv")
    
    args = parser.parse_args()
    
    paths = glob.glob(args.input)
    all_rows = []
    for path in sorted(paths):
        print(f"Parsing {path}...")
        all_rows.extend(parse(path, args.owner))
        
    if all_rows:
        keys = all_rows[0].keys()
        with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"Saved {len(all_rows)} rows to {args.output}")
    else:
        print("No rows parsed.")
