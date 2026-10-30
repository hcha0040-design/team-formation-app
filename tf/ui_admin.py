"""관리자 화면: 명단 올리기, 모집 마감, 팀 현황, 팀이 없는 학생, AI 배정과 확정."""

import time

import streamlit as st

from tf import ai, db
from tf.roster import RosterError, parse_roster
from tf.rules import explain_infeasible, search_assignment
from tf.ui_common import member_line, render_result, render_team_members, set_result

REFRESH = "3s"  # 다른 사람의 변경을 다시 그리는 간격(공고: 5초 이하)
JOB_KEY = "assign_job"            # 진행 중이거나 끝난 AI 배정(ai.AssignJob)
INFEASIBLE_KEY = "assign_infeasible"  # 규칙을 지키는 배정이 없을 때의 이유 목록


def _clear_assignment() -> None:
    st.session_state.pop(JOB_KEY, None)
    st.session_state.pop(INFEASIBLE_KEY, None)


def _start(uploaded, team_count: int) -> None:
    if uploaded is None:
        set_result("막힘: 명단 CSV 파일을 올려 주세요")
        return
    try:
        students = parse_roster(uploaded.getvalue())
    except RosterError as e:
        set_result(f"막힘: 명단이 틀림 — {e}")
        return
    db.reset_roster(students, int(team_count))
    _clear_assignment()  # 이전 명단으로 받은 배정안은 버린다
    set_result(f"승인: 명단으로 처음 상태를 만듦(학생 {len(students)}명, 팀 {int(team_count)}개)")


def _assign() -> None:
    job = st.session_state.get(JOB_KEY)
    if job is not None and not job.done:
        set_result("막힘: AI 배정이 이미 진행 중임")
        return
    state = db.load_state()
    if not state.closed:
        set_result("막힘: 모집을 마감한 뒤에 배정할 수 있음")
        return
    _clear_assignment()
    teams, unassigned = db.snapshot(state)

    # 먼저 앱이 규칙을 지키는 배정이 있는지 끝까지 찾아 본다. 없으면 AI 를 부르지 않는다(공고 2.5절 8항).
    fallback = search_assignment(teams, unassigned)
    if fallback is None:
        st.session_state[INFEASIBLE_KEY] = explain_infeasible(teams, unassigned)
        set_result("막힘: 규칙을 지키는 배정이 없음")
        return
    if not unassigned:
        job = ai.AssignJob(teams, unassigned, fallback, done=True, plan=[], source="팀이 없는 학생이 없음")
        st.session_state[JOB_KEY] = job
        set_result("승인: 배정할 학생이 없음(지금 팀 구성이 규칙을 지킴)")
        return

    job = ai.AssignJob(teams, unassigned, fallback)
    st.session_state[JOB_KEY] = job
    ai.start_job(job)
    set_result(f"승인: AI 배정을 시작함(팀이 없는 학생 {len(unassigned)}명). 진행 상황은 아래에 보임")


def _render_attempts(job: ai.AssignJob) -> None:
    for a in job.attempts:
        if a.outcome == "응답 기다리는 중":
            continue
        mark = "✅" if a.outcome == "성공" else "❌"
        st.markdown(f"{mark} {a.number}차 모델 `{a.model}` — **{a.outcome}** ({a.elapsed}초) {a.detail}")


def _render_plan(job: ai.AssignJob) -> None:
    by_no = {s.student_no: s for s in job.unassigned}
    rows = []
    for student_no, team_id in sorted(job.plan, key=lambda p: (p[1], p[0])):
        s = by_no[student_no]
        rows.append({"이름": s.name, "주 역할": s.main_role,
                     "보조 역할": ", ".join(s.sub_roles) or "없음", "배정된 팀": f"팀{team_id}"})
    st.dataframe(rows, hide_index=True, width="stretch")


@st.fragment(run_every="1s")
def _assign_panel() -> None:
    job: ai.AssignJob | None = st.session_state.get(JOB_KEY)
    reasons = st.session_state.get(INFEASIBLE_KEY)

    with st.container(key="assign_status", border=True):
        if reasons:
            st.error("규칙을 지키는 배정이 없음")
            for r in reasons:
                st.markdown(f"- {r}")
        elif job is None:
            st.caption("모집을 마감한 뒤 'AI 배정'을 누르면 진행 상황이 여기에 보임")
        elif not job.done:
            current = job.current
            waited = int(time.time() - job.started)
            st.info(f"{current.number}차 모델(`{current.model}`) 응답을 기다리는 중… "
                    f"{waited}초 / {ai.TIMEOUT_SEC}초")
            st.progress(min(waited / ai.TIMEOUT_SEC, 1.0))
            _render_attempts(job)
        else:
            if job.attempts and not job.logged:
                job.logged = True
                db.log_ai(job.attempts)
            st.success(f"검사를 통과한 배정안을 받음 — {job.source}")
            _render_attempts(job)

    if job is not None and job.done and job.plan:
        st.markdown("**배정안** (확정하면 저장됨)")
        _render_plan(job)
        if st.button("배정안 확정", key="admin_confirm", type="primary"):
            message = db.confirm_assignment(job.plan)
            set_result(message)
            if message.startswith("승인"):
                _clear_assignment()
            st.rerun(scope="app")


@st.fragment(run_every=REFRESH)
def _live() -> None:
    state = db.load_state()
    st.subheader("팀 현황" + (" (모집 마감됨)" if state.closed else ""))
    if not state.teams:
        st.info("아직 팀이 없음. 명단을 올려 주세요.")
    cols = st.columns(2)
    for i, team_id in enumerate(state.teams):
        with cols[i % 2], st.container(key=f"team_{team_id}", border=True):
            st.markdown(f"**팀{team_id}**")
            render_team_members(state, team_id)
            for a in state.pending:
                if a.team_id == team_id:
                    st.caption(f"대기 중인 지원: {state.students[a.student_id].name}")

    st.subheader("팀이 없는 학생")
    with st.container(key="unassigned", border=True):
        left = state.unassigned()
        if not left:
            st.write("없음")
        for student_id in left:
            st.markdown(f"- {member_line(state, student_id)}")


def render() -> None:
    render_result()

    with st.expander("명단 올리기(처음 상태 만들기)", expanded=True):
        uploaded = st.file_uploader("명단 CSV", type=["csv"], key="admin_roster_file")
        team_count = st.number_input("팀 수", min_value=1, max_value=20, value=4, step=1, key="admin_team_count")
        st.caption("시작하면 지원, 투표, 팀원, 마감 표시를 모두 지우고 명단의 학생과 빈 팀을 새로 만듦")
        if st.button("명단으로 처음 상태 만들기", key="admin_start", type="primary"):
            with st.spinner("처음 상태를 만드는 중…"):
                _start(uploaded, team_count)
            st.rerun()

    left, right = st.columns(2)
    with left:
        st.caption("마감하면 지원과 투표를 할 수 없고, 대기 중인 지원은 거절되며, 1명뿐인 팀의 학생은 팀에서 빠짐")
        if st.button("모집 마감", key="admin_close"):
            set_result(db.close_recruiting())
            st.rerun()
    with right:
        st.caption("팀이 없는 학생을 AI가 배정함. 1·2·3차 모델이 모두 실패하면 앱이 직접 배정함")
        if st.button("AI 배정", key="admin_assign"):
            _assign()
            st.rerun()

    _assign_panel()
    _live()
