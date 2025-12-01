# Developer Documentation

## Overview

ImageHosting is a Flask-based image hosting service that stores images in AWS S3 and metadata in Redis. Users can upload, view, and manage their images through a REST API and web interface.

## Tech Stack

- **Backend Framework:** Flask (Python)
- **Web Server:** Nginx (reverse proxy on port 80) + Gunicorn (WSGI server on port 8000)
- **Database:** Redis (for metadata storage)
- **Storage:** AWS S3 (for image files)
- **Authentication:** API key-based (using itsdangerous URLSafeSerializer)
- **Frontend:** Vanilla JavaScript with HTML/CSS

## Architecture

### Components

1. **Nginx Reverse Proxy**
   - Listens on port 80 (HTTP)
   - Proxies all requests to Gunicorn on port 8000
   - Handles static file serving (optional)

2. **Flask Application (`app.py`)**
   - Handles HTTP requests and routing
   - Manages authentication and authorization
   - Delegates business logic to Service Layer

3. **Service Layer (`services.py`)**
   - `AuthService`: User registration, login, and authentication
   - `ImageService`: Image upload, retrieval, deletion, and gallery management
   - Contains all business logic separated from HTTP concerns

4. **Infrastructure Layer**
   - `infrastructure/redis_client.py`: Redis connection and operations
   - `infrastructure/s3_client.py`: S3 operations and presigned URL generation

5. **Redis Database**
   - Stores user metadata (`user:{uid}`)
   - Stores image metadata (`img:{iid}`)
   - Maintains user image lists (`user:{uid}:images` sorted set)

6. **AWS S3**
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

2. **Run the deployment script:**
   ```bash
   ./deploy.sh
   ```
   
   This script will:
   - Install Redis and Nginx (if on Amazon Linux)
   - Configure Nginx to proxy port 80 → 8000
   - Create Python virtual environment
   - Install Python dependencies
   - Start Redis
   - Start the application (Gunicorn in production, Flask dev server locally)

3. **Set up environment variables:**
   Create a `.env` file in the project root:
   ```env
   FLASK_SECRET=your-secret-key-here
   REDIS_URL=redis://localhost:6379/0
   AWS_REGION=us-east-1
   AWS_S3_BUCKET_NAME=your-bucket-name
   FLASK_DEBUG=1
   ```

4. **Access the application:**
   - **Production (EC2)**: `http://your-server-ip` (port 80, no port number needed)
   - **Local development**: `http://localhost:8000` (Flask dev server)

**Note:** The deployment script automatically sets up Nginx as a reverse proxy. In production, Nginx listens on port 80 and forwards requests to Gunicorn on port 8000.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_SECRET` | Secret key for signing API keys | `dev-secret` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `AWS_REGION` | AWS region for S3 | `us-east-1` |
| `AWS_S3_BUCKET_NAME` | S3 bucket name | *Required* |
| `FLASK_DEBUG` | Enable Flask debug mode | `1` |

**Note:** The application runs on port 8000 internally (Gunicorn). Nginx proxies from port 80 to port 8000 automatically.

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
├── app.py                  # Main Flask application (HTTP layer)
├── services.py             # Service layer (business logic)
├── cli.py                  # Command-line interface
├── deploy.sh               # Deployment script
├── down.sh                 # Shutdown script
├── requirements.txt        # Python dependencies
├── infrastructure/
│   ├── redis_client.py    # Redis client wrapper
│   └── s3_client.py       # S3 client wrapper
├── template/
│   └── index.html         # Frontend HTML template
├── static/
│   ├── script.js          # Frontend JavaScript
│   └── style.css          # Frontend CSS
├── test/                  # Test files
│   ├── test_app.py
│   ├── test_services.py
│   ├── test_cli.py
│   └── test_infrastructure.py
└── docs/                  # Documentation
    ├── api.md
    ├── developers.md
    └── deploy.md
```

### Key Components

#### Service Layer (`services.py`)
- **`AuthService`**: 
  - `register_user(username, password)`: Creates new user account
  - `login_user(username, password)`: Authenticates user and returns user data
  - `create_new_user()`: Legacy method for dev API key issuance
- **`ImageService`**:
  - `initiate_upload(uid, filename, mime_type)`: Generates presigned S3 upload URL
  - `finalize_upload(uid, iid, key, filename, mime_type)`: Saves image metadata
  - `get_user_gallery(uid)`: Retrieves all images for a user
  - `get_image_download_url(iid)`: Generates presigned S3 download URL
  - `delete_image(iid, uid)`: Deletes image and verifies ownership

#### Infrastructure Layer
- **`RedisClient`** (`infrastructure/redis_client.py`):
  - Handles all Redis operations
  - Manages connections and error handling
- **`S3Client`** (`infrastructure/s3_client.py`):
  - Generates presigned URLs for uploads/downloads
  - Handles S3 object operations

#### HTTP Layer (`app.py`)
- `require_api_key()`: Validates API key from `X-API-Key` header
- API keys are signed using `URLSafeSerializer` with the Flask secret key
- Decoded tokens contain `{"uid": "user_id"}`
- `ok(payload, status)`: Returns JSON success response
- `err(code, message, status)`: Returns JSON error response

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
curl http://localhost/health
# Or locally: curl http://localhost:8000/health

# Register a new user
curl -X POST http://localhost/api/v1/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass"}'

# Login
curl -X POST http://localhost/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass"}'

# List images (use API key from register/login)
curl -X GET http://localhost/api/v1/me/images \
  -H "X-API-Key: YOUR_API_KEY"
```

**Note:** Replace `localhost` with your server IP in production. Port 80 is used (no port number needed) when Nginx is configured.

## Security Considerations

1. **API Keys**: User registration and login are implemented. API keys are issued after successful registration/login.

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
- `gunicorn`: WSGI HTTP server for production
- `redis`: Redis client
- `boto3`: AWS SDK for Python
- `python-dotenv`: Environment variable management
- `pytest`: Testing framework
- `requests`: HTTP library (for CLI)

See `requirements.txt` for specific versions.

## Deployment

The application uses a layered deployment approach:

1. **Nginx** (port 80): Reverse proxy that forwards requests to Gunicorn
2. **Gunicorn** (port 8000): WSGI server running the Flask application
3. **Redis**: Metadata storage (runs as daemon)
4. **AWS S3**: Image file storage

Use `./deploy.sh` to automatically set up and start all components. Use `./down.sh` to stop all services.

## Version History

- **v2.0** - Current version
  - Service layer architecture (separation of concerns)
  - User registration and login
  - Nginx reverse proxy setup
  - Infrastructure layer abstraction
  - CLI tool for API interaction
  - Comprehensive test suite

- **v1.0** - Initial release
  - Basic upload/download functionality
  - Dev API key issuance
  - Image gallery
  - Image deletion
