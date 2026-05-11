# Multiplayer Camera Music Game — GitHub Project Plan

## Working Title

**Beat Dodge**

A 2-player camera-based PC party game where kids move in lanes to dodge, duck, jump, freeze, and pose in sync with a dynamically generated course created from any song.

---

## Product Goal

Build a fun, kid-friendly PC game that uses a webcam to track two players in side-by-side lanes. Players respond to rhythm-based movement prompts generated automatically from an input song.

The MVP should prioritize:

1. Fun gameplay over perfect motion accuracy.
2. Two-player lane-based tracking.
3. Automatic song-to-course generation.
4. Forgiving scoring.
5. Fast iteration with keyboard fallback before camera integration.

---

## Core User Experience

1. User selects a song file.
2. System analyzes the song for tempo, beats, energy, and sections.
3. Game generates a movement course.
4. Two players stand in left/right lanes in front of a webcam.
5. Obstacles/prompts arrive in sync with music.
6. Players jump, duck, lean, freeze, or raise hands.
7. System scores each player independently.
8. Results screen shows score, combo, misses, and “best move” moments.

---

## Recommended MVP Stack

### Game Engine

**Godot 4**

Reasons:

- Great for 2D rhythm/runner-style games.
- Lightweight and fast to iterate.
- Easy PC export.
- Good JSON loading and audio playback.
- Open source.

### Camera / Pose Tracking

**Python + MediaPipe + OpenCV**

Responsibilities:

- Read webcam frames.
- Detect up to 2 player skeletons.
- Assign Player 1 / Player 2 by lane.
- Emit movement events over WebSocket or UDP.

### Song Analysis / Course Generation

**Python + librosa**

Responsibilities:

- Load song file.
- Estimate BPM.
- Detect beat timestamps.
- Estimate energy levels.
- Detect likely high-energy moments.
- Generate JSON course file.

### Runtime Communication

Recommended first version:

- Godot reads generated course JSON.
- Godot receives camera movement events from Python over WebSocket.
- Keyboard fallback remains enabled for development and debugging.

---

## High-Level Architecture

```text
Song File
   ↓
Audio Analyzer
   ↓
Course Generator
   ↓
Course JSON
   ↓
Godot Game Runtime ← Camera Input Service
                          ↑
                       Webcam
```

---

## Main Components

### 1. Game Runtime

The Godot game handles:

- Song playback.
- Course timeline.
- Prompt spawning.
- Player state.
- Scoring.
- UI and results screen.
- Keyboard fallback controls.
- Camera input event integration.

### 2. Audio Analyzer

The analyzer handles:

- Tempo estimation.
- Beat detection.
- Song duration.
- Onset strength.
- Energy windows.
- Section-like changes.

The MVP should not try to perfectly identify verses and choruses. Instead, use energy and beat density to create gameplay intensity.

### 3. Course Generator

The course generator converts song analysis into gameplay events.

Examples:

- Big beat → both players jump.
- Low energy → fewer prompts.
- High energy → denser prompts.
- Quiet section → freeze pose.
- Alternating beats → Player 1 / Player 2 call-and-response.

### 4. Camera Input Service

The camera service handles:

- Webcam capture.
- Pose detection.
- Lane assignment.
- Movement detection.
- Confidence scoring.
- Event publishing.

It should not know game rules. It should only emit movement events.

---

## Course JSON Format

```json
{
  "schemaVersion": 1,
  "song": {
    "title": "example-song",
    "file": "songs/example.mp3",
    "durationSec": 182.4,
    "bpm": 124
  },
  "players": 2,
  "difficulty": "normal",
  "events": [
    {
      "timeSec": 3.25,
      "player": "both",
      "move": "jump",
      "intensity": 0.8
    },
    {
      "timeSec": 5.18,
      "player": 1,
      "move": "duck",
      "intensity": 0.6
    },
    {
      "timeSec": 5.18,
      "player": 2,
      "move": "leanRight",
      "intensity": 0.6
    }
  ]
}
```

---

## Movement Event Format

The camera service should emit events like:

```json
{
  "timestampMs": 124350,
  "players": [
    {
      "id": 1,
      "action": "jump",
      "confidence": 0.91
    },
    {
      "id": 2,
      "action": "duck",
      "confidence": 0.87
    }
  ]
}
```

Supported MVP actions:

- `jump`
- `duck`
- `leanLeft`
- `leanRight`
- `leftHandUp`
- `rightHandUp`
- `handsUp`
- `freeze`

---

## MVP Scope

### In Scope

- 2-player lane-based gameplay.
- PC game.
- Webcam input.
- Keyboard fallback input.
- Song file import.
- Automatic beat-based course generation.
- Simple scoring.
- Results screen.
- Configurable difficulty.
- Forgiving movement detection.

### Out of Scope for MVP

- Xbox support.
- 4-player support.
- Free-roaming identity tracking.
- Perfect dance choreography scoring.
- Online multiplayer.
- Mobile app.
- Real-time song analysis during gameplay.
- Advanced ML choreography generation.

---

## Gameplay Design

### Player Layout

```text
TV / Monitor
Camera centered above or below screen

[ Player 1 Lane ]    [ Player 2 Lane ]
```

### MVP Modes

#### Mode 1: Beat Dodge

Players respond to obstacles coming down their lane.

Examples:

- Low bar → duck.
- Floor hazard → jump.
- Left wall → lean right.
- Right wall → lean left.
- Spotlight → freeze.
- Star beat → hands up.

#### Mode 2: Mirror Battle

Both players get similar prompts and compete for accuracy.

#### Mode 3: Call-and-Response

Player 1 and Player 2 alternate movements on beat.

---

## Scoring Model

### Timing Windows

- Perfect: within ±150 ms.
- Good: within ±300 ms.
- Late/Early: within ±500 ms.
- Miss: no valid movement in window.

### Score Values

- Perfect: 100 points.
- Good: 70 points.
- Early/Late: 30 points.
- Miss: 0 points.

### Combo

- Consecutive successful moves increase combo.
- Miss resets combo.
- Confidence below threshold can downgrade result instead of causing instant miss.

### Kid-Friendly Forgiveness

Rules:

- Do not punish brief tracking loss.
- Accept exaggerated movement.
- Prefer false positives over frustrating false misses.
- Allow each prompt to have a generous activation window.

---

## Course Generation Rules

### Basic Rules

- Generate prompts on beat timestamps.
- Avoid impossible sequences.
- Avoid too many jumps in a row.
- Avoid jump immediately followed by duck unless spacing is long enough.
- Give both players roughly equal activity.
- Increase density during high-energy sections.
- Decrease density during low-energy sections.

### Difficulty Levels

#### Easy

- Prompts every 4 beats.
- Mostly jump, duck, hands up.
- Fewer split-player prompts.

#### Normal

- Prompts every 2–4 beats.
- Includes lean left/right.
- Some call-and-response.

#### Hard

- Prompts every 1–2 beats.
- More alternating player prompts.
- More combo chains.

---

## Repository Structure

```text
beat-dodge/
  README.md
  docs/
    architecture.md
    gameplay-design.md
    course-schema.md
    camera-input-schema.md
    song-analysis.md
  game/
    godot-project/
  services/
    camera-input/
      README.md
      requirements.txt
      src/
    song-analyzer/
      README.md
      requirements.txt
      src/
  courses/
    generated/
    samples/
  songs/
    .gitkeep
  tools/
    generate-course.sh
    run-camera-service.sh
  .github/
    workflows/
      ci.yml
```

Important: do not commit copyrighted songs. Keep `songs/` ignored except for `.gitkeep`.

---

## GitHub Milestones and Epics

## Milestone 1 — Project Foundation

Goal: Create the repo, docs, schemas, and basic local development workflow.

### Epic 1: Repository and Documentation Setup

Issues:

1. Create initial repository structure.
2. Add README with product vision and MVP scope.
3. Add architecture document.
4. Add gameplay design document.
5. Add course JSON schema document.
6. Add camera input event schema document.
7. Add local development instructions.
8. Add `.gitignore` for songs, generated files, Python caches, and Godot artifacts.

Acceptance Criteria:

- Repo has clear structure.
- MVP scope is documented.
- Developers can understand the architecture without reading code.

---

## Milestone 2 — Song Analyzer and Course Generator

Goal: Generate playable course JSON from a song file.

### Epic 2: Audio Analysis Pipeline

Issues:

1. Set up Python song analyzer package.
2. Add CLI for analyzing a song file.
3. Extract song duration.
4. Estimate BPM.
5. Detect beat timestamps.
6. Calculate energy over time windows.
7. Identify high-energy moments.
8. Export raw analysis JSON.

Acceptance Criteria:

- Running the analyzer on a song outputs BPM, duration, beat timestamps, and energy data.

### Epic 3: Course Generation Engine

Issues:

1. Define internal movement prompt model.
2. Convert beat timestamps into movement prompts.
3. Add difficulty settings.
4. Add player balancing logic.
5. Add impossible-sequence prevention.
6. Add energy-aware prompt density.
7. Export final course JSON.
8. Add sample generated courses.

Acceptance Criteria:

- A song file can produce a valid course JSON.
- Course includes events for both players.
- Course avoids obviously impossible movement chains.

---

## Milestone 3 — Keyboard-Playable Game Prototype

Goal: Build the game loop before camera integration.

### Epic 4: Godot Game Foundation

Issues:

1. Create Godot 4 project.
2. Implement main menu.
3. Load course JSON.
4. Load and play song file.
5. Implement game timeline synchronized to song playback.
6. Spawn movement prompts based on course events.
7. Add two-player lane visuals.
8. Add pause/restart flow.

Acceptance Criteria:

- Game can load a course and play it in sync with the song.

### Epic 5: Keyboard Input and Scoring

Issues:

1. Add keyboard controls for Player 1.
2. Add keyboard controls for Player 2.
3. Implement movement action events.
4. Implement scoring windows.
5. Add combo tracking.
6. Add per-player score UI.
7. Add miss/good/perfect feedback.
8. Add results screen.

Acceptance Criteria:

- Two players can play the game using keyboard controls.
- Scoring works independently per player.

---

## Milestone 4 — Camera Input MVP

Goal: Replace keyboard input with webcam-based movement events while preserving keyboard fallback.

### Epic 6: Camera Pose Tracking Service

Issues:

1. Set up Python camera input service.
2. Capture webcam frames with OpenCV.
3. Run MediaPipe pose detection.
4. Detect up to two player bodies.
5. Assign Player 1 and Player 2 by left/right lane.
6. Draw debug skeleton overlay.
7. Calculate body landmarks needed for MVP moves.
8. Emit debug telemetry for pose confidence.

Acceptance Criteria:

- Two players are detected and assigned to lanes.
- Debug view shows pose landmarks and player IDs.

### Epic 7: Movement Detection

Issues:

1. Detect jump.
2. Detect duck.
3. Detect lean left.
4. Detect lean right.
5. Detect left hand up.
6. Detect right hand up.
7. Detect both hands up.
8. Detect freeze / stillness.
9. Add confidence thresholding.
10. Add smoothing to avoid noisy detections.

Acceptance Criteria:

- Camera service emits useful movement events for both players.
- Events are stable enough for kids to play simple prompts.

### Epic 8: Game Integration

Issues:

1. Add WebSocket or UDP listener to Godot.
2. Parse camera movement events.
3. Map camera events to game actions.
4. Preserve keyboard fallback mode.
5. Add camera connection status UI.
6. Add calibration screen for player lanes.
7. Add tracking confidence indicators.
8. Add fallback behavior when tracking is lost.

Acceptance Criteria:

- Game can be played by two players using camera input.
- Keyboard fallback remains available.

---

## Milestone 5 — Playtest Polish

Goal: Make the MVP fun and usable by kids.

### Epic 9: Kid-Friendly Game Feel

Issues:

1. Add sound effects for perfect/good/miss.
2. Add visual hit feedback.
3. Add combo celebration effects.
4. Add simple character avatars.
5. Add lane color themes.
6. Add clear prompt icons.
7. Add end-of-song celebration.
8. Add “try again” flow.

Acceptance Criteria:

- Kids can understand what to do without instructions.
- Feedback feels fun and encouraging.

### Epic 10: Calibration and Setup

Issues:

1. Add setup screen for camera positioning.
2. Add lane boundary visualization.
3. Add “stand here” player calibration.
4. Add lighting quality warning.
5. Add full-body-in-frame warning.
6. Add tracking confidence meter.
7. Add simple troubleshooting screen.

Acceptance Criteria:

- A parent can set up the game in a living room without developer help.

---

## Milestone 6 — Packaging and Demo

Goal: Create a shareable local demo build.

### Epic 11: Local Packaging

Issues:

1. Add one-command setup script for Python dependencies.
2. Add one-command course generation script.
3. Add one-command camera service script.
4. Add Godot export preset for Windows.
5. Add Godot export preset for macOS if needed.
6. Add sample non-copyright test audio or placeholder beat track.
7. Add demo instructions.

Acceptance Criteria:

- Project can be run locally from documented steps.
- Demo build can be launched by a non-developer.

---

## Future Milestones

### Future Milestone — 4 Player Support

Potential issues:

1. Add configurable player count.
2. Add four-lane layout.
3. Add 4-player course generation balancing.
4. Add wide-camera setup mode.
5. Add multi-player tracking confidence UI.
6. Add 4-player results screen.

### Future Milestone — Better Music Intelligence

Potential issues:

1. Detect song sections.
2. Detect drops.
3. Detect chorus-like repeated sections.
4. Use ML-assisted section labeling.
5. Generate more intentional movement sequences.
6. Add manual course editor.

### Future Milestone — Multi-Camera Support

Potential issues:

1. Add camera abstraction layer.
2. Support multiple camera feeds.
3. Synchronize camera frames.
4. Fuse pose confidence across cameras.
5. Improve occlusion recovery.

### Future Milestone — Xbox / Controller Bridge Exploration

Potential issues:

1. Research Xbox Adaptive Controller integration.
2. Prototype hardware input bridge.
3. Map camera actions to HID joystick/gamepad events.
4. Validate two-player controller support.

---

## Technical Risks

### Risk: Pose tracking swaps players

Mitigation:

- Start with lane-based identity.
- Add lane calibration.
- Add warning when players cross lanes.

### Risk: Camera misses movements

Mitigation:

- Use forgiving scoring.
- Use smoothing.
- Use exaggerated movement prompts.
- Show confidence UI.

### Risk: Generated courses feel random

Mitigation:

- Use rule-based generation.
- Avoid impossible sequences.
- Use energy-aware density.
- Add manual seed and difficulty tuning.

### Risk: Song synchronization feels off

Mitigation:

- Use Godot audio playback time as source of truth.
- Add configurable input latency offset.
- Add calibration test.

### Risk: Copyrighted music handling

Mitigation:

- Do not commit songs.
- Use local-only song import.
- Include only royalty-free or generated demo audio.

---

## Development Strategy

Recommended build sequence:

1. Build course generator first.
2. Build keyboard-playable game second.
3. Add camera service third.
4. Polish gameplay fourth.

Reason:

The game must be fun even before camera tracking works. Keyboard fallback gives a reliable baseline and makes debugging easier.

---

## MVP Definition of Done

The MVP is complete when:

1. A user can select or provide a song file.
2. The system generates a playable course.
3. Two players can play using keyboard controls.
4. Two players can play using webcam controls.
5. The game tracks independent scores.
6. The course feels loosely synchronized to the song.
7. The game has setup/calibration instructions.
8. The result is fun enough for kids to replay.

---

## Suggested GitHub Labels

- `epic`
- `mvp`
- `game-runtime`
- `song-analysis`
- `course-generation`
- `camera-input`
- `pose-tracking`
- `scoring`
- `ui`
- `polish`
- `documentation`
- `future`
- `risk`

---

## Suggested GitHub Project Fields

- Status: Backlog, Ready, In Progress, Review, Done
- Milestone
- Epic
- Priority: P0, P1, P2, P3
- Area: Game, Camera, Audio, Tooling, Docs
- MVP: Yes/No

---

## Suggested First 10 Issues

1. Create repository structure and initial README.
2. Document MVP architecture.
3. Create course JSON schema.
4. Create camera input event schema.
5. Set up Python song analyzer package.
6. Implement BPM and beat detection CLI.
7. Generate first course JSON from a song.
8. Create Godot project and load course JSON.
9. Implement keyboard-playable two-player prototype.
10. Set up Python camera service with skeleton overlay.

---

## Copilot Implementation Prompt

Use this prompt to start implementation with GitHub Copilot or an agent:

```text
We are building a PC-based 2-player camera music game called Beat Dodge.

The MVP uses Godot 4 for the game, Python + librosa for song analysis/course generation, and Python + MediaPipe + OpenCV for webcam pose tracking.

Start by creating the repository structure from the project plan. Then implement the song analyzer and course generator first. The generator should take a local song file and output a course JSON with song duration, estimated BPM, beat timestamps converted into movement events, player assignments, move type, and intensity.

Do not implement camera tracking yet. The first playable game should work with keyboard fallback controls for two players.

Prioritize clean schemas, simple local scripts, and documentation. Do not commit copyrighted songs.
```
