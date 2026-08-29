"""yt-dlp による YouTube からの音声取得モジュール。"""
from __future__ import annotations

import os
from typing import Dict

import yt_dlp

# 解析対象の動画の長さ上限（秒）。長時間動画の解析を防ぐ。
MAX_DURATION_SECONDS = 600

# YouTube の URL ホスト判定用
_YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")


class YouTubeDownloadError(Exception):
    """YouTube からの音声取得に失敗した際に送出される例外。"""


def _is_valid_youtube_url(url: str) -> bool:
    """YouTube の URL かどうかを簡易判定する。"""
    url_lower = url.lower()
    return any(host in url_lower for host in _YOUTUBE_HOSTS)


def _build_opts(output_dir: str) -> dict:
    """yt-dlp のオプションを構築する。"""
    return {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }
        ],
        "outtmpl": os.path.join(output_dir, "youtube_%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
    }


def download_audio(url: str, output_dir: str) -> Dict:
    """
    YouTube URL から音声をダウンロードし、WAV ファイルとして保存する。

    Args:
        url: YouTube の動画 URL。
        output_dir: 音声ファイルの保存先ディレクトリ。

    Returns:
        {"path": 音声ファイルのパス, "id": 動画ID, "title": 動画タイトル, "duration": 動画の長さ（秒）}

    Raises:
        YouTubeDownloadError: URL が無効、またはダウンロードに失敗した場合。
    """
    if not _is_valid_youtube_url(url):
        raise YouTubeDownloadError("YouTube の URL を入力してください")

    os.makedirs(output_dir, exist_ok=True)
    opts = _build_opts(output_dir)

    # 1. メタデータのみ取得して長さを確認（長すぎる動画をダウンロード前に弾く）
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise YouTubeDownloadError(f"YouTube の情報を取得できませんでした: {exc}") from exc

    duration = info.get("duration") or 0
    if duration > MAX_DURATION_SECONDS:
        raise YouTubeDownloadError(
            f"動画の長さが上限（{MAX_DURATION_SECONDS // 60}分）を超えています"
        )

    video_id = info.get("id", "unknown")
    title = info.get("title", "")

    # 2. 音声をダウンロードして WAV に変換
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as exc:
        raise YouTubeDownloadError(f"YouTube から音声を取得できませんでした: {exc}") from exc

    audio_path = os.path.join(output_dir, f"youtube_{video_id}.wav")
    if not os.path.exists(audio_path):
        raise YouTubeDownloadError("音声ファイルの変換に失敗しました（ffmpeg を確認してください）")

    return {
        "path": audio_path,
        "id": video_id,
        "title": title,
        "duration": duration,
    }
