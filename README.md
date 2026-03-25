# gemini-video-analyze-mcp

Gemini APIを使用して動画ファイルを解析するMCPサーバーです。

## 機能

- 動画ファイルとプロンプトを指定してGemini APIで解析
- モデル選択可能（デフォルト: `gemini-2.5-flash`）
- 小動画（<20MB）はインライン送信、大動画はFile API経由で自動切り替え
- 対応フォーマット: mp4, mov, avi, webm, mkv, flv, wmv, m4v, 3gp

## インストール

### Claude Code から直接インストール

```bash
claude mcp add gemini-video-analyze -- uv run --directory /path/to/gemini_video_analyze_mcp gemini-video-analyze-mcp
```

### Git URL からインストール

```bash
git clone <repository-url> /path/to/gemini_video_analyze_mcp
cd /path/to/gemini_video_analyze_mcp
uv sync
```

その後 Claude Code に登録:

```bash
claude mcp add gemini-video-analyze -- uv run --directory /path/to/gemini_video_analyze_mcp gemini-video-analyze-mcp
```

### settings.json で設定する場合

`~/.claude/settings.json` に以下を追加:

```json
{
  "mcpServers": {
    "gemini-video-analyze": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/gemini_video_analyze_mcp", "gemini-video-analyze-mcp"],
      "env": {
        "GEMINI_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `GEMINI_API_KEY` | ※1 | Gemini API キー |
| `GOOGLE_APPLICATION_CREDENTIALS` | ※2 | サービスアカウントJSONファイルのパス |
| `GEMINI_PROJECT_ID` | ※2 | Google Cloud プロジェクトID |
| `GEMINI_PROJECT_LOCATION` | No | リージョン（デフォルト: `us-central1`） |

※1 APIキー認証の場合に必須
※2 Vertex AI認証の場合に必須（`GEMINI_API_KEY` が未設定時に使用）

## MCPツール

### `analyze_video`

動画ファイルをGemini APIで解析します。

**パラメータ:**

| 名前 | 型 | 必須 | デフォルト | 説明 |
|------|------|------|-----------|------|
| `video_path` | string | Yes | - | 動画ファイルの絶対パス |
| `prompt` | string | Yes | - | 解析指示テキスト |
| `model` | string | No | `gemini-2.5-flash` | 使用するGeminiモデル |

**対応モデル:**

- `gemini-3.1-pro-preview`
- `gemini-3.1-flash-lite-preview`
- `gemini-3-pro-preview`
- `gemini-3-flash-preview`
- `gemini-2.5-pro`
- `gemini-flash-latest`
- `gemini-2.5-flash`
- `gemini-2.5-flash-lite`

## 開発

```bash
# 依存関係インストール
uv sync

# サーバー起動
uv run gemini-video-analyze-mcp

# フォーマット・リント
uv run ruff format .
uv run ruff check . --fix
```
