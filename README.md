# gemini-video-analyze-mcp

Gemini APIを使用して動画ファイルを解析するMCPサーバーです。

## 機能

- 動画ファイルとプロンプトを指定してGemini APIで解析
- モデル選択可能（デフォルト: `gemini-2.5-flash`）
- 小動画（<20MB）はインライン送信、大動画はFile API経由で自動切り替え
- 対応フォーマット: mp4, mov, avi, webm, flv, wmv, m4v, 3gp

## インストール

### Git URL から直接インストール（推奨）

クローン不要で、GitHub URLを指定するだけでインストールできます:

```bash
claude mcp add gemini-video-analyze -e GEMINI_API_KEY=your-api-key -- uvx --from git+https://github.com/kazyam53/gemini_video_analyze_mcp.git gemini-video-analyze-mcp
```

### ローカルクローンからインストール

```bash
git clone https://github.com/kazyam53/gemini_video_analyze_mcp.git
cd gemini_video_analyze_mcp
uv sync
claude mcp add gemini-video-analyze -- uv run --directory $(pwd) gemini-video-analyze-mcp
```

### settings.json で設定する場合

`~/.claude/settings.json` に以下を追加:

```json
{
  "mcpServers": {
    "gemini-video-analyze": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/kazyam53/gemini_video_analyze_mcp.git", "gemini-video-analyze-mcp"],
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

**推奨モデル:**

- `gemini-2.5-flash`（デフォルト）
- `gemini-2.5-pro`
- `gemini-2.5-flash-lite`

任意のGeminiモデル名を指定できます。

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
