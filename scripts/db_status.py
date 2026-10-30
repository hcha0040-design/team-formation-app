"""지금 DB 상태(팀 구성, 지원 기록)를 짧게 보여 준다. 배포한 앱에서 시험할 때 확인용.

실행: py scripts/db_status.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.disable(logging.WARNING)

from tf import db  # noqa: E402

state = db.load_state()
print("마감:", state.closed)
for team_id, members in state.teams.items():
    print(f"팀{team_id}:", ", ".join(state.students[s].name for s in members) or "-")
print("팀이 없는 학생:", ", ".join(state.students[s].name for s in state.unassigned()) or "-")


def _history(cur):
    cur.execute("select s.name, a.team_id, a.status, a.reason from tf_applications a"
                " join tf_students s on s.id = a.student_id order by a.id")
    return cur.fetchall()


print("지원 기록:")
for r in db.run(_history):
    print(f"  {r['name']} → 팀{r['team_id']}: {r['status']}" + (f" ({r['reason']})" if r["reason"] else ""))
