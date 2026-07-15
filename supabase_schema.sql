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

-- 3) 별지5 지적사항 (v1.5: 별지6 조치 단계 흡수 / v1.5+: 불량 사유 카탈로그 / v1.7: 세부 checklist)
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
  checklist_items  jsonb not null default '{}',      -- v1.7: 세부 항목별 상태 (OK/NG/NA)
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

-- 6) 점검 유형 카탈로그 (v1.8: 관리자 점검 유형 관리 — 추가/비활성/삭제)
create table if not exists public.inspection_types (
  name       text primary key,          -- 유형 이름. 장비·회차가 이름으로 참조
  is_active  boolean not null default true,
  is_builtin boolean not null default false,
  sort_order int not null default 100,
  created_at timestamptz not null default now()
);
insert into public.inspection_types (name, is_builtin, sort_order) values
  ('일일 점검', true, 1), ('주간 점검', true, 2), ('월간 점검', true, 3),
  ('분기 점검', true, 4), ('연간 점검', true, 5)
on conflict (name) do nothing;

-- RLS: 활성화만 하고 정책을 만들지 않음 → anon/authenticated 직접 접근 전부 차단
alter table public.equipment        enable row level security;
alter table public.inspection_tasks enable row level security;
alter table public.deficiencies     enable row level security;
alter table public.notices          enable row level security;
alter table public.malfunctions     enable row level security;
alter table public.inspection_types enable row level security;

-- 7) 회차 취소 컬럼 (v1.8) — inspection_rounds 기본 테이블은 별도 관리(앱 생성).
--    이 프로젝트의 회차 테이블에 취소 플래그/사유를 추가한다.
alter table public.inspection_rounds
  add column if not exists cancelled     boolean     not null default false,
  add column if not exists cancel_reason text,
  add column if not exists cancelled_at  timestamptz,
  add column if not exists cancelled_by  text;

-- 8) 점검 유형 명칭 변경 함수 (v1.8) — 이름 변경 시 참조를 원자적으로 연쇄 갱신
create or replace function public.rename_inspection_type(old_name text, new_name text)
returns void language plpgsql as $$
begin
  new_name := btrim(new_name);
  if new_name = '' then raise exception 'empty name'; end if;
  if not exists (select 1 from public.inspection_types where name = old_name) then
    raise exception 'type not found: %', old_name;
  end if;
  if exists (select 1 from public.inspection_types where name = new_name) then
    raise exception 'name exists: %', new_name;
  end if;
  update public.inspection_types  set name = new_name       where name = old_name;
  update public.inspection_rounds set task_type = new_name  where task_type = old_name;
  update public.inspection_tasks  set task_type = new_name  where task_type = old_name;
  update public.equipment set inspection_types = (
      select jsonb_agg(case when t = old_name then new_name else t end)
      from jsonb_array_elements_text(inspection_types) t)
    where inspection_types ? old_name;
end $$;
