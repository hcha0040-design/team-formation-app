"""화면을 브라우저 없이(Streamlit AppTest) key 로 조작해, 자동 채점처럼 학생마다 세션을 따로 열어 본다.

실행: py scripts/ui_check.py
어려움 시나리오를 6단계까지 DB 함수로 만든 뒤, 7~8단계(투표)와 11단계(막힘)를 화면 단추로 해 본다.
주의: 실행하면 DB의 명단이 어려움 시나리오로 바뀐다.
"""

import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)

from streamlit.testing.v1 import AppTest  # noqa: E402

subprocess.run([sys.executable, str(ROOT / "scripts" / "run_scenarios.py"), "어려움", "--until", "6"],
               check=True, capture_output=True)


def login(student_no: str) -> AppTest:
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
    at.run()
    at.text_input(key="login_student_no").input(student_no)
    at.text_input(key="login_password").input("1234")
    at.button(key="login_submit").click().run()
    return at


def result(at: AppTest) -> str:
    for kind in (at.success, at.info, at.warning):
        for el in kind:
            if el.value.split(":")[0] in ("승인", "대기", "거절", "막힘"):
                last = el.value
    return last


def keys(at: AppTest) -> list[str]:
    return [b.key for b in at.button if b.key]


failures = 0


def expect(label: str, got: str, want: str) -> None:
    global failures
    ok = got.split(":")[0] == want
    failures += not ok
    print(f"{'OK' if ok else 'XX'} {label:<40} 기대 {want} | {got}")


s2 = login("2026302")
print("학생2 화면의 단추 key:", keys(s2))
s2.button(key="vote_yes_2026305").click().run()
expect("7단계 학생2 → 학생5 찬성", result(s2), "대기")
print("   찬성 뒤 학생2의 학생5 단추 남음:", "vote_yes_2026305" in keys(s2),
      "| '내 투표: 찬성' 보임:", any("내 투표: 찬성" in m.value for m in s2.markdown))

s8 = login("2026308")
s8.button(key="vote_yes_2026305").click().run()
expect("7단계 학생8 → 학생5 찬성", result(s8), "승인")

s2.button(key="vote_yes_2026306").click().run()
expect("8단계 학생2 → 학생6 찬성", result(s2), "대기")
s8.button(key="vote_yes_2026306").click().run()
expect("8단계 학생8 → 학생6 찬성", result(s8), "대기")
s5 = login("2026305")
print("학생5 화면의 단추 key:", keys(s5))
s5.button(key="vote_yes_2026306").click().run()
expect("8단계 학생5 → 학생6 찬성", result(s5), "거절")

s11 = login("2026311")
s11.button(key="apply_3").click().run()
expect("9단계 학생11 → 팀3 지원", result(s11), "승인")
print("   팀이 생긴 뒤 지원 단추 숨김:", not any(k.startswith("apply_") for k in keys(s11)))
s15 = login("2026315")
s15.button(key="apply_3").click().run()
expect("10단계 학생15 → 팀3 지원", result(s15), "대기")
print("   대기 중 지원 단추 숨김:", not any(k.startswith("apply_") for k in keys(s15)))
s11.run()  # 자동 갱신과 같은 효과: 다시 그려 새 지원을 봄
s11.button(key="vote_yes_2026315").click().run()
expect("10단계 학생11 → 학생15 찬성", result(s11), "승인")
s14 = login("2026314")
s14.button(key="apply_3").click().run()
expect("11단계 학생14 → 팀3 지원", result(s14), "막힘")

s10 = login("2026310")
s10.button(key="apply_4").click().run()
expect("12단계 학생10 → 팀4 지원", result(s10), "승인")
s13 = login("2026313")
s13.button(key="apply_1").click().run()
expect("13단계 학생13 → 팀1 지원", result(s13), "대기")
s1 = login("2026301")
s1.button(key="vote_yes_2026313").click().run()
expect("13단계 학생1 → 학생13 찬성", result(s1), "대기")

# 관리자: 비밀번호는 .env 에서 읽어 넣기만 하고 출력하지 않는다.
from config import get_secret  # noqa: E402

admin = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
admin.run()
admin.text_input(key="login_student_no").input("admin")
admin.text_input(key="login_password").input(get_secret("ADMIN_PASSWORD"))
admin.button(key="login_submit").click().run()
print("관리자 화면의 단추 key:", keys(admin))
admin.button(key="admin_close").click().run()
expect("14단계 관리자 모집 마감", result(admin), "승인")
unassigned_text = " ".join(m.value for m in admin.markdown)
print("   팀이 없는 학생에 학생10, 학생13:", "학생10(" in unassigned_text and "학생13(" in unassigned_text)
s3 = login("2026303")
print("   마감 뒤 지원 단추 숨김:", not any(k.startswith("apply_") for k in keys(s3)))
admin.button(key="admin_close").click().run()
expect("다시 마감 누름", result(admin), "막힘")

print("모두 통과" if failures == 0 else f"{failures}개 다름")
