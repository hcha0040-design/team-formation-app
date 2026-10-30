"""관리자 화면: 명단 올리기, 모집 마감, 팀 현황, 팀이 없는 학생."""

import streamlit as st

from tf import db
from tf.roster import RosterError, parse_roster
from tf.ui_common import member_line, render_result, render_team_members, set_result

REFRESH = "3s"  # 다른 사람의 변경을 다시 그리는 간격(공고: 5초 이하)


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
    st.session_state.pop("plan", None)  # 이전 명단으로 받은 배정안은 버린다
    set_result(f"승인: 명단으로 처음 상태를 만듦(학생 {len(students)}명, 팀 {int(team_count)}개)")


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

    st.caption("마감하면 지원과 투표를 할 수 없고, 대기 중인 지원은 거절되며, 1명뿐인 팀의 학생은 팀에서 빠짐")
    if st.button("모집 마감", key="admin_close"):
        set_result(db.close_recruiting())
        st.rerun()

    _live()
