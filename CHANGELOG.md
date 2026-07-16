# Changelog

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
