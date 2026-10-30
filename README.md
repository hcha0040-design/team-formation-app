# 팀 프로젝트 팀 편성 웹 앱

학생들이 팀 프로젝트 팀을 스스로 편성하는 Streamlit 웹 앱이다. 학생은 팀에 지원하고, 팀원은 투표로 받아들인다. 모집을 마감한 뒤 팀이 없는 학생은 AI(오픈라우터)가 배정안을 내고, 앱이 그 배정안을 규칙으로 검사한 뒤 관리자가 확정한다. DB는 Supabase(PostgreSQL)를 쓴다.

## 1. 배포 주소

https://team-formation-app-bwqebxmhscuxwuqj8t47pu.streamlit.app

## 2. PRD와 구현 계획의 위치

- PRD: [docs/PRD.md](docs/PRD.md)
- 구현 계획: [docs/구현 계획.md](docs/구현%20계획.md)
- AI 모델 시험 기록: [docs/AI 모델 시험 기록.md](docs/AI%20모델%20시험%20기록.md)
- 화면 점검 기록: [docs/화면 점검 기록.md](docs/화면%20점검%20기록.md)
- DB 스키마: [schema.sql](schema.sql)

## 3. 고른 해결 방법

모든 기능을 어려운 해결로 만들었다.

| 기능 | 고른 해결 | 만든 방법 |
|---|---|---|
| 다른 사람의 변경 보기 | 어려운 해결 | `st.fragment(run_every="3s")`로 학생 화면(팀 목록, 지원, 투표)과 관리자 화면(팀 현황, 팀이 없는 학생)의 바뀐 부분만 3초마다 다시 그림 ([tf/ui_student.py](tf/ui_student.py), [tf/ui_admin.py](tf/ui_admin.py)) |
| 필수 포함 역할을 지킬 수 없는 팀 | 어려운 해결 | 지원할 때 "들어간 뒤 남는 자리 수 < 아직 못 채운 필수 포함 역할 수"이면 막음. 기획자와 웹 프로그래머는 서로 다른 학생으로 짝지어 셈 (`check_join`, [tf/rules.py](tf/rules.py)) |
| 같은 팀에 대기 중인 지원이 여럿 | 어려운 해결 | 모든 팀원이 찬성한 순간 팀 행을 잠그고(`SELECT … FOR UPDATE`) 정원, 주 역할 중복, 필수 역할 자리를 다시 검사함. 처리 순서는 투표가 끝난 순서 (`_vote`, [tf/db.py](tf/db.py)) |
| 마지막 자리에 두 명이 동시에 들어감 | 어려운 해결 | `tf_members`의 `(team_id, slot_no)` 기본 키, `student_id` 유일성 제약, `slot_no between 1 and 4` 검사로 먼저 도착한 학생만 기록 ([schema.sql](schema.sql)) |
| AI 응답이 늦을 때 | 어려운 해결 | 모델 호출을 작업 스레드에서 하고, 부른 때부터 응답을 다 받을 때까지 전체 120초를 재서 넘으면 끊고 다음 모델로 넘어감 (`_attempt`, [tf/ai.py](tf/ai.py)) |
| 3차 모델까지 실패 | 어려운 해결 | 백트래킹으로 모든 경우를 따져 검사 다섯 가지를 모두 통과하는 배정을 끝까지 찾음. AI를 부르기 전에 먼저 찾아 두고, 없으면 AI를 부르지 않고 이유를 보여 줌 (`search_assignment`, `explain_infeasible`, [tf/rules.py](tf/rules.py)) |
| AI 대기 중 화면 | 어려운 해결 | `assign_status`에 "1차 모델(`…`) 응답을 기다리는 중… 23초 / 120초"처럼 몇 차 모델인지와 경과 시간을 1초마다 보여 줌. 끝난 시도는 결과와 이유를 목록으로 남김 |
| DB(Supabase)가 일시정지되지 않게 | 어려운 해결 | GitHub Actions 예약 실행으로 매일 09:00(한국 시각)에 DB에 질의함 ([.github/workflows/keepalive.yml](.github/workflows/keepalive.yml)). 첫 실행: 2026-10-30 15:29 "DB 질의 성공" (화면 `img/keepalive.png`) |

## 4. 쓴 모델 3개

- 1차 `nvidia/nemotron-3-ultra-550b-a55b:free`
- 2차 `nvidia/nemotron-3.5-super-vl:free`
- 3차 `google/gemma-4-31b-it:free`

10/30에 무료 모델 후보 7개를 실제로 한 번씩 불러 보고 정했다([AI 모델 시험 기록](docs/AI%20모델%20시험%20기록.md)). 오픈라우터의 자동 라우터(`openrouter/free`)는 쓰지 않는다.

## 5. 오픈라우터 AI 모델 호출 실패 사례

0. **배포한 앱에서 1차 시간 초과 → 2차 빈 응답 → 3차 성공**: 10/30 17:11(한국 시각), 배포한 앱에서 부록 3(어려움) 15단계의 AI 배정을 했다.
   - 1차 `nvidia/nemotron-3-ultra-550b-a55b:free`는 **120.1초** 동안 응답을 다 받지 못해 앱이 끊었다.
   - 2차 `nvidia/nemotron-3.5-super-vl:free`는 42.7초 만에 **빈 응답**을 냈다.
   - 3차 `google/gemma-4-31b-it:free`가 97.5초 만에 낸 배정안(8명)이 검사 5가지를 통과했다.
   - 확정한 팀 4개는 모두 4명이고 규칙을 지켰다. 기록은 DB `tf_ai_logs`에 남아 있다. (화면 `img/ai-fail.png`)
1. **HTTP 429로 거절됨**: 10/30 오후 `google/gemma-4-31b-it:free`를 부르자 2.0초 만에 "HTTP 429 Provider returned error"가 왔다(사용량이 많아 제공자가 거절). 앱은 이를 실패로 보고 다음 모델로 넘어간다. 이 모델은 3차로 두었다.
2. **검사에서 걸러 낸 배정안**: `poolside/laguna-s-2.1:free`가 4.7초 만에 배정안을 냈지만 "팀2에 필수 포함 역할을 채우지 못함, 팀3에 주 역할 기획자가 2명"이라 앱이 불합격 처리했다. 그래서 이 모델은 쓰지 않았다.
3. **빈 응답**: `dots-studio/dots-3-note-preview:free`가 57.6초 동안 생각한 뒤 내용 없이 답했다. 앱은 빈 응답도 실패로 처리한다.
4. **쓸 수 없는 모델**: `thinkingmachines/inkling:free`는 HTTP 403("지정된 에이전트 앱에서만 쓸 수 있음")으로 거절했다.

- 화면: `img/ai-fail.png` (0번 사례. AI 배정 화면의 `assign_status`에 1차, 2차 시도가 ❌로 남은 모습)
- 기록: [docs/AI 모델 시험 기록.md](docs/AI%20모델%20시험%20기록.md)(1~4번), DB `tf_ai_logs` 테이블(0번)

## 6. 클로드가 잘못된 추론이나 답변을 한 사례

1. **Streamlit Secrets에 `.env`를 그대로 붙여 넣으라고 잘못 안내함**
   - 클로드는 "`.env`의 세 줄을 Secrets에 그대로 붙여 넣으면 형식이 같다"고 안내했다. 하지만 `.env`의 첫 줄 `OPENROUTER_API_KEY` 값에는 큰따옴표가 없었다. Secrets는 TOML 형식이라 값마다 큰따옴표가 있어야 하고, 한 줄이라도 틀리면 전체를 읽지 못한다.
   - 배포한 첫 화면에서 "DATABASE_URL 가 없습니다" 오류가 났다(화면 `img/secrets-error.png`). `.env`의 각 줄이 TOML로 읽히는지 값을 보지 않고 검사해서 원인을 찾았다.
   - `.env`에 따옴표를 넣고 Secrets를 다시 저장해 해결했다. 같은 일이 생기면 원인이 보이도록 오류 안내도 고쳤다(커밋 `428f876`).
2. **써 보지 않은 모델을 후보로 넣음**
   - 클로드는 구현 계획에서 `thinkingmachines/inkling:free`를 모델 후보로 적었다. 모델 목록에 무료(`:free`)로 나온다는 것만 보고, 실제로 부를 수 있는지는 확인하지 않았다.
   - 실제로 불러 보니 HTTP 403(일반 앱에서는 못 씀)이었다. `scripts/probe_models.py`로 후보 7개를 모두 불러 본 뒤 모델을 바꿨다(커밋 `e43b49b`의 `MODELS`, [AI 모델 시험 기록](docs/AI%20모델%20시험%20기록.md)).

## 7. 제출한 앱에서 발견한 문제점과 개선 필요 사항

1. **빠르게 입력하면 학번이 빠진 채 로그인되어 "막힘"이 남**
   - 배포한 앱에서 부록 3(어려움)을 자동 조작으로 해 볼 때, 13단계에서 학생13이 로그인하지 못했다. 화면에는 "막힘: 학번 또는 비밀번호가 틀림"이 떴고, 비밀번호 칸은 채워져 있는데 학번 칸이 비어 있었다. 같은 단계를 다시 하면 통과했고, 로그인만 3번 따로 해 보니 1번이 같은 식으로 실패했다.
   - 원인: 학번과 비밀번호 칸이 입력할 때마다 따로 서버에 보내지고 화면을 다시 그린다. 그래서 로그아웃 직후 빠르게 입력하면 다시 그리기와 겹쳐 학번 값이 사라졌다.
   - 고침: 두 칸을 `st.form`으로 묶어 로그인 단추(`login_submit`)를 누를 때 한 번에 보내게 했다(커밋 `8760247`). 고친 뒤 배포한 앱에서 로그인을 6번 연달아 해 보니 모두 성공했다.
   - 기록: [docs/화면 점검 기록.md](docs/화면%20점검%20기록.md). 1~12단계의 `result`가 기대와 같았고 13단계에서 로그인이 실패한 자동 조작 기록, 실패한 때 화면의 글자(`막힘: 학번 또는 비밀번호가 틀림`), 학번 칸의 값(빈 값), 비밀번호 칸의 글자 수(4)를 시각과 함께 그대로 남겼다.
   - 그때는 화면 캡처를 찍지 않았다. 나중에 캡처를 남기려고 고치기 전 코드를 로컬에서 34번 실행해 보았지만 재현되지 않았다(배포한 앱의 통신 지연이 있을 때만 생기는 것으로 보임). 그래서 캡처 대신 위 기록을 근거로 둔다.
2. **코드를 올린 직후 앱이 `KeyError: 'tf'`로 멈춤**
   - 깃허브에 커밋을 올리자 Streamlit Cloud가 앱을 자동으로 갱신하는 도중 `KeyError: 'tf'`가 났다(화면 `img/keyerror.png`). Manage app에서 Reboot 하니 정상으로 돌아왔다.
   - 3초마다 다시 그리는 프래그먼트와, 코드 묶음(`tf`)을 다시 불러오는 시점이 겹친 것으로 보인다. 마감 뒤에는 커밋하지 않으므로 채점에는 영향이 없지만, 코드를 올린 뒤에는 앱을 직접 확인해야 한다.

## 실행 방법(로컬)

```bash
py -m pip install -r requirements.txt
py check_env.py                          # .env 의 비밀 값 3개가 있는지 "있음/없음"만 출력
py -m streamlit run streamlit_app.py
py -m pytest tests                       # 규칙, 명단, AI 실패 처리 단위 시험
py scripts/run_scenarios.py              # 연습 시나리오 3개를 DB 함수로 점검(DB 명단이 바뀜)
```

`.env`(로컬)와 Streamlit Secrets(배포)에는 `OPENROUTER_API_KEY`, `DATABASE_URL`, `ADMIN_PASSWORD`를 둔다([.env.example](.env.example)). 값은 모두 큰따옴표로 감싼다.
