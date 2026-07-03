# PRD — PyroSafe: QR 기반 소방시설 점검 관리 시스템

| 항목 | 내용 |
|---|---|
| 제품명 | PyroSafe |
| 적용 현장 | 용인덕성 AI 데이터센터 (건설/운영 현장) |
| 버전 | v1.7 (2026-07-01 스냅샷 기준) |
| 문서 작성일 | 2026-07-01 |
| 상태 | 운영 전환 완료 — Supabase 영속화 + 인증 + 회차 모델 + 점검 인라인 + 오동작 3분기 + 화기작업·가설컨테이너 점검 + 불량 사유 카탈로그 + **세부 checklist 12+7 추가 (v1.7)** |

---

## 1. 개요

PyroSafe는 데이터센터 현장의 소방안전 시설(소화기, 감지기, 스프링클러, 임시소방시설 등)을
**QR 코드로 식별·점검·기록**하고, 법정 서식(별지5·별지6·별지9)을 **PDF로 자동 출력**하는
웹 기반 점검 관리 시스템이다.

v1.5부터 **점검 회차(Round) 모델**을 도입해, 신규 일정 등록 시 1개 회차 + 그에 속한
점검 작업(Task) N개를 한 번에 생성한다. 점검자는 안전점검 페이지의 회차 [상세] →
[점검 시작]으로 모바일에서 별지5 결과를 즉시 기록하며, 불량 시 현장 즉시 조치도 같은
모달에서 처리한다. 별지6 통보서의 조치 단계 데이터는 별지5에 흡수되어 흐름이
단순화됐다. 별지9 오동작 관리대장은 법정 양식 그대로 분리된 흐름으로 유지된다.

현장 점검자가 장비에 부착된 QR을 스캔하면 해당 장비의 점검 입력 화면이 즉시 열리고,
불량 판정 시 별지5 row + 통보서 번호가 자동 발급된다. 관리자는 대시보드와 도면 뷰에서
전 층 시설 상태를 실시간으로 파악하고, 보고서 페이지에서 제출용 PDF를 원클릭으로 출력한다.

## 2. 배경 및 문제 정의

### 현재 업무 방식의 문제

1. **수기 서류 작업** — 안전점검 결과 지적내역서(별지5), 조치 결과 통보서(별지6),
   오동작 관리대장(별지9)을 수기 또는 한글/엑셀 문서로 개별 작성. 동일 정보를 여러 양식에 중복 기입.
2. **장비 식별의 비효율** — 현장에서 장비 ID·위치를 종이 대장과 대조해야 하며, 오기입 위험이 높음.
3. **조치 추적 누락** — 지적사항 발급 후 후속 조치가 완료되었는지 추적하는 체계가 없어
   "조치 대기" 건이 방치될 수 있음.
4. **현황 가시성 부재** — 층별·구역별 시설 상태(정상/불량/점검 도래)를 한눈에 볼 수단이 없음.

### 해결 방향

- 장비마다 QR 스티커를 부착하고, 스캔 → 점검 입력 → 서식 자동 생성까지 단일 흐름으로 연결.
- 별지5/6/9 데이터를 한 번만 입력하면 시스템이 서식 간 연결(지적 ↔ 통보서)과 PDF 생성을 처리.

## 3. 목표 및 비목표

### 목표 (v1)

| # | 목표 | 측정 지표 |
|---|---|---|
| G1 | 점검 1건 입력~서식 출력 소요 시간 단축 | 건당 10분+ → 2분 이내 |
| G2 | 전 장비 QR **실제 부착·검증률** 확보 (v1.5+ — 발급률 아닌 첫 스캔 통과율) | QR 적용률 ≥ 95% (대시보드 KPI) |
| G3 | 지적사항 후속 조치 누락 제거 | "조치 대기" 건의 평균 처리일 추적, 방치 0건 |
| G4 | 법정 서식 PDF 자동화 | 별지5·6·9 수기 작성 0건 |

### 비목표 (v1 범위 제외)

- 소방서 제출 시스템과의 전자 연동 (PDF 출력까지만 담당)
- 다중 현장(멀티 테넌트) 지원 — 용인덕성 AI DC 단일 현장 전용
- 네이티브 모바일 앱 — 모바일 브라우저(QR 딥링크) 대응으로 갈음
- 사용자 인증/권한 체계 — v2 항목 (현재는 공개 URL)

## 4. 사용자 및 페르소나

| 페르소나 | 역할 | 주요 사용 시나리오 |
|---|---|---|
| **점검자** (예: 박소방) | 현장 소방안전 점검 담당 | 모바일로 QR 스캔 → 점검 결과(양호/불량) 입력. 불량 시 통보서 자동 발급 |
| **조치 담당자** (예: 홍길동) | 지적사항 시정 작업 수행 | "조치 대기" 통보서 확인 → 조치 후 사진·내용·확인자 등록 |
| **안전 관리자** (예: 김소장) | 현장 소방안전 총괄 | 대시보드·도면으로 현황 파악, 점검 일정 배정, 통보서 확인자 서명 |
| **문서 담당자** | 대관 서류 제출 | 보고서 페이지에서 별지5/6/9 PDF 출력 후 제출 |

## 5. 핵심 사용자 흐름

### 5.1 회차 단위 점검 흐름 (v1.5)

```
안전점검 페이지 [점검 ID = INS-YYYYMMDD-NNN]
  → 회차(Round) 등록 (점검 주기 + 대상 장비 N건 선택 또는 자유 등록)
       └ Round 1건 + Task N건 자동 생성 (round_id 공유)
  → 회차 [점검] 모달
       ├ Task 목록 + 진행률 (n/m)
       ├ [점검 시작 →] 각 Task별 **인라인 점검 영역** (모달 안 펼쳐짐, v1.5+)
       │    ├ 점검 종류 multiselect (별지5)
       │    ├ 결과: 양호 / 불량 / 오동작 (v1.5+ 3분기)
       │    │    ├ 양호 → Deficiency(완료) + Task=Completed
       │    │    ├ 불량 → Deficiency + 통보서 번호 + **불량 사유 multiselect (점검 종류별 카탈로그, v1.6)**
       │    │    │           + **조치 사진 필수 (v1.6)** + 현장 즉시 조치(선택, 비필수)
       │    │    │           + **세부 checklist (OK/NG/N/A, v1.7)** — 점검 종류가 카탈로그 보유 종류면 인라인 라디오 렌더링
       │    │    │             · NG 있으면 "결과=불량" 강제 힌트 + 결과가 불량 아니면 저장 차단
       │    │    └ 오동작 → Malfunction(action_done=False) → 4. 작업 조치 관리에서 조치
       │    ├ 장소·구역 정정 (선택) — QR 스캔 / 도면 spot 선택(별도 모달) 2탭
       │    └ 저장 시 회차 status 자동 재계산
       ├ [+ Task 추가] 자유 점검 회차에 동적 추가 (장비 선택[QR+목록] / 📍 점검 위치 등록)
       │    └ 후보 자유화 — 점검 주기 매칭 우선 + 매핑 외 장비도 자유 추가 가능
       ├ Completed Task 결과 카드 inline — 양호/불량/오동작 한 행에 노출
       ├ [제외] Task 점검 대상 제외 + 제외 사유 로그 보존
       └ [별지5 PDF (N건)] 회차 단위 지적내역서 PDF 다운로드

안전점검 페이지 우상단 [오동작 등록] — 점검 회차와 별개로 단건 오동작 등록 (v1.5+)
대시보드 상단 [📷 점검 (QR 스캔)] 빠른 진입 — 작업 유형 선택 후 QR 스캔
모바일에서 부착된 QR 스캔 → URL deeplink ?eq=EQ-XXXX → 작업 조치 관리 + 점검 모달
  · **회차 연결 (v1.7)**: 스캔 장비의 진행 중(미완료) 점검 Task 개수로 분기 —
    0건=회차 미연결 단독 기록 / 1건=자동 연결(+안내) / **2건 이상=「어느 회차 점검인가요?」 라디오 목록**(점검 ID·종류·마감·상태)에서 선택 → 그 Task에 연결.
    목록 끝에 「회차 미연결(단독 기록)」 안전 옵션 포함 (오연결 방지)
```

### 5.2 후속 조치 등록

```
지적·오동작 관리 리스트에서 "조치 대기" row의 [조치 입력 →] 버튼
  → 점검 작업 페이지 (처리 대기 통보서 카드)
  → 조치 내용 · 조치 사진 업로드 · 확인자 입력 → 저장
  → 통보서 상태 "조치 완료"로 전환, 별지6 PDF 출력 가능
```

### 5.3 QR 발급 → 부착 → 검증 (v1.5+)

```
① 시설 관리 [+ 신규 장비 등록] (ID/시리얼/위치 자동 채번)
   → qr_status = PENDING (부착 대기)
② 보고서 → QR 스티커 시트 PDF (A4 4×6) 또는 행 [속성] 모달 → PNG 개별 다운로드
③ 인쇄 → 자체 프린터 또는 인쇄소
④ 현장 부착 → 시스템 외부 행위 (qr_status 변화 없음)
⑤ 점검자 첫 스캔 → ?eq= 딥링크 진입 시 자동으로 PENDING → ASSIGNED 전환
   ("실제로 부착됐고 누군가 읽었다"는 신호)
   → toast 알림 "QR 첫 스캔 인식 — EQ-NNNN 가 ASSIGNED(부착 완료)로 전환"

⇒ QR 적용률 KPI = ASSIGNED / 전체 = 실제 부착·검증률 (발급률 아님)
```

## 6. 기능 요구사항

### 6.0 전역 상단바 (`lib/ui.py` `render_topbar`, v1.5+)

- Streamlit 기본 헤더(Deploy·메뉴) 숨김 — 커스텀 상단바로 일원화
- **좌측**: 브랜드 ("Samsung C&T")
- **우측 (좌 → 우)**: 🔔 알림 벨 — ❓ 도움말 — 👤 아바타 메뉴
  - **알림 벨** (`_render_notify_button`): 카운트(조치 대기 통보서 + 지연 Task + 임박 회차) 합계.
    `st.popover`로 카드 리스트 → 클릭 시 항목별 페이지 이동.
    매 rerun + `@st.cache_data(ttl=15)`로 갱신 (다른 사용자 변경은 본인 rerun 시점에 반영)
  - **도움말 FAQ** (`_render_help_button`): `st.dialog`로 v1.5+ 변경 12개 항목 FAQ 노출
  - **아바타 메뉴** (`_render_avatar_menu`): 현재 계정 / 로그아웃
- 배치는 `position: fixed` + `.st-key-*` 셀렉터로 우측 정렬 (알림 9.5rem · 도움말 5.5rem · 아바타 1.75rem)

### 6.1 대시보드 (`pages_app/dashboard.py`)

- **2탭 구조** (v1.5+, 개별 층 탭 제거 / v1.7 탭명 'Location' → '층별 도면'): 현황 요약 / 층별 도면
- 현황 요약: 장비·점검·지적 KPI 카드, Plotly 차트, 상단 [📷 점검 (QR 스캔)] 진입
- 층별 도면: 전 11개 층(B3·B2·B1·P4·L1·L2·2F·4F·5F·6F·SRV)의 zone 도면 미니맵.
  층 카드 [상세 보기] → 도면 모달 (도면 + 장비 리스트, 잠금 토글)
- 단일 층 상세 보기는 도면 그리드 카드의 [상세 보기] 모달로 통합
- **도면 UX (R12, v1.5+)**:
  - 좌상단 **컨트롤 토글** (🔓 조작 / 🔒 잠금, **기본 ON=잠금**) — 잠금 시 staticPlot, pan/zoom·modebar 비활성. 의도치 않은 viewport 흔들림 방지
  - **줌/팬 상태 유지** — Plotly `uirevision`으로 토글·rerun에도 사용자가 본 뷰 그대로 유지 (층 변경 시 자동 reset)
  - 도면 위 **색상 범례 5종** (양호 / 불량 / 임박 / 빈 spot / 결과 없음)
  - Streamlit element fullscreen 버튼 제거 — Plotly 🏠 Home(`resetScale2d`)이 전체 도면 보기 역할
  - **위치 마스터 역할 (v1.7 재정의)**: 등록된 spot **관리·검증 전용** — 사용 여부(장비 유무), 신규(임시) spot 정식 전환, 속성·좌표 편집·삭제. 일상 신규 위치 생성은 시설 관리·안전점검으로 이관 ([+ 신규 위치] 버튼은 초기 세팅·예외용 secondary로 축소)
  - **ID 표기 통일 (v1.7)**: spot 목록 첫 컬럼을 사용자 가시 **위치 ID(예: B2-01)** 메인 + 원본 **spot ID(SPOT-B2-001)** 작게 병기. location_id는 `location_id_from_spot(spot_id)`로 파생된 1:1 별칭이라 시설 관리 화면의 '위치 ID'와 형식 일치 (혼란 방지)
  - **층 선택 아래 도면 미리보기 (읽기 전용, v1.7)** — 특정 층: 그 층 도면 + spot 마커 / "전체": 전 층 4열 미니맵 그리드 + [이 층 보기] 드릴인
  - 위치 마스터의 **spot 속성 변경 모달** — 현재 spot은 파란 마커, 다른 spot은 옅은 주황. 도면 클릭으로 새 좌표 픽업, number_input 미세조정 (신규 위치의 정밀 좌표 조정처)
  - 위치 마스터 층 필터에 **"전체" 옵션** (v1.5+) — 모든 층 spot 한 화면에 표시, 행에 층 배지 노출

### 6.2 시설 관리 (`pages_app/equipment_inventory.py`)

- 장비 목록 테이블 (**v1.7 7컬럼 재편 — 자산·이력 관점**):
  위치 ID / 시설 종류(명+SN) / **위치 등록**(도면 spot 등록 여부 등록/미등록, QR 상태 좌측 별도 컬럼·이모지 없음) / QR 상태(ASSIGNED/PENDING) /
  **최근 점검**(날짜 + 결과 PASS/FAIL/DUE 병합, 구 'Inspection Status' 흡수) / **점검 이력**(완료 횟수, 클릭 시 이력 팝업) / 작업(속성)
  · **컬럼 설명 ▾ 팝오버** — 위치 등록·QR 상태·최근 점검 3개 헤더 옆 작은 ▾(st.popover) 클릭 시 뜻+조치 패널 (미등록/PENDING/FAIL·DUE 시 다음 행동)
  · **장비 점검 이력 팝업** (`_status_dialog`) — ⓐ **점검 결과 이력**(완료 점검, `Deficiency.task_id` 정밀 매칭, 일자·유형·양호/지적·내용) / ⓑ 점검 일정(예정·진행 포함) / ⓒ 구역 통보서(층·구역 단위)
  · (v1.6까지의 '작업 상태' 칩(예정/진행/지연)은 v1.7에서 '점검 이력'으로 성격 전환 — 미래 작업 관점은 안전점검 관리 페이지가 담당)
- 행별 **QR 미리보기 모달** — QR PNG 다운로드, 인코딩 URL 확인
- **신규 장비 등록** — 장비 ID(`EQ-NNNN`)·시리얼(`PYRO-NNNNN`)·위치 ID 자동 채번,
  카테고리에 따른 기본 점검 유형 자동 매핑 (사용자 수정 가능)
  · **위치 지정 (v1.7 전체 이관)**: "기존 위치 선택" 또는 "**신규 위치 만들기**"(층+방이름+x/y%) 라디오.
    신규 선택 시 등록과 동시에 spot 정식 생성(is_temporary=False). 정밀 좌표는 위치 마스터 [속성 변경]에서 조정.
    → spot 생성 주 경로가 시설 관리(장비 등록)로 이동, 위치 마스터는 관리·검증 전용화
- **QR 스티커 시트 PDF** — 선택 장비로 A4 4×6(24매/page) 시트 생성
  (QR + 장비ID + 층/구역 + 카테고리, 한글 NanumGothic 임베드)

### 6.3 안전점검 관리 (`pages_app/inspection_tasks.py`) — v1.5 (v1.7: 메뉴명 '안전점검' → '안전점검 관리')

- **회차(Round) 단위 목록**: **점검 ID**(`INS-YYYYMMDD-NNN`, v1.5+ prefix RND → INS) / 점검 주기 / 담당자 /
  마감일 / **진행률 바(완료/전체)** / 상태(Scheduled·In Progress·Overdue·Completed)
- 별지5 반영: 회차에 등록만 한 Task는 별지5에 들어가지 않음. **점검 시작 → 양호/불량 결과 입력 후**
  Deficiency가 생성되어야 별지5 row 추가. 불량 시 별지6 통보서도 자동 발급
- 별지5 **지적사항 컬럼 형식 (v1.5+)**: `장비명 (양호)` 또는 `장비명 (지적사항 내용)` —
  task_id로 InspectionTask.equipment_label을 lookup해 prefix로 붙임
- **점검 주기 카탈로그 (5종, v1.6)**: **일일 점검 (v1.6 신규)** / 주간 점검 / 월간 점검 / 분기 점검 / 연간 점검.
  · 시설 종류와 직교 — 한 회차에 여러 시설 포함 가능
  · 별지5 양식의 법정 점검종류 3종(임시소방시설/피난로/화기취급감독)과 별개 (행 단위 입력)
  · 일일 점검은 화기작업구간 점검 등 매일 수시로 실시되는 점검을 회차 단위로 묶기 위한 주기
- **점검 종류 카탈로그 (v1.6 확장, `lib/inspection_dialog.py` `INSPECTION_TYPES`)**:
  · 기존 법정 3종(임시소방시설/피난로/화기취급감독) + **🔥 화기작업구간 점검 (v1.6 신규)** + **📦 가설컨테이너 사무실 점검 (v1.6 신규)**
  · **화기작업구간 점검** — 일일/수시. 작업 구간을 자유 텍스트로 지정(spot 없이 층 + 구간 + 업체 자유 입력), PTW(작업허가) 프로세스 중 점검
  · **가설컨테이너 사무실 점검** — 월간 통합. 위치 마스터 spot 기반(컨테이너 사무실이 spot으로 등록된 경우)
- **신규 일정 등록 모달**:
  - 점검 주기 선택 → Equipment.inspection_types 매핑 장비 자동 후보 필터
  - **"일일 점검" 선택 시 자유 등록 모드 자동 활성화 (v1.6)** — 일일 점검은 본질적으로 그날 즉시 추가되는 구조이므로 회차만 만들고 Task는 점검 시 동적 추가하는 모드를 기본값으로 toggle ON
  - "대상 미선택 (자유 점검)" 토글: 회차만 만들고 Task는 점검 시 동적 추가
  - 저장 시 Round 1건 + Task N건 일괄 생성 (round_id 공유)
- **회차 상세 모달** ([점검] 클릭):
  - Task 목록 + 각 행 [점검 시작 →] / [제외] 버튼
  - **Completed Task 결과 카드 inline (v1.5+)**: 양호/불량 배지 + 점검자·점검일·점검종류 +
    불량 시 지적사항 / 현장 즉시 조치까지 한 카드로 한눈에 확인
  - **[+ Task 추가]** (자유 점검 회차) — **장비 선택 (사전 위치 설정됨) / 📍 점검 위치 등록 2탭** (v1.7, 탭명 '도면 선택' → '점검 위치 등록')
    · **장비 선택 탭 (v1.7 통합)**: QR 스캔 + 목록 선택을 한 탭으로 — 둘 다 등록 장비를 고르는 동일 흐름.
      QR 인식 시 목록 선택보다 우선 적용
    · (v1.7: 직접 선택 + QR 스캔 통합 / 화기작업 구간 별도 탭 제거 — 도면 신규 위치로 통합)
    · **후보 자유화 (v1.5+)**: 점검 주기 매칭 장비 우선 정렬 + **매핑 외 장비도 자유 추가 가능**
      (회차에 이미 포함된 장비만 후보에서 제외, 매칭 강제 안 함)
    · 점검 위치 등록 탭(도면): **3색 범례로 단순화 (v1.7)** — ⓐ점검 대상(회차 매칭, 파란 원) / ⓑ그 외 선택 가능(회색 · ● 매핑 외 장비 · ◇ 빈·신규 위치) / ⓒ이미 포함(진회색, 선택 불가). 세부 종류는 모양(●장비/◇위치)·마커 글자("빈"/"신규")·hover로 구분. 매칭/매핑 외 장비·빈 spot·신규 위치 모두 클릭 추가
    · 빈 spot → `equipment_label = '{spot_id} - {room_name} (빈 spot)'`
    · **🆕 신규 위치 추가 토글** (도면 위, 기본 OFF). ON 시에만 도면 빈 곳 클릭이 좌표 픽업 — 의도치 않은 등록 방지
    · 토글 ON + 빈 곳 클릭 → 좌표 픽업 + 위치 설명 입력 → **신규 위치 즉시 생성** + Task 추가 (`floor_spots.is_temporary=true` — 검증 대기 의미로 컬럼명 유지)
    · 신규 위치는 관리자가 위치 마스터 [속성 변경] 모달의 "정식 spot으로 전환" 체크 후 저장 시 정식화
    · **화기작업 구간 (v1.7)** — 도면에 spot이 없는 작업 위치(용접·절단 등)는 위 **🆕 신규 위치 추가**로 등록.
      v1.6의 별도 🔥 탭은 도면 신규 위치와 기능 중복이라 v1.7에서 제거 (업체명은 위치 설명·메모에 기재)
  - **[별지5 PDF (N건)]** — 그 회차 지적사항 회차 단위 PDF
  - 제외된 Task는 회색 표시 + 사유/작성자 로그 보존 + [복구] 버튼
- **점검 입력 (`task_inspect_inline`, v1.5+ 인라인)**: 회차 모달 안에서 Task 행 [점검 시작 →] 클릭 시
  같은 모달 내에 펼쳐지는 인라인 영역. 모달 안 모달 호출 불가 제약 회피.
  - Task 정보 + 매핑 장비 + 점검자/점검일
  - **장소·구역 정정 (선택)** — QR 스캔 / 도면 spot 선택 2탭
    · 도면 spot 선택 탭: 도면은 별도 모달로 분리 (회차 모달 안에서 도면 줌·팬 충돌 회피).
      모달에서 spot 마커 클릭 → 인라인 영역에 정정 반영 (파란 = 선택, 옅은 주황 = 다른 spot)
  - 점검 종류 multiselect + **결과: 양호 / 불량 / 오동작** 3분기 (v1.5+)
  - **세부 checklist (v1.7, 점검 시작 인라인)** — 점검 종류가 카탈로그 보유 종류면
    (화기작업구간 = 4카테고리×3=12항목 `CHECKLIST_FIRE_WORK`,
     가설컨테이너 = 7항목 `CHECKLIST_CONTAINER`)
    항목별 라디오 3택 (OK / NG / N/A)를 인라인 렌더링.
    · 저장 검증: NG 항목이 하나라도 있으면 결과 자동 "불량" 힌트 노출 + 결과 셀렉트가
      "불량"이 아니면 form validation으로 **저장 차단**
    · 저장 시 `Deficiency.checklist_items: dict[str, str]` (평평한 key → OK/NG/N/A) 로 영속화
    · 별지5 PDF는 NG 항목만 요약해 지적사항 컬럼에 함께 노출
  - 불량 시: 지적사항 입력 (수기) + **불량 사유 multiselect (v1.6, 점검 종류별 카탈로그)** + 현장 즉시 조치
    · **불량 사유 카탈로그 (v1.6)** — 결과 "불량" 선택 시 점검 종류가 카탈로그 보유 종류면 사유 multiselect 노출.
      화기작업구간 6종(DEFECT_CODES_FIRE_WORK), 가설컨테이너 7종(DEFECT_CODES_CONTAINER) 등 점검 종류별 사전 정의 사유.
      "기타" 선택 시 상세 텍스트(`defect_other`) 필수 입력
    · **조치 사진 의무화 (v1.6)** — 결과 "불량" 시 현장 즉시 조치 사진 첨부가 form validation으로 필수.
      사진 누락 시 저장 차단 (현장 즉시 조치 텍스트는 선택, 사진은 필수)
  - **오동작 시 (v1.5+)**: 시설구분 + 발생일(점검일 자동) + 오동작 내용
    · 시설구분: Task 장비 category가 별지9 카테고리에 직접 매핑되면 **자동 텍스트로만 표시**,
      매핑 안 되면 셀렉트박스 노출 (확산소화기/유도등/스프링클러/소화전 등)
    · 저장 시 Malfunction(task_id 매핑, action_done=False)에 INSERT + Task=Completed
    · 조치는 [작업 조치 관리]에서 [조치 입력 →]로 별도 시점 처리
  - 저장 → Deficiency 또는 Malfunction row + Task=Completed + 회차 status 자동 재계산
- KPI: 전체 회차 / 지연 / 진행 중 / 완료

### 6.4 작업 조치 관리 (`pages_app/deficiency_manager.py`) — v1.5

- 별지5(조치 단계 흡수) + 별지9(오동작)를 **단일 통합 리스트**로 표시
  · 컬럼: 구분 / 일자 / 장소·시설 / 점검종류 / 내용 / 상태 / 통보서 번호 / **점검 ID** / **작업 ID** / 작업
  · 점검 ID = `Task.round_id` (Deficiency가 어느 점검 회차에서 나왔는지 추적)
- v1.5: 별지6 데이터는 별지5에 통합됨 (`Deficiency.action_*`)
- row 상태 로직: `완료`(양호/현장 즉시 조치) / `조치 완료` / `조치 대기` / `불가`
- **신규 점검 추가 모달** — 장비 매칭 회차 Task 자동 task_id 매핑
- **오동작 등록 진입 (v1.5+)** — **3. 안전점검** 페이지 우상단 [오동작 등록]로 이동
  · 등록 시 시설구분 / 발생일 / 오동작 내용 / 최초 발견자만 입력 (조치 X)
- **오동작 조치 입력 모달** (`malfunction_action_dialog`) — 4. 작업 조치 관리에서 조치 대기 오동작 행 [조치 입력 →]
  · action_at / action_note / confirmer 입력 → `record_malfunction_action`
- 필터(전체/지적사항/오동작/조치 대기만) + 정렬(최신순/오래된순)
- "조치 대기" row에 **[조치 입력 →]** 직접 모달 (`action_input_dialog`)
  - 확인자/조치일/조치 내용/사진 입력 → `record_deficiency_action`로 저장
- **작업 ID 컬럼** — 회차 Task와의 매핑 표시
- KPI 5개: 전체 항목 / 지적사항 / 통보서 발급(조치 대기) / 오동작 / 작업 조치율

### 6.6 보고서 (`pages_app/report_center.py`)

| 별지 | 명칭 | 출력 단위 | 내용 |
|---|---|---|---|
| 별지5 | 안전점검 결과 지적내역서 | 지적사항 전체 1부 | 점검일·점검자·위치·점검종류·지적사항·조치결과·확인자 |
| 별지6 | 안전점검 조치 결과 통보서 | 통보서 1건당 1부 | 통보서 번호·지적 내용·조치 결과·사진·제출자/확인자 |
| 별지9 | 소방시설 오동작 관리대장 | 오동작 전체 1부 | 시설구분·발생일·오동작 내용·조치·확인자 |

- ReportLab 기반, 한글 본문(NanumGothic 임베드) + 표 양식 + 단일 페이지
- QR 스티커 시트 PDF도 이 페이지에서 일괄 출력 가능

### 6.7 QR 딥링크 (`app.py`, `lib/qr.py`)

- 페이로드: `{BASE_URL}/inspect?eq={equipment_id}`
- `BASE_URL` 결정 우선순위: ① Streamlit secrets → ② 환경변수 `PYROSAFE_BASE_URL` → ③ placeholder
  - secrets 변경만으로 코드 수정 없이 전체 QR URL 일괄 갱신
- Error correction H (30% 손상 복구) — 현장 스티커 마모 대응
- 동일 세션에서 다른 장비 QR 연속 스캔 지원 (`?eq=` 값 변경 감지)
- **첫 스캔 시 자동 부착 검증 (v1.5+)**: `?eq=` 진입 시 `mark_qr_assigned()` 호출 —
  해당 장비가 PENDING이면 ASSIGNED로 전환 (이미 ASSIGNED면 no-op).
  실패해도 점검 진입 흐름은 그대로 진행. 전환 직후 작업 조치 관리 페이지에서 toast 안내.

## 7. 데이터 모델 (`lib/data.py`)

```
Equipment        장비. id, 위치ID(spot_id 파생), 카테고리(14종), 시리얼,
                 qr_status(PENDING=부착 대기 / ASSIGNED=첫 스캔 후 부착 확인, v1.5+),
                 최근점검일, 건강상태(PASS/FAIL/DUE), 층/구역, 적용 점검유형[]
Spot             위치 마스터. spot_id, floor, room_name, x_pct/y_pct(0~100),
                 is_temporary(신규=검증 대기) — equipment의 위치 좌표는 spot에서 파생
InspectionRound  점검 회차. round_id(`INS-YYYYMMDD-NNN`, v1.5+ prefix INS),
                 점검 주기(주간/월간/분기/연간), 담당자, 기한, 상태(4단계)
InspectionTask   점검 작업. id, round_id(FK), 대상, 유형, 담당자, 기한,
                 상태(4단계), 층/구역, excluded(제외 시 사유/작성자)
Deficiency       별지5 row + 조치 단계 흡수(v1.5) + 불량 사유 카탈로그(v1.6) + 세부 checklist(v1.7).
                 점검일, 점검자, 층/구역, 점검종류[], 지적사항, 조치결과(완료/불가),
                 확인자, 통보서번호(FK), task_id(FK),
                 action_done/at/note/photo(별지6 데이터 흡수),
                 defect_codes: list[str] (v1.6, 사유 코드 배열),
                 defect_other: str (v1.6, "기타" 선택 시 상세),
                 checklist_items: dict[str, str] (v1.7, 평평한 key → OK/NG/N/A)
Notice           별지6 row. 통보서번호(PK), 지적정보, 제출자/확인자.
                 v1.5+ 잔존 — 통보서 번호 관리 + 별지6 PDF 데이터 소스로 유지.
                 조치 단계는 Deficiency.action_*로 흡수돼 PDF 빌더가 Deficiency 기준
Malfunction      별지9 row. malfunction_id, 시설구분, 발생일, 오동작 내용, 확인자,
                 task_id(v1.5+ 점검 회차 연결), action_done/at/note(v1.5+)
```

- **관계**: `Deficiency.notice_no → Notice.notice_no` (불량 지적 1건 = 통보서 1건),
  `Task.round_id → Round.round_id`, `Deficiency.task_id → Task.task_id`,
  `Malfunction.task_id → Task.task_id` (점검 중 발견 시)
- **채번 규칙**: 장비 `EQ-NNNN`, 시리얼 `PYRO-NNNNN`, 일정 `TSK-NNNN`,
  점검 회차 `INS-YYYYMMDD-NNN` (v1.5+ prefix RND → INS),
  통보서 `YYYY-MM-DD-NN`(일자 내 순번), spot `SPOT-{층}-NNN`
- **저장 방식 (v1.5+)**: Supabase Postgres 영속화. `_db()` 헬퍼 + service_role 키.
  읽기 `@st.cache_data(ttl=15)`, 쓰기 시 해당 캐시 무효화. 사진은 Supabase Storage
- **불량 사유 카탈로그 시스템 (v1.6, `lib/data.py`)**:
  · `DEFECT_CODES_FIRE_WORK` — 화기작업구간 점검 불량 사유 6종 (코드 → 라벨 매핑)
  · `DEFECT_CODES_CONTAINER` — 가설컨테이너 사무실 점검 불량 사유 7종
  · `DEFECT_CODE_CATALOG: dict` — 점검 종류 키 → 사유 코드 dict 매핑 (점검 종류별 라우팅)
  · `defect_codes_for(inspection_type: str) -> dict` — 점검 종류를 받아 해당 사유 카탈로그 반환.
    카탈로그 미보유 점검 종류는 빈 dict 반환 → UI에서 multiselect 미노출 분기
  · DB 마이그레이션: `supabase_migration_v1_6_defect_codes.sql` — `deficiencies.defect_codes text[]`,
    `deficiencies.defect_other text` 컬럼 추가
- **세부 checklist 시스템 (v1.7, `lib/data.py`)**:
  · `CHECKLIST_FIRE_WORK` — 화기작업구간 점검 세부 checklist **4 카테고리 × 3 = 12항목**
    (방화포·소화기 비치 / 화재감시자 업무 숙련도 / 가연물 정리정돈 / 주변 간섭사항)
  · `CHECKLIST_CONTAINER` — 가설컨테이너 사무실 점검 세부 checklist **7항목**
    (소화기 비치·점검 / 환기팬 / 외부 차단기·시건 / 감지기 / 접지 /
     철제쓰레기통·인화성물질 / 일일점검체크리스트 작성)
  · `checklist_for(inspection_type: str) -> dict` — 점검 종류 → 카탈로그(카테고리 dict) 매핑 헬퍼.
    카탈로그 미보유 종류는 빈 dict 반환 → 인라인에서 checklist 미노출 분기
  · `checklist_flat_keys(inspection_type: str) -> list[str]` — 카탈로그를 평평하게 펼친 항목 key 리스트
    (form state 초기화·저장 페이로드 구성용)
  · DB 마이그레이션: `supabase_migration_v1_7_checklist_items.sql` — `deficiencies.checklist_items jsonb`
    컬럼 추가 (평평한 key → "OK"/"NG"/"N/A")

## 8. 기술 아키텍처

| 레이어 | 기술 | 비고 |
|---|---|---|
| 프런트/백엔드 | Streamlit (단일 앱) | wide 레이아웃, 커스텀 테마 + 상단바 (`lib/ui.py`) |
| 차트·도면 | Plotly | 대시보드 + 도면 (uirevision 줌/팬 유지 + CSS overlay 잠금) |
| PDF | ReportLab | 별지 서식 + 스티커 시트, NanumGothic 임베드 (`lib/fonts.py`) |
| QR | qrcode + Pillow | Error correction H |
| 데이터 | **Supabase Postgres** (v1.5+) | service_role 키로 서버사이드 접근, `_db()` 헬퍼 + 캐시(ttl=15) |
| 인증 | **Supabase Auth** (v1.5+) | username/password — 점검자/관리자 분리 |
| Storage | **Supabase Storage** (v1.5+) | 점검·조치 사진 영속 |
| 배포 | Streamlit Cloud | `packages.txt`(fonts-nanum), secrets로 BASE_URL + Supabase URL/키 주입 |

- 페이지 모듈 구조: `app.py`(라우팅·딥링크) → `pages_app/*.py`(페이지) → `lib/*.py`(데이터·UI·QR·PDF)

## 9. 비기능 요구사항

| 항목 | 요구사항 |
|---|---|
| 모바일 대응 | QR 스캔 진입 흐름이 모바일 브라우저에서 동작해야 함 (점검 모달 중심) |
| 한글 처리 | 모든 PDF 산출물에 한글 폰트 임베드 (배포 환경 폰트 부재 시에도 보장) |
| QR 내구성 | Error correction H — 현장 스티커 30% 손상까지 판독 |
| 설정 주입 | 배포 URL 변경 시 코드 수정 없이 secrets만으로 QR 갱신 |
| 응답성 | 페이지 전환·모달 오픈 3초 이내 (Streamlit rerun 기준) |

## 10. 현재 한계 및 리스크

| # | 한계/리스크 | 영향 | 상태 |
|---|---|---|---|
| ~~R1~~ | ~~데이터 비영속 — session_state~~ | — | **✅ 해소 (v1.5)** Supabase Postgres 영속화 + 캐시 ttl=15 |
| ~~R2~~ | ~~인증 부재~~ | — | **✅ 해소 (v1.5)** Supabase Auth (username/password, admin/inspector 분리) |
| R3 | KPI에 데모 보정값 하드코딩 가능성 (`+38`, `+14` 등) | 실 수치 왜곡 | 운영 데이터로 검증 후 보정값 제거 |
| ~~R4~~ | ~~`TODAY`가 2026-05-27로 고정~~ | — | **✅ 해소 (v1.5)** `TODAY = date.today()` (lib/data.py:225) |
| R5 | Streamlit deprecated API 사용 (`use_container_width` 84곳, 일부 `st.components.v1.html`) | 향후 Streamlit 업그레이드 시 깨짐 | `width=` 파라미터로 점진 교체 |
| ~~R6~~ | ~~사진 업로드가 메모리(bytes) 저장~~ | — | **✅ 해소 (v1.5)** Supabase Storage 연동 |
| R7 | service_role 키를 Streamlit 서버에서 사용 — 클라이언트 노출 시 위험 | 키 회전 정책 필요 | Streamlit 서버사이드 렌더링이라 안전하나 작업 완료 후 키 회전 권장 |

## 11. 로드맵

### v1.1 — 운영 전환 ✅ 완료 (2026-06)
- [x] Supabase 연결: `lib/data.py`의 `load_*`/`add_*` 교체, 사진은 Storage 업로드
- [x] `TODAY` 고정값 → `date.today()` 전환
- [x] Supabase Auth (admin/inspector 역할 분리)
- [ ] KPI 데모 보정값 (`+38`, `+14`) 운영 데이터로 정밀 검증
- [ ] Deprecated Streamlit API (`use_container_width` 84곳) 점진 교체

### v1.5 — 회차 모델 + 인라인 점검 ✅ 완료 (2026-06)
- [x] 점검 회차(Round) 모델 — 1 회차 + Task N건
- [x] 별지6 조치 단계 → Deficiency.action_* 흡수
- [x] 회차 모달 안 인라인 점검 (모달 안 모달 제약 회피)
- [x] 점검 결과 양호/불량/오동작 3분기 + 오동작 등록 흐름 분리
- [x] 점검 주기 카탈로그 4종 (주간/월간/분기/연간)
- [x] 도면 UX — 잠금 토글 + uirevision + 빈 spot/신규 위치 추가
- [x] 위치 마스터 — 신규 위치 추가/속성 변경 모달, 전체 보기 필터
- [x] 상단바 — 알림 벨/도움말 FAQ/아바타 메뉴

### v1.6 — 화기작업·가설컨테이너 점검 + 불량 사유 카탈로그 ✅ 완료 (2026-06)
- [x] **일일 점검 주기 추가** — 점검 주기 카탈로그 4종 → 5종 (`lib/data.py` `TASK_INSPECTION_TYPES`)
- [x] **화기작업구간 점검 도입** — 일일/수시, 작업 구간 자유 입력 (spot 없이 층 + 구간 + 업체), PTW 프로세스 중 점검
- [x] **가설컨테이너 사무실 점검 도입** — 월간 통합, 위치 마스터 spot 기반
- [x] **불량 사유 카탈로그 시스템화** — `DEFECT_CODES_FIRE_WORK` 6종 / `DEFECT_CODES_CONTAINER` 7종 +
      `DEFECT_CODE_CATALOG` dict + `defect_codes_for()` 매핑 함수 (`lib/data.py`)
- [x] **점검 시작 인라인 변경** — 결과 "불량" + 카탈로그 보유 종류 시 사유 multiselect, "기타" 시 상세 텍스트 필수
- [x] **조치 사진 의무화** — 결과 "불량" 시 조치 사진 첨부 필수 (form validation)
- [x] **[+ Task 추가] 화기작업 구간 등록** — v1.6 별도 🔥 탭 → v1.7 도면 신규 위치로 통합 (탭 중복 제거)
- [x] **회차 등록 모달** — "일일 점검" 선택 시 자유 등록 모드 자동 활성화
- [x] **Deficiency 모델 확장** — `defect_codes: list[str]` + `defect_other: str` (DB 컬럼 추가,
      `supabase_migration_v1_6_defect_codes.sql`)

### v1.7 — 세부 checklist ✅ 완료 (2026-07)
- [x] **Deficiency 모델 확장** — `checklist_items: dict[str, str]` 필드 추가 (`lib/data.py`)
- [x] **화기작업구간 세부 checklist** — `CHECKLIST_FIRE_WORK` 4 카테고리 × 3 = 12항목
      (방화포·소화기 비치 / 화재감시자 업무 숙련도 / 가연물 정리정돈 / 주변 간섭사항)
- [x] **가설컨테이너 세부 checklist** — `CHECKLIST_CONTAINER` 7항목
      (소화기·환기팬·차단기/시건·감지기·접지·철제쓰레기통/인화성물질·일일점검체크리스트)
- [x] **매핑 헬퍼** — `checklist_for(inspection_type)` + `checklist_flat_keys(inspection_type)`
- [x] **점검 시작 인라인** — 카탈로그 보유 종류 시 항목별 OK/NG/N/A 라디오 렌더링,
      NG 있으면 "결과=불량" 힌트 + 결과가 불량 아니면 저장 차단
- [x] **별지5 PDF** — NG 항목만 요약해 지적사항과 함께 출력
- [x] **DB 마이그레이션** — `supabase_migration_v1_7_checklist_items.sql`
      (`deficiencies.checklist_items jsonb` 컬럼 추가)

### v1.8 — 현장 편의 (예정)
- [ ] 도면 위 장비 마커 클릭 → 점검 모달 진입
- [ ] 지적·오동작 리스트 검색(장소·내용 키워드)
- [ ] 조치 기한 알림 (조치 대기 N일 경과 시 통지)

### v2 — 거버넌스
- [ ] Supabase Realtime 구독 — 다른 사용자 변경 실시간 push (현재는 ttl=15 폴링)
- [ ] 점검 이력 기반 통계 리포트 (월간/분기)
- [ ] 권한 세분화 (점검자 본인 점검만 / 관리자 전체) — RLS 정책 확장

## 12. 성공 지표 (출시 후 측정)

- 점검 1건 입력 소요 시간 (목표: 2분 이내)
- QR 커버리지 (목표: 95% 이상 유지)
- "조치 대기" 평균 체류 일수 (목표: 7일 이내)
- 별지 서식 수기 작성 건수 (목표: 0건)
- 주간 활성 점검 건수 (시스템 정착도 프록시)

---

*본 PRD는 2026-07-01 기준 코드베이스(`app.py`, `lib/`, `pages_app/`)의 실제 구현을 근거로 작성되었다.
v1.5+ 변경 — 회차 모델, 점검 인라인, 3분기 결과(양호/불량/오동작), Supabase 영속화 완료, 도면 잠금 기본 ON, 상단바 정렬 — 모두 반영.
v1.6 변경 — 일일 점검 주기, 🔥 화기작업구간/📦 가설컨테이너 사무실 점검 종류, 불량 사유 카탈로그(`DEFECT_CODES_*`), 조치 사진 의무화, 회차 등록 일일 자유 등록 자동 활성화 — 모두 반영.
v1.7 변경 — 세부 checklist 12+7(OK/NG/N/A), [+ Task 추가] 화기작업 구간 별도 탭 제거(도면 신규 위치로 통합), [+ Task 추가] 장비 선택 탭 통합(QR+목록), 탭명 '도면 선택'→'점검 위치 등록', 메뉴명 '안전점검'→'안전점검 관리', 사이드바 번호→이모지(🏠🧯🔍🛠️📄⚙️).
v1.7 변경 — 세부 checklist 시스템(`CHECKLIST_FIRE_WORK` 12항목 / `CHECKLIST_CONTAINER` 7항목), `Deficiency.checklist_items: dict[str, str]`, `checklist_for()`·`checklist_flat_keys()` 매핑 헬퍼, 점검 시작 인라인 OK/NG/N/A 라디오 + NG 있으면 불량 강제, 별지5 PDF NG 항목 요약, DB 마이그레이션(`supabase_migration_v1_7_checklist_items.sql`) — 모두 반영.*
