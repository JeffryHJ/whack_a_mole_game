import math
import struct
import pygame
import random
import sys
import time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WINDOW_WIDTH  = 800
WINDOW_HEIGHT = 620
FPS           = 60

# Colors
WHITE         = (255, 255, 255)
BLACK         = (  0,   0,   0)
GREEN         = ( 34, 139,  34)
DARK_GREEN    = (  0,  80,   0)
BROWN         = (139,  69,  19)
DARK_BROWN    = ( 90,  40,   5)
YELLOW        = (255, 215,   0)
RED           = (220,  50,  50)
GRAY          = (180, 180, 180)
BG_TOP        = ( 95, 195,  85)
BG_BOTTOM     = ( 60, 140,  50)
HEADER_COLOR  = ( 20,  80,  20)
SCORE_COLOR   = (255, 240, 100)
TIMER_OK      = (200, 255, 200)
TIMER_WARN    = (255,  80,  80)
HOLE_COLOR    = ( 30,  15,   5)
HOLE_RIM      = ( 80,  45,  10)

# Board: 3 × 3 grid of holes
COLS, ROWS    = 3, 3
HOLE_RADIUS   = 52          # px – hit-detection & drawing radius
HEADER_H      = 100         # height of the top HUD bar

# Distribute holes evenly across the playfield below the header
_play_h       = WINDOW_HEIGHT - HEADER_H - 20
H_STEP        = WINDOW_WIDTH  // (COLS + 1)
V_STEP        = _play_h       // (ROWS + 1)
HOLES: list[tuple[int, int]] = [
    (H_STEP * (c + 1), HEADER_H + 20 + V_STEP * (r + 1))
    for r in range(ROWS)
    for c in range(COLS)
]

# Game timing
MOLE_VISIBLE_S  = 1.0    # seconds a mole stays up before retreating
MOLE_INTERVAL_S = 0.75   # seconds between new mole spawns
GAME_DURATION_S = 30     # total game time in seconds

# Difficulty settings: (mole_visible_s, mole_interval_s)
DIFFICULTIES = {
    "Easy":   (1.2, 1.0),
    "Medium": (1.0, 0.75),
    "Hard":   (0.6, 0.4),
}
DIFFICULTY_ORDER = ["Easy", "Medium", "Hard"]


# ---------------------------------------------------------------------------
# Sound helpers
# ---------------------------------------------------------------------------
def _make_beep(freq: float, duration: float, volume: float = 0.5) -> pygame.mixer.Sound:
    """Generate a sine-wave tone as a pygame.mixer.Sound (22050 Hz, 16-bit mono)."""
    rate  = 22050
    n     = int(rate * duration)
    buf   = bytearray(n * 2)
    for i in range(n):
        val = int(volume * 32767 * math.sin(2 * math.pi * freq * i / rate))
        struct.pack_into('<h', buf, i * 2, max(-32768, min(32767, val)))
    return pygame.mixer.Sound(buffer=bytes(buf))


# ---------------------------------------------------------------------------
# Mole entity
# ---------------------------------------------------------------------------
class Mole:
    """Represents a single mole that has popped up from a hole."""

    def __init__(self, hole_index: int, appeared_at: float,
                 mole_visible_s: float = MOLE_VISIBLE_S) -> None:
        self.hole_index  = hole_index
        self.appeared_at = appeared_at
        self.whacked     = False
        self.hide_at     = appeared_at + mole_visible_s

    # Convenience position accessors
    @property
    def cx(self) -> int:
        return HOLES[self.hole_index][0]

    @property
    def cy(self) -> int:
        return HOLES[self.hole_index][1]

    def is_expired(self, now: float) -> bool:
        return now >= self.hide_at

    def hit(self, mx: int, my: int) -> bool:
        """Return True if (mx, my) is within the mole's circular area."""
        return (mx - self.cx) ** 2 + (my - self.cy) ** 2 <= HOLE_RADIUS ** 2


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def draw_background(screen: pygame.Surface) -> None:
    """Gradient-style grass background."""
    for y in range(WINDOW_HEIGHT):
        t   = y / WINDOW_HEIGHT
        r   = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g   = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b   = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        pygame.draw.line(screen, (r, g, b), (0, y), (WINDOW_WIDTH, y))


def draw_holes(screen: pygame.Surface) -> None:
    """Draw all nine holes as shadowed ellipses."""
    for cx, cy in HOLES:
        ew, eh = HOLE_RADIUS * 2, int(HOLE_RADIUS * 0.65)
        # Outer rim
        rim = pygame.Rect(cx - HOLE_RADIUS - 4, cy - eh // 2 - 4, ew + 8, eh + 8)
        pygame.draw.ellipse(screen, HOLE_RIM, rim)
        # Dark hole interior
        hole = pygame.Rect(cx - HOLE_RADIUS, cy - eh // 2, ew, eh)
        pygame.draw.ellipse(screen, HOLE_COLOR, hole)


def draw_mole(screen: pygame.Surface, mole: Mole, font: pygame.font.Font) -> None:
    """Draw a mole centered on its hole."""
    cx, cy = mole.cx, mole.cy
    r      = HOLE_RADIUS - 4

    body_color = RED if mole.whacked else BROWN
    shade      = RED if mole.whacked else DARK_BROWN

    # Body shadow
    pygame.draw.circle(screen, shade, (cx + 4, cy + 4), r)
    # Body
    pygame.draw.circle(screen, body_color, (cx, cy), r)

    # Eyes
    for ex in (cx - 13, cx + 13):
        pygame.draw.circle(screen, WHITE,        (ex, cy - 10), 9)
        pygame.draw.circle(screen, BLACK,        (ex + 2, cy - 10), 5)
        pygame.draw.circle(screen, WHITE,        (ex + 3, cy - 12), 2)  # gleam

    # Nose
    pygame.draw.circle(screen, (255, 130, 130), (cx, cy + 2), 7)
    pygame.draw.circle(screen, (200, 60, 60),   (cx, cy + 2), 4)

    # Teeth
    pygame.draw.rect(screen, WHITE, pygame.Rect(cx - 9, cy + 10, 8, 10))
    pygame.draw.rect(screen, WHITE, pygame.Rect(cx + 1, cy + 10, 8, 10))

    # Whacked "★ HIT!" indicator
    if mole.whacked:
        hit_txt = font.render("HIT!", True, YELLOW)
        screen.blit(hit_txt, (cx - hit_txt.get_width() // 2, cy - r - 34))


def difficulty_screen(screen: pygame.Surface,
                      font: pygame.font.Font,
                      big_font: pygame.font.Font) -> str:
    """Show a difficulty selection screen; return one of 'Easy', 'Medium', 'Hard'."""
    selected = 1  # index into DIFFICULTY_ORDER (default: Medium)
    clock    = pygame.time.Clock()

    # Colours for each difficulty option
    diff_colors = {
        "Easy":   (100, 210, 100),
        "Medium": YELLOW,
        "Hard":   (230, 80, 80),
    }

    while True:
        clock.tick(30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    selected = (selected - 1) % len(DIFFICULTY_ORDER)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    selected = (selected + 1) % len(DIFFICULTY_ORDER)
                elif event.key == pygame.K_RETURN:
                    return DIFFICULTY_ORDER[selected]
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                for i, rect in enumerate(_diff_rects):
                    if rect.collidepoint(mx, my):
                        selected = i
                if _confirm_rect.collidepoint(mx, my):
                    return DIFFICULTY_ORDER[selected]

        # ── Draw ──
        screen.fill(DARK_GREEN)
        for i in range(0, WINDOW_WIDTH, 40):
            pygame.draw.line(screen, GREEN, (i, 0), (i, WINDOW_HEIGHT), 1)

        title = big_font.render("WHACK-A-MOLE", True, YELLOW)
        screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 60))

        sub = font.render("Select Difficulty", True, WHITE)
        screen.blit(sub, (WINDOW_WIDTH // 2 - sub.get_width() // 2, 140))

        # Three difficulty buttons
        btn_w, btn_h = 180, 70
        gap          = 30
        total_w      = btn_w * 3 + gap * 2
        start_x      = WINDOW_WIDTH // 2 - total_w // 2
        _diff_rects.clear()
        for i, name in enumerate(DIFFICULTY_ORDER):
            rect = pygame.Rect(start_x + i * (btn_w + gap), 200, btn_w, btn_h)
            _diff_rects.append(rect)
            is_sel    = (i == selected)
            bg_color  = diff_colors[name] if is_sel else HEADER_COLOR
            bd_color  = diff_colors[name]
            pygame.draw.rect(screen, bg_color, rect, border_radius=12)
            pygame.draw.rect(screen, bd_color, rect, 3, border_radius=12)
            lbl_color = BLACK if is_sel else diff_colors[name]
            lbl       = font.render(name, True, lbl_color)
            screen.blit(lbl, (rect.centerx - lbl.get_width() // 2,
                               rect.centery - lbl.get_height() // 2))

        # Show timing info for selected difficulty
        vis_s, int_s = DIFFICULTIES[DIFFICULTY_ORDER[selected]]
        info = font.render(
            f"Mole visible: {vis_s:.1f}s   |   Spawn interval: {int_s:.2f}s",
            True, GRAY)
        screen.blit(info, (WINDOW_WIDTH // 2 - info.get_width() // 2, 295))

        # Confirm button
        _confirm_rect.update(WINDOW_WIDTH // 2 - 120, 360, 240, 52)
        pygame.draw.rect(screen, HEADER_COLOR, _confirm_rect, border_radius=12)
        pygame.draw.rect(screen, YELLOW,       _confirm_rect, 3, border_radius=12)
        conf_lbl = font.render("CONFIRM  (Enter)", True, YELLOW)
        screen.blit(conf_lbl, (WINDOW_WIDTH // 2 - conf_lbl.get_width() // 2,
                                _confirm_rect.centery - conf_lbl.get_height() // 2))

        hint = font.render("← / → to change", True, GRAY)
        screen.blit(hint, (WINDOW_WIDTH // 2 - hint.get_width() // 2, 430))

        pygame.display.flip()


# Module-level mutable containers used inside difficulty_screen (avoids
# recreating list/Rect objects on every frame)
_diff_rects:   list[pygame.Rect] = []
_confirm_rect: pygame.Rect       = pygame.Rect(0, 0, 0, 0)



def name_input_screen(screen: pygame.Surface,
                      font: pygame.font.Font,
                      big_font: pygame.font.Font,
                      player_number: int = 1) -> str:
    """Show a name-entry screen for the given player; return the entered name."""
    player_name = ""
    MAX_LEN     = 18
    clock       = pygame.time.Clock()
    cursor_on   = True
    cursor_tick = 0

    while True:
        clock.tick(30)
        cursor_tick += 1
        if cursor_tick >= 15:
            cursor_on   = not cursor_on
            cursor_tick = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and player_name.strip():
                    return player_name.strip()
                elif event.key == pygame.K_BACKSPACE:
                    player_name = player_name[:-1]
                elif len(player_name) < MAX_LEN and event.unicode.isprintable():
                    player_name += event.unicode

        # ── Draw ──
        screen.fill(DARK_GREEN)
        for i in range(0, WINDOW_WIDTH, 40):
            pygame.draw.line(screen, GREEN, (i, 0), (i, WINDOW_HEIGHT), 1)

        panel = pygame.Rect(WINDOW_WIDTH // 2 - 260, 160, 520, 260)
        pygame.draw.rect(screen, HEADER_COLOR, panel, border_radius=18)
        pygame.draw.rect(screen, YELLOW,       panel, 3,  border_radius=18)

        title = big_font.render("WHACK-A-MOLE", True, YELLOW)
        screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 60))

        prompt = font.render(f"Player {player_number}  -  Enter your name:", True, WHITE)
        screen.blit(prompt, (WINDOW_WIDTH // 2 - prompt.get_width() // 2, 195))

        # Input box
        box = pygame.Rect(WINDOW_WIDTH // 2 - 180, 240, 360, 46)
        pygame.draw.rect(screen, WHITE, box, border_radius=8)
        pygame.draw.rect(screen, YELLOW, box, 2, border_radius=8)
        display   = player_name + ("|" if cursor_on else " ")
        name_surf = font.render(display, True, BLACK)
        screen.blit(name_surf, (box.x + 12, box.y + 9))

        hint_color = GRAY if player_name.strip() else RED
        hint = font.render("Press  ENTER  to confirm", True, hint_color)
        screen.blit(hint, (WINDOW_WIDTH // 2 - hint.get_width() // 2, 310))

        pygame.display.flip()


def round_intro_screen(screen: pygame.Surface, player_name: str, round_num: int,
                       font: pygame.font.Font, big_font: pygame.font.Font) -> None:
    """Show a 'get ready' screen for the current player; wait for SPACE."""
    clock = pygame.time.Clock()
    while True:
        clock.tick(30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                return

        screen.fill(DARK_GREEN)
        for i in range(0, WINDOW_WIDTH, 40):
            pygame.draw.line(screen, GREEN, (i, 0), (i, WINDOW_HEIGHT), 1)

        panel = pygame.Rect(WINDOW_WIDTH // 2 - 270, 165, 540, 250)
        pygame.draw.rect(screen, HEADER_COLOR, panel, border_radius=18)
        pygame.draw.rect(screen, YELLOW,       panel, 3,  border_radius=18)

        round_txt = big_font.render(f"Round {round_num}", True, YELLOW)
        name_txt  = font.render(f"Get ready,  {player_name}!", True, WHITE)
        hint_txt  = font.render("Press  SPACE  to start your turn", True, GRAY)

        screen.blit(round_txt, (WINDOW_WIDTH // 2 - round_txt.get_width() // 2, 185))
        screen.blit(name_txt,  (WINDOW_WIDTH // 2 - name_txt.get_width()  // 2, 268))
        screen.blit(hint_txt,  (WINDOW_WIDTH // 2 - hint_txt.get_width()  // 2, 330))
        pygame.display.flip()


def final_scoreboard(screen: pygame.Surface,
                     names: list, scores: list,
                     font: pygame.font.Font, big_font: pygame.font.Font) -> bool:
    """Display final scores and winner. Return True to play again."""
    clock = pygame.time.Clock()

    if scores[0] > scores[1]:
        winner_line = f"{names[0]}  WINS!"
        win_color   = SCORE_COLOR
    elif scores[1] > scores[0]:
        winner_line = f"{names[1]}  WINS!"
        win_color   = SCORE_COLOR
    else:
        winner_line = "IT'S A TIE!"
        win_color   = WHITE

    while True:
        clock.tick(30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return True
                if event.key == pygame.K_q:
                    pygame.quit()
                    sys.exit()

        screen.fill(DARK_GREEN)
        for i in range(0, WINDOW_WIDTH, 40):
            pygame.draw.line(screen, GREEN, (i, 0), (i, WINDOW_HEIGHT), 1)

        panel = pygame.Rect(WINDOW_WIDTH // 2 - 270, 110, 540, 360)
        pygame.draw.rect(screen, HEADER_COLOR, panel, border_radius=18)
        pygame.draw.rect(screen, YELLOW,       panel, 3,  border_radius=18)

        title  = big_font.render("FINAL SCORES", True, YELLOW)
        p1_col = SCORE_COLOR if scores[0] >= scores[1] else GRAY
        p2_col = SCORE_COLOR if scores[1] >= scores[0] else GRAY
        p1_txt = font.render(f"{names[0]}:   {scores[0]} pts", True, p1_col)
        p2_txt = font.render(f"{names[1]}:   {scores[1]} pts", True, p2_col)
        win_txt = big_font.render(winner_line, True, win_color)
        re_txt  = font.render("R  -  Play Again       Q  -  Quit", True, GRAY)

        screen.blit(title,   (WINDOW_WIDTH // 2 - title.get_width()   // 2, 128))
        screen.blit(p1_txt,  (WINDOW_WIDTH // 2 - p1_txt.get_width()  // 2, 210))
        screen.blit(p2_txt,  (WINDOW_WIDTH // 2 - p2_txt.get_width()  // 2, 255))
        screen.blit(win_txt, (WINDOW_WIDTH // 2 - win_txt.get_width() // 2, 315))
        screen.blit(re_txt,  (WINDOW_WIDTH // 2 - re_txt.get_width()  // 2, 415))
        pygame.display.flip()


def draw_hud(screen: pygame.Surface, score: int, time_left: float,
             player_name: str,
             font: pygame.font.Font, big_font: pygame.font.Font) -> None:
    """Draw the header bar with title, player name, score, and timer."""
    # Background bar
    pygame.draw.rect(screen, HEADER_COLOR, (0, 0, WINDOW_WIDTH, HEADER_H))
    pygame.draw.rect(screen, DARK_GREEN,   (0, HEADER_H - 4, WINDOW_WIDTH, 4))

    # Title
    title = big_font.render("WHACK-A-MOLE", True, YELLOW)
    screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 4))

    # Player name (centre, below title)
    name_surf = font.render(player_name, True, WHITE)
    screen.blit(name_surf, (WINDOW_WIDTH // 2 - name_surf.get_width() // 2, 60))

    # Score (left)
    score_label = font.render("SCORE", True, GRAY)
    score_value = font.render(str(score), True, SCORE_COLOR)
    screen.blit(score_label, (40, 58))
    screen.blit(score_value, (40 + score_label.get_width() + 10, 56))

    # Timer (right)
    secs        = max(0, int(time_left) + 1)
    time_color  = TIMER_WARN if secs <= 5 else TIMER_OK
    time_label  = font.render("TIME", True, GRAY)
    time_value  = font.render(f"{secs}s", True, time_color)
    total_w     = time_label.get_width() + 10 + time_value.get_width()
    screen.blit(time_label, (WINDOW_WIDTH - total_w - 40, 58))
    screen.blit(time_value, (WINDOW_WIDTH - time_value.get_width() - 40, 56))


# ---------------------------------------------------------------------------
# Single-player round  (returns the score)
# ---------------------------------------------------------------------------
def run_round(screen: pygame.Surface, clock: pygame.time.Clock,
              font: pygame.font.Font, big_font: pygame.font.Font,
              player_name: str,
              whack_sound: pygame.mixer.Sound,
              miss_sound: pygame.mixer.Sound,
              mole_visible_s: float = MOLE_VISIBLE_S,
              mole_interval_s: float = MOLE_INTERVAL_S) -> int:
    """Run one 30-second round for player_name and return their score."""
    score:        int        = 0
    start_time:   float      = time.time()
    moles:        list[Mole] = []
    last_mole_t:  float      = 0.0
    active_holes: set[int]   = set()

    while True:
        now       = time.time()
        time_left = GAME_DURATION_S - (now - start_time)

        # ── Events ──────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                for mole in moles:
                    if not mole.whacked and mole.hit(mx, my):
                        mole.whacked = True
                        mole.hide_at = now + 0.30
                        score       += 1
                        active_holes.discard(mole.hole_index)
                        whack_sound.play()
                        break

        # ── Spawn ────────────────────────────────────────────────────────────
        available = [i for i in range(len(HOLES)) if i not in active_holes]
        if (available
                and time_left > 0
                and (now - last_mole_t) >= mole_interval_s):
            idx = random.choice(available)
            moles.append(Mole(idx, now, mole_visible_s))
            active_holes.add(idx)
            last_mole_t = now

        # ── Retire expired moles ─────────────────────────────────────────────
        for mole in moles[:]:
            if mole.is_expired(now):
                if not mole.whacked:
                    miss_sound.play()
                active_holes.discard(mole.hole_index)
                moles.remove(mole)

        # ── Render ───────────────────────────────────────────────────────────
        draw_background(screen)
        draw_holes(screen)
        for mole in moles:
            draw_mole(screen, mole, font)
        draw_hud(screen, score, time_left, player_name, font, big_font)
        pygame.display.flip()
        clock.tick(FPS)

        if time_left <= 0:
            return score


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    screen   = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Whack-a-Mole")
    clock       = pygame.time.Clock()
    font        = pygame.font.SysFont("Arial", 28, bold=True)
    big_font    = pygame.font.SysFont("Arial", 52, bold=True)
    whack_sound = _make_beep(600, 0.10, 0.6)
    miss_sound  = _make_beep(180, 0.15, 0.4)

    while True:
        # Choose difficulty first
        difficulty = difficulty_screen(screen, font, big_font)
        mole_visible_s, mole_interval_s = DIFFICULTIES[difficulty]

        # Collect both player names
        name1 = name_input_screen(screen, font, big_font, player_number=1)
        name2 = name_input_screen(screen, font, big_font, player_number=2)

        # Round 1 — Player 1
        round_intro_screen(screen, name1, round_num=1, font=font, big_font=big_font)
        score1 = run_round(screen, clock, font, big_font, name1, whack_sound, miss_sound,
                           mole_visible_s, mole_interval_s)

        # Round 2 — Player 2
        round_intro_screen(screen, name2, round_num=2, font=font, big_font=big_font)
        score2 = run_round(screen, clock, font, big_font, name2, whack_sound, miss_sound,
                           mole_visible_s, mole_interval_s)

        # Final scoreboard — loop back if they want to play again
        if not final_scoreboard(screen, [name1, name2], [score1, score2],
                                font, big_font):
            break
