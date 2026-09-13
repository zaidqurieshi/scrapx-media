"""Helper script for non-interactive Telegram authentication."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from telethon import TelegramClient, errors

from config.settings import get_settings


def get_state_file() -> Path:
    return Path("data") / ".auth_state.json"


async def request_code(phone: str) -> None:
    settings = get_settings()
    session_path = Path("data") / settings.telegram_session_name
    session_path.parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(session_path), settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()

    if await client.is_user_authorized():
        print("ALREADY_AUTHORIZED")
        await client.disconnect()
        return

    result = await client.send_code_request(phone)
    state = {
        "phone": phone,
        "phone_code_hash": result.phone_code_hash,
    }

    state_file = get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f)

    print("CODE_SENT")
    await client.disconnect()


async def verify_code(code: str) -> None:
    settings = get_settings()
    session_path = Path("data") / settings.telegram_session_name

    state_file = get_state_file()
    if not state_file.exists():
        print("ERROR: No pending authentication request found.")
        sys.exit(1)

    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)

    phone = state["phone"]
    phone_code_hash = state["phone_code_hash"]

    client = TelegramClient(str(session_path), settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        print("SUCCESS_AUTHORIZED")
        if state_file.exists():
            state_file.unlink()
    except errors.SessionPasswordNeededError:
        print("PASSWORD_NEEDED")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        await client.disconnect()


async def verify_password(password: str) -> None:
    settings = get_settings()
    session_path = Path("data") / settings.telegram_session_name

    client = TelegramClient(str(session_path), settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()

    try:
        await client.sign_in(password=password)
        print("SUCCESS_AUTHORIZED")
        state_file = get_state_file()
        if state_file.exists():
            state_file.unlink()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")

    req_parser = subparsers.add_parser("request")
    req_parser.add_argument("phone", type=str)

    ver_parser = subparsers.add_parser("verify")
    ver_parser.add_argument("code", type=str)

    pwd_parser = subparsers.add_parser("password")
    pwd_parser.add_argument("password", type=str)

    args = parser.parse_args()

    if args.action == "request":
        asyncio.run(request_code(args.phone))
    elif args.action == "verify":
        asyncio.run(verify_code(args.code))
    elif args.action == "password":
        asyncio.run(verify_password(args.password))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
