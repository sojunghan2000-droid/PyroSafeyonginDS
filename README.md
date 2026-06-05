# PyroSafe · 용인덕성 AI DC

QR 코드 기반 소방시설 점검 관리 시스템 — Streamlit + ReportLab + Plotly.

## 핵심 기능

- **시설 관리** — 장비 목록, QR 발급/미리보기 (모달), 스티커 시트 PDF (A4 4×6)
- **지적·오동작 관리** — 별지5 지적사항 + 별지6 통보서 정보 + 별지9 오동작을 한 페이지에서
  - "신규 점검 추가" 모달 — 양호/불량 입력, 불량 시 통보서 자동 발급
  - "조치 입력 →" 버튼 — 후속 조치 등록 (사진/조치내용/확인자)
  - "오동작 등록" 모달 — 별지9 row 추가
- **대시보드** — 3탭 (현황 요약 / 도면 그리드 / 개별 층)
- **점검 일정** — Inspection Tasks 스케줄
- **보고서** — 별지5/6/9 PDF 자동 출력 + QR 스티커 시트 PDF (한글 NanumGothic 임베드)

## 사이드바 (5개)
```
1. 대시보드
2. 시설 관리
3. 점검 일정
4. 지적·오동작 관리
5. 보고서
```

## 로컬 실행

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1     # Windows
source venv/bin/activate         # Linux/Mac
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 배포

1. GitHub에 본 repo 푸시 — **완료**
2. https://share.streamlit.io 에서 **"New app"** 클릭
   - Repository: `sojunghan2000-droid/YonginAIDC`
   - Branch: `main`
   - Main file: `app.py`
3. Deploy 클릭 → 약 2–3분 빌드. 한글 폰트는 번들된 NanumGothic + `packages.txt` 백업 사용
4. URL 발급되면 **앱 Settings → Secrets**에 한 줄 추가
   ```toml
   BASE_URL = "https://<your-app>.streamlit.app"
   ```
   → 코드 변경/push 없이 즉시 모든 QR이 새 URL로 갱신됨

## 데이터

현재 mock 데이터 (시드 + session_state 누적). 페이지 새로고침 시 시드만 남음.

영구 저장은 Supabase 연결 후 가능 — `lib/data.py`의 `load_*()`/`add_*()` 함수만 교체.

## 별지 산출물 출력

| 별지 | 명칭 | 트리거 |
|---|---|---|
| 5 | 안전점검 결과 지적내역서 | 지적사항 row 전체 |
| 6 | 안전점검 조치 결과 통보서 | 조치 완료된 통보서 1건씩 |
| 9 | 소방시설 오동작 관리대장 | 오동작 row 전체 |

모든 PDF는 한글 본문 + 표 양식 + 단일 페이지.
