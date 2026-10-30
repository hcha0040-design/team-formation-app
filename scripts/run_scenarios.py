"""연습용 시나리오(공고 부록 1~3)를 화면 없이 DB 함수로 돌려, 결과 안내의 첫 단어가 기대와 같은지 본다.

주의: 실행하면 DB의 명단을 시나리오 명단으로 바꾼다(명단 올리기와 같음).
실행: py scripts/run_scenarios.py [쉬움|중간|어려움] [--until 단계]   (이름을 생략하면 셋 다)
      --until 6 이면 6단계까지만 하고 멈춘다(화면에서 이어서 시험할 때).

이 파일은 개발용 점검 도구다. 앱 코드는 학생 이름이나 순서를 보지 않는다.
"""

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)

from tf import db  # noqa: E402
from tf.roster import parse_roster  # noqa: E402

# (동작, 인자, 기대 첫 단어)
#   ("apply", (학번, 팀)), ("vote", (투표자 학번, 지원자 학번, "찬성"/"거부")), ("close", ())
#   ("unassigned", (학번, …)) 는 마감 뒤 팀이 없는 학생 목록에 그 학번들이 들어 있는지 본다.
SCENARIOS = {
    "쉬움": (3, [
        (1, "apply", ("2026101", 1), "승인"), (1, "apply", ("2026102", 2), "승인"), (1, "apply", ("2026103", 3), "승인"),
        (2, "apply", ("2026104", 1), "대기"), (2, "vote", ("2026101", "2026104", "찬성"), "승인"),
        (3, "apply", ("2026105", 2), "대기"), (3, "vote", ("2026102", "2026105", "찬성"), "승인"),
        (4, "apply", ("2026107", 1), "대기"), (4, "vote", ("2026101", "2026107", "찬성"), "대기"),
        (4, "vote", ("2026104", "2026107", "거부"), "거절"),
        (5, "apply", ("2026106", 3), "대기"), (5, "vote", ("2026103", "2026106", "찬성"), "승인"),
        (6, "close", (), "승인"),
    ]),
    "중간": (4, [
        (1, "apply", ("2026201", 1), "승인"),
        (2, "apply", ("2026205", 1), "대기"), (2, "vote", ("2026201", "2026205", "찬성"), "승인"),
        (3, "apply", ("2026202", 1), "막힘"),
        (4, "apply", ("2026206", 2), "승인"),
        (5, "apply", ("2026209", 2), "대기"), (5, "vote", ("2026206", "2026209", "찬성"), "승인"),
        (6, "apply", ("2026210", 2), "대기"), (6, "vote", ("2026206", "2026210", "찬성"), "대기"),
        (6, "vote", ("2026209", "2026210", "거부"), "거절"),
        (7, "apply", ("2026203", 3), "승인"), (7, "apply", ("2026211", 4), "승인"),
        (8, "apply", ("2026212", 4), "대기"), (8, "apply", ("2026212", 3), "막힘"),
        (9, "close", (), "승인"), (9, "unassigned", ("2026203", "2026211", "2026212"), "승인"),
        (10, "apply", ("2026202", 3), "막힘"),
    ]),
    "어려움": (4, [
        (1, "apply", ("2026301", 1), "승인"),
        (2, "apply", ("2026304", 1), "대기"), (2, "vote", ("2026301", "2026304", "찬성"), "승인"),
        (3, "apply", ("2026307", 1), "대기"), (3, "vote", ("2026301", "2026307", "찬성"), "대기"),
        (3, "vote", ("2026304", "2026307", "찬성"), "승인"),
        (4, "apply", ("2026302", 2), "승인"),
        (5, "apply", ("2026308", 2), "대기"), (5, "vote", ("2026302", "2026308", "찬성"), "승인"),
        (6, "apply", ("2026305", 2), "대기"), (6, "apply", ("2026306", 2), "대기"),
        (7, "vote", ("2026302", "2026305", "찬성"), "대기"), (7, "vote", ("2026308", "2026305", "찬성"), "승인"),
        (8, "vote", ("2026302", "2026306", "찬성"), "대기"), (8, "vote", ("2026308", "2026306", "찬성"), "대기"),
        (8, "vote", ("2026305", "2026306", "찬성"), "거절"),
        (9, "apply", ("2026311", 3), "승인"),
        (10, "apply", ("2026315", 3), "대기"), (10, "vote", ("2026311", "2026315", "찬성"), "승인"),
        (11, "apply", ("2026314", 3), "막힘"),
        (12, "apply", ("2026310", 4), "승인"),
        (13, "apply", ("2026313", 1), "대기"), (13, "vote", ("2026301", "2026313", "찬성"), "대기"),
        (14, "close", (), "승인"), (14, "unassigned", ("2026310", "2026313"), "승인"),
    ]),
}


def run_scenario(name: str, until: int | None = None) -> int:
    team_count, steps = SCENARIOS[name]
    if until is not None:
        steps = [s for s in steps if s[0] <= until]
    db.reset_roster(parse_roster((ROOT / "data" / f"{name}.csv").read_bytes()), team_count)
    state = db.load_state()
    ids = {s.student_no: sid for sid, s in state.students.items()}

    failures = 0
    print(f"\n=== {name} (팀 {team_count}개) ===")
    for step, action, args, expected in steps:
        if action == "apply":
            result = db.apply(ids[args[0]], args[1])
            what = f"{args[0]} → 팀{args[1]} 지원"
        elif action == "vote":
            result = db.vote(ids[args[0]], args[1], args[2])
            what = f"{args[0]} 가 {args[1]} 에 {args[2]}"
        elif action == "close":
            result = db.close_recruiting()
            what = "모집 마감"
        else:  # unassigned
            left = {state.students[sid].student_no for sid in db.load_state().unassigned()}
            missing = [no for no in args if no not in left]
            result = "승인: 모두 팀이 없는 학생에 있음" if not missing else f"거절: 빠짐 {missing}"
            what = f"팀이 없는 학생에 {', '.join(args)}"
        ok = result.split(":")[0] == expected
        failures += not ok
        print(f"{'OK ' if ok else 'XX '} {step:>2}단계 {what:<36} 기대 {expected} | {result}")

    final = db.load_state()
    print("팀 구성:", {t: [final.students[s].student_no[-2:] for s in m] for t, m in final.teams.items()})
    print("팀이 없는 학생:", [final.students[s].student_no[-2:] for s in final.unassigned()])
    print(f"{name}: {'모두 통과' if failures == 0 else f'{failures}개 다름'}")
    return failures


if __name__ == "__main__":
    args = sys.argv[1:]
    until = None
    if "--until" in args:
        i = args.index("--until")
        until = int(args[i + 1])
        del args[i:i + 2]
    names = args or list(SCENARIOS)
    total = sum(run_scenario(n, until) for n in names)
    sys.exit(1 if total else 0)
