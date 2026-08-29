"""Basic Pitch によるベース音源から MIDI 変換モジュール。"""
from __future__ import annotations

import os

import basic_pitch.inference


def bass_to_midi(
    bass_audio_path: str,
    output_midi_path: str,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
) -> str:
    """
    ベース音源（WAV）を Basic Pitch で解析し、単音ベースラインの MIDI を生成する。

    Args:
        bass_audio_path: ベース音源 WAV ファイルのパス。
        output_midi_path: 出力 MIDI ファイルのパス。
        onset_threshold: ノートオン検出閾値（0.0〜1.0）。
        frame_threshold: フレーム検出閾値（0.0〜1.0）。

    Returns:
        生成された MIDI ファイルのパス。
    """
    os.makedirs(os.path.dirname(output_midi_path) or ".", exist_ok=True)

    # Basic Pitch は (model_output, midi_data, note_events) を返す
    _, midi_data, _ = basic_pitch.inference.predict(
        bass_audio_path,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
    )

    midi_data.write(output_midi_path)
    return output_midi_path
