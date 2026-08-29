"""librosa によるテンポ・ビート検出モジュール。"""
from __future__ import annotations

from typing import List

import librosa
import numpy as np


def detect_beats(audio_path: str, start_bpm: float = 120.0, sr: int = 22050) -> dict:
    """
    音声ファイルからテンポ（BPM）とビート時刻（秒）を検出する。

    Args:
        audio_path: 解析対象の音声ファイルパス。
        start_bpm: テンポ推定の初期値。
        sr: リサンプルするサンプリングレート。

    Returns:
        {"bpm": 推定BPM, "beats": ビート時刻のリスト（秒）}
    """
    y, sr = librosa.load(audio_path, sr=sr, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, start_bpm=start_bpm)

    # librosa 0.10 ではスカラー、0.11+ では配列で返る場合がある
    if isinstance(tempo, np.ndarray):
        bpm = float(np.nanmean(tempo))
    else:
        bpm = float(tempo)
    if not np.isfinite(bpm) or bpm <= 0:
        bpm = float(start_bpm)

    beat_times: List[float] = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    return {"bpm": round(bpm), "beats": beat_times}
