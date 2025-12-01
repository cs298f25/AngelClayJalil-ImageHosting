# Deployment Guide

Follow these steps to deploy the ImageHosting application to AWS.

---

### 1. S3 Bucket Setup

1.  **Create an S3 Bucket**
    * Uncheck "Block all public access" (We need the images to be viewable).
    * Enable ACLs if necessary, but Bucket Policy is preferred.

2.  **Add Bucket Policy**
    * Go to **Permissions** -> **Bucket Policy**.
    * Paste this JSON:
    ```json
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadUploads",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::<bucket name>/uploads/*"
            }
        ]
    }
    ```

3.  **Add CORS Configuration**
    * Go to **Permissions** -> **Cross-origin resource sharing (CORS)**.
    * Paste this configuration:
    ```json
    [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
            "AllowedOrigins": ["*"],
            "ExposeHeaders": []
        }
    ]
    ```

---

### 2. EC2 Instance Setup

1.  **Launch Instance**
    * **Important:** In Security Group settings, allow **SSH (22)**, **HTTP (80)**, and **HTTPS (443)** from anywhere (`0.0.0.0/0`).
    * **IAM Role:** Select `LabInstanceProfile` so the app can talk to S3.

2.  **Prepare Server**
    * SSH into your instance:
        ```bash
        ssh -i your-key.pem ec2-user@your-ip-address
        ```
    * Install Git:
        ```bash
        sudo yum install git -y
        ```
    * Clone your repository:
        ```bash
        git clone <your-repo-url>
        cd <repo-folder>
        ```

3.  **Configure Environment**
    * Create the `.env` file:
        ```bash
        nano .env
        ```
    * Paste your configuration:
        ```ini
        # --- Flask Settings ---
        FLASK_SECRET=<secret key>
        PORT=8000
        FLASK_DEBUG=1

        # --- Redis Settings ---
        REDIS_URL=redis://localhost:6379/0

        # --- S3 Settings ---
        AWS_S3_BUCKET_NAME=<your-bucket-name>
        AWS_REGION=us-east-1
        ```

---

### 3. Domain Registration (Required for HTTPS)


     Run the registration:
    ```bash
    ./register_ip.sh
    ```

---

### 4. Deploy Application

1.  **Update Domain in Script**
    * Open `deploy.sh`:
        ```bash
        nano deploy.sh
        ```
    * Change the `DOMAIN` variable at the top to match your specific domain:
        ```bash
        DOMAIN=<"your domain">
        ```

2.  **Run Deployment**
    ```bash
    ./deploy.sh
    ```
    *This will install Redis, Nginx, Python, and start the app on HTTP.*

---

### 5. Enable HTTPS (SSL)

To get the secure green lock icon, run these commands **once** after deploying:

1.  **Request Certificate**
    ```bash
    sudo dnf install certbot python3-certbot-nginx -y
    sudo certbot --nginx
    ```
2.  **Follow Prompts**
    * Enter your email.
    * Agree to terms (`Y`).
    * Select your domain name (Press `Enter`).

Your site is now secure! The `deploy.sh` script is smart enough to preserve these settings on future updates.

