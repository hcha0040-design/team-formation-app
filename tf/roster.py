"""명단 CSV(student_no,name,main_role,sub_roles)를 읽어 Student 목록으로 바꾼다."""

import csv
import io
import re

from tf.models import ROLES, Student

HEADER = ["student_no", "name", "main_role", "sub_roles"]


class RosterError(ValueError):
    """명단이 틀렸을 때. 메시지는 관리자 화면에 그대로 보여 준다."""


def _clean(text: str) -> str:
    """앞뒤 공백을 지우고, 가운데 연속 공백은 하나로 줄인다. 예: ' 웹  프로그래머 ' → '웹 프로그래머'"""
    return re.sub(r"\s+", " ", text).strip()


def _role(text: str, line_no: int) -> str:
    role = _clean(text)
    if role not in ROLES:
        raise RosterError(f"{line_no}번째 줄: 알 수 없는 역할 '{role}'")
    return role


def parse_roster(raw: bytes) -> list[Student]:
    # 엑셀용 BOM 이 붙은 UTF-8 도 읽도록 utf-8-sig 로 읽는다.
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise RosterError("UTF-8 로 읽을 수 없는 파일임")

    rows = [row for row in csv.reader(io.StringIO(text)) if any(cell.strip() for cell in row)]
    if not rows or [_clean(c) for c in rows[0]] != HEADER:
        raise RosterError("첫 줄 머리글이 student_no,name,main_role,sub_roles 가 아님")

    students: list[Student] = []
    seen: set[str] = set()
    for line_no, row in enumerate(rows[1:], start=2):
        if len(row) == 3:  # 보조 역할이 없을 때 마지막 쉼표를 빠뜨린 줄도 받아 준다
            row = row + [""]
        if len(row) != 4:
            raise RosterError(f"{line_no}번째 줄: 열이 {len(row)}개임(4개여야 함)")

        student_no, name = _clean(row[0]), _clean(row[1])
        if not student_no or not name:
            raise RosterError(f"{line_no}번째 줄: 학번이나 이름이 비어 있음")
        if student_no.lower() == "admin":
            raise RosterError(f"{line_no}번째 줄: 학번 admin 은 관리자 전용임")
        if student_no in seen:
            raise RosterError(f"{line_no}번째 줄: 학번 {student_no} 중복")
        seen.add(student_no)

        main_role = _role(row[2], line_no)
        subs: list[str] = []
        for part in row[3].split(";"):
            if _clean(part):
                role = _role(part, line_no)
                if role not in subs:
                    subs.append(role)
        if len(subs) > 2:
            raise RosterError(f"{line_no}번째 줄: 보조 역할이 {len(subs)}개임(0~2개여야 함)")

        students.append(Student(student_no, name, main_role, tuple(subs)))

    if not students:
        raise RosterError("명단에 학생이 없음")
    return students
