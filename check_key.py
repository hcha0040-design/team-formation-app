"""OpenRouter 키가 올바르게 로드되고 유효한지 확인한다.

크레딧을 쓰지 않는 GET /api/v1/key 엔드포인트만 호출한다.
실행: py check_key.py
"""

import json
import urllib.error
import urllib.request

from config import get_openrouter_key, mask


def main() -> None:
    key = get_openrouter_key()
    print(f"키 로드 성공: {mask(key)}")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp).get("data", {})
    except urllib.error.HTTPError as e:
        print(f"키 확인 실패: HTTP {e.code} (401 이면 키가 잘못되었거나 폐기된 것입니다)")
        return

    print("키 유효함")
    print(f"  사용량(USD): {data.get('usage')}")
    print(f"  한도(USD): {data.get('limit')}  (None 이면 한도 없음)")
    print(f"  무료 등급: {data.get('is_free_tier')}")


if __name__ == "__main__":
    main()
