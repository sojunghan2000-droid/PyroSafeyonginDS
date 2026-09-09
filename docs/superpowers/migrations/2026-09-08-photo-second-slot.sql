-- 260907 후속: 점검사진/조치 전/조치 후 사진 각각 2번째 슬롯 추가 (최대 2장 지원)
alter table deficiencies
  add column if not exists photo_path2            text,  -- 조치 전 사진 2번째
  add column if not exists action_photo_path2      text,  -- 조치 후 사진 2번째
  add column if not exists inspection_photo_path2  text;  -- 점검사진 2번째
