import pytest
import cli
import argparse
import builtins
import getpass
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Attempt to import PIL to create real dummy images for testing
try:
    from PIL import Image
except ImportError:
    Image = None

# --- FIXTURES ---

@pytest.fixture
def temp_image(tmp_path):
    """Creates a valid 10x10 JPEG image for testing"""
    if not Image:
        pytest.skip("Pillow not installed, cannot generate test image")
    
    img_path = tmp_path / "valid.jpg"
    img = Image.new('RGB', (10, 10), color='red')
    img.save(img_path)
    return img_path

@pytest.fixture
def temp_text_file(tmp_path):
    """Creates a text file disguised as an image"""
    f = tmp_path / "fake.jpg"
    f.write_text("This is not an image")
    return f

@pytest.fixture
def temp_heic(tmp_path):
    """Creates a dummy file with .heic extension"""
    f = tmp_path / "photo.heic"
    f.write_bytes(b"dummy_heic_content")
    return f

# --- TEST VALIDATION LOGIC ---

def test_process_file_valid_image(temp_image):
    """Should return the path and correct mime type without cleanup"""
    path, mime, cleanup = cli.process_file(temp_image)
    
    assert path == temp_image
    assert mime == "image/jpeg"
    assert cleanup is False

def test_process_file_rejects_text_file(temp_text_file, capsys):
    """Should exit with error if file is not a real image"""
    with pytest.raises(SystemExit) as exc:
        cli.process_file(temp_text_file)
    
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Invalid or Corrupt File" in captured.out

def test_process_file_rejects_forbidden_mime(tmp_path, capsys):
    """Should reject valid images that are not in the ALLOWED list (like BMP or TIFF)"""
    if not Image: pytest.skip("Pillow needed")
    
    bmp_path = tmp_path / "test.bmp"
    img = Image.new('RGB', (10, 10))
    img.save(bmp_path)
    
    with pytest.raises(SystemExit) as exc:
        cli.process_file(bmp_path)
        
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Forbidden file type" in captured.out

def test_process_file_heic_conversion(temp_heic, monkeypatch):
    """Should trigger conversion logic for HEIC files"""
    
    # Mock Image.open so we don't actually try to convert the dummy file
    mock_img = MagicMock()
    mock_converted = MagicMock()
    
    # Setup chain: open() -> convert() -> save()
    mock_img.convert.return_value = mock_converted
    
    def fake_open(fp):
        return mock_img

    monkeypatch.setattr(cli.Image, "open", fake_open)
    
    # Run
    path, mime, cleanup = cli.process_file(temp_heic)
    
    # Assert
    assert mime == "image/jpeg"
    assert cleanup is True
    assert path.suffix == ".jpg" # Should be a temp file ending in .jpg
    
    # Verify PIL methods were called
    mock_img.convert.assert_called_with("RGB")
    mock_converted.save.assert_called()

# --- TEST COMMANDS (Login / Upload) ---

class DummyResponse:
    def __init__(self, ok=True, json_data=None):
        self.ok = ok
        self.status_code = 200
        self.text = ""
        self._json = json_data or {}

    def json(self):
        return self._json

def test_cmd_login_flow(monkeypatch, tmp_path, capsys):
    # 1. Setup paths
    monkeypatch.setattr(cli, "KEY_PATH", tmp_path / "keyfile")

    # 2. Mock API Request
    def fake_api_request(method, path, json_body=None, use_auth=True):
        return {"api_key": "secret_key_123"}

    monkeypatch.setattr(cli, "api_request", fake_api_request)

    # 3. Mock Inputs (Username: 'test', New Account?: 'n', Password: 'pw')
    inputs = iter(["testuser", "n"]) 
    monkeypatch.setattr(builtins, "input", lambda msg: next(inputs))
    monkeypatch.setattr(getpass, "getpass", lambda msg: "password123")

    # 4. Run
    cli.cmd_login(argparse.Namespace())

    # 5. Assert
    captured = capsys.readouterr()
    assert "Login successful" in captured.out
    assert cli.KEY_PATH.read_text().strip() == "secret_key_123"

def test_cmd_upload_flow(monkeypatch, tmp_path, capsys, temp_image):
    # 1. Mock API calls
    api_calls = []
    def fake_api_request(method, path, json_body=None, use_auth=True):
        api_calls.append(path)
        if "request" in path:
            return {
                "presigned_url": "http://s3.fake/upload",
                "iid": "123", 
                "key": "key"
            }
        return {}

    monkeypatch.setattr(cli, "api_request", fake_api_request)
    monkeypatch.setattr(cli, "load_api_key", lambda: "token")
    
    # 2. Mock S3 PUT request
    monkeypatch.setattr(cli.requests, "put", lambda *_, **__: DummyResponse())

    # 3. Run
    cli.cmd_upload(argparse.Namespace(path=str(temp_image)))

    # 4. Assert
    captured = capsys.readouterr()
    assert "Upload complete" in captured.out
    assert "/api/v1/upload/request" in api_calls
    assert "/api/v1/upload/complete" in api_calls