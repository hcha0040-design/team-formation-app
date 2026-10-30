"""OpenRouter API 로 텍스트 인식과 이미지 인식을 각각 테스트한다.

실행:
    py test_api.py          # 둘 다
    py test_api.py text     # 텍스트만
    py test_api.py image    # 이미지만
"""

import base64
import json
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib

from config import get_openrouter_key

API_URL = "https://openrouter.ai/api/v1/chat/completions"
TEXT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
IMAGE_MODEL = "minimax/minimax-m3.1-flash:free"


RETRY_STATUS = {429, 502, 503, 504}  # 무료 모델에서 흔한 일시적 오류
RETRY_WAITS = [10, 20, 40]  # 초


def chat(model: str, messages: list, max_tokens: int = 1024) -> dict:
    body = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {get_openrouter_key()}",
            "Content-Type": "application/json",
            "X-Title": "Study_04 API test",
        },
    )
    for wait in RETRY_WAITS + [None]:
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.load(resp)
            code = result.get("error", {}).get("code")
        except urllib.error.HTTPError as e:
            if wait is None:
                raise
            code = e.code
            if code not in RETRY_STATUS:
                raise
        else:
            # HTTP 200 이어도 본문에 error 가 담겨 오는 경우가 있다
            if code not in RETRY_STATUS or wait is None:
                return result
        print(f"  오류 {code} (일시적 오류) → {wait}초 후 재시도")
        time.sleep(wait)


def make_test_png(width: int = 240, height: int = 120) -> bytes:
    """흰 배경 왼쪽에 빨간 원, 오른쪽에 파란 정사각형이 있는 PNG 를 만든다."""
    rows = []
    for y in range(height):
        row = bytearray([0])  # 필터 없음
        for x in range(width):
            if (x - 60) ** 2 + (y - 60) ** 2 <= 40 ** 2:
                row += bytes((220, 30, 30))
            elif 140 <= x < 220 and 20 <= y < 100:
                row += bytes((30, 60, 220))
            else:
                row += bytes((255, 255, 255))
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


def report(title: str, model: str, run) -> None:
    print(f"\n=== {title} ({model}) ===")
    start = time.perf_counter()
    try:
        result = run()
    except urllib.error.HTTPError as e:
        print(f"실패: HTTP {e.code}\n{e.read().decode(errors='replace')[:500]}")
        return
    except urllib.error.URLError as e:
        print(f"실패: 네트워크 오류 {e.reason}")
        return
    elapsed = time.perf_counter() - start

    if "error" in result:
        print(f"실패: {result['error']}")
        return
    choice = result["choices"][0]
    usage = result.get("usage", {})
    print(f"응답 시간: {elapsed:.1f}초 | 실제 처리 제공자: {result.get('provider')}")
    print(f"토큰: 입력 {usage.get('prompt_tokens')} / 출력 {usage.get('completion_tokens')}"
          f" | 종료 사유: {choice.get('finish_reason')}")
    print("--- 응답 ---")
    print((choice["message"].get("content") or "(내용 없음)").strip())


def test_text() -> None:
    messages = [{
        "role": "user",
        "content": "다음 문장의 감정을 긍정/부정/중립 중 하나로 분류하고, 핵심 단어 3개를 뽑아 줘.\n"
                   "문장: \"오늘 처음으로 API 연동에 성공해서 정말 뿌듯했다.\"",
    }]
    report("텍스트 인식 테스트", TEXT_MODEL, lambda: chat(TEXT_MODEL, messages))


def test_image() -> None:
    png = make_test_png()
    with open("test_image.png", "wb") as f:
        f.write(png)
    data_url = "data:image/png;base64," + base64.b64encode(png).decode()
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": "이 이미지에 무엇이 있는지 한국어로 설명해 줘. 도형의 모양, 색, 위치를 구체적으로."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    }]
    report("이미지 인식 테스트", IMAGE_MODEL, lambda: chat(IMAGE_MODEL, messages))
    print("(정답: 흰 배경, 왼쪽에 빨간 원, 오른쪽에 파란 정사각형 / 이미지는 test_image.png 로 저장됨)")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target in ("all", "text"):
        test_text()
    if target in ("all", "image"):
        test_image()
