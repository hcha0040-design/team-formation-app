"""팀 프로젝트 팀 편성 앱. 실행: py -m streamlit run streamlit_app.py"""

import streamlit as st

from tf import db, ui_admin, ui_student
from tf.ui_common import RESULT_KEY, render_result, render_whoami, set_result

st.set_page_config(page_title="팀 편성", page_icon="👥", layout="wide")

db.init_db()


def login_screen() -> None:
    st.title("팀 편성")
    render_result()
    # 학번과 비밀번호를 폼으로 묶어 로그인 단추를 누를 때 한 번에 보낸다.
    # (칸마다 따로 보내면 빠르게 입력할 때 다시 그리기와 겹쳐 학번이 빠진 채 로그인되는 일이 있었음)
    with st.form("login_form", border=False):
        student_no = st.text_input("학번", key="login_student_no")
        password = st.text_input("비밀번호", type="password", key="login_password")
        submitted = st.form_submit_button("로그인", key="login_submit", type="primary")
    if submitted:
        account = db.authenticate(student_no, password)
        if account is None:
            set_result("막힘: 학번 또는 비밀번호가 틀림")
        else:
            st.session_state["account"] = account
            set_result(f"승인: {account.name} 님으로 로그인함")
        st.rerun()


def logout() -> None:
    for key in ("account", RESULT_KEY, "assign_job", "assign_infeasible"):
        st.session_state.pop(key, None)


account = st.session_state.get("account")
if account is None:
    login_screen()
else:
    top_left, top_right = st.columns([5, 1])
    with top_left:
        st.title("관리자" if account.is_admin else "팀 편성")
        render_whoami(account.name, account.student_no)
    with top_right:
        st.button("로그아웃", on_click=logout)

    if account.is_admin:
        ui_admin.render()
    else:
        ui_student.render(account)
