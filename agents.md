# Transaction Analysis System - Agents & Architecture

## 프로젝트 개요

이 프로젝트는 여러 금융 자산(은행 계좌, 신용카드, 지역화폐, 네이버페이 등)의 거래 내역을 통합하여 발생주의 복식부기 회계 트랜잭션을 생성하는 시스템입니다. 최종적으로 Whooing 회계 시스템에 업로드 가능한 형식으로 변환합니다.

### 주요 목적
- 다양한 금융 자산의 거래 내역 파싱 및 통합
- 발생주의 복식부기 회계 원칙 적용
- Whooing 회계 시스템과의 연동
- 두 명의 사용자(태우, 채영)의 거래 분리 및 관리

---

## 시스템 아키텍처

### 디렉토리 구조

```
transaction_anal/
├── parser/              # 거래 내역 파서 모듈
│   ├── woori_bank.py    # 우리은행 통장 파서
│   ├── hyundai_card.py  # 현대카드 파서
│   ├── shinhan_card.py  # 신한카드 파서
│   ├── corp_card.py     # 법인카드 파서
│   ├── gcpay.py         # 경기지역화폐(토리) 파서
│   ├── onnuri.py        # 온누리 상품권 파서
│   └── naverpay.py      # 네이버페이 파서 (HTML 파싱)
├── crawler/             # 웹 크롤링 모듈
│   └── naverpay.py      # 네이버페이 브라우저 크롤러
├── assets/              # 설정 파일
│   ├── whooing_setting.xlsx    # Whooing 계정 설정
│   └── whooing_default.xlsx     # Whooing 업로드 템플릿
├── invoices/            # 원본 거래 내역 파일
├── debug/               # 파싱 중간 결과물 (CSV)
├── union.py             # 메인 통합 모듈
├── calibrator.py        # 분류 규칙 보정 도구
├── whooing_converter.py # Whooing 형식 변환기
└── config.py           # 전역 설정

```

---

## 핵심 컴포넌트

### 1. Parser 모듈 (`parser/`)

각 파서는 독립적으로 실행 가능하며, CSV 출력을 지원합니다.

#### 주요 파서

**woori_bank.py**
- 우리은행 통장 거래 내역 파싱
- Excel/HTML 형식 지원
- 출금/입금 구분 및 잔액 처리
- 토리/온누리 충전 거래 감지 (키워드 기반)

**hyundai_card.py / shinhan_card.py**
- 신용카드 거래 내역 파싱
- 카드번호 기반 owner 자동 감지 (태우/채영)
- 승인일시, 가맹점명, 금액 추출

**gcpay.py**
- 경기지역화폐(토리) 거래 파싱
- 이름 기반 owner 매핑 (이태우 → taewoo, 서채영 → chaeyoung)
- 충전 거래 및 인센티브 정보 추출

**onnuri.py**
- 온누리 상품권 거래 파싱
- 결제 내역 추출

**naverpay.py**
- 네이버페이 HTML 파일 파싱
- 3가지 타입 지원:
  - `payments_pc`: 결제 내역 (정보 보강용)
  - `points`: 포인트 거래
  - `money`: 머니 거래

### 2. Crawler 모듈 (`crawler/`)

**naverpay.py**
- Selenium 기반 브라우저 자동화
- 네이버페이 로그인 및 데이터 수집
- 설정 가능한 페이지 수 및 스크롤 횟수
- Owner별 데이터 수집 (taewoo/chaeyoung)

### 3. Union 모듈 (`union.py`)

거래 내역을 통합하고 복식부기 트랜잭션을 생성하는 핵심 모듈입니다.

#### 주요 함수

**`detect_parser(path, content)`**
- 파일 경로와 내용을 분석하여 적절한 파서 선택

**`_to_std_txn(row, source, owner)`**
- 파서 출력을 표준 트랜잭션 형식(`StdTxn`)으로 변환
- 날짜/시간 파싱 및 정규화

**`enrich_with_naverpay(txns, np_payments)`**
- 네이버페이 결제 정보로 은행/카드 거래 보강
- 날짜, 시간, 금액 매칭으로 상세 정보 추가

**`enrich_with_onnuri(txns, onnuri_rows)`**
- 온누리 거래 정보로 은행 거래 보강

**`match_internal_transfers(txns)`**
- 내부 계좌 간 이체 거래 매칭 및 통합
- 지원하는 이체 유형:
  - 우리은행 태우 ↔ 채영 계좌 이체
  - 네이버페이 머니 충전 (우리은행 → 네이버머니)
  - 토리 충전 (우리은행 → 토리태우)
  - 온누리 충전 (우리은행 → 온누리태우)

**`build_postings(txns)`**
- 표준 트랜잭션을 복식부기 포스팅으로 변환
- 계정 매핑 및 분류 규칙 적용
- 복식부기 원칙:
  - 왼쪽(Debit): 자산 증가, 비용 발생
  - 오른쪽(Credit): 자산 감소, 수익 발생

**`build_whooing_rows(postings, config)`**
- 포스팅을 Whooing 업로드 형식으로 변환
- 계정명 검증 (whooing_setting.xlsx 기반)
- 계정 타입별 제약사항 적용:
  - 자산/부채/순자산: 왼쪽/오른쪽 모두 가능
  - 비용: 왼쪽만 가능
  - 수익: 오른쪽만 가능

**`main()`**
- 전체 파이프라인 실행
- 파서 호출 → 통합 → 보강 → 매칭 → 포스팅 → 변환
- 결과 파일 생성:
  - `final_transactions.csv`: 표준 트랜잭션 목록
  - `whooing_postings.csv`: 포스팅 목록
  - `whooing_upload_final.xlsx`: Whooing 업로드 파일
  - `debug/*.csv`: 각 파서의 중간 결과물

### 4. Calibrator 모듈 (`calibrator.py`)

- Google Sheets의 거래 분류와 시스템 분류 규칙을 비교
- 분류 규칙 보정 및 업데이트 도구

### 5. Whooing Converter (`whooing_converter.py`)

- 포스팅 데이터를 Whooing Excel 형식으로 변환
- 날짜, 시간, 금액, 계정명 매핑

---

## 주요 비즈니스 로직

### 1. 토리(경기지역화폐) 충전 처리

**시나리오:**
- 은행에서 30,000원 출금 (타행건별 1월 토리)
- 토리 계좌에 30,000원 충전
- 인센티브 24,000원 추가 지급

**처리 방식:**
1. 은행 거래와 토리 충전 거래를 날짜/금액으로 매칭
2. Transfer 거래 생성: 우리은행태우(-30,000) ↔ 토리태우(+30,000)
3. 인센티브 거래 생성: 토리태우(+24,000) ↔ 기타수익(-24,000)

**구현 위치:**
- `union.py::match_internal_transfers()` - 토리 충전 매칭
- `union.py::build_postings()` - 인센티브 처리

### 2. 온누리 충전 처리

**시나리오:**
- 은행에서 9,000원 출금 (온누리충전)
- 온누리 계좌에 10,000원 충전 (1/9 인센티브)

**처리 방식:**
1. 은행 거래에서 "온누리충전" 키워드 감지
2. 잔액 변화로 실제 출금 금액 계산
3. 충전 금액 = 출금 금액 × 10/9
4. 인센티브 = 충전 금액 - 출금 금액
5. Transfer 및 인센티브 거래 생성

**구현 위치:**
- `union.py::match_internal_transfers()` - 온누리 충전 매칭
- `parser/woori_bank.py` - 키워드 기반 출금 감지

### 3. 네이버페이 통합

**3가지 데이터 타입:**

1. **payments_pc**: 결제 내역
   - 용도: 은행/카드 거래 정보 보강
   - 처리: `enrich_with_naverpay()`에서 매칭하여 merchant/description 업데이트

2. **points**: 포인트 거래
   - 용도: 독립적인 자산 계정으로 처리
   - 처리: 일반 거래처럼 포스팅 생성

3. **money**: 머니 거래
   - 용도: 독립적인 자산 계정으로 처리
   - 특수 처리:
     - 출처가 하나은행: "타통장입금" 항목 사용
     - 출처가 우리은행: 우리은행 통장 내역과 매칭하여 통합

### 4. Owner 분리

**자동 감지:**
- 카드: 카드번호 기반
- 토리: 이름 기반 (이태우/서채영)
- 은행: 파일명 또는 명시적 파라미터

**매핑:**
- `taewoo` ↔ "이태우", "우리은행태우"
- `chaeyoung` ↔ "서채영", "우리은행채영"

---

## 데이터 흐름

```
[원본 파일들]
    ↓
[Parser 모듈들]
    ↓ (CSV 출력)
[union.py::detect_parser()]
    ↓
[union.py::_to_std_txn()]
    ↓ (StdTxn 리스트)
[union.py::enrich_with_*()]
    ↓ (정보 보강)
[union.py::match_internal_transfers()]
    ↓ (이체 거래 통합)
[union.py::build_postings()]
    ↓ (Posting 리스트)
[union.py::build_whooing_rows()]
    ↓ (Whooing 형식)
[whooing_converter.py]
    ↓
[whooing_upload_final.xlsx]
```

---

## 설정 파일

### `config.py`
- Google Sheets ID
- 네이버페이 크롤러 설정 (페이지 수, 스크롤 횟수)
- 파일 경로 상수

### `assets/whooing_setting.xlsx`
- 계정명 → 계정 타입 매핑
- 계정 타입: 자산, 부채, 수익, 비용, 순자산
- Whooing 시스템의 계정 구조 정의

### `assets/whooing_default.xlsx`
- Whooing 업로드 템플릿
- 필수 컬럼: 날짜, 시간, 왼쪽, 오른쪽, 금액, 메모 등

---

## 주요 개선 사항 (MD 파일 기반)

### 1. 모듈화 및 리팩토링
- 모든 파서를 `parser/` 폴더로 이동
- 네이버페이 크롤러를 `crawler/` 폴더로 분리
- 중복 코드 제거 및 공통 함수 추출

### 2. 토리 충전 로직 구현
- 은행 거래와 토리 충전 자동 매칭
- 인센티브 자동 추출 및 별도 거래 생성
- 키워드 기반 출금 감지 개선

### 3. 온누리 충전 로직 구현
- 온누리 충전 자동 감지 및 처리
- 1/9 인센티브 자동 계산

### 4. Owner 분리 개선
- 경기지역화폐 이름 기반 owner 매핑
- 카드번호 기반 owner 자동 감지

### 5. 데이터 정렬
- 모든 출력 파일을 날짜/시간 순서대로 정렬

### 6. 디버깅 지원
- 각 파서의 중간 결과물을 `debug/` 폴더에 저장
- 파싱 과정 추적 가능

---

## 사용 방법

### 기본 실행
```bash
python union.py
```

### 네이버페이 데이터 수집
```bash
python crawler/naverpay.py --owner taewoo --output result
```

### 개별 파서 실행
```bash
python parser/woori_bank.py invoices/거래내역조회.xls taewoo
```

---

## 주요 데이터 구조

### StdTxn
```python
@dataclass
class StdTxn:
    txn_uid: str           # 고유 ID
    occurred_at: datetime  # 발생 일시
    source: str            # 출처 (bank, card, tori, onnuri, naverpay 등)
    owner: str             # 소유자 (taewoo, chaeyoung)
    merchant: str          # 가맹점명
    description: str       # 거래 설명
    amount: int            # 금액 (음수: 출금, 양수: 입금)
    payment_method: str    # 결제 수단 (optional)
    raw_ref: str           # 원본 참조 (optional)
```

### Posting
```python
@dataclass
class Posting:
    txn_uid: str           # 트랜잭션 ID
    occurred_at: datetime  # 발생 일시
    account: str           # 계정명 (Whooing 계정명)
    amount: int            # 금액 (양수: 왼쪽, 음수: 오른쪽)
    memo: str              # 메모
```

---

## 향후 개선 가능 영역

1. **에러 처리 강화**: 파싱 실패 시 상세 로그 및 복구 메커니즘
2. **성능 최적화**: 대용량 파일 처리 시 메모리 효율성 개선
3. **테스트 코드**: 각 파서 및 통합 로직에 대한 단위 테스트
4. **설정 파일화**: 하드코딩된 규칙들을 설정 파일로 분리
5. **다국어 지원**: 에러 메시지 및 로그의 다국어화

---

## 참고 사항

- 모든 거래는 발생주의 원칙에 따라 처리됩니다
- 복식부기 회계 원칙을 엄격히 준수합니다
- Whooing 시스템의 계정 구조와 완전히 호환됩니다
- 두 명의 사용자(태우, 채영)의 거래를 명확히 분리합니다
