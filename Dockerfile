# StemMIDI — Python 3.11 + ffmpeg のデプロイ用 Dockerfile
# Render / Fly.io など Docker をサポートするプラットフォームで使用可能
FROM python:3.11-slim

# yt-dlp の音声変換と librosa のデコードに必要な ffmpeg をインストール
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存ライブラリを先にコピーしてビルドキャッシュを効かせる
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体をコピー
COPY backend/ ./backend/
COPY services/ ./services/
COPY static/ ./static/
COPY scripts/ ./scripts/
COPY README.md ./

# アップロード・解析用の一時ディレクトリを作成
RUN mkdir -p temp

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
