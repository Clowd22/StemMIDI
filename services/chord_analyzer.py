"""librosa のクロマグラムに基づくコード進行推定モジュール。"""
from __future__ import annotations

from typing import Dict, List

import librosa
import numpy as np

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# メジャー / マイナーコードのピッチクラス強度テンプレート
MAJOR_TEMPLATE = np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0], dtype=float)
MINOR_TEMPLATE = np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0], dtype=float)


def _build_templates() -> np.ndarray:
    """12 根音 × メジャー/マイナーの 24 テンプレートを構築する。"""
    templates = []
    for root in range(12):
        for template in (MAJOR_TEMPLATE, MINOR_TEMPLATE):
            templates.append(np.roll(template, root))
    return np.array(templates)


_TEMPLATES = _build_templates()


def _match_chord(chroma_vec: np.ndarray) -> int:
    """クロマベクトルに対して最もスコアの高いテンプレートのインデックスを返す。"""
    norm = np.linalg.norm(chroma_vec)
    if norm < 1e-8:
        return 0
    scores = _TEMPLATES @ (chroma_vec / norm)
    return int(np.argmax(scores))


def _idx_to_chord(idx: int) -> str:
    root = idx // 2
    suffix = "m" if idx % 2 == 1 else ""
    return f"{NOTE_NAMES[root]}{suffix}"


def analyze_chords(
    audio_path: str,
    hop_length: int = 512,
    min_chord_duration: float = 0.5,
    n_chroma: int = 12,
) -> List[Dict[str, float | str]]:
    """
    音声ファイルからコード進行を推定する。

    Args:
        audio_path: 解析対象の音声ファイル（Other トラック想定）。
        hop_length: クロマグラムのフレーム間隔（サンプル数）。
        min_chord_duration: 最小コード持続時間（秒）。これより短いコードは前のセグメントに統合。
        n_chroma: クロマビン数（通常 12）。

    Returns:
        コード進行のリスト。各要素は {"start": 開始秒, "end": 終了秒, "chord": 和音名}
    """
    y, sr = librosa.load(audio_path, sr=22050, mono=True)

    # クロマグラム（12 × フレーム数）
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length, n_chroma=n_chroma)

    frame_times = librosa.frames_to_time(
        np.arange(chroma.shape[1]), sr=sr, hop_length=hop_length
    )

    segments: List[Dict[str, float | str]] = []
    for i in range(chroma.shape[1]):
        chord = _idx_to_chord(_match_chord(chroma[:, i]))
        start = float(frame_times[i])
        end = start + float(frame_times[1])  # 1 フレーム分
        if segments and segments[-1]["chord"] == chord:
            segments[-1]["end"] = end
        else:
            segments.append({"start": start, "end": end, "chord": chord})

    # 短すぎるコードを前のセグメントに統合
    merged: List[Dict[str, float | str]] = []
    for seg in segments:
        if merged and (seg["end"] - seg["start"]) < min_chord_duration:
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(seg)

    return merged
