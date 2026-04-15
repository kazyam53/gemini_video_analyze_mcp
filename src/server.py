import logging
from typing import Annotated

from google import genai
from google.oauth2 import service_account
from mcp.server.fastmcp import FastMCP

from .config import DEFAULT_MODEL, RECOMMENDED_MODELS
from .gemini_client import analyze_video as _analyze_video
from .gemini_client import create_client
from .gemini_client import delete_uploaded_video_from_gcs as _delete_uploaded_video

logger = logging.getLogger(__name__)

mcp = FastMCP(name="gemini-video-analyze")

_client: genai.Client | None = None
_is_vertex_ai: bool = False
_credentials: service_account.Credentials | None = None


def _get_client() -> tuple[genai.Client, bool, service_account.Credentials | None]:
    global _client, _is_vertex_ai, _credentials
    if _client is None:
        _client, _is_vertex_ai, _credentials = create_client()
    return _client, _is_vertex_ai, _credentials


@mcp.tool()
def analyze_video(
    video_path: Annotated[str, "解析する動画ファイルの絶対パス"],
    prompt: Annotated[str, "動画に対する解析指示テキスト"],
    model: Annotated[
        str,
        f"使用するGeminiモデル名。推奨: {', '.join(RECOMMENDED_MODELS)}",
    ] = DEFAULT_MODEL,
) -> str:
    """Gemini APIを使用して動画ファイルを解析します。

    動画ファイルとプロンプトを指定すると、Geminiモデルが動画の内容を分析し、
    指示に基づいたテキスト回答を返します。
    対応フォーマット: mp4, mov, avi, webm, flv, wmv, m4v, 3gp
    """
    try:
        client, is_vertex, credentials = _get_client()
        return _analyze_video(
            client=client,
            video_path=video_path,
            prompt=prompt,
            model=model,
            is_vertex_ai=is_vertex,
            credentials=credentials,
        )
    except Exception:
        logger.exception("動画解析エラー")
        raise


@mcp.tool()
def delete_uploaded_video(
    video_path: Annotated[
        str,
        "削除対象のローカル動画ファイルの絶対パス。"
        "このファイルの内容ハッシュとファイル名からGCS上のBlob名を再計算し、"
        "一致するBlobのみ削除する（意図しない削除防止のため）。",
    ],
) -> str:
    """動画解析後のクリーンアップ用途で、GCSにアップロード済みの動画を削除します。

    ユーザから明示的に依頼された場合のみ呼び出してください。
    Vertex AIモード + 約19MiB超の動画のみが対象です（それ以外はアップロードされません）。
    指定ローカルファイルのSHA256ハッシュの先頭16文字を計算し、
    `gemini-video-analyze-mcp/{sha256_16}_{name}` と同一名のBlobが存在する場合のみ削除します。
    """
    try:
        _, is_vertex, credentials = _get_client()
        if not is_vertex or credentials is None:
            raise RuntimeError(
                "この削除機能はVertex AIモード（GOOGLE_APPLICATION_CREDENTIALS +"
                " GEMINI_PROJECT_ID）でのみ利用可能です。"
            )
        return _delete_uploaded_video(
            credentials=credentials,
            video_path=video_path,
        )
    except Exception:
        logger.exception("動画削除エラー")
        raise


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
