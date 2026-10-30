# 호텔 무료 숙박권 추첨 이벤트 페이지

`index.html` 한 장짜리 정적 페이지입니다. 이름 · 휴대폰 번호 · 생년월일 + 개인정보 수집·이용 동의를 받아 Google 스프레드시트에 저장합니다.

## 신청 내역 받기 (Google 스프레드시트 연결, 약 5분)

1. Google 스프레드시트를 새로 만듭니다.
2. 메뉴 **확장 프로그램 → Apps Script** 를 열고, `apps-script.gs` 내용을 붙여 넣고 저장합니다.
3. **배포 → 새 배포 → 유형: 웹 앱** 선택
   - 실행 사용자: **나**
   - 액세스 권한: **모든 사용자**
4. 배포 후 나오는 웹 앱 URL(`https://script.google.com/macros/s/.../exec`)을 복사합니다.
5. `index.html` 의 `const ENDPOINT = "";` 에 그 URL을 넣습니다.

신청이 들어오면 시트의 `신청자` 탭에 한 줄씩 쌓입니다. 같은 휴대폰 번호로는 중복 신청이 막힙니다.

## 배포

정적 파일이라 GitHub Pages, Netlify, Vercel 등 어디든 `index.html` 과 `images/` 폴더만 올리면 됩니다.
(GitHub Pages: 저장소 Settings → Pages → 브랜치 선택)

## 운영 전 확인

- 개인정보 동의 문구의 보유 기간(현재 "이벤트 종료 후 3개월")과 주최자 정보를 실제 내용으로 바꿔 주세요.
- 실제 호텔명을 쓰는 경우, 해당 호텔과의 제휴·협찬이 확정된 상태여야 합니다.

## 페이스북 광고 집행 체크리스트

1. **사이트 공개** 후 주소 확정 → `index.html` 의 `og:url`, `og:image` 의 `https://example.com` 을 실제 주소로 교체
2. **Meta 픽셀**: 이벤트 관리자에서 픽셀 생성 → ID를 `META_PIXEL_ID` 에 입력
   - 방문 시 `PageView`, 신청 완료 시 `Lead` 이벤트가 전송됩니다 (이름·번호·생년월일은 전송하지 않음)
   - 광고 목표는 **잠재 고객(Leads)**, 전환 위치 **웹사이트**, 전환 이벤트 **Lead** 로 설정
3. **대괄호 `[ ]` 항목 채우기**: `index.html` 유의사항·주최 정보, `privacy.html` 전체
4. 페이스북 [공유 디버거](https://developers.facebook.com/tools/debug/)에 주소를 넣어 미리보기 이미지 확인
