"""Telegram progress notifier for long-running experiment suites.

Reads ``COEVSEC_TELEGRAM_BOT_TOKEN`` and ``COEVSEC_TELEGRAM_CHAT_ID`` from the
environment (or a ``.env`` file). If the chat id is empty, polls
``getUpdates`` until the user sends ``/start`` to the bot, then persists the
id back into ``.env``.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _load_dotenv(path: Path | None = None) -> None:
    env_path = path or Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def _api(token: str, method: str, **params) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        _load_dotenv()
        self.token = token or os.environ.get("COEVSEC_TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("COEVSEC_TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token)
        self._offset = 0

    def discover_chat_id(self, wait_s: float = 600.0, poll_s: float = 3.0) -> str | None:
        """Block until someone messages the bot, then return and persist chat_id."""
        if not self.enabled:
            return None
        if self.chat_id:
            return self.chat_id
        deadline = time.time() + wait_s
        if wait_s > 0:
            print(
                "[telegram] Send /start to @L40unimebot so progress can be notified.",
                flush=True,
            )
        # Drop pending updates once so we do not fight another getUpdates consumer.
        try:
            body = _api(self.token, "getUpdates", offset=-1, timeout=0)
            for upd in body.get("result", []):
                self._offset = max(self._offset, int(upd["update_id"]) + 1)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception):
            pass
        while time.time() < deadline:
            try:
                body = _api(
                    self.token, "getUpdates",
                    offset=self._offset, timeout=20,
                )
            except urllib.error.HTTPError as exc:
                if exc.code == 409:
                    # Another poller is active; back off and retry.
                    time.sleep(5)
                    continue
                print(f"[telegram] getUpdates HTTP {exc.code}", flush=True)
                time.sleep(poll_s)
                continue
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"[telegram] getUpdates failed: {exc}", flush=True)
                time.sleep(poll_s)
                continue
            for upd in body.get("result", []):
                self._offset = max(self._offset, int(upd["update_id"]) + 1)
                msg = upd.get("message") or upd.get("edited_message") or {}
                chat = msg.get("chat") or {}
                cid = chat.get("id")
                if cid is not None:
                    self.chat_id = str(cid)
                    self._persist_chat_id(self.chat_id)
                    os.environ["COEVSEC_TELEGRAM_CHAT_ID"] = self.chat_id
                    print(f"[telegram] chat_id={self.chat_id}", flush=True)
                    return self.chat_id
            if wait_s <= 0:
                break
            time.sleep(poll_s)
        if wait_s > 0:
            print("[telegram] timed out waiting for /start; continuing without Telegram", flush=True)
        return None

    def _persist_chat_id(self, chat_id: str) -> None:
        env_path = Path(__file__).resolve().parents[1] / ".env"
        if not env_path.exists():
            return
        lines = env_path.read_text().splitlines()
        out, found = [], False
        for line in lines:
            if line.startswith("COEVSEC_TELEGRAM_CHAT_ID="):
                out.append(f"COEVSEC_TELEGRAM_CHAT_ID={chat_id}")
                found = True
            else:
                out.append(line)
        if not found:
            out.append(f"COEVSEC_TELEGRAM_CHAT_ID={chat_id}")
        env_path.write_text("\n".join(out) + "\n")

    def send(self, text: str, *, disable_preview: bool = True) -> bool:
        if not self.enabled or not self.chat_id:
            print(f"[telegram:dry] {text[:200]}", flush=True)
            return False
        # Telegram hard limit is 4096 chars.
        chunks = [text[i : i + 3500] for i in range(0, len(text), 3500)] or [text]
        ok = True
        for chunk in chunks:
            try:
                _api(
                    self.token,
                    "sendMessage",
                    chat_id=self.chat_id,
                    text=chunk,
                    disable_web_page_preview=str(disable_preview).lower(),
                )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"[telegram] send failed: {exc}", flush=True)
                ok = False
        return ok


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("message", nargs="?", default="coevsec telegram ping")
    p.add_argument("--wait-chat", type=float, default=0.0, help="seconds to wait for /start")
    args = p.parse_args(argv)
    n = TelegramNotifier()
    if args.wait_chat > 0 and not n.chat_id:
        n.discover_chat_id(wait_s=args.wait_chat)
    n.send(args.message)
    return 0 if n.chat_id else 1


if __name__ == "__main__":
    raise SystemExit(main())
