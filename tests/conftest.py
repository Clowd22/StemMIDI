"""pytest の共通フィクスチャ。

- プロジェクトルートを sys.path に追加（services / backend の import 用）
- モック音声の生成（session スコープで一度だけ）
- Demucs 分離結果と Basic Pitch の MIDI 化結果を session スコープで共有
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import torch
from scipy.io import wavfile

# torch（Demucs）のスレッド数を制限して libc++abi のクラッシュを防ぐ
torch.set_num_threads(2)

# プロジェクトルートと tests/ を sys.path に追加
ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
for p in (str(ROOT), str(TESTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from create_mock_audio import SR, generate_mock_audio  # noqa: E402

MOCK_AUDIO_PATH = ROOT / "temp" / "mock.wav"
STEMS_DIR = ROOT / "temp" / "test_stems"
BASS_MIDI_PATH = ROOT / "temp" / "test_bass.mid"


@pytest.fixture(scope="session")
def mock_audio_path() -> Path:
    """テスト用のモック音声（C-G-Am-F 進行・10 秒）を生成し、パスを返す。"""
    if not MOCK_AUDIO_PATH.exists():
        MOCK_AUDIO_PATH.parent.mkdir(parents=True, exist_ok=True)
        mix = generate_mock_audio()
        wavfile.write(str(MOCK_AUDIO_PATH), SR, (mix * 32767).astype(np.int16))
    return MOCK_AUDIO_PATH


@pytest.fixture(scope="session")
def separated_stems(mock_audio_path) -> dict:
    """モック音声を Demucs で分離し、ステムパスの dict を返す（一度だけ実行）。"""
    from services import separator

    STEMS_DIR.mkdir(parents=True, exist_ok=True)
    stem_files = separator.separate_audio(str(mock_audio_path), str(STEMS_DIR))
    return {Path(p).stem: p for p in stem_files}


@pytest.fixture(scope="session")
def bass_midi_path(separated_stems) -> Path:
    """分離されたベーストラックを Basic Pitch で MIDI 化したパスを返す。"""
    from services import bass_to_midi

    bass_to_midi.bass_to_midi(separated_stems["bass"], str(BASS_MIDI_PATH))
    return BASS_MIDI_PATH
