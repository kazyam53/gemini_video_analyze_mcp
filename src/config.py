import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GEMINI_PROJECT_ID = os.getenv("GEMINI_PROJECT_ID")
GEMINI_PROJECT_LOCATION = os.getenv("GEMINI_PROJECT_LOCATION", "us-central1")

DEFAULT_MODEL = "gemini-2.5-flash"

GEMINI_MODELS = [
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".flv": "video/x-flv",
    ".wmv": "video/x-ms-wmv",
    ".m4v": "video/mp4",
    ".3gp": "video/3gpp",
}

# File APIを使うファイルサイズ閾値 (20MB)
INLINE_SIZE_LIMIT = 20 * 1024 * 1024
