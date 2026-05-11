# Beat Dodge Implementation Status Report (2026-05-11)

## Purpose

This report compares the current repository state against the project plan in `docs/multiplayer_camera_music_game_project_plan.md`, and estimates what remains to make Beat Dodge playable in a typical living room setup.

## Executive Summary

- Estimated implementation against Milestones 1-6: **~47% complete** (rough planning issue coverage, not code line count).
- Current playability: **keyboard-playable prototype is working**.
- Current blocker for living room camera gameplay: **camera-to-game action pipeline is not implemented**.
- Fastest path to living-room playability: implement camera movement classification, stream events to Godot, add calibration/setup UX, and provide one-command launch scripts.

## Current State By Milestone

## Milestone 1 - Project Foundation

Estimated: **4/8 (~50%)**

Implemented:
- Repository structure exists for game, services, docs, schemas, courses, songs, tools.
- Root README documents vision, MVP, and local setup at a high level.
- JSON schemas exist for course and camera frame payloads.

Missing or partial:
- Planned docs (`architecture.md`, `gameplay-design.md`, schema-focused docs) are not present.
- Root `.gitignore` is not present (service-level ignores exist only).

## Milestone 2 - Song Analyzer and Course Generator

Estimated: **12/16 (~75%)**

Implemented:
- Song analyzer service exists with CLI and tests.
- Analysis includes duration, BPM, beats, and energy windows.
- Course generator exists and emits schema-aligned JSON.
- Player assignment alternates between `player_1` and `player_2`.

Missing or partial:
- Difficulty levels (easy/normal/hard) are not implemented.
- Impossible-sequence prevention rules are not implemented.
- Energy-aware prompt density is not implemented (currently one prompt per beat).
- `courses/generated/` has no generated sample output committed.

## Milestone 3 - Keyboard-Playable Game Prototype

Estimated: **14/16 (~88%)**

Implemented:
- Godot 4 project with runtime script and main scene.
- Course JSON loading, audio loading/playback, and timeline sync.
- Prompt spawn/motion per event in two lanes.
- Two-player keyboard controls implemented.
- Scoring windows (perfect/good/early-late/miss), combo, per-player score UI, and results overlay.

Missing or partial:
- Main menu is not implemented.
- Pause/restart flow is not implemented.

## Milestone 4 - Camera Input MVP

Estimated: **8/26 (~31%)**

Implemented:
- Camera input Python service with OpenCV capture and MediaPipe pose detection.
- Two-lane split processing and player assignment by lane.
- Debug overlay with skeleton and lane boundaries.
- Landmark extraction for move-related joints.

Missing or partial (critical):
- Movement detection actions are not implemented (`jump`, `duck`, `lean`, `handsUp`, `freeze`).
- Confidence thresholding and temporal smoothing are not implemented.
- No Godot WebSocket/UDP listener for camera events.
- No mapping from camera events to runtime actions.
- No camera connection status, lane calibration screen, or tracking confidence UI in game.
- No tracking-loss fallback behavior in runtime.

## Milestone 5 - Playtest Polish

Estimated: **2/15 (~13%)**

Implemented:
- Basic lane color differentiation in gameplay scene.
- Basic text-based hit feedback and end-of-round results.

Missing:
- SFX for scoring states, richer hit feedback, combo celebrations, prompt icons/avatars.
- End-of-song celebration and explicit try-again flow.
- Parent-friendly setup flow, calibration, lighting/frame warnings, troubleshooting screen.

## Milestone 6 - Packaging and Demo

Estimated: **1/7 (~14%)**

Implemented:
- Sample non-copyright audio placeholder exists (`game/godot-project/audio/sample_tone.wav`).

Missing:
- One-command setup script for Python services.
- One-command course generation script.
- One-command camera service script.
- Godot export presets for desktop targets.
- Demo instructions for non-developers.

## Living Room Readiness Assessment

Status: **Not yet living-room playable with camera input.**

What works today:
- Two players can play the lane game with keyboard fallback.
- Song analysis and course generation pipeline exists.

What blocks real living-room use:
- No camera-derived gameplay actions are produced.
- No runtime network integration for camera events.
- No setup/calibration UX for non-developer operation.
- No one-command launch flow for parent/kid use.

## Recommended Remaining Work (Priority Order)

1. Implement camera movement classifier in `services/camera-input`:
   - detect `jump`, `duck`, `leanLeft`, `leanRight`, `leftHandUp`, `rightHandUp`, `handsUp`, `freeze`
   - include action confidence, thresholding, and short smoothing window
2. Add camera event transport:
   - emit action events over WebSocket (preferred) from camera service
   - define and validate action-event schema
3. Integrate camera input into Godot runtime:
   - add WebSocket client/listener
   - map camera actions to existing `_handle_action_input` flow
   - keep keyboard fallback togglable
4. Add setup/calibration UX in game:
   - camera connection status
   - lane calibration/stand-here guidance
   - tracking confidence and basic warnings (lighting/body in frame)
5. Add minimal production usability:
   - pause/restart and try-again flow
   - one-command scripts in `tools/` (setup, generate course, run camera)
   - desktop export presets and short demo runbook

## Suggested MVP-Playable Definition (Living Room)

Treat the game as living-room playable when all are true:

- Two players complete a full song round using camera controls only.
- Median action recognition latency is acceptable for kid play (target less than ~300 ms end-to-end).
- Tracking loss recovers gracefully without breaking the round.
- Setup from clone to play is possible in under 15 minutes from documented steps.
- Parent can run: generate course -> start camera service -> start game, without code edits.

## Confidence and Caveats

- This assessment is based on repository inspection of code/docs/tests.
- Automated tests were not executed here because `pytest` is not installed in the current environment.
- Completion percentages are planning-progress estimates derived from project-plan issue checklists.