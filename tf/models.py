"""앱 전체에서 쓰는 역할 이름과 학생 정보."""

from dataclasses import dataclass

ROLES = ("기획자", "웹 프로그래머", "프론트엔드 디자이너", "테스터", "보고서 작성자", "발표자")

# 확정한 팀마다 서로 다른 학생이 1명씩 맡아야 하는 역할
REQUIRED_ROLES = ("기획자", "웹 프로그래머")


@dataclass(frozen=True)
class Student:
    student_no: str
    name: str
    main_role: str
    sub_roles: tuple[str, ...] = ()
    id: int | None = None  # DB의 tf_students.id (명단을 읽을 때는 없음)

    def can_cover(self, role: str) -> bool:
        """주 역할이나 보조 역할로 그 역할을 맡을 수 있는지."""
        return role == self.main_role or role in self.sub_roles
