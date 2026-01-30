import re
import csv
import glob
import os
from html import unescape
from typing import List, Dict, Optional, Any

DATETIME_RE = re.compile(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}$")
AMOUNT_RE = re.compile(r"^\s*([+-])\s*([\d,]+)원\s*$")
NAME_RE = re.compile(
    r'<a href="javascript:void\(0\)" class="header__myname">\s*<span>\s*(.*?)\s*</span>',
    re.DOTALL,
)
TRANSACTION_TBODY_RE = re.compile(
    r'<tbody class="transaction-data">(.*?)</tbody>',
    re.DOTALL,
)
ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

NAME_OWNER_MAP = {
    "이태우": "taewoo",
    "서채영": "chaeyoung",
}

def _clean_html(text: str) -> str:
    return unescape(TAG_RE.sub("", text)).strip()

def _parse_amount(text: str) -> Optional[int]:
    m = AMOUNT_RE.match(text.strip())
    if not m:
        return None
    sign = -1 if m.group(1) == "-" else 1
    return sign * int(m.group(2).replace(",", ""))

def parse(path: str, owner: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parses Gyeonggi Local Currency HTML files.
    """
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
        
    name_match = NAME_RE.search(html)
    user_name = _clean_html(name_match.group(1)) if name_match else ""

    body_match = TRANSACTION_TBODY_RE.search(html)
    if not body_match:
        return []

    rows: List[Dict[str, Any]] = []
    tbody = body_match.group(1)
    for row_html in ROW_RE.findall(tbody):
        cells = [_clean_html(c) for c in CELL_RE.findall(row_html)]
        if len(cells) < 6:
            continue

        tx_type = cells[0]
        method = cells[1]
        merchant = cells[2]
        amount_text = cells[3]
        memo = cells[4]
        dt = cells[5]

        if not DATETIME_RE.match(dt):
            continue
        amount = _parse_amount(amount_text)
        if amount is None:
            continue

        date_str, time_str = dt.split(" ", 1)
        date_str = date_str.replace("/", "-")
        
        # Map Korean name to owner identifier
        if user_name in NAME_OWNER_MAP:
            row_owner = NAME_OWNER_MAP[user_name]
        else:
            row_owner = owner or user_name or "unknown"

        rows.append({
            "날짜": date_str,
            "시간": time_str,
            "결제정보": merchant,
            "액션": f"{tx_type} {method}".strip(),
            "금액": amount,
            "메모": memo if memo != "-" else "",
            "이름": user_name,
            "owner": row_owner,
        })

    return rows

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Gyeonggi Local Currency HTML Parser")
    parser.add_argument("input", help="Input file path or pattern")
    parser.add_argument("--owner", help="Owner name")
    parser.add_argument("--output", help="Output CSV path", default="gcpay.csv")
    
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
