# SchoolTracs → iCal Sync

Auto-syncs your assigned classes from SchoolTracs to a `.ics` file you can subscribe to from Apple Calendar / Google Calendar / anything else.

Runs twice a day (8 AM and 8 PM HK time) via GitHub Actions, hosted free on GitHub Pages.

## How it works

1. GitHub Actions logs into SchoolTracs on a schedule
2. Hits the GraphQL `weeklyActivityList` endpoint to pull your classes
3. Filters down to ones assigned to you, generates `.ics`
4. Commits the file to `docs/` which GitHub Pages serves
5. Apple Calendar (or any other) subscribes to the public URL and refreshes automatically

## Setup

### 1. Push this to a new GitHub repo

```bash
cd st-calendar-sync
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/st-calendar-sync.git
git push -u origin main
```

### 2. Add secrets

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

Add these:

| Name | Value |
|------|-------|
| `ST_EMAIL` | Your SchoolTracs login email (`pika.baran06@gmail.com`) |
| `ST_PASSWORD` | Your SchoolTracs password |
| `ST_STAFF_ID` | `77` |
| `ST_CENTER_ID` | `2` |
| `ST_ORG` | `encodeworld` |

### 3. Enable GitHub Pages

**Settings → Pages → Source: Deploy from a branch → Branch: `main` → Folder: `/docs` → Save**

After ~30 seconds your calendar will be live at:

```
https://YOUR_USERNAME.github.io/st-calendar-sync/schooltracs.ics
```

### 4. Run the workflow once manually

**Actions tab → "Sync SchoolTracs Calendar" → Run workflow**

This generates the first `.ics` file. After that it runs automatically twice a day.

### 5. Subscribe in Apple Calendar

**On Mac:**
- Calendar → File → New Calendar Subscription
- Paste your URL: `https://YOUR_USERNAME.github.io/st-calendar-sync/schooltracs.ics`
- Set auto-refresh to "Every hour" or "Every day"

**On iPhone:**
- Calendar app → Calendars → Add Calendar → Add Subscription Calendar
- Paste the same URL

Done! Your SchoolTracs schedule will now show up in iCal and update automatically.

## Local testing

```bash
export ST_EMAIL="..."
export ST_PASSWORD="..."
export ST_STAFF_ID=77
export ST_CENTER_ID=2
export ST_ORG=encodeworld

pip install requests
python sync.py
```

This generates `docs/schooltracs.ics` locally so you can verify it before pushing.

## Troubleshooting

**Login fails:** the login endpoint shape might be different than what we guessed. Run locally first and inspect the response. If it fails, open Chrome DevTools, log in manually, watch which `/auth/login` request fires, and adjust the `payload` dict in `sync.py` to match.

**Empty calendar:** check the staff ID is correct. You can also temporarily comment out the staff filter in `fetch_activities` to see all center activities.

**ICS not updating:** GitHub Pages can cache for a few minutes. Apple Calendar also caches — set refresh to "Every hour" minimum.
