-- 별지9 오동작에 위치 정보(선택) 추가 — v1.9
ALTER TABLE malfunctions ADD COLUMN IF NOT EXISTS floor text;
ALTER TABLE malfunctions ADD COLUMN IF NOT EXISTS zone text;
ALTER TABLE malfunctions ADD COLUMN IF NOT EXISTS spot_id text;
