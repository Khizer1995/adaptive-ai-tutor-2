"""
core/supabase_client.py
=======================
Singleton Supabase client.
Import this everywhere you need Supabase access instead of calling
create_client() multiple times.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None


def get_supabase() -> Client:
    """Return the shared Supabase client, initialising it on first call."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set in .env"
            )
        # Remove trailing /rest/v1/ if someone accidentally left it in.
        url = url.rstrip("/")
        if url.endswith("/rest/v1"):
            url = url[: -len("/rest/v1")]
        _client = create_client(url, key)
    return _client
