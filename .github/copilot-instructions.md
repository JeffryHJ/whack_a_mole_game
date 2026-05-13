# GitHub Copilot Instructions

## Project overview
This is a two-player Whack-a-Mole arcade game built with **Python 3** and **pygame**.
All game logic, rendering, and UI live in a single file: `whack_a_mole.py`.

---

## Language & runtime
- **Python 3.10+** — use modern syntax (`match`, `|` union types, `list[T]`, etc.) where appropriate.
- **pygame 2.x** — prefer pygame 2 APIs; do not introduce pygame 1-only patterns.
- No external dependencies beyond `pygame` and the Python standard library.

---

## Code style
- Follow **PEP 8** with a max line length of **100 characters**.
- Use **snake_case** for variables and functions, **PascalCase** for classes, **UPPER_SNAKE_CASE** for module-level constants.
- Align related assignments with spaces for readability (as seen in the constants block).
- Add a section divider comment (`# ---...---`) before every top-level logical group (constants, helpers, classes, screens, game loop, entry point).
- Use type hints on all function signatures (`-> None`, `-> int`, etc.).
- Prefer f-strings over `%` or `.format()` formatting.

---

## Architecture & design
- **Constants at the top** — every magic number or color tuple must be a named constant.
- **Pure drawing functions** — `draw_*` functions must only receive a `pygame.Surface` and the data they render; no global state reads inside them.
- **Screen functions** — each UI screen (name input, round intro, scoreboard, etc.) is an isolated function that runs its own event loop and returns a value when done.
- **`run_round`** is the core game loop; keep it free of UI/screen logic unrelated to the active round.
- Avoid classes for one-off screens; only model persistent game entities (e.g., `Mole`) as classes.
- Sounds are generated programmatically via `_make_beep()`; do **not** add dependencies on external audio files.

---

## Gameplay assumptions
- Board is a fixed **3 × 3** grid of holes (`COLS = 3`, `ROWS = 3`).
- One round lasts **`GAME_DURATION_S` seconds** (default 30).
- At most **one mole per hole** at any time; always verify a hole is free before spawning.
- A whacked mole turns red and retreats after **0.30 s**; an un-whacked mole retreats after **`MOLE_VISIBLE_S`**.

---

## What to avoid
- Do not use `pygame.time.delay` or `time.sleep` inside the main game loop — use frame timing via `clock.tick(FPS)`.
- Do not read from or write to files unless implementing a feature that explicitly requires persistence (e.g., a leaderboard).
- Do not add third-party libraries (numpy, Pillow, etc.) without a clear necessity.
- Do not use bare `except:` clauses; always catch a specific exception type.
- Do not silently swallow `pygame.QUIT` events — always call `pygame.quit(); sys.exit()`.
