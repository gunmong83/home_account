import pandas as pd
import csv
import glob
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

def _detect_owner_from_filename(path: str) -> str:
    filename = os.path.basename(path).lower()
    if "_tw" in filename:
        return "taewoo"
    elif "_cy" in filename:
        return "chaeyoung"
    return "unknown"


def parse(path: str, owner: Optional[str] = None) -> List[Dict[str, Any]]:
    if owner is None:
        owner = _detect_owner_from_filename(path)
    
    df = pd.read_excel(path)
    
    # Verify columns exist
    required_cols = ['거래일자', '거래시각', '가맹점 및 상품권명', '거래금액', '거래구분']
    for col in required_cols:
        if col not in df.columns:
            return []

    rows = []
    for _, row in df.iterrows():
        # Date Time parsing
        d_str = str(row['거래일자']).strip()
        t_str = str(row['거래시각']).strip().zfill(6) # Ensure 6 digits
        try:
            dt = datetime.strptime(f"{d_str} {t_str}", "%Y%m%d %H%M%S")
        except ValueError:
            continue
            
        merchant = str(row['가맹점 및 상품권명']).strip()
        amount = int(row['거래금액'])
        status = str(row['거래구분']).strip()
        
        rows.append({
            "날짜": dt.strftime("%Y-%m-%d"),
            "시간": dt.strftime("%H:%M:%S"),
            "가맹점": merchant,
            "금액": amount,
            "상태": status,
            "owner": owner,
        })
        
    return rows

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Onnuri Gift Certificate Excel Parser")
    parser.add_argument("input", help="Input file path or pattern")
    parser.add_argument("--owner", help="Owner name", default="unknown")
    parser.add_argument("--output", help="Output CSV path", default="onnuri.csv")
    
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
