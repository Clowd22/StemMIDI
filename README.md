# StemMIDI

音源（MP3 / WAV 等）から「コード進行」「ベースライン」「リズム・ビート」を自動解析し、**マルチトラック MIDI** としてエクスポート・Web 上で可視化できるアプリケーションです。

- **音源分離**: [Demucs](https://github.com/facebookresearch/demucs) で Bass / Drums / Other に分離
- **ベース→MIDI**: [Basic Pitch](https://github.com/spotify/basic-pitch)（Spotify 製）でベースラインを音符化
- **コード解析**: librosa のクロマグラム + テンプレートマッチングでコード進行を推定
- **ビート検出**: librosa でテンポ（BPM）とビートを検出
- **MIDI 生成**: コード・ベース・ビートを統合した 4 トラック MIDI を出力
- **YouTube 解析**: yt-dlp で YouTube 動画から直接音声を取得して解析
- **Web UI**: DAW 風のダーク UI。波形・コードタイムライン・ピアノロールを再生に同期して表示

## 技術スタック

| 分類 | 技術 |
| --- | --- |
| バックエンド | FastAPI, Uvicorn |
| 音源分離 | Demucs 4.x (PyTorch) |
| Audio-to-MIDI | Basic Pitch 0.4.0 (Core ML) |
| YouTube 取得 | yt-dlp |
| 音声処理 | librosa 0.11, numpy |
| MIDI | mido, pretty-midi |
| フロントエンド | HTML / CSS / JavaScript (Canvas) |

## セットアップ

### 要件

- Python 3.11（Basic Pitch の依存関係のため）
- Homebrew（macOS の場合）

### インストール

```bash
# Python 3.11 が無い場合は Homebrew でインストール
brew install python@3.11

# 仮想環境を作成・有効化
python3.11 -m venv .venv
source .venv/bin/activate

# 依存ライブラリをインストール
pip install -r requirements.txt
```

> **注意**: Python 3.13 では Basic Pitch の依存関係（`numpy<1.24` / TensorFlow）が非互換のため動作しません。必ず Python 3.11 を使用してください。

## 起動方法

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

ブラウザで http://127.0.0.1:8000 を開きます。

音声ファイルをドラッグ＆ドロップすると、以下の処理が自動で実行されます。

1. Demucs による音源分離（初回はモデルのダウンロードに時間がかかります）
2. テンポ・ビート検出
3. ベースラインの MIDI 化（Basic Pitch）
4. コード進行の推定
5. マルチトラック MIDI の生成

解析には数分かかる場合があります。

## API 仕様

### `POST /api/analyze`

音声ファイルをアップロードして解析を実行します。

- リクエスト: `multipart/form-data` の `file` フィールド
- レスポンス:

```json
{
  "file_id": "xxxxxxxx",
  "bpm": 120,
  "chords": [{ "start": 0.0, "end": 2.0, "chord": "C" }],
  "bass_notes": [{ "start": 0.0, "end": 1.0, "note": 36 }],
  "beat_count": 16,
  "midi_url": "/api/download-midi/xxxxxxxx"
}
```

### `POST /api/analyze-youtube`

YouTube の URL を指定して解析を実行します。

- リクエスト: `multipart/form-data` の `url` フィールド
- レスポンス: `POST /api/analyze` と同形式 + `youtube_id`（埋め込みプレイヤー用）

### `GET /api/download-midi/{file_id}`

生成されたマルチトラック MIDI ファイルをダウンロードします。

- トラック構成: Tempo / Chords / Bass / Drums（GM ドラムマップ）

### `GET /`

フロントエンド（index.html）を配信します。

## デプロイ（Docker / Render）

```bash
# Docker イメージをビルドして実行
docker build -t stemmidi .
docker run -p 8000:8000 stemmidi
```

- Python 3.11 + ffmpeg が含まれます（yt-dlp の音声変換に必要）
- `temp/` は解析用の一時領域として利用され、古いファイルは自動でクリーンアップされます
- Render では `render.yaml` を利用して Docker デプロイできます

## テスト（サンプル音源）

```bash
# 1. サンプル音源（C-Am-F-G の 4 小節・8 秒）を生成
python scripts/generate_sample.py

# 2. 全体パイプライン（分離 → 解析 → MIDI 生成）を実行
python scripts/test_pipeline.py
```

## ディレクトリ構成

```
StemMIDI/
├── backend/            # FastAPI アプリケーション
│   └── main.py         # API エンドポイント定義
├── services/           # 解析処理モジュール
│   ├── separator.py       # Demucs による音源分離
│   ├── bass_to_midi.py    # Basic Pitch によるベース→MIDI
│   ├── chord_analyzer.py  # クロマグラムによるコード推定
│   ├── beat_detector.py   # テンポ・ビート検出
│   └── midi_generator.py  # マルチトラック MIDI 生成
├── static/             # Web フロントエンド
│   ├── index.html
│   └── app.js
├── scripts/            # サンプル生成・テストスクリプト
├── temp/               # アップロード・処理用一時ディレクトリ
└── requirements.txt
```

## ライセンス

本プロジェクトが利用するオープンソースライブラリ:
- [Demucs](https://github.com/facebookresearch/demucs) (MIT License)
- [Basic Pitch](https://github.com/spotify/basic-pitch) (Apache-2.0 License)
- [librosa](https://librosa.org/) (ISC License)
