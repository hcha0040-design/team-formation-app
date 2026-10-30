"""API 키를 .env 파일에서 안전하게 불러오는 모듈 (외부 패키지 불필요).

사용법:
    from config import get_openrouter_key
    api_key = get_openrouter_key()

규칙:
- 키를 코드에 직접 적지 않는다.
- 키를 print 하거나 로그에 남기지 않는다. 확인이 필요하면 mask() 를 쓴다.
"""

import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env(path: Path = ENV_PATH) -> None:
    """.env 의 KEY=VALUE 줄을 환경변수로 등록한다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def mask(secret: str) -> str:
    """앞 9자와 끝 4자만 보여 준다. 예: sk-or-v1-…a1b2"""
    if len(secret) <= 13:
        return "*" * len(secret)
    return f"{secret[:9]}…{secret[-4:]}"


def _from_streamlit_secrets(name: str) -> str:
    """배포한 앱에서는 Streamlit Secrets 에서 읽는다. Streamlit 밖이거나 secrets 가 없으면 빈 문자열."""
    try:
        import streamlit as st

        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def get_secret(name: str) -> str:
    """비밀 값을 Streamlit Secrets → 환경변수(.env) 순서로 찾는다. 값은 출력하지 않는다."""
    value = _from_streamlit_secrets(name)
    if value:
        return value
    load_env()
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} 가 없습니다. 로컬은 .env, 배포한 앱은 Streamlit Secrets 에 넣어 주세요. "
            "Secrets 는 TOML 형식이라 값을 모두 큰따옴표로 감싸야 하며, 한 줄이라도 틀리면 전체를 읽지 못합니다."
        )
    return value


def get_openrouter_key() -> str:
    return get_secret("OPENROUTER_API_KEY")
