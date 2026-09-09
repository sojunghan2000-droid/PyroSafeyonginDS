# DB 모니터 (db_monitor.py) — 설계

- 날짜: 2026-08-19
- 대상 DB: 신규 Supabase 프로젝트 `ivpzfrvboazpbcejpqwc` (박재나 '소방안전' Org, region ap-south-1)
- 목적: 이 프로젝트 DB 전체(PyroSafe 8테이블 + FIRE-PASS 테이블)를 웹에서 읽기전용으로 모니터링

## 1. 범위 (확정)

- **모니터링 범위**: 4개 영역 전부 — ① 테이블 현황(행수·최근 갱신) ② 최근 활동·추이 차트 ③ 읽기전용 테이블 브라우저 ④ Storage·Auth 상태
- **대상**: 프로젝트 DB 전체 (PyroSafe + FIRE-PASS 두 앱)
- **배포**: Streamlit Cloud + 비밀번호 게이트
- **auth 이메일**: 마스킹 없이 그대로 표시 (합성 주소 `@pyrosafe.local` / `@firepass.example` 로 실제 개인 이메일 아님)

## 2. 아키텍처

- **단일 파일** `db_monitor.py`를 리포 `YonginAIDC`(github.com/sojunghan2000-droid/YonginAIDC) 루트에 추가.
- Streamlit Cloud에서 **별도 앱**으로 배포 (같은 repo, Main file path = `db_monitor.py`, 별도 URL·별도 secrets). PyroSafe 본 앱(`app.py`)과 코드 의존성 없음 — `app.py`/`lib/`를 import 하지 않는다. 프로덕션 무영향.
- **데이터 접근**: `psycopg2`로 Supabase **pooler 직결 커넥션 1개**.
  - host `aws-0-ap-south-1.pooler.supabase.com`, port 5432, dbname `postgres`, user `postgres.ivpzfrvboazpbcejpqwc`, password=DB 비번, `sslmode=require`.
  - REST(PostgREST) 대신 DB 직결이라 PostgREST 미노출 테이블과 `storage`·`auth` 스키마까지 조회 가능 → "전체 DB" 모니터링의 근거.
- **비밀번호 게이트**: `st.session_state["monitor_authed"]` 가 True 가 아니면 비밀번호 입력창만 렌더. 입력값 == `st.secrets["monitor"]["password"]` 이면 통과.

## 3. 컴포넌트 (탭 4개)

각 탭은 독립 함수(`render_overview`, `render_trends`, `render_browser`, `render_ops`)로 분리. DB 조회는 캐시된 헬퍼 함수(`@st.cache_data(ttl=60)`)로 분리해 재사용·테스트 가능하게 한다.

### 3.1 개요 (render_overview)
- `information_schema.tables` 에서 `table_schema='public'` 테이블 자동 발견.
- 테이블별: 행수(`SELECT count(*)`), 최근 갱신(`created_at` 컬럼 존재 시 `max(created_at)`, 없으면 '-').
- 그룹핑: PyroSafe(하드코딩 8개: equipment, inspection_tasks, inspection_rounds, deficiencies, notices, malfunctions, floor_spots, inspection_types) / FIRE-PASS(나머지) / 기타.
- 빈 테이블(행수 0)은 시각적으로 표시(예: ⚠️).
- 상단에 총 테이블 수·총 행수 metric.

### 3.2 추이 (render_trends)
- `created_at`(timestamptz) 컬럼이 있는 테이블만 선택 대상.
- 선택 테이블에 대해 `SELECT date(created_at) d, count(*) c ... group by 1 order by 1` → plotly 막대/선 차트.
- 기본 표시 테이블: deficiencies, inspection_tasks, malfunctions (PyroSafe 활동 지표). 사용자가 selectbox로 변경 가능.
- 조회 기간 필터(최근 30/90/전체) 옵션.

### 3.3 브라우저 (render_browser)
- 테이블 selectbox → `SELECT * FROM {table} ORDER BY created_at DESC NULLS LAST LIMIT {N}` (N 기본 100, 슬라이더).
- 텍스트 검색: 입력 시 조회된 DataFrame에 대해 pandas 문자열 필터(전 컬럼 대상). (DB WHERE 아닌 클라이언트 필터 — 단순·안전.)
- 읽기전용 `st.dataframe`. 테이블명은 `information_schema` 로 검증한 화이트리스트에서만 선택되므로 SQL 인젝션 불가(사용자 자유 입력 아님).

### 3.4 운영 (render_ops)
- Storage: `storage.buckets` 목록 + 버킷별 `storage.objects` 개수·용량 합계(`sum((metadata->>'size')::bigint)`).
- Auth: `auth.users` 총수, 최근 로그인 목록(email, last_sign_in_at, app_metadata->>'role') — email 그대로 표시.

### 3.5 공통
- 사이드바: 새로고침 버튼(`st.cache_data.clear()`), 접속 대상 프로젝트 ref 표시, 로그아웃 버튼.
- 접속 정보 배지: 프로젝트 ref, region.

## 4. 데이터 흐름

```
사용자 → 비밀번호 게이트 → (통과) → 사이드바 선택
      → 캐시된 조회 헬퍼(@cache_data ttl=60) → psycopg2 pooler 커넥션 → 렌더
```

- 커넥션은 `@st.cache_resource` 로 1개 유지(재사용). 조회는 `@st.cache_data(ttl=60)`.

## 5. 에러 처리

- 커넥션 실패: 상단에 명확한 에러 배너("DB 연결 실패 — secrets 확인") + 상세 예외 텍스트.
- 테이블별 조회는 개별 try/except: 한 테이블(권한/타입 이슈)이 실패해도 개요 전체가 안 깨지고 해당 행에 'error' 표기.
- 빈 결과: 정상적으로 '데이터 없음' 표시.

## 6. 보안

- DB 접속정보(host/user/password)와 모니터 비밀번호는 **Streamlit Cloud Secrets(TOML)에만** 저장. 리포에 커밋 금지. `.gitignore` 에 `.streamlit/secrets.toml` 이미 포함 확인.
- 리포에는 `.streamlit/secrets.toml.example` 형태로 키 구조만(값 없이) 문서화.
- service_role 키는 이 앱에서 사용하지 않음(psycopg2 직결만 사용). 단, 대화에 노출된 service_role·DB 비번은 rotate 권장(별도 작업).
- 테이블명은 화이트리스트(information_schema 조회 결과)로만 선택 → 사용자 자유 입력 SQL 없음.

## 7. Secrets 구조 (Streamlit Cloud)

```toml
[monitor]
password = "<모니터 접속 비밀번호>"

[db]
host = "aws-0-ap-south-1.pooler.supabase.com"
port = 5432
dbname = "postgres"
user = "postgres.ivpzfrvboazpbcejpqwc"
password = "<DB 비밀번호>"
```

## 8. 의존성

- `requirements.txt` 에 `psycopg2-binary` 추가 (기존 streamlit·pandas·plotly 재사용).

## 9. 테스트 / 검증

- 로컬 스모크: `.streamlit/secrets.toml` 에 위 구조 채우고 `streamlit run db_monitor.py`.
  - 게이트: 틀린 비번 → 차단, 맞는 비번 → 통과 확인.
  - 개요: equipment 17, inspection_tasks 39 등 알려진 값과 일치 확인(이관 검증값).
  - 추이/브라우저/운영 각 탭 렌더 확인, 예외 없음.
- 조회 헬퍼 함수는 psycopg2 커넥션을 인자로 받는 순수 함수로 작성 → 로컬에서 단위 호출 가능.

## 10. 배포 절차 (사용자 실행)

1. `db_monitor.py` + `requirements.txt`(psycopg2-binary) push (main).
2. Streamlit Cloud → New app → repo `sojunghan2000-droid/YonginAIDC`, branch `main`, main file `db_monitor.py`.
3. App settings → Secrets 에 §7 TOML 붙여넣기.
4. Deploy → 비밀번호로 접속 확인.

## 11. 비목표 (YAGNI)

- 쓰기/편집 기능 없음(읽기전용).
- 알림·이메일·실시간 스트리밍 없음.
- 사용자별 권한/역할 없음(단일 비밀번호 게이트).
- FIRE-PASS 앱 도메인 로직 이해 불필요(스키마 레벨 표시만).
