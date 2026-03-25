import time
from pathlib import Path

from google import genai
from google.genai import types
from google.oauth2 import service_account

from .config import (
    GEMINI_API_KEY,
    GEMINI_PROJECT_ID,
    GEMINI_PROJECT_LOCATION,
    GOOGLE_APPLICATION_CREDENTIALS,
    INLINE_SIZE_LIMIT,
    VIDEO_MIME_TYPES,
)


def create_client() -> genai.Client:
    """認証方法を自動判定してGeminiクライアントを生成する。"""
    if GEMINI_API_KEY:
        return genai.Client(api_key=GEMINI_API_KEY)

    if GOOGLE_APPLICATION_CREDENTIALS and GEMINI_PROJECT_ID:
        credentials_obj = service_account.Credentials.from_service_account_file(
            GOOGLE_APPLICATION_CREDENTIALS,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return genai.Client(
            vertexai=True,
            project=GEMINI_PROJECT_ID,
            location=GEMINI_PROJECT_LOCATION,
            credentials=credentials_obj,
        )

    raise RuntimeError(
        "GEMINI_API_KEY または GOOGLE_APPLICATION_CREDENTIALS + GEMINI_PROJECT_ID を設定してください"
    )


def _get_mime_type(video_path: Path) -> str:
    """拡張子からMIME typeを取得する。"""
    suffix = video_path.suffix.lower()
    mime_type = VIDEO_MIME_TYPES.get(suffix)
    if not mime_type:
        supported = ", ".join(VIDEO_MIME_TYPES.keys())
        raise ValueError(f"未対応の動画フォーマット: {suffix} (対応: {supported})")
    return mime_type


def _upload_video(client: genai.Client, video_path: Path, mime_type: str) -> types.File:
    """File APIで動画をアップロードし、処理完了まで待つ。"""
    uploaded_file = client.files.upload(
        file=str(video_path), config={"mime_type": mime_type}
    )

    timeout = 300
    elapsed = 0
    while uploaded_file.state.name == "PROCESSING":
        if elapsed >= timeout:
            raise TimeoutError(
                f"動画のアップロード処理がタイムアウトしました ({timeout}秒)"
            )
        time.sleep(2)
        elapsed += 2
        uploaded_file = client.files.get(name=uploaded_file.name)

    if uploaded_file.state.name == "FAILED":
        raise RuntimeError("動画のアップロード処理に失敗しました")

    return uploaded_file


def analyze_video(
    client: genai.Client,
    video_path: str,
    prompt: str,
    model: str,
) -> str:
    """動画を解析してテキスト結果を返す。"""
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

    mime_type = _get_mime_type(path)
    file_size = path.stat().st_size

    if file_size <= INLINE_SIZE_LIMIT:
        video_part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
        response = client.models.generate_content(
            model=model,
            contents=[prompt, video_part],
        )
    else:
        uploaded = _upload_video(client, path, mime_type)
        try:
            response = client.models.generate_content(
                model=model,
                contents=[prompt, uploaded],
            )
        finally:
            client.files.delete(name=uploaded.name)

    if not response.text:
        raise RuntimeError(
            "Gemini APIからテキスト応答が得られませんでした（安全フィルタ等の可能性）"
        )
    return response.text
