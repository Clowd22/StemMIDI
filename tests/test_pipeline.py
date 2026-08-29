"""StemMIDI パイプラインと API の自動テスト。

- テスト1: 音源分離＆MIDI 変換（Demucs + Basic Pitch がエラーなく動作し .mid を出力）
- テスト2: MIDI データ構造チェック（トラックと Note On/Off イベント）
- テスト3: API エンドポイント（POST /api/analyze が 200 と構造化 JSON を返す）
- テスト4: 例外系（壊れたファイル・無音ファイルで適切なエラーを返す）
"""
from __future__ import annotations

import io
from pathlib import Path

import mido
import numpy as np
import pytest
from scipy.io import wavfile


# ---------- テスト1: 音源分離＆MIDI 変換 ----------
def test_source_separation_and_midi_conversion(separated_stems, bass_midi_path):
    """Demucs で分離し、Basic Pitch でベースを MIDI 化できることを検証する。"""
    # 分離結果に bass / drums トラックが含まれる
    assert "bass" in separated_stems, "分離結果に bass トラックが含まれるべき"
    assert "drums" in separated_stems, "分離結果に drums トラックが含まれるべき"

    # .mid ファイルが出力されている
    assert bass_midi_path.exists(), "MIDI ファイルが出力されるべき"
    assert bass_midi_path.stat().st_size > 0, "MIDI ファイルは空であってはならない"


# ---------- テスト2: MIDI データ構造チェック ----------
def test_midi_data_structure(bass_midi_path):
    """生成された MIDI にトラックと Note On/Off イベントが記録されているか検証する。"""
    mid = mido.MidiFile(str(bass_midi_path))

    assert len(mid.tracks) > 0, "MIDI にトラックが存在すべき"

    note_on = []
    note_end = []  # note_off または note_on velocity=0（MIDI 仕様では終了を velocity=0 で表す場合がある）
    for track in mid.tracks:
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0:
                note_on.append(msg)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                note_end.append(msg)

    assert len(note_on) > 0, "Note On イベントが存在すべき"
    assert len(note_end) > 0, "Note 終了イベント（note_off / velocity=0）が存在すべき"
    assert all(0 <= n.note <= 127 for n in note_on), "ノート番号は MIDI 範囲（0-127）内"

    # 開始時間が負にならない（タイムスタンプの整合性）
    for track in mid.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            assert tick >= 0, "MIDI のタイムスタンプが負にならないこと"


# ---------- テスト3: API エンドポイント ----------
def test_api_analyze_endpoint(mock_audio_path):
    """POST /api/analyze が 200 OK と構造化 JSON を返すことを検証する。"""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with open(mock_audio_path, "rb") as f:
        resp = client.post(
            "/api/analyze",
            files={"file": ("mock.wav", f, "audio/wav")},
        )

    assert resp.status_code == 200, f"200 OK が期待される: {resp.text[:300]}"
    data = resp.json()

    # コード進行配列（タイムスタンプ付き）
    assert isinstance(data["chords"], list)
    assert len(data["chords"]) > 0, "コード進行が 1 つ以上検出されるべき"
    first = data["chords"][0]
    assert "start" in first and "end" in first and "chord" in first

    # BPM
    assert isinstance(data["bpm"], (int, float))
    assert data["bpm"] > 0, "BPM が正の値であるべき"

    # MIDI URL
    assert data["midi_url"].startswith("/api/download-midi/")
    assert "file_id" in data


# ---------- テスト4: 例外系 ----------
def test_api_broken_file():
    """壊れたファイルを送信した際に 400 エラーが返ることを検証する。"""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    broken = io.BytesIO(b"\x00\x01\x02 not a real wav file" * 100)
    resp = client.post(
        "/api/analyze",
        files={"file": ("broken.wav", broken, "audio/wav")},
    )

    assert resp.status_code == 400, "壊れたファイルは 400 エラーになるべき"
    assert "detail" in resp.json()
    assert "読み込めません" in resp.json()["detail"]


def test_api_silence_file():
    """無音ファイルを送信した際に 400 エラーが返ることを検証する。"""
    from fastapi.testclient import TestClient

    from backend.main import app

    sr = 44100
    buf = io.BytesIO()
    wavfile.write(buf, sr, np.zeros(sr, dtype=np.int16))
    buf.seek(0)

    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("silence.wav", buf, "audio/wav")},
    )

    assert resp.status_code == 400, "無音ファイルは 400 エラーになるべき"
    assert "detail" in resp.json()
    assert "無音" in resp.json()["detail"]
