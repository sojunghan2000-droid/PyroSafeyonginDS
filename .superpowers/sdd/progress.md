# SDD Progress — 오동작 위치 모듈 (v1.9)

Plan: docs/superpowers/plans/2026-07-15-오동작-위치-모듈.md
Base: 5c09a1a

- [x] Task 1: 마이그레이션 B (malfunctions floor/zone/spot_id) — complete (commit 94fe02e, 적용·검증 완료)
- [x] Task 2: Malfunction 모델 + 데이터 레이어 — complete (commit 9f2528d, review clean)
- [x] Task 3: _location_map_picker 범용 픽커 — complete (commits 6dcae45..5e56b74, review Important 1건 수정: 빈 spot 라벨 중복 제거)
- [x] Task 4: 오동작 다이얼로그 위치 픽커 장착 — complete (commit 1d3aac2, review clean; Minor: 픽업 위치가 다이얼로그 재오픈 시 유지되나 기존 관례와 동일, 수정 불필요)
- [x] Task 5: 통합 목록 오동작 행 재배치 — complete (commit 826c327, review clean)

## 최종 리뷰 + 후속 배치 (완료, main 푸시 df26bf6)
- 최종 whole-branch 리뷰(opus): "With fixes" — Critical 없음, Important 1건(오동작 '위치 지우기' 실효성).
- 후속 배치 커밋 df26bf6: (1) 위치 지우기 실효화(차트 선택키 clear) (2) 장소정정 현재위치 파란마커(eq.spot_id) (3) QR 폴백 st.error→caption (4) 적용점검유형 라벨 정리.
- 별도: b8c1ece 장비명 자동생성, 5a96ce0 시리얼 라벨.
- 실화면 검증: Fix2(QR 캡션)·Fix3(파란 마커) 스크린샷 확인 완료. Fix1(위치 지우기)·Fix4(라벨)은 ast/import+무에러, 프리뷰 불안정으로 실클릭 미검증 → 사용자 Ctrl+F5 클릭테스트 요청.
- Feature A(신규 위치 카테고리)는 스펙에만 있고 미구현(사용자 지시로 보류).

## Minor findings roll-up (최종 리뷰에서 triage)
- T3: _location_map_picker와 _add_task_map_picker 구조 중복(~60-90줄, 의도적 별도 함수 — 3번째 픽커 생기면 공용 헬퍼로 리팩터 후보); load_spots() 전층 로드 1회 중복(성능 무시 가능).
- T4: 픽업 위치가 다이얼로그 재오픈 시 유지(기존 mal_dlg_* 필드 관례와 동일, 회귀 아님).
- T5: floor/zone 한쪽만 빈 값이면 "B2 / " 구분자 잔존(픽커 흐름상 둘 다 채워져 발생 불가, 지적사항 행도 동일 미가드).

# SDD Progress — 오동작 접수 회차 발행 (v1.10)
Plan: docs/superpowers/plans/2026-07-16-오동작-접수-회차-발행.md
Base: 5d9aa60
- [x] Task 1: MAL_ROUND_TYPE 상수 + 회차·Task 발행·연결 — complete (commit 66f51de, review clean; Minor: type:ignore 주석 제거 무영향)
- [x] Task 2: 회차 목록 '오동작 접수' 배지 — complete (commit 68cc3e8, review clean)
- [x] Task 3: KPI + 별지5 드롭다운 제외 — complete (commit 125cf17, review clean)
- 최종 whole-branch 리뷰(opus): "With fixes" — Critical 없음, Important 1건(field_kpis/task_kpis Task 단위 KPI 누출) → 수정 75e306d(오동작 접수 Task 제외, KPI-EXCLUDE OK). Minor(3-insert 비원자성·INS 결번·유형필터 노출)는 기존 패턴/스펙 허용으로 수용.

# SDD Progress — 도움말 개편 (v1.11)
Plan: docs/superpowers/plans/2026-07-16-도움말-개편.md
Base: 39228e5
- [x] Task 1: _faq_search 경량 유사도 함수 — complete (commit f05c96f, review clean)
- [x] Task 2: FAQ 카테고리 데이터 + 내용 갱신(+신규 5) — complete (commit 6489422, review clean; 후속: 화기작업 답변 잔여 '탭' 문구 정리)
- [x] Task 3: _help_dialog 검색창+카테고리 렌더 — complete (commit 1805a6a, review clean, 미푸시); 화기작업 탭 정정 78ae0f1
