"""과제 앱에 필요한 비밀 값이 .env 에 있는지 확인한다.

값은 출력하지 않고 "있음/없음"만 보여 준다.
실행: py check_env.py
"""

import os

from config import load_env

REQUIRED = ["OPENROUTER_API_KEY", "DATABASE_URL", "ADMIN_PASSWORD"]


def main() -> None:
    load_env()
    for name in REQUIRED:
        status = "있음" if os.environ.get(name, "").strip() else "없음"
        print(f"{name}: {status}")


if __name__ == "__main__":
    main()
