import csv
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple, Any

import parser.woori_bank as woori_bank
import parser.hyundai_card as hyundai_card
import parser.shinhan_card as shinhan_card
import parser.gcpay as gcpay
import parser.naverpay as naverpay
import parser.onnuri as onnuri
import parser.corp_card as corp_card
import config
from whooing_converter import convert_to_whooing_excel
import pandas as pd


# Mappings from internal/external names to Whooing account names
# These names must match whooing_setting.xlsx
ACCOUNTS = {
    "WOORI_TAEWOO": "우리은행태우",
    "WOORI_CHAEYOUNG": "우리은행채영",
    "HYUNDAI_CARD": "신용카드태우",
    "SHINHAN_CARD": "신용카드태우",
    "NAVERPAY_POINTS_TAEWOO": "네이버포인트",
    "NAVERPAY_MONEY_TAEWOO": "네이버머니",
    "CASH": "현금",
    "ONNURI": "온누리태우",
    "ONNURI_CHAEYOUNG": "온누리채영",
    "GC_PAY": "토리태우",
    "GC_PAY_CHAEYOUNG": "토리채영",
    "CORP_CARD": "개인업무지원비", # Using this as a fallback for corp card
}

EXP = {
    "LIFE_COSMETICS": "화장품",
    "LIFE_TOYS": "장난감",
    
    # Education
    "EDU_ACADEMY": "학원비",
    "EDU_MATERIALS": "교재교구비",
    "EDU_BAREFOOT": "맨발조합비",
    
    # Health
    "HEALTH_HOSPITAL": "진료비",
    "HEALTH_PHARMACY": "약국",
    
    # Culture
    "CULTURE_EVENTS": "경조사", 
    "CULTURE_TRAVEL": "여행경비",
    "CULTURE_LEISURE": "문화유흥",
    
    # ETC
    "ETC_ONEOFF": "일회성지출",
    "ETC_MISC": "일회성지출",
    "ETC": "일회성지출",
}

INC = {
    "SALARY_TAEWOO": "월급태우",
    "SALARY_CHAEYOUNG": "채영소득",
    "BONUS_TAEWOO": "상여금",
    "SUPPORT_WORK": "개인업무지원비",
    "POINT_NAVER": "네이버포인트지급",
    "INVEST_INTEREST": "이자소득",
    "INVEST_STOCK": "주식소득",
    "INSURANCE_CLAIM": "보험금지급",
    "ETC_ONEOFF": "일회성수입",
    "ETC_MISC": "기타수익",
    "INCOME": "기타수익",
}

def load_whooing_config(path: str = "assets/whooing_setting.xlsx") -> Dict[str, str]:
    """Loads a mapping of account name -> type (자산, 부채, 수익, 비용, 순자산)"""
    import pandas as pd
    try:
        df = pd.read_excel(path)
        # Ensure correct column names: '계정' and '항목명'
        return dict(zip(df['항목명'], df['계정']))
    except Exception as e:
        print(f"Warning: Could not load Whooing config from {path}: {e}")
        return {}

CATEGORY_RULES: List[Tuple[int, str, str]] = [
    # Fixed
    (1, r"Apple Services|App Store|iTunes|Adobe|넷플릭스|유튜브|YouTube|Google|Coupang Wow|Skt우주", "FIXED_SUBSCRIPTION"),
    (1, r"대출이자|이자", "FIXED_LOAN_INTEREST"),
    (1, r"관리비|삼천리도시가스|한전|한국전력|가스", "FIXED_MANAGEMENT"), 
    (1, r"SKT|KT|LG U\+|통신|인터넷", "FIXED_COMMUNICATION"),
    (1, r"보험|현대해상|삼성화재|DB손해|교보생명|메리츠", "FIXED_INSURANCE"),
    
    # Transport
    (1, r"주유|SK에너지|GS칼텍스|HD현대오일|S-OIL", "TRANSPORT_FUEL"),
    (1, r"티머니|버스|지하철|후불교통|코레일|SRT", "TRANSPORT_PUBLIC"),
    (1, r"한국도로공사|하이패스|고속도로|연결고속도로", "TRANSPORT_TOLL"),
    (1, r"공업사|정비|타이어|블루핸즈|오토큐", "TRANSPORT_MAINTENANCE"),

    # Shopping / Life
    (2, r"이케아|IKEA|한샘|리바트|다이소|모던하우스", "LIFE_INTERIOR"),
    (2, r"올리브영|Olive Young|화장품|이니스프리", "LIFE_COSMETICS"),
    (2, r"장난감|토이|키즈|문구|알파|모닝글로리", "LIFE_TOYS"),
    (2, r"무신사|유니클로|ZARA|H&M|나이키|아디다스|의류|패션|탑텐", "LIFE_CLOTHING_TAEWOO"), # Defaulting to Taewoo/General
    (2, r"쿠팡|Coupang|네이버페이|G마켓|옥션|11번가|Amazon|당근|스마트스토어", "LIFE_DAILY"), 
    (2, r"클라이밍|헬스|운동|체육센터", "CULTURE_LEISURE"),
    
    # Food
    (2, r"과천식자재마트|도시곳간|지에스 더 프레|GS|CU|세븐일레븐|이마트|홈플러스|롯데마트|컬리|SSG|하나로마트|농협", "FOOD_GROCERIES"),
    (2, r"우아한형제들|배달|땡겨요|요기요|배달의민족", "FOOD_DELIVERY"),
    (2, r"스타벅스|카페|커피|투썸|이디야|폴바셋|메가커피|컴포즈", "FOOD_CAFE"),
    (2, r"식당|음식|레스토랑|맥도날드|버거킹|써브웨이|김밥|스파게티|한우|갈비", "FOOD_EATING_OUT"),

    # Health
    (2, r"피부과|내과|의원|병원|치과|안과|산부인과|한의원", "HEALTH_HOSPITAL"),
    (2, r"약국", "HEALTH_PHARMACY"),

    # Education
    (2, r"학원|아카데미|교습소", "EDU_ACADEMY"),
    (2, r"서점|알라딘|교보문고|YES24|영풍문고", "EDU_MATERIALS"),

    # Culture
    (2, r"CGV|롯데시네마|메가박스|영화|전시|박물관", "CULTURE_LEISURE"),
    (2, r"축의금|조의금|장례|웨딩", "CULTURE_EVENTS"),
]

TOPUP_PATTERNS = [
    r"경기지역화폐",
    r"온누리충전",
    r"모바일티머니선불형|티머니\s*$",
    r"네이버페이\s*충전|하나\(\d+\*+\d+\)",
]

NAVERPAY_BANK_KEYWORD = "네이버페이결제"

NAME_OWNER_MAP = {
    "이태우": "taewoo",
    "서채영": "chaeyoung",
}

CARD_OWNER_BY_NUMBER = {
    # 카드번호(마스킹) -> owner, 필요 시 보강
}


@dataclass
class StdTxn:
    txn_uid: str
    occurred_at: datetime
    source: str
    owner: str
    merchant: str
    description: str
    amount: int
    currency: str = "KRW"
    status: str = "posted"
    payment_method: str = ""
    raw_ref: str = ""


@dataclass
class Posting:
    txn_uid: str
    occurred_at: datetime
    account: str
    amount: int
    memo: str = ""


def make_uid(*parts: object) -> str:
    raw = "|".join(str(p) for p in parts)
    return f"{abs(hash(raw)) & 0xFFFFFFFFFFFF:012x}"


def pick_category(merchant: str, desc: str) -> str:
    text = f"{merchant} {desc}"
    for prio, pat, cat in sorted(CATEGORY_RULES, key=lambda x: x[0]):
        if re.search(pat, text, re.IGNORECASE):
            return EXP.get(cat, EXP["ETC"])
    return EXP["ETC"]


# Helper functions for union logic
def is_topup_like(merchant: str, desc: str) -> bool:
    text = f"{merchant} {desc}"
    return any(re.search(pat, text, re.IGNORECASE) for pat in TOPUP_PATTERNS)

def _parse_dt(date_str: str, time_str: str = "") -> Optional[datetime]:
    if not date_str:
        return None
    # Ensure date_str is YYYY-MM-DD
    date_str = date_str.replace("/", "-").strip()
    if not time_str or time_str.strip() == "":
        time_str = "00:00:00"
    
    time_str = time_str.strip()
    full_str = f"{date_str} {time_str}"
    
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H"):
        try:
            return datetime.strptime(full_str, fmt)
        except ValueError:
            continue
    
    # Try just date
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

def _owner_from_name(name: str, fallback: str = "taewoo") -> str:
    name = name.strip()
    if name in NAME_OWNER_MAP:
        return NAME_OWNER_MAP[name]
    return fallback

def detect_parser(path: str, content: bytes) -> str:
    # Base detection for legacy compatibility or quick dispatch
    filename = os.path.basename(path).lower()
    if "woori" in filename or "우리" in filename:
        return "bank"
    if "shinhancard" in filename or "shinhan" in filename or "신한" in filename:
        return "shinhan"
    if "hyundaicard" in filename or "hyundai" in filename or "현대" in filename:
        return "card"
    if "naverpay" in filename or "네이버페이" in filename:
        return "naverpay"
    if "경기지역화폐" in filename:
        return "gcpay"
    if "onnuri" in filename or "온누리" in filename:
        return "onnuri"
    if "corp_card" in filename or "법인카드" in filename:
        return "corp_card"

    # Fallback to content-based
    if content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "bank" 
    if path.endswith(".xlsx"):
        return "onnuri"
    text = content.decode("utf-8", errors="ignore")
    lower = text.lower()
    if "paymentitem_item-payment__" in lower or "__next_data__" in lower:
        return "naverpay"
    if "header__myname" in lower and "transaction-data" in lower:
        return "gcpay"
    if "승인일" in text and "승인시각" in text and "<table" in lower:
        return "card"
    if "승인ID" in text and "정산상태" in text and "카드번호" in text:
        return "corp_card"
    return "unknown"

def _to_std_txn(row: Dict[str, Any], source: str, owner: str) -> Optional[StdTxn]:
    date_str = row.get("날짜")
    time_str = row.get("시간") or ""
    if not date_str: 
        # print(f"  [Skip] No date in row: {row}")
        return None
    dt = _parse_dt(str(date_str), str(time_str))
    if not dt:
        print(f"  [Skip] Invalid datetime ({date_str} {time_str}) for row: {row}")
        return None
    
    amount = row.get("금액") or row.get("승인금액") or row.get("거래금액") or 0
    # Handle amounts that might be strings or have commas
    if isinstance(amount, str):
        amount = re.sub(r"[^\d\-]", "", amount)
        amount = int(amount) if amount else 0
    
    merchant = row.get("적요") or row.get("가맹점명") or row.get("가맹점") or row.get("내용") or row.get("상품명") or row.get("결제정보") or ""
    desc = row.get("기재내용") or row.get("거래구분") or row.get("승인구분") or row.get("상태") or row.get("액션") or ""
    
    # Use owner from row if available (parsers set this), otherwise use provided owner
    row_owner = row.get("owner") or owner
    
    uid = make_uid(source, row_owner, dt.isoformat(), merchant, amount)
    
    return StdTxn(
        txn_uid=uid,
        occurred_at=dt,
        source=source,
        owner=row_owner,
        merchant=str(_clean_text(str(merchant))),
        description=str(_clean_text(str(desc))),
        amount=int(amount),
        raw_ref=str(row)
    )

def _clean_text(text: str) -> str:
    from html import unescape
    return unescape(re.sub(r"<.*?>", "", text)).strip()

def _build_naverpay_index(
    rows: Iterable[Dict[str, object]]
) -> Dict[Tuple[str, int], List[Dict[str, object]]]:
    index: Dict[Tuple[str, int], List[Dict[str, object]]] = {}
    for row in rows:
        date_str = str(row.get("날짜", "")).strip()
        time_str = str(row.get("시간", "")).strip()
        dt = _parse_dt(date_str, time_str)
        amount = row.get("금액")
        if not dt or not isinstance(amount, int):
            continue
        key = (dt.strftime("%Y-%m-%d"), abs(amount))
        index.setdefault(key, []).append(row)
    return index

def enrich_with_naverpay(
    txns: List[StdTxn], naverpay_rows: List[Dict[str, object]]
) -> None:
    index = _build_naverpay_index(naverpay_rows)
    for txn in txns:
        if txn.source not in ("bank", "card"):
            continue
        text = f"{txn.merchant} {txn.description}".lower()
        if "네이버페이" not in text and "naverpay" not in text:
            continue
        key = (txn.occurred_at.strftime("%Y-%m-%d"), abs(txn.amount))
        candidates = index.get(key, [])
        if not candidates:
            continue
        candidates.sort(
            key=lambda r: abs(
                (
                    _parse_dt(str(r.get("날짜", "")), str(r.get("시간", "")))
                    - txn.occurred_at
                ).total_seconds()
            )
            if _parse_dt(str(r.get("날짜", "")), str(r.get("시간", "")))
            else 999999
        )
        match = candidates[0]
        product = str(match.get("상품명", "")).strip()
        status = str(match.get("상태", "")).strip()
        extras = " ".join(part for part in [product, status] if part)
        if extras and extras not in txn.description:
            txn.description = f"{txn.description} {extras}".strip()

def enrich_with_onnuri(
    txns: List[StdTxn], onnuri_rows: List[Dict[str, object]]
) -> None:
    index: Dict[str, List[Dict[str, object]]] = {}
    for row in onnuri_rows:
        dt = _parse_dt(row.get("날짜"), row.get("시간"))
        if not dt: continue
        key = dt.strftime("%Y-%m-%d")
        index.setdefault(key, []).append(row)

    for txn in txns:
        if txn.source != "bank": continue
        if "온누리충전" not in txn.merchant and "온누리충전" not in txn.description:
            continue
        key = txn.occurred_at.strftime("%Y-%m-%d")
        candidates = index.get(key, [])
        if not candidates: continue
        candidates.sort(
            key=lambda r: abs((_parse_dt(r.get("날짜"), r.get("시간")) - txn.occurred_at).total_seconds())
        )
        match = candidates[0]
        match_dt = _parse_dt(match.get("날짜"), match.get("시간"))
        if abs((match_dt - txn.occurred_at).total_seconds()) > 180:
            continue
        txn.merchant = str(match.get("가맹점")).strip()
        if "(Onnuri)" not in txn.description:
             txn.description = f"{txn.description} (Onnuri)".strip()


def build_postings(txns: List[StdTxn]) -> List[Posting]:
    postings: List[Posting] = []

    for t in txns:
        memo = f"{t.source}/{t.owner} {t.merchant} {t.description}".strip()

        if t.source == "bank":
            bank_acc = (
                ACCOUNTS["WOORI_TAEWOO"]
                if t.owner == "taewoo"
                else ACCOUNTS["WOORI_CHAEYOUNG"]
            )

            if t.amount < 0:
                if NAVERPAY_BANK_KEYWORD in t.merchant:
                    cat_acc = EXP["ETC"]
                    postings += [
                        Posting(t.txn_uid, t.occurred_at, bank_acc, t.amount, memo),
                        Posting(t.txn_uid, t.occurred_at, cat_acc, -t.amount, memo),
                    ]
                elif is_topup_like(t.merchant, t.description):
                    if re.search(r"경기지역화폐", f"{t.merchant} {t.description}"):
                        # Select tori account based on owner
                        wallet = ACCOUNTS["GC_PAY_CHAEYOUNG"] if t.owner == "chaeyoung" else ACCOUNTS["GC_PAY"]
                    elif re.search(r"온누리충전", f"{t.merchant} {t.description}"):
                        # Select onnuri account based on owner
                        wallet = ACCOUNTS["ONNURI_CHAEYOUNG"] if t.owner == "chaeyoung" else ACCOUNTS["ONNURI"]
                    else:
                        wallet = ACCOUNTS["WOORI_CHAEYOUNG"] if t.owner == "chaeyoung" else ACCOUNTS["WOORI_TAEWOO"] # Fallback to other account
                    postings += [
                        Posting(t.txn_uid, t.occurred_at, bank_acc, t.amount, memo),
                        Posting(t.txn_uid, t.occurred_at, wallet, -t.amount, memo),
                    ]
                else:
                    cat_acc = pick_category(t.merchant, t.description)
                    postings += [
                        Posting(t.txn_uid, t.occurred_at, bank_acc, t.amount, memo),
                        Posting(t.txn_uid, t.occurred_at, cat_acc, -t.amount, memo),
                    ]
            elif t.amount > 0:
                postings += [
                    Posting(t.txn_uid, t.occurred_at, bank_acc, t.amount, memo),
                    Posting(t.txn_uid, t.occurred_at, INC["INCOME"], -t.amount, memo),
                ]
            else:
                continue

        elif t.source == "card":
            card_acc = ACCOUNTS["HYUNDAI_CARD"]

            if re.search(r"모바일티머니선불형", t.merchant):
                amt = abs(t.amount)
                tmoney_acc = ACCOUNTS.get("TMONEY", "현금")
                postings += [
                    Posting(t.txn_uid, t.occurred_at, card_acc, amt, memo),
                    Posting(t.txn_uid, t.occurred_at, tmoney_acc, -amt, memo),
                ]
                continue

            if t.status == "canceled":
                cat_acc = pick_category(t.merchant, t.description)
                postings += [
                    Posting(t.txn_uid, t.occurred_at, card_acc, -abs(t.amount), memo),
                    Posting(t.txn_uid, t.occurred_at, cat_acc, abs(t.amount), memo),
                ]
            else:
                cat_acc = pick_category(t.merchant, t.description)
                postings += [
                    Posting(t.txn_uid, t.occurred_at, card_acc, abs(t.amount), memo),
                    Posting(t.txn_uid, t.occurred_at, cat_acc, -abs(t.amount), memo),
                ]

        elif t.source == "shinhan":
            card_acc = ACCOUNTS["SHINHAN_CARD"]
            
            if t.status == "canceled":
                cat_acc = pick_category(t.merchant, t.description)
                postings += [
                    Posting(t.txn_uid, t.occurred_at, card_acc, -abs(t.amount), memo),
                    Posting(t.txn_uid, t.occurred_at, cat_acc, abs(t.amount), memo),
                ]
            else:
                cat_acc = pick_category(t.merchant, t.description)
                postings += [
                    Posting(t.txn_uid, t.occurred_at, card_acc, abs(t.amount), memo),
                    Posting(t.txn_uid, t.occurred_at, cat_acc, -abs(t.amount), memo),
                ]

        elif t.source == "naverpay":
            points_acc = ACCOUNTS["NAVERPAY_POINTS_TAEWOO"]
            money_acc = ACCOUNTS["NAVERPAY_MONEY_TAEWOO"]
            
            if t.payment_method == "points":
                # point: 하나의 통장처럼 활용
                cat_acc = pick_category(t.merchant, t.description)
                postings += [
                    Posting(t.txn_uid, t.occurred_at, points_acc, t.amount, memo),
                    Posting(t.txn_uid, t.occurred_at, cat_acc, -t.amount, memo),
                ]
            elif t.payment_method == "money":
                # money: 하나의 통장처럼 활용
                cat_acc = pick_category(t.merchant, t.description)
                postings += [
                    Posting(t.txn_uid, t.occurred_at, money_acc, t.amount, memo),
                    Posting(t.txn_uid, t.occurred_at, cat_acc, -t.amount, memo),
                ]
            else:
                continue

        elif t.source == "tori":
            # Select wallet account based on owner
            wallet = ACCOUNTS["GC_PAY_CHAEYOUNG"] if t.owner == "chaeyoung" else ACCOUNTS["GC_PAY"]

            if t.payment_method == "topup":
                postings += [
                    Posting(t.txn_uid, t.occurred_at, wallet, t.amount, memo),
                    Posting(t.txn_uid, t.occurred_at, ACCOUNTS["EXTERNAL"], -t.amount, memo),
                ]
            elif t.payment_method == "incentive":
                # Tori incentive: wallet receives bonus from income
                postings += [
                    Posting(t.txn_uid, t.occurred_at, wallet, t.amount, memo),
                    Posting(t.txn_uid, t.occurred_at, INC["INCOME"], -t.amount, memo),
                ]
            else:
                cat_acc = pick_category(t.merchant, t.description)
                postings += [
                    Posting(t.txn_uid, t.occurred_at, wallet, t.amount, memo),
                    Posting(t.txn_uid, t.occurred_at, cat_acc, -t.amount, memo),
                ]

        elif t.source == "corp_card":
            card_acc = ACCOUNTS["CORP_CARD"]
            cat_acc = pick_category(t.merchant, t.description)
            postings += [
                Posting(t.txn_uid, t.occurred_at, card_acc, abs(t.amount), memo),
                Posting(t.txn_uid, t.occurred_at, cat_acc, -abs(t.amount), memo),
            ]

        elif t.source == "onnuri":
            onnuri_acc = ACCOUNTS["ONNURI_CHAEYOUNG"] if t.owner == "chaeyoung" else ACCOUNTS["ONNURI"]
            
            if t.payment_method == "incentive":
                postings += [
                    Posting(t.txn_uid, t.occurred_at, onnuri_acc, t.amount, memo),
                    Posting(t.txn_uid, t.occurred_at, INC["INCOME"], -t.amount, memo),
                ]
            else:
                cat_acc = pick_category(t.merchant, t.description)
                amt = abs(t.amount)
                postings += [
                    Posting(t.txn_uid, t.occurred_at, cat_acc, amt, memo),
                    Posting(t.txn_uid, t.occurred_at, onnuri_acc, -amt, memo),
                ]

        elif t.source == "transfer":
            # Internal transfers (bank to bank, bank to naver_money, bank to tori, etc.)
            if "INTERNAL_TRANSFER" in t.merchant:
                # Bank to bank transfer between owners
                # Parse from_owner and to_owner from merchant: "INTERNAL_TRANSFER:taewoo->chaeyoung"
                match = re.search(r"INTERNAL_TRANSFER:(\w+)->(\w+)", t.merchant)
                if match:
                    from_owner, to_owner = match.groups()
                    from_bank = ACCOUNTS["WOORI_TAEWOO"] if from_owner == "taewoo" else ACCOUNTS["WOORI_CHAEYOUNG"]
                    to_bank = ACCOUNTS["WOORI_TAEWOO"] if to_owner == "taewoo" else ACCOUNTS["WOORI_CHAEYOUNG"]
                    # from_bank decreases (negative), to_bank increases (positive)
                    postings += [
                        Posting(t.txn_uid, t.occurred_at, to_bank, abs(t.amount), memo),  # Left: receiving account increases
                        Posting(t.txn_uid, t.occurred_at, from_bank, t.amount, memo),  # Right: sending account decreases
                    ]
                else:
                    # Fallback: use owner to determine
                    from_bank = ACCOUNTS["WOORI_TAEWOO"] if t.owner == "taewoo" else ACCOUNTS["WOORI_CHAEYOUNG"]
                    to_bank = ACCOUNTS["WOORI_CHAEYOUNG"] if t.owner == "taewoo" else ACCOUNTS["WOORI_TAEWOO"]
                    postings += [
                        Posting(t.txn_uid, t.occurred_at, to_bank, abs(t.amount), memo),
                        Posting(t.txn_uid, t.occurred_at, from_bank, t.amount, memo),
                    ]
            else:
                # Other transfers (bank to naver_money, bank to tori, etc.)
                # merchant contains the destination (e.g., "NAVER_MONEY_TOPUP", "TORI_TOPUP")
                bank_acc = ACCOUNTS.get(f"WOORI_{t.owner.upper()}", ACCOUNTS["WOORI_TAEWOO"])
                
                if "NAVER_MONEY" in t.merchant:
                    dest_acc = ACCOUNTS["NAVERPAY_MONEY_TAEWOO"]
                elif "TORI" in t.merchant or "경기지역화폐" in t.description:
                    # Select tori account based on owner
                    dest_acc = ACCOUNTS["GC_PAY_CHAEYOUNG"] if t.owner == "chaeyoung" else ACCOUNTS["GC_PAY"]
                elif "ONNURI" in t.merchant or "온누리" in t.merchant or "온누리" in t.description:
                    # Select onnuri account based on owner
                    dest_acc = ACCOUNTS["ONNURI_CHAEYOUNG"] if t.owner == "chaeyoung" else ACCOUNTS["ONNURI"]
                else:
                    # Default: transfer to other owner's account
                    dest_acc = ACCOUNTS["WOORI_CHAEYOUNG"] if t.owner == "taewoo" else ACCOUNTS["WOORI_TAEWOO"]
                
                postings += [
                    Posting(t.txn_uid, t.occurred_at, dest_acc, abs(t.amount), memo),  # Left: destination account increases
                    Posting(t.txn_uid, t.occurred_at, bank_acc, t.amount, memo),  # Right: source account decreases
                ]

    return postings


def match_internal_transfers(txns: List[StdTxn]) -> List[StdTxn]:
    bank_txns = [t for t in txns if t.source == "bank"]
    others = [t for t in txns if t.source != "bank"]

    bank_txns_sorted = sorted(bank_txns, key=lambda x: x.occurred_at)
    used = set()
    merged: List[StdTxn] = []

    def score(a: StdTxn, b: StdTxn) -> int:
        sc = 0
        ta = f"{a.merchant} {a.description}"
        tb = f"{b.merchant} {b.description}"
        if ("서채영" in ta and "이태우" in tb) or ("이태우" in ta and "서채영" in tb):
            sc += 3
        if "토스" in ta or "토스" in tb:
            sc += 1
        return sc

    for i, a in enumerate(bank_txns_sorted):
        if a.txn_uid in used:
            continue
        if a.amount == 0:
            continue
        best = None
        best_sc = -1
        for j in range(i + 1, min(i + 50, len(bank_txns_sorted))):
            b = bank_txns_sorted[j]
            if b.txn_uid in used:
                continue
            if a.owner == b.owner:
                continue
            if abs(a.amount) != abs(b.amount):
                continue
            if a.amount * b.amount >= 0:
                continue
            if abs((b.occurred_at - a.occurred_at).total_seconds()) > 600:
                continue
            sc = score(a, b)
            if sc > best_sc:
                best_sc = sc
                best = b

        if best and best_sc >= 1:
            used.add(a.txn_uid)
            used.add(best.txn_uid)
            dt = a.occurred_at if a.amount < 0 else best.occurred_at
            amt = abs(a.amount)
            if a.amount < 0:
                from_owner, to_owner = a.owner, best.owner
            else:
                from_owner, to_owner = best.owner, a.owner
            txn_uid = make_uid("xfer", from_owner, to_owner, dt.isoformat(), amt)
            merged.append(
                StdTxn(
                    txn_uid=txn_uid,
                    occurred_at=dt,
                    source="transfer",
                    owner=from_owner,
                    merchant=f"INTERNAL_TRANSFER:{from_owner}->{to_owner}",
                    description="merged_internal_transfer",
                    amount=-amt,
                    status="posted",
                    payment_method="transfer",
                    raw_ref=f"{a.raw_ref} || {best.raw_ref}",
                )
            )
    # 2. Match Bank to NaverPay Money (Topups)
    naver_money_txns = [t for t in txns if t.source == "naverpay" and t.payment_method == "money" and t.amount > 0]
    for n in naver_money_txns:
        if n.txn_uid in used: continue
        # Find matching withdrawal from bank
        best_b = None
        for b in bank_txns:
            if b.txn_uid in used: continue
            if b.amount > 0: continue
            if abs(b.amount) != abs(n.amount): continue
            if abs((b.occurred_at - n.occurred_at).total_seconds()) > 1800: continue # 30 min window
            # If bank transaction contains "네이버", its likely a match
            if "네이버" in b.merchant or "네이버" in b.description:
                best_b = b
                break
        
        if best_b:
            used.add(n.txn_uid)
            used.add(best_b.txn_uid)
            dt = best_b.occurred_at
            amt = abs(n.amount)
            owner = n.owner
            txn_uid = make_uid("xfer_np", owner, dt.isoformat(), amt)
            merged.append(
                StdTxn(
                    txn_uid=txn_uid,
                    occurred_at=dt,
                    source="transfer",
                    owner=owner,
                    merchant=f"NAVER_MONEY_TOPUP",
                    description=f"from {best_b.source} to naver_money",
                    amount=-amt, # Spending from bank
                    status="posted",
                    payment_method="transfer",
                    raw_ref=f"{n.raw_ref} || {best_b.raw_ref}",
                )
            )

    # 3. Match Bank to Tori (GCPay) Topups
    tori_txns = [t for t in txns if t.source == "tori" and t.amount > 0 and "충전" in t.description]
    for tori_tx in tori_txns:
        if tori_tx.txn_uid in used: continue
        # Find matching withdrawal from bank
        best_b = None
        for b in bank_txns:
            if b.txn_uid in used: continue
            if b.amount >= 0: continue  # Must be withdrawal
            if abs(b.amount) != abs(tori_tx.amount): continue
            if abs((b.occurred_at - tori_tx.occurred_at).total_seconds()) > 7200: continue  # 2 hour window
            # Check if bank transaction mentions tori/경기지역화폐
            if "토리" in b.merchant or "토리" in b.description or "경기지역화폐" in b.merchant or "경기지역화폐" in b.description:
                best_b = b
                break
        
        if best_b:
            used.add(tori_tx.txn_uid)
            used.add(best_b.txn_uid)
            dt = best_b.occurred_at
            amt = abs(tori_tx.amount)
            owner = tori_tx.owner
            txn_uid = make_uid("xfer_tori", owner, dt.isoformat(), amt)
            merged.append(
                StdTxn(
                    txn_uid=txn_uid,
                    occurred_at=dt,
                    source="transfer",
                    owner=owner,
                    merchant=f"TORI_TOPUP",
                    description=f"from {best_b.source} to tori",
                    amount=-amt,  # Spending from bank
                    status="posted",
                    payment_method="transfer",
                    raw_ref=f"{tori_tx.raw_ref} || {best_b.raw_ref}",
                )
            )
            
            # Extract incentive from tori transaction memo if present
            # Format: "인센티브24,000원" or "인센티브 24,000원"
            incentive_match = re.search(r"인센티브\s*([0-9,]+)원", str(tori_tx.raw_ref))
            if incentive_match:
                incentive_amt = int(incentive_match.group(1).replace(",", ""))
                incentive_uid = make_uid("tori_incentive", owner, dt.isoformat(), incentive_amt)
                merged.append(
                    StdTxn(
                        txn_uid=incentive_uid,
                        occurred_at=tori_tx.occurred_at,
                        source="tori",
                        owner=owner,
                        merchant="토리 인센티브",
                        description="충전 인센티브",
                        amount=incentive_amt,
                        status="posted",
                        payment_method="incentive",
                        raw_ref=f"Incentive from: {tori_tx.raw_ref}",
                    )
                )

    # 4. Match Bank to Onnuri Topups
    # Onnuri topups appear only in bank transactions with "온누리충전" keyword
    # The topup amount is withdrawal × 10/9 (1/9 incentive)
    for b in bank_txns:
        if b.txn_uid in used: continue
        if b.amount >= 0: continue  # Must be withdrawal
        
        # Check if this is an Onnuri topup
        combined_text = f"{b.merchant} {b.description}"
        if "온누리충전" in combined_text or "온누리" in combined_text:
            used.add(b.txn_uid)
            dt = b.occurred_at
            withdrawal_amt = abs(b.amount)
            topup_amt = int(withdrawal_amt * 10 / 9)  # Add 1/9 incentive
            incentive_amt = topup_amt - withdrawal_amt
            owner = b.owner
            
            # Create transfer transaction
            txn_uid = make_uid("xfer_onnuri", owner, dt.isoformat(), withdrawal_amt)
            merged.append(
                StdTxn(
                    txn_uid=txn_uid,
                    occurred_at=dt,
                    source="transfer",
                    owner=owner,
                    merchant="ONNURI_TOPUP",
                    description=f"from {b.source} to onnuri",
                    amount=-withdrawal_amt,
                    status="posted",
                    payment_method="transfer",
                    raw_ref=f"Onnuri topup: {b.raw_ref}",
                )
            )
            
            # Create incentive transaction
            if incentive_amt > 0:
                incentive_uid = make_uid("onnuri_incentive", owner, dt.isoformat(), incentive_amt)
                merged.append(
                    StdTxn(
                        txn_uid=incentive_uid,
                        occurred_at=dt,
                        source="onnuri",
                        owner=owner,
                        merchant="온누리 인센티브",
                        description="충전 인센티브",
                        amount=incentive_amt,
                        status="posted",
                        payment_method="incentive",
                        raw_ref=f"Incentive from: {b.raw_ref}",
                    )
                )

    # 5. Collect unmatched
    for t in txns:
        if t.txn_uid not in used:
            merged.append(t)
    
    return merged


def _write_csv(path: str, rows: Iterable[Dict[str, object]], fieldnames: List[str]) -> None:
    # Organize columns as [날짜, 아이템, 금액, 왼쪽, 오른쪽, 메모, 시간]
    target_headers = ["날짜", "아이템", "금액", "왼쪽", "오른쪽", "메모", "시간"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=target_headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

def build_whooing_rows(postings: List[Posting], config: Dict[str, str] = None) -> List[Dict[str, Any]]:
    """
    Groups postings by txn_uid and builds rows for whooing_upload_final.xlsx.
    Strict Rules:
    - Expenses (비용) -> Left
    - Income (수익) -> Right
    - Assets/Liabilities (자산/부채) -> Left (Increase) / Right (Decrease)
    """
    if config is None:
        config = load_whooing_config()
    
    txns_map: Dict[str, List[Posting]] = {}
    for p in postings:
        txns_map.setdefault(p.txn_uid, []).append(p)
    
    rows = []
    
    for txn_uid, ps in txns_map.items():
        if len(ps) < 2: continue
        
        # Valid account check
        is_valid = True
        for p in ps:
            if p.account not in config:
                print(f"  [Warning] Account name '{p.account}' not found in whooing_setting.xlsx. Skipping transaction {txn_uid}.")
                is_valid = False
                break
        if not is_valid: continue

        left_cand = []
        right_cand = []
        
        # Determine side based on Whooing rules
        for p in ps:
            acc_type = config.get(p.account, "자산")
            
            if acc_type == "비용":
                left_cand.append(p)
            elif acc_type == "수익":
                right_cand.append(p)
            elif acc_type in ("자산", "부채", "순자산"):
                # For balance sheet items, side depends on increase/decrease
                if p.amount > 0:
                    left_cand.append(p)
                else:
                    right_cand.append(p)
            else:
                # Default behavior
                if p.amount > 0: left_cand.append(p)
                else: right_cand.append(p)
        
        # We need at least one on each side to create a valid Whooing row.
        # Most transactions are 1:1. For 1:N or N:1 we can generate multiple rows.
        if not left_cand or not right_cand:
            # Maybe the signs were flipped or categories are both restricted to one side.
            # This can happen if internal transfer logic is wrong.
            continue
            
        # Match them up. Simple N:M product for now or just zip.
        # For bulk upload, it's safer to use the larger list and repeat the other if singular.
        num_rows = max(len(left_cand), len(right_cand))
        for i in range(num_rows):
            l = left_cand[i % len(left_cand)]
            r = right_cand[i % len(right_cand)]
            
            rows.append({
                "날짜": l.occurred_at.strftime("%Y-%m-%d"),
                "아이템": l.memo.split('/')[-1].split(' ')[0], 
                "금액": abs(l.amount),
                "왼쪽": l.account,
                "오른쪽": r.account,
                "메모": l.memo,
                "시간": l.occurred_at.strftime("%H:%M:%S"),
            })
    
    rows.sort(key=lambda r: (r["날짜"], r["시간"]))
    return rows

def _std_txns_to_dict_list(txns: List[StdTxn]) -> List[Dict[str, Any]]:
    return [
        {
            "txn_uid": t.txn_uid,
            "occurred_at": t.occurred_at.isoformat(),
            "source": t.source,
            "owner": t.owner,
            "merchant": t.merchant,
            "description": t.description,
            "amount": t.amount,
            "payment_method": t.payment_method,
        }
        for t in txns
    ]

def main() -> None:
    invoice_dir = "invoices"
    debug_dir = "debug"
    os.makedirs(debug_dir, exist_ok=True)
    
    txns: List[StdTxn] = []
    naverpay_files: List[str] = []
    onnuri_rows: List[Dict[str, object]] = []
    for filename in sorted(os.listdir(invoice_dir)):
        path = os.path.join(invoice_dir, filename)
        if not os.path.isfile(path): continue
        
        # Determine owner from filename (Tae-woo's vs Chae-young's)
        # For bank files, let parser determine owner from account number
        owner = "taewoo" if "태우" in filename or "tw" in filename.lower() else "chaeyoung" if "채영" in filename or "cy" in filename.lower() else "taewoo"

        with open(path, "rb") as f:
            content = f.read()
            
        kind = detect_parser(path, content)
        print(f"[{kind}] Processing {path}...")
        
        current_rows = []
        if kind == "bank":
            # Bank parser determines owner from account number in the file
            current_rows = woori_bank.parse(path, None)
        elif kind == "card":
            current_rows = hyundai_card.parse(path, None)  # Card parser determines owner from card number
        elif kind == "shinhan":
            current_rows = shinhan_card.parse(path, None)  # Card parser determines owner from card number
        elif kind == "corp_card":
            current_rows = corp_card.parse(path, owner)
        elif kind == "gcpay":
            current_rows = gcpay.parse(path, None)  # GCPay parser determines owner from name in HTML
        elif kind == "onnuri":
            current_rows = onnuri.parse(path, owner)
            onnuri_rows.extend(current_rows)
        elif kind == "naverpay":
            # naverpay_rows for enrichment
            naverpay_files.append((path, owner))
            continue
        else:
            print(f"  -> Unknown kind, skipped")
            continue

        print(f"  -> Extracted {len(current_rows)} {kind} rows")
        
        # Save to debug folder
        if current_rows:
            debug_path = os.path.join(debug_dir, f"{filename}.csv")
            pd.DataFrame(current_rows).to_csv(debug_path, index=False, encoding="utf-8-sig")
            
        if kind != "onnuri":
            std_list = list(filter(None, [_to_std_txn(r, kind if kind != 'gcpay' else 'tori', owner) for r in current_rows]))
            txns.extend(std_list)

    if naverpay_files:
        # Collect all types of naverpay rows
        all_np_rows = []
        for path, owner in naverpay_files:
            rows = naverpay.parse(path, owner)
            all_np_rows.extend(rows)
            # Save debug for Naver Pay
            filename = os.path.basename(path)
            debug_path = os.path.join(debug_dir, f"{filename}.csv")
            pd.DataFrame(rows).to_csv(debug_path, index=False, encoding="utf-8-sig")
        
        # Enrich bank/card txns using payments_pc
        enrich_with_naverpay(txns, [r for r in all_np_rows if "payments" in str(r.get("raw_ref", "")) or r.get("source") == "payments"])
        
        # Add point/money as separate txns
        added_np_txns = 0
        for r in all_np_rows:
            method = r.get("method")
            if method in ("points", "money"):
                dt = _parse_dt(str(r["날짜"]), str(r["시간"]))
                if not dt: continue
                txns.append(StdTxn(
                    txn_uid=make_uid("np", r["owner"], dt.isoformat(), r["상품명"], r["금액"]),
                    occurred_at=dt,
                    source="naverpay",
                    owner=r["owner"],
                    merchant=str(r["상품명"]),
                    description=str(r["상태"]),
                    amount=int(r["금액"] if r.get("상태") != "충전" else -r["금액"]), # Heuristic: expense if not charging
                    payment_method=method,
                    raw_ref=str(r)
                ))
                added_np_txns += 1
        print(f"  -> Added {added_np_txns} Naver Pay (points/money) transactions")

    if onnuri_rows:
        enrich_with_onnuri(txns, onnuri_rows)
        
        added_onnuri_txns = 0
        for r in onnuri_rows:
            merchant_str = str(r.get("가맹점", ""))
            if "인센티브" in merchant_str:
                continue
            dt = _parse_dt(str(r["날짜"]), str(r["시간"]))
            if not dt: 
                continue
            amount_val = r["금액"]
            amount = int(amount_val) if amount_val is not None else 0
            status = str(r.get("상태", ""))
            if status in ["결제", "사용"]:
                amount = -abs(amount)
            elif status in ["취소", "환불", "입금"]:
                amount = abs(amount)
            owner_str = str(r.get("owner", "unknown"))
            txns.append(StdTxn(
                txn_uid=make_uid("onnuri", owner_str, dt.isoformat(), merchant_str, amount),
                occurred_at=dt,
                source="onnuri",
                owner=owner_str,
                merchant=merchant_str,
                description=status,
                amount=amount,
                payment_method="onnuri",
                raw_ref=str(r)
            ))
            added_onnuri_txns += 1
        print(f"  -> Added {added_onnuri_txns} Onnuri usage transactions")

    print(f"Post-enrichment total: {len(txns)} transactions")
    txns = match_internal_transfers(txns)
    print(f"Post-matching total: {len(txns)} transactions")

    # Sort transactions by datetime (oldest first)
    txns.sort(key=lambda t: t.occurred_at)

    postings = build_postings(txns)
    print(f"Generated {len(postings)} postings")
    
    # Sort postings by datetime (oldest first)
    postings.sort(key=lambda p: p.occurred_at)

    # Final conversion to Whooing Excel format
    whooing_conf = load_whooing_config()
    w_rows = build_whooing_rows(postings, whooing_conf)
    _write_csv("whooing_postings.csv", w_rows, [])
    
    print("Converting postings to Whooing Excel format...")
    convert_to_whooing_excel(
        w_rows, # Changed from "whooing_postings.csv" to w_rows
        "assets/whooing_default.xlsx", # Added this argument
        "whooing_upload_final.xlsx"
    )

    # Output intermediate for reference
    final_txns_dicts = _std_txns_to_dict_list(txns)
    if final_txns_dicts:
        pd.DataFrame(final_txns_dicts).to_csv("final_transactions.csv", index=False, encoding="utf-8-sig")

    print(f"Done. Generated whooing_upload_final.xlsx")

if __name__ == "__main__":
    main()
