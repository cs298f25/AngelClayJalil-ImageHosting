How to deploy:

--- S3 Bucket Setup ---

Create an S3 Bucket with Public Access

Add this policy to the bucket
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadUploads",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::imagehostingbucketal/uploads/*"
        }
    ]
}
```
```
Add this CORS Configuration
[
    {
        "AllowedHeaders": [
            "*"
        ],
        "AllowedMethods": [
            "GET",
            "PUT",
            "POST",
            "DELETE"
        ],
        "AllowedOrigins": [
            "*"
        ],
        "ExposeHeaders": []
    }
]
```
---  EC2 Instance Setup ---

Create an EC2 Instance with HTTP and HTTPS enabled
    
- Make sure to Launch EC2 Instance with the LabInstanceProfile 

SSH into the EC2 Instance

Install Git

Clone the Repository

Set up the .env file as shown
```
# --- Flask Settings ---
FLASK_SECRET=<secret key>
PORT=8000
FLASK_DEBUG=1

# --- Redis Settings ---
REDIS_URL=redis://localhost:6379/0

# --- S3 Settings ---
AWS_S3_BUCKET_NAME=<bucket-name>
AWS_REGION=<aws-region>
```
Activate the Deploy Script and the Application is running! (You can check the app.log folder to verify)

When done with the application, run the down script to terminate it. 
