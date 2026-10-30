"""학생 화면: 팀 목록, 지원, 내 팀에 들어온 지원에 투표. 3초마다 바뀐 부분만 다시 그린다."""

import streamlit as st

from tf import db
from tf.db import Account, State
from tf.ui_common import member_line, render_result, render_team_members, set_result

REFRESH = "3s"  # 다른 사람의 변경을 다시 그리는 간격(공고: 5초 이하)


def _on_apply(student_id: int, team_id: int) -> None:
    set_result(db.apply(student_id, team_id))


def _on_vote(voter_id: int, applicant_no: str, vote: str) -> None:
    set_result(db.vote(voter_id, applicant_no, vote))


def _my_pending(state: State, student_id: int):
    return next((a for a in state.pending if a.student_id == student_id), None)


def _render_votes(state: State, account: Account, my_team: int) -> None:
    applications = [a for a in state.pending if a.team_id == my_team]
    st.subheader("내 팀에 들어온 지원")
    if not applications:
        st.caption("대기 중인 지원 없음")
    members = state.teams[my_team]
    for a in applications:
        applicant = state.students[a.student_id]
        votes = state.votes.get(a.id, {})
        yes = sum(1 for m in members if votes.get(m) == "찬성")
        with st.container(border=True):
            st.markdown(f"**{member_line(state, a.student_id)}**")
            st.caption(f"찬성 {yes}/{len(members)}명")
            mine = votes.get(account.id)
            if mine:
                st.markdown(f"내 투표: {mine}")
            else:
                left, right = st.columns(2)
                left.button("찬성", key=f"vote_yes_{applicant.student_no}", on_click=_on_vote,
                            args=(account.id, applicant.student_no, "찬성"), width="stretch")
                right.button("거부", key=f"vote_no_{applicant.student_no}", on_click=_on_vote,
                             args=(account.id, applicant.student_no, "거부"), width="stretch")


@st.fragment(run_every=REFRESH)
def _live(account: Account) -> None:
    state = db.load_state()
    if account.id not in state.students:
        # 관리자가 명단을 다시 올려 이 계정이 지워졌으면 로그인 화면으로 돌아간다.
        st.session_state.pop("account", None)
        st.rerun(scope="app")

    render_result()

    my_team = state.team_of(account.id)
    pending = _my_pending(state, account.id)
    if state.closed:
        st.info("모집이 마감됨")
    if my_team:
        st.markdown(f"내 팀: **팀{my_team}**")
    else:
        st.markdown("아직 팀이 없음")
    if pending:
        st.markdown(f"팀{pending.team_id}에 지원함 — 결과를 기다리는 중")

    # 이미 팀이 있거나, 결과를 기다리는 지원이 있거나, 모집이 마감되었으면 지원 단추를 숨긴다(공고 2.8절).
    can_apply = not (my_team or pending or state.closed)

    cols = st.columns(2)
    for i, team_id in enumerate(state.teams):
        with cols[i % 2], st.container(key=f"team_{team_id}", border=True):
            st.markdown(f"**팀{team_id}**" + (" · 내 팀" if team_id == my_team else ""))
            render_team_members(state, team_id)
            if can_apply:
                st.button(f"팀{team_id}에 지원", key=f"apply_{team_id}", on_click=_on_apply,
                          args=(account.id, team_id))

    if my_team and not state.closed:
        _render_votes(state, account, my_team)


def render(account: Account) -> None:
    _live(account)
