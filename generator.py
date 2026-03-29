#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Procedural Word Puzzle Generator (Turkish)

Usage:
  python generator.py --difficulty kolay --seed 42
  python generator.py --difficulty zor --count 3
  python generator.py --samples          # Generate samples for all difficulty levels
"""

import json
import random
import os
import sys
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set
from enum import Enum
from datetime import datetime


# ══════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════

TURKISH_LETTERS = "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ"

class Difficulty(Enum):
    EASY   = "kolay"
    MEDIUM = "orta"
    HARD   = "zor"


class Direction(Enum):
    """(row_delta, col_delta)"""
    RIGHT      = ( 0,  1)
    LEFT       = ( 0, -1)
    DOWN       = ( 1,  0)
    UP         = (-1,  0)
    DOWN_RIGHT = ( 1,  1)
    DOWN_LEFT  = ( 1, -1)
    UP_RIGHT   = (-1,  1)
    UP_LEFT    = (-1, -1)


# Configuration table per difficulty level
DIFFICULTY_CONFIG: Dict[Difficulty, Dict] = {
    Difficulty.EASY: {
        "grid_size":      (9, 12),   # (min, max) square size
        "word_count":     (5, 8),
        "directions":     [Direction.RIGHT, Direction.DOWN],
        "min_word_len":   3,
        "max_word_len":   6,
        "min_frequency":  70,
    },
    Difficulty.MEDIUM: {
        "grid_size":      (12, 15),
        "word_count":     (9, 13),
        "directions":     [Direction.RIGHT, Direction.DOWN,
                           Direction.DOWN_RIGHT, Direction.DOWN_LEFT],
        "min_word_len":   4,
        "max_word_len":   8,
        "min_frequency":  40,
    },
    Difficulty.HARD: {
        "grid_size":      (15, 20),
        "word_count":     (14, 20),
        "directions":     list(Direction),          # All 8 directions (including reverse)
        "min_word_len":   5,
        "max_word_len":   15,
        "min_frequency":  0,
    },
}


# ══════════════════════════════════════════════════════════════
#  Data Classes
# ══════════════════════════════════════════════════════════════

@dataclass
class PlacedWord:
    word:      str
    row:       int
    col:       int
    direction: Direction

    def cells(self) -> List[Tuple[int, int]]:
        """Returns list of (row, col) cells occupied by the word."""
        dr, dc = self.direction.value
        return [(self.row + i * dr, self.col + i * dc) for i in range(len(self.word))]

    def to_dict(self) -> Dict:
        return {
            "word":      self.word,
            "row":       self.row,
            "col":       self.col,
            "direction": self.direction.name,
            "cells":     self.cells(),
        }


# ══════════════════════════════════════════════════════════════
#  Grid Manager
# ══════════════════════════════════════════════════════════════

class PuzzleGrid:
    """NxM letter grid; handles word placement and random fill."""

    EMPTY = "."

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self.grid: List[List[str]] = [
            [self.EMPTY] * cols for _ in range(rows)
        ]
        self.placed: List[PlacedWord] = []

    # ── Bounds & Collision Check ──────────────────────────────

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def can_place(self, word: str, row: int, col: int, direction: Direction) -> bool:
        """
        Can the word be placed at this position?
        - All cells must be within the grid
        - Occupied cells must match the word's letter (intersection allowed)
        """
        dr, dc = direction.value
        for i, ch in enumerate(word):
            r, c = row + i * dr, col + i * dc
            if not self.in_bounds(r, c):
                return False
            cell = self.grid[r][c]
            if cell != self.EMPTY and cell != ch:
                return False
        return True

    # ── Placement & Fill ────────────────────────────────────

    def place_word(self, word: str, row: int, col: int, direction: Direction) -> PlacedWord:
        dr, dc = direction.value
        for i, ch in enumerate(word):
            r, c = row + i * dr, col + i * dc
            self.grid[r][c] = ch
        pw = PlacedWord(word, row, col, direction)
        self.placed.append(pw)
        return pw

    def fill_random(self, letters: str = TURKISH_LETTERS, seed: Optional[int] = None):
        """Fill empty cells with random letters."""
        rng = random.Random(seed)
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == self.EMPTY:
                    self.grid[r][c] = rng.choice(letters)

    # ── Visual Output ────────────────────────────────────────

    def display(self) -> str:
        col_header = "    " + "  ".join(f"{c:2}" for c in range(self.cols))
        sep = "    " + "-" * (self.cols * 4)
        rows_out = []
        for r, row in enumerate(self.grid):
            rows_out.append(f"{r:2}  " + "  ".join(f"{ch:2}" for ch in row))
        return "\n".join([col_header, sep] + rows_out)


# ══════════════════════════════════════════════════════════════
#  Word Placer
# ══════════════════════════════════════════════════════════════

class WordPlacer:
    """
    Word search puzzle placer:
    - Longer words are placed first (they require more space).
    - Intersections (crossword-style shared letters) are preferred → denser grid.
    - Placements closer to the center are scored higher.
    """

    def __init__(self, grid: PuzzleGrid, directions: List[Direction],
                 seed: Optional[int] = None):
        self.grid = grid
        self.directions = directions
        self.rng = random.Random(seed)

    def _all_placements(self, word: str) -> List[Tuple[int, int, Direction]]:
        """Return all valid (row, col, dir) triples for the given word."""
        valid = []
        for d in self.directions:
            dr, dc = d.value
            for r in range(self.grid.rows):
                for c in range(self.grid.cols):
                    if self.grid.can_place(word, r, c, d):
                        valid.append((r, c, d))
        return valid

    def _score(self, word: str, row: int, col: int, direction: Direction) -> int:
        """
        Score:
        +10  → per intersection (shared letter with an already-placed word)
        -dist→ distance penalty from the grid center
        """
        dr, dc = direction.value
        score = 0
        for i, ch in enumerate(word):
            r, c = row + i * dr, col + i * dc
            if self.grid.grid[r][c] == ch:   # intersection
                score += 10
        cr, cc = self.grid.rows // 2, self.grid.cols // 2
        score -= (abs(row - cr) + abs(col - cc)) // 2
        return score

    def place_words(self, words: List[str]) -> List[str]:
        """
        Place words onto the grid.
        Returns the list of successfully placed words.
        """
        placed_names: List[str] = []
        # Descending order by length → longer words first
        for word in sorted(words, key=len, reverse=True):
            placements = self._all_placements(word)
            if not placements:
                continue
            # Pick randomly from the top 20% highest-scoring placements
            scored = sorted(
                [(self._score(word, r, c, d), r, c, d.name) for r, c, d in placements],
                reverse=True,
            )
            # Convert direction name back to enum
            scored_with_dir = [
                (s, r, c, Direction[dn]) for s, r, c, dn in scored
            ]
            scored = scored_with_dir
            top_n = max(1, len(scored) // 5)
            _, row, col, direction = self.rng.choice(scored[:top_n])  # direction is now a Direction enum
            self.grid.place_word(word, row, col, direction)
            placed_names.append(word)
        return placed_names


# ══════════════════════════════════════════════════════════════
#  Difficulty Scorer
# ══════════════════════════════════════════════════════════════

class DifficultyScorer:
    """
    Scores a puzzle with a normalised 0–100 value.

    Metrics:
    ┌──────────────────┬─────┬─────────────────────────────────────┐
    │ Metric           │ Wt  │ Description                         │
    ├──────────────────┼─────┼─────────────────────────────────────┤
    │ Grid size        │ 20% │ 9×9 → 0, 20×20 → 100               │
    │ Word count       │ 25% │ 5 → 0, 20 → 100                     │
    │ Avg word length  │ 25% │ 3 letters → 0, 12 letters → 100     │
    │ Letter diversity │ 15% │ unique/total ratio                  │
    │ Direction count  │ 15% │ 1 direction → 0, 8 directions → 100 │
    └──────────────────┴─────┴─────────────────────────────────────┘

    Level thresholds:
      0–33  → Easy
      34–66 → Medium
      67–100→ Hard
    """

    @staticmethod
    def compute(grid: PuzzleGrid, words: List[str],
                directions_used: Set[Direction]) -> Dict:
        if not words:
            return {"score": 0.0, "level": "kolay", "metrics": {}}

        total_letters  = sum(len(w) for w in words)
        unique_letters = len(set("".join(words)))
        avg_length     = total_letters / len(words)
        letter_ratio   = unique_letters / total_letters if total_letters else 0.0
        grid_area      = grid.rows * grid.cols
        dir_count      = len(directions_used)

        # Normalize to 0–1
        f_size  = min((grid_area - 81)  / (400 - 81),   1.0)
        f_count = min((len(words) - 5)  / (20 - 5),     1.0)
        f_len   = min((avg_length - 3)  / (12 - 3),     1.0)
        f_ratio = letter_ratio                             # already 0–1
        f_dir   = min((dir_count - 1)   / 7,             1.0)

        score = (
            f_size  * 0.20 +
            f_count * 0.25 +
            f_len   * 0.25 +
            f_ratio * 0.15 +
            f_dir   * 0.15
        ) * 100

        score = round(max(0.0, min(100.0, score)), 2)

        if score < 34:
            level = "kolay"
        elif score < 67:
            level = "orta"
        else:
            level = "zor"

        return {
            "score": score,
            "level": level,
            "metrics": {
                "grid_size":         f"{grid.rows}x{grid.cols}",
                "word_count":        len(words),
                "total_letters":     total_letters,
                "unique_letters":    unique_letters,
                "avg_word_length":   round(avg_length, 2),
                "letter_ratio":      round(letter_ratio, 3),
                "direction_count":   dir_count,
                "directions_used":   [d.name for d in sorted(directions_used, key=lambda d: d.name)],
            },
        }


# ══════════════════════════════════════════════════════════════
#  Main Generator
# ══════════════════════════════════════════════════════════════

class PuzzleGenerator:
    """
    Generates puzzle levels from a word list.

    Pipeline:
      1. Filter the word pool by difficulty settings
      2. Randomly select words
      3. Create the grid and place words
      4. Fill empty cells randomly
      5. Compute the difficulty score
      6. Save as JSON
    """

    def __init__(self, word_list_path: str = "word_list.json"):
        path = word_list_path
        if not os.path.isabs(path):
            # Look in the same directory as this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(script_dir, word_list_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.all_words: List[Dict] = data["words"]

    # ── Helpers ───────────────────────────────────────────────

    def _filter_pool(self, cfg: Dict) -> List[Dict]:
        pool = [
            w for w in self.all_words
            if cfg["min_word_len"] <= w["length"] <= cfg["max_word_len"]
            and w["frequency"] >= cfg["min_frequency"]
        ]
        # If not enough words, drop the frequency filter
        if len(pool) < cfg["word_count"][1]:
            pool = [
                w for w in self.all_words
                if cfg["min_word_len"] <= w["length"] <= cfg["max_word_len"]
            ]
        return pool

    # ── Main Method ───────────────────────────────────────────

    def generate(
        self,
        difficulty:  Difficulty          = Difficulty.MEDIUM,
        seed:        Optional[int]       = None,
        output_dir:  str                 = "level_outputs",
        theme:       Optional[str]       = None,   # e.g. "meyve", "hayvan"
    ) -> Tuple[Dict, str]:
        """
        Generate a single puzzle level.

        Returns:
            (level_dict, file_path)
        """
        if seed is None:
            seed = random.randint(1_000, 999_999)
        rng = random.Random(seed)
        cfg = DIFFICULTY_CONFIG[difficulty]

        # 1. Grid size
        size = rng.randint(*cfg["grid_size"])
        rows, cols = size, size

        # 2. Word count & selection
        word_count = rng.randint(*cfg["word_count"])
        pool = self._filter_pool(cfg)

        if theme:
            themed = [w for w in pool if w["category"] == theme]
            pool = themed if len(themed) >= word_count // 2 else pool

        selected = rng.sample(pool, min(word_count, len(pool)))
        words = [w["word"].upper() for w in selected]

        # 3. Create grid & place words
        grid = PuzzleGrid(rows, cols)
        placer = WordPlacer(grid, cfg["directions"], seed=seed)
        placed_words = placer.place_words(words)

        # 4. Fill empty cells
        grid.fill_random(seed=seed + 1)

        # 5. Difficulty score
        directions_used = {pw.direction for pw in grid.placed}
        scoring = DifficultyScorer.compute(grid, placed_words, directions_used)

        # 6. Build output object
        level_id = f"{difficulty.value}_{seed}"
        level = {
            "level_id":     level_id,
            "difficulty":   difficulty.value,
            "seed":         seed,
            "grid":         grid.grid,
            "words":        placed_words,
            "placed_words": [pw.to_dict() for pw in grid.placed],
            "grid_size":    [rows, cols],
            "metrics":      scoring,
            "theme":        theme,
            "created_at":   datetime.now().isoformat(),
        }

        # 7. Save to file
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, f"{level_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(level, f, ensure_ascii=False, indent=2)

        return level, out_path

    # ── Batch Sample Generation ───────────────────────────────

    def generate_samples(self, output_dir: str = "level_outputs") -> List[str]:
        """Generate one sample puzzle per difficulty level."""
        samples = [
            (Difficulty.EASY,   42,    "kolay_ornek"),
            (Difficulty.MEDIUM, 1337,  "orta_ornek"),
            (Difficulty.HARD,   99999, "zor_ornek"),
        ]
        paths = []
        for diff, seed, _ in samples:
            level, path = self.generate(diff, seed=seed, output_dir=output_dir)
            paths.append(path)
            _print_level(level)
        return paths


# ══════════════════════════════════════════════════════════════
#  Terminal Output / Pretty Print
# ══════════════════════════════════════════════════════════════

def _print_level(level: Dict):
    grid_obj = PuzzleGrid(level["grid_size"][0], level["grid_size"][1])
    grid_obj.grid = level["grid"]

    m = level["metrics"]
    sep = "=" * 60
    print()
    print(sep)
    print(f"  Bulmaca ID  : {level['level_id']}")
    print(f"  Zorluk      : {level['difficulty'].upper()}"
          f"  (Skor: {m['score']}/100 -> {m['level']})")
    print(f"  Izgara      : {m['metrics']['grid_size']}")
    print(f"  Kelime Sayisi: {m['metrics']['word_count']}")
    print(f"  Ort. Uzunluk : {m['metrics']['avg_word_length']} harf")
    print(f"  Harf Orani  : {m['metrics']['letter_ratio']}"
          f"  (benzersiz/toplam)")
    print(f"  Yonler      : {', '.join(m['metrics']['directions_used'])}")
    print()
    print(f"  Kelimeler: {', '.join(level['words'])}")
    print()
    print(grid_obj.display())
    print()


# ══════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Türkçe Kelime Bulmaca Üretici",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python generator.py --difficulty kolay --seed 42
  python generator.py --difficulty zor --count 5
  python generator.py --difficulty orta --theme meyve
  python generator.py --samples
        """,
    )
    parser.add_argument("--difficulty", choices=["kolay", "orta", "zor"],
                        default="orta", help="Zorluk seviyesi")
    parser.add_argument("--seed",    type=int, default=None,
                        help="Rastgele tohum (tekrar üretilebilirlik için)")
    parser.add_argument("--count",   type=int, default=1,
                        help="Üretilecek bulmaca sayısı")
    parser.add_argument("--output",  default="level_outputs",
                        help="Çıktı dizini (varsayılan: level_outputs)")
    parser.add_argument("--theme",   default=None,
                        help="Tema filtresi (ör: meyve, hayvan, renk)")
    parser.add_argument("--samples", action="store_true",
                        help="Her zorluk için örnek bulmaca üret")
    parser.add_argument("--word-list", default="word_list.json",
                        help="Kelime listesi JSON dosyası")

    args = parser.parse_args()

    gen = PuzzleGenerator(word_list_path=args.word_list)

    if args.samples:
        print("Örnek bulmacalar üretiliyor...")
        paths = gen.generate_samples(output_dir=args.output)
        print(f"\n{len(paths)} ornek kaydedildi -> {args.output}/")
        return

    diff_map = {
        "kolay": Difficulty.EASY,
        "orta":  Difficulty.MEDIUM,
        "zor":   Difficulty.HARD,
    }
    difficulty = diff_map[args.difficulty]
    base_seed  = args.seed if args.seed is not None else random.randint(1, 999_999)

    for i in range(args.count):
        level, path = gen.generate(
            difficulty  = difficulty,
            seed        = base_seed + i,
            output_dir  = args.output,
            theme       = args.theme,
        )
        _print_level(level)
        print(f"  Kaydedildi -> {path}\n")


if __name__ == "__main__":
    main()
