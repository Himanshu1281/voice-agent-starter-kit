from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is not configured")

if not SUPABASE_SECRET_KEY:
    raise RuntimeError("SUPABASE_SECRET_KEY is not configured")


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


def create_call(
    livekit_room: str,
    phone: Optional[str] = None,
    language: str = "en",
) -> str:
    """Create a call record and return its Supabase UUID."""

    data = {
        "livekit_room": livekit_room,
        "phone": phone,
        "language": language,
    }

    response = (
        supabase
        .table("calls")
        .insert(data)
        .execute()
    )

    return response.data[0]["id"]


def save_message(
    call_id: str,
    speaker: str,
    message: str,
) -> None:
    """Save one customer or Maya message."""

    if not message or not message.strip():
        return

    (
        supabase
        .table("messages")
        .insert(
            {
                "call_id": call_id,
                "speaker": speaker,
                "message": message.strip(),
            }
        )
        .execute()
    )


def finish_call(call_id: str) -> None:
    """Mark a call as finished."""

    (
        supabase
        .table("calls")
        .update(
            {
                "ended_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", call_id)
        .execute()
    )


if __name__ == "__main__":
    print("Testing Supabase connection...")

    (
        supabase
        .table("calls")
        .select("id")
        .limit(1)
        .execute()
    )

    print("Supabase connection OK")
    print("calls table is accessible")
