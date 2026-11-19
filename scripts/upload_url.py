#!/usr/bin/env python3
"""Upload a video from a public URL to the channel via the YouTube Data API.

Used by .github/workflows/youtube-upload-url.yml for videos that live outside this
repo (e.g. BESTEP videos stored as GitHub release assets in ck5227/bestep-daily).

Inputs come from env: VIDEO_URL, TITLE, DESCRIPTION, TAGS (comma separated),
PRIVACY (default public). Needs YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
Prints one line `RESULT {json}` with videoId, url and the status YouTube returned.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from upload_youtube import access_token, clip_bytes, post_json, MAX_DESC_BYTES  # noqa: E402


def main():
    url = os.environ["VIDEO_URL"]
    if not url.startswith("https://github.com/ck5227/"):
        sys.exit("VIDEO_URL must be a ck5227 GitHub release asset")
    with urllib.request.urlopen(url, timeout=600) as r:
        data = r.read()
    clean = lambda s: s.replace("<", "").replace(">", "")
    tags = [t.strip() for t in os.environ.get("TAGS", "").split(",") if t.strip()]
    status = {"privacyStatus": os.environ.get("PRIVACY") or "public",
              "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False,
              "embeddable": True, "license": "youtube"}
    meta = {
        "snippet": {
            "title": clean(os.environ["TITLE"])[:100],
            "description": clip_bytes(clean(os.environ.get("DESCRIPTION", "")), MAX_DESC_BYTES),
            "tags": tags,
            "categoryId": "27",  # Education
            "defaultLanguage": "zh-TW",
            "defaultAudioLanguage": "en",
        },
        "status": status,
    }
    tok = access_token()
    init_url = ("https://www.googleapis.com/upload/youtube/v3/videos"
                "?uploadType=resumable&part=snippet,status&notifySubscribers=true")
    _, hdrs, _ = post_json(init_url, json.dumps(meta).encode(), {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(len(data)),
    })
    loc = hdrs.get("Location") or hdrs.get("location")
    _, _, raw = post_json(loc, data, {"Authorization": f"Bearer {tok}",
                                      "Content-Type": "video/mp4",
                                      "Content-Length": str(len(data))}, method="PUT")
    res = json.loads(raw)
    vid = res["id"]
    out = {"videoId": vid, "url": f"https://www.youtube.com/watch?v={vid}",
           "requested": status["privacyStatus"],
           "returned": res.get("status", {}).get("privacyStatus")}
    print("RESULT " + json.dumps(out, ensure_ascii=False))
    if out["returned"] != out["requested"]:
        sys.exit(f"WARNING: requested {out['requested']} but YouTube returned {out['returned']!r}")


if __name__ == "__main__":
    main()
