"""
Service layer: This is where the *actual business logic* lives.
The Flask app shouldn’t be doing heavy lifting — it should just forward requests here.
"""

import uuid
import os
import re
import unicodedata
import time
from infrastructure.redis_client import RedisClient
from infrastructure.s3_client import S3Client

redis_client = RedisClient()
s3_client = S3Client()

# Helper to get timestamps in seconds
def now():
    return int(time.time())


class Utils:

    @staticmethod
    def sanitize_filename(filename: str, max_len: int = 120) -> str:
        """Normalize filenames so S3 keys are URL-safe and consistent."""
        filename = filename or "file"
        name, ext = os.path.splitext(filename)

        # Normalize / strip accents
        def normalize(value: str) -> str:
            normalized = unicodedata.normalize("NFKD", value)
            return normalized.encode("ascii", "ignore").decode()

        # Clean the base name
        safe_name = normalize(name)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", safe_name).strip("-._").lower()
        if not safe_name:
            safe_name = "file"

        safe_name = safe_name[:max_len]

        # Clean the extension
        safe_ext = normalize(ext).lower()
        safe_ext = re.sub(r"[^a-z0-9]", "", safe_ext)
        safe_ext = f".{safe_ext}" if safe_ext else ""

        return f"{safe_name}{safe_ext}"


from werkzeug.security import generate_password_hash, check_password_hash



class AuthService:
    @staticmethod
    def register_user(username, password):
        """
        Creates a new user with a password.
        1. Check if username exists.
        2. Create UID.
        3. Save username->uid mapping.
        4. Save user data with hashed password.
        """
        # 1. Check if username is taken (we use a simple redis key for this)
        if redis_client._r.exists(f"username:{username}"):
            return {"error": "Username already exists"}

        uid = f"u_{uuid.uuid4().hex[:8]}"
        password_hash = generate_password_hash(password)

        # 2. Transaction to save everything
        pipe = redis_client._r.pipeline()
        
        # Save the lookup index: username -> uid
        pipe.set(f"username:{username}", uid)
        
        # Save the user data
        pipe.hset(f"user:{uid}", mapping={
            "uid": uid,
            "username": username,
            "password_hash": password_hash,
            "created_at": now()
        })
        
        pipe.execute()

        return {"uid": uid, "username": username}

    @staticmethod
    def login_user(username, password):
        """
        Verifies password and returns the user's UID (which we turn into an API Key).
        """
        # 1. Lookup UID from username
        uid = redis_client._r.get(f"username:{username}")
        if not uid:
            return None # User not found

        # 2. Get the password hash
        user_data = redis_client.get_image(uid.replace("u_", "user:")) # reusing get_image helper which is basically hgetall
        # Or better, just use raw redis here since get_image expects img: prefix
        user_data = redis_client._r.hgetall(f"user:{uid}")
        
        if not user_data or "password_hash" not in user_data:
            return None

        # 3. Verify password
        if check_password_hash(user_data["password_hash"], password):
            return {"uid": uid, "username": username}
        
        return None

class ImageService:
    """
    Handles all image-related business logic.
    Flask calls into this anytime you upload, view, or delete an image.
    """

    @staticmethod
    def initiate_upload(uid: str, filename: str, mime_type: str):
        """
        Step 1 of uploading:
        - clean filename
        - generate image ID
        - build the S3 key path
        - ask S3 for a presigned upload URL
        """
        safe_filename = Utils.sanitize_filename(filename)
        iid = f"img_{uuid.uuid4().hex[:12]}"

        # Storing everything under uploads/<user>/<imageID>/<filename>
        key = f"uploads/{uid}/{iid}/{safe_filename}"

        # Ask S3 to give us a temporary upload link
        presigned_url = s3_client.generate_presigned_upload_url(key, mime_type)

        return {
            "iid": iid,
            "key": key,
            "filename": safe_filename,
            "presigned_url": presigned_url,
        }

    @staticmethod
    def finalize_upload(uid: str, iid: str, key: str, filename: str, mime_type: str):
        """
        Step 2 of uploading:
        The image is already in S3 — now we save the metadata to Redis.
        """
        public_url = s3_client.get_public_url(key)

        redis_client.store_image(
            iid,
            uid,
            key,
            public_url,
            filename,
            mime_type,
            now()
        )

        return {"id": iid, "url": public_url}

    @staticmethod
    def get_user_gallery(uid: str):
        """
        Pull all images for the user and make sure URLs are actually usable.
        Redis might store older URLs, so we fix/refresh as needed.
        """
        iids = redis_client.get_user_images(uid, limit=50)
        results = redis_client.get_images_batch(iids)

        clean_items = []
        for data in results:
            if not data:
                continue

            url = data.get("url")
            key = data.get("key")

            # Clean or rebuild URLs when needed
            if key and (not url or url.startswith("s3://") or "#" in url):
                data["url"] = s3_client.get_public_url(key)

            # If URL is completely missing, fallback to app proxy
            if not data.get("url"):
                data["url"] = f"/api/v1/image/{data['id']}"

            clean_items.append(data)

        return clean_items

    @staticmethod
    def get_image_download_url(iid: str):
        """
        Fetch an individual image record and generate a temporary download link.
        """
        img_data = redis_client.get_image(iid)
        if not img_data:
            return None

        s3_key = img_data.get("key")
        if not s3_key:
            raise ValueError("Image record missing S3 key — this means it's corrupted.")

        return s3_client.generate_presigned_download_url(s3_key)

    @staticmethod
    def delete_image(iid: str, requester_uid: str):
        """
        Full delete logic:
        - make sure image exists
        - make sure the person deleting it actually owns it
        - delete from S3 first
        - delete from Redis second
        """
        img_data = redis_client.get_image(iid)
        if not img_data:
            return {"error": "not_found", "code": 404}

        if img_data.get("owner_uid") != requester_uid:
            return {"error": "forbidden", "code": 403}

        s3_key = img_data.get("key")
        if not s3_key:
            return {"error": "corrupt_record", "code": 500}

        # Try removing from both storage layers
        try:
            s3_client.delete_object(s3_key)
            redis_client.delete_image(iid, requester_uid)
            return {"status": "success"}
        except Exception as e:
            print(f"Service Error: {e}")
            return {"error": "storage_error", "code": 500}
