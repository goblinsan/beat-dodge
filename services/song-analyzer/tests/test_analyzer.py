"""Tests for the song-analyzer service.

A synthetic WAV file (a short sine-wave tone) is generated in a temporary
directory so no real audio asset is required.
"""

from __future__ import annotations

import json
import os
import struct
import tempfile
import wave

import numpy as np
import pytest

from song_analyzer.analyzer import analyze
from song_analyzer.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_beat_wav(
    path: str,
    duration: float = 5.0,
    sr: int = 22050,
    bpm: float = 120.0,
    freq: float = 440.0,
) -> None:
    """Write a mono PCM-16 WAV file with a sine tone and periodic beat impulses.

    The impulses make the rhythm detectable by librosa's beat tracker.
    """
    n_samples = int(sr * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    # Background sine tone (quiet)
    audio = (np.sin(2 * np.pi * freq * t) * 0.2).astype(np.float32)

    # Periodic click at every beat (10 ms burst at full amplitude)
    beat_interval_samples = int(sr * 60.0 / bpm)
    click_len = int(sr * 0.01)
    num_beats = int(duration * bpm / 60.0)
    for i in range(num_beats):
        start = i * beat_interval_samples
        end = min(start + click_len, n_samples)
        audio[start:end] = 0.9

    samples = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


@pytest.fixture(scope="module")
def sine_wav(tmp_path_factory) -> str:
    """Return path to a temporary 5-second rhythmic WAV file (120 BPM)."""
    tmp = tmp_path_factory.mktemp("audio")
    path = str(tmp / "beat.wav")
    _write_beat_wav(path, duration=5.0, bpm=120.0)
    return path


# ---------------------------------------------------------------------------
# analyzer.analyze() tests
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_returns_required_keys(self, sine_wav):
        result = analyze(sine_wav)
        assert set(result.keys()) == {
            "version",
            "source",
            "duration_seconds",
            "bpm",
            "beats",
            "energy_windows",
        }

    def test_version_is_string(self, sine_wav):
        result = analyze(sine_wav)
        assert isinstance(result["version"], str)

    def test_source_is_basename(self, sine_wav):
        result = analyze(sine_wav)
        assert result["source"] == os.path.basename(sine_wav)

    def test_duration_is_positive_float(self, sine_wav):
        result = analyze(sine_wav)
        assert isinstance(result["duration_seconds"], float)
        assert result["duration_seconds"] > 0

    def test_duration_approximately_correct(self, sine_wav):
        result = analyze(sine_wav)
        assert abs(result["duration_seconds"] - 5.0) < 0.1

    def test_bpm_is_positive_float(self, sine_wav):
        result = analyze(sine_wav)
        assert isinstance(result["bpm"], float)
        assert result["bpm"] > 0

    def test_beats_is_list_of_floats(self, sine_wav):
        result = analyze(sine_wav)
        assert isinstance(result["beats"], list)
        for b in result["beats"]:
            assert isinstance(b, float)

    def test_beats_within_duration(self, sine_wav):
        result = analyze(sine_wav)
        for b in result["beats"]:
            assert 0.0 <= b <= result["duration_seconds"]

    def test_energy_windows_non_empty(self, sine_wav):
        result = analyze(sine_wav)
        assert len(result["energy_windows"]) > 0

    def test_energy_window_keys(self, sine_wav):
        result = analyze(sine_wav)
        for w in result["energy_windows"]:
            assert set(w.keys()) == {"start_seconds", "end_seconds", "energy", "level"}

    def test_energy_window_times_ascending(self, sine_wav):
        result = analyze(sine_wav)
        windows = result["energy_windows"]
        for i in range(1, len(windows)):
            assert windows[i]["start_seconds"] >= windows[i - 1]["start_seconds"]

    def test_energy_window_end_gte_start(self, sine_wav):
        result = analyze(sine_wav)
        for w in result["energy_windows"]:
            assert w["end_seconds"] >= w["start_seconds"]

    def test_energy_level_range(self, sine_wav):
        result = analyze(sine_wav)
        for w in result["energy_windows"]:
            assert 1 <= w["level"] <= 5

    def test_energy_is_non_negative(self, sine_wav):
        result = analyze(sine_wav)
        for w in result["energy_windows"]:
            assert w["energy"] >= 0.0

    def test_result_is_json_serialisable(self, sine_wav):
        result = analyze(sine_wav)
        serialised = json.dumps(result)
        parsed = json.loads(serialised)
        assert parsed["bpm"] == result["bpm"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            analyze(str(tmp_path / "no_such_file.wav"))


# ---------------------------------------------------------------------------
# cli.main() tests
# ---------------------------------------------------------------------------

class TestCli:
    def test_cli_prints_json_to_stdout(self, sine_wav, capsys):
        main([sine_wav])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "bpm" in parsed
        assert "beats" in parsed

    def test_cli_writes_json_to_file(self, sine_wav, tmp_path):
        out_file = str(tmp_path / "result.json")
        main([sine_wav, "--output", out_file])
        assert os.path.isfile(out_file)
        with open(out_file) as fh:
            parsed = json.load(fh)
        assert "energy_windows" in parsed

    def test_cli_missing_file_exits_nonzero(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            main([str(tmp_path / "no_such_file.wav")])
        assert exc_info.value.code != 0
