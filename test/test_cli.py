import pytest
import cli
import argparse

# Dummy helper class to simulate requests.Response
class DummyResponse:
    def __init__(self, ok=True):
        self.ok = ok
        self.status_code = 200
        self.text = ""

def test_cmd_login_saves_key(monkeypatch, tmp_path, capsys):
    # 1. Point the KEY_PATH to a temporary folder so we don't overwrite your real key
    monkeypatch.setattr(cli, "KEY_PATH", tmp_path / "keyfile")

    # 2. Mock the API request function inside cli.py
    monkeypatch.setattr(cli, "api_request", lambda *args, **kwargs: {"api_key": "secret", "uid": "u_1"})

    # 3. Run the command
    cli.cmd_login(argparse.Namespace())

    # 4. Check stdout output
    captured = capsys.readouterr()
    assert "saved API key" in captured.out
    
    # 5. Check if file was written
    assert cli.KEY_PATH.read_text().strip() == "secret"

def test_cmd_upload_happy_path(monkeypatch, tmp_path, capsys):
    # Create a fake image file
    img = tmp_path / "photo.png"
    img.write_bytes(b"binarydata")

    # Track calls to make sure flow is correct
    calls = []
    
    def fake_api_request(method, path, json_body=None, use_auth=True):
        calls.append((method, path, json_body, use_auth))
        if path == "/api/v1/upload/request":
            return {"iid": "img_1", "key": "k1", "presigned_url": "https://upload"}
        if path == "/api/v1/upload/complete":
            assert json_body["iid"] == "img_1"
            return {"status": "ok"}
        raise AssertionError("unexpected path")

    monkeypatch.setattr(cli, "api_request", fake_api_request)
    monkeypatch.setattr(cli, "load_api_key", lambda: "token")
    # Mock requests.put for the S3 upload
    monkeypatch.setattr(cli.requests, "put", lambda *_, **__: DummyResponse())

    # Run
    cli.cmd_upload(argparse.Namespace(path=str(img)))

    # Verify
    captured = capsys.readouterr()
    assert "[ok] upload complete!" in captured.out
    assert calls[0][1] == "/api/v1/upload/request"
    assert calls[1][1] == "/api/v1/upload/complete"