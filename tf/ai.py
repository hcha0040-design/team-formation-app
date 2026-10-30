"""오픈라우터 AI 배정. 1차 → 2차 → 3차 모델을 차례로 부르고, 모두 실패하면 앱이 찾은 배정을 쓴다.

- 모델마다 부른 때부터 응답을 다 받을 때까지 전체 120초를 재서, 넘으면 끊고 다음 모델로 넘어간다.
  (urllib 의 timeout 은 응답이 시작될 때까지만 재는 경우가 많아, 호출을 작업 스레드에서 하고
   기다리는 쪽에서 전체 시간을 잰다.)
- 화면이 멈추지 않도록 배정 전체를 백그라운드 스레드에서 하고, 진행 상황은 AssignJob 에 적는다.
  이 스레드에서는 Streamlit 이나 DB 를 쓰지 않는다.
"""

import json
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from config import get_openrouter_key
from tf.models import Student
from tf.rules import Plan, validate_assignment

API_URL = "https://openrouter.ai/api/v1/chat/completions"
# 10/30 시험(scripts/probe_models.py) 결과로 정함:
#   nemotron-3-ultra 성공(47초) / nemotron-3.5-super-vl 은 기존 팀원까지 적어 냄(지금은 그런 항목을 빼고 봄)
#   gemma-4-31b 는 그 시각 HTTP 429. inkling 은 HTTP 403(일반 앱에서 못 씀)이라 뺌
MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "google/gemma-4-31b-it:free",
]
TIMEOUT_SEC = 120


@dataclass
class Attempt:
    number: int          # 1차, 2차, 3차
    model: str
    outcome: str = "응답 기다리는 중"  # 성공, 시간 초과, 빈 응답, 오류, 검사 불합격
    detail: str = ""
    elapsed: float = 0.0


@dataclass
class AssignJob:
    teams: dict[int, list[Student]]
    unassigned: list[Student]
    fallback: Plan                    # 앱이 완전 탐색으로 찾아 둔 배정(3차까지 실패하면 씀)
    attempts: list[Attempt] = field(default_factory=list)
    started: float = 0.0              # 지금 부르는 모델을 부른 시각
    done: bool = False
    plan: Plan | None = None
    source: str = ""
    logged: bool = False              # tf_ai_logs 에 기록했는지

    @property
    def current(self) -> Attempt | None:
        return self.attempts[-1] if self.attempts and not self.done else None


# ---------------------------------------------------------------- 요청 만들기

def _describe(s: Student) -> str:
    subs = ", ".join(s.sub_roles) if s.sub_roles else "없음"
    return f"학번 {s.student_no} ({s.name}): 주 역할 {s.main_role}, 보조 역할 {subs}"


def build_messages(teams: dict[int, list[Student]], unassigned: list[Student]) -> list[dict]:
    lines = ["[지금의 팀 구성] (이미 팀에 있는 학생은 옮기지 않음)"]
    for team_id, members in teams.items():
        lines.append(f"팀{team_id} (현재 {len(members)}명)")
        if members:
            lines.extend(f"  - {_describe(m)}" for m in members)
        else:
            lines.append("  - 팀원 없음")
    lines.append("")
    lines.append(f"[팀이 없는 학생] {len(unassigned)}명")
    lines.extend(f"  - {_describe(s)}" for s in unassigned)

    rules = """[규칙] 배정이 끝난 뒤 모든 팀이 다음을 지켜야 한다.
1. 팀이 없는 학생을 빠짐없이, 한 학생은 한 팀에만 배정한다. 이미 팀에 있는 학생은 옮기지 않는다.
2. 모든 팀은 2~4명이다(빈 팀도 2명 이상이 되게 채운다).
3. 한 팀 안에 주 역할이 같은 학생이 2명 이상이면 안 된다(보조 역할은 겹쳐도 됨).
4. 모든 팀에 '기획자'를 맡을 학생과 '웹 프로그래머'를 맡을 학생이 서로 다른 사람으로 1명씩 있어야 한다.
   주 역할이나 보조 역할에 그 역할이 있으면 맡을 수 있다. 한 학생이 둘 다 맡을 수는 없다."""

    output = """[출력 형식] 설명 없이 아래 JSON 하나만 출력한다. team 은 팀 번호(정수)다.
assignments 에는 [팀이 없는 학생]만 한 번씩 넣는다(이미 팀에 있는 학생은 넣지 않는다).
{"assignments": [{"student_no": "2026001", "team": 1}, ...]}"""

    return [
        {"role": "system", "content": "너는 팀 배정을 돕는 도우미다. 규칙을 모두 지키는 배정을 찾아 JSON만 출력한다."},
        {"role": "user", "content": "\n".join(lines) + "\n\n" + rules + "\n\n" + output},
    ]


# ---------------------------------------------------------------- 응답 읽기

def parse_plan(content: str) -> Plan:
    """모델의 답에서 배정안을 꺼낸다. 코드 블록(```)이나 앞뒤 설명이 붙어 있어도 첫 { 부터 마지막 } 까지 읽는다."""
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end < start:
        raise ValueError("JSON 을 찾을 수 없음")
    data = json.loads(content[start:end + 1])
    items = data.get("assignments") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("assignments 목록이 없음")
    plan: Plan = []
    for item in items:
        student_no = str(item.get("student_no", "")).strip()
        team = item.get("team", item.get("team_id"))
        digits = re.search(r"\d+", str(team))
        if not student_no or digits is None:
            raise ValueError(f"항목을 읽을 수 없음: {item}")
        plan.append((student_no, int(digits.group())))
    return plan


def drop_unchanged_members(teams: dict[int, list[Student]], plan: Plan) -> Plan:
    """모델이 이미 팀에 있는 학생을 지금 팀 그대로 함께 적은 항목은 빼고 본다(옮긴 것이 아니므로).
    다른 팀으로 옮긴 항목은 그대로 두어 검사에서 걸리게 한다."""
    current = {m.student_no: team_id for team_id, members in teams.items() for m in members}
    return [(no, team) for no, team in plan if current.get(no) != team]


def _call(model: str, messages: list[dict], box: dict) -> None:
    """작업 스레드에서 실행. 결과를 box 에 넣는다(content 또는 error)."""
    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 6000,
        "temperature": 0.2,
        "reasoning": {"effort": "low"},  # 추론 모델이 생각하는 데 토큰을 다 써서 빈 응답을 내는 일을 줄인다
    }).encode()
    request = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {get_openrouter_key()}",
        "Content-Type": "application/json",
        "X-Title": "Team formation app",
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:
            data = json.load(response)
    except urllib.error.HTTPError as e:
        try:
            message = json.load(e).get("error", {}).get("message", "")
        except Exception:
            message = ""
        box["error"] = f"HTTP {e.code} {message}"[:200]
        return
    except Exception as e:  # 연결 실패, 읽기 시간 초과 등
        box["error"] = f"{type(e).__name__}: {e}"[:200]
        return
    if "error" in data:  # HTTP 200 인데 본문에 오류가 들어 있는 경우
        box["error"] = f"{data['error'].get('code', '')} {data['error'].get('message', '')}"[:200]
        return
    choices = data.get("choices") or [{}]
    box["content"] = (choices[0].get("message") or {}).get("content") or ""


# ---------------------------------------------------------------- 배정 진행

def _attempt(job: AssignJob, number: int, model: str, messages: list[dict]) -> bool:
    attempt = Attempt(number, model)
    job.started = time.time()
    job.attempts.append(attempt)

    box: dict = {}
    worker = threading.Thread(target=_call, args=(model, messages, box), daemon=True)
    worker.start()
    worker.join(TIMEOUT_SEC)  # 전체 대기 시간 120초
    attempt.elapsed = round(time.time() - job.started, 1)

    if worker.is_alive():
        attempt.outcome, attempt.detail = "시간 초과", f"{TIMEOUT_SEC}초 안에 응답을 다 받지 못해 끊음"
        return False
    if "error" in box:
        attempt.outcome, attempt.detail = "오류", box["error"]
        return False
    if not box.get("content", "").strip():
        attempt.outcome, attempt.detail = "빈 응답", "모델이 내용 없이 답함"
        return False
    try:
        plan = drop_unchanged_members(job.teams, parse_plan(box["content"]))
    except (ValueError, json.JSONDecodeError, AttributeError) as e:
        attempt.outcome, attempt.detail = "오류", f"응답 형식이 틀림: {e}"[:200]
        return False
    problems = validate_assignment(job.teams, job.unassigned, plan)
    if problems:
        attempt.outcome, attempt.detail = "검사 불합격", "; ".join(problems[:3])
        return False

    attempt.outcome, attempt.detail = "성공", f"{len(plan)}명 배정, 검사 5가지 통과"
    job.plan, job.source = plan, f"{number}차 모델({model})"
    return True


def run_job(job: AssignJob) -> None:
    messages = build_messages(job.teams, job.unassigned)
    try:
        for number, model in enumerate(MODELS, start=1):
            if _attempt(job, number, model, messages):
                return
        # 3차 모델까지 실패 → 앱이 완전 탐색으로 찾아 둔 배정을 쓴다.
        job.plan, job.source = job.fallback, "앱이 직접 찾은 배정(AI 모델 3개가 모두 실패)"
    except Exception as e:  # 예상하지 못한 오류에도 배정은 끝나야 한다
        if job.attempts and job.attempts[-1].outcome == "응답 기다리는 중":
            job.attempts[-1].outcome, job.attempts[-1].detail = "오류", f"{type(e).__name__}: {e}"[:200]
        job.plan, job.source = job.fallback, "앱이 직접 찾은 배정(AI 호출 중 오류)"
    finally:
        job.done = True


def start_job(job: AssignJob) -> None:
    threading.Thread(target=run_job, args=(job,), daemon=True).start()
