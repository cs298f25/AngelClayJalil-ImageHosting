# API Documentation

## Base URL
All API endpoints are prefixed with `/api/v1/`.

## Authentication
Most endpoints require authentication via an API key. Include your API key in the request header:
```
X-API-Key: <your_api_key>
```

## Endpoints

### Development

#### Issue API Key
Create a new user account and receive an API key.

**Endpoint:** `POST /api/v1/dev/issue-key`

**Authentication:** None required

**Response:**
```json
{
  "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "uid": "u_user_abc12345"
}
```

**Status Codes:**
- `200 OK`: API key issued successfully

---

### Upload

#### Request Upload
Request a presigned URL for uploading an image to S3.

**Endpoint:** `POST /api/v1/upload/request`

**Authentication:** Required (X-API-Key header)

**Request Body:**
```json
{
  "filename": "example.jpg",
  "mime_type": "image/jpeg"
}
```

**Response:**
```json
{
  "iid": "img_abc123456789",
  "key": "uploads/u_user_abc12345/img_abc123456789/example.jpg",
  "presigned_url": "https://s3.amazonaws.com/bucket/path?..."
}
```

**Status Codes:**
- `200 OK`: Presigned URL generated successfully
- `401 Unauthorized`: Invalid or missing API key
- `400 Bad Request`: Missing required fields (filename, mime_type)
- `500 Internal Server Error`: S3 error occurred

**Usage:**
1. Call this endpoint to get a presigned URL
2. Upload your image file directly to the presigned URL using a PUT request
3. Call `/api/v1/upload/complete` to finalize the upload

---

#### Complete Upload
Mark an upload as complete and register it in the system.

**Endpoint:** `POST /api/v1/upload/complete`

**Authentication:** Required (X-API-Key header)

**Request Body:**
```json
{
  "iid": "img_abc123456789",
  "key": "uploads/u_user_abc12345/img_abc123456789/example.jpg",
  "filename": "example.jpg",
  "mime_type": "image/jpeg"
}
```

**Response:**
```json
{
  "id": "img_abc123456789",
  "url": "/api/v1/image/img_abc123456789"
}
```

**Status Codes:**
- `201 Created`: Image successfully registered
- `401 Unauthorized`: Invalid or missing API key
- `400 Bad Request`: Missing required fields (iid, key, filename, mime_type)

---

### Gallery

#### List My Images
Retrieve all images uploaded by the authenticated user.

**Endpoint:** `GET /api/v1/me/images`

**Authentication:** Required (X-API-Key header)

**Response:**
```json
{
  "items": [
    {
      "id": "img_abc123456789",
      "owner_uid": "u_user_abc12345",
      "key": "uploads/u_user_abc12345/img_abc123456789/example.jpg",
      "url": "/api/v1/image/img_abc123456789",
      "filename": "example.jpg",
      "mime": "image/jpeg",
      "private": "1",
      "created_at": "1699123456",
      "views": "0"
    }
  ]
}
```

**Status Codes:**
- `200 OK`: Images retrieved successfully (may be empty array)
- `401 Unauthorized`: Invalid or missing API key

**Notes:**
- Returns up to 50 most recent images
- Images are sorted by creation time (newest first)

---

### Images

#### Get Image
Retrieve and view an image by its ID.

**Endpoint:** `GET /api/v1/image/<iid>`

**Authentication:** None required

**Parameters:**
- `iid` (path): Image ID (e.g., `img_abc123456789`)

**Response:**
- `302 Found`: Redirects to the presigned S3 URL (valid for 1 hour)

**Status Codes:**
- `302 Found`: Image found, redirecting to image URL
- `404 Not Found`: Image not found
- `500 Internal Server Error`: S3 error or corrupt image record

**Notes:**
- The redirect URL is a presigned S3 URL that expires after 1 hour
- Images are publicly accessible (no authentication required)

---

#### Delete Image
Delete an image and remove it from the system.

**Endpoint:** `DELETE /api/v1/image/<iid>`

**Authentication:** Required (X-API-Key header)

**Parameters:**
- `iid` (path): Image ID (e.g., `img_abc123456789`)

**Response:**
```json
{
  "status": "deleted",
  "id": "img_abc123456789"
}
```

**Status Codes:**
- `200 OK`: Image deleted successfully
- `401 Unauthorized`: Invalid or missing API key
- `403 Forbidden`: User does not own this image
- `404 Not Found`: Image not found
- `500 Internal Server Error`: S3 deletion error

**Notes:**
- Only the image owner can delete their images
- Deletes both the S3 object and Redis metadata

---

### Health Checks

#### Health Check
Check if the API is running.

**Endpoint:** `GET /health`

**Authentication:** None required

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- `200 OK`: Service is healthy

---

#### Redis Check
Check if Redis is accessible.

**Endpoint:** `GET /redis-check`

**Authentication:** None required

**Response:**
```json
{
  "redis": true
}
```

**Status Codes:**
- `200 OK`: Redis is accessible
- `500 Internal Server Error`: Redis is unreachable

---

## Error Response Format

All error responses follow this format:

```json
{
  "error": {
    "code": "error_code",
    "message": "Human-readable error message"
  }
}
```

**Common Error Codes:**
- `auth`: Authentication failed (invalid API key)
- `validation`: Request validation failed (missing/invalid fields)
- `not_found`: Resource not found
- `invalid_record`: Database record is corrupt
- `s3_error`: AWS S3 operation failed
- `redis_unreachable`: Redis connection failed

---

## Upload Flow Example

Complete workflow for uploading an image:

1. **Issue API Key** (one-time setup):
   ```bash
   curl -X POST http://localhost:8000/api/v1/dev/issue-key
   ```

2. **Request Upload URL**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/upload/request \
     -H "X-API-Key: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"filename": "photo.jpg", "mime_type": "image/jpeg"}'
   ```

3. **Upload to S3** (using the presigned URL from step 2):
   ```bash
   curl -X PUT "PRESIGNED_URL_FROM_STEP_2" \
     -H "Content-Type: image/jpeg" \
     --data-binary @photo.jpg
   ```

4. **Complete Upload**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/upload/complete \
     -H "X-API-Key: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "iid": "iid_from_step_2",
       "key": "key_from_step_2",
       "filename": "photo.jpg",
       "mime_type": "image/jpeg"
     }'
   ```

5. **View Image**:
   ```bash
   curl -L http://localhost:8000/api/v1/image/IMG_ID
   ```
