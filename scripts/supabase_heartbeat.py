#!/usr/bin/env python3
"""
Supabase Keep-Alive Heartbeat Script
=====================================
Prevents Supabase free-tier project from pausing due to inactivity.

This script:
1. Connects to Supabase using service role credentials
2. Inserts a heartbeat record with current timestamp
3. Deletes records older than 7 days to keep the table small
4. Logs success/failure clearly

Environment Variables Required:
- SUPABASE_URL: Your Supabase project URL
- SUPABASE_SERVICE_ROLE_KEY: Service role key (not anon key)

Usage:
    python scripts/supabase_heartbeat.py
"""

import os
import sys
from datetime import datetime, timedelta
from supabase import create_client, Client


def get_supabase_client() -> Client:
    """Create and return Supabase client using service role key."""
    url = os.getenv("SUPABASE_URL", "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    
    if not url:
        raise RuntimeError("❌ SUPABASE_URL environment variable is not set")
    if not service_key:
        raise RuntimeError("❌ SUPABASE_SERVICE_ROLE_KEY environment variable is not set")
    
    # Clean URL (remove trailing slashes or /rest/v1)
    url = url.rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[:-len("/rest/v1")]
    
    print(f"✓ Connecting to Supabase: {url}")
    return create_client(url, service_key)


def insert_heartbeat(client: Client) -> dict:
    """Insert a new heartbeat record."""
    timestamp = datetime.utcnow().isoformat()
    
    print(f"→ Inserting heartbeat at {timestamp}")
    
    response = client.table("heartbeat").insert({
        "timestamp": timestamp,
        "source": "github_actions"
    }).execute()
    
    if response.data:
        print(f"✓ Heartbeat inserted successfully (ID: {response.data[0].get('id', 'N/A')})")
        return response.data[0]
    else:
        raise RuntimeError(f"Failed to insert heartbeat: {response}")


def cleanup_old_records(client: Client, days: int = 7) -> int:
    """Delete heartbeat records older than specified days."""
    cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    print(f"→ Deleting records older than {days} days (before {cutoff_date})")
    
    response = client.table("heartbeat").delete().lt("timestamp", cutoff_date).execute()
    
    deleted_count = len(response.data) if response.data else 0
    
    if deleted_count > 0:
        print(f"✓ Deleted {deleted_count} old record(s)")
    else:
        print("✓ No old records to delete")
    
    return deleted_count


def get_heartbeat_count(client: Client) -> int:
    """Get total number of heartbeat records."""
    response = client.table("heartbeat").select("id", count="exact").execute()
    return response.count if response.count is not None else 0


def main():
    """Main heartbeat execution."""
    print("=" * 60)
    print("Supabase Keep-Alive Heartbeat")
    print("=" * 60)
    
    try:
        # Connect to Supabase
        client = get_supabase_client()
        
        # Insert new heartbeat
        heartbeat = insert_heartbeat(client)
        
        # Cleanup old records
        deleted = cleanup_old_records(client, days=7)
        
        # Get final count
        total = get_heartbeat_count(client)
        print(f"\n✓ Total heartbeat records: {total}")
        
        print("\n" + "=" * 60)
        print("✅ Heartbeat completed successfully!")
        print("=" * 60)
        
        return 0
        
    except Exception as exc:
        print("\n" + "=" * 60)
        print(f"❌ Heartbeat failed: {exc}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
