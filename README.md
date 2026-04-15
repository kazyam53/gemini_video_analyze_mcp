# gemini-video-analyze-mcp

Gemini APIを使用して動画ファイルを解析するMCPサーバーです。

## 機能

- 動画ファイルとプロンプトを指定してGemini APIで解析
- モデル選択可能（デフォルト: `gemini-3-flash-preview`）
- 2種類の認証モードをサポート:
  - **Gemini Developer API** (`GEMINI_API_KEY`): 簡易
  - **Vertex AI** (`GOOGLE_APPLICATION_CREDENTIALS` + `GEMINI_PROJECT_ID`): エンタープライズ向け、リージョン指定・監査ログ・DPA対応
- 動画サイズに応じて送信方法を自動切り替え:
  - 小動画（19 MiB 未満）: インライン送信
  - 大動画（Gemini Developer APIモード）: File API経由
  - 大動画（Vertex AIモード）: GCSバケット経由（`GCS_BUCKET_NAME` が必須）
- 対応フォーマット: mp4, mov, avi, webm, flv, wmv, m4v, 3gp

> **注意**: 解析後のリモート側動画（Gemini Developer APIのFile API上、またはVertex AIモード時のGCS上）は**本MCPでは削除しません**。同じ動画に対する再解析を可能にするためです。各モードの寿命・課金・推奨クリーンアップ方法については [リモート側動画の保持について](#リモート側動画の保持について) を参照してください。

## インストール

以下のセットアップ手順は [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 向けです。他のMCPクライアントで使用する場合は、各クライアントの設定方法に従ってください。

### Git URL から直接インストール（推奨）

クローン不要で、GitHub URLを指定するだけでインストールできます。認証モードは2種類から選択します。

**A. Gemini Developer API モード（APIキー認証）**

```bash
claude mcp add gemini-video-analyze -e GEMINI_API_KEY=your-api-key -- uvx --from git+https://github.com/kazyam53/gemini_video_analyze_mcp.git gemini-video-analyze-mcp
```

**B. Vertex AI モード（サービスアカウント認証、東京リージョン例）**

```bash
claude mcp add gemini-video-analyze \
  -e GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json \
  -e GEMINI_PROJECT_ID=your-gcp-project-id \
  -e GEMINI_PROJECT_LOCATION=asia-northeast1 \
  -e GCS_BUCKET_NAME=your-video-bucket \
  -- uvx --from git+https://github.com/kazyam53/gemini_video_analyze_mcp.git gemini-video-analyze-mcp
```

Vertex AIモードでは `GEMINI_API_KEY` を**渡さない**ことで自動的に認証モードが切り替わります。`GCS_BUCKET_NAME` は約19MiB超の動画を扱う場合に必須です。サービスアカウントには `roles/aiplatform.user` + `roles/storage.objectAdmin` の付与が必要です。詳細は [環境変数](#環境変数) セクションを参照してください。

### ローカルクローンからインストール

```bash
git clone https://github.com/kazyam53/gemini_video_analyze_mcp.git
cd gemini_video_analyze_mcp
uv sync
claude mcp add gemini-video-analyze -- uv run --directory $(pwd) gemini-video-analyze-mcp
```

### Claude Code の settings.json で設定する場合

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
| `GEMINI_API_KEY` | ※1 | Gemini Developer API キー |
| `GOOGLE_APPLICATION_CREDENTIALS` | ※2 | サービスアカウントJSONファイルのパス |
| `GEMINI_PROJECT_ID` | ※2 | Google Cloud プロジェクトID |
| `GEMINI_PROJECT_LOCATION` | No | Vertex AI のリージョン（デフォルト: `us-central1`、例: `asia-northeast1`） |
| `GCS_BUCKET_NAME` | ※3 | 大容量動画のアップロード先GCSバケット名（解析後も保持される、バケット名のみ、`gs://` プレフィックス不要） |

※1 Gemini Developer API 認証の場合に必須
※2 Vertex AI 認証の場合に必須（`GEMINI_API_KEY` が未設定時に自動的にVertex AIモードに切り替わる）
※3 Vertex AIモードで約19MiB超の動画を扱う場合に必須。バケットは `GEMINI_PROJECT_LOCATION` と同一リージョンを推奨。サービスアカウントには `roles/storage.objectAdmin` （または最低限 `objectCreator` + `objectViewer` + `objectUser`）を付与すること

### Vertex AIモードの設定例（東京リージョン）

```bash
claude mcp add gemini-video-analyze \
  -e GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json \
  -e GEMINI_PROJECT_ID=your-gcp-project-id \
  -e GEMINI_PROJECT_LOCATION=asia-northeast1 \
  -e GCS_BUCKET_NAME=your-video-bucket \
  -- uvx --from git+https://github.com/kazyam53/gemini_video_analyze_mcp.git gemini-video-analyze-mcp
```

GCSバケットの作成例:

```bash
gcloud storage buckets create gs://your-video-bucket \
  --location=asia-northeast1 \
  --uniform-bucket-level-access
```

### Vertex AI での大容量動画の扱い

Vertex AI の Gemini API は Gemini Developer API と異なり `files.upload()` を提供しないため、約19MiB 超の動画は一度 GCS バケットにアップロードしてから `gs://` URI でモデルに渡す必要があります。本MCPは以下を行います:

1. ローカル動画ファイルのSHA256ハッシュ先頭16文字を計算し、Blob名を `gemini-video-analyze-mcp/<hash>_<filename>` で決定
2. バケット内に同じBlob名が既に存在するか確認
   - **存在する場合**: アップロードをスキップして既存のBlobを再利用（同一内容の再解析でアップロード料金と時間を節約）
   - **存在しない場合**: 新規にアップロード
3. `Part.from_uri` で Gemini に参照させて解析
4. アップロード後の `generate_content` が失敗した場合は、**当該実行でアップロードしたBlobのみ**を削除（既存Blobを再利用したケースでは何も削除しない）

ハッシュは内容ベースで計算されるため、ファイル名を変えても内容が同じなら再利用され、逆に内容が変わればファイル名が同じでも新規アップロードされます。

アップロードしたBlobは**解析後も残したまま**にします（再解析時の再利用のため）。後述のクリーンアップ方法を必ず確認してください。

動画長の上限はモデル依存（Gemini 2.5/3系で最長約2時間、低解像度で最大約6時間）。

## リモート側動画の保持について

本MCPは解析後にリモート側の動画を**削除しません**。同じ動画に対する再解析（モデル・プロンプト違い等）を低コストで行えるようにするためです。ただし各モードで寿命・課金・放置時のリスクが異なるため、以下を把握した上で利用してください。

### Gemini Developer API モード（File API）

約19MiB超の動画がアップロードされるのはGoogle側のFile APIです。

| 項目 | 内容 |
|---|---|
| 自動削除 | **あり**（アップロードから**48時間**後にGoogle側で自動削除） |
| ストレージ料金 | **無料** |
| 容量上限 | プロジェクトあたり **20 GB** |
| 放置時のリスク | **課金の暴走は発生しない**。ただし大量アップロードで20GB上限に達すると新規アップロードが失敗する |
| 手動クリーンアップ | 原則不要。必要なら `client.files.delete(name=...)` または [Files API](https://ai.google.dev/gemini-api/docs/files) を使って削除可能 |

参考: https://ai.google.dev/gemini-api/docs/files

### Vertex AI モード（GCS）

約19MiB超の動画は `GCS_BUCKET_NAME` で指定したGCSバケットにアップロードされます。

| 項目 | 内容 |
|---|---|
| 自動削除 | **なし**（ユーザーが削除またはライフサイクルルールを設定するまで永久に残る） |
| ストレージ料金 | Standard Storage (asia-northeast1) で**約 $0.023/GB/月**が**継続的に**発生 |
| 下り (egress) | Vertex AI と同一リージョンなら**無料**（`asia-northeast1` のバケット+ `asia-northeast1` のVertex AIの組み合わせが推奨） |
| 放置時のリスク | **課金が継続的に増加**。例: 50GB溜めっぱなしで月約 $1.15、年約 $13.80。解析回数が多いプロジェクトではさらに膨らむ |
| 手動クリーンアップ | 後述の**ライフサイクルルール**による自動削除を強く推奨 |

#### 推奨: バケットのライフサイクルルールで自動削除

GCSバケット自体に「N日経過したオブジェクトを自動削除する」ルールを設定できます。これはバケットの属性であり、アップロード側のコードは何も変更不要です。GCS側が定期スキャンで該当オブジェクトを削除します。

本MCPは `gemini-video-analyze-mcp/` プレフィックス配下にオブジェクトを置くので、以下のように**プレフィックス限定**で設定すれば同じバケットを他用途と共有していても安全です。

```bash
cat > lifecycle.json <<'EOF'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 7,
          "matchesPrefix": ["gemini-video-analyze-mcp/"]
        }
      }
    ]
  }
}
EOF

gcloud storage buckets update gs://your-video-bucket --lifecycle-file=lifecycle.json
```

`age` は再利用したい日数に合わせて調整してください（例: 1日、7日、30日）。ライフサイクルルールのスキャン周期は1日1回程度なので、指定した日数より最大1日程度遅れて削除される点に注意してください（リアルタイム削除ではなく、あくまで長期放置を防ぐ保険です）。

参考: https://cloud.google.com/storage/docs/lifecycle

## MCPツール

### `analyze_video`

動画ファイルをGemini APIで解析します。

**パラメータ:**

| 名前 | 型 | 必須 | デフォルト | 説明 |
|------|------|------|-----------|------|
| `video_path` | string | Yes | - | 動画ファイルの絶対パス |
| `prompt` | string | Yes | - | 解析指示テキスト |
| `model` | string | No | `gemini-3-flash-preview` | 使用するGeminiモデル |

**推奨モデル:**

- `gemini-3-flash-preview`（デフォルト）
- `gemini-3.1-pro-preview`
- `gemini-2.5-flash`
- `gemini-2.5-pro`
- `gemini-2.5-flash-lite`

任意のGeminiモデル名を指定できます。

### `delete_uploaded_video`

動画解析後のクリーンアップ用途で、GCSにアップロード済みの動画を削除します。**Vertex AIモード専用**で、ユーザから明示的に依頼があった場合のみ呼び出すことを想定しています。

**パラメータ:**

| 名前 | 型 | 必須 | 説明 |
|------|------|------|------|
| `video_path` | string | Yes | 削除対象のローカル動画ファイルの絶対パス |

**動作:**

指定されたローカルファイルのSHA256ハッシュの先頭16文字を計算し、`gemini-video-analyze-mcp/{sha256_16}_{filename}` 形式のBlob名を再構築して、一致する名前のBlobが存在する場合のみ削除します。ローカルファイルの内容が過去アップロード時と変わっていれば再計算したBlob名が一致しないため、内容の異なるファイルを誤って指定しても別Blobを削除してしまう事故は起きません（ただしGCS上オブジェクトの実内容そのものを検証しているわけではなく、あくまで決定論的なBlob名の一致に依存しています）。

- 約19MiB以下の動画はそもそもアップロードされないため、削除対象なしと返します
- Gemini Developer APIモードでは利用できません（File API側のファイル名がハッシュベースではないため）
- サービスアカウントには削除権限（`roles/storage.objectAdmin` または `roles/storage.objectUser`）が必要です

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
