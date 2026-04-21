"""
youtube_uploader.py — Authenticated YouTube upload with token caching.

First run: opens a browser for Google OAuth (one-time).
Subsequent runs: uses cached token — fully non-interactive.

Requires client_secrets.json from:
  Google Cloud Console → APIs & Services → Credentials → Download OAuth JSON
"""

import os
import pickle
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES       = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE   = "youtube_token.pickle"
SECRETS_FILE = "client_secrets.json"


def _get_credentials():
    creds = None

    if Path(TOKEN_FILE).exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        print("  [YouTube] Refreshing OAuth token…")
        creds.refresh(Request())
    else:
        if not Path(SECRETS_FILE).exists():
            raise FileNotFoundError(
                f"\n[YouTube] {SECRETS_FILE} not found.\n"
                "Download from: Google Cloud Console → APIs & Services → "
                "Credentials → OAuth 2.0 Client IDs → Download JSON\n"
                "Rename the file to client_secrets.json and place it here."
            )
        print("  [YouTube] Opening browser for one-time Google OAuth…")
        flow  = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)
    print("  [YouTube] Token cached → youtube_token.pickle")

    return creds


def upload_video(
    file: str,
    title: str,
    description: str,
    tags: list[str],
    scheduled_time: str | None = None,
) -> str | None:
    """
    Upload a video to YouTube.
    Returns the YouTube video ID, or None if upload is skipped/failed.
    scheduled_time: ISO-8601 UTC string e.g. '2026-04-12T14:00:00+00:00'
    """
    try:
        creds   = _get_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        privacy = "public" if not scheduled_time else "scheduled"
        body    = {
            "snippet": {
                "title":       title[:100],      # YouTube 100-char limit
                "description": description[:5000],
                "tags":        tags[:500],
                "categoryId":  "20",             # Gaming
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }
        if scheduled_time:
            body["status"]["publishAt"] = scheduled_time

        media   = MediaFileUpload(file, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        print(f"  [YouTube] Uploading {Path(file).name}…")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"  [YouTube] {pct}% uploaded", end="\r")

        video_id = response.get("id")
        print(f"  [YouTube] Done → https://youtu.be/{video_id}  (status: {privacy})")
        return video_id

    except FileNotFoundError as exc:
        print(f"  [YouTube] Skipped — {exc}")
        return None
    except Exception as exc:
        print(f"  [YouTube] Upload failed: {exc}")
        return None


if __name__ == "__main__":
    # Quick test
    upload_video(
        file="final_video.mp4",
        title="Test Upload",
        description="Test from youtube_uploader.py",
        tags=["Minecraft", "Shorts"],
    )
