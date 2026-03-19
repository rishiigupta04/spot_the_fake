from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os, sys, traceback
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
import tempfile

# Ensure project root is on path so we can import app1/app2
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

app = Flask(__name__)
CORS(app)

# Places to store uploads
USER_FOLDER = os.getenv("USER_FOLDER") or os.path.join(tempfile.gettempdir(), "spot-the-fake-user")
os.makedirs(USER_FOLDER, exist_ok=True)

# Lazy import of your existing modules. Import errors will be returned by /health
try:
    from app2 import classify_content
    from app2 import classify_url_fast
    from app2 import get_llm_status
    from app1 import check_website
    _IMPORT_ERROR = None
except Exception as e:
    classify_content = None
    classify_url_fast = None
    get_llm_status = None
    check_website = None
    _IMPORT_ERROR = traceback.format_exc()

# Try to import model loader (optional)
try:
    from backend.models import loader as model_loader
    _LOADER_ERROR = None
except Exception:
    model_loader = None
    _LOADER_ERROR = traceback.format_exc()


def _error_response(code, message, status=400, details=None):
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status


def _normalize_url(raw_value):
    if not isinstance(raw_value, str):
        return None

    raw_value = raw_value.strip()
    if not raw_value:
        return None

    if "://" not in raw_value:
        raw_value = f"https://{raw_value}"

    parsed = urlparse(raw_value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return raw_value


def _cloudinary_status():
    has_cloud_name = bool(os.getenv("CLOUDINARY_CLOUD_NAME"))
    has_api_key = bool(os.getenv("CLOUDINARY_API_KEY"))
    has_api_secret = bool(os.getenv("CLOUDINARY_API_SECRET"))
    configured = has_cloud_name and has_api_key and has_api_secret
    return {
        "configured": configured,
        "cloud_name_set": has_cloud_name,
        "api_key_set": has_api_key,
        "api_secret_set": has_api_secret,
    }


@app.route("/health", methods=["GET"])
def health():
    """Simple health check"""
    llm_status = get_llm_status() if get_llm_status else None
    return jsonify({
        "status": "ok",
        "imports": "ok" if _IMPORT_ERROR is None else "error",
        "import_error": None if _IMPORT_ERROR is None else _IMPORT_ERROR,
        "loader": "ok" if _LOADER_ERROR is None else "error",
        "loader_error": None if _LOADER_ERROR is None else _LOADER_ERROR,
        "llm": llm_status,
        "cloudinary": _cloudinary_status(),
        "user_folder": USER_FOLDER,
    })


@app.route("/model-info", methods=["GET"])
def model_info():
    """Return basic info about the pickled ML package (if available)"""
    if model_loader is None:
        return jsonify({"error": "Model loader not available", "details": _LOADER_ERROR}), 500
    try:
        info = model_loader.get_model_info()
        return jsonify({"success": True, "info": info})
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/predict", methods=["POST"])
def predict():
    """POST /predict
    JSON body: {"url": "https://..."}
    Returns: JSON result from classify_content
    """
    if _IMPORT_ERROR:
        return _error_response("BACKEND_IMPORT_FAILURE", "Backend import failure", status=500, details=_IMPORT_ERROR)

    data = request.get_json(silent=True)
    if not data:
        return _error_response("INVALID_REQUEST", "Missing JSON body", status=400)

    normalized_url = _normalize_url(data.get("url") or data.get("text"))
    if not normalized_url:
        return _error_response("INVALID_URL", "Provide a valid URL (http/https)", status=400)

    try:
        result = classify_content(normalized_url)
        if isinstance(result, dict) and result.get("error"):
            return _error_response("PREDICTION_FAILED", result.get("error"), status=502)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        tb = traceback.format_exc()
        return _error_response("PREDICTION_EXCEPTION", str(e), status=500, details=tb)


@app.route("/predict-lite", methods=["POST"])
def predict_lite():
    """POST /predict-lite
    JSON body: {"url": "https://..."}
    Returns: fast ML-only URL risk result
    """
    if _IMPORT_ERROR:
        return _error_response("BACKEND_IMPORT_FAILURE", "Backend import failure", status=500, details=_IMPORT_ERROR)

    data = request.get_json(silent=True)
    if not data:
        return _error_response("INVALID_REQUEST", "Missing JSON body", status=400)

    normalized_url = _normalize_url(data.get("url") or data.get("text"))
    if not normalized_url:
        return _error_response("INVALID_URL", "Provide a valid URL (http/https)", status=400)

    try:
        result = classify_url_fast(normalized_url)
        if isinstance(result, dict) and result.get("error"):
            return _error_response("PREDICTION_FAILED", result.get("error"), status=502)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        tb = traceback.format_exc()
        return _error_response("PREDICTION_EXCEPTION", str(e), status=500, details=tb)


@app.route("/similarity", methods=["POST"])
def similarity():
    """POST /similarity
    JSON body: {"url": "https://..."}
    Returns: JSON result from check_website
    """
    if _IMPORT_ERROR:
        return _error_response("BACKEND_IMPORT_FAILURE", "Backend import failure", status=500, details=_IMPORT_ERROR)

    data = request.get_json(silent=True)
    if not data:
        return _error_response("INVALID_REQUEST", "Missing JSON body", status=400)

    normalized_url = _normalize_url(data.get("url"))
    if not normalized_url:
        return _error_response("INVALID_URL", "Provide a valid URL (http/https)", status=400)

    try:
        result = check_website(normalized_url)
        if result is None:
            return _error_response("SIMILARITY_UNAVAILABLE", "Similarity analysis unavailable for this URL", status=422)
        if isinstance(result, dict) and result.get("error"):
            return _error_response("SIMILARITY_FAILED", result.get("error"), status=502)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        tb = traceback.format_exc()
        return _error_response("SIMILARITY_EXCEPTION", str(e), status=500, details=tb)


# New endpoint: upload an image file for similarity checking
@app.route("/similarity-upload", methods=["POST"])
def similarity_upload():
    """Accepts multipart/form-data with a file field 'file'. Saves file to User/ and runs check_website on it.
    Returns similarity result JSON.
    """
    if _IMPORT_ERROR:
        return _error_response("BACKEND_IMPORT_FAILURE", "Backend import failure", status=500, details=_IMPORT_ERROR)

    if 'file' not in request.files:
        return _error_response("INVALID_REQUEST", "No file part in request", status=400)

    file = request.files['file']
    if file.filename == '':
        return _error_response("INVALID_REQUEST", "No selected file", status=400)

    filename = secure_filename(file.filename)
    save_path = os.path.join(USER_FOLDER, filename)
    try:
        file.save(save_path)
        # call check_website with local file path
        result = check_website(save_path)
        if result is None:
            return _error_response("SIMILARITY_UNAVAILABLE", "Similarity analysis unavailable for this image", status=422)
        if isinstance(result, dict) and result.get("error"):
            return _error_response("SIMILARITY_FAILED", result.get("error"), status=502)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        tb = traceback.format_exc()
        return _error_response("SIMILARITY_EXCEPTION", str(e), status=500, details=tb)


@app.route('/static/brands/<path:filename>')
def serve_brand_image(filename):
    brands_dir = os.path.join(ROOT, 'Brands')
    return send_from_directory(brands_dir, filename)

@app.route('/static/user/<path:filename>')
def serve_user_image(filename):
    return send_from_directory(USER_FOLDER, filename)


if __name__ == "__main__":
    # Run Flask app on port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)