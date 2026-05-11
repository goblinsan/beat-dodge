"""Core audio analysis logic for the song-analyzer service.

Extracts:
- duration (seconds)
- BPM (tempo)
- beat timestamps (seconds)
- energy windows (1-second slices, each with an RMS energy value and a
  normalised intensity level 1–5)
- the full structured result as a JSON-serialisable dict (raw analysis)
"""

from __future__ import annotations

import os
from typing import Any

import librosa
import numpy as np

#: Width of each energy window in seconds.
ENERGY_WINDOW_SECONDS: float = 1.0


def analyze(song_path: str) -> dict[str, Any]:
    """Analyze *song_path* and return a structured analysis dict.

    Parameters
    ----------
    song_path:
        Absolute or relative path to an audio file supported by librosa
        (MP3, WAV, FLAC, OGG, …).

    Returns
    -------
    dict with keys:
        ``version``, ``source``, ``duration_seconds``, ``bpm``,
        ``beats``, ``energy_windows``.

    Raises
    ------
    FileNotFoundError
        If *song_path* does not exist.
    """
    if not os.path.isfile(song_path):
        raise FileNotFoundError(f"Audio file not found: {song_path}")

    y, sr = librosa.load(song_path, mono=True)

    # Duration
    duration: float = float(librosa.get_duration(y=y, sr=sr))

    # BPM + beat frames
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    bpm: float = float(np.atleast_1d(tempo)[0])
    beats: list[float] = [
        round(float(t), 3)
        for t in librosa.frames_to_time(beat_frames, sr=sr)
    ]

    # Energy windows
    energy_windows = _compute_energy_windows(y, sr, duration)

    return {
        "version": "1.0.0",
        "source": os.path.basename(song_path),
        "duration_seconds": round(duration, 3),
        "bpm": round(bpm, 2),
        "beats": beats,
        "energy_windows": energy_windows,
    }


def _compute_energy_windows(
    y: np.ndarray,
    sr: int,
    duration: float,
) -> list[dict[str, Any]]:
    """Split *y* into fixed-length windows and compute RMS energy for each.

    Energy values are normalised across the song to an integer intensity
    level in the range **1–5**.
    """
    window_samples = int(sr * ENERGY_WINDOW_SECONDS)
    num_windows = max(1, int(np.ceil(len(y) / window_samples)))

    raw: list[dict[str, Any]] = []
    rms_values: list[float] = []

    for i in range(num_windows):
        start_sample = i * window_samples
        end_sample = min((i + 1) * window_samples, len(y))
        chunk = y[start_sample:end_sample]

        rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
        start_sec = round(start_sample / sr, 3)
        end_sec = round(min(end_sample / sr, duration), 3)

        raw.append(
            {
                "start_seconds": start_sec,
                "end_seconds": end_sec,
                "energy": round(rms, 6),
                "level": 1,  # placeholder; set after normalisation
            }
        )
        rms_values.append(rms)

    # Normalise RMS to integer levels 1–5
    e_min = min(rms_values)
    e_max = max(rms_values)
    span = e_max - e_min

    for window, rms in zip(raw, rms_values):
        if span > 0:
            normalised = (rms - e_min) / span
        else:
            normalised = 0.0
        window["level"] = int(np.clip(round(normalised * 4 + 1), 1, 5))

    return raw
