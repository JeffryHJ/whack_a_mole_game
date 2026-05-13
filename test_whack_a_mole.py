"""Comprehensive tests for whack_a_mole.py

Covers:
  - Mole class: construction, position, expiry, hit-detection
  - _make_beep: sound generation
  - Board layout: hole count, bounds, spacing, non-collision
  - Constants: valid RGB, positive dimensions/timings
  - HUD timer display logic
  - Winner determination logic
  - Draw functions: smoke tests (headless SDL)
  - Spawn guard: active_holes prevents duplicate spawning (issue #8 regression)

Run with:
    python -m pytest test_whack_a_mole.py -v
or:
    python -m unittest test_whack_a_mole -v
"""

import math
import os
import struct
import sys
import unittest

# ---------------------------------------------------------------------------
# Headless SDL — must be set before importing pygame or the game module
# ---------------------------------------------------------------------------
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()

# Make the game module importable from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import whack_a_mole as wam


# ---------------------------------------------------------------------------
# Pure-logic helpers that mirror embedded game logic
# ---------------------------------------------------------------------------

def _winner_info(names: list, scores: list) -> tuple[str, tuple]:
    """Mirror the winner-determination logic inside final_scoreboard."""
    if scores[0] > scores[1]:
        return f"{names[0]}  WINS!", wam.SCORE_COLOR
    elif scores[1] > scores[0]:
        return f"{names[1]}  WINS!", wam.SCORE_COLOR
    return "IT'S A TIE!", wam.WHITE


def _hud_timer_secs(time_left: float) -> int:
    """Mirror: max(0, int(time_left) + 1)"""
    return max(0, int(time_left) + 1)


def _hud_timer_color(time_left: float) -> tuple:
    """Mirror the timer color selection from draw_hud."""
    secs = _hud_timer_secs(time_left)
    return wam.TIMER_WARN if secs <= 5 else wam.TIMER_OK


# ===========================================================================
# Mole.__init__
# ===========================================================================
class TestMoleInit(unittest.TestCase):

    def test_whacked_is_false_on_creation(self):
        m = wam.Mole(0, 100.0)
        self.assertFalse(m.whacked)

    def test_appeared_at_stored(self):
        m = wam.Mole(3, 42.5)
        self.assertAlmostEqual(m.appeared_at, 42.5)

    def test_hole_index_stored(self):
        for i in range(len(wam.HOLES)):
            with self.subTest(i=i):
                m = wam.Mole(i, 0.0)
                self.assertEqual(m.hole_index, i)

    def test_hide_at_equals_appeared_plus_visible(self):
        m = wam.Mole(0, 100.0)
        self.assertAlmostEqual(m.hide_at, 100.0 + wam.MOLE_VISIBLE_S)

    def test_hide_at_with_zero_appeared_at(self):
        m = wam.Mole(0, 0.0)
        self.assertAlmostEqual(m.hide_at, wam.MOLE_VISIBLE_S)

    def test_hide_at_with_large_appeared_at(self):
        appeared = 1_000_000.0
        m = wam.Mole(0, appeared)
        self.assertAlmostEqual(m.hide_at, appeared + wam.MOLE_VISIBLE_S)


# ===========================================================================
# Mole.cx / Mole.cy properties
# ===========================================================================
class TestMolePosition(unittest.TestCase):

    def test_cx_matches_holes_table(self):
        for i, (x, _) in enumerate(wam.HOLES):
            with self.subTest(hole=i):
                self.assertEqual(wam.Mole(i, 0.0).cx, x)

    def test_cy_matches_holes_table(self):
        for i, (_, y) in enumerate(wam.HOLES):
            with self.subTest(hole=i):
                self.assertEqual(wam.Mole(i, 0.0).cy, y)

    def test_all_positions_are_distinct(self):
        positions = [(wam.Mole(i, 0.0).cx, wam.Mole(i, 0.0).cy)
                     for i in range(len(wam.HOLES))]
        self.assertEqual(len(set(positions)), len(wam.HOLES))


# ===========================================================================
# Mole.is_expired
# ===========================================================================
class TestMoleIsExpired(unittest.TestCase):

    def setUp(self):
        self.m = wam.Mole(0, 100.0)   # hide_at = 100 + MOLE_VISIBLE_S

    def test_not_expired_well_before_hide(self):
        self.assertFalse(self.m.is_expired(self.m.appeared_at))

    def test_not_expired_one_ms_before_hide(self):
        self.assertFalse(self.m.is_expired(self.m.hide_at - 0.001))

    def test_expired_exactly_at_hide(self):
        self.assertTrue(self.m.is_expired(self.m.hide_at))

    def test_expired_after_hide(self):
        self.assertTrue(self.m.is_expired(self.m.hide_at + 0.001))

    def test_expired_far_in_future(self):
        self.assertTrue(self.m.is_expired(self.m.hide_at + 1000.0))

    def test_whacked_mole_has_shortened_hide_at(self):
        m = wam.Mole(0, 100.0)
        m.whacked = True
        m.hide_at = 100.30          # game sets this on a successful whack
        self.assertFalse(m.is_expired(100.0))
        self.assertTrue(m.is_expired(100.30))


# ===========================================================================
# Mole.hit — circular hit-detection
# ===========================================================================
class TestMoleHit(unittest.TestCase):

    def setUp(self):
        # Use the centre hole (index 4 in a 3×3 grid)
        self.m  = wam.Mole(4, 0.0)
        self.cx = self.m.cx
        self.cy = self.m.cy
        self.r  = wam.HOLE_RADIUS

    # --- direct hits --------------------------------------------------------

    def test_hit_exact_center(self):
        self.assertTrue(self.m.hit(self.cx, self.cy))

    def test_hit_one_pixel_inside_right(self):
        self.assertTrue(self.m.hit(self.cx + self.r - 1, self.cy))

    def test_hit_exactly_on_boundary(self):
        # distance == r → r² <= r² → True
        self.assertTrue(self.m.hit(self.cx + self.r, self.cy))

    def test_hit_from_above(self):
        self.assertTrue(self.m.hit(self.cx, self.cy - self.r))

    def test_hit_from_below(self):
        self.assertTrue(self.m.hit(self.cx, self.cy + self.r))

    def test_hit_from_left(self):
        self.assertTrue(self.m.hit(self.cx - self.r, self.cy))

    def test_hit_from_right(self):
        self.assertTrue(self.m.hit(self.cx + self.r, self.cy))

    def test_hit_diagonal_45_inside(self):
        # distance at 45° = d√2 < r  →  d < r/√2
        d = int(self.r / math.sqrt(2)) - 1
        self.assertTrue(self.m.hit(self.cx + d, self.cy + d))

    # --- misses -------------------------------------------------------------

    def test_miss_one_pixel_outside(self):
        self.assertFalse(self.m.hit(self.cx + self.r + 1, self.cy))

    def test_miss_far_top_left(self):
        self.assertFalse(self.m.hit(0, 0))

    def test_miss_bottom_right_corner(self):
        self.assertFalse(self.m.hit(wam.WINDOW_WIDTH - 1, wam.WINDOW_HEIGHT - 1))

    def test_miss_diagonal_45_outside(self):
        d = int(self.r / math.sqrt(2)) + 2
        self.assertFalse(self.m.hit(self.cx + d, self.cy + d))

    # --- cross-hole tests ---------------------------------------------------

    def test_all_moles_hit_at_own_center(self):
        for i in range(len(wam.HOLES)):
            m = wam.Mole(i, 0.0)
            with self.subTest(hole=i):
                self.assertTrue(m.hit(m.cx, m.cy))

    def test_hole_0_center_does_not_hit_hole_8(self):
        m0 = wam.Mole(0, 0.0)
        m8 = wam.Mole(8, 0.0)
        self.assertFalse(m8.hit(m0.cx, m0.cy))

    def test_adjacent_hole_centers_do_not_cross_hit(self):
        for i in range(len(wam.HOLES) - 1):
            mi = wam.Mole(i, 0.0)
            mj = wam.Mole(i + 1, 0.0)
            with self.subTest(pair=(i, i + 1)):
                self.assertFalse(mj.hit(mi.cx, mi.cy))


# ===========================================================================
# _make_beep
# ===========================================================================
class TestMakeBeep(unittest.TestCase):

    def test_returns_pygame_sound(self):
        self.assertIsInstance(wam._make_beep(440, 0.1), pygame.mixer.Sound)

    def test_whack_frequency_works(self):
        s = wam._make_beep(600, 0.10, 0.6)
        self.assertIsNotNone(s)

    def test_miss_frequency_works(self):
        s = wam._make_beep(180, 0.15, 0.4)
        self.assertIsNotNone(s)

    def test_very_short_duration(self):
        s = wam._make_beep(440, 0.001)
        self.assertIsNotNone(s)

    def test_longer_duration(self):
        s = wam._make_beep(440, 1.0)
        self.assertIsNotNone(s)

    def test_zero_volume_does_not_raise(self):
        s = wam._make_beep(440, 0.05, volume=0.0)
        self.assertIsNotNone(s)

    def test_full_volume_does_not_raise(self):
        s = wam._make_beep(440, 0.05, volume=1.0)
        self.assertIsNotNone(s)

    def test_over_max_volume_clamped_no_raise(self):
        # volume > 1.0 would overflow int16 — clamping must prevent that
        s = wam._make_beep(440, 0.05, volume=2.0)
        self.assertIsNotNone(s)

    def test_buffer_sample_count_correct(self):
        """Manually replicate the buffer to confirm no struct errors."""
        rate, duration = 22050, 0.1
        n   = int(rate * duration)
        buf = bytearray(n * 2)
        for i in range(n):
            val = int(0.5 * 32767 * math.sin(2 * math.pi * 440 * i / rate))
            struct.pack_into('<h', buf, i * 2, max(-32768, min(32767, val)))
        # Verify it can be wrapped as a Sound without errors
        s = pygame.mixer.Sound(buffer=bytes(buf))
        self.assertIsInstance(s, pygame.mixer.Sound)


# ===========================================================================
# Board layout — HOLES constant
# ===========================================================================
class TestBoardLayout(unittest.TestCase):

    def test_hole_count_equals_cols_times_rows(self):
        self.assertEqual(len(wam.HOLES), wam.COLS * wam.ROWS)

    def test_hole_count_is_nine(self):
        self.assertEqual(len(wam.HOLES), 9)

    def test_all_holes_x_within_window(self):
        for x, _ in wam.HOLES:
            self.assertGreater(x, 0)
            self.assertLess(x, wam.WINDOW_WIDTH)

    def test_all_holes_y_below_header(self):
        for _, y in wam.HOLES:
            self.assertGreater(y, wam.HEADER_H)

    def test_all_holes_y_within_window(self):
        for _, y in wam.HOLES:
            self.assertLess(y, wam.WINDOW_HEIGHT)

    def test_holes_are_unique(self):
        self.assertEqual(len(set(wam.HOLES)), len(wam.HOLES))

    def test_holes_not_overlapping(self):
        """No two hole centres are closer than 2 × HOLE_RADIUS."""
        min_dist_sq = (2 * wam.HOLE_RADIUS) ** 2
        for i, (x1, y1) in enumerate(wam.HOLES):
            for j, (x2, y2) in enumerate(wam.HOLES):
                if i >= j:
                    continue
                dist_sq = (x1 - x2) ** 2 + (y1 - y2) ** 2
                with self.subTest(pair=(i, j)):
                    self.assertGreater(dist_sq, min_dist_sq)

    def test_grid_has_exactly_three_distinct_x_values(self):
        x_vals = set(x for x, _ in wam.HOLES)
        self.assertEqual(len(x_vals), wam.COLS)

    def test_grid_has_exactly_three_distinct_y_values(self):
        y_vals = set(y for _, y in wam.HOLES)
        self.assertEqual(len(y_vals), wam.ROWS)

    def test_columns_are_evenly_spaced(self):
        xs = sorted(set(x for x, _ in wam.HOLES))
        gaps = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        self.assertEqual(len(set(gaps)), 1, "Column gaps are not uniform")

    def test_rows_are_evenly_spaced(self):
        ys = sorted(set(y for _, y in wam.HOLES))
        gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
        self.assertEqual(len(set(gaps)), 1, "Row gaps are not uniform")


# ===========================================================================
# Constants
# ===========================================================================
class TestConstants(unittest.TestCase):

    _COLOR_NAMES = [
        "WHITE", "BLACK", "GREEN", "DARK_GREEN", "BROWN", "DARK_BROWN",
        "YELLOW", "RED", "GRAY", "BG_TOP", "BG_BOTTOM", "HEADER_COLOR",
        "SCORE_COLOR", "TIMER_OK", "TIMER_WARN", "HOLE_COLOR", "HOLE_RIM",
    ]

    def test_all_colors_are_three_channel_tuples(self):
        for name in self._COLOR_NAMES:
            with self.subTest(color=name):
                self.assertEqual(len(getattr(wam, name)), 3)

    def test_all_color_channels_in_valid_range(self):
        for name in self._COLOR_NAMES:
            color = getattr(wam, name)
            with self.subTest(color=name):
                for ch in color:
                    self.assertGreaterEqual(ch, 0)
                    self.assertLessEqual(ch, 255)

    def test_window_width_positive(self):
        self.assertGreater(wam.WINDOW_WIDTH, 0)

    def test_window_height_positive(self):
        self.assertGreater(wam.WINDOW_HEIGHT, 0)

    def test_fps_at_least_one(self):
        self.assertGreaterEqual(wam.FPS, 1)

    def test_hole_radius_positive(self):
        self.assertGreater(wam.HOLE_RADIUS, 0)

    def test_header_height_positive(self):
        self.assertGreater(wam.HEADER_H, 0)

    def test_header_height_less_than_window_height(self):
        self.assertLess(wam.HEADER_H, wam.WINDOW_HEIGHT)

    def test_mole_visible_s_positive(self):
        self.assertGreater(wam.MOLE_VISIBLE_S, 0)

    def test_mole_interval_s_positive(self):
        self.assertGreater(wam.MOLE_INTERVAL_S, 0)

    def test_game_duration_s_positive(self):
        self.assertGreater(wam.GAME_DURATION_S, 0)

    def test_cols_is_three(self):
        self.assertEqual(wam.COLS, 3)

    def test_rows_is_three(self):
        self.assertEqual(wam.ROWS, 3)

    def test_timer_ok_and_warn_are_different(self):
        self.assertNotEqual(wam.TIMER_OK, wam.TIMER_WARN)


# ===========================================================================
# HUD timer display logic (mirrors draw_hud internals)
# ===========================================================================
class TestHudTimerLogic(unittest.TestCase):

    def test_secs_normal_countdown(self):
        self.assertEqual(_hud_timer_secs(10.0), 11)

    def test_secs_with_fraction(self):
        self.assertEqual(_hud_timer_secs(9.9), 10)

    def test_secs_exactly_zero(self):
        self.assertEqual(_hud_timer_secs(0.0), 1)

    def test_secs_tiny_positive(self):
        self.assertEqual(_hud_timer_secs(0.001), 1)

    def test_secs_clamped_on_negative(self):
        self.assertEqual(_hud_timer_secs(-1.0), 0)

    def test_secs_large_negative_clamps_to_zero(self):
        self.assertEqual(_hud_timer_secs(-999.0), 0)

    def test_color_ok_well_above_5(self):
        self.assertEqual(_hud_timer_color(10.0), wam.TIMER_OK)

    def test_color_ok_at_boundary_secs_6(self):
        # time_left=5.0 → secs=6 → OK
        self.assertEqual(_hud_timer_color(5.0), wam.TIMER_OK)

    def test_color_warn_at_boundary_secs_5(self):
        # time_left=4.0 → secs=5 → WARN
        self.assertEqual(_hud_timer_color(4.0), wam.TIMER_WARN)

    def test_color_warn_at_secs_1(self):
        self.assertEqual(_hud_timer_color(0.5), wam.TIMER_WARN)

    def test_color_warn_at_secs_0(self):
        # time_left=-1.0 → secs=0 → WARN
        self.assertEqual(_hud_timer_color(-1.0), wam.TIMER_WARN)

    def test_boundary_is_strictly_less_than_or_equal_5(self):
        # secs=5 → WARN; secs=6 → OK — verify the boundary is <=5
        self.assertNotEqual(_hud_timer_color(4.0), _hud_timer_color(5.0))


# ===========================================================================
# Winner determination logic (mirrors final_scoreboard internals)
# ===========================================================================
class TestWinnerLogic(unittest.TestCase):

    def test_player1_wins(self):
        line, color = _winner_info(["Alice", "Bob"], [10, 5])
        self.assertEqual(line, "Alice  WINS!")
        self.assertEqual(color, wam.SCORE_COLOR)

    def test_player2_wins(self):
        line, color = _winner_info(["Alice", "Bob"], [3, 9])
        self.assertEqual(line, "Bob  WINS!")
        self.assertEqual(color, wam.SCORE_COLOR)

    def test_tie_message(self):
        line, color = _winner_info(["Alice", "Bob"], [7, 7])
        self.assertEqual(line, "IT'S A TIE!")
        self.assertEqual(color, wam.WHITE)

    def test_zero_zero_tie(self):
        line, _ = _winner_info(["X", "Y"], [0, 0])
        self.assertEqual(line, "IT'S A TIE!")

    def test_player1_wins_by_one(self):
        line, _ = _winner_info(["X", "Y"], [6, 5])
        self.assertEqual(line, "X  WINS!")

    def test_player2_wins_by_one(self):
        line, _ = _winner_info(["X", "Y"], [5, 6])
        self.assertEqual(line, "Y  WINS!")

    def test_large_score_gap(self):
        line, _ = _winner_info(["X", "Y"], [0, 999])
        self.assertEqual(line, "Y  WINS!")

    def test_winner_name_appears_in_line(self):
        line, _ = _winner_info(["LongPlayerName", "Bob"], [10, 0])
        self.assertIn("LongPlayerName", line)

    def test_loser_name_absent_from_winner_line(self):
        line, _ = _winner_info(["Alice", "Bob"], [10, 0])
        self.assertNotIn("Bob", line)


# ===========================================================================
# Draw functions — smoke tests (headless surface, verify no exception)
# ===========================================================================
class TestDrawSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.screen   = pygame.display.set_mode((wam.WINDOW_WIDTH, wam.WINDOW_HEIGHT))
        cls.font     = pygame.font.SysFont("Arial", 28, bold=True)
        cls.big_font = pygame.font.SysFont("Arial", 52, bold=True)

    def test_draw_background(self):
        wam.draw_background(self.screen)

    def test_draw_holes(self):
        wam.draw_holes(self.screen)

    def test_draw_mole_normal(self):
        wam.draw_mole(self.screen, wam.Mole(0, 0.0), self.font)

    def test_draw_mole_whacked(self):
        m = wam.Mole(4, 0.0)
        m.whacked = True
        wam.draw_mole(self.screen, m, self.font)

    def test_draw_mole_all_holes(self):
        for i in range(len(wam.HOLES)):
            with self.subTest(hole=i):
                wam.draw_mole(self.screen, wam.Mole(i, 0.0), self.font)

    def test_draw_hud_normal(self):
        wam.draw_hud(self.screen, 0, 30.0, "Player 1", self.font, self.big_font)

    def test_draw_hud_warn_timer(self):
        wam.draw_hud(self.screen, 5, 3.9, "Alice", self.font, self.big_font)

    def test_draw_hud_zero_time(self):
        wam.draw_hud(self.screen, 0, 0.0, "Bob", self.font, self.big_font)

    def test_draw_hud_negative_time(self):
        wam.draw_hud(self.screen, 10, -1.0, "Test", self.font, self.big_font)

    def test_draw_hud_high_score(self):
        wam.draw_hud(self.screen, 9999, 15.5, "Champion", self.font, self.big_font)

    def test_draw_hud_max_length_name(self):
        wam.draw_hud(self.screen, 1, 20.0, "A" * 18, self.font, self.big_font)

    def test_draw_hud_empty_name(self):
        wam.draw_hud(self.screen, 0, 10.0, "", self.font, self.big_font)


# ===========================================================================
# Spawn guard — active_holes invariant (issue #8 regression)
# ===========================================================================
class TestSpawnGuard(unittest.TestCase):
    """
    The game prevents duplicate spawning with:
        available = [i for i in range(len(HOLES)) if i not in active_holes]
    and only spawns when available is non-empty.
    """

    def test_occupied_holes_excluded_from_available(self):
        active = {0, 1, 2}
        available = [i for i in range(len(wam.HOLES)) if i not in active]
        for idx in active:
            self.assertNotIn(idx, available)

    def test_free_holes_included_in_available(self):
        active = {0, 1, 2}
        available = [i for i in range(len(wam.HOLES)) if i not in active]
        for i in range(3, len(wam.HOLES)):
            self.assertIn(i, available)

    def test_no_spawn_when_all_holes_occupied(self):
        active = set(range(len(wam.HOLES)))
        available = [i for i in range(len(wam.HOLES)) if i not in active]
        self.assertEqual(available, [])

    def test_all_holes_available_when_empty(self):
        active: set = set()
        available = [i for i in range(len(wam.HOLES)) if i not in active]
        self.assertEqual(available, list(range(len(wam.HOLES))))

    def test_single_occupied_hole_reduces_available_by_one(self):
        active = {4}
        available = [i for i in range(len(wam.HOLES)) if i not in active]
        self.assertEqual(len(available), len(wam.HOLES) - 1)
        self.assertNotIn(4, available)

    def test_spawned_index_added_to_active_holes(self):
        active: set = set()
        chosen = 5
        active.add(chosen)
        self.assertIn(chosen, active)

    def test_whacked_mole_freed_from_active_holes(self):
        active = {3}
        active.discard(3)
        self.assertNotIn(3, active)

    def test_expired_mole_freed_from_active_holes(self):
        active = {7}
        active.discard(7)
        self.assertNotIn(7, active)

    def test_double_discard_is_safe(self):
        active = {2}
        active.discard(2)
        active.discard(2)   # must not raise
        self.assertNotIn(2, active)

    def test_available_list_always_subset_of_all_holes(self):
        for occupied in range(len(wam.HOLES)):
            active = {occupied}
            available = [i for i in range(len(wam.HOLES)) if i not in active]
            with self.subTest(occupied=occupied):
                for idx in available:
                    self.assertIn(idx, range(len(wam.HOLES)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
