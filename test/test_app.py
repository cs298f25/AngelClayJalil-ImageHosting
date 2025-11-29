import pytest
import app 
from services import redis_client

@pytest.fixture
def client():
    app.app.config["TESTING"] = True
    with app.app.test_client() as client:
        yield client

def _auth_header(uid="u_test"):
    token = app.signer.dumps({"uid": uid})
    return {"X-API-Key": token}

def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}

# --- NEW AUTH ROUTE TESTS ---
def test_register_route_success(client, monkeypatch):
    # Mock AuthService to return success
    monkeypatch.setattr(app.AuthService, "register_user", lambda u, p: {"uid": "u_1", "username": u})
    
    resp = client.post("/api/v1/register", json={"username": "me", "password": "pw"})
    payload = resp.get_json()
    
    assert resp.status_code == 200
    assert payload["username"] == "me"
    assert "api_key" in payload

def test_login_route_success(client, monkeypatch):
    # Mock AuthService to return success
    monkeypatch.setattr(app.AuthService, "login_user", lambda u, p: {"uid": "u_1", "username": u})
    
    resp = client.post("/api/v1/login", json={"username": "me", "password": "pw"})
    payload = resp.get_json()
    
    assert resp.status_code == 200
    assert "api_key" in payload

def test_request_upload_requires_api_key(client):
    resp = client.post("/api/v1/upload/request", json={"filename": "x", "mime_type": "image/png"})
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "auth"

def test_request_upload_success(client, monkeypatch):
    expected = {"iid": "img_1", "key": "k", "presigned_url": "url", "filename": "f"}
    
    def fake_initiate(uid, filename, mime_type):
        assert uid == "u_owner"
        assert filename == "photo.png"
        assert mime_type == "image/png"
        return expected
        
    monkeypatch.setattr(app.ImageService, "initiate_upload", fake_initiate)

    resp = client.post(
        "/api/v1/upload/request", 
        json={"filename": "photo.png", "mime_type": "image/png"},
        headers=_auth_header(uid="u_owner")
    )

    assert resp.status_code == 200
    assert resp.get_json() == expected

def test_redis_check_handles_failure(client, monkeypatch):
    def broken_ping():
        raise RuntimeError("boom")
    monkeypatch.setattr(redis_client, "ping", broken_ping)
    resp = client.get("/redis-check")
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["error"]["code"] == "redis_unreachable"

def test_get_image_redirects(client, monkeypatch):
    monkeypatch.setattr(app.ImageService, "get_image_download_url", lambda iid: "http://example.com/img.jpg")
    resp = client.get("/api/v1/image/i1")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "http://example.com/img.jpg"