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


# ---------------------------------------------------------------- 마감 뒤 배정
# 배정안(plan)은 (학번, 팀 번호) 쌍의 목록이다. 팀이 없는 학생만 넣고 기존 팀원은 옮기지 않는다.

Plan = list[tuple[str, int]]


def _team_problems(team_id: int, members: list[Student]) -> list[str]:
    """확정할 팀 하나가 규칙을 어기는 점(인원, 주 역할 중복, 필수 포함 역할)."""
    problems = []
    if not MIN_TEAM <= len(members) <= MAX_TEAM:
        problems.append(f"팀{team_id}이 {len(members)}명임(2~4명이어야 함)")
    mains = [m.main_role for m in members]
    for role in sorted({r for r in mains if mains.count(r) > 1}):
        problems.append(f"팀{team_id}에 주 역할 {role}가 {mains.count(role)}명임")
    if members and required_missing(members) > 0:
        problems.append(f"팀{team_id}에 필수 포함 역할(기획자, 웹 프로그래머)을 서로 다른 학생으로 채우지 못함")
    return problems


def validate_assignment(teams: dict[int, list[Student]], unassigned: list[Student], plan: Plan) -> list[str]:
    """배정안을 공고 2.5절 4항의 다섯 가지로 검사한다. 어긴 점의 목록(빈 목록이면 통과)."""
    problems = []
    by_no = {s.student_no: s for s in unassigned}
    counts: dict[str, int] = {}
    after = {team_id: list(members) for team_id, members in teams.items()}

    for student_no, team_id in plan:
        if student_no not in by_no:
            problems.append(f"학번 {student_no}은(는) 팀이 없는 학생이 아님")
            continue
        if team_id not in after:
            problems.append(f"{by_no[student_no].name}을(를) 없는 팀(팀{team_id})에 배정함")
            continue
        counts[student_no] = counts.get(student_no, 0) + 1
        if counts[student_no] == 1:
            after[team_id].append(by_no[student_no])

    # 1. 빠짐없이 배정  2. 한 학생은 한 팀에만
    for s in unassigned:
        if counts.get(s.student_no, 0) == 0:
            problems.append(f"{s.name}이(가) 배정에서 빠짐")
        elif counts[s.student_no] > 1:
            problems.append(f"{s.name}을(를) 여러 팀에 배정함")
    # 3. 인원  4. 주 역할 중복  5. 필수 포함 역할
    for team_id, members in after.items():
        problems.extend(_team_problems(team_id, members))
    return problems


def search_assignment(teams: dict[int, list[Student]], unassigned: list[Student]) -> Plan | None:
    """규칙을 모두 지키는 배정을 모든 경우를 따져(백트래킹) 끝까지 찾는다. 없으면 None."""
    team_ids = list(teams)
    current = {t: list(teams[t]) for t in team_ids}

    def fits(team_id: int, s: Student) -> bool:
        members = current[team_id]
        return len(members) < MAX_TEAM and all(m.main_role != s.main_role for m in members)

    def hopeless(left: int) -> bool:
        # 남은 학생으로는 2명이 안 되는 팀을 다 채울 수 없거나, 필수 역할을 채울 자리가 없는 팀이 있음
        if sum(max(0, MIN_TEAM - len(m)) for m in current.values()) > left:
            return True
        return any(m and MAX_TEAM - len(m) < required_missing(m) for m in current.values())

    # 들어갈 수 있는 팀이 적은 학생부터 정하면 빨리 끝난다.
    order = sorted(unassigned, key=lambda s: sum(fits(t, s) for t in team_ids))
    chosen: dict[str, int] = {}

    def place(i: int) -> bool:
        if hopeless(len(order) - i):
            return False
        if i == len(order):
            return all(not _team_problems(t, m) for t, m in current.items())
        s = order[i]
        tried_empty = False
        for team_id in team_ids:
            # 빈 팀끼리는 서로 바꿔도 같은 경우이므로 빈 팀은 하나만 해 본다.
            if not current[team_id]:
                if tried_empty:
                    continue
                tried_empty = True
            if fits(team_id, s):
                current[team_id].append(s)
                chosen[s.student_no] = team_id
                if place(i + 1):
                    return True
                current[team_id].pop()
                del chosen[s.student_no]
        return False

    if not place(0):
        return None
    return [(s.student_no, chosen[s.student_no]) for s in unassigned]


def explain_infeasible(teams: dict[int, list[Student]], unassigned: list[Student]) -> list[str]:
    """규칙을 지키는 배정이 없을 때 사람이 읽을 이유. 예: '팀3에 웹 프로그래머를 맡을 학생이 없음'"""
    reasons = []
    seats = sum(MAX_TEAM - len(m) for m in teams.values())
    if seats < len(unassigned):
        reasons.append(f"남은 자리가 {seats}개인데 팀이 없는 학생이 {len(unassigned)}명임")
    need = sum(max(0, MIN_TEAM - len(m)) for m in teams.values())
    if need > len(unassigned):
        reasons.append(f"2명이 안 되는 팀을 채우려면 {need}명이 필요한데 팀이 없는 학생이 {len(unassigned)}명임")

    for team_id, members in teams.items():
        mains = [m.main_role for m in members]
        dup = sorted({r for r in mains if mains.count(r) > 1})
        if dup:
            reasons.append(f"팀{team_id}에 주 역할 {', '.join(dup)}가 겹침")
        open_seats = MAX_TEAM - len(members)
        for role in REQUIRED_ROLES:
            if any(m.can_cover(role) for m in members):
                continue
            candidates = [s for s in unassigned if s.can_cover(role) and s.main_role not in mains]
            if open_seats == 0:
                reasons.append(f"팀{team_id}은 4명이 다 찼는데 {role}를 맡을 학생이 없음")
            elif not candidates:
                reasons.append(f"팀{team_id}에 {role}를 맡을 학생이 없음")
        if members and 0 < open_seats < required_missing(members):
            reasons.append(f"팀{team_id}은 남은 자리 {open_seats}개로 필수 포함 역할 {required_missing(members)}개를 채울 수 없음")

    for role in REQUIRED_ROLES:
        lacking = [t for t, m in teams.items() if not any(x.can_cover(role) for x in m)]
        able = [s for s in unassigned if s.can_cover(role)]
        if len(lacking) > len(able):
            reasons.append(f"{role}가 필요한 팀이 {len(lacking)}개인데 맡을 수 있는 학생이 {len(able)}명임")

    if not reasons:
        reasons.append("인원, 주 역할 중복, 필수 포함 역할을 모두 지키는 조합이 없음"
                       "(학생마다 들어갈 수 있는 팀이 겹쳐 모두 나눌 수 없음)")
    return reasons
