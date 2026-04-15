import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GEMINI_PROJECT_ID = os.getenv("GEMINI_PROJECT_ID")
GEMINI_PROJECT_LOCATION = os.getenv("GEMINI_PROJECT_LOCATION", "us-central1")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

DEFAULT_MODEL = "gemini-3-flash-preview"

# 推奨モデル一覧（ツールのdescriptionに表示用、バリデーションには使わない）
RECOMMENDED_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
]

VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/avi",
    ".webm": "video/webm",
    ".flv": "video/x-flv",
    ".wmv": "video/wmv",
    ".m4v": "video/mp4",
    ".3gp": "video/3gpp",
}

IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}

# File APIを使うファイルサイズ閾値 (promptサイズの余裕を考慮して19MB)
INLINE_SIZE_LIMIT = 19 * 1024 * 1024
