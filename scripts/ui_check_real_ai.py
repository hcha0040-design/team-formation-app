"""연습 시나리오를 마감까지 진행한 뒤, 실제 AI 모델로 배정하고 확정해 본다(무료 호출 1~3회를 씀).

실행: py scripts/ui_check_real_ai.py [쉬움|중간|어려움]   (기본 쉬움)
주의: 실행하면 DB의 명단이 바뀐다.
"""

import logging
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)

from streamlit.testing.v1 import AppTest  # noqa: E402

from config import get_secret  # noqa: E402
from tf import db  # noqa: E402
from tf.rules import _team_problems  # noqa: E402

name = sys.argv[1] if len(sys.argv) > 1 else "쉬움"
subprocess.run([sys.executable, str(ROOT / "scripts" / "run_scenarios.py"), name], check=True, capture_output=True)

at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
at.run()
at.text_input(key="login_student_no").input("admin")
at.text_input(key="login_password").input(get_secret("ADMIN_PASSWORD"))
at.button(key="login_submit").click().run()
at.button(key="admin_assign").click().run()

start = time.time()
while not at.session_state["assign_job"].done and time.time() - start < 420:
    time.sleep(2)
    at.run()
    shown = [e.value for e in at.info if "기다리는 중" in e.value]
    if shown:
        print(f"[{int(time.time() - start):>3}초] {shown[0]}", flush=True)
at.run()

job = at.session_state["assign_job"]
print("배정안 출처:", job.source)
for a in job.attempts:
    print(f"  {a.number}차 {a.model}: {a.outcome} ({a.elapsed}초) {a.detail}")
at.button(key="admin_confirm").click().run()
print("확정 결과:", next(e.value for kind in (at.success, at.warning) for e in kind if e.value[:2] in ("승인", "막힘")))

teams, unassigned = db.snapshot(db.load_state())
problems = [p for t, m in teams.items() for p in _team_problems(t, m)]
print("확정 뒤 검사:", "모든 팀이 규칙을 지킴" if not problems and not unassigned else f"문제 {problems} / 팀 없는 학생 {len(unassigned)}")
for t, m in teams.items():
    print(f"  팀{t}: " + ", ".join(f"{s.name}" for s in m))
