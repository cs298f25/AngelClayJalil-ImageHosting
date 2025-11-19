# Developer Documentation

## Overview

ImageHosting is a Flask-based image hosting service that stores images in AWS S3 and metadata in Redis. Users can upload, view, and manage their images through a REST API.

## Tech Stack

- **Backend Framework:** Flask (Python)
- **Database:** Redis (for metadata storage)
- **Storage:** AWS S3 (for image files)
- **Authentication:** API key-based (using itsdangerous URLSafeSerializer)

## Architecture

### Components

1. **Flask Application (`app.py`)**
   - Handles HTTP requests and routing
   - Manages authentication and authorization
   - Coordinates between Redis and S3

2. **Redis Database**
   - Stores user metadata (`user:{uid}`)
   - Stores image metadata (`img:{iid}`)
   - Maintains user image lists (`user:{uid}:images` sorted set)

3. **AWS S3**
   - Stores actual image files
   - Images are organized by: `uploads/{uid}/{iid}/{filename}`
   - Uses presigned URLs for secure uploads/downloads

### Data Models

#### User
```
user:{uid}
  - username: string
  - uid: string
  - created_at: timestamp
```

#### Image
```
img:{iid}
  - id: string (iid)
  - owner_uid: string
  - key: string (S3 key)
  - url: string (S3 URL reference)
  - filename: string
  - mime: string (MIME type)
  - private: int (0 or 1)
  - created_at: timestamp
  - views: int
```

#### User Images Index
```
user:{uid}:images (sorted set)
  - key: iid
  - score: timestamp (for sorting by newest first)
```

## Setup

### Prerequisites

- Python 3.7+
- Redis server
- AWS account with S3 bucket
- AWS credentials configured

### Installation

1. **Clone the repository** (if applicable)

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the project root:
   ```env
   FLASK_SECRET=your-secret-key-here
   REDIS_URL=redis://localhost:6379/0
   AWS_REGION=us-east-1
   AWS_S3_BUCKET_NAME=your-bucket-name
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   PORT=80
   FLASK_DEBUG=1
   ```

4. **Start Redis:**
   ```bash
   redis-server
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

The server will start on `http://localhost:80` (or the PORT specified in your .env file).

**Note:** Port 80 requires root privileges on Linux. For production, consider using a reverse proxy (nginx/apache) on port 80 that forwards to Flask on a higher port.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_SECRET` | Secret key for signing API keys | `dev-secret` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `AWS_REGION` | AWS region for S3 | `us-east-1` |
| `AWS_S3_BUCKET_NAME` | S3 bucket name | *Required* |
| `PORT` | Port to run Flask app | `8000` (or `80` for production) |
| `FLASK_DEBUG` | Enable Flask debug mode | `1` |

### AWS S3 Configuration

Ensure your S3 bucket:
- Has appropriate CORS configuration for browser uploads (if needed)
- Has IAM policies that allow the application to:
  - `s3:PutObject` - for uploads
  - `s3:GetObject` - for viewing images
  - `s3:DeleteObject` - for deleting images

Example IAM policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

## Development

### Project Structure

```
.
├── app.py              # Main Flask application
├── index.html          # Frontend HTML
├── script.js           # Frontend JavaScript
├── style.css           # Frontend CSS
├── requirements.txt    # Python dependencies
├── api.md             # API documentation
├── developers.md      # This file
├── README.md          # Project overview
└── deploy.md          # Deployment instructions
```

### Key Functions

#### Authentication
- `require_api_key()`: Validates API key from `X-API-Key` header
- API keys are signed using `URLSafeSerializer` with the Flask secret key
- Decoded tokens contain `{"uid": "user_id"}`

#### Redis Keys
- `k_user(uid)`: Returns `user:{uid}`
- `k_user_images(uid)`: Returns `user:{uid}:images`
- `k_img(iid)`: Returns `img:{iid}`

#### Helper Functions
- `now()`: Returns current Unix timestamp
- `ok(payload, status)`: Returns JSON success response
- `err(code, message, status)`: Returns JSON error response
- `get_s3_url(key)`: Returns S3 URL reference string

### Upload Flow

1. Client requests presigned URL via `/api/v1/upload/request`
2. Server generates presigned PUT URL for S3 (expires in 1 hour)
3. Client uploads image directly to S3 using presigned URL
4. Client notifies server via `/api/v1/upload/complete`
5. Server creates Redis records and associates image with user

### Testing

Test the API using curl or your preferred HTTP client:

```bash
# Health check
curl http://localhost:8000/health

# Get API key
curl -X POST http://localhost:8000/api/v1/dev/issue-key

# List images (use API key from above)
curl -X GET http://localhost:8000/api/v1/me/images \
  -H "X-API-Key: YOUR_API_KEY"
```

## Security Considerations

1. **API Keys**: Currently issued without user authentication. In production, implement proper user registration/login.

2. **Image Access**: All images are currently publicly accessible. Consider implementing:
   - Private image flag enforcement
   - Access control lists
   - Image sharing with expiration

3. **File Validation**: The API accepts any MIME type. Consider:
   - Validating MIME types (only allow image/*)
   - File size limits
   - Virus scanning
   - Image dimension validation

4. **Rate Limiting**: No rate limiting is currently implemented. Consider adding:
   - Per-user upload limits
   - Request rate limiting
   - Storage quotas

5. **CORS**: If serving the frontend from a different domain, configure CORS appropriately.

## Extending the Service

### Adding Image Metadata

To add new fields to images, update the `complete_upload()` function:

```python
pipe.hset(k_img(iid), mapping={
    # ... existing fields ...
    "new_field": value,
})
```

### Adding User Preferences

Add user preferences to the user hash:

```python
pipe.hset(k_user(uid), mapping={
    # ... existing fields ...
    "preference_name": value,
})
```

### Custom Image Processing

Add image processing after upload completion:

```python
@app.post("/api/v1/upload/complete")
def complete_upload():
    # ... existing code ...
    
    # Add image processing here
    process_image(key)  # Your processing function
    
    return ok({"id": iid, "url": f"/api/v1/image/{iid}"}, 201)
```

## Troubleshooting

### Redis Connection Issues
- Ensure Redis is running: `redis-cli ping`
- Check `REDIS_URL` environment variable
- Verify Redis is accessible from your network

### S3 Upload Failures
- Verify AWS credentials are set correctly
- Check S3 bucket name is correct
- Ensure IAM permissions are sufficient
- Check S3 bucket region matches `AWS_REGION`

### API Key Invalid Errors
- API keys are signed with `FLASK_SECRET`
- Changing `FLASK_SECRET` invalidates all existing keys
- Ensure `FLASK_SECRET` is consistent across deployments

## Dependencies

- `flask`: Web framework
- `redis`: Redis client
- `boto3`: AWS SDK for Python
- `python-dotenv`: Environment variable management
- `itsdangerous`: Secure token signing

See `requirements.txt` for specific versions.

## Version History

- **v1.0** - Initial release
  - Basic upload/download functionality
  - API key authentication
  - Image gallery
  - Image deletion
