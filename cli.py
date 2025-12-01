#!/usr/bin/env python3
"""
ImageHost CLI
"""

import argparse
import json
import mimetypes
import os
import sys
import tempfile
from pathlib import Path
import requests

# --- STRICT IMPORT CHECK ---
try:
    from PIL import Image
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    print("\n[CRITICAL ERROR] Missing required libraries.")
    print("This CLI needs image processing tools to validate files and convert HEIC.")
    print("Please run this command on your laptop:")
    print("    pip install Pillow pillow-heif requests")
    print("\nExiting...")
    sys.exit(1)

KEY_PATH = Path.home() / ".imagehost_key"
ALLOWED_MIMES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}

# Helpers
def get_base_url() -> str:
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
    url = get_base_url() + path
    headers = {}
    if use_auth:
        headers["X-API-Key"] = load_api_key()

    try:
        resp = requests.request(method, url, json=json_body, headers=headers)
    except Exception as e:
        print(f"[error] Connection failed: {e}")
        sys.exit(1)

    if not resp.ok:
        print(f"[error] Server returned {resp.status_code}:")
        print(resp.text)
        sys.exit(1)

    try:
        body = resp.json()
        return body.get("data", body) if isinstance(body, dict) else body
    except Exception:
        return resp.text

# --- IMAGE PROCESSING ---
def process_file(file_path: Path):
    """
    Validates image type and converts HEIC to JPEG.
    Halt execution if file is invalid.
    """
    ext = file_path.suffix.lower()
    
    # 1. HEIC Conversion
    if ext in ['.heic', '.heif']:
        print("[info] HEIC image detected. Converting to JPEG...")
        try:
            img = Image.open(file_path)
            tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            tmp.close()
            
            img = img.convert("RGB")
            img.save(tmp.name, "JPEG", quality=90)
            return Path(tmp.name), "image/jpeg", True
        except Exception as e:
            print(f"[error] HEIC Conversion failed: {e}")
            sys.exit(1)

    # 2. Standard Validation
    try:
        img = Image.open(file_path)
        img.verify() # Verify it's actually an image, not just a renamed PDF
        
        # Re-open because verify() closes the file pointer in some versions
        img = Image.open(file_path) 
        mime = Image.MIME.get(img.format)
        
        if mime not in ALLOWED_MIMES:
            print(f"[error] Forbidden file type detected: {mime}")
            print(f"Allowed types: JPG, PNG, GIF, WEBP")
            sys.exit(1)
            
        return file_path, mime, False
    except Exception as e:
        print(f"[error] Invalid or Corrupt File: {e}")
        sys.exit(1)

# Commands
def cmd_login(args):
    print("--- ImageHost Login ---")
    username = input("Username: ").strip()
    mode = input("Do you have an account? [y/n]: ").lower()
    import getpass
    password = getpass.getpass("Password: ")

    endpoint = "/api/v1/register" if mode == 'n' else "/api/v1/login"
    data = api_request("POST", endpoint, json_body={"username": username, "password": password}, use_auth=False)
    save_api_key(data["api_key"])
    print(f"[ok] Login successful!")

def cmd_upload(args):
    original_path = Path(args.path).expanduser()
    if not original_path.is_file():
        print(f"[error] File not found: {original_path}")
        sys.exit(1)

    # This will now EXIT if the file is invalid
    upload_path, mime_type, needs_cleanup = process_file(original_path)
    
    # Use original name but ensure correct extension
    if needs_cleanup:
        filename = original_path.with_suffix('.jpg').name
    else:
        filename = original_path.name

    print(f"[info] Uploading {filename} ({mime_type})...")

    # Request -> Upload -> Complete
    req = api_request("POST", "/api/v1/upload/request", json_body={"filename": filename, "mime_type": mime_type}, use_auth=True)
    
    with upload_path.open("rb") as f:
        s3_resp = requests.put(req["presigned_url"], data=f, headers={"Content-Type": mime_type})
    
    if not s3_resp.ok:
        print(f"[error] S3 Upload Failed: {s3_resp.status_code}")
        if needs_cleanup: os.unlink(upload_path)
        sys.exit(1)

    api_request("POST", "/api/v1/upload/complete", json_body={
        "iid": req["iid"], "key": req["key"], "filename": filename, "mime_type": mime_type
    }, use_auth=True)
    
    print("[ok] Upload complete!")
    if needs_cleanup: os.unlink(upload_path)

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    
    sub.add_parser("login").set_defaults(func=cmd_login)
    up = sub.add_parser("upload")
    up.add_argument("path")
    up.set_defaults(func=cmd_upload)
    
    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()