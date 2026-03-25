import logging
from typing import Annotated

from google import genai
from mcp.server.fastmcp import FastMCP

from .config import DEFAULT_MODEL, RECOMMENDED_MODELS
from .gemini_client import analyze_video as _analyze_video
from .gemini_client import create_client

logger = logging.getLogger(__name__)

mcp = FastMCP(name="gemini-video-analyze")

_client: genai.Client | None = None
_is_vertex_ai: bool = False


def _get_client() -> tuple[genai.Client, bool]:
    global _client, _is_vertex_ai
    if _client is None:
        _client, _is_vertex_ai = create_client()
    return _client, _is_vertex_ai


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
        client, is_vertex = _get_client()
        return _analyze_video(
            client=client,
            video_path=video_path,
            prompt=prompt,
            model=model,
            is_vertex_ai=is_vertex,
        )
    except Exception:
        logger.exception("動画解析エラー")
        raise


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
