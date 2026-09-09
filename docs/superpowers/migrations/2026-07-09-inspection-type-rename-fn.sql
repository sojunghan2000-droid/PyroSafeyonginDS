-- 점검 유형 명칭 변경 (v1.8)
-- 이름을 바꾸면 참조(카탈로그·회차·Task·장비)를 한 트랜잭션에서 연쇄 갱신하는 함수.
-- 실행: Supabase 대시보드 → SQL Editor → 붙여넣기 → Run (1회).

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

notify pgrst, 'reload schema';
