from itertools import product

from tf.models import Student
from tf.rules import explain_infeasible, search_assignment, validate_assignment

PL, WP, FD, TT, RW, PT = "기획자", "웹 프로그래머", "프론트엔드 디자이너", "테스터", "보고서 작성자", "발표자"


def S(no, main, *subs):
    return Student(str(no), f"학생{no}", main, tuple(subs))


def hard_after_close():
    """어려움 연습 시나리오 14단계(마감) 뒤의 상태."""
    teams = {
        1: [S(1, PL, RW), S(4, WP, PL), S(7, FD, PT, TT)],
        2: [S(2, PL, PT), S(8, FD, TT), S(5, WP, FD)],
        3: [S(11, TT, PT), S(15, PT, FD)],
        4: [],
    }
    unassigned = [S(3, PL, TT), S(6, WP, RW), S(9, FD, WP), S(10, TT, RW), S(12, TT, PL),
                  S(13, RW, PT, FD), S(14, RW, TT), S(16, PT)]
    return teams, unassigned


def medium_after_close():
    teams = {1: [S(1, PL, PT, TT), S(5, WP, TT)], 2: [S(6, WP, FD), S(9, FD, WP)], 3: [], 4: []}
    unassigned = [S(2, PL, TT), S(3, PL, RW), S(4, PL), S(7, WP), S(8, WP, PT), S(10, TT, PL),
                  S(11, RW), S(12, PT, RW, FD)]
    return teams, unassigned


# ------------------------------------------------------------ validate_assignment

def test_validate_accepts_good_plan():
    teams = {1: [S(1, PL), S(2, WP)], 2: []}
    unassigned = [S(3, PL), S(4, WP)]
    assert validate_assignment(teams, unassigned, [("3", 2), ("4", 2)]) == []


def test_validate_reports_each_rule():
    teams = {1: [S(1, PL), S(2, WP)], 2: []}
    unassigned = [S(3, PL), S(4, WP), S(5, TT)]
    # 학생5 빠짐
    assert any("빠짐" in v for v in validate_assignment(teams, unassigned, [("3", 2), ("4", 2)]))
    # 학생3 두 번
    assert any("두 팀" in v or "여러" in v for v in
               validate_assignment(teams, unassigned, [("3", 2), ("3", 1), ("4", 2), ("5", 1)]))
    # 팀2 1명
    assert any("2~4명" in v for v in validate_assignment(teams, unassigned, [("3", 2), ("4", 1), ("5", 1)]))
    # 팀1에 기획자 중복
    assert any("주 역할" in v for v in validate_assignment(teams, unassigned, [("3", 1), ("4", 2), ("5", 2)]))
    # 팀2에 웹 프로그래머 없음
    assert any("필수" in v for v in validate_assignment(teams, unassigned, [("3", 2), ("5", 2), ("4", 1)]))


def test_validate_rejects_unknown_student_and_team():
    teams = {1: [S(1, PL), S(2, WP)]}
    unassigned = [S(3, TT)]
    assert validate_assignment(teams, unassigned, [("3", 9)])
    assert validate_assignment(teams, unassigned, [("3", 1), ("1", 1)])  # 이미 팀이 있는 학생을 옮김
    assert validate_assignment(teams, unassigned, [("3", 1), ("99", 1)])


# ------------------------------------------------------------ search_assignment

def test_search_finds_valid_plan_for_practice_states():
    for teams, unassigned in (hard_after_close(), medium_after_close()):
        plan = search_assignment(teams, unassigned)
        assert plan is not None
        assert validate_assignment(teams, unassigned, plan) == []


def test_search_matches_brute_force_on_small_cases():
    # 작은 경우를 모든 조합으로 따져 본 결과와 같은지(있다/없다) 확인한다.
    pool = [S(1, PL), S(2, WP), S(3, TT, PL), S(4, FD, WP), S(5, RW), S(6, PT)]
    teams = {1: [S(10, TT)], 2: [], 3: [S(11, PL, WP)]}
    for size in range(1, 6):
        unassigned = pool[:size]
        brute = any(
            validate_assignment(teams, unassigned, list(zip([s.student_no for s in unassigned], combo))) == []
            for combo in product(teams, repeat=size)
        )
        assert (search_assignment(teams, unassigned) is not None) == brute


def test_search_returns_none_when_full_team_lacks_role():
    teams = {1: [S(1, PL), S(2, FD), S(3, TT), S(4, RW)], 2: []}
    assert search_assignment(teams, [S(5, PL), S(6, WP)]) is None


def test_search_uses_sub_roles():
    # 웹 프로그래머는 보조 역할로만 맡을 수 있음
    teams = {1: [S(1, PL)]}
    plan = search_assignment(teams, [S(2, FD, WP)])
    assert plan == [("2", 1)]


# ------------------------------------------------------------ explain_infeasible

def test_explain_full_team_without_role():
    teams = {1: [S(1, PL), S(2, FD), S(3, TT), S(4, RW)], 2: []}
    reasons = explain_infeasible(teams, [S(5, PL), S(6, WP)])
    assert any("팀1" in r and "웹 프로그래머" in r for r in reasons)


def test_explain_no_candidate_for_role():
    teams = {1: [S(1, PL)], 2: [S(2, PL, WP)]}
    reasons = explain_infeasible(teams, [S(3, TT)])
    assert any("팀1" in r and "웹 프로그래머" in r for r in reasons)


def test_explain_not_enough_seats():
    teams = {1: [S(1, PL), S(2, WP), S(3, FD)]}
    reasons = explain_infeasible(teams, [S(4, TT), S(5, RW)])
    assert any("자리" in r for r in reasons)


def test_explain_always_gives_a_reason():
    teams = {1: [S(1, PL), S(2, WP)], 2: [S(3, PL), S(4, WP)]}
    # 둘 다 테스터라 한 팀에 못 들어가고, 각 팀에 하나씩 넣으면 됨 → 사실은 가능. 불가능한 예:
    unassigned = [S(5, PL), S(6, PL), S(7, PL)]  # 기획자 3명을 두 팀(이미 기획자 있음)에 못 넣음
    assert search_assignment(teams, unassigned) is None
    assert explain_infeasible(teams, unassigned)


def test_search_is_fast_with_everyone_unassigned():
    # 아무도 팀에 들어가지 않고 마감한 경우(어려움 명단 16명, 빈 팀 4개)도 바로 끝나야 한다.
    import time
    from pathlib import Path

    from tf.roster import parse_roster

    students = parse_roster((Path(__file__).resolve().parent.parent / "data" / "어려움.csv").read_bytes())
    teams = {1: [], 2: [], 3: [], 4: []}
    start = time.time()
    plan = search_assignment(teams, students)
    assert time.time() - start < 2
    assert plan is not None and validate_assignment(teams, students, plan) == []


def test_search_is_fast_when_impossible():
    # 웹 프로그래머가 아무도 없으면 불가능 — 끝까지 따져도 빨리 끝나야 한다.
    import time

    teams = {1: [], 2: [], 3: []}
    unassigned = [S(i, role) for i, role in enumerate([PL, FD, TT, RW, PT, PL, FD, TT], start=1)]
    start = time.time()
    assert search_assignment(teams, unassigned) is None
    assert time.time() - start < 2
    assert any("웹 프로그래머" in r for r in explain_infeasible(teams, unassigned))
