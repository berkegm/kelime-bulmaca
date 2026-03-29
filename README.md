# kelime-bulmaca

A configurable Turkish word search puzzle generator and automated solver.

---

## What problem did I solve?

Designing word search puzzles by hand is tedious and doesn't scale — especially when you need dozens of them at different difficulty levels for a game. I built a generator that takes a word list, a difficulty preset, and an optional seed, and produces a valid puzzle with full placement metadata. A separate solver then verifies each puzzle is actually solvable, making it easy to catch grid-packing edge cases before they ship.

---

## What did I find?

- Denser grids (zor/hard) have a non-trivial failure rate when the word list is long and min-word-length is high — the placement algorithm occasionally can't fit all words within the maximum attempt budget. The metrics output flags these cases so they can be regenerated with a different seed.
- Difficulty score doesn't map linearly to player-perceived difficulty. Grid size and direction count dominate the score, but average word length is what actually makes a puzzle feel hard to a human. Worth weighting differently in future iterations.
- The solver runs in `O(rows × cols × 8 × max_word_length)` — fast enough on any grid the generator produces, but the placement metadata in the JSON makes it even faster in practice since it can verify the expected position first before doing a full scan.

---

## What should a game team do with this?

- Use `--seed` to make puzzle generation reproducible — the same seed always produces the same grid, so QA can retest specific puzzles by ID.
- Hook the solver into CI: run `python solver_bot.py --dir level_outputs` as part of the build and fail the pipeline if any puzzle returns exit code 1 (unsolvable). Catches regressions without manual review.
- The `--theme` filter lets content teams generate topic-specific packs (fruit, animals, colors) for seasonal events or educational modes without touching the code.

---

## Project Structure

```
kelime-bulmaca/
├── generator.py       # Puzzle generator
├── solver_bot.py      # Solvability verifier
├── word_list.json     # Word database with categories and frequency scores
└── level_outputs/     # Generated puzzles (JSON)
```

---

## Quick Start

```bash
# Generate one sample puzzle per difficulty level
python generator.py --samples

# Specific difficulty and seed
python generator.py --difficulty kolay --seed 42
python generator.py --difficulty orta  --seed 1337
python generator.py --difficulty zor   --seed 99999

# Generate multiple puzzles at once
python generator.py --difficulty zor --count 5

# Theme filter (based on categories in word_list.json)
python generator.py --difficulty orta --theme meyve

# Verify all generated puzzles
python solver_bot.py

# Verify a single file
python solver_bot.py --file level_outputs/kolay_42.json

# Save a summary report
python solver_bot.py --report report.json
```

No external dependencies — standard library only.

---

## Difficulty Levels

| Parameter | Easy (kolay) | Medium (orta) | Hard (zor) |
|---|---|---|---|
| Grid size | 9–12 | 12–15 | 15–20 |
| Word count | 5–8 | 9–13 | 14–20 |
| Directions | 2 (→ ↓) | 4 (→ ↓ ↘ ↙) | 8 (all) |
| Min word length | 3 | 4 | 5 |
| Max word length | 6 | 8 | 15 |

### Difficulty Score (0–100)

| Metric | Weight |
|---|---|
| Grid size | 20% |
| Word count | 25% |
| Avg word length | 25% |
| Letter diversity | 15% |
| Direction count | 15% |

Score ranges: `0–33` → Easy · `34–66` → Medium · `67–100` → Hard

---

## Output Format (JSON)

```json
{
  "level_id":     "kolay_42",
  "difficulty":   "kolay",
  "seed":         42,
  "grid":         [["A", "R", "..."], "..."],
  "words":        ["ELMA", "ARMUT"],
  "placed_words": [
    { "word": "ELMA", "row": 0, "col": 0, "direction": "RIGHT", "cells": [[0,0],[0,1],[0,2],[0,3]] }
  ],
  "grid_size":    [9, 9],
  "metrics":      { "score": 12.5, "level": "kolay", "metrics": { "..." : "..." } },
  "theme":        null,
  "created_at":   "2026-03-23T10:00:00"
}
```

---

## word_list.json Format

```json
{
  "words": [
    { "word": "elma", "length": 4, "frequency": 95, "category": "meyve" }
  ]
}
```

| Field | Description |
|---|---|
| `word` | Turkish word |
| `length` | Character count |
| `frequency` | Usage frequency 0–100 |
| `category` | Theme tag (e.g. `meyve`, `hayvan`, `renk`) |

---

## CLI Reference

### generator.py

| Argument | Description | Default |
|---|---|---|
| `--difficulty` | `kolay` / `orta` / `zor` | `orta` |
| `--seed` | Random seed | Random |
| `--count` | Number of puzzles to generate | `1` |
| `--output` | Output directory | `level_outputs` |
| `--theme` | Category filter | — |
| `--samples` | Generate one sample per difficulty | — |
| `--word-list` | Word list file | `word_list.json` |

### solver_bot.py

| Argument | Description | Default |
|---|---|---|
| `--dir` | Puzzle directory | `level_outputs` |
| `--file` | Single file to verify | — |
| `--report` | Save JSON summary | — |

Exit code `0` = all puzzles solvable · `1` = at least one puzzle has missing words.

---

## License

MIT
