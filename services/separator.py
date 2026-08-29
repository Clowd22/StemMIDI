"""Demucs による音源分離（Bass / Drums / Other）モジュール。"""
from __future__ import annotations

import os
from typing import List

import demucs.api

# Demucs が分離するステム名（Vocals は今回使用しない）
STEMS = ["bass", "drums", "other"]


def separate_audio(
    input_path: str,
    output_dir: str,
    model_name: str = "htdemucs",
    device: str | None = None,
    verbose: bool = False,
) -> List[str]:
    """
    音声ファイルを Demucs で分離し、指定ディレクトリに WAV として保存する。

    Args:
        input_path: 入力音声ファイルのパス。
        output_dir: 分離結果の保存先ディレクトリ。
        model_name: Demucs モデル名（デフォルト: htdemucs）。
        device: 推論デバイス（"cpu" / "cuda"）。None なら自動選択。
        verbose: Demucs のログ出力を有効にするか。

    Returns:
        生成されたステム WAV ファイルのパス一覧（bass / drums / other）。
    """
    os.makedirs(output_dir, exist_ok=True)

    separator = demucs.api.Separator(model=model_name, device=device or "cpu", verbose=verbose)
    # Demucs は (原音波形, {ステム名: 波形}) を返す
    _, separated = separator.separate_audio_file(input_path)

    output_files: List[str] = []
    for stem in STEMS:
        if stem not in separated:
            continue
        stem_path = os.path.join(output_dir, f"{stem}.wav")
        demucs.api.save_audio(
            separated[stem],
            stem_path,
            samplerate=separator.samplerate,
        )
        output_files.append(stem_path)

    return output_files
