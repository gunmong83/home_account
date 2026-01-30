"""
Whooing Transaction Partitioning & Classification Rules
This file contains the mapping between transaction keywords and Whooing account names.
Users can easily add or modify rules here to improve classification accuracy.
"""

# Account Mappings
# These names must exactly match the '항목명' in assets/whooing_setting.xlsx
ACCOUNTS = {
    "WOORI_TAEWOO": "우리은행태우",
    "WOORI_CHAEYOUNG": "우리은행채영",
    "HYUNDAI_CARD_TAEWOO": "신용카드태우",
    "HYUNDAI_CARD_CHAEYOUNG": "신용카드채영",
    "SHINHAN_CARD_TAEWOO": "신용카드태우",
    "SHINHAN_CARD_CHAEYOUNG": "신용카드채영",
    "NAVERPAY_POINTS_TAEWOO": "네이버포인트",
    "NAVERPAY_MONEY_TAEWOO": "네이버머니",
    "CASH": "현금",
    "ONNURI": "온누리태우",
    "ONNURI_CHAEYOUNG": "온누리채영",
    "GC_PAY": "토리태우",
    "GC_PAY_CHAEYOUNG": "토리채영",
    "CORP_CARD": "개인업무지원비",
    "EXTERNAL": "기타수익", # Fallback for external income/transfer
}

# Expense (비용) Categories
EXP = {
    "LIFE_INTERIOR": "일회성지출",
    "LIFE_COSMETICS": "화장품",
    "LIFE_TOYS": "장난감",
    "LIFE_CLOTHING_TAEWOO": "의류태우",
    "LIFE_DAILY": "일회성지출",
    
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
    
    # Food
    "FOOD_GROCERIES": "장보기",
    "FOOD_DELIVERY": "배달",
    "FOOD_CAFE": "카페",
    "FOOD_EATING_OUT": "외식",

    # Fixed
    "FIXED_SUBSCRIPTION": "구독료",
    "FIXED_LOAN_INTEREST": "대출이자",
    "FIXED_MANAGEMENT": "관리비",
    "FIXED_COMMUNICATION": "통신비",
    "FIXED_INSURANCE": "보험",

    # Transport
    "TRANSPORT_FUEL": "일회성지출",
    "TRANSPORT_PUBLIC": "일회성지출",
    "TRANSPORT_TOLL": "일회성지출",
    "TRANSPORT_MAINTENANCE": "일회성지출",
    
    # Default
    "ETC": "일회성지출",
}

# Income (수익) Categories
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

# Classification Rules (Priority, Regex Pattern, Category Key)
# Priority: Lower number means higher priority.
CATEGORY_RULES = [
    # Fixed Costs & Subscriptions
    (1, r"Apple Services|App Store|iTunes|Adobe|넷플릭스|유튜브|YouTube|Google|Coupang Wow|Skt우주", "FIXED_SUBSCRIPTION"),
    (1, r"대출이자|이자", "FIXED_LOAN_INTEREST"),
    (1, r"관리비|삼천리도시가스|한전|한국전력|가스", "FIXED_MANAGEMENT"), 
    (1, r"SKT|KT|LG U\+|통신|인터넷", "FIXED_COMMUNICATION"),
    (1, r"보험|현대해상|삼성화재|DB손해|교보생명|메리츠", "FIXED_INSURANCE"),
    
    # Transportation
    (1, r"주유|SK에너지|GS칼텍스|HD현대오일|S-OIL", "TRANSPORT_FUEL"),
    (1, r"티머니|버스|지하철|후불교통|코레일|SRT", "TRANSPORT_PUBLIC"),
    (1, r"한국도로공사|하이패스|고속도로|연결고속도로", "TRANSPORT_TOLL"),
    (1, r"공업사|정비|타이어|블루핸즈|오토큐", "TRANSPORT_MAINTENANCE"),

    # Shopping & Life
    (2, r"이케아|IKEA|한샘|리바트|다이소|모던하우스", "LIFE_INTERIOR"),
    (2, r"올리브영|Olive Young|화장품|이니스프리", "LIFE_COSMETICS"),
    (2, r"장난감|토이|키즈|문구|알파|모닝글로리", "LIFE_TOYS"),
    (2, r"무신사|유니클로|ZARA|H&M|나이키|아디다스|의류|패션|탑텐", "LIFE_CLOTHING_TAEWOO"),
    (2, r"쿠팡|Coupang|네이버페이|G마켓|옥션|11번가|Amazon|당근|스마트스토어", "LIFE_DAILY"), 
    (2, r"클라이밍|헬스|운동|체육센터", "CULTURE_LEISURE"),
    
    # Food & Dining
    (2, r"과천식자재마트|도시곳간|지에스 더 프레|GS|CU|세븐일레븐|이마트|홈플러스|롯데마트|컬리|SSG|하나로마트|농협", "FOOD_GROCERIES"),
    (2, r"우아한형제들|배달|땡겨요|요기요|배달의민족", "FOOD_DELIVERY"),
    (2, r"스타벅스|카페|커피|투썸|이디야|폴바셋|메가커피|컴포즈", "FOOD_CAFE"),
    (2, r"식당|음식|레스토랑|맥도날드|버거킹|써브웨이|김밥|스파게티|한우|갈비", "FOOD_EATING_OUT"),

    # Health & Medical
    (2, r"피부과|내과|의원|병원|치과|안과|산부인과|한의원", "HEALTH_HOSPITAL"),
    (2, r"약국", "HEALTH_PHARMACY"),

    # Education
    (2, r"학원|아카데미|교습소", "EDU_ACADEMY"),
    (2, r"서점|알라딘|교보문고|YES24|영풍문고", "EDU_MATERIALS"),

    # Culture & Events
    (2, r"CGV|롯데시네마|메가박스|영화|전시|박물관", "CULTURE_LEISURE"),
    (2, r"축의금|조의금|장례|웨딩", "CULTURE_EVENTS"),
]

# Patterns that indicate a wallet top-up (not an expense)
TOPUP_PATTERNS = [
    r"경기지역화폐",
    r"온누리충전",
    r"모바일티머니선불형|티머니\s*$",
    r"네이버페이\s*충전|하나\(\d+\*+\d+\)",
]

# Generic banking terms to strip from item labels
GENERIC_BANK_TERMS = {
    "체크우리", "펌뱅킹", "타행건별", "오픈뱅킹", "체크", "출금", "입금", "대체", "인터넷", 
    "모바일", "토스", "토스페이", "카카오페이", "네이버페이결제", "현금", "F/B 출금", "F/B 입금",
    "타행대량", "계좌이체", "예금결산", "예금이자", "예금", "적요", "내용", "오픈",
}
