#!/usr/bin/env python3
import os
import sys
import json
import argparse
import mimetypes
import subprocess
import pathlib
import requests
from dotenv import load_dotenv

# read BASE_URL from .env, fall back to local server
load_dotenv()
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# where we stash the API key locally
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".imagehost.json")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def call_api(path, *, method="GET", api_key=None, body=None):
    """Small helper for talking to the Flask API."""
    url = f"{BASE_URL}{path}"
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    if body is not None:
        headers["Content-Type"] = "application/json"

    resp = requests.request(method, url, headers=headers, json=body)
    if not resp.ok:
        try:
            data = resp.json()
            msg = data.get("error", {}).get("message") or resp.text
        except Exception:
            msg = resp.text
        raise SystemExit(f"{method} {path} failed: {resp.status_code} {msg}")

    return resp.json() if resp.text else {}


def copy_to_clipboard(text):
    """Best effort copy (macOS). If not available, just return False."""
    if sys.platform != "darwin":
        return False
    try:
        p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"))
        return p.returncode == 0
    except Exception:
        return False


def cmd_login(_args):
    # ask the server for a dev key and store it locally
    data = call_api("/api/v1/dev/issue-key", method="POST", body={})
    cfg = load_config()
    cfg["api_key"] = data["api_key"]
    cfg["uid"] = data["uid"]
    save_config(cfg)
    print(f"saved api key for {cfg['uid']}")


def cmd_upload(args):
    cfg = load_config()
    api_key = cfg.get("api_key")
    if not api_key:
        raise SystemExit("no API key. run: python cli.py login")

    path = pathlib.Path(args.file)
    if not path.exists():
        raise SystemExit(f"file not found: {path}")

    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        mime = "application/octet-stream"

    # 1) get a presigned PUT url
    presign = call_api(
        "/api/v1/upload/request",
        method="POST",
        api_key=api_key,
        body={"filename": path.name, "mime_type": mime},
    )
    iid, key, put_url = presign["iid"], presign["key"], presign["presigned_url"]

    # 2) upload the bytes to S3
    with open(path, "rb") as f:
        r = requests.put(put_url, data=f, headers={"Content-Type": mime})
        if not r.ok:
            raise SystemExit(f"S3 PUT failed: {r.status_code} {r.text}")

    # 3) tell the server we’re done so it saves metadata in Redis
    done = call_api(
        "/api/v1/upload/complete",
        method="POST",
        api_key=api_key,
        body={"iid": iid, "key": key, "filename": path.name, "mime_type": mime},
    )

    url = f"{BASE_URL}{done['url']}"  # /api/v1/image/<iid>
    copied = copy_to_clipboard(url)
    print(f"uploaded: {path.name}")
    print(url + ("  (copied)" if copied else ""))


def cmd_list(_args):
    cfg = load_config()
    api_key = cfg.get("api_key")
    if not api_key:
        raise SystemExit("no API key. run: python cli.py login")

    data = call_api("/api/v1/me/images", method="GET", api_key=api_key)
    items = data.get("items", [])
    if not items:
        print("no images")
        return

    for it in items:
        iid = it.get("id", "")
        name = it.get("filename", "")
        m = it.get("mime", "")
        url = f"{BASE_URL}{it.get('url', '')}"
        print(f"{iid}\t{name}\t{m}\t{url}")


def cmd_delete(args):
    cfg = load_config()
    api_key = cfg.get("api_key")
    if not api_key:
        raise SystemExit("no API key. run: python cli.py login")
    iid = args.iid
    call_api(f"/api/v1/image/{iid}", method="DELETE", api_key=api_key)
    print(f"deleted {iid}")


def main():
    parser = argparse.ArgumentParser(prog="imagehost", description="CLI for ImageHost")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_login = sub.add_parser("login", help="get and save a dev API key")
    p_login.set_defaults(func=cmd_login)

    p_upload = sub.add_parser("upload", help="upload an image file")
    p_upload.add_argument("file", help="path to an image")
    p_upload.set_defaults(func=cmd_upload)

    p_list = sub.add_parser("list", help="list my images")
    p_list.set_defaults(func=cmd_list)

    p_del = sub.add_parser("delete", help="delete by image id")
    p_del.add_argument("iid", help="e.g., img_ab12cd34")
    p_del.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
