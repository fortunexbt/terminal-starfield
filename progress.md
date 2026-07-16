Original prompt: yeah turn it into a full blown terminal game. make it INSANE [@Games](plugin://computer-use@openai-bundled?app=com.apple.games) [$develop-web-game](/Users/fortune/.codex/skills/develop-web-game/SKILL.md)

## Direction

- Keep the shipped product native to the terminal and dependency-free.
- Expand Voyager into a complete arcade roguelite: title/menu flow, combat, enemies, waves, bosses, pickups, upgrade drafts, campaign progression, endless mode, game over, and deterministic test hooks.
- Preserve Zen Drift as the non-combat descendant of the original screensaver.
- Validate in small implementation → input → observe loops, using model-state text plus real PTY visual captures in place of a browser canvas.

## Current state

- Voyager 2.0 baseline passes 9 tests and has a deterministic simulation/renderer split.
- Playable signal/debris loop, responsive HUD, themes, terminal restoration, snapshots, and package entry point already exist.

## TODO

- [x] Add complete menu and run-state machine.
- [x] Add weapons, projectiles, enemy archetypes, pickups, and wave director.
- [x] Add sector bosses, upgrade draft, progression, and endless scaling.
- [x] Build combat HUD, announcements, and richer effects.
- [x] Expose concise deterministic game-state text and scripted action runner.
- [x] Expand tests across full interaction chains and inspect live captures.
- [x] Repackage and document the complete game.

## Iteration 1 — deterministic combat core

- Added Campaign, Endless, Zen, title, playing, upgrade, victory, and game-over states.
- Added scouts, hunters, frigates, named sector bosses, player/enemy projectiles, pickups, and collision chains.
- Added primary heat/overheat, homing missiles, nova pulse, wave director, score/credits/combos, and nine stackable upgrades.
- Added `advance_time(ms)` and `render_game_to_text()` deterministic verification hooks.
- Verification: 13/13 tests pass, including primary fire → enemy death → score and wave clear → draft → apply upgrade → wave 2.

## Iteration 2 — full terminal presentation

- Added animated title/menu, combat HUD, enemy silhouettes/health, boss bar, laser/plasma/missile rendering, pickups, upgrade draft, victory, pause/help, and game-over layers.
- Fixed all modal surfaces to clear their interiors after visual inspection found star glyphs leaking through copy.
- Added keyboard flows for menu, combat abilities, upgrade selection, restart, and title return.
- Added deterministic `--state-snapshot` output alongside visual snapshots.
- Verified a real PTY flow: title → campaign → primary/missile/pulse/boost → wave clear → upgrade → wave 2 → pause/resume → clean exit and TTY restoration.
- Rendered and visually inspected full-color title and boss-combat captures; contrast, hierarchy, boss telegraphing, HUD, and reticle are all readable.
- Verification: 19/19 tests pass.

## Iteration 3 — campaign, scale, and release

- Added tactical radar and verified hostile/pickup plotting.
- Completed a deterministic 15-wave campaign: 243 kills, three boss sectors, 14 upgrade drafts, and the victory state.
- Ran the renderer matrix across Campaign/Endless/Zen, 20×8 through 160×45, four themes, Unicode/ASCII, and ANSI/plain output.
- Benchmarked 650 stars at 160×45: 5.29 ms average render time.
- Built and installed the wheel in an isolated environment; `starfield 3.0.0`, snapshots, and JSON state output all passed.
- Added a visually inspected boss-combat capture, rewrote the README, expanded the changelog, and promoted the package to 3.0.0.
- Verification: 20/20 tests pass.

## TODO / handoff

- No known correctness blockers.
- Optional future work: persistent local high-score table, terminal audio toggle, additional boss attack patterns.

## Iteration 4 — launch media

- Generated all release media from real deterministic renderer states; no mockups or unrelated artwork.
- Added full-frame boss-combat and progression GIFs plus title and boss PNG stills.
- Visually inspected first, middle, and late frames; replaced delta-optimized GIFs after telemetry artifacts were found.
- Embedded the media into the README and prepared the same assets for the GitHub release.
