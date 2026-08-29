"""音源分離から MIDI 生成までの全体パイプラインをテストするスクリプト。

使用方法:
    .venv/bin/python scripts/test_pipeline.py [入力音声ファイル]
"""
from __future__ import annotations

import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加（scripts/ から実行しても services を import できるようにする）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import bass_to_midi, beat_detector, chord_analyzer, midi_generator, separator

ROOT = Path(__file__).resolve().parent.parent
INPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "temp" / "sample.wav"
WORK = ROOT / "temp" / "pipeline_test"


def main() -> None:
    if not INPUT.exists():
        print(f"入力音声ファイルが見つかりません: {INPUT}")
        print("先に scripts/generate_sample.py を実行してサンプル音源を生成してください。")
        sys.exit(1)

    WORK.mkdir(parents=True, exist_ok=True)
    stems_dir = WORK / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)

    # 1. 音源分離（Demucs）
    print("[1/5] 音源分離 (Demucs)...")
    stem_files = separator.separate_audio(str(INPUT), str(stems_dir))
    stems = {Path(p).stem: p for p in stem_files}
    print(f"  分離完了: {list(stems.keys())}")

    # 2. テンポ・ビート検出（Drums トラック）
    print("[2/5] テンポ・ビート検出...")
    beat_info = beat_detector.detect_beats(stems["drums"])
    print(f"  BPM: {beat_info['bpm']} / ビート数: {len(beat_info['beats'])}")

    # 3. ベース MIDI 変換（Basic Pitch）
    print("[3/5] ベース MIDI 変換 (Basic Pitch)...")
    bass_midi = WORK / "bass.mid"
    bass_to_midi.bass_to_midi(stems["bass"], str(bass_midi))
    bass_notes = bass_to_midi.extract_notes_from_midi(str(bass_midi))
    print(f"  ベースノート数: {len(bass_notes)}")

    # 4. コード進行推定（Other トラック）
    print("[4/5] コード進行推定...")
    chords = chord_analyzer.analyze_chords(stems["other"])
    print(f"  コード数: {len(chords)}")
    for c in chords[:6]:
        print(f"    {c['start']:.1f}-{c['end']:.1f}s: {c['chord']}")

    # 5. マルチトラック MIDI 生成
    print("[5/5] マルチトラック MIDI 生成...")
    out = WORK / "multitrack.mid"
    midi_generator.generate_multitrack_midi(
        chords, bass_notes, beat_info["beats"], beat_info["bpm"], str(out)
    )
    print(f"  生成完了: {out} ({out.stat().st_size} bytes)")
    print("\n=== パイプライン全体のテストが成功しました ===")


if __name__ == "__main__":
    main()
