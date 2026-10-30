"""마감 → AI 배정 → 확정을 화면(AppTest)으로 해 보고, 확정한 팀이 규칙을 지키는지 DB 에서 다시 검사한다.

AI 호출은 가짜로 바꿔(실제 호출 없음, 무료 횟수를 쓰지 않음) 실패 처리를 시험한다.
가짜 시험의 기록이 tf_ai_logs 에 실제 기록처럼 남지 않도록, 모델 이름을 test/ 로 시작하게 하고 끝에 지운다.
실행: py scripts/ui_check_assign.py
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
from tf import ai, db  # noqa: E402
from tf.models import Student  # noqa: E402
from tf.rules import _team_problems  # noqa: E402

failures = 0
ai.MODELS = ["test/가짜-1차", "test/가짜-2차", "test/가짜-3차"]


def expect(label: str, ok: bool, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"{'OK' if ok else 'XX'} {label} {detail}")


def admin_session() -> AppTest:
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
    at.run()
    at.text_input(key="login_student_no").input("admin")
    at.text_input(key="login_password").input(get_secret("ADMIN_PASSWORD"))
    at.button(key="login_submit").click().run()
    return at


def result(at: AppTest) -> str:
    texts = [e.value for kind in (at.success, at.info, at.warning) for e in kind]
    return next((t for t in texts if t.split(":")[0] in ("승인", "대기", "거절", "막힘")), "")


def texts(at: AppTest) -> str:
    return "\n".join(e.value for kind in (at.success, at.info, at.warning, at.error, at.markdown) for e in kind)


def final_check(label: str) -> None:
    state = db.load_state()
    teams, unassigned = db.snapshot(state)
    problems = [p for t, m in teams.items() for p in _team_problems(t, m)]
    expect(f"{label}: 확정 뒤 모든 팀이 규칙을 지킴", not problems and not unassigned,
           f"팀이 없는 학생 {len(unassigned)}명, 문제 {problems[:2]}")


def assign_and_confirm(label: str, fake_call, timeout=None) -> None:
    ai._call = fake_call
    if timeout is not None:
        ai.TIMEOUT_SEC = timeout
    at = admin_session()
    at.button(key="admin_assign").click().run()
    expect(f"{label}: AI 배정 단추", result(at).startswith("승인"), result(at))
    seen_waiting = False
    for _ in range(60):
        job = at.session_state["assign_job"]
        if "응답을 기다리는 중" in texts(at):
            seen_waiting = True
        if job.done:
            break
        time.sleep(0.5)
        at.run()
    at.run()
    expect(f"{label}: 진행 중 '몇 차 모델 응답을 기다리는 중' 안내", seen_waiting)
    print("   assign_status:", " / ".join(t for t in texts(at).split("\n") if "모델" in t or "배정안" in t)[:300])
    at.button(key="admin_confirm").click().run()
    expect(f"{label}: 확정 단추", result(at).startswith("승인"), result(at))
    final_check(label)


def slow_fail(model, messages, box):
    time.sleep(1.5)
    box["error"] = "HTTP 429 (가짜) 사용량 초과"


def scenario(name: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_scenarios.py"), name],
                   check=True, capture_output=True)


# 1) 중간 시나리오: 3개 모델 모두 오류 → 앱이 직접 배정
scenario("중간")
assign_and_confirm("중간/3차까지 오류", slow_fail)

# 2) 어려움 시나리오: 1·2차 시간 초과(제한 1초로 줄여 시험), 3차 빈 응답 → 앱이 직접 배정
scenario("어려움")
calls = {"n": 0}


def timeout_then_empty(model, messages, box):
    calls["n"] += 1
    if calls["n"] <= 2:
        time.sleep(3)  # 제한보다 늦게 옴
        box["content"] = "{}"
    else:
        box["content"] = ""


assign_and_confirm("어려움/시간 초과·빈 응답", timeout_then_empty, timeout=1)
ai.TIMEOUT_SEC = 120

# 3) 규칙을 지키는 배정이 없음: 팀 2개인데 웹 프로그래머를 맡을 학생이 1명뿐
db.reset_roster([Student("1", "가상A", "기획자"), Student("2", "가상B", "웹 프로그래머"),
                 Student("3", "가상C", "기획자"), Student("4", "가상D", "테스터")], 2)
db.close_recruiting()
ai._call = lambda *a: (_ for _ in ()).throw(AssertionError("AI 를 부르면 안 됨"))
at = admin_session()
at.button(key="admin_assign").click().run()
expect("배정 불가: 결과 안내 막힘", result(at).startswith("막힘"), result(at))
expect("배정 불가: assign_status 에 이유", "규칙을 지키는 배정이 없음" in texts(at) and "웹 프로그래머" in texts(at),
       next((t for t in texts(at).split("\n") if "웹 프로그래머" in t), ""))
expect("배정 불가: 확정 단추 없음", not any(b.key == "admin_confirm" for b in at.button))

def _drop_fake_logs(cur):
    cur.execute("delete from tf_ai_logs where model like 'test/%'")


db.run(_drop_fake_logs)
print("모두 통과" if failures == 0 else f"{failures}개 다름")
