"""Tests for the course-generation module.

Uses the same synthetic WAV fixture as test_analyzer.py to exercise the
full pipeline (analyze → generate_course) as well as isolated unit tests
for the internal helpers.
"""

from __future__ import annotations

import json
import os
import wave

import numpy as np
import pytest

from song_analyzer.analyzer import analyze
from song_analyzer.course_cli import main as course_main
from song_analyzer.course_generator import (
    MOVES,
    PLAYERS,
    MovementPrompt,
    _energy_level_at,
    beats_to_prompts,
    generate_course,
)


# ---------------------------------------------------------------------------
# Shared fixture (mirrors the one in test_analyzer.py)
# ---------------------------------------------------------------------------

def _write_beat_wav(
    path: str,
    duration: float = 5.0,
    sr: int = 22050,
    bpm: float = 120.0,
    freq: float = 440.0,
) -> None:
    n_samples = int(sr * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    audio = (np.sin(2 * np.pi * freq * t) * 0.2).astype(np.float32)
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
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


@pytest.fixture(scope="module")
def sine_wav(tmp_path_factory) -> str:
    tmp = tmp_path_factory.mktemp("audio_cg")
    path = str(tmp / "beat.wav")
    _write_beat_wav(path, duration=5.0, bpm=120.0)
    return path


@pytest.fixture(scope="module")
def analysis(sine_wav) -> dict:
    return analyze(sine_wav)


# ---------------------------------------------------------------------------
# MovementPrompt dataclass
# ---------------------------------------------------------------------------

class TestMovementPrompt:
    def test_fields_accessible(self):
        p = MovementPrompt(
            time_seconds=1.0,
            player="player_1",
            move="jump",
            intensity=3,
        )
        assert p.time_seconds == 1.0
        assert p.player == "player_1"
        assert p.move == "jump"
        assert p.intensity == 3
        assert p.metadata == {}

    def test_metadata_stored(self):
        p = MovementPrompt(
            time_seconds=2.0,
            player="player_2",
            move="duck",
            intensity=2,
            metadata={"beat_index": 5},
        )
        assert p.metadata["beat_index"] == 5


# ---------------------------------------------------------------------------
# _energy_level_at
# ---------------------------------------------------------------------------

class TestEnergyLevelAt:
    _windows = [
        {"start_seconds": 0.0, "end_seconds": 1.0, "energy": 0.1, "level": 2},
        {"start_seconds": 1.0, "end_seconds": 2.0, "energy": 0.3, "level": 4},
        {"start_seconds": 2.0, "end_seconds": 3.0, "energy": 0.2, "level": 3},
    ]

    def test_exact_start(self):
        assert _energy_level_at(0.0, self._windows) == 2

    def test_mid_window(self):
        assert _energy_level_at(1.5, self._windows) == 4

    def test_boundary_moves_to_next_window(self):
        # 1.0 is the start of the second window (not end of first)
        assert _energy_level_at(1.0, self._windows) == 4

    def test_beyond_last_window_returns_last_level(self):
        assert _energy_level_at(99.0, self._windows) == 3

    def test_empty_windows_returns_one(self):
        assert _energy_level_at(1.0, []) == 1


# ---------------------------------------------------------------------------
# beats_to_prompts
# ---------------------------------------------------------------------------

class TestBeatsToPrompts:
    _windows = [
        {"start_seconds": 0.0, "end_seconds": 1.0, "energy": 0.1, "level": 2},
        {"start_seconds": 1.0, "end_seconds": 2.0, "energy": 0.3, "level": 4},
    ]
    _beats = [0.25, 0.75, 1.25, 1.75]

    def test_returns_one_prompt_per_beat(self):
        prompts = beats_to_prompts(self._beats, self._windows)
        assert len(prompts) == len(self._beats)

    def test_all_are_movement_prompts(self):
        for p in beats_to_prompts(self._beats, self._windows):
            assert isinstance(p, MovementPrompt)

    def test_time_seconds_match_beats(self):
        prompts = beats_to_prompts(self._beats, self._windows)
        for prompt, beat in zip(prompts, self._beats):
            assert prompt.time_seconds == beat

    def test_players_alternate(self):
        prompts = beats_to_prompts(self._beats, self._windows)
        for i, p in enumerate(prompts):
            assert p.player == PLAYERS[i % len(PLAYERS)]

    def test_moves_cycle_through_all(self):
        # With 4 beats the full MOVES cycle should appear once
        prompts = beats_to_prompts(self._beats, self._windows)
        for i, p in enumerate(prompts):
            assert p.move == MOVES[i % len(MOVES)]

    def test_intensity_from_energy_window(self):
        prompts = beats_to_prompts(self._beats, self._windows)
        # First two beats are in window with level 2
        assert prompts[0].intensity == 2
        assert prompts[1].intensity == 2
        # Next two beats are in window with level 4
        assert prompts[2].intensity == 4
        assert prompts[3].intensity == 4

    def test_intensity_in_valid_range(self):
        prompts = beats_to_prompts(self._beats, self._windows)
        for p in prompts:
            assert 1 <= p.intensity <= 5

    def test_metadata_contains_beat_index(self):
        prompts = beats_to_prompts(self._beats, self._windows)
        for i, p in enumerate(prompts):
            assert p.metadata["beat_index"] == i

    def test_empty_beats_returns_empty(self):
        assert beats_to_prompts([], self._windows) == []

    def test_player_balance(self):
        # Roughly equal distribution over an even number of beats
        beats = list(range(8))
        prompts = beats_to_prompts(beats, self._windows)  # type: ignore[arg-type]
        p1 = sum(1 for p in prompts if p.player == "player_1")
        p2 = sum(1 for p in prompts if p.player == "player_2")
        assert p1 == p2


# ---------------------------------------------------------------------------
# generate_course
# ---------------------------------------------------------------------------

class TestGenerateCourse:
    def test_required_top_level_keys(self, analysis):
        course = generate_course(analysis)
        assert set(course.keys()) == {"version", "song", "events"}

    def test_version_is_string(self, analysis):
        assert isinstance(generate_course(analysis)["version"], str)

    def test_song_keys(self, analysis):
        song = generate_course(analysis)["song"]
        assert set(song.keys()) == {"id", "bpm", "duration_seconds"}

    def test_song_id_matches_source(self, analysis):
        course = generate_course(analysis)
        assert course["song"]["id"] == analysis["source"]

    def test_song_bpm_matches_analysis(self, analysis):
        course = generate_course(analysis)
        assert course["song"]["bpm"] == analysis["bpm"]

    def test_song_duration_matches_analysis(self, analysis):
        course = generate_course(analysis)
        assert course["song"]["duration_seconds"] == analysis["duration_seconds"]

    def test_events_is_list(self, analysis):
        assert isinstance(generate_course(analysis)["events"], list)

    def test_event_count_matches_beats(self, analysis):
        course = generate_course(analysis)
        assert len(course["events"]) == len(analysis["beats"])

    def test_event_keys(self, analysis):
        for event in generate_course(analysis)["events"]:
            assert set(event.keys()) == {"time_seconds", "player", "move", "intensity"}

    def test_event_players_valid(self, analysis):
        for event in generate_course(analysis)["events"]:
            assert event["player"] in PLAYERS

    def test_event_moves_valid(self, analysis):
        for event in generate_course(analysis)["events"]:
            assert event["move"] in MOVES

    def test_event_intensity_range(self, analysis):
        for event in generate_course(analysis)["events"]:
            assert 1 <= event["intensity"] <= 5

    def test_events_time_seconds_match_beats(self, analysis):
        course = generate_course(analysis)
        for event, beat in zip(course["events"], analysis["beats"]):
            assert event["time_seconds"] == beat

    def test_result_is_json_serialisable(self, analysis):
        course = generate_course(analysis)
        serialised = json.dumps(course)
        parsed = json.loads(serialised)
        assert parsed["song"]["bpm"] == course["song"]["bpm"]


# ---------------------------------------------------------------------------
# course_cli.main()
# ---------------------------------------------------------------------------

class TestCourseCli:
    def test_cli_prints_json_to_stdout(self, sine_wav, capsys):
        course_main([sine_wav])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "events" in parsed
        assert "song" in parsed

    def test_cli_writes_json_to_file(self, sine_wav, tmp_path):
        out_file = str(tmp_path / "course.json")
        course_main([sine_wav, "--output", out_file])
        assert os.path.isfile(out_file)
        with open(out_file) as fh:
            parsed = json.load(fh)
        assert "events" in parsed

    def test_cli_events_have_required_fields(self, sine_wav, capsys):
        course_main([sine_wav])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        for event in parsed["events"]:
            assert "player" in event
            assert "move" in event
            assert "intensity" in event
            assert "time_seconds" in event

    def test_cli_missing_file_exits_nonzero(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            course_main([str(tmp_path / "no_such_file.wav")])
        assert exc_info.value.code != 0
