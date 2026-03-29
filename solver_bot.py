#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Puzzle Solvability Checker

Automatically solves every generated puzzle and verifies
that all words can be found in the grid.

Usage:
  python solver_bot.py                         # scan level_outputs/ directory
  python solver_bot.py --dir level_outputs     # specify directory
  python solver_bot.py --file kolay_42.json    # single file
  python solver_bot.py --report report.json    # save summary report
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Optional, Dict
from datetime import datetime


# ══════════════════════════════════════════════════════════════
#  Direction Vectors
# ══════════════════════════════════════════════════════════════

DIRECTIONS: Dict[str, Tuple[int, int]] = {
    "RIGHT":      ( 0,  1),
    "LEFT":       ( 0, -1),
    "DOWN":       ( 1,  0),
    "UP":         (-1,  0),
    "DOWN_RIGHT": ( 1,  1),
    "DOWN_LEFT":  ( 1, -1),
    "UP_RIGHT":   (-1,  1),
    "UP_LEFT":    (-1, -1),
}


# ══════════════════════════════════════════════════════════════
#  Data Classes
# ══════════════════════════════════════════════════════════════

@dataclass
class WordResult:
    word:       str
    found:      bool
    row:        Optional[int]  = None
    col:        Optional[int]  = None
    direction:  Optional[str]  = None
    expected_direction: Optional[str] = None   # direction stored by the generator (if available)

    def to_dict(self) -> Dict:
        d = {"word": self.word, "found": self.found}
        if self.found:
            d["position"] = {
                "row":       self.row,
                "col":       self.col,
                "direction": self.direction,
            }
        else:
            d["expected_direction"] = self.expected_direction
        return d


@dataclass
class SolveReport:
    level_id:     str
    difficulty:   str
    solvable:     bool
    total_words:  int
    found:        int
    missing:      int
    success_rate: float
    results:      List[WordResult] = field(default_factory=list)
    solved_at:    str              = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["results"] = [r.to_dict() for r in self.results]
        return d


# ══════════════════════════════════════════════════════════════
#  Solver
# ══════════════════════════════════════════════════════════════

class PuzzleSolver:
    """
    Searches for words in the given grid.

    Algorithm:
      For each cell:
        → If the first letter matches, continue in all 8 directions
        → If the full word matches → found
    O(rows × cols × 8 × max_word_len) time complexity
    """

    def __init__(self, grid: List[List[str]]):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0]) if grid else 0

    def _check_direction(self, word: str, r: int, c: int,
                          dr: int, dc: int) -> bool:
        """Does the word exist starting at (r, c) going in direction (dr, dc)?"""
        for i, ch in enumerate(word):
            nr, nc = r + i * dr, c + i * dc
            if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                return False
            if self.grid[nr][nc] != ch:
                return False
        return True

    def find_word(self, word: str,
                  hint_direction: Optional[str] = None) -> WordResult:
        """
        Search for the word in the grid.
        hint_direction: try this direction first (from generator records).
        """
        # Try the hint direction first → O(rows×cols) fast path
        if hint_direction and hint_direction in DIRECTIONS:
            dr, dc = DIRECTIONS[hint_direction]
            for r in range(self.rows):
                for c in range(self.cols):
                    if self.grid[r][c] == word[0]:
                        if self._check_direction(word, r, c, dr, dc):
                            return WordResult(word, True, r, c, hint_direction,
                                              hint_direction)

        # Brute-force search across all 8 directions
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == word[0]:
                    for dir_name, (dr, dc) in DIRECTIONS.items():
                        if self._check_direction(word, r, c, dr, dc):
                            return WordResult(word, True, r, c, dir_name,
                                              hint_direction)

        return WordResult(word, False, expected_direction=hint_direction)

    def solve_all(self, words: List[str],
                  placed_meta: Optional[List[Dict]] = None) -> SolveReport:
        """
        Solve all words and return a report.

        placed_meta: placement info from the generator
                     (used to extract direction hints for optimisation).
        """
        direction_hints: Dict[str, str] = {}
        if placed_meta:
            for pm in placed_meta:
                direction_hints[pm["word"]] = pm.get("direction")

        results: List[WordResult] = []
        for word in words:
            hint = direction_hints.get(word)
            res  = self.find_word(word, hint_direction=hint)
            results.append(res)

        found_count = sum(1 for r in results if r.found)
        total       = len(words)
        solvable    = found_count == total

        return SolveReport(
            level_id     = "",     # filled in by caller
            difficulty   = "",
            solvable     = solvable,
            total_words  = total,
            found        = found_count,
            missing      = total - found_count,
            success_rate = round(found_count / total * 100, 1) if total else 0.0,
            results      = results,
        )


# ══════════════════════════════════════════════════════════════
#  Batch Runner
# ══════════════════════════════════════════════════════════════

def run_batch(directory: str = "level_outputs",
              save_report: Optional[str] = None) -> Dict:
    """
    Solve all JSON puzzles in the given directory.
    Optionally save a summary report.
    """
    if not os.path.isdir(directory):
        print(f"[HATA] Dizin bulunamadı: {directory}", file=sys.stderr)
        sys.exit(1)

    files = sorted(f for f in os.listdir(directory) if f.endswith(".json"))
    if not files:
        print("Çözülecek bulmaca bulunamadı.", file=sys.stderr)
        return {}

    summary = {
        "run_at":       datetime.now().isoformat(),
        "directory":    directory,
        "total":        0,
        "solvable":     0,
        "unsolvable":   [],
        "by_difficulty": {"kolay": {"total": 0, "solvable": 0},
                          "orta":  {"total": 0, "solvable": 0},
                          "zor":   {"total": 0, "solvable": 0}},
        "reports":      [],
    }

    SEP  = "=" * 72
    SEP2 = "-" * 72
    print()
    print(SEP)
    print(f"  Bulmaca Cozum Botu  --  {directory}")
    print(SEP)
    header = (f"  {'Seviye ID':<30}  {'Zorluk':<8}"
              f"  {'Bulunan':>9}  {'Oran':>6}  Durum")
    print(header)
    print(SEP2)

    for fname in files:
        path = os.path.join(directory, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"║  [ATLA] {fname}: {e}".ljust(71) + "║")
            continue

        grid         = data.get("grid", [])
        words        = data.get("words", [])
        placed_meta  = data.get("placed_words")
        level_id     = data.get("level_id", fname.removesuffix(".json"))
        difficulty   = data.get("difficulty", "?")

        solver = PuzzleSolver(grid)
        report = solver.solve_all(words, placed_meta=placed_meta)
        report.level_id   = level_id
        report.difficulty = difficulty

        # Add to summary
        summary["total"] += 1
        diff_key = difficulty if difficulty in summary["by_difficulty"] else "orta"
        summary["by_difficulty"][diff_key]["total"] += 1

        if report.solvable:
            summary["solvable"] += 1
            summary["by_difficulty"][diff_key]["solvable"] += 1
            status = "[OK] COZULEBILIR"
        else:
            summary["unsolvable"].append(level_id)
            missing_words = [r.word for r in report.results if not r.found]
            status = f"[!!] EKSIK ({', '.join(missing_words)})"

        row = (f"  {level_id:<30}  {difficulty:<8}"
               f"  {report.found}/{report.total_words:>5}"
               f"  {report.success_rate:>5}%  {status}")
        print(row)
        summary["reports"].append(report.to_dict())

    # Footer totals row
    print(SEP)
    success_rate = (summary["solvable"] / summary["total"] * 100
                    if summary["total"] else 0)
    print(f"  TOPLAM: {summary['solvable']}/{summary['total']} cozulebilir"
          f"  --  Basari: %{success_rate:.1f}")

    # Breakdown by difficulty
    for d, v in summary["by_difficulty"].items():
        if v["total"] > 0:
            dr = round(v["solvable"] / v["total"] * 100, 1)
            print(f"    {d.upper()}: {v['solvable']}/{v['total']} (%{dr})")

    print(SEP)

    # Save report
    if save_report:
        with open(save_report, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\nRapor kaydedildi → {save_report}")

    return summary


def run_single(filepath: str) -> SolveReport:
    """Solve a single puzzle file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    solver = PuzzleSolver(data["grid"])
    report = solver.solve_all(data["words"], placed_meta=data.get("placed_words"))
    report.level_id   = data.get("level_id", "")
    report.difficulty = data.get("difficulty", "")

    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return report


# ══════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Kelime Bulmaca Çözüm Botu — Solvability Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python solver_bot.py                             # varsayılan dizin
  python solver_bot.py --dir level_outputs         # dizin belirt
  python solver_bot.py --file level_outputs/kolay_42.json
  python solver_bot.py --report cikti/rapor.json   # özet kaydet
        """,
    )
    parser.add_argument("--dir",    default="level_outputs",
                        help="Bulmaca JSON dosyalarının dizini")
    parser.add_argument("--file",   default=None,
                        help="Tek bir bulmaca dosyasını test et")
    parser.add_argument("--report", default=None,
                        help="Özet raporu kaydet (JSON)")

    args = parser.parse_args()

    if args.file:
        run_single(args.file)
    else:
        summary = run_batch(directory=args.dir, save_report=args.report)
        # Exit with code 1 if any puzzles are unsolvable
        if summary.get("unsolvable"):
            sys.exit(1)


if __name__ == "__main__":
    main()
