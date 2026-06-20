# Supabase Keep-Alive Heartbeat Setup

## Overview

This heartbeat system prevents your Supabase free-tier project from pausing due to inactivity (7-day threshold). It automatically writes to the `heartbeat` table every 2 days via GitHub Actions.

## Files Created

```
.github/workflows/supabase-heartbeat.yml    # GitHub Actions workflow
scripts/supabase_heartbeat.py               # Python heartbeat script
docs/supabase-heartbeat-setup.md            # This documentation
```

## Setup Instructions

### 1. Verify Heartbeat Table Exists

Ensure your Supabase project has a `heartbeat` table. If not, create it:

```sql
CREATE TABLE heartbeat (
  id BIGSERIAL PRIMARY KEY,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source TEXT DEFAULT 'github_actions'
);

-- Optional: Add an index for faster cleanup queries
CREATE INDEX idx_heartbeat_timestamp ON heartbeat(timestamp);

-- Optional: Enable Row Level Security (RLS) if needed
ALTER TABLE heartbeat ENABLE ROW LEVEL SECURITY;

-- Optional: Allow service role to bypass RLS
CREATE POLICY "Service role can manage heartbeat" ON heartbeat
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
```

### 2. Get Your Supabase Service Role Key

1. Go to your Supabase project dashboard
2. Navigate to **Settings** → **API**
3. Copy these values:
   - **Project URL** (e.g., `https://xxxxx.supabase.co`)
   - **service_role key** (NOT the `anon` key - service role has admin access)

⚠️ **Important**: The service role key is a secret credential. Never commit it to your repository!

### 3. Add GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these two secrets:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `SUPABASE_URL` | Your Supabase project URL | `https://abcdefg.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Your service role key | `eyJhbGc...` (long JWT token) |

### 4. Test the Workflow Manually

Before relying on the scheduled runs, test it manually:

1. Go to **Actions** tab in your GitHub repository
2. Click **Supabase Keep-Alive Heartbeat** workflow
3. Click **Run workflow** dropdown (top right)
4. Click the green **Run workflow** button
5. Wait ~30 seconds and check the logs

**Expected output:**
```
============================================================
Supabase Keep-Alive Heartbeat
============================================================
✓ Connecting to Supabase: https://xxxxx.supabase.co
→ Inserting heartbeat at 2026-06-20T12:34:56.789000
✓ Heartbeat inserted successfully (ID: 123)
→ Deleting records older than 7 days (before 2026-06-13T12:34:56.789000)
✓ Deleted 5 old record(s)

✓ Total heartbeat records: 42
============================================================
✅ Heartbeat completed successfully!
============================================================
```

### 5. Verify in Supabase

1. Go to your Supabase dashboard
2. Navigate to **Table Editor** → **heartbeat**
3. You should see a new row with:
   - Recent `timestamp`
   - `source` = "github_actions"

## How It Works

### Schedule
- **Frequency**: Every 2 days at 3:00 AM UTC
- **Cron**: `0 3 */2 * *`
- **Why 2 days?**: Supabase pauses after 7 days of inactivity. Running every 2 days ensures 3+ heartbeats within the 7-day window (plenty of safety margin).

### Workflow Steps
1. Checks out your repository
2. Sets up Python 3.11
3. Installs `supabase` and `python-dotenv` packages
4. Runs `scripts/supabase_heartbeat.py` with secrets as environment variables
5. Reports success/failure

### Script Operations
1. Connects to Supabase using service role key
2. Inserts a new heartbeat record with current UTC timestamp
3. Deletes records older than 7 days (keeps table small)
4. Logs total record count
5. Exits with code 0 (success) or 1 (failure)

## Monitoring

### Check Workflow Status

**Via GitHub UI:**
1. Go to **Actions** tab
2. Check recent runs of **Supabase Keep-Alive Heartbeat**
3. Green checkmark = success, red X = failed

**Via Email:**
- GitHub sends email notifications for workflow failures (if enabled in your notification settings)

### Check Heartbeat Table

Run this query in Supabase SQL Editor:

```sql
-- Show recent heartbeats
SELECT * FROM heartbeat
ORDER BY timestamp DESC
LIMIT 10;

-- Count total heartbeats
SELECT COUNT(*) FROM heartbeat;

-- Check oldest heartbeat (should be < 7 days old)
SELECT MIN(timestamp) as oldest_heartbeat FROM heartbeat;
```

## Troubleshooting

### Workflow Fails with "SUPABASE_URL is not set"
- Go to **Settings** → **Secrets and variables** → **Actions**
- Verify `SUPABASE_URL` secret exists and is spelled correctly (case-sensitive)

### Workflow Fails with "SUPABASE_SERVICE_ROLE_KEY is not set"
- Go to **Settings** → **Secrets and variables** → **Actions**
- Verify `SUPABASE_SERVICE_ROLE_KEY` secret exists and is spelled correctly
- Make sure you used the **service_role** key, not the `anon` key

### Workflow Fails with "relation 'heartbeat' does not exist"
- Your `heartbeat` table hasn't been created yet
- Run the SQL from step 1 in Supabase SQL Editor

### Workflow Fails with "permission denied"
- Check if RLS is enabled on the `heartbeat` table
- Add a policy to allow service role access (see step 1 SQL)
- Or disable RLS: `ALTER TABLE heartbeat DISABLE ROW LEVEL SECURITY;`

### Project Still Paused Despite Heartbeats
- Verify heartbeats are actually being inserted (check table in Supabase)
- Check that workflow is running successfully (green checkmark in Actions tab)
- Supabase might pause for other reasons (billing issues, quota exceeded)

## Local Testing

Test the heartbeat script locally before committing:

```bash
# Set environment variables (temporary, not committed)
export SUPABASE_URL="https://xxxxx.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="eyJhbGc..."

# Run the script
python scripts/supabase_heartbeat.py
```

Expected output should show successful connection, insertion, and cleanup.

## Modifying the Schedule

Edit `.github/workflows/supabase-heartbeat.yml`:

```yaml
schedule:
  - cron: '0 3 */2 * *'  # Current: Every 2 days at 3 AM UTC
```

**Common alternatives:**
```yaml
- cron: '0 0 * * *'     # Daily at midnight UTC
- cron: '0 12 */3 * *'  # Every 3 days at noon UTC
- cron: '0 6 * * 1'     # Weekly on Mondays at 6 AM UTC
```

Use [crontab.guru](https://crontab.guru/) to visualize cron schedules.

## Removing the Heartbeat System

If you upgrade off the free tier and no longer need this:

1. **Delete the workflow:**
   ```bash
   rm .github/workflows/supabase-heartbeat.yml
   ```

2. **Delete the script:**
   ```bash
   rm scripts/supabase_heartbeat.py
   ```

3. **Delete the documentation:**
   ```bash
   rm docs/supabase-heartbeat-setup.md
   ```

4. **Remove GitHub secrets** (optional):
   - Go to **Settings** → **Secrets and variables** → **Actions**
   - Delete `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`

5. **Drop the table** (optional):
   ```sql
   DROP TABLE IF EXISTS heartbeat;
   ```

All components are self-contained and can be removed cleanly.

## Security Notes

✅ **Good practices:**
- Service role key stored in GitHub secrets (encrypted)
- Never committed to repository
- Only accessible to GitHub Actions runners
- Transmitted over HTTPS
- Logged output never shows secrets

❌ **Don't:**
- Never hardcode credentials in scripts
- Never commit `.env` files with real credentials
- Never share service role key publicly (treat like a password)

## Cost Considerations

**Free tier limits:**
- This heartbeat uses minimal resources (1 insert + 1 delete every 2 days)
- Total monthly operations: ~30 writes, ~30 deletes
- Negligible impact on Supabase quotas
- No API request limits exceeded

**If you exceed limits:**
- Supabase will throttle, not charge
- Workflow will fail with rate limit error
- Adjust schedule to less frequent (e.g., every 3-4 days)

## Resources

- [Supabase Pricing](https://supabase.com/pricing)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Supabase Python Client](https://github.com/supabase-community/supabase-py)
