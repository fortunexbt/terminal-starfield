# Changelog

## 4.0.0 — Odyssey

### Added

- Procedural planets, orbital rings, and ruins with shaded 3D ship and flagship geometry
- Three distinct flagships: The Null Engine, Archon Prime, and Void Seraph, each with three attack patterns
- Branching sector destinations with heat, plasma, salvage, hull, and repair modifiers
- Paid refit repairs, seeker crates, and draft rerolls alongside the free wave upgrade
- Siphon Array, Event Horizon, Arc Relay, and Nova Echo upgrade paths
- Buffered primary fire, `F` autofire, optional `--mouse` controls, and `I` ship systems
- `--demo` pilot-driven attract mode that never records demonstration runs
- Route, jump, boss, and systems snapshot fixtures
- Ruleset, route, accuracy, graze, and boss statistics in completed flight records

### Changed

- Combat advances in fixed 120 Hz steps independently of rendering
- Target alignment, seeker locks, and committed impact markers replace the tactical radar
- Bosses commit both aim and attack pattern before firing; ordinary shooters also telegraph their volleys
- Remaining salvage is collected when a wave clears, including the final victory
- The README documents Odyssey controls, builds, routes, and current screenshots

### Fixed

- Swept collision detection prevents fast projectiles from passing through hulls
- Piercing projectiles damage each target once instead of repeatedly inside its hull
- Fragmented SGR mouse input is decoded safely and mouse reporting is restored on exit
- Pauses and overlays discard elapsed time and buffered weapon input
- Existing flight logs remain readable with optional Odyssey statistics

## 3.1.0 — Flight Deck

### Added

- Three selectable ships: balanced Vanguard, photon specialist Wraith, and nova tank Aegis
- Flight deck with ship schematics, loadout tradeoffs, seed, and personal best
- Three boss health phases: committed-aim Lance, Fan, and Crossfire attacks with visible warnings
- Local flight history, personal bests, and detailed end-of-run debriefs
- `--ship`, `--records`, `--record-file`, `--no-record`, and `--snapshot-screen`

### Fixed

- Bosses hold engagement depth and must be destroyed to advance
- Combat randomness is independent of star density, visual settings, and time on the title screen
- Restart replays the same seed and ship; seeds are shown for reproducible runs
- Completed combat runs are saved once, with bounded history and atomic, serialized writes
- Paused flight rejects combat actions and movement
- Fragmented and batched arrow-key sequences retain every input
- Small terminals expose menu selections and all three upgrade choices
- ASCII mode covers the entire frame, including boxes and help
- Capped upgrades leave the draft pool; fabricators refill three missiles per level without reducing stock

## 3.0.0 — Rogue

Voyager has become a complete terminal arcade roguelite.

### Added

- Animated title screen with Campaign, Endless, and Zen Drift modes
- Fifteen-wave campaign across three sectors with named boss encounters
- Photon arrays with heat/overheat, homing seekers, nova pulse, and vector boost
- Scouts, hunters, frigates, boss archetypes, enemy plasma, collisions, and tactical radar
- Repair, reactor, missile, and void-cache pickups
- Nine stackable upgrade families with three-choice wave drafts
- Full score, kill-chain, shield, heat, energy, missile, threat, wave, and boss telemetry
- Dedicated upgrade, victory, game-over, pause, and context-aware help screens
- Deterministic `advance_time()` and `render_game_to_text()` hooks
- `--mode` and `--state-snapshot` automation options
- Full 15-wave automated campaign verification

### Changed

- Space now fires the primary weapon in combat; vector boost moved to `B`
- Snapshots now showcase campaign combat by default
- Modal surfaces own their interiors for clean readability over live animation
- The package and console command are now version 3.0.0

## 2.0.0 — Voyager

Terminal Starfield is now a complete deep-space flight console while retaining its zero-dependency, one-command launch.

### Added

- Inertial two-axis steering and variable throttle
- Energy-powered vector boost with depth-scaled star streaks
- Signal capture, debris evasion, shields, scoring, combos, and sectors
- Responsive cockpit HUD, flight manual, pause, and end-of-voyage overlays
- Four live true-color themes, Unicode art, and ASCII/monochrome fallbacks
- HUD-free Zen Drift mode
- Deterministic seeds and non-interactive snapshot rendering
- Installable `starfield` command through `pyproject.toml`
- Automated simulation, renderer, control, and viewport tests
- Linux/macOS CI across Python 3.9 and 3.13

### Changed

- Split the original monolith into simulation, renderer, and terminal-runtime layers
- Replaced retained trail particles with projection-derived light streaks
- Moved rendering into the terminal alternate screen and hardened state restoration
- Reworked controls around flight while keeping density presets, themes, trails, reset, and quit
