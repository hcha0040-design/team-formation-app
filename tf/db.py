"""Supabase(PostgreSQL) 접근. 연결은 풀 하나로 만들어 다시 쓴다."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import bcrypt
import psycopg2
import psycopg2.extras
import psycopg2.pool
import streamlit as st

from config import get_secret
from tf.models import Student
from tf.rules import check_join

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"
STUDENT_PASSWORD = "1234"  # 공고 2.2절: 학생의 비밀번호는 모두 1234


# ---------------------------------------------------------------- 연결

@st.cache_resource(show_spinner=False)
def _pool() -> psycopg2.pool.ThreadedConnectionPool:
    # 질의마다 새로 연결하면 느리므로 앱 전체에서 풀 하나를 만들어 둔다.
    # 세션(브라우저)마다 트랜잭션이 섞이지 않게 연결 하나를 같이 쓰지 않고 풀에서 빌린다.
    return psycopg2.pool.ThreadedConnectionPool(
        1, 5, get_secret("DATABASE_URL"), connect_timeout=15,
        keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
    )


_CONNECTION_ERRORS = (psycopg2.OperationalError, psycopg2.InterfaceError)


@contextmanager
def transaction(read_only: bool = False):
    """커서를 주고, 끝나면 커밋한다. 오류가 나면 되돌린다. 끊긴 연결은 버린다.
    read_only 이면 autocommit 으로 실행해 BEGIN/COMMIT 왕복 두 번을 아낀다(질의 하나짜리 읽기용)."""
    pool = _pool()
    conn = pool.getconn()
    broken = False
    try:
        if conn.closed:
            raise psycopg2.InterfaceError("연결이 닫혀 있음")
        conn.autocommit = read_only
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        if not read_only:
            conn.commit()
    except _CONNECTION_ERRORS:
        broken = True
        raise
    except BaseException:
        if not read_only:
            conn.rollback()
        raise
    finally:
        pool.putconn(conn, close=broken or bool(conn.closed))


def run(fn, *args, read_only: bool = False, **kwargs):
    """fn(cur, ...) 를 트랜잭션 안에서 실행한다. 연결이 끊겨 실패하면 새 연결로 한 번 더 한다.
    (트랜잭션이 통째로 되돌려지므로 다시 해도 안전하다)"""
    for attempt in range(2):
        try:
            with transaction(read_only) as cur:
                return fn(cur, *args, **kwargs)
        except _CONNECTION_ERRORS:
            if attempt == 1:
                raise


# ---------------------------------------------------------------- 준비

def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def _init(cur) -> None:
    cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    cur.execute("insert into tf_settings (key, value) values ('closed', 'false') on conflict (key) do nothing")

    # 관리자 계정을 ADMIN_PASSWORD 로 만들거나 비밀번호를 갱신한다(공고 2.1절).
    admin_password = get_secret("ADMIN_PASSWORD")
    cur.execute("select id, password_hash from tf_students where student_no = 'admin'")
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "insert into tf_students (student_no, name, main_role, password_hash, is_admin)"
            " values ('admin', '관리자', null, %s, true)",
            (_hash(admin_password),),
        )
    elif not _check(admin_password, row["password_hash"]):
        cur.execute("update tf_students set password_hash = %s, is_admin = true where id = %s",
                    (_hash(admin_password), row["id"]))


@st.cache_resource(show_spinner="DB 준비 중…")
def init_db() -> bool:
    """앱이 처음 뜰 때 한 번: 테이블을 만들고 관리자 계정을 맞춘다."""
    run(_init)
    return True


# ---------------------------------------------------------------- 명단과 로그인

def _reset(cur, students: list[Student], team_count: int) -> None:
    # 지원, 투표, 팀원, 팀, 학생(관리자 제외)을 모두 지우고 새로 만든다.
    cur.execute("delete from tf_votes")
    cur.execute("delete from tf_applications")
    cur.execute("delete from tf_members")
    cur.execute("delete from tf_teams")
    cur.execute("delete from tf_students where not is_admin")
    cur.execute("update tf_settings set value = 'false' where key = 'closed'")

    # 학생 비밀번호가 모두 같으므로 해시를 한 번만 만들어 함께 쓴다(bcrypt 는 한 번에 0.3초쯤 걸림).
    # DB가 멀어 왕복마다 시간이 들므로 행을 한 번에 묶어 넣는다.
    password_hash = _hash(STUDENT_PASSWORD)
    rows = psycopg2.extras.execute_values(
        cur,
        "insert into tf_students (student_no, name, main_role, password_hash) values %s returning id, student_no",
        [(s.student_no, s.name, s.main_role, password_hash) for s in students],
        fetch=True,
    )
    ids = {r["student_no"]: r["id"] for r in rows}
    sub_rows = [(ids[s.student_no], role) for s in students for role in s.sub_roles]
    if sub_rows:
        psycopg2.extras.execute_values(cur, "insert into tf_student_sub_roles (student_id, role) values %s", sub_rows)
    psycopg2.extras.execute_values(cur, "insert into tf_teams (id, name) values %s",
                                   [(n, f"팀{n}") for n in range(1, team_count + 1)])


def reset_roster(students: list[Student], team_count: int) -> None:
    run(_reset, students, team_count)


@dataclass
class Account:
    id: int
    student_no: str
    name: str
    is_admin: bool


def _authenticate(cur, student_no: str, password: str) -> Account | None:
    cur.execute("select id, student_no, name, is_admin, password_hash from tf_students where student_no = %s",
                (student_no,))
    row = cur.fetchone()
    if row is None or not _check(password, row["password_hash"]):
        return None
    return Account(row["id"], row["student_no"], row["name"], row["is_admin"])


def authenticate(student_no: str, password: str) -> Account | None:
    return run(_authenticate, student_no.strip(), password, read_only=True)


# ---------------------------------------------------------------- 화면용 상태

@dataclass
class Application:
    id: int
    team_id: int
    student_id: int
    status: str
    reason: str | None


@dataclass
class State:
    students: dict[int, Student]                  # tf_students.id → 학생(관리자 제외)
    teams: dict[int, list[int]]                   # 팀 번호 → 팀원 student_id 목록(자리 순서)
    closed: bool
    pending: list[Application]                    # 대기 중인 지원(지원한 순서)
    votes: dict[int, dict[int, str]] = field(default_factory=dict)  # 지원 id → {투표자 id: 찬성/거부}

    def team_of(self, student_id: int) -> int | None:
        for team_id, members in self.teams.items():
            if student_id in members:
                return team_id
        return None

    def unassigned(self) -> list[int]:
        placed = {sid for members in self.teams.values() for sid in members}
        return [sid for sid in self.students if sid not in placed]


# 화면을 한 번 그리는 데 필요한 것을 질의 한 번(왕복 한 번)으로 모두 가져온다.
_STATE_SQL = """
select
  (select coalesce(json_agg(x order by x.student_no), '[]') from (
     select s.id, s.student_no, s.name, s.main_role,
            coalesce(array_agg(r.role order by r.role) filter (where r.role is not null), '{}') as subs
     from tf_students s left join tf_student_sub_roles r on r.student_id = s.id
     where not s.is_admin group by s.id) x) as students,
  (select coalesce(json_agg(id order by id), '[]') from tf_teams) as teams,
  (select coalesce(json_agg(json_build_array(team_id, student_id) order by team_id, slot_no), '[]')
     from tf_members) as members,
  (select value = 'true' from tf_settings where key = 'closed') as closed,
  (select coalesce(json_agg(json_build_object('id', id, 'team_id', team_id, 'student_id', student_id,
                                              'status', status, 'reason', reason) order by created_at, id), '[]')
     from tf_applications where status = '대기') as pending,
  (select coalesce(json_agg(json_build_array(v.application_id, v.voter_id, v.vote)), '[]')
     from tf_votes v join tf_applications a on a.id = v.application_id where a.status = '대기') as votes
"""


def _load_state(cur) -> State:
    cur.execute(_STATE_SQL)
    row = cur.fetchone()

    students = {r["id"]: Student(r["student_no"], r["name"], r["main_role"], tuple(r["subs"]), r["id"])
                for r in row["students"]}
    teams: dict[int, list[int]] = {team_id: [] for team_id in row["teams"]}
    for team_id, student_id in row["members"]:
        teams[team_id].append(student_id)
    pending = [Application(**r) for r in row["pending"]]
    votes: dict[int, dict[int, str]] = {}
    for application_id, voter_id, vote in row["votes"]:
        votes.setdefault(application_id, {})[voter_id] = vote

    return State(students, teams, bool(row["closed"]), pending, votes)


def load_state() -> State:
    return run(_load_state, read_only=True)


# ---------------------------------------------------------------- 지원, 투표, 마감
# 모든 결과 안내는 "승인", "대기", "거절", "막힘" 가운데 하나로 시작한다.

BLOCK_CLOSED = "모집이 마감됨"
BLOCK_HAS_TEAM = "이미 팀이 있음"
BLOCK_PENDING = "결과를 기다리는 지원이 있음"


def _student(cur, student_id: int) -> Student:
    cur.execute("select s.id, s.student_no, s.name, s.main_role,"
                " coalesce(array_agg(r.role order by r.role) filter (where r.role is not null), '{}') as subs"
                " from tf_students s left join tf_student_sub_roles r on r.student_id = s.id"
                " where s.id = %s group by s.id", (student_id,))
    r = cur.fetchone()
    return Student(r["student_no"], r["name"], r["main_role"], tuple(r["subs"]), r["id"])


def _team_members(cur, team_id: int) -> list[Student]:
    cur.execute("select s.id, s.student_no, s.name, s.main_role,"
                " coalesce(array_agg(r.role order by r.role) filter (where r.role is not null), '{}') as subs"
                " from tf_members m join tf_students s on s.id = m.student_id"
                " left join tf_student_sub_roles r on r.student_id = s.id"
                " where m.team_id = %s group by s.id, m.slot_no order by m.slot_no", (team_id,))
    return [Student(r["student_no"], r["name"], r["main_role"], tuple(r["subs"]), r["id"]) for r in cur.fetchall()]


def _lock_team(cur, team_id: int) -> bool:
    # 같은 팀에 대한 지원과 승인을 한 번에 하나씩 처리하도록 팀 행을 잠근다.
    cur.execute("select id from tf_teams where id = %s for update", (team_id,))
    return cur.fetchone() is not None


def _is_closed(cur) -> bool:
    cur.execute("select value from tf_settings where key = 'closed'")
    row = cur.fetchone()
    return row is not None and row["value"] == "true"


def _add_member(cur, team_id: int, student_id: int) -> None:
    """비어 있는 가장 작은 자리에 넣는다. 자리나 학생이 겹치면 DB 유일성 제약이 막는다."""
    cur.execute("select coalesce(min(n), 0) as slot from generate_series(1, 4) n"
                " where n not in (select slot_no from tf_members where team_id = %s)", (team_id,))
    slot = cur.fetchone()["slot"]
    if slot == 0:
        raise psycopg2.errors.CheckViolation("빈 자리 없음")
    cur.execute("insert into tf_members (team_id, slot_no, student_id) values (%s, %s, %s)",
                (team_id, slot, student_id))


def _apply(cur, student_id: int, team_id: int) -> str:
    if not _lock_team(cur, team_id):
        return f"막힘: 팀{team_id}이 없음"
    if _is_closed(cur):
        return f"막힘: {BLOCK_CLOSED}"
    cur.execute("select 1 from tf_members where student_id = %s", (student_id,))
    if cur.fetchone():
        return f"막힘: {BLOCK_HAS_TEAM}"
    cur.execute("select 1 from tf_applications where student_id = %s and status = '대기'", (student_id,))
    if cur.fetchone():
        return f"막힘: {BLOCK_PENDING}"

    members = _team_members(cur, team_id)
    reason = check_join(members, _student(cur, student_id))
    if reason:
        return f"막힘: {reason}"

    if not members:
        # 빈 팀: 투표할 팀원이 없으므로 바로 승인
        _add_member(cur, team_id, student_id)
        cur.execute("insert into tf_applications (team_id, student_id, status, decided_at)"
                    " values (%s, %s, '승인', now())", (team_id, student_id))
        return f"승인: 팀{team_id}의 팀원이 됨"

    cur.execute("insert into tf_applications (team_id, student_id, status) values (%s, %s, '대기')",
                (team_id, student_id))
    return f"대기: 팀{team_id} 팀원 {len(members)}명의 투표를 기다림"


def apply(student_id: int, team_id: int) -> str:
    try:
        return run(_apply, student_id, team_id)
    except psycopg2.IntegrityError:
        # 같은 순간 다른 지원이 먼저 기록됨(마지막 자리, 대기 지원 1개 제약)
        return "막힘: 다른 지원이 먼저 처리됨. 다시 시도해 주세요"


def _reject(cur, application_id: int, reason: str) -> None:
    cur.execute("update tf_applications set status = '거절', reason = %s, decided_at = now() where id = %s",
                (reason, application_id))


def _vote(cur, voter_id: int, applicant_no: str, vote: str) -> str:
    cur.execute("select a.id, a.team_id, a.student_id, a.status from tf_applications a"
                " join tf_students s on s.id = a.student_id"
                " where s.student_no = %s order by a.created_at desc, a.id desc limit 1", (applicant_no,))
    app = cur.fetchone()
    if app is None:
        return "막힘: 지원을 찾을 수 없음"
    _lock_team(cur, app["team_id"])
    cur.execute("select status, reason from tf_applications where id = %s", (app["id"],))
    current = cur.fetchone()  # 잠근 뒤 다시 읽는다(그 사이 다른 투표로 결과가 났을 수 있음)
    if current["status"] != "대기":
        return f"{current['status']}: 이미 결과가 나온 지원임" + (f"({current['reason']})" if current["reason"] else "")
    if _is_closed(cur):
        return f"막힘: {BLOCK_CLOSED}"

    members = _team_members(cur, app["team_id"])
    if voter_id not in {m.id for m in members}:
        return "막힘: 이 팀의 팀원만 투표할 수 있음"
    cur.execute("insert into tf_votes (application_id, voter_id, vote) values (%s, %s, %s)"
                " on conflict do nothing returning 1", (app["id"], voter_id, vote))
    if cur.fetchone() is None:
        return "막힘: 이미 투표함(투표는 바꿀 수 없음)"

    if vote == "거부":
        _reject(cur, app["id"], "팀원의 거부")
        return "거절: 팀원이 거부함"

    # 투표할 사람은 지금의 팀원 전체다.
    cur.execute("select voter_id, vote from tf_votes where application_id = %s", (app["id"],))
    votes = {r["voter_id"]: r["vote"] for r in cur.fetchall()}
    yes = sum(1 for m in members if votes.get(m.id) == "찬성")
    if yes < len(members):
        return f"대기: 찬성 {yes}/{len(members)}명"

    # 모든 팀원이 찬성 → 승인 직전에 규칙을 다시 검사한다(앞의 지원이 먼저 승인되어 팀이 바뀌었을 수 있음).
    reason = check_join(members, _student(cur, app["student_id"]))
    if reason:
        _reject(cur, app["id"], f"승인 직전 검사: {reason}")
        return f"거절: 승인 직전 검사에서 규칙 위반({reason})"
    _add_member(cur, app["team_id"], app["student_id"])
    cur.execute("update tf_applications set status = '승인', decided_at = now() where id = %s", (app["id"],))
    return f"승인: 팀{app['team_id']}의 팀원이 됨"


def vote(voter_id: int, applicant_no: str, vote: str) -> str:
    try:
        return run(_vote, voter_id, applicant_no, vote)
    except psycopg2.IntegrityError:
        return "막힘: 다른 처리가 먼저 끝남. 다시 시도해 주세요"


def _close(cur) -> str:
    cur.execute("lock table tf_members in exclusive mode")  # 마감 중에 승인이 끼어들지 않게
    if _is_closed(cur):
        return "막힘: 이미 모집이 마감됨"
    cur.execute("update tf_settings set value = 'true' where key = 'closed'")
    cur.execute("update tf_applications set status = '거절', reason = '모집 마감', decided_at = now()"
                " where status = '대기'")
    rejected = cur.rowcount
    # 1명뿐인 팀의 학생은 팀에서 빠져 팀이 없는 학생이 된다.
    cur.execute("delete from tf_members where team_id in"
                " (select team_id from tf_members group by team_id having count(*) = 1)")
    removed = cur.rowcount
    return f"승인: 모집을 마감함(대기 지원 {rejected}건 거절, 1명뿐인 팀에서 {removed}명이 빠짐)"


def close_recruiting() -> str:
    return run(_close)
