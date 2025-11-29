import pytest
import os
from unittest.mock import MagicMock, patch, ANY  # <--- FIX: Imported ANY here
from infrastructure.redis_client import RedisClient
from infrastructure.s3_client import S3Client

# --- REDIS CLIENT TESTS ---

@patch("infrastructure.redis_client.redis.from_url")
def test_redis_init(mock_from_url):
    os.environ["REDIS_URL"] = "redis://test:6379/0"
    client = RedisClient()
    mock_from_url.assert_called_with("redis://test:6379/0", decode_responses=True)

@patch("infrastructure.redis_client.redis.from_url")
def test_redis_create_user(mock_from_url):
    mock_redis = MagicMock()
    mock_from_url.return_value = mock_redis
    client = RedisClient()
    client.create_user("u_123", "john_doe", 1000.0)
    mock_redis.hsetnx.assert_called_with("user:u_123", "username", "john_doe")
    mock_redis.hset.assert_called()

@patch("infrastructure.redis_client.redis.from_url")
def test_redis_store_image_uses_pipeline(mock_from_url):
    mock_redis = MagicMock()
    mock_pipeline = MagicMock()
    mock_redis.pipeline.return_value = mock_pipeline
    mock_from_url.return_value = mock_redis

    client = RedisClient()
    client.store_image("img_1", "u_1", "key.png", "http://url", "file.png", "image/png", 123)

    mock_redis.pipeline.assert_called()
    mock_pipeline.hset.assert_called()
    mock_pipeline.zadd.assert_called()
    mock_pipeline.execute.assert_called()

@patch("infrastructure.redis_client.redis.from_url")
def test_redis_get_user_images(mock_from_url):
    mock_redis = MagicMock()
    mock_from_url.return_value = mock_redis
    client = RedisClient()
    client.get_user_images("u_1", limit=10)
    mock_redis.zrevrange.assert_called_with("user:u_1:images", 0, 9)

# --- S3 CLIENT TESTS ---

def test_s3_init_requires_bucket_name():
    if "AWS_S3_BUCKET_NAME" in os.environ:
        del os.environ["AWS_S3_BUCKET_NAME"]
    with pytest.raises(ValueError) as exc:
        S3Client()
    assert "environment variable not set" in str(exc.value)

@patch("infrastructure.s3_client.boto3.client")
def test_s3_init_connects_boto(mock_boto):
    os.environ["AWS_S3_BUCKET_NAME"] = "my-bucket"
    os.environ["AWS_REGION"] = "us-west-2"
    
    S3Client()
    
    # FIX: Use ANY instead of pytest.any
    mock_boto.assert_called_with(
        "s3", 
        region_name="us-west-2", 
        config=ANY
    )

@patch("infrastructure.s3_client.boto3.client")
def test_s3_generate_presigned_upload(mock_boto):
    os.environ["AWS_S3_BUCKET_NAME"] = "test-bucket"
    mock_s3 = MagicMock()
    mock_boto.return_value = mock_s3
    
    client = S3Client()
    client.generate_presigned_upload_url("uploads/file.jpg", "image/jpeg")

    mock_s3.generate_presigned_url.assert_called_with(
        "put_object",
        Params={
            "Bucket": "test-bucket",
            "Key": "uploads/file.jpg",
            "ContentType": "image/jpeg"
        },
        ExpiresIn=3600
    )

@patch("infrastructure.s3_client.boto3.client")
def test_s3_public_url_formatting(mock_boto):
    os.environ["AWS_S3_BUCKET_NAME"] = "my-bucket"
    client = S3Client()
    
    url = client.get_public_url("simple.png")
    assert url == "https://my-bucket.s3.amazonaws.com/simple.png"

    url_spaces = client.get_public_url("folder/my file.png")
    assert url_spaces == "https://my-bucket.s3.amazonaws.com/folder/my%20file.png"