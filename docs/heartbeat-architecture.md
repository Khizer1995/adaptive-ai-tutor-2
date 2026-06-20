# Supabase Heartbeat Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      GITHUB ACTIONS                              │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Workflow: supabase-heartbeat.yml                          │ │
│  │                                                             │ │
│  │  Triggers:                                                  │ │
│  │  • Schedule: Every 2 days at 3:00 AM UTC                  │ │
│  │  • Manual: workflow_dispatch (Run workflow button)        │ │
│  └────────────────────────┬───────────────────────────────────┘ │
│                           │                                      │
│                           ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Job: heartbeat                                             │ │
│  │  Runner: ubuntu-latest                                      │ │
│  │                                                             │ │
│  │  Steps:                                                     │ │
│  │  1. Checkout repository                                     │ │
│  │  2. Setup Python 3.11                                       │ │
│  │  3. Install dependencies (supabase, python-dotenv)         │ │
│  │  4. Run scripts/supabase_heartbeat.py                      │ │
│  │     with environment variables from secrets                │ │
│  │  5. Report status                                           │ │
│  └────────────────────────┬───────────────────────────────────┘ │
│                           │                                      │
└───────────────────────────┼──────────────────────────────────────┘
                            │
                            │ Environment Variables:
                            │ SUPABASE_URL (from secrets)
                            │ SUPABASE_SERVICE_ROLE_KEY (from secrets)
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              PYTHON SCRIPT (supabase_heartbeat.py)               │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  1. get_supabase_client()                                 │  │
│  │     • Read SUPABASE_URL from env                          │  │
│  │     • Read SUPABASE_SERVICE_ROLE_KEY from env             │  │
│  │     • Validate both are present                           │  │
│  │     • Create Supabase client                              │  │
│  └───────────────────────┬───────────────────────────────────┘  │
│                           │                                       │
│                           ▼                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  2. insert_heartbeat()                                    │  │
│  │     • Get current UTC timestamp                           │  │
│  │     • Insert row: {timestamp, source: "github_actions"}  │  │
│  │     • Log success with inserted ID                        │  │
│  └───────────────────────┬───────────────────────────────────┘  │
│                           │                                       │
│                           ▼                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  3. cleanup_old_records()                                 │  │
│  │     • Calculate cutoff date (7 days ago)                  │  │
│  │     • Delete rows where timestamp < cutoff                │  │
│  │     • Log number of deleted records                       │  │
│  └───────────────────────┬───────────────────────────────────┘  │
│                           │                                       │
│                           ▼                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  4. get_heartbeat_count()                                 │  │
│  │     • Query total records in table                        │  │
│  │     • Log final count                                     │  │
│  └───────────────────────┬───────────────────────────────────┘  │
│                           │                                       │
│                           ▼                                       │
│                  Exit Code: 0 (success) or 1 (failure)           │
│                                                                   │
└───────────────────────────┼──────────────────────────────────────┘
                            │
                            │ HTTPS (TLS encrypted)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SUPABASE PROJECT                              │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Table: heartbeat                                          │ │
│  │                                                             │ │
│  │  Columns:                                                   │ │
│  │  • id (BIGSERIAL, PRIMARY KEY)                            │ │
│  │  • timestamp (TIMESTAMPTZ)                                │ │
│  │  • source (TEXT)                                          │ │
│  │                                                             │ │
│  │  Data:                                                      │ │
│  │  ┌────┬─────────────────────────┬─────────────────┐       │ │
│  │  │ id │ timestamp                │ source          │       │ │
│  │  ├────┼─────────────────────────┼─────────────────┤       │ │
│  │  │ 1  │ 2026-06-20 12:00:00+00  │ github_actions │       │ │
│  │  │ 2  │ 2026-06-18 12:00:00+00  │ github_actions │       │ │
│  │  │ 3  │ 2026-06-16 12:00:00+00  │ github_actions │       │ │
│  │  └────┴─────────────────────────┴─────────────────┘       │ │
│  │                                                             │ │
│  │  (Only last 7 days kept via auto-cleanup)                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Inactivity Monitor                                        │ │
│  │  • Checks for database activity                           │ │
│  │  • If no activity for 7 days → pause project              │ │
│  │  • Heartbeat writes count as activity ✓                   │ │
│  │  • Project stays active!                                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Scheduled Trigger

```
GitHub Actions Scheduler
    ↓
    Checks cron schedule: '0 3 */2 * *'
    ↓
    Every 2 days at 3:00 AM UTC
    ↓
    Trigger workflow run
```

### 2. Workflow Execution

```
Start Workflow
    ↓
Setup Environment (Python 3.11, pip cache)
    ↓
Install Dependencies (supabase, python-dotenv)
    ↓
Load Secrets as Environment Variables
    ├─ SUPABASE_URL
    └─ SUPABASE_SERVICE_ROLE_KEY
    ↓
Execute: python scripts/supabase_heartbeat.py
    ↓
Capture Exit Code (0 = success, 1 = failure)
    ↓
Report Final Status
```

### 3. Script Operations

```
Read Environment Variables
    ↓
Validate Credentials Present
    ↓
Create Supabase Client (with service_role key)
    ↓
Insert Heartbeat
    ├─ Current UTC timestamp
    ├─ Source: "github_actions"
    └─ Returns inserted row ID
    ↓
Cleanup Old Records
    ├─ Calculate cutoff (NOW - 7 days)
    ├─ DELETE WHERE timestamp < cutoff
    └─ Returns deleted count
    ↓
Get Total Count (for monitoring)
    ↓
Log Results
    ↓
Exit with Status Code
```

### 4. Supabase Processing

```
Receive HTTPS Request
    ↓
Authenticate Service Role Key
    ↓
Execute SQL Operations
    ├─ INSERT INTO heartbeat
    └─ DELETE FROM heartbeat WHERE ...
    ↓
Return Response
    ↓
Update Inactivity Timer
    ↓
Project Remains Active ✓
```

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  GitHub Repository Secrets (Encrypted at Rest)                   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  SUPABASE_URL                                            │   │
│  │  Value: https://xxxxx.supabase.co                       │   │
│  │  Encrypted: Yes                                          │   │
│  │  Access: GitHub Actions runners only                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  SUPABASE_SERVICE_ROLE_KEY                               │   │
│  │  Value: eyJhbGc... (JWT token)                          │   │
│  │  Encrypted: Yes                                          │   │
│  │  Access: GitHub Actions runners only                     │   │
│  │  Masked in Logs: Yes                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ Decrypted only at runtime
                          ▼
              ┌────────────────────────────┐
              │  GitHub Actions Runner     │
              │  (Ephemeral VM)            │
              │                            │
              │  Environment Variables:    │
              │  • SUPABASE_URL           │
              │  • SUPABASE_SERVICE_...   │
              │                            │
              │  Scope: Single job only    │
              │  Lifetime: Minutes         │
              │  Logged: Masked (****)     │
              └──────────┬─────────────────┘
                         │
                         │ HTTPS/TLS
                         ▼
              ┌────────────────────────────┐
              │  Supabase API              │
              │  (TLS 1.3 encrypted)       │
              │                            │
              │  Authentication:           │
              │  • Bearer token            │
              │  • Service role verified   │
              │  • Rate limited            │
              └────────────────────────────┘
```

## Timing Diagram

```
Time: 0 days         2 days        4 days        6 days        8 days
      │               │             │             │             │
      ▼               ▼             ▼             ▼             ▼
      
Heartbeat #1    Heartbeat #2  Heartbeat #3  Heartbeat #4  Heartbeat #5
    (Insert)        (Insert)      (Insert)      (Insert)      (Insert)
      │               │             │             │             │
      └───────────────┴─────────────┴─────────────┴─────────────┘
                                                                 │
                                    Supabase Inactivity Window   │
                                    ◄────── 7 days ──────►       │
                                                                 │
                                    Never reaches 7 days! ✓      │
                                    Project stays active         │

Cleanup:
  Each heartbeat deletes records older than 7 days
  
  After Heartbeat #4 (day 6):
  ┌─────────────────────────────────────────────────────┐
  │ Table contains:                                     │
  │ • Heartbeat #4 (0 days old) ✓                      │
  │ • Heartbeat #3 (2 days old) ✓                      │
  │ • Heartbeat #2 (4 days old) ✓                      │
  │ • Heartbeat #1 (6 days old) ✓                      │
  │ • Older records (7+ days) ✗ DELETED                │
  └─────────────────────────────────────────────────────┘
```

## Error Handling Flow

```
Script Execution
    │
    ├─ Missing SUPABASE_URL?
    │   └─> RuntimeError → Exit 1 → GitHub Actions marks as failed
    │
    ├─ Missing SUPABASE_SERVICE_ROLE_KEY?
    │   └─> RuntimeError → Exit 1 → GitHub Actions marks as failed
    │
    ├─ Network error?
    │   └─> Exception → Exit 1 → GitHub Actions marks as failed
    │
    ├─ Table doesn't exist?
    │   └─> Exception → Exit 1 → GitHub Actions marks as failed
    │
    ├─ Permission denied?
    │   └─> Exception → Exit 1 → GitHub Actions marks as failed
    │
    └─ All operations succeed?
        └─> Exit 0 → GitHub Actions marks as passed ✓

Failed Run:
    ├─> Email notification to repo owner
    ├─> Red X in Actions tab
    └─> Logs available for debugging
```

## Resource Usage

```
Per Workflow Run:
┌──────────────────────────────────────────┐
│ GitHub Actions                           │
│ • Duration: ~30 seconds                  │
│ • Compute: Free tier minutes             │
│ • Storage: ~10 KB logs per run           │
│ • Cost: $0                               │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ Supabase                                 │
│ • API Requests: 2 (1 INSERT, 1 DELETE)  │
│ • Database Storage: ~100 bytes/record    │
│ • Total Storage: ~700 bytes (7 records)  │
│ • Bandwidth: <1 KB                       │
│ • Cost: $0 (within free tier)            │
└──────────────────────────────────────────┘

Monthly Total:
• GitHub Actions: ~15 runs/month
• Supabase Operations: ~30 writes, ~30 deletes
• Total Cost: $0
• Free Tier Impact: <0.1%
```

## Monitoring Points

```
┌─────────────────────────────────────────────────────────────┐
│  Monitoring Layer                                            │
│                                                              │
│  1. GitHub Actions                                           │
│     • Workflow run status (pass/fail)                       │
│     • Execution logs                                         │
│     • Email notifications on failure                         │
│     • Badge status (optional)                                │
│                                                              │
│  2. Script Output                                            │
│     • Connection success/failure                             │
│     • Insert success with row ID                             │
│     • Cleanup results (rows deleted)                         │
│     • Total record count                                     │
│                                                              │
│  3. Supabase Dashboard                                       │
│     • Table Editor (view records)                            │
│     • API logs (if enabled)                                  │
│     • Project activity status                                │
│                                                              │
│  4. SQL Queries                                              │
│     • Recent heartbeats                                      │
│     • Oldest heartbeat age                                   │
│     • Total record count                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## File Organization

```
AI_Tutor_Repository/
│
├── .github/
│   └── workflows/
│       └── supabase-heartbeat.yml          ← GitHub Actions workflow
│
├── scripts/
│   ├── supabase_heartbeat.py               ← Heartbeat script
│   ├── build_layered_kb.py                 ← Existing scripts
│   └── ...
│
├── docs/
│   ├── supabase-heartbeat-setup.md         ← Full documentation
│   ├── heartbeat-architecture.md           ← This file
│   └── ...
│
├── HEARTBEAT_SETUP_QUICKSTART.md           ← Quick start guide
├── SETUP_COMPLETE.md                       ← Setup checklist
│
└── .gitignore                              ← Ensures .env is never committed
```

## Integration Points

The heartbeat system is **completely isolated** from your main application:

```
Main Application         Heartbeat System
      │                        │
      │                        │
      ├─ core/                 ├─ scripts/supabase_heartbeat.py
      ├─ tests/                ├─ .github/workflows/
      ├─ data/                 └─ docs/supabase-heartbeat-setup.md
      ├─ api_server.py
      └─ run_langgraph.py
      
      No shared code           Independent execution
      No dependencies          Self-contained
      
      Can run without ────┐    ┌──── Can run without
      heartbeat system    │    │     main application
                          │    │
                          ▼    ▼
                      Both are independent!
```

## Removal Process

```
To Remove Heartbeat System:

1. Delete Workflow
   rm .github/workflows/supabase-heartbeat.yml

2. Delete Script  
   rm scripts/supabase_heartbeat.py

3. Delete Docs
   rm docs/supabase-heartbeat-setup.md
   rm docs/heartbeat-architecture.md
   rm HEARTBEAT_SETUP_QUICKSTART.md
   rm SETUP_COMPLETE.md

4. (Optional) Remove GitHub Secrets
   Settings → Secrets → Delete SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

5. (Optional) Drop Table
   Supabase SQL Editor: DROP TABLE heartbeat;

Result: No trace left, zero impact on main application
```
