import csv
import glob
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

def parse(path: str, owner: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parses corporate card CSV-like text files.
    """
    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            def clean_num(s):
                if not s: return 0
                return int(str(s).replace(',', '').replace('"', ''))

            try:
                date_str = row.get('사용일자', '').strip()
                time_str = row.get('사용시간', '').strip()
                if not date_str or not time_str:
                    continue
                
                dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                merchant = row.get('가맹점', '').strip()
                amount = clean_num(row.get('사용금액', '0'))
                user = row.get('사용자', '').strip()
                card_no = row.get('카드번호', '').strip()
                approval_no = row.get('승인번호', '').strip()
                category = row.get('업종', '').strip()

                row_owner = owner or user or "unknown"

                rows.append({
                    "날짜": dt.strftime("%Y-%m-%d"),
                    "시간": dt.strftime("%H:%M:%S"),
                    "상품명": merchant,
                    "가맹점": merchant,
                    "금액": amount,
                    "이름": user,
                    "카드번호": card_no,
                    "승인번호": approval_no,
                    "업종": category,
                    "owner": row_owner,
                })
            except Exception as e:
                print(f"Error parsing row in {path}: {e}")
                continue
    return rows

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Corporate Card Parser")
    parser.add_argument("input", help="Input file path or pattern")
    parser.add_argument("--owner", help="Owner name")
    parser.add_argument("--output", help="Output CSV path", default="corp_card.csv")
    
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
