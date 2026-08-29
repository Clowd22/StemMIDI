"""コード進行・ベースライン・ビートを統合してマルチトラック MIDI を生成するモジュール。"""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

import mido
from mido import Message, MidiFile, MidiTrack

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# GM ドラムマップ
GM_KICK = 36
GM_SNARE = 38
GM_CLOSED_HAT = 42


def _chord_to_notes(chord_name: str, base_octave: int = 3) -> List[int]:
    """
    コード名（例: "C", "Am", "G#m"）を MIDI ノート番号リストに変換する。
    base_octave は MIDI 表記（C4=60 基準）でのルートのオクターブ。
    """
    name = chord_name.strip()
    is_minor = name.endswith("m") and not name.endswith("maj")
    root_name = name[:-1] if is_minor else name
    intervals = [0, 3, 7] if is_minor else [0, 4, 7]
    root = NOTE_NAMES.index(root_name)
    return [(base_octave + 1) * 12 + root + i for i in intervals]


def _build_note_events(
    notes: List[Dict], bpm: int, ticks_per_beat: int
) -> List[Tuple[int, int, str, int]]:
    """(start, end, note) のリストをソート済みイベント（tick, sort, on/off, note）に変換する。"""
    events: List[Tuple[int, int, str, int]] = []
    for note in notes:
        start_tick = int(float(note["start"]) * bpm * ticks_per_beat / 60)
        end_tick = int(float(note["end"]) * bpm * ticks_per_beat / 60)
        if end_tick <= start_tick:
            end_tick = start_tick + ticks_per_beat // 4
        note_num = int(note["note"])
        events.append((start_tick, 0, "on", note_num))
        events.append((end_tick, 1, "off", note_num))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


def _write_events(
    track: MidiTrack, events: List[Tuple[int, int, str, int]], velocity: int = 70
) -> None:
    """イベントリストを MIDI トラックに書き込む（デルタタイム方式）。"""
    prev = 0
    for tick, _, ev, note_num in events:
        delta = max(0, tick - prev)
        if ev == "on":
            track.append(Message("note_on", note=note_num, velocity=velocity, time=delta))
        else:
            track.append(Message("note_off", note=note_num, velocity=0, time=delta))
        prev = tick


def _build_drum_events(
    beats: List[float], bpm: int, ticks_per_beat: int
) -> List[Tuple[int, int, str, int]]:
    """
    ビート時刻からドラムイベントを生成する。
    キック（4つ打ち）・スネア（2/4拍目）・クローズハイハット（8分音符）を配置。
    """
    events: List[Tuple[int, int, str, int]] = []
    for i, beat_time in enumerate(beats):
        tick = int(float(beat_time) * bpm * ticks_per_beat / 60)
        events.append((tick, 0, "on", GM_KICK))
        events.append((tick, 1, "off", GM_KICK))
        if i % 4 in (1, 3):
            events.append((tick, 0, "on", GM_SNARE))
            events.append((tick, 1, "off", GM_SNARE))
        half_tick = tick + ticks_per_beat // 2
        events.append((half_tick, 0, "on", GM_CLOSED_HAT))
        events.append((half_tick, 1, "off", GM_CLOSED_HAT))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


def generate_multitrack_midi(
    chords: List[Dict],
    bass_notes: List[Dict],
    beats: List[float],
    bpm: int,
    output_path: str,
    chord_velocity: int = 64,
    bass_velocity: int = 80,
) -> str:
    """
    コード進行・ベースライン・ビートを統合したマルチトラック MIDI を生成する。

    Args:
        chords: コード進行。各要素 {"start", "end", "chord"}。
        bass_notes: ベースノート。各要素 {"start", "end", "note"}。
        beats: ビート時刻（秒）。
        bpm: テンポ。
        output_path: 出力 MIDI ファイルのパス。
        chord_velocity: コードトラックのベロシティ。
        bass_velocity: ベーストラックのベロシティ。

    Returns:
        生成された MIDI ファイルのパス。
    """
    ticks_per_beat = 480
    mid = MidiFile(ticks_per_beat=ticks_per_beat)

    # テンポ / 拍子マップ
    tempo_track = MidiTrack()
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=int(60_000_000 / bpm), time=0))
    tempo_track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    tempo_track.append(mido.MetaMessage("track_name", name="Tempo", time=0))
    mid.tracks.append(tempo_track)

    # コードトラック
    chord_track = MidiTrack()
    chord_track.append(mido.MetaMessage("track_name", name="Chords", time=0))
    chord_track.append(Message("program_change", program=0, time=0))
    chord_notes: List[Dict] = []
    for ch in chords:
        for note in _chord_to_notes(str(ch["chord"])):
            chord_notes.append({"start": ch["start"], "end": ch["end"], "note": note})
    _write_events(
        chord_track,
        _build_note_events(chord_notes, bpm, ticks_per_beat),
        velocity=chord_velocity,
    )
    mid.tracks.append(chord_track)

    # ベーストラック
    bass_track = MidiTrack()
    bass_track.append(mido.MetaMessage("track_name", name="Bass", time=0))
    bass_track.append(Message("program_change", program=32, time=0))  # Acoustic Bass
    _write_events(
        bass_track,
        _build_note_events(bass_notes, bpm, ticks_per_beat),
        velocity=bass_velocity,
    )
    mid.tracks.append(bass_track)

    # リズム（ドラム）トラック
    drums_track = MidiTrack()
    drums_track.append(mido.MetaMessage("track_name", name="Drums", time=0))
    drums_track.append(Message("program_change", program=0, time=0))
    _write_events(
        drums_track,
        _build_drum_events(beats, bpm, ticks_per_beat),
        velocity=90,
    )
    mid.tracks.append(drums_track)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    mid.save(output_path)
    return output_path
