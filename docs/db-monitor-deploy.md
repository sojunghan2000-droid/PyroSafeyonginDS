# DB 모니터 배포 (Streamlit Cloud)

같은 리포(YonginAIDC)에서 **별도 앱**으로 배포한다. PyroSafe 본 앱과 독립.

## 절차
1. `feat/db-monitor` 브랜치를 main 에 머지하고 push.
2. https://share.streamlit.io → **New app**.
   - Repository: `sojunghan2000-droid/YonginAIDC`
   - Branch: `main`
   - Main file path: `db_monitor.py`
3. **Advanced settings → Secrets** 에 아래 붙여넣기(값 실제로 채움):

   ```toml
   [monitor]
   password = "<모니터 접속 비밀번호>"

   [db]
   host = "aws-0-ap-south-1.pooler.supabase.com"
   port = 5432
   dbname = "postgres"
   user = "postgres.ivpzfrvboazpbcejpqwc"
   password = "<대상 DB 비밀번호>"
   ```
4. **Deploy** → 발급된 URL 접속 → 모니터 비밀번호로 로그인.

## 주의
- 읽기전용(SELECT). 쓰기 기능 없음.
- 대화에 노출된 DB 비밀번호·service_role 키는 rotate 권장. rotate 후 위 Secrets 의 `[db].password` 갱신.
- DB 비밀번호를 바꾸면 pooler 접속도 갱신 필요.
- 로컬 실행: `.streamlit/secrets.toml` 에 위 `[monitor]`/`[db]` 섹션을 넣고 `streamlit run db_monitor.py`.
