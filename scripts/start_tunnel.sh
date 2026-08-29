#!/usr/bin/env bash
# =============================================================================
# StemMIDI — uvicorn + Cloudflare Tunnel を同時に起動するヘルパースクリプト
#
# 使い方:
#   sh scripts/start_tunnel.sh
#   npm run tunnel
#
# 要件:
#   - cloudflared がインストールされていること
#       macOS: brew install cloudflared
#   - Python 仮想環境 (.venv) が用意されていること
#
# 環境変数（任意）:
#   HOST          バインドするアドレス（デフォルト: 127.0.0.1）
#   PORT          バインドするポート（デフォルト: 8000）
#   ALLOWED_ORIGINS  CORS 許可オリジン（カンマ区切り、未指定なら全許可）
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

# cloudflared の存在確認
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "ERROR: cloudflared がインストールされていません。" >&2
  echo "  macOS:  brew install cloudflared" >&2
  echo "  その他: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" >&2
  exit 1
fi

# Python 仮想環境の確認
if [ ! -x "${ROOT_DIR}/.venv/bin/uvicorn" ]; then
  echo "ERROR: Python 仮想環境 (.venv) が見つかりません。" >&2
  echo "  README.md のセットアップ手順に従って仮想環境を用意してください。" >&2
  exit 1
fi

echo "=============================================="
echo " StemMIDI を Cloudflare Tunnel で公開します"
echo "----------------------------------------------"
echo " local server : http://${HOST}:${PORT}"
echo "=============================================="

# uvicorn をバックグラウンドで起動
"${ROOT_DIR}/.venv/bin/uvicorn" backend.main:app --host "${HOST}" --port "${PORT}" &
UVICORN_PID=$!

# サーバー起動を待つ
sleep 3

# Ctrl+C で uvicorn も停止するよう trap を設定
trap 'echo ""; echo "[*] 停止しています..."; kill "${UVICORN_PID}" 2>/dev/null || true; exit 0' INT TERM

echo "[*] cloudflared を起動しています（一時的な公開 URL が生成されます）"
echo "    表示された https://....trycloudflare.com をブラウザで開いてください"
echo "    停止するには Ctrl+C を押してください"
echo ""

# cloudflared クイックトンネル（Cloudflare アカウント不要で一時 URL を発行）
cloudflared tunnel --url "http://${HOST}:${PORT}"

# cloudflared が終了したら uvicorn も停止
kill "${UVICORN_PID}" 2>/dev/null || true
