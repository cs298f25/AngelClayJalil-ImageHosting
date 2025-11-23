from infrastructure.s3_client import S3Client

def main():
    s3 = S3Client()
    print("[test] S3Client is using bucket:", s3.bucket_name)

    # Just a fake key to see if presign works
    key = "test-folder/test-object.txt"
    url = s3.generate_presigned_upload_url(key, "text/plain")
    print("[test] Got presigned URL:")
    print(url)

if __name__ == "__main__":
    main()
