"""テスト用のモック音声（C → G → Am → F 進行）を自動生成するスクリプト。

- パッド: コードトーン（サイン波 + 2倍音）
- ベース: C2 / G1 / A1 / F1 の単音
- リズム: 4つ打ちドラム（キック・スネア・ハイハット、ビート検出用）

使用方法:
    python tests/create_mock_audio.py [出力WAVパス]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile

SR = 44100
BPM = 120
BEAT = 60.0 / BPM  # 0.5 秒

# C → G → Am → F（各 2.5 秒、合計 10 秒）
PROGRESSION = [
    {"chord": "C", "root": 36},   # C2
    {"chord": "G", "root": 31},   # G1
    {"chord": "Am", "root": 33},  # A1
    {"chord": "F", "root": 29},   # F1
]
# 各コードのピッチクラス間隔（ルートからの半音）
CHORD_INTERVALS = {
    "C": [0, 4, 7],   # C メジャー
    "G": [0, 4, 7],   # G メジャー
    "Am": [0, 3, 7],  # A マイナー
    "F": [0, 4, 7],   # F メジャー
}
SEGMENT_DURATION = 2.5  # 各コードの長さ（秒）


def midi_to_freq(midi: int) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _t(dur: float) -> np.ndarray:
    return np.linspace(0, dur, int(SR * dur), endpoint=False)


def _note(freq: float, dur: float, amp: float = 0.3, decay: float = 0.3) -> np.ndarray:
    """減衰エンベロープ付きのサイン波（+2倍音）を生成する。"""
    t = _t(dur)
    wave = np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * 2 * t)
    env = np.exp(-decay * t)
    return amp * wave * env


def add_to_mix(mix: np.ndarray, start_sec: float, wave: np.ndarray) -> None:
    """開始時刻（秒）を起点に、波形を安全にミックス配列へ加算する。"""
    s = int(SR * start_sec)
    e = min(s + len(wave), len(mix))
    mix[s:e] += wave[: e - s]


def generate_mock_audio() -> np.ndarray:
    """10 秒のテスト用音声波形を生成して返す。"""
    total_dur = SEGMENT_DURATION * len(PROGRESSION)
    mix = np.zeros(int(SR * total_dur))

    for idx, seg in enumerate(PROGRESSION):
        start = idx * SEGMENT_DURATION
        root = seg["root"]

        # パッド（コードトーン）
        for interval in CHORD_INTERVALS[seg["chord"]]:
            freq = midi_to_freq(root + 36 + interval)  # 1 オクターブ上
            add_to_mix(mix, start, _note(freq, SEGMENT_DURATION - 0.1, amp=0.12, decay=0.2))

        # ベース（ルート音を各ビートで鳴らす）
        bass_freq = midi_to_freq(root)
        beats_in_seg = int(SEGMENT_DURATION / BEAT)
        for b in range(beats_in_seg):
            bt = start + b * BEAT
            add_to_mix(mix, bt, _note(bass_freq, BEAT * 0.8, amp=0.35, decay=1.8))

    # ドラム（4つ打ち: キック + スネア + ハイハット）
    rng = np.random.default_rng(2026)
    total_beats = int(total_dur / BEAT)
    for beat in range(total_beats):
        bt = beat * BEAT
        # キック
        kick = np.exp(-35 * _t(0.15)) * np.sin(2 * np.pi * 55 * _t(0.15))
        add_to_mix(mix, bt, 0.5 * kick)
        # ハイハット（オフビート）
        if beat % 2 == 1:
            hat = np.exp(-25 * _t(0.1)) * np.sign(np.sin(2 * np.pi * 6500 * _t(0.1)))
            add_to_mix(mix, bt, 0.1 * hat)
        # スネア（2・4 拍目）
        if beat % 4 in (1, 3):
            noise = rng.normal(0, 1, int(SR * 0.15))
            snare = noise * np.exp(-20 * _t(0.15))
            add_to_mix(mix, bt, 0.2 * snare)

    # 正規化（クリッピングを防ぐ）
    max_abs = np.max(np.abs(mix))
    if max_abs > 0:
        mix = mix / max_abs * 0.85
    return mix


def main() -> str:
    default_path = Path(__file__).resolve().parent.parent / "temp" / "mock.wav"
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mix = generate_mock_audio()
    wavfile.write(str(out_path), SR, (mix * 32767).astype(np.int16))
    print(f"モック音声を生成しました: {out_path} ({len(mix) / SR:.1f} 秒)")
    return str(out_path)


if __name__ == "__main__":
    main()
