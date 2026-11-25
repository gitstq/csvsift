<div align="center">

# 🧰 csvsift

**Streaming CSV Command-Line Toolbox — Zero Dependencies, Low Memory, Encoding-Friendly**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/Release-v1.0.0-green.svg)](../../releases)

[简体中文](README.md) | English | [繁體中文](README.zh-TW.md)

</div>

---

## 🎉 Introduction

**csvsift** is a CSV command-line toolkit built entirely on the Python standard library. It distills the most common spreadsheet chores — previewing, profiling, statistics, filtering, sorting, deduplication, sampling, format conversion and structural validation — into a single command, with fully streaming processing so memory usage stays constant regardless of file size.

Three design principles:

- **Zero burden**: no third-party dependencies at all — `pip install csvsift` and you are done;
- **Large files, no sweat**: reading, filtering and sampling are all single-pass and streaming; multi-hundred-MB CSVs respond in seconds;
- **Encoding-friendly**: automatically detects UTF-8 / UTF-8-BOM / GBK / Big5 encodings and common delimiters, so mixed-encoding files just work.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 Auto-sniffing | Detects encodings (UTF-8 / BOM / GBK / Big5 / Shift-JIS…) and delimiters (`,` `;` `\t` `\|`) |
| 📊 Data profiling | `info` prints row/column counts, type hints, null ratio, cardinality and top values in one shot |
| 📈 Stats summary | `stats` reports min / max / mean / median / std for numeric columns |
| 🪄 Safe filtering | `filter` evaluates expressions through an AST whitelist — **no eval, no injection** |
| 🔀 Numeric-aware sorting | `sort` detects numeric columns; mixed types never break the order |
| 🎯 Reservoir sampling | `sample` draws random rows in a single pass, with reproducible seeds |
| 🔁 Format conversion | `convert` moves data freely between CSV / JSON / JSONL / XLSX |
| ✅ Structural validation | `validate` checks column drift and null ratios; non-zero exit codes fit CI pipelines |
| 🖥️ Tidy output | Aligned terminal tables with adaptive coloring; disable via `NO_COLOR` or `--no-color` |

## 🚀 Quick Start

**Install:**

```bash
# From source
pip install git+https://github.com/gitstq/csvsift.git

# Optional XLSX export support
pip install "csvsift[xlsx]"
```

**Up and running in 30 seconds:**

```bash
# Profile: rows, columns, types and null ratios at a glance
csvsift info sales.csv

# Filter: keep orders above 1000
csvsift filter -w 'amount > 1000' sales.csv -o big_orders.csv

# Hand off to downstream programs as JSON Lines
csvsift convert -t jsonl -o sales.jsonl sales.csv
```

No install needed either: `python -m csvsift info sales.csv`

## 📖 Usage Guide

### Command Overview

| Command | Purpose | Example |
|---------|---------|---------|
| `info` | Profile the data | `csvsift info data.csv` |
| `stats` | Numeric summary | `csvsift stats data.csv` |
| `head` / `tail` | Preview first/last rows | `csvsift tail -n 5 data.csv` |
| `select` | Pick columns (names or `1,3-5` indices) | `csvsift select -c name,amount data.csv` |
| `filter` | Expression filtering | `csvsift filter -w 'age > 30 and city == "NYC"' data.csv` |
| `sort` | Numeric-aware sorting | `csvsift sort -k amount --desc data.csv` |
| `dedupe` | Full-row or keyed dedup | `csvsift dedupe -k id data.csv -o clean.csv` |
| `sample` | Random sampling | `csvsift sample -n 100 --seed 42 data.csv -o s.csv` |
| `convert` | Format conversion | `csvsift convert -t xlsx -o out.xlsx data.csv` |
| `validate` | Structure check (CI-friendly) | `csvsift validate --strict data.csv` |

### Filter Expression Syntax

Only column names, literals, comparisons, arithmetic and `and / or / not / in` are allowed; invalid or dangerous syntax is rejected outright:

```bash
csvsift filter -w 'score >= 60 and not (name == "test")' exams.csv
csvsift filter -w 'price * qty > 10000' orders.csv        # arithmetic supported
csvsift filter -w 'city in ("NYC", "LA", "SF")' users.csv
```

### Global Options

- `-e/--encoding`, `-d/--delimiter`: override auto-detected encoding / delimiter;
- `-o/--output`: write to a file instead of stdout;
- `-f/--format csv|json|jsonl`: output format;
- `--no-color`: disable colored tables.

> 💡 **Memory note**: `sort` and `dedupe` materialize full results — filter or sample first for very large files. Everything else is streaming.

## 💡 Roadmap

- **v1.0.0 (current)**: first release covering preview / profiling / stats / filter / sort / dedupe / sample / convert / validate, with 25 unit tests;
- **Planned**:
  - `join` subcommand: streaming hash join between two CSVs;
  - `between` ranges and string functions in filter expressions;
  - External sorting for even lower memory peaks;
  - Publishing to PyPI.

Feature requests are welcome in [Issues](../../issues).

## 📦 Packaging & Deployment

```bash
# One-click build: tests → wheel/sdist → SHA256 checksums
bash scripts/build.sh

# Artifacts land in dist/, ready for Releases or private indexes
pip install dist/csvsift-1.0.0-py3-none-any.whl
```

You can also grab the wheel / sdist plus `SHA256SUMS.txt` from the [Releases](../../releases) page.

## 🤝 Contributing

Issues and PRs are welcome! Before contributing, please read [CONTRIBUTING.md](CONTRIBUTING.md):

- Commit messages follow the Angular convention (`feat:` / `fix:` / `docs:` …);
- New features come with unit tests; keep `python -m unittest discover -s tests` green;
- Respect the two architectural red lines: zero mandatory dependencies and streaming processing.

## 📄 License

Released under the [MIT License](LICENSE) — free for personal and commercial use.
