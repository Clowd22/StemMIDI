"""サンプル音源（C-Am-F-G の 4 小節）を合成して WAV を生成するスクリプト。

- コード: パッド音（コードトーン）
- ベース: ルート音のベースライン
- リズム: 4つ打ちドラム（キック・スネア・ハイハット）
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
BPM = 120
BEAT = 60.0 / BPM  # 0.5 秒
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "temp"


def _t(dur: float) -> np.ndarray:
    return np.linspace(0, dur, int(SR * dur), endpoint=False)


def _env(dur: float, decay: float = 0.3) -> np.ndarray:
    return np.exp(-decay * _t(dur))


def midi_to_freq(midi: int) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def note(
    freq: float, dur: float, amp: float = 0.4, decay: float = 0.3, harmonics: int = 2
) -> np.ndarray:
    t = _t(dur)
    wave = np.zeros_like(t)
    for h in range(1, harmonics + 1):
        wave += (1 / h) * np.sin(2 * np.pi * freq * h * t)
    return amp * wave * _env(dur, decay)


def add_to_mix(mix: np.ndarray, start_sec: float, wave: np.ndarray) -> None:
    """開始時刻（秒）を起点に、波形を安全にミックス配列へ加算する。"""
    s = int(SR * start_sec)
    e = min(s + len(wave), len(mix))
    mix[s:e] += wave[: e - s]


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    total_dur = 8.0  # 4 小節（1 小節 2 秒）
    mix = np.zeros(int(SR * total_dur))

    # コード進行: C - Am - F - G（各 2 秒）
    progression = [
        {"root": 48, "chord": "C"},
        {"root": 45, "chord": "Am"},
        {"root": 41, "chord": "F"},
        {"root": 43, "chord": "G"},
    ]
    chord_intervals = {
        "C": [0, 4, 7],
        "Am": [0, 3, 7],
        "F": [0, 4, 7],
        "G": [0, 4, 7],
    }

    for idx, seg in enumerate(progression):
        start = idx * 2.0
        root = seg["root"]
        intervals = chord_intervals[seg["chord"]]

        # パッド（コードトーンを 1 オクターブ上で重ねる）
        for iv in intervals:
            f = midi_to_freq(root + 36 + iv)
            add_to_mix(mix, start, note(f, 1.9, amp=0.12, decay=0.25))

        # ベース（ルート音を各ビートで）
        bass_f = midi_to_freq(root - 12)
        for beat in range(4):
            bt = start + beat * BEAT
            add_to_mix(mix, bt, note(bass_f, BEAT * 0.8, amp=0.35, decay=1.8, harmonics=2))

    # ドラム（4つ打ち: キック + スネア + ハイハット）
    rng = np.random.default_rng(42)
    for beat in range(16):
        bt = beat * BEAT

        # キック
        kick = np.exp(-35 * _t(0.15)) * np.sin(2 * np.pi * 55 * _t(0.15))
        add_to_mix(mix, bt, 0.55 * kick)

        # ハイハット（オフビート）
        if beat % 2 == 1:
            hat = np.exp(-25 * _t(0.1)) * np.sign(np.sin(2 * np.pi * 6500 * _t(0.1)))
            add_to_mix(mix, bt, 0.12 * hat)

        # スネア（2・4 拍目）
        if beat % 4 in (1, 3):
            noise = rng.normal(0, 1, int(SR * 0.15))
            snare = noise * np.exp(-20 * _t(0.15)) + 0.3 * np.exp(-40 * _t(0.15)) * np.sin(
                2 * np.pi * 180 * _t(0.15)
            )
            add_to_mix(mix, bt, 0.25 * snare)

    # 正規化して保存
    mix = mix / np.max(np.abs(mix)) * 0.9
    out = SAMPLE_DIR / "sample.wav"
    sf.write(str(out), mix, SR)
    print(f"サンプル音源を生成しました: {out} ({len(mix) / SR:.1f} 秒, {BPM} BPM)")


if __name__ == "__main__":
    main()
