import re
import csv
import glob
import os
from datetime import datetime
from html import unescape
from typing import Dict, List, Optional, Any, Iterable, Tuple

# --- Parsing Logic (from original naverpay.py) ---

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
    re.DOTALL,
)
PAYMENT_ITEM_MARKER_RE = re.compile(r'PaymentItem_item-payment__')
STATUS_RE = re.compile(
    r'<strong class="OrderStatus_value__[^"]*">\s*(.*?)\s*</strong>',
    re.DOTALL,
)
PRODUCT_RE = re.compile(
    r'<span class="ProductNameHighlightByKeyword_article__[^"]*">\s*(.*?)\s*</span>',
    re.DOTALL,
)
PRODUCT_FALLBACK_RE = re.compile(
    r'<p class="ProductName_name__[^"]*">\s*(.*?)\s*</p>',
    re.DOTALL,
)
PRICE_RE = re.compile(
    r'<b class="PaymentItem_price__[^"]*">\s*(.*?)\s*</b>',
    re.DOTALL,
)
TIME_RE = re.compile(
    r'<span class="PaymentItem_time__[^"]*">\s*(?:<span[^>]*>.*?</span>)?\s*([^<]+)</span>',
    re.DOTALL,
)
ORDER_LINK_RE = re.compile(
    r'href="https://orders\.pay\.naver\.com/(?:order/status|instantPay/detail)/([^"?]+)',
    re.DOTALL,
)

def _clean_text(text: str) -> str:
    return unescape(re.sub(r"<.*?>", "", text)).strip()

def _clean_time_text(text: str) -> str:
    cleaned = _clean_text(text)
    cleaned = cleaned.replace("결제일시", "").replace("결제", "")
    return cleaned.strip()

def _normalize_amount(value: Any) -> Optional[int]:
    if value is None: return None
    if isinstance(value, (int, float)): return int(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d\-]", "", value)
        if cleaned in ("", "-"): return None
        try: return int(cleaned)
        except ValueError: return None
    return None

def _parse_md_time(text: str, order_id: Optional[str] = None, year_hint: Optional[int] = None) -> Optional[Tuple[str, str]]:
    # Handle formats like "1. 29. 14:45" or "01.29 14:45" or "25.01.29 14:45"
    m = re.search(r"(\d{2,4}[-.] )?(\d{1,2})[-.]\s*(\d{1,2})[-.]?\s+(\d{2}:\d{2})", text)
    if m:
        # Check if year is present (e.g. 25.01.29)
        year_str = m.group(1)
        month, day, time_str = int(m.group(2)), int(m.group(3)), m.group(4)
        year = None
        if year_str:
            y = year_str.strip().replace(".", "").replace("-", "")
            if len(y) == 2: year = 2000 + int(y)
            elif len(y) == 4: year = int(y)
        
        if not year and order_id:
            m_order = re.match(r"^(\d{4})", str(order_id))
            if m_order: year = int(m_order.group(1))
        if not year: year = year_hint or datetime.now().year
        return f"{year:04d}-{month:02d}-{day:02d}", f"{time_str}:00"
    
    # Try the old regex just in case
    m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{2}:\d{2})", text)
    if not m: return None
    month, day, time_str = int(m.group(1)), int(m.group(2)), m.group(3)
    year = year_hint or datetime.now().year
    return f"{year:04d}-{month:02d}-{day:02d}", f"{time_str}:00"

def _parse_payment_list_from_html(html: str) -> List[Dict[str, Any]]:
    starts = [m.start() for m in PAYMENT_ITEM_MARKER_RE.finditer(html)]
    items = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(html)
        block = html[start:end]
        
        def first_match(p, t):
            m = p.search(t)
            return m.group(1).strip() if m else ""

        status = _clean_text(first_match(STATUS_RE, block))
        product = _clean_text(first_match(PRODUCT_RE, block) or first_match(PRODUCT_FALLBACK_RE, block))
        price = _normalize_amount(_clean_text(first_match(PRICE_RE, block)))
        time_text = _clean_time_text(first_match(TIME_RE, block))
        order_id = _clean_text(first_match(ORDER_LINK_RE, block))

        dt = _parse_md_time(time_text, order_id)
        date_str, time_str = dt if dt else ("", "")

        if not date_str and not product:
            continue

        items.append({
            "날짜": date_str,
            "시간": time_str,
            "상품명": product,
            "가맹점": product,
            "상태": status,
            "금액": price if price is not None else 0,
            "주문번호": order_id,
            "source": "payments",
            "method": "payments"
        })
    return items

def parse_html(path: str, owner: Optional[str] = None) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Identify type by filename first (more reliable)
    filename_lower = os.path.basename(path).lower()
    if "naverpay_points" in filename_lower or "points" in filename_lower:
        rows = parse_points_html(html, owner)
    elif "naverpay_money" in filename_lower or "money" in filename_lower:
        rows = parse_money_html(html, owner)
    elif "naverpay_pc" in filename_lower or "naverpay" in filename_lower or "네이버페이" in path.lower():
        # Check for payment items first - this is the most specific indicator
        if "PaymentItem_item-payment__" in html:
            rows = _parse_payment_list_from_html(html)
        elif "PointsHistoryItem_article___qs8W" in html:
            rows = parse_points_html(html, owner)
        elif "History_history__" in html:
            rows = parse_money_html(html, owner)
        else:
            # Fallback: use URL patterns in the HTML
            if "new-m.pay.naver.com/pointshistory" in html:
                rows = parse_points_html(html, owner)
            elif "new-m.pay.naver.com/paymoney/history" in html:
                rows = parse_money_html(html, owner)
            else:
                rows = _parse_payment_list_from_html(html)
    else:
        # Fallback to content-based
        if "pointshistory" in html:
            rows = parse_points_html(html, owner)
        elif "paymoney/history" in html or "History_history__" in html:
            rows = parse_money_html(html, owner)
        else:
            rows = _parse_payment_list_from_html(html)
    
    for r in rows: r["owner"] = owner or "unknown"
    return rows

# --- Points Parsing ---
POINT_ITEM_RE = re.compile(r'class="PointsHistoryItem_article___qs8W[^"]*"')
POINT_DATE_RE = re.compile(r'class="PointsHistoryItem_date__[^"]*">.*?(\d{2}\.\d{2})</div>')
POINT_TIME_RE = re.compile(r'class="blind">시간</span>\s*(\d{2}:\d{2})</span>')
POINT_DESC_RE = re.compile(r'class="PointsHistoryItem_title__[^"]*"[^>]*>\s*(.*?)\s*(?:</span|</a>|<svg)', re.DOTALL)
POINT_AMOUNT_RE = re.compile(r'class="PointsHistoryItem_price__[^"]*"[^>]*>\s*(.*?)\s*</strong>', re.DOTALL)

def parse_points_html(html: str, owner: Optional[str] = None) -> List[Dict[str, Any]]:
    # Find all years mentioned in HTML (supports "전체 2025년" and "2026년")
    year_match = re.search(r'전체\s*((?:20)?\d{2,4})\s*년', html)
    year_str = year_match.group(1) if year_match else "2026"
    
    starts = [m.start() for m in POINT_DESC_RE.finditer(html)]
    items = []
    
    item_marker = POINT_ITEM_RE
    item_starts = [m.start() for m in item_marker.finditer(html)]
    
    for i, start in enumerate(item_starts):
        end = item_starts[i + 1] if i + 1 < len(item_starts) else len(html)
        block = html[start:end]
        
        # Find the closest date element before this item
        date_val = ""
        for dm in list(POINT_DATE_RE.finditer(block)):
            if dm.start() < start:
                date_val = dm.group(1)
                break
        
        time_match = re.search(POINT_TIME_RE.pattern, block)
        time_val = time_match.group(1) if time_match else ""
        
        desc_match = re.search(POINT_DESC_RE.pattern, block)
        desc = desc_match.group(1) if desc_match else ""
        
        amount_match = re.search(POINT_AMOUNT_RE.pattern, block)
        amount_text = amount_match.group(1) if amount_match else ""
        amount = _normalize_amount(amount_text)
        
        if not date_val and not time_val:
            continue
        
        items.append({
            "날짜": f"{year_str}-{date_val.replace('.', '-')}" if date_val else "",
            "날짜_raw": date_val,
            "시간": f"{time_val}:00" if time_val else "",
            "상품명": desc,
            "가맹점": desc,
            "상태": "적립/사용",
            "금액": amount,
            "owner": owner or "unknown",
        })

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(html)
        block = html[start:end]
        
        def first_match(p, t):
            m = p.search(t)
            return m.group(1).strip() if m else ""

        date_val = ""
        if not date_val:
            # Date is outside the item block, find the last date header before this item
            for dm in reversed(date_markers):
                if dm.start() < start:
                    date_val = dm.group(1)
                    break

        time_val = first_match(POINT_TIME_RE, block)
        desc = _clean_text(first_match(POINT_DESC_RE, block))
        amount_text = _clean_text(first_match(POINT_AMOUNT_RE, block))
        amount = _normalize_amount(amount_text)

        items.append({
            "날짜": f"{datetime.now().year}-{date_val.replace('.', '-')}" if date_val else "",
            "날짜_raw": date_val,
            "시간": f"{time_val}:00" if time_val else "",
            "상품명": desc,
            "가맹점": desc,
            "상태": "적립/사용",
            "금액": amount if amount is not None else 0,
            "owner": owner or "unknown",
            "source": "points",
            "method": "points"
        })
    return items

# --- Money Parsing ---
MONEY_ITEM_RE = re.compile(r'class="History_history__')
MONEY_DATE_RE = re.compile(r'class="History_date__[^"]*">.*?(\d{2}\.\d{2}\.)')
MONEY_TIME_RE = re.compile(r'class="History_type-time__[^"]*">.*?(\d{2}:\d{2})')
MONEY_TITLE_RE = re.compile(r'class="History_title__[^"]*">(?:<a[^>]*>)?\s*(.*?)\s*(?:<span|</a>|</strong>)', re.DOTALL)
MONEY_TYPE_RE = re.compile(r'class="History_type-sub-title__[^"]*">\s*(.*?)\s*</span>', re.DOTALL)
MONEY_AMOUNT_RE = re.compile(r'class="History_price___[^"]*">.*?([+\-]?[\d,]+)\s*원', re.DOTALL)

def parse_money_html(html: str, owner: Optional[str] = None) -> List[Dict[str, Any]]:
    starts = [m.start() for m in MONEY_ITEM_RE.finditer(html)]
    items = []
    
    date_markers = list(MONEY_DATE_RE.finditer(html))

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(html)
        block = html[start:end]
        
        current_date_val = ""
        for dm in reversed(date_markers):
            if dm.start() < start:
                current_date_val = dm.group(1)
                break

        def first_match(p, t):
            m = p.search(t)
            return m.group(1).strip() if m else ""

        time_val = first_match(MONEY_TIME_RE, block)
        title = _clean_text(first_match(MONEY_TITLE_RE, block))
        m_type = _clean_text(first_match(MONEY_TYPE_RE, block))
        amount_text = first_match(MONEY_AMOUNT_RE, block)
        amount = _normalize_amount(amount_text)

        items.append({
            "날짜": f"{datetime.now().year}-{current_date_val.replace('.', '-').rstrip('-')}" if current_date_val else "",
            "시간": f"{time_val}:00" if time_val else "",
            "상품명": title,
            "가맹점": title,
            "상태": m_type,
            "금액": amount if amount is not None else 0,
            "owner": owner or "unknown",
            "source": "money",
            "method": "money"
        })
    return items

# --- Main CLI ---

def parse(path: str, owner: Optional[str] = None) -> List[Dict[str, Any]]:
    # Redirect to specialized parsers if needed, but for now HTML parsing
    return parse_html(path, owner)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Naver Pay Parser & Fetcher")
    parser.add_argument("--action", choices=["parse", "fetch"], default="parse")
    parser.add_argument("--owner", required=True, help="taewoo or chaeyoung")
    parser.add_argument("--input", help="Input file pattern for parsing")
    parser.add_argument("--output", help="Output prefix", default="naverpay")
    args = parser.parse_args()
    
    paths = glob.glob(args.input)
    all_rows = []
    for path in sorted(paths):
        print(f"Parsing {path}...")
        all_rows.extend(parse(path, args.owner))
    if all_rows:
        csv_path = f"{args.output}_{args.owner}.csv"
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"Saved {len(all_rows)} rows to {csv_path}")
