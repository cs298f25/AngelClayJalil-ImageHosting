#!/usr/bin/env python3
"""
CLI helper for our Image Hosting project.
"""

import argparse
import json
import mimetypes
import os
import sys
import tempfile
from pathlib import Path

import requests

# Try imports for image processing
try:
    from PIL import Image
    import pillow_heif
    pillow_heif.register_heif_opener()
    HAS_IMAGE_TOOLS = True
except ImportError:
    HAS_IMAGE_TOOLS = False

KEY_PATH = Path.home() / ".imagehost_key"
ALLOWED_MIMES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}

# Helpers
# -----------------------
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
        print(f"[error] could not connect to {url}: {e}")
        sys.exit(1)

    if not resp.ok:
        print(f"[error] HTTP {resp.status_code} from server:")
        try:
            print(json.dumps(resp.json(), indent=2))
        except Exception:
            print(resp.text)
        sys.exit(1)

    try:
        body = resp.json()
    except Exception:
        return resp.text

    return body.get("data", body) if isinstance(body, dict) else body

# --- NEW: Image Processing Logic ---
def process_file(file_path: Path):
    """
    Validates image type and converts HEIC to JPEG if needed.
    Returns: (Path to file to upload, mime_type, needs_cleanup_bool)
    """
    if not HAS_IMAGE_TOOLS:
        print("[warning] Pillow/pillow-heif not installed. Skipping strict validation and HEIC conversion.")
        mime, _ = mimetypes.guess_type(str(file_path))
        return file_path, mime or "application/octet-stream", False

    # Check extension first
    ext = file_path.suffix.lower()
    
    # 1. Handle HEIC Conversion
    if ext in ['.heic', '.heif']:
        print("[info] HEIC detected. Converting to JPEG for web compatibility...")
        try:
            img = Image.open(file_path)
            # Create temp file
            tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            tmp.close()
            
            # Convert and save
            img = img.convert("RGB")
            img.save(tmp.name, "JPEG", quality=90)
            
            return Path(tmp.name), "image/jpeg", True
        except Exception as e:
            print(f"[error] Failed to convert HEIC: {e}")
            sys.exit(1)

    # 2. Validate standard images
    try:
        img = Image.open(file_path)
        img.verify() # Checks file integrity
        mime = Image.MIME.get(img.format)
        
        if mime not in ALLOWED_MIMES:
            print(f"[error] Invalid image type: {mime}")
            print(f"Allowed: {', '.join(ALLOWED_MIMES)}")
            sys.exit(1)
            
        return file_path, mime, False
    except Exception as e:
        print(f"[error] Invalid file: {e}")
        sys.exit(1)

# Commands
# -----------------------
def cmd_login(args):
    print("--- ImageHost Login ---")
    username = input("Username: ").strip()
    mode = input("Do you have an account? [y/n]: ").lower()
    
    import getpass
    password = getpass.getpass("Password: ")

    endpoint = "/api/v1/register" if mode == 'n' else "/api/v1/login"
    payload = {"username": username, "password": password}
    
    data = api_request("POST", endpoint, json_body=payload, use_auth=False)

    try:
        save_api_key(data["api_key"])
        print(f"[ok] Login successful! Key saved.")
    except Exception:
        print("[error] Unexpected response")
        sys.exit(1)

def cmd_upload(args):
    original_path = Path(args.path).expanduser()
    if not original_path.is_file():
        print(f"[error] file does not exist: {original_path}")
        sys.exit(1)

    # Validate and/or Convert
    upload_path, mime_type, needs_cleanup = process_file(original_path)
    filename = upload_path.name

    # If we converted HEIC, we want the filename to be original_name.jpg, not tempfile_name.jpg
    if needs_cleanup:
        filename = original_path.with_suffix('.jpg').name

    print(f"[info] Uploading {filename} ({mime_type})...")

    # Step 1: Request URL
    payload = {"filename": filename, "mime_type": mime_type}
    data = api_request("POST", "/api/v1/upload/request", json_body=payload, use_auth=True)

    try:
        # Step 2: Upload bytes
        with upload_path.open("rb") as f:
            put_resp = requests.put(
                data["presigned_url"],
                data=f,
                headers={"Content-Type": mime_type},
            )
        
        if not put_resp.ok:
            print(f"[error] S3 Error: {put_resp.status_code}")
            sys.exit(1)

        # Step 3: Finalize
        final_payload = {
            "iid": data["iid"],
            "key": data["key"],
            "filename": filename,
            "mime_type": mime_type,
        }
        api_request("POST", "/api/v1/upload/complete", json_body=final_payload, use_auth=True)
        print("[ok] Upload complete!")

    finally:
        # Clean up temp file if we created one
        if needs_cleanup:
            os.unlink(upload_path)

# -----------------------
# Argparse wiring
# -----------------------
def build_parser():
    p = argparse.ArgumentParser(description="Image host CLI")
    sub = p.add_subparsers(dest="command", required=True)

    lp = sub.add_parser("login", help="login or register")
    lp.set_defaults(func=cmd_login)

    up = sub.add_parser("upload", help="upload an image file")
    up.add_argument("path", help="path to an image file")
    up.set_defaults(func=cmd_upload)

    return p

def main():
    args = build_parser().parse_args()
    args.func(args)

if __name__ == "__main__":
    main()