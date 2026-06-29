-- PyroSafe 점검 데이터 스키마
-- 실행 방법: Supabase 대시보드 → SQL Editor → 이 파일 내용 붙여넣기 → Run
-- 모든 테이블은 RLS 활성화 + 정책 없음 = 외부 직접 접근 차단.
-- 앱(Streamlit, 서버측)은 service_role 키로만 접근한다.

-- 1) 장비 (시설 관리)
create table if not exists public.equipment (
  equipment_id   text primary key,
  location_id    text not null,
  category       text not null,
  equipment_name text not null,
  serial         text not null,
  qr_status      text not null default 'PENDING',   -- ASSIGNED | PENDING
  last_inspection date,
  health_status  text not null default 'DUE',        -- PASS | FAIL | DUE
  floor          text not null,
  zone           text not null,
  pixel_x        double precision not null default 0,
  pixel_y        double precision not null default 0,
  inspection_types jsonb not null default '[]'::jsonb,
  created_at     timestamptz not null default now()
);

-- 2) 점검 일정
create table if not exists public.inspection_tasks (
  task_id         text primary key,
  equipment_label text not null,
  task_type       text not null,
  assignee        text not null default '',
  due_date        date not null,
  status          text not null default 'Scheduled', -- Scheduled | In Progress | Overdue | Completed
  floor           text not null,
  zone            text not null,
  note            text not null default '',
  created_at      timestamptz not null default now()
);

-- 3) 별지5 지적사항 (v1.5: 별지6 조치 단계 흡수 / v1.5+: 불량 사유 카탈로그)
create table if not exists public.deficiencies (
  deficiency_id    text primary key,
  inspection_date  date not null,
  inspector        text not null,
  floor            text not null,
  zone             text not null,
  inspection_types jsonb not null default '[]'::jsonb,
  issue            text not null,
  resolution       text not null,                    -- 완료 | 불가
  confirmer        text,
  notice_no        text,
  task_id          text,                             -- v1.5: 점검 회차 Task FK
  submitter        text,                             -- v1.5: 점검자(발급자)
  action_done      boolean not null default false,   -- v1.5: 조치 완료 여부
  action_at        date,
  action_note      text not null default '',
  action_photo_path text,
  defect_codes     text[] not null default '{}',     -- v1.5+: 불량 사유 코드 (multiselect)
  defect_other     text not null default '',         -- v1.5+: "기타" 선택 시 상세
  created_at       timestamptz not null default now()
);

-- 4) 별지6 통보서
create table if not exists public.notices (
  notice_no         text primary key,
  inspection_date   date not null,
  floor             text not null,
  zone              text not null,
  inspection_type   text not null,
  issue             text not null,
  photo_path        text,
  submitter         text not null,
  confirmer         text not null,
  action_done       boolean not null default false,
  action_at         date,
  action_note       text not null default '',
  action_photo_path text,                            -- Storage(action-photos) 내 경로
  created_at        timestamptz not null default now()
);

-- 5) 별지9 오동작 (v1.5+: 등록/조치 분리)
create table if not exists public.malfunctions (
  malfunction_id text primary key,
  category       text not null,
  occurred_on    date not null,
  detail         text not null,
  action         text not null default '',
  confirmer      text not null default '',
  task_id        text,                                -- v1.5+: 점검 회차 Task FK
  action_done    boolean not null default false,      -- v1.5+: 조치 완료 여부
  action_at      date,
  action_note    text not null default '',
  created_at     timestamptz not null default now()
);

-- RLS: 활성화만 하고 정책을 만들지 않음 → anon/authenticated 직접 접근 전부 차단
alter table public.equipment        enable row level security;
alter table public.inspection_tasks enable row level security;
alter table public.deficiencies     enable row level security;
alter table public.notices          enable row level security;
alter table public.malfunctions     enable row level security;
