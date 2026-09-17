"""텔레그램 알림 — odin 패턴 차용(미설정 no-op·예외 삼킴). 멀티유저 제거, chat_id 단일값.

★ 미설정/실패는 조용히 넘긴다 — 알림이 안 된다고 스캔·감지 흐름이 멈추면 안 된다.
"""

import httpx
from loguru import logger

from src.config.settings import settings


def is_enabled() -> bool:
    """토큰·chat_id 둘 다 있어야 알림 활성."""
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


async def send_telegram(text: str) -> bool:
    """메시지 발송. 미설정이면 no-op, 예외는 로그만(흐름 차단 금지)."""
    if not is_enabled():
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
        # ★ 성공도 남긴다(2026-09-17) — 그전엔 성공 흔적이 어디에도 없어 "알림이 갔는지"를
        #   2주치 로그로도 확인할 수 없었다. 감지·알림 도구의 알림이 검증 불가면 성공 기준
        #   ("안 봐도 안 놓친다")을 아무도 확인 못 한다.
        if resp.status_code == 200:
            logger.info(f"[텔레그램] 발송 성공 ({len(text)}자)")
            return True
        logger.warning(f"[텔레그램] 발송 거절 HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.warning(f"[텔레그램] 발송 실패: {e}")
        return False


def send_telegram_sync(text: str) -> bool:
    """동기 발송 — 일간보고 오케스트레이션이 threadpool(동기)에서 부르기 위한 버전.

    텔레그램 4096자 제한 → 넉넉히 3800자 단위로 잘라 여러 번 보낸다. 미설정/실패는 no-op.
    """
    if not is_enabled():
        return False
    chunks = _split(text, 3800)
    ok = True
    try:
        with httpx.Client(timeout=10.0) as client:
            for chunk in chunks:
                resp = client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={
                        "chat_id": settings.telegram_chat_id,
                        "text": chunk,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
                if resp.status_code != 200:
                    ok = False
                    logger.warning(f"[텔레그램] 발송 거절 HTTP {resp.status_code}: {resp.text[:200]}")
        if ok:
            logger.info(f"[텔레그램] 발송 성공 ({len(chunks)}건, {len(text)}자)")
        return ok
    except Exception as e:
        logger.warning(f"[텔레그램] 발송 실패: {e}")
        return False


def _split(text: str, limit: int) -> list[str]:
    """줄 경계 우선으로 limit 이하 청크로 자른다(한 줄이 limit보다 길면 강제 분할)."""
    out: list[str] = []
    buf = ""
    for line in text.split("\n"):
        while len(line) > limit:  # 초장문 한 줄은 강제로 쪼갬
            out.append(line[:limit])
            line = line[limit:]
        if len(buf) + len(line) + 1 > limit:
            if buf:
                out.append(buf)
            buf = line
        else:
            buf = f"{buf}\n{line}" if buf else line
    if buf:
        out.append(buf)
    return out
