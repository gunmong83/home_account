import re
import csv
import glob
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Sequence

DATE_RE = re.compile(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")

SHINHAN_OWNER_MAP = {
    "147*": "taewoo",
    "6267": "taewoo",
}

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

def parse(path: str, owner: Optional[str] = "taewoo") -> List[Dict[str, object]]:
    """
    Parses Shinhan Card XLS files.
    """
    rows, datemode = _read_xls_rows(path)
    if not rows:
        return []

    header_idx = -1
    headers: List[str] = []
    
    for idx, row in enumerate(rows):
        row_str = [str(c).strip() for c in row]
        if "거래일" in row_str and "가맹점명" in row_str:
            header_idx = idx
            headers = row_str
            break
            
    if header_idx == -1:
        return []

    result: List[Dict[str, object]] = []
    for row in rows[header_idx + 1 :]:
        if not row or all(str(c).strip() == "" for c in row):
            continue
        
        row_map: Dict[str, object] = {}
        for i, header in enumerate(headers):
            if i < len(row):
                row_map[header] = row[i]
        
        if "거래일" not in row_map:
            continue
            
        amt = _parse_amount(row_map.get("금액"))
        if amt is None:
            continue
            
        # Parse datetime
        # Shinhan date format in card.py was: 2026.01.23 10:29
        date_str = str(row_map.get("거래일", "")).strip()
        # Handle both 2026.01.23 and 2026-01-23
        date_str = date_str.replace(".", "-")
        try:
            # Check if it has time
            if " " in date_str:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            else:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        # Try to determine owner from card number if not provided
        row_owner = owner
        card_info = str(row_map.get("이용카드", "")).strip()
        if card_info:
            for last4, o in SHINHAN_OWNER_MAP.items():
                if last4 in card_info:
                    row_owner = o
                    break

        result.append({
            "날짜": dt.strftime("%Y-%m-%d"),
            "시간": dt.strftime("%H:%M:%S"),
            "가맹점명": str(row_map.get("가맹점명", "")).strip(),
            "금액": amt,
            "매입구분": str(row_map.get("매입구분", "")).strip(),
            "취소상태": str(row_map.get("취소상태", "")).strip(),
            "이용카드": card_info,
            "owner": row_owner,
        })

    return result

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Shinhan Card XLS Parser")
    parser.add_argument("input", help="Input file path or pattern")
    parser.add_argument("--owner", help="Owner name", default="taewoo")
    parser.add_argument("--output", help="Output CSV path", default="shinhan_card.csv")
    
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
