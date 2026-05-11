"""song_analyzer — Python song analysis service for Beat Dodge."""

from song_analyzer.analyzer import analyze
from song_analyzer.course_generator import MovementPrompt, beats_to_prompts, generate_course

__all__ = ["analyze", "MovementPrompt", "beats_to_prompts", "generate_course"]
