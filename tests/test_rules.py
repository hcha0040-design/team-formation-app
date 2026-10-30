from tf.models import Student
from tf.rules import BLOCK_DUP_ROLE, BLOCK_FULL, BLOCK_REQUIRED, check_join, required_filled


def S(no, main, *subs):
    return Student(str(no), f"학생{no}", main, tuple(subs))


PL, WP, FD, TT, RW, PT = "기획자", "웹 프로그래머", "프론트엔드 디자이너", "테스터", "보고서 작성자", "발표자"


# ------------------------------------------------------------ required_filled

def test_required_filled_counts_distinct_students():
    assert required_filled([]) == 0
    assert required_filled([S(1, TT), S(2, PT)]) == 0
    assert required_filled([S(1, PL)]) == 1
    assert required_filled([S(1, PL), S(2, WP)]) == 2


def test_one_student_covering_both_counts_once():
    # 공고 3장 예: 주 역할 기획자, 보조 역할 웹 프로그래머인 학생 혼자 → 1개만 채움
    assert required_filled([S(1, PL, WP)]) == 1


def test_sub_roles_count():
    assert required_filled([S(1, TT, PL), S(2, FD, WP)]) == 2


def test_matching_picks_the_right_pairing():
    # 1은 둘 다, 2는 기획자만 → 2가 기획자, 1이 웹 프로그래머
    assert required_filled([S(1, PL, WP), S(2, TT, PL)]) == 2
    # 둘 다 기획자만 가능 → 1
    assert required_filled([S(1, PL), S(2, TT, PL)]) == 1


# ------------------------------------------------------------ check_join

def test_join_empty_team_is_ok():
    assert check_join([], S(1, RW)) is None


def test_full_team_blocks():
    team = [S(1, PL), S(2, WP), S(3, FD), S(4, TT)]
    assert check_join(team, S(5, RW)) == BLOCK_FULL


def test_same_main_role_blocks():
    assert check_join([S(1, PL, PT, TT), S(5, WP, TT)], S(2, PL, TT)) == BLOCK_DUP_ROLE


def test_sub_role_overlap_is_not_duplicate():
    # 주 역할만 중복을 따진다
    assert check_join([S(1, PL, TT)], S(2, TT)) is None


def test_required_slot_example_from_notice():
    # 공고 3장 예: 테스터와 발표자만 있는 팀(2명)에 보고서 작성자가 지원 → 남는 1자리로 2개를 못 채움
    assert check_join([S(1, TT), S(2, PT)], S(3, RW)) == BLOCK_REQUIRED


def test_required_slot_allows_when_newcomer_fills_a_role():
    # 테스터, 발표자 팀에 기획자가 들어가면 남는 1자리로 웹 프로그래머 1개를 채울 수 있음
    assert check_join([S(1, TT), S(2, PT)], S(3, PL)) is None


def test_required_slot_with_three_members_and_one_missing():
    # 3명이 차고 웹 프로그래머가 없으면 4번째는 웹 프로그래머를 맡을 수 있어야 함
    team = [S(1, PL), S(2, FD), S(3, TT)]
    assert check_join(team, S(4, RW)) == BLOCK_REQUIRED
    assert check_join(team, S(4, RW, WP)) is None


def test_hard_scenario_step11_shape():
    # 테스터(보조 발표자)와 발표자(보조 FD) 2명 팀에 보고서 작성자(보조 테스터)가 지원 → 막힘
    assert check_join([S(11, TT, PT), S(15, PT, FD)], S(14, RW, TT)) == BLOCK_REQUIRED


def test_hard_scenario_step8_shape_recheck_at_approval():
    # 지원할 때(팀원 2명)는 통과, 같은 주 역할의 학생이 먼저 승인된 뒤 다시 검사하면 막힘
    team = [S(2, PL, PT), S(8, FD, TT)]
    applicant = S(6, WP, RW)
    assert check_join(team, applicant) is None
    assert check_join(team + [S(5, WP, FD)], applicant) == BLOCK_DUP_ROLE
