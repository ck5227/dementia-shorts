#!/usr/bin/env python3
"""Upload one episode to YouTube via the YouTube Data API (resumable upload).

Usage: python3 scripts/upload_youtube.py NAME     (e.g. 2026-11-19 or 2026-11-19-classic)

Needs env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (OAuth, scope youtube.upload).
Publishes at NAME's date 07:30 Asia/Taipei (scheduled, via publishAt); if that time has
already passed (or is < 15 min away), publishes immediately as public.
Writes episodes/NAME.youtube.json with the video id on success.
"""
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

TAIPEI = dt.timezone(dt.timedelta(hours=8))
MAX_DESC_BYTES = 4900  # YouTube limit is 5000 bytes


def post_json(url, data, headers=None, method="POST"):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.status, dict(r.headers), r.read()


def access_token():
    body = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    _, _, raw = post_json("https://oauth2.googleapis.com/token", body,
                          {"Content-Type": "application/x-www-form-urlencoded"})
    return json.loads(raw)["access_token"]


def clip_bytes(s, n):
    b = s.encode("utf-8")
    if len(b) <= n:
        return s
    return b[:n].decode("utf-8", "ignore").rstrip() + "…"


def main(name):
    ep = json.load(open(f"episodes/{name}.json", encoding="utf-8"))
    video = f"videos/{name}.mp4"
    out = f"episodes/{name}.youtube.json"
    if os.path.exists(out):
        print(f"{out} exists; already uploaded, skipping")
        return

    d = dt.date.fromisoformat(ep["date"])
    when = dt.datetime(d.year, d.month, d.day, 7, 30, tzinfo=TAIPEI)
    now = dt.datetime.now(TAIPEI)
    status = {"selfDeclaredMadeForKids": False, "containsSyntheticMedia": False,
              "embeddable": True, "license": "youtube"}
    if when - now > dt.timedelta(minutes=15):
        status["privacyStatus"] = "private"
        status["publishAt"] = when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    else:
        status["privacyStatus"] = "public"

    meta = {
        "snippet": {
            "title": ep["youtube_title"].replace("<", "").replace(">", "")[:100],
            "description": clip_bytes(ep["youtube_description"].replace("<", "").replace(">", ""), MAX_DESC_BYTES),
            "tags": ep.get("tags", []),
            "categoryId": "27",  # Education
            "defaultLanguage": "zh-TW",
            "defaultAudioLanguage": "zh-TW",
        },
        "status": status,
    }
    size = os.path.getsize(video)
    tok = access_token()
    init_url = ("https://www.googleapis.com/upload/youtube/v3/videos"
                "?uploadType=resumable&part=snippet,status&notifySubscribers=true")
    _, hdrs, _ = post_json(init_url, json.dumps(meta).encode(), {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(size),
    })
    loc = hdrs.get("Location") or hdrs.get("location")
    with open(video, "rb") as f:
        data = f.read()
    _, _, raw = post_json(loc, data, {"Authorization": f"Bearer {tok}",
                                      "Content-Type": "video/mp4",
                                      "Content-Length": str(size)}, method="PUT")
    res = json.loads(raw)
    vid = res["id"]
    got = res.get("status", {})
    record = {"videoId": vid, "url": f"https://youtube.com/shorts/{vid}",
              "uploadedAt": now.isoformat(timespec="seconds"),
              "requested": status, "returned": got}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(json.dumps(record, ensure_ascii=False, indent=2))

    # Unverified Google API projects can have uploads locked to private.
    if status["privacyStatus"] == "public" and got.get("privacyStatus") != "public":
        sys.exit(f"WARNING: requested public but YouTube returned {got.get('privacyStatus')!r} "
                 "(project may be locked to private until Google audit)")
    if "publishAt" in status and not got.get("publishAt"):
        sys.exit("WARNING: scheduled publishAt was not accepted (video may be locked private)")


if __name__ == "__main__":
    main(sys.argv[1])
