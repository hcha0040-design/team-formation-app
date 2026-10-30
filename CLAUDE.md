# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 개요

데이터과학 중간 대체 과제: 학생들이 팀 프로젝트 팀을 스스로 편성하는 Streamlit 웹 앱(Supabase DB, 오픈라우터 AI 배정). 마감 11/2(월) 23:59, 마감 뒤 커밋 금지(-5). 모든 기능은 "어려운 해결"로 만든다.

- 요구사항: [docs/PRD.md](docs/PRD.md), 작업 순서와 설계: [docs/구현 계획.md](docs/구현%20계획.md)
- 과제 공고 원문: `_ref/중간과제 공고.pdf`, 텍스트 사본 `_ref/중간과제 공고.txt` (gitignore 대상, 규칙이 헷갈리면 여기를 먼저 확인)
- 연습용 가상 명단: `data/쉬움.csv`, `data/중간.csv`, `data/어려움.csv`. 기대 결과는 공고 부록(텍스트 사본 끝부분)에 있다
- 코드 주석, 화면 문구, 문서는 한국어로 쓴다

예전 4장 실습 파일(`check_key.py`, `test_api.py`)은 오픈라우터 키 확인용으로 남겨 둔다. `test_api.py`의 10→20→40초 재시도 방식은 과제의 "모델마다 전체 120초" 규칙과 맞지 않으므로 앱에 옮기지 않는다.

## 실행

Windows의 `py` 런처로 실행한다.

```bash
py check_env.py                         # .env 의 비밀 값 3개가 있는지 "있음/없음"만 출력
py check_key.py                         # 오픈라우터 키 유효성 확인 (크레딧 소모 없음)
py -m streamlit run streamlit_app.py    # 앱 실행 (구현 후)
py -m pytest tests                      # 규칙 함수 단위 시험 (구현 후)
```

## 반드시 지킬 것 (감점 규칙)

- **Streamlit key**는 PRD 9절 표와 글자 하나까지 같아야 한다(자동 채점이 key로 요소를 찾음, 틀리면 -5). 한글 key 금지
- `result` 안내는 "승인", "대기", "거절", "막힘" 가운데 하나로 시작한다
- 테이블 이름은 모두 `tf_`로 시작하고, 실제 스키마는 `schema.sql`과 항상 같게 유지한다
- 비밀번호는 bcrypt 해시로만 저장한다
- 연습 시나리오의 학생 이름이나 순서를 보고 결과를 정하는 코드 금지(그 시나리오 0점)
- 실제 사람의 이름이나 학번을 코드, 문서, 명단에 쓰지 않는다. 가상 명단만 쓴다
- 오픈라우터 `openrouter/free` 라우터 금지. 1차, 2차, 3차 모델을 직접 정해 차례로 넘어간다
- 무료 모델 호출은 하루 50회 한도. 시험할 때 AI 배정을 아껴 쓴다

## 키 취급 규칙

- 비밀 값은 `OPENROUTER_API_KEY`, `DATABASE_URL`, `ADMIN_PASSWORD` 3개다. 로컬은 `.env`, 배포는 Streamlit Secrets에 같은 이름으로 둔다(`.env.example` 참고)
- 값을 화면, 터미널, 로그, 코드, 커밋에 절대 쓰지 않는다. 있는지 확인할 때는 "있음/없음"만 출력한다(`check_env.py`). 꼭 일부를 보여야 하면 `config.mask()`를 쓴다
- `.env`를 직접 열어 읽지 않는다
- 커밋 전에 `git status`로 `.env`가 빠졌는지 확인한다
