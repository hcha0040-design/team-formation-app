from pathlib import Path

import pytest

from tf.roster import RosterError, parse_roster

DATA = Path(__file__).resolve().parent.parent / "data"


def test_practice_rosters_load_with_bom():
    for name, count in [("쉬움", 8), ("중간", 12), ("어려움", 16)]:
        raw = (DATA / f"{name}.csv").read_bytes()
        students = parse_roster(raw)
        assert len(students) == count


def test_bom_and_spaces_are_cleaned():
    raw = (
        "﻿student_no,name,main_role,sub_roles\n"
        "2026001, 가나다 , 기획자 , 보고서  작성자\n"
        "2026002, 라마바 , 웹  프로그래머 ,\n"
        "2026003, 사아자 , 테스터 , 기획자 ; 발표자\n"
    ).encode("utf-8")
    s1, s2, s3 = parse_roster(raw)
    assert (s1.student_no, s1.name, s1.main_role, s1.sub_roles) == ("2026001", "가나다", "기획자", ("보고서 작성자",))
    assert (s2.main_role, s2.sub_roles) == ("웹 프로그래머", ())
    assert s3.sub_roles == ("기획자", "발표자")


def test_unknown_role_is_rejected():
    raw = "student_no,name,main_role,sub_roles\n1,가,요리사,\n".encode("utf-8")
    with pytest.raises(RosterError, match="요리사"):
        parse_roster(raw)


def test_duplicate_student_no_is_rejected():
    raw = "student_no,name,main_role,sub_roles\n1,가,기획자,\n1,나,테스터,\n".encode("utf-8")
    with pytest.raises(RosterError, match="중복"):
        parse_roster(raw)


def test_admin_student_no_is_rejected():
    raw = "student_no,name,main_role,sub_roles\nadmin,가,기획자,\n".encode("utf-8")
    with pytest.raises(RosterError):
        parse_roster(raw)


def test_more_than_two_sub_roles_is_rejected():
    raw = "student_no,name,main_role,sub_roles\n1,가,기획자,테스터;발표자;보고서 작성자\n".encode("utf-8")
    with pytest.raises(RosterError, match="보조 역할"):
        parse_roster(raw)


def test_missing_header_is_rejected():
    raw = "1,가,기획자,\n".encode("utf-8")
    with pytest.raises(RosterError, match="머리글"):
        parse_roster(raw)


def test_empty_roster_is_rejected():
    raw = "student_no,name,main_role,sub_roles\n".encode("utf-8")
    with pytest.raises(RosterError):
        parse_roster(raw)
