import hashlib
import logging
import time
from pathlib import Path

from google import genai
from google.api_core import exceptions as google_exceptions
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
        try:
            credentials_obj = service_account.Credentials.from_service_account_file(
                GOOGLE_APPLICATION_CREDENTIALS,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"サービスアカウントJSONが見つかりません: {GOOGLE_APPLICATION_CREDENTIALS}。"
                " GOOGLE_APPLICATION_CREDENTIALS のパスを確認してください。"
            ) from e
        except ValueError as e:
            raise RuntimeError(
                f"サービスアカウントJSONの読み込みに失敗しました: {GOOGLE_APPLICATION_CREDENTIALS}。"
                f" ファイル内容が不正な可能性があります: {e}"
            ) from e
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

    # Vertex AIモードの部分設定を検出して具体的な案内を出す
    if GOOGLE_APPLICATION_CREDENTIALS and not GEMINI_PROJECT_ID:
        raise RuntimeError(
            "Vertex AIモードには GOOGLE_APPLICATION_CREDENTIALS と GEMINI_PROJECT_ID の両方が必要です。"
            " 現在 GEMINI_PROJECT_ID が未設定です。"
        )
    if GEMINI_PROJECT_ID and not GOOGLE_APPLICATION_CREDENTIALS:
        raise RuntimeError(
            "Vertex AIモードには GOOGLE_APPLICATION_CREDENTIALS と GEMINI_PROJECT_ID の両方が必要です。"
            " 現在 GOOGLE_APPLICATION_CREDENTIALS が未設定です。"
        )

    raise RuntimeError(
        "認証情報が設定されていません。"
        " Gemini Developer API を使う場合は GEMINI_API_KEY を、"
        " Vertex AI を使う場合は GOOGLE_APPLICATION_CREDENTIALS と GEMINI_PROJECT_ID を設定してください。"
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


def _compute_file_hash(video_path: Path) -> str:
    """動画ファイルのSHA256ハッシュ先頭16文字をストリーミング計算する。"""
    hasher = hashlib.sha256()
    with video_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def _upload_to_gcs(
    credentials: service_account.Credentials,
    video_path: Path,
    mime_type: str,
) -> tuple[str, storage.Blob, bool]:
    """動画をGCSバケットにアップロードし、(gs:// URI, blob, is_newly_uploaded) を返す。

    Blob名は内容ハッシュベースで決定論的に決まるため、同一内容の動画を
    再解析する際はアップロードをスキップして既存Blobを再利用する。

    Returns:
        gcs_uri: `gs://bucket/path` 形式のURI
        blob: Blobオブジェクト（失敗時クリーンアップで使用する場合あり）
        is_newly_uploaded: 今回新規にアップロードした場合はTrue、既存Blobを再利用した場合はFalse
    """
    if not GCS_BUCKET_NAME:
        raise RuntimeError(
            "Vertex AIモードで約19MiB超の動画を扱うには GCS_BUCKET_NAME の設定が必要です。"
            " `.claude.json` の env に GCS_BUCKET_NAME=<bucket-name> を追加してください。"
        )

    try:
        storage_client = storage.Client(
            project=GEMINI_PROJECT_ID, credentials=credentials
        )
        bucket = storage_client.bucket(GCS_BUCKET_NAME)

        digest = _compute_file_hash(video_path)
        blob_name = f"gemini-video-analyze-mcp/{digest}_{video_path.name}"
        blob = bucket.blob(blob_name)
        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{blob_name}"

        if blob.exists():
            logger.info("GCS上に既存の動画を再利用: %s", gcs_uri)
            return gcs_uri, blob, False

        logger.info("GCSへアップロード開始: %s", gcs_uri)
        blob.upload_from_filename(str(video_path), content_type=mime_type)
        logger.info("GCSへアップロード完了: %s", gcs_uri)
        return gcs_uri, blob, True
    except google_exceptions.Forbidden as e:
        raise RuntimeError(
            f"GCSバケット `{GCS_BUCKET_NAME}` へのアクセスが拒否されました。"
            " サービスアカウントに `roles/storage.objectAdmin`（または"
            " `objectCreator`/`objectViewer`/`objectUser`）が付与されているか確認してください。"
        ) from e
    except google_exceptions.NotFound as e:
        raise RuntimeError(
            f"GCSバケット `{GCS_BUCKET_NAME}` が見つかりません。"
            " バケットが存在し、GEMINI_PROJECT_ID と同じプロジェクトにあることを確認してください。"
        ) from e


def _delete_blob_quietly(blob: storage.Blob) -> None:
    """GCS上のBlobを削除する。失敗してもログのみ。"""
    try:
        blob.delete()
    except Exception:
        logger.warning("GCS上の動画削除に失敗: %s", blob.name)


def delete_uploaded_video_from_gcs(
    credentials: service_account.Credentials,
    video_path: str,
) -> str:
    """指定ローカル動画のハッシュからGCS上のBlobを特定して削除する。

    意図しない削除を防ぐため、削除対象は _upload_to_gcs と同じ決定論的Blob名
    （`gemini-video-analyze-mcp/{sha256先頭16桁}_{ファイル名}`）に限定する。
    ローカルファイルの内容が過去にアップロードしたものと一致する場合のみBlobが
    ヒットし、削除される。
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

    file_size = path.stat().st_size
    if file_size <= INLINE_SIZE_LIMIT:
        return (
            f"インラインサイズ（{file_size}バイト ≤ {INLINE_SIZE_LIMIT}バイト）のため"
            " GCSへはアップロードされていません。削除対象はありません。"
        )

    if not GCS_BUCKET_NAME:
        raise RuntimeError(
            "GCS_BUCKET_NAME が未設定です。削除対象バケットを特定できません。"
        )

    _get_mime_type(path)

    try:
        storage_client = storage.Client(
            project=GEMINI_PROJECT_ID, credentials=credentials
        )
        bucket = storage_client.bucket(GCS_BUCKET_NAME)

        digest = _compute_file_hash(path)
        blob_name = f"gemini-video-analyze-mcp/{digest}_{path.name}"
        blob = bucket.blob(blob_name)
        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{blob_name}"

        if not blob.exists():
            return (
                f"同一ハッシュのBlobが見つかりませんでした: {gcs_uri}。"
                " 既に削除済み、または別の内容/名前でアップロードされた可能性があります。"
            )

        blob.delete()
        logger.info("GCS上の動画を削除: %s", gcs_uri)
        return f"GCS上の動画を削除しました: {gcs_uri}"
    except google_exceptions.Forbidden as e:
        raise RuntimeError(
            f"GCSバケット `{GCS_BUCKET_NAME}` への削除権限がありません。"
            " サービスアカウントに `roles/storage.objectAdmin` または"
            " `objectUser` が付与されているか確認してください。"
        ) from e
    except google_exceptions.NotFound as e:
        raise RuntimeError(f"GCSバケット `{GCS_BUCKET_NAME}` が見つかりません。") from e


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
                "Vertex AIモードで約19MiB超の動画を扱うには Google Cloud の認証設定が必要です。"
                " GOOGLE_APPLICATION_CREDENTIALS と GEMINI_PROJECT_ID を確認してください。"
            )
        gcs_uri, blob, is_newly_uploaded = _upload_to_gcs(credentials, path, mime_type)
        try:
            video_part = types.Part.from_uri(file_uri=gcs_uri, mime_type=mime_type)
            response = client.models.generate_content(
                model=model,
                contents=[prompt, video_part],
            )
        except Exception:
            if is_newly_uploaded:
                _delete_blob_quietly(blob)
            raise
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
