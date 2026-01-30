import re
import csv
import glob
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Sequence

# Account mapping might be useful internally but the interface requires owner
ACCOUNT_NAME_MAP = {
    "126-808192-02-001": "taewoo",
    "167-055234-12-101": "chaeyoung",
}

ACCOUNT_RE = re.compile(r"\b\d{3}-\d{6}-\d{2}-\d{3}\b")
DATE_RE = re.compile(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")

KNOWN_HEADERS = {
    "거래일시", "거래일자", "거래일", "거래시간", "시간", "적요", "내용", "거래내용",
    "거래구분", "구분", "입금액", "출금액", "맡기신금액", "찾으신금액", "거래금액", "금액",
    "잔액", "거래후잔액", "기재내용", "취급기관", "계좌번호",
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

def parse(path: str, owner: Optional[str] = None) -> List[Dict[str, object]]:
    """
    Parses Woori Bank XLS files.
    If owner is provided, it filters or tags rows with that owner.
    """
    rows, datemode = _read_xls_rows(path)
    header_idx, headers = _detect_header(rows)
    if header_idx == -1:
        return []

    result: List[Dict[str, object]] = []
    prev_balance = None
    for row in rows[header_idx + 1 :]:
        if all(str(cell).strip() == "" for cell in row):
            continue
        row_map = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            if idx >= len(row):
                continue
            row_map[header] = row[idx]

        date_value = _pick_first(row_map, ["거래일시", "거래일자", "거래일"])
        time_value = _pick_first(row_map, ["거래시간", "시간"])
        dt = _parse_excel_datetime(date_value, datemode)
        if dt is None and time_value is not None:
            dt = _parse_excel_datetime(f"{date_value} {time_value}", datemode)
        if dt is None:
            continue

        deposit = _parse_amount(_pick_first(row_map, ["입금액", "맡기신금액"]))
        withdraw = _parse_amount(_pick_first(row_map, ["출금액", "찾으신금액"]))
        amount = _parse_amount(_pick_first(row_map, ["거래금액", "금액"]))
        balance = _parse_amount(_pick_first(row_map, ["거래후잔액", "잔액"]))
        memo = _pick_first(row_map, ["적요", "내용", "거래내용"]) or ""
        note = _pick_first(row_map, ["기재내용"]) or ""
        institution = _pick_first(row_map, ["취급기관"]) or ""
        tx_type = _pick_first(row_map, ["거래구분", "구분"]) or ""

        # If amount is not directly available, calculate from deposit/withdraw
        if amount is None:
            if deposit is not None and deposit > 0:
                amount = deposit
            elif withdraw is not None and withdraw > 0:
                amount = -withdraw
            elif deposit is not None and withdraw is not None:
                # Both present: net amount
                amount = deposit - withdraw
        
        # Determine amount sign
        # Check keywords first (topup/transfer out)
        topup_keywords = ["토리", "경기지역화폐", "네이버페이", "네이버머니", "온누리충전"]
        combined_text = f"{memo} {note}"
        if any(keyword in combined_text for keyword in topup_keywords):
            if amount is not None:
                amount = -abs(amount)
            elif deposit is not None:
                amount = -abs(deposit)
            elif withdraw is not None:
                amount = -abs(withdraw)
        # Otherwise use deposit/withdraw columns
        if balance is not None:
            prev_balance = balance

        
        # Determine owner from path or account number if not provided
        row_owner = owner
        if not row_owner:
            account = _pick_first(row_map, ["계좌번호"])
            if account:
                row_owner = ACCOUNT_NAME_MAP.get(str(account).strip(), "unknown")
            else:
                # Try to find account hint in the first few rows
                for r in rows[:header_idx + 3]:
                    for cell in r:
                        match = ACCOUNT_RE.search(str(cell))
                        if match:
                            row_owner = ACCOUNT_NAME_MAP.get(match.group(0), "unknown")
                            break
                    if row_owner: break
        
        if not row_owner:
            row_owner = "unknown"

        result.append({
            "날짜": dt.strftime("%Y-%m-%d"),
            "시간": dt.strftime("%H:%M:%S"),
            "거래구분": str(tx_type).strip(),
            "적요": str(memo).strip(),
            "기재내용": str(note).strip(),
            "취급기관": str(institution).strip(),
            "입금액": deposit if deposit is not None else 0,
            "출금액": withdraw if withdraw is not None else 0,
            "잔액": balance if balance is not None else 0,
            "금액": amount if amount is not None else 0,
            "owner": row_owner,
        })

    return result

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Woori Bank XLS Parser")
    parser.add_argument("input", help="Input file path or pattern (e.g. 'invoices/*.xls')")
    parser.add_argument("--owner", help="Owner name (taewoo or chaeyoung)")
    parser.add_argument("--output", help="Output CSV path", default="woori_bank.csv")
    
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
