#!/usr/bin/env python3
"""
Tiny CLI helper for our Image Hosting project.

It talks to the Flask API:
- login: asks the server for a dev API key and saves it locally
- upload: uploads an image via S3 presigned URL and finalizes it

It supports BOTH response shapes:
- {"data": {...}}    (new pattern)
- {...}              (older pattern)
"""

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

import requests

KEY_PATH = Path.home() / ".imagehost_key"


# Helpers
# -----------------------
def get_base_url() -> str:
    """
    Where the API lives.
    On your Mac:
      - local:  http://127.0.0.1:8000
      - EC2:    http://34.204.188.204:8000
    """
    return os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def save_api_key(api_key: str) -> None:
    KEY_PATH.write_text(api_key.strip(), encoding="utf-8")
    print(f"[ok] saved API key to {KEY_PATH}")


def load_api_key() -> str:
    if not KEY_PATH.exists():
        print("[error] no API key found. Run `python cli.py login` first.")
        sys.exit(1)
    return KEY_PATH.read_text(encoding="utf-8").strip()


def api_request(method: str, path: str, json_body=None, use_auth: bool = True):
    """
    Basic HTTP wrapper.
    It accepts BOTH:

      { "data": {...} }
      {...}
    """
    url = get_base_url() + path
    headers = {}

    if use_auth:
        api_key = load_api_key()
        headers["X-API-Key"] = api_key

    try:
        resp = requests.request(method, url, json=json_body, headers=headers)
    except Exception as e:
        print(f"[error] could not connect to {url}: {e}")
        sys.exit(1)

    if not resp.ok:
        print(f"[error] HTTP {resp.status_code} from server:")
        try:
            print(json.dumps(resp.json(), indent=2))
        except Exception:
            print(resp.text)
        sys.exit(1)

    # Try to parse JSON and unwrap data if present
    try:
        body = resp.json()
    except Exception:
        print("[error] server returned non-JSON response:")
        print(resp.text)
        sys.exit(1)

    if isinstance(body, dict) and "data" in body:
        return body["data"]
    else:
        # Older server style – just return whole JSON
        return body


# Commands
# -----------------------
def cmd_login(args):
    print("[info] requesting dev API key...")
    data = api_request("POST", "/api/v1/dev/issue-key", use_auth=False)

    # Accept both shapes: {"api_key": ..., "uid": ...} OR nested under data
    try:
        api_key = data["api_key"]
        uid = data["uid"]
    except Exception:
        print("[error] login response did not contain api_key/uid:")
        print(json.dumps(data, indent=2))
        sys.exit(1)

    save_api_key(api_key)
    print(f"[ok] got key for user {uid}")


def cmd_upload(args):
    img_path = Path(args.path).expanduser()
    if not img_path.is_file():
        print(f"[error] file does not exist: {img_path}")
        sys.exit(1)

    # Guess MIME type
    mime_type, _ = mimetypes.guess_type(str(img_path))
    if not mime_type:
        mime_type = "application/octet-stream"

    filename = img_path.name
    print(f"[info] requesting upload URL for {filename} ({mime_type})...")

    # Step 1: ask API for presigned URL
    payload = {
        "filename": filename,
        "mime_type": mime_type,
    }
    data = api_request("POST", "/api/v1/upload/request", json_body=payload, use_auth=True)

    # Expect at least these fields
    try:
        iid = data["iid"]
        key = data["key"]
        presigned_url = data["presigned_url"]
    except Exception:
        print("[error] upload request response missing fields:")
        print(json.dumps(data, indent=2))
        sys.exit(1)

    # Step 2: actually upload the file bytes to S3
    print("[info] uploading file bytes to S3 via presigned URL...")
    with img_path.open("rb") as f:
        put_resp = requests.put(
            presigned_url,
            data=f,
            headers={"Content-Type": mime_type},
        )

    if not put_resp.ok:
        print(f"[error] S3 upload failed: HTTP {put_resp.status_code}")
        print(put_resp.text)
        sys.exit(1)

    print("[ok] file uploaded to S3. Finalizing metadata with API...")

    # Step 3: tell API we’re done so it can store metadata in Redis
    complete_payload = {
        "iid": iid,
        "key": key,
        "filename": filename,
        "mime_type": mime_type,
    }

    final_data = api_request(
        "POST",
        "/api/v1/upload/complete",
        json_body=complete_payload,
        use_auth=True,
    )

    print("[ok] upload complete!")
    print(json.dumps(final_data, indent=2))


# -----------------------
# Argparse wiring
# -----------------------
def build_parser():
    p = argparse.ArgumentParser(description="Image host CLI")
    sub = p.add_subparsers(dest="command", required=True)

    # login
    lp = sub.add_parser("login", help="request a dev API key")
    lp.set_defaults(func=cmd_login)

    # upload
    up = sub.add_parser("upload", help="upload an image file")
    up.add_argument("path", help="path to an image file")
    up.set_defaults(func=cmd_upload)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
