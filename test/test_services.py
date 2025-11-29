import os
import pytest
import services
from services import AuthService, ImageService, Utils

# We set a dummy bucket name so the S3Client doesn't crash on init
os.environ.setdefault("AWS_S3_BUCKET_NAME", "test-bucket")

# --- MOCKS ---
# Instead of using real Redis/S3, we create fake classes that look like them.

class DummyRedis:
    def __init__(self):
        self.created_users = []
        self.images = {}
        self.user_images = {}
        self.deleted = []

    def create_user(self, uid, username, created_at):
        self.created_users.append((uid, username, created_at))

    def store_image(self, iid, owner_uid, key, url, filename, mime_type, created_at):
        self.images[iid] = {
            "id": iid,
            "owner_uid": owner_uid,
            "key": key,
            "url": url,
            "filename": filename,
            "mime_type": mime_type,
            "created_at": created_at,
        }
        self.user_images.setdefault(owner_uid, []).append(iid)

    def get_user_images(self, uid, limit=50):
        return list(self.user_images.get(uid, []))[:limit]

    def get_images_batch(self, iids):
        return [self.images.get(i) for i in iids]

    def get_image(self, iid):
        return self.images.get(iid)

    def delete_image(self, iid, uid):
        self.deleted.append((iid, uid))


class DummyS3:
    def __init__(self):
        self.upload_calls = []
        self.download_calls = []
        self.deleted = []

    def generate_presigned_upload_url(self, key, mime_type):
        self.upload_calls.append((key, mime_type))
        return f"https://upload/{key}"

    def generate_presigned_download_url(self, key):
        self.download_calls.append(key)
        return f"https://download/{key}"

    def get_public_url(self, key):
        return f"https://public/{key}"

    def delete_object(self, key):
        self.deleted.append(key)


# --- FIXTURES ---
# Pytest uses fixtures to setup the state before tests run

@pytest.fixture
def fake_redis(monkeypatch):
    fake = DummyRedis()
    # This magic line replaces the real redis_client in services.py with our fake one
    monkeypatch.setattr(services, "redis_client", fake)
    return fake

@pytest.fixture
def fake_s3(monkeypatch):
    fake = DummyS3()
    monkeypatch.setattr(services, "s3_client", fake)
    return fake

@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    # Freeze time so tests are predictable
    monkeypatch.setattr(services, "now", lambda: 123456)


# --- TESTS ---

def test_sanitize_filename_handles_unicode():
    result = Utils.sanitize_filename("Špéciål Name!!.PNG")
    assert result == "special-name.png"

def test_auth_service_creates_user(fake_redis):
    data = AuthService.create_new_user()
    assert data["uid"].startswith("u_")
    assert fake_redis.created_users # entry recorded

def test_initiate_upload_builds_expected_key(fake_s3):
    result = ImageService.initiate_upload("u_1", "My Photo.JPG", "image/jpeg")
    
    # Check if key structure is correct: uploads/u_1/img_.../my-photo.jpg
    assert result["key"].startswith("uploads/u_1/img_")
    assert result["filename"] == "my-photo.jpg"
    # Check if S3 was asked for a URL
    assert fake_s3.upload_calls[0][0] == result["key"]

def test_finalize_upload_stores_metadata(fake_redis, fake_s3):
    # Act
    payload = ImageService.finalize_upload("u_1", "img_1", "uploads/u/img/file.png", "file.png", "image/png")
    
    # Assert return value
    assert payload == {"id": "img_1", "url": "https://public/uploads/u/img/file.png"}
    # Assert DB storage
    assert fake_redis.images["img_1"]["owner_uid"] == "u_1"

def test_get_user_gallery_refreshes_bad_urls(fake_redis, fake_s3):
    """If Redis has an old s3:// URL, service should convert it to https://"""
    fake_redis.images["img_1"] = {
        "id": "img_1", "owner_uid": "u_2", "key": "k1", "url": "s3://bad"
    }
    fake_redis.user_images["u_2"] = ["img_1"]

    gallery = ImageService.get_user_gallery("u_2")
    
    # Should be fixed by logic
    assert gallery[0]["url"] == "https://public/k1"

def test_get_image_download_url_requires_key(fake_redis):
    # Setup corrupted record (no key)
    fake_redis.images["img_1"] = {"id": "img_1"}
    
    with pytest.raises(ValueError):
        ImageService.get_image_download_url("img_1")

def test_delete_image_validates_owner(fake_redis, fake_s3):
    fake_redis.images["img_1"] = {"id": "img_1", "owner_uid": "owner", "key": "k1"}

    # 1. Try deleting as wrong user
    response = ImageService.delete_image("img_1", "other_person")
    assert response["error"] == "forbidden"

    # 2. Try deleting as correct user
    response_ok = ImageService.delete_image("img_1", "owner")
    assert response_ok == {"status": "success"}
    assert fake_s3.deleted == ["k1"]
    assert fake_redis.deleted[0] == ("img_1", "owner")