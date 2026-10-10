# ShopOn 마트 데모 봇

마트 사장님에게 보여주기 위한 **데모 전용** 텔레그램 봇입니다.
기존 `b2_erp.py`와 코드·데이터를 전혀 공유하지 않으며, 데이터는 이 폴더의 SQLite 파일(`mart_demo.db`)에만 저장됩니다.

## 기능
- 🛒 **판매**: 카테고리 → 상품(사진 표시) → 수량 → 장바구니 → 결제수단(Cash/GCash/Maya/Card) → 영수증
- 🔎 **상품 검색**: 채팅창에 상품명 입력 (예: `삼겹살`, `콜라`)
- 📦 **재고 확인**: 🔴 부족 / 🟡 주의 / 🟢 충분, 부족 상품만 모아보기
- 🚨 **재고 부족 알림**: 판매로 최소 재고 이하가 되면 자동 알림 (그룹방으로도 가능)
- 🚚 **입고**: 물건 들어오면 수량 추가
- 💸 **지출**: 항목 → 금액 → 결제수단
- 👤 **출퇴근** 기록
- 📊 **오늘 마감**: 매출 합계·결제수단별·TOP 5 상품·지출·금고 현금·부족 재고
- 🌐 한국어 / English 전환
- 정육은 kg 단위(0.5kg 단위 선택 가능), 나머지는 개 단위

## 한 줄 설치 (서버에서)
```bash
curl -fsSL https://raw.githubusercontent.com/kimsungyong1117-jpg/shopon-mart-demo/main/install.sh | bash -s <BOT_TOKEN>
```
`/root/shopon-demo`에 설치되고 systemd 서비스(`shopon-demo`)로 실행돼서 재부팅해도 다시 켜집니다. 다시 실행하면 업데이트되고, `.env`와 데모 데이터는 유지됩니다.

## 직접 실행
```bash
cd demo_bot
pip install -r requirements.txt
cp .env.example .env      # .env 파일을 열어 BOT_TOKEN 입력
python mart_demo_bot.py
```
webhook이나 도메인 없이 polling 방식으로 돌아가서, 인터넷만 되면 어느 서버나 PC에서도 실행됩니다.

## 명령어
- `/start` 시작 화면, `/menu` 메뉴 다시 열기
- `/reset` 데모 데이터 초기화 (판매·지출 기록 삭제, 재고를 `products.csv` 값으로 되돌림)
- `/chatid` 현재 채팅방 id 확인 (재고 알림 그룹 설정용)

## 상품 바꾸기
`products.csv`를 수정한 뒤 `/reset` 하면 반영됩니다.
열: `id, category, name, price, unit(ea/kg), stock, min_stock, image`
`category`는 `한국어 English` 형식 (예: `정육 Meat`), `image`는 `images/` 폴더의 파일명입니다.
