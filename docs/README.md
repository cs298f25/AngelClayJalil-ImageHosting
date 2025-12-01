# AngelClayJalil-ImageHosting

# ImageHost

**ImageHost** is a image hosting service built with a Service-Oriented Architecture. It allows users to register accounts, upload images via drag-and-drop or CLI, and serve them via AWS S3.

## Project Description

This project implements a scalable web application that separates concerns into distinct layers:
* **Presentation Layer:** Flask API and Nginx Reverse Proxy.
* **Service Layer:** Business logic for Authentication and Image processing.
* **Infrastructure Layer:** Abstractions for Redis and AWS S3.

**Key Features:**
* **Secure Authentication:** User registration/login with password hashing and API Key generation.
* **Hybrid Storage:** Metadata lookups via Redis and binary storage via AWS S3.
* **CLI Tool:** A dedicated Python Command Line Interface for headless uploads.
* **Automated Deployment:** One-click deployment script (`deploy.sh`) for Amazon Linux environments including Nginx configuration and SSL setup.

### Tech Stack
* **Backend:** Python 3.9+, Flask, Gunicorn
* **Database:** Redis (Key-Value Store)
* **Storage:** AWS S3 (Simple Storage Service)
* **Server:** Nginx (Reverse Proxy)
* **Frontend:** Vanilla JavaScript, HTML5, CSS3
* **Testing:** Pytest

---

## API Documentation

All API endpoints are prefixed with `/api/v1/`. Authentication is handled via the `X-API-Key` header.

### Authentication
| Method | Endpoint | Description | Auth Required |
| --- | --- | --- | --- |
| `POST` | `/register` | Create a new account with username/password. | No |
| `POST` | `/login` | Log in to receive an API Key. | No |

### Image Operations
| Method | Endpoint | Description | Auth Required |
| --- | --- | --- | --- |
| `POST` | `/upload/request` | Request a presigned S3 URL for direct upload. | Yes |
| `POST` | `/upload/complete` | Finalize upload and save metadata to Redis. | Yes |
| `GET` | `/me/images` | List all images owned by the user. | Yes |
| `GET` | `/image/<id>` | Redirects to the publicly accessible S3 URL. | No |
| `DELETE` | `/image/<id>` | Delete image from S3 and Redis. | Yes |

### System
| Method | Endpoint | Description | Auth Required |
| --- | --- | --- | --- |
| `GET` | `/health` | Check API status. | No |
| `GET` | `/redis-check` | Check Database connectivity. | No |

---


### Prerequisites
* Python 3.9+
* Redis Server (`redis-server`)
* AWS Account 


### Deployment with AWS EC2

1.  **Launch an EC2 Instance:**
    * Ensure Security Group allows ports: `22` (SSH), `80` (HTTP), `443` (HTTPS).
    * Attach an IAM Role (`LabInstanceProfile`) with S3 permissions.

2.  **Deploy the Code:**
    SSH into the server, clone the repo, and create the `.env` file.

3.  **Run the Deployment Script:**
    This script installs Nginx, Redis, and Python, configures the proxy, and starts the app.
    ```bash
    ./deploy.sh
    ```

4.  **Enable HTTPS (SSL):**
    ```bash
    sudo dnf install certbot python3-certbot-nginx -y
    sudo certbot --nginx
    ```

---

## LI Usage

The project includes a CLI tool (`cli.py`) for interacting with the service from the terminal.

1.  **Set the Target URL:**
    ```bash
    export BASE_URL="[http://your-domain.com](http://your-domain.com)"
    ```

2.  **Login:**
    ```bash
    python3 cli.py login
    ```
    *Make sure you are in the folder where cli.py is in the terminal*
    *Follow the prompts to enter your username/password. The API key will be saved locally.*

3.  **Upload an Image:**
    ```bash
    python3 cli.py upload /path/to/image.jpg
    ```

---
