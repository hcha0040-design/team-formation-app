"""AI 모델 후보를 한 번씩 실제로 불러 성공, 시간, 실패 이유를 본다(무료 호출 횟수를 씀).

실행: py scripts/probe_models.py [모델 이름 ...]   (생략하면 tf/ai.py 의 MODELS 3개)
중간 연습 시나리오의 마감 뒤 상태(팀이 없는 학생 8명)를 보낸다. DB 는 쓰지 않는다.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tf import ai  # noqa: E402
from tf.models import Student  # noqa: E402

PL, WP, FD, TT, RW, PT = "기획자", "웹 프로그래머", "프론트엔드 디자이너", "테스터", "보고서 작성자", "발표자"


def S(no, main, *subs):
    return Student(f"20262{no:02d}", f"학생{no}", main, tuple(subs))


teams = {1: [S(1, PL, PT, TT), S(5, WP, TT)], 2: [S(6, WP, FD), S(9, FD, WP)], 3: [], 4: []}
unassigned = [S(2, PL, TT), S(3, PL, RW), S(4, PL), S(7, WP), S(8, WP, PT), S(10, TT, PL), S(11, RW), S(12, PT, RW, FD)]

models = sys.argv[1:] or ai.MODELS
messages = ai.build_messages(teams, unassigned)
for number, model in enumerate(models, start=1):
    job = ai.AssignJob(teams, unassigned, fallback=[])
    ok = ai._attempt(job, number, model, messages)
    a = job.attempts[-1]
    print(f"{'성공' if ok else '실패'} | {model} | {a.outcome} | {a.elapsed}초 | {a.detail}", flush=True)
