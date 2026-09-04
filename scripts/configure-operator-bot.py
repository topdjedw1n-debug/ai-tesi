#!/usr/bin/env python3
"""Run interactively ON the server. Write credentials without printing them.

Does not deploy/restart anything or mutate production data. Re-running keeps
the shared gateway key. Existing mappings must be supplied in full.
"""

import getpass
import json
import os
import re
import secrets
import subprocess
from pathlib import Path


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )


def write_env(path: Path, values: dict[str, str]) -> None:
    for value in values.values():
        if "\n" in value or "\r" in value or "$" in value:
            raise ValueError("Unsupported environment value")
    temporary = path.with_suffix(".tmp")
    temporary.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
    temporary.chmod(0o600)
    temporary.replace(path)


def main() -> None:
    os.umask(0o077)
    directory = Path("/etc/thesica/operator-bot")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    previous = read_env(directory / "bot.env")
    token = getpass.getpass(
        "Токен від BotFather (ввід прихований; Enter — залишити наявний): "
    ).strip() or previous.get("TELEGRAM_BOT_TOKEN", "")
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
        raise ValueError("Некоректний токен")
    mapping = json.loads(
        input(
            'Прив’язки Telegram ID → Thesica ID, наприклад {"123456789":1}; для початкового запуску {}: '
        )
    )
    if not isinstance(mapping, dict) or any(
        not str(k).isdecimal() or int(k) <= 0 or type(v) is not int or v <= 0
        for k, v in mapping.items()
    ):
        raise ValueError("Некоректні прив’язки")
    unlimited = json.loads(
        input("Thesica ID з дозволом без квот (manager1 = 1): [1] або []: ")
    )
    if not isinstance(unlimited, list) or any(
        type(v) is not int or v <= 0 for v in unlimited
    ):
        raise ValueError("Некоректні ID")
    model = (
        input("Модель помічника (Enter — claude-sonnet-5): ").strip()
        or "claude-sonnet-5"
    )
    # Read only the needed existing provider credential into memory, never
    # print a full container environment or a secret in a command argument.
    key = previous.get("ANTHROPIC_API_KEY")
    if not key:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "ai-thesis-api",
                "python",
                "-c",
                "import os; print(os.environ.get('ANTHROPIC_API_KEY', ''), end='')",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        key = result.stdout.strip()
    if not key:
        key = getpass.getpass(
            "Ключ Anthropic для помічника (ввід прихований): "
        ).strip()
    if not key:
        raise ValueError("Ключ провайдера відсутній")
    shared = previous.get("OPERATOR_BOT_SECRET") or secrets.token_hex(32)
    write_env(
        directory / "bot.env",
        {
            "TELEGRAM_BOT_TOKEN": token,
            "OPERATOR_BOT_SECRET": shared,
            "ANTHROPIC_API_KEY": key,
            "OPERATOR_BOT_MODEL": model,
        },
    )
    write_env(
        directory / "api.env",
        {
            "OPERATOR_BOT_SECRET": shared,
            "OPERATOR_BOT_USERS": json.dumps(mapping, separators=(",", ":")),
            "UNLIMITED_GENERATION_USER_IDS": json.dumps(unlimited),
        },
    )
    print(
        "Налаштування збережено з правами 600. Секрети не виводилися. Сервер не перезапущено."
    )


if __name__ == "__main__":
    main()
