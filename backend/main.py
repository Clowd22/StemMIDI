"""FastAPI バックエンドアプリケーション。"""
from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from services import (
    bass_to_midi,
    beat_detector,
    chord_analyzer,
    midi_generator,
    separator,
    youtube,
)

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "temp"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="StemMIDI",
    description="音源からコード・ベース・ビートを解析し、マルチトラック MIDI を生成する API",
)

# 開発用 CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# フロントエンド（静的ファイル）配信
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    """フロントエンドの index.html を返す。"""
    return FileResponse(STATIC_DIR / "index.html")


def cleanup_temp_files(max_age_hours: float = 24.0) -> None:
    """temp/ 配下の一定時間以上前の解析結果ディレクトリを削除する。"""
    cutoff = time.time() - max_age_hours * 3600
    for entry in TEMP_DIR.iterdir():
        if not entry.is_dir():
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry)
        except Exception:
            pass  # 削除に失敗しても処理を継続


def run_pipeline(file_id: str, input_path: str, title: str = "") -> dict:
    """
    音声ファイルを解析し、結果を返す共通パイプライン。
    音源分離 → コード・ベース・ビート解析 → マルチトラック MIDI 生成。
    """
    work_dir = TEMP_DIR / file_id
    stems_dir = work_dir / "stems"
    midi_dir = work_dir / "midi"
    stems_dir.mkdir(parents=True, exist_ok=True)
    midi_dir.mkdir(parents=True, exist_ok=True)

    # 1. 音源分離（Bass / Drums / Other）
    stem_files = separator.separate_audio(input_path, str(stems_dir))
    stems = {Path(p).stem: p for p in stem_files}

    # 2. テンポ・ビート検出（Drums トラック、なければ原音源）
    drum_path = stems.get("drums")
    beat_source = drum_path or input_path
    beat_info = beat_detector.detect_beats(beat_source)
    bpm = beat_info["bpm"]
    beats = beat_info["beats"]

    # 3. ベースライン MIDI 化（Basic Pitch）
    bass_path = stems.get("bass")
    bass_midi_path = midi_dir / "bass.mid"
    bass_to_midi.bass_to_midi(bass_path, str(bass_midi_path))
    bass_notes = bass_to_midi.extract_notes_from_midi(str(bass_midi_path))

    # 4. コード進行推定（Other トラック、なければ原音源）
    other_path = stems.get("other")
    chord_source = other_path or input_path
    chords = chord_analyzer.analyze_chords(chord_source)

    # 5. マルチトラック MIDI 生成
    multitrack_path = midi_dir / "multitrack.mid"
    midi_generator.generate_multitrack_midi(
        chords, bass_notes, beats, bpm, str(multitrack_path)
    )

    return {
        "file_id": file_id,
        "title": title,
        "bpm": bpm,
        "chords": chords,
        "bass_notes": bass_notes[:100],  # フロント表示用（最大100ノート）
        "beat_count": len(beats),
        "midi_url": f"/api/download-midi/{file_id}",
    }


@app.post("/api/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """音声ファイルのアップロードを受け取り、解析パイプラインを実行する。"""
    cleanup_temp_files()
    file_id = uuid.uuid4().hex
    input_dir = TEMP_DIR / file_id / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    # アップロードファイルを保存（パス要素を除去して安全に保存）
    safe_name = Path(file.filename or "audio").name
    input_path = input_dir / safe_name
    with input_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        return run_pipeline(file_id, str(input_path), title=safe_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"解析に失敗しました: {exc}") from exc


@app.post("/api/analyze-youtube")
async def analyze_youtube(url: str = Form(...)):
    """YouTube URL を受け取り、音声を取得して解析パイプラインを実行する。"""
    cleanup_temp_files()
    file_id = uuid.uuid4().hex
    input_dir = TEMP_DIR / file_id / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    try:
        info = youtube.download_audio(url, str(input_dir))
    except youtube.YouTubeDownloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = run_pipeline(file_id, info["path"], title=info["title"])
        result["youtube_id"] = info["id"]  # フロントエンドの YouTube 埋め込み用
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"解析に失敗しました: {exc}") from exc


@app.get("/api/download-midi/{file_id}")
def download_midi(file_id: str) -> FileResponse:
    """生成されたマルチトラック MIDI ファイルをダウンロードする。"""
    midi_path = TEMP_DIR / file_id / "midi" / "multitrack.mid"
    if not midi_path.exists():
        raise HTTPException(status_code=404, detail="MIDI ファイルが見つかりません")
    return FileResponse(
        str(midi_path),
        media_type="audio/midi",
        filename="multitrack.mid",
    )
