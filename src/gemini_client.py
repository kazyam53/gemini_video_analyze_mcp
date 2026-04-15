import logging
import time
import uuid
from pathlib import Path

from google import genai
from google.cloud import storage
from google.genai import types
from google.oauth2 import service_account

from .config import (
    GCS_BUCKET_NAME,
    GEMINI_API_KEY,
    GEMINI_PROJECT_ID,
    GEMINI_PROJECT_LOCATION,
    GOOGLE_APPLICATION_CREDENTIALS,
    INLINE_SIZE_LIMIT,
    VIDEO_MIME_TYPES,
)

logger = logging.getLogger(__name__)


def create_client() -> tuple[genai.Client, bool, service_account.Credentials | None]:
    """認証方法を自動判定してGeminiクライアントを生成する。

    Returns:
        (client, is_vertex_ai, credentials) のタプル。
        credentialsはVertex AI時のみ返る（GCSクライアント流用のため）。
    """
    if GEMINI_API_KEY:
        return genai.Client(api_key=GEMINI_API_KEY), False, None

    if GOOGLE_APPLICATION_CREDENTIALS and GEMINI_PROJECT_ID:
        credentials_obj = service_account.Credentials.from_service_account_file(
            GOOGLE_APPLICATION_CREDENTIALS,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return (
            genai.Client(
                vertexai=True,
                project=GEMINI_PROJECT_ID,
                location=GEMINI_PROJECT_LOCATION,
                credentials=credentials_obj,
            ),
            True,
            credentials_obj,
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


def _delete_file_quietly(client: genai.Client, file_name: str) -> None:
    """アップロード済みファイルを削除する。失敗してもログのみ。"""
    try:
        client.files.delete(name=file_name)
    except Exception:
        logger.warning("アップロードファイルの削除に失敗: %s", file_name)


def _upload_video(client: genai.Client, video_path: Path, mime_type: str) -> types.File:
    """File APIで動画をアップロードし、処理完了まで待つ。"""
    uploaded_file = client.files.upload(
        file=str(video_path), config={"mime_type": mime_type}
    )

    timeout = 300
    elapsed = 0
    try:
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
    except Exception:
        _delete_file_quietly(client, uploaded_file.name)
        raise

    return uploaded_file


def _upload_to_gcs(
    credentials: service_account.Credentials,
    video_path: Path,
    mime_type: str,
) -> tuple[str, storage.Blob]:
    """動画をGCSバケットにアップロードし、(gs:// URI, blob) を返す。"""
    if not GCS_BUCKET_NAME:
        raise RuntimeError(
            "Vertex AIモードで大容量動画を扱うには GCS_BUCKET_NAME の設定が必要です"
        )

    storage_client = storage.Client(project=GEMINI_PROJECT_ID, credentials=credentials)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob_name = f"gemini-video-analyze-mcp/{uuid.uuid4()}_{video_path.name}"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(str(video_path), content_type=mime_type)
    gcs_uri = f"gs://{GCS_BUCKET_NAME}/{blob_name}"
    return gcs_uri, blob


def analyze_video(
    client: genai.Client,
    video_path: str,
    prompt: str,
    model: str,
    *,
    is_vertex_ai: bool = False,
    credentials: service_account.Credentials | None = None,
) -> str:
    """動画を解析してテキスト結果を返す。

    解析後のリモート側動画（Gemini Developer APIのFile API上、
    またはVertex AIモード時のGCS上）は意図的に削除しません。
    再利用の余地を残すためです。詳細な寿命・課金・推奨クリーンアップ方法は
    README を参照してください。
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

    mime_type = _get_mime_type(path)
    file_size = path.stat().st_size
    is_large = file_size > INLINE_SIZE_LIMIT

    if not is_large:
        video_part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
        response = client.models.generate_content(
            model=model,
            contents=[prompt, video_part],
        )
    elif is_vertex_ai:
        if credentials is None:
            raise RuntimeError(
                "Vertex AIモードで大容量動画を扱うには credentials が必要です"
            )
        gcs_uri, _blob = _upload_to_gcs(credentials, path, mime_type)
        video_part = types.Part.from_uri(file_uri=gcs_uri, mime_type=mime_type)
        response = client.models.generate_content(
            model=model,
            contents=[prompt, video_part],
        )
    else:
        uploaded = _upload_video(client, path, mime_type)
        response = client.models.generate_content(
            model=model,
            contents=[prompt, uploaded],
        )

    if not response.text:
        raise RuntimeError(
            "Gemini APIからテキスト応答が得られませんでした（安全フィルタ等の可能性）"
        )
    return response.text
