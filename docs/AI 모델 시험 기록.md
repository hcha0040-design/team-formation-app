# AI 모델 시험 기록

README 5항(오픈라우터 AI 모델 호출 실패 사례)의 근거로 쓴다. 시험 도구는 `scripts/probe_models.py`이고, 중간 연습 시나리오의 마감 뒤 상태(팀이 없는 학생 8명, 팀 4개)를 보냈다. 앱에서 한 호출은 DB의 `tf_ai_logs` 테이블에도 남는다.

## 2026-10-30 (금) 오후

| 모델 | 결과 | 걸린 시간 | 내용 |
|---|---|---|---|
| `google/gemma-4-31b-it:free` | 오류 | 2.0초 | HTTP 429 Provider returned error (사용량이 많아 제공자가 거절) |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | **성공** | 47.2초 | 8명 배정, 검사 5가지 통과 |
| `thinkingmachines/inkling:free` | 오류 | 0.1초 | HTTP 403. 이 모델은 코딩 에이전트 같은 지정된 앱에서만 쓸 수 있음 → 후보에서 뺌 |
| `nvidia/nemotron-3.5-super-vl:free` | 검사 불합격 | 52.6초 | 이미 팀에 있는 학생(2026201 등)까지 배정안에 적어 냄 |
| `dots-studio/dots-3-note-preview:free` | 빈 응답 | 57.6초 | 내용 없이 답함(추론 모델이 토큰을 생각하는 데 다 쓴 것으로 보임) |
| `google/gemma-4-26b-a4b-it:free` | 오류 | 0.4초 | HTTP 429 Provider returned error |
| `poolside/laguna-s-2.1:free` | 검사 불합격 | 4.7초 | 팀2에 필수 포함 역할을 채우지 못함, 팀3에 주 역할 기획자가 2명 → 앱이 걸러 냄 |

## 이 결과로 바꾼 것

- 1차 `nvidia/nemotron-3-ultra-550b-a55b:free`, 2차 `nvidia/nemotron-3.5-super-vl:free`, 3차 `google/gemma-4-31b-it:free`로 정했다.
- nemotron-3.5-super-vl처럼 기존 팀원을 **지금 팀 그대로** 함께 적은 항목은 옮긴 것이 아니므로 빼고 검사하게 고쳤다. 기존 팀원을 다른 팀으로 옮긴 배정안은 여전히 불합격이다.
- 요청에 "assignments 에는 팀이 없는 학생만 넣는다"를 더했다.
