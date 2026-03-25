import logging
from typing import Annotated

from google import genai
from mcp.server.fastmcp import FastMCP

from .config import DEFAULT_MODEL, GEMINI_MODELS
from .gemini_client import analyze_video as _analyze_video
from .gemini_client import create_client

logger = logging.getLogger(__name__)

mcp = FastMCP(name="gemini-video-analyze")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = create_client()
    return _client


@mcp.tool()
def analyze_video(
    video_path: Annotated[str, "解析する動画ファイルの絶対パス"],
    prompt: Annotated[str, "動画に対する解析指示テキスト"],
    model: Annotated[
        str,
        f"使用するGeminiモデル。選択肢: {', '.join(GEMINI_MODELS)}",
    ] = DEFAULT_MODEL,
) -> str:
    """Gemini APIを使用して動画ファイルを解析します。

    動画ファイルとプロンプトを指定すると、Geminiモデルが動画の内容を分析し、
    指示に基づいたテキスト回答を返します。
    対応フォーマット: mp4, mov, avi, webm, mkv, flv, wmv, m4v, 3gp
    """
    if model not in GEMINI_MODELS:
        return f"エラー: 未対応のモデルです。対応モデル: {', '.join(GEMINI_MODELS)}"

    try:
        return _analyze_video(
            client=_get_client(),
            video_path=video_path,
            prompt=prompt,
            model=model,
        )
    except Exception:
        logger.exception("動画解析エラー")
        raise


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
