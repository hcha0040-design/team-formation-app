"""팀 규칙 계산(DB 없이 학생 목록만으로). 지원, 승인 직전 재검사, 배정 검사가 함께 쓴다."""

from tf.models import REQUIRED_ROLES, Student

MAX_TEAM = 4
MIN_TEAM = 2

BLOCK_FULL = "팀이 꽉 참"
BLOCK_DUP_ROLE = "같은 주 역할의 팀원이 있음"
BLOCK_REQUIRED = "필수 포함 역할을 맡을 학생의 자리가 모자람"


def required_filled(members: list[Student]) -> int:
    """필수 포함 역할(기획자, 웹 프로그래머) 가운데 서로 다른 학생으로 채울 수 있는 수(0~2).
    한 학생이 둘 다 할 수 있어도 하나로만 센다."""
    planner, web = REQUIRED_ROLES
    can_plan = [m.student_no for m in members if m.can_cover(planner)]
    can_web = [m.student_no for m in members if m.can_cover(web)]
    if can_plan and can_web and any(a != b for a in can_plan for b in can_web):
        return 2
    return 1 if (can_plan or can_web) else 0


def required_missing(members: list[Student]) -> int:
    return len(REQUIRED_ROLES) - required_filled(members)


def check_join(members: list[Student], newcomer: Student) -> str | None:
    """newcomer 가 이 팀에 들어갈 수 없으면 그 이유를, 들어갈 수 있으면 None 을 돌려준다.
    지원할 때와 승인 직전 재검사 때 같은 함수를 쓴다."""
    if len(members) >= MAX_TEAM:
        return BLOCK_FULL
    if any(m.main_role == newcomer.main_role for m in members):
        return BLOCK_DUP_ROLE
    after = members + [newcomer]
    # 들어간 뒤 남는 자리 수가 아직 못 채운 필수 포함 역할 수보다 적으면 막는다(공고 3장).
    if MAX_TEAM - len(after) < required_missing(after):
        return BLOCK_REQUIRED
    return None
