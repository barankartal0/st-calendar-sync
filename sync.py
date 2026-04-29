"""
SchoolTracs → ICS Calendar Sync
Fetches your assigned classes from SchoolTracs and outputs an .ics file
that Apple/Google Calendar can subscribe to.
"""

import os
import sys
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ─── CONFIG ────────────────────────────────────────────────────────────────
ST_BASE = "https://web.schooltracs.com"
GRAPHQL_URL = f"{ST_BASE}/v4/graphql"

ST_EMAIL    = os.environ.get("ST_EMAIL")
ST_PASSWORD = os.environ.get("ST_PASSWORD")
ST_STAFF_ID = os.environ.get("ST_STAFF_ID", "77")
ST_CENTER_ID= os.environ.get("ST_CENTER_ID", "2")
ST_ORG      = os.environ.get("ST_ORG", "encodeworld")

WEEKS_AHEAD = 8
OUTPUT_PATH = Path(__file__).parent / "docs" / "schooltracs.ics"
HK_TZ       = timezone(timedelta(hours=8))

BROWSER_UA  = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)


# ─── AUTH ──────────────────────────────────────────────────────────────────
def login(session: requests.Session) -> None:
    if not ST_EMAIL or not ST_PASSWORD:
        sys.exit("❌ ST_EMAIL and ST_PASSWORD env vars are required")

    print(f"🔐 Logging in as {ST_EMAIL}...")

    # 1. Visit login page first to pick up any initial cookies
    session.get(
        f"{ST_BASE}/app/login",
        headers={"User-Agent": BROWSER_UA},
        timeout=30,
    )

    # 2. Submit the form exactly as the browser does
    redirect_to = (
        f"https://web.schooltracs.com/v4/web/timetable"
        f"?o={ST_ORG}"
    )
    payload = {
        "redirectTo": redirect_to,
        "username":   ST_EMAIL,
        "password":   ST_PASSWORD,
    }

    resp = session.post(
        f"{ST_BASE}/app/login",
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin":        ST_BASE,
            "Referer":       f"{ST_BASE}/app/login",
            "User-Agent":    BROWSER_UA,
        },
        allow_redirects=True,
        timeout=30,
    )

    print(f"   status={resp.status_code}  final_url={resp.url}")
    print(f"   cookies={list(session.cookies.keys())}")

    if resp.status_code == 401 or "app/login" in resp.url:
        print("❌ Login failed — wrong credentials or form format")
        print(resp.text[:400])
        sys.exit(1)

    print(f"✅ Logged in ({len(session.cookies)} cookies)")


# ─── GRAPHQL QUERY ─────────────────────────────────────────────────────────
WEEKLY_ACTIVITY_QUERY = """
query weeklyActivityList($where: Json, $sort: Json, $limit: Int) {
  activityList(where: $where, sort: $sort, limit: $limit) {
    items {
      id centerId category name level cnl courseId classId
      startDate endDate date realWeekDay startTime endTime
      number detail remark color enrolled
      activityStaffs {
        staff { id name deleted __typename }
        staffId status __typename
      }
      activityFacilities {
        facility { id name deleted __typename }
        facilityId __typename
      }
      __typename
    }
    __typename
  }
}
"""


def fetch_activities(session: requests.Session) -> list[dict]:
    today = datetime.now(HK_TZ).date()
    end   = today + timedelta(weeks=WEEKS_AHEAD)

    print(f"📅 Fetching {today} → {end} ...")

    body = [{
        "operationName": "weeklyActivityList",
        "variables": {
            "where": {
                "date":     {"$gte": today.isoformat(), "$lt": end.isoformat()},
                "deleted":  0,
                "centerId": ST_CENTER_ID,
            },
            "limit": 7000,
        },
        "query": WEEKLY_ACTIVITY_QUERY,
    }]

    resp = session.post(
        GRAPHQL_URL,
        json=body,
        headers={
            "Content-Type": "application/json",
            "Origin":  ST_BASE,
            "Referer": f"{ST_BASE}/v4/web/timetable?b={ST_CENTER_ID}&o={ST_ORG}",
            "User-Agent": BROWSER_UA,
        },
        timeout=60,
    )

    if resp.status_code != 200:
        print(f"❌ GraphQL failed: {resp.status_code}")
        print(resp.text[:400])
        sys.exit(1)

    items = resp.json()[0]["data"]["activityList"]["items"]
    print(f"📦 {len(items)} total activities")

    mine = [
        a for a in items
        if any(s["staffId"] == ST_STAFF_ID for s in (a.get("activityStaffs") or []))
    ]
    print(f"👤 {len(mine)} assigned to staff {ST_STAFF_ID}")
    return mine


# ─── ICS ───────────────────────────────────────────────────────────────────
def fmt_dt(date_str: str, time_str: str) -> str:
    return f"{date_str.replace('-','')}T{time_str.replace(':','')}00"

def esc(text: str) -> str:
    if not text:
        return ""
    return (text.replace("\\","\\\\")
                .replace(",","\\,")
                .replace(";","\\;")
                .replace("\n","\\n"))

def make_ics(activities: list[dict]) -> str:
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Baran//SchoolTracs Sync//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:SchoolTracs",
        "X-WR-TIMEZONE:Asia/Hong_Kong",
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Hong_Kong",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0800",
        "TZOFFSETTO:+0800",
        "TZNAME:HKT",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]

    for a in activities:
        title  = a.get("cnl") or a.get("name") or "Class"
        rooms  = ", ".join(
            f["facility"]["name"]
            for f in (a.get("activityFacilities") or [])
            if f.get("facility")
        )
        desc_parts = []
        if a.get("level"):    desc_parts.append(f"Level: {a['level']}")
        if a.get("number"):   desc_parts.append(f"Lesson #{a['number']}")
        desc_parts.append(f"Enrolled: {a.get('enrolled', 0)}")
        if a.get("remark"):   desc_parts.append(f"Remark: {a['remark']}")
        description = "\n".join(desc_parts)

        uid = hashlib.md5(
            f"{a['id']}-{a['date']}-{a['startTime']}".encode()
        ).hexdigest() + "@schooltracs"

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART;TZID=Asia/Hong_Kong:{fmt_dt(a['date'], a['startTime'])}",
            f"DTEND;TZID=Asia/Hong_Kong:{fmt_dt(a['date'], a['endTime'])}",
            f"SUMMARY:{esc(title)}",
            f"DESCRIPTION:{esc(description)}",
        ]
        if rooms:
            lines.append(f"LOCATION:{esc(rooms)}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ─── MAIN ──────────────────────────────────────────────────────────────────
def main() -> None:
    session = requests.Session()
    login(session)
    activities = fetch_activities(session)
    ics = make_ics(activities)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(ics, encoding="utf-8")
    print(f"✅ Wrote {len(activities)} events → {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
