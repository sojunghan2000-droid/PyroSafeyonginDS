-- 260907 현장요구사항: 신규 컬럼 3종 (전부 추가적 변경, 기존 row는 기본값)
alter table equipment
  add column if not exists active boolean not null default true;

alter table deficiencies
  add column if not exists photo_path            text,  -- 조치 전(발견 시) 사진 — 기존 action_photo_path와 분리
  add column if not exists inspection_photo_path  text;  -- 결과 무관 점검사진 (양호 포함)
