"""AI 배정의 실패 처리를 실제 호출 없이 시험한다(_call 을 가짜로 바꿈)."""

import time

import pytest

from tf import ai
from tf.models import Student

PL, WP, TT = "기획자", "웹 프로그래머", "테스터"


def S(no, main, *subs):
    return Student(str(no), f"학생{no}", main, tuple(subs))


TEAMS = {1: [S(1, PL)], 2: [S(2, PL)]}
UNASSIGNED = [S(3, WP), S(4, WP)]
GOOD = '{"assignments": [{"student_no": "3", "team": 1}, {"student_no": "4", "team": 2}]}'
BAD = '{"assignments": [{"student_no": "3", "team": 1}, {"student_no": "4", "team": 1}]}'  # 팀1에 웹 프로그래머 2명
FALLBACK = [("3", 2), ("4", 1)]


def make_job():
    return ai.AssignJob(TEAMS, UNASSIGNED, FALLBACK)


def fake_calls(monkeypatch, behaviours):
    """모델을 부를 때마다 behaviours 의 다음 동작을 한다: 문자열(내용), ("error", 메시지), ("sleep", 초)."""
    queue = list(behaviours)

    def _call(model, messages, box):
        b = queue.pop(0)
        if isinstance(b, tuple) and b[0] == "sleep":
            time.sleep(b[1])
            box["content"] = GOOD
        elif isinstance(b, tuple):
            box["error"] = b[1]
        else:
            box["content"] = b

    monkeypatch.setattr(ai, "_call", _call)


def test_parse_plan_handles_code_fence_and_team_names():
    content = '설명\n```json\n{"assignments":[{"student_no":2026301,"team":"팀2"}]}\n```'
    assert ai.parse_plan(content) == [("2026301", 2)]


def test_parse_plan_rejects_garbage():
    with pytest.raises(ValueError):
        ai.parse_plan("배정할 수 없습니다")


def test_first_model_success(monkeypatch):
    fake_calls(monkeypatch, [GOOD])
    job = make_job()
    ai.run_job(job)
    assert job.done and job.plan == [("3", 1), ("4", 2)]
    assert job.source.startswith("1차")
    assert [a.outcome for a in job.attempts] == ["성공"]


def test_falls_through_error_empty_and_invalid(monkeypatch):
    fake_calls(monkeypatch, [("error", "HTTP 429 rate limited"), "", BAD])
    job = make_job()
    ai.run_job(job)
    assert [a.outcome for a in job.attempts] == ["오류", "빈 응답", "검사 불합격"]
    assert job.plan == FALLBACK and "직접" in job.source


def test_second_model_success_after_bad_plan(monkeypatch):
    fake_calls(monkeypatch, [BAD, GOOD])
    job = make_job()
    ai.run_job(job)
    assert [a.outcome for a in job.attempts] == ["검사 불합격", "성공"]
    assert job.source.startswith("2차")


def test_total_timeout_per_model(monkeypatch):
    # 응답이 제한 시간보다 늦으면(천천히 오는 경우 포함) 끊고 다음 모델로 넘어간다.
    monkeypatch.setattr(ai, "TIMEOUT_SEC", 0.3)
    fake_calls(monkeypatch, [("sleep", 2), GOOD])
    job = make_job()
    start = time.time()
    ai.run_job(job)
    assert time.time() - start < 1.5
    assert [a.outcome for a in job.attempts] == ["시간 초과", "성공"]


def test_existing_members_in_their_own_team_are_ignored(monkeypatch):
    # 모델이 기존 팀원을 지금 팀 그대로 함께 적으면 빼고 검사한다.
    with_members = ('{"assignments": [{"student_no": "1", "team": 1}, {"student_no": "2", "team": 2},'
                    ' {"student_no": "3", "team": 1}, {"student_no": "4", "team": 2}]}')
    fake_calls(monkeypatch, [with_members])
    job = make_job()
    ai.run_job(job)
    assert [a.outcome for a in job.attempts] == ["성공"]
    assert job.plan == [("3", 1), ("4", 2)]


def test_moving_an_existing_member_still_fails(monkeypatch):
    moved = ('{"assignments": [{"student_no": "1", "team": 2},'
             ' {"student_no": "3", "team": 1}, {"student_no": "4", "team": 2}]}')
    fake_calls(monkeypatch, [moved, GOOD])
    job = make_job()
    ai.run_job(job)
    assert [a.outcome for a in job.attempts] == ["검사 불합격", "성공"]
