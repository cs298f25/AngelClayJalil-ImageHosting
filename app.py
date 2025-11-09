from __future__ import annotations
import os, time, uuid, redis
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, url_for
from itsdangerous import URLSafeSerializer
from werkzeug.utils import secure_filename

# --- Setup ---
load_dotenv()
app = Flask(__name__)

# --- Configure an upload folder ---
# Create an 'uploads' folder in your project
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "dev-secret")
signer = URLSafeSerializer(app.config["SECRET_KEY"], salt="api-key")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.from_url(REDIS_URL, decode_responses=True)

# --- Helper functions ---
def now(): return int(time.time())
def ok(payload, status=200): return jsonify(payload), status
def err(code, message, status): return jsonify({"error": {"code": code, "message": message}}), status
def k_user(uid): return f"user:{uid}"
def k_user_images(uid): return f"user:{uid}:images"
def k_img(iid): return f"img:{iid}"

# --- Serve static files (HTML, CSS, JS) ---
@app.get("/")
def serve_index():
    root = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(root, "index.html")

@app.get("/script.js")
def serve_script():
    root = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(root, "script.js")

@app.get("/style.css")
def serve_style():
    root = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(root, "style.css")

# --- NEW: Create a route to serve uploaded files ---
@app.get('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.get("/health")
def health_check():
    return ok({"status": "ok"})

# --- Redis test routes ---
@app.get("/redis-check")
def redis_check():
    try:
        return ok({"redis": bool(r.ping())})
    except Exception as e:
        return err("redis_unreachable", str(e), 500)

# --- Authentication helper ---
def require_api_key():
    token = (request.headers.get("X-API-Key") or "").strip()
    if not token:
        return None
    try:
        return signer.loads(token)
    except Exception:
        return None

# --- Create a dev API key ---
@app.post("/api/v1/dev/issue-key")
def issue_key():
    username = (request.json or {}).get("username", "demo").strip() or "demo"
    uid = f"u_{username}"
    r.hsetnx(k_user(uid), "username", username)
    r.hset(k_user(uid), mapping={"uid": uid, "created_at": now()})
    token = signer.dumps({"uid": uid})
    return ok({"api_key": token, "uid": uid})

# --- NEW: Local Upload Endpoint ---
@app.post("/api/v1/upload")
def upload_local():
    auth = require_api_key()
    if not auth:
        return err("auth", "invalid api key", 401)
    
    uid = auth["uid"]

    if 'file' not in request.files:
        return err("validation", "No file part", 400)
    
    file = request.files['file']
    if file.filename == '':
        return err("validation", "No selected file", 400)

    if file:
        # Create a unique-ish filename
        filename = secure_filename(file.filename)
        ext = filename.split('.')[-1] if '.' in filename else ''
        iid = f"img_{uuid.uuid4().hex[:12]}"
        new_filename = f"{iid}.{ext}" if ext else iid
        
        # Save the file
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        file.save(save_path)
        
        # Get the URL where the file is served
        img_url = url_for('serve_upload', filename=new_filename, _external=True)
        
        # Save metadata to Redis
        pipe = r.pipeline()
        pipe.hset(k_img(iid), mapping={
            "id": iid,
            "owner_uid": uid,
            "key": new_filename, # Store the local filename
            "url": img_url,
            "filename": filename, # Original filename
            "mime": file.mimetype,
            "private": 0,
            "created_at": now(),
            "views": 0
        })
        pipe.zadd(k_user_images(uid), {iid: now()})
        pipe.execute()

        return ok({"id": iid, "url": img_url}, 201)

# --- List all images for a user ---
@app.get("/api/v1/me/images")
def me_images():
    auth = require_api_key()
    if not auth:
        return err("auth", "invalid api key", 401)
    uid = auth["uid"]
    iids = r.zrevrange(k_user_images(uid), 0, 49)
    items = []
    
    pipe = r.pipeline()
    for iid in iids:
        pipe.hgetall(k_img(iid))
    results = pipe.execute()
    
    for data in results:
        if data:
            items.append(data)
            
    return ok({"items": items})

# --- Run the app ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)