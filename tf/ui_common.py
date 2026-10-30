"""학생 화면과 관리자 화면이 함께 쓰는 그리기 함수."""

import streamlit as st

from tf.db import State

RESULT_KEY = "result_message"  # st.session_state 에 마지막 결과 안내를 두는 이름


def set_result(message: str) -> None:
    """결과 안내를 남긴다. "승인", "대기", "거절", "막힘" 가운데 하나로 시작해야 한다."""
    st.session_state[RESULT_KEY] = message


def render_result() -> None:
    """단추를 누른 결과 안내(key=result)."""
    with st.container(key="result"):
        message = st.session_state.get(RESULT_KEY)
        if not message:
            return
        if message.startswith("승인"):
            st.success(message)
        elif message.startswith("대기"):
            st.info(message)
        else:
            st.warning(message)


def render_whoami(name: str, student_no: str) -> None:
    with st.container(key="whoami"):
        st.markdown(f"**{name}** ({student_no}) 님으로 로그인함")


def member_line(state: State, student_id: int) -> str:
    s = state.students[student_id]
    subs = ", ".join(s.sub_roles) if s.sub_roles else "없음"
    return f"{s.name} — 주 역할: {s.main_role} · 보조 역할: {subs}"


def render_team_members(state: State, team_id: int) -> None:
    members = state.teams[team_id]
    if not members:
        st.caption("팀원 없음")
    for student_id in members:
        st.markdown(f"- {member_line(state, student_id)}")
    st.caption(f"{len(members)}/4명")
