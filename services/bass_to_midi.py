"""Basic Pitch によるベース音源から MIDI 変換モジュール。"""
from __future__ import annotations

import os
from typing import Dict, List

import basic_pitch.inference
import mido


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


def extract_notes_from_midi(midi_path: str) -> List[Dict[str, float]]:
    """
    MIDI ファイルからノート（開始秒・終了秒・MIDI番号）を抽出する。

    Args:
        midi_path: 入力 MIDI ファイルのパス。

    Returns:
        {"start": 開始秒, "end": 終了秒, "note": MIDIノート番号} のリスト。
    """
    mid = mido.MidiFile(midi_path)
    notes: List[Dict[str, float]] = []
    for track in mid.tracks:
        current_time = 0.0
        tempo = 500_000  # デフォルト 120 BPM（マイクロ秒/四分音符）
        open_notes: Dict[int, float] = {}
        for msg in track:
            current_time += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
            if msg.type == "set_tempo":
                tempo = msg.tempo
            elif msg.type == "note_on" and msg.velocity > 0:
                open_notes[msg.note] = current_time
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                if msg.note in open_notes:
                    start = open_notes.pop(msg.note)
                    notes.append(
                        {
                            "start": round(start, 3),
                            "end": round(current_time, 3),
                            "note": msg.note,
                        }
                    )
    return notes
