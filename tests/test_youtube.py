"""YouTube URL からの音声取得と全パイプライン処理のテスト。

- テスト1: yt-dlp で指定 URL から音声がダウンロードされるか
- テスト2: ダウンロード音声が Demucs 分離 + Basic Pitch を経て .mid / コード進行を生成するか
- テスト3: POST /api/analyze-youtube が 200 OK と構造化 JSON を返すか
- テスト4: 不正 URL・存在しない動画 ID で適切なエラー（400）を返すか
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# テスト用の YouTube URL（環境変数 YOUTUBE_TEST_URL で上書き可能）
# デフォルト: 15 秒のピアノコード動画（短時間・ダウンロード可能な音源）
YOUTUBE_TEST_URL = os.environ.get(
    "YOUTUBE_TEST_URL",
    "https://www.youtube.com/watch?v=hdqzSa9eEL0",
)


@pytest.fixture(scope="session")
def youtube_audio_info(tmp_path_factory) -> dict:
    """yt-dlp で YouTube 音声をダウンロードし、情報を返す（セッション中に一度だけ）。"""
    from services import youtube

    out_dir = tmp_path_factory.mktemp("youtube_audio")
    return youtube.download_audio(YOUTUBE_TEST_URL, str(out_dir))


# ---------- テスト1: yt-dlp によるダウンロード ----------
def test_youtube_download(youtube_audio_info):
    """yt-dlp 経由で YouTube URL から音声ファイルが正常にダウンロードされることを検証する。"""
    audio_path = Path(youtube_audio_info["path"])
    assert audio_path.exists(), "音声ファイルが存在するべき"
    assert audio_path.stat().st_size > 0, "音声ファイルは空であってはならない"
    assert youtube_audio_info["duration"] > 0, "動画の長さが取得できるべき"
    assert youtube_audio_info["id"], "動画 ID が取得できるべき"
    assert youtube_audio_info["title"], "動画タイトルが取得できるべき"


# ---------- テスト2: ダウンロード音声のパイプライン処理 ----------
def test_youtube_audio_pipeline(youtube_audio_info, tmp_path):
    """ダウンロード音声が Demucs 分離と Basic Pitch を経て .mid とコード進行データを生成するか検証する。"""
    from services import bass_to_midi, chord_analyzer, separator

    audio_path = youtube_audio_info["path"]

    # 音源分離（Demucs）
    stems_dir = tmp_path / "stems"
    stem_files = separator.separate_audio(audio_path, str(stems_dir))
    stems = {Path(p).stem: p for p in stem_files}
    assert "bass" in stems, "分離結果に bass トラックが含まれるべき"

    # ベース → MIDI（Basic Pitch）
    midi_path = bass_to_midi.bass_to_midi(stems["bass"], str(tmp_path / "bass.mid"))
    assert Path(midi_path).exists(), ".mid ファイルが生成されるべき"
    assert Path(midi_path).stat().st_size > 0, ".mid ファイルは空であってはならない"

    # コード進行データ
    chord_source = stems.get("other") or audio_path
    chords = chord_analyzer.analyze_chords(chord_source)
    assert isinstance(chords, list)
    assert len(chords) > 0, "コード進行が 1 つ以上検出されるべき"
    assert all("chord" in c for c in chords), "各コードに和音名が含まれるべき"


# ---------- テスト3: API エンドポイント ----------
def test_api_analyze_youtube(youtube_audio_info):
    """POST /api/analyze-youtube が 200 OK と正しく構造化された JSON を返すことを検証する。"""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    resp = client.post("/api/analyze-youtube", data={"url": YOUTUBE_TEST_URL})

    assert resp.status_code == 200, f"200 OK が期待される: {resp.text[:300]}"
    data = resp.json()
    assert data["youtube_id"] == youtube_audio_info["id"], "youtube_id が一致するべき"
    assert isinstance(data["chords"], list)
    assert len(data["chords"]) > 0, "コード進行が 1 つ以上検出されるべき"
    assert data["bpm"] > 0, "BPM が正の値であるべき"
    assert data["midi_url"].startswith("/api/download-midi/")
    assert "file_id" in data


# ---------- テスト4: 例外系（ネットワークエラー） ----------
@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=invalid_id_xxxx",
        "not_a_youtube_url",
    ],
)
def test_api_invalid_youtube_url(url):
    """不正な URL・存在しない動画 ID でサーバーが落ちずに適切なエラー（400）を返すことを検証する。"""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    resp = client.post("/api/analyze-youtube", data={"url": url})

    assert resp.status_code == 400, f"400 エラーが期待される: {resp.text[:200]}"
    assert "detail" in resp.json(), "エラーメッセージが返るべき"
