"""csvsift 命令行入口：argparse 定义与子命令实现。

子命令一览：
  info      数据画像（行列数、类型推断、缺失值）
  stats     数值列统计摘要
  head/tail 预览
  select    选列
  filter    安全表达式过滤
  sort      排序（数值感知）
  dedupe    去重
  sample    蓄水池随机抽样
  convert   CSV ↔ JSON / JSONL / XLSX 互转
  validate  结构校验（可用于 CI）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core.filter_expr import FilterSyntaxError, compile_filter
from .core.io_engine import (
    iter_rows,
    read_json_records,
    write_csv,
    write_json,
    write_jsonl,
    write_xlsx,
)
from .core.reader import sniff
from .core.stats import TableStats, dedupe_rows, reservoir_sample, sort_rows
from .core.table import render_table

PREVIEW_LIMIT = 40


def _add_common_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("file", help="输入 CSV 文件路径")
    p.add_argument("-e", "--encoding", help="强制指定编码（默认自动嗅探）")
    p.add_argument("-d", "--delimiter", help="强制指定分隔符（默认自动嗅探）")
    p.add_argument("--no-color", action="store_true", help="禁用终端着色")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csvsift",
        description="csvsift —— 流式 CSV 命令行工具箱：零依赖、低内存、中文编码友好",
    )
    parser.add_argument("-V", "--version", action="version", version=f"csvsift {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="数据画像：行列数、类型推断、缺失值")
    _add_common_flags(p_info)

    p_stats = sub.add_parser("stats", help="数值列统计摘要 min/max/mean/median/std")
    _add_common_flags(p_stats)

    p_head = sub.add_parser("head", help="预览前 N 行")
    _add_common_flags(p_head)
    p_head.add_argument("-n", "--rows", type=int, default=10, help="显示行数（默认 10）")

    p_tail = sub.add_parser("tail", help="预览后 N 行（环形缓冲流式实现）")
    _add_common_flags(p_tail)
    p_tail.add_argument("-n", "--rows", type=int, default=10, help="显示行数（默认 10）")

    p_select = sub.add_parser("select", help="选择列子集")
    _add_common_flags(p_select)
    p_select.add_argument("-c", "--columns", required=True, help="列名，逗号分隔，支持 1,3-5 序号")
    p_select.add_argument("-o", "--output", help="输出文件路径（默认 stdout）")
    p_select.add_argument("-f", "--format", choices=("csv", "json", "jsonl"), default="csv")
    p_select.add_argument("--out-encoding", default="utf-8")
    p_select.add_argument("--out-delimiter", default=",")
    p_select.add_argument("--no-header", action="store_true", help="输出不写表头")

    p_filter = sub.add_parser("filter", help="按安全表达式过滤行，如 -w 'age > 30 and city in (\"北京\",\"上海\")'")
    _add_common_flags(p_filter)
    p_filter.add_argument("-w", "--where", required=True, help="过滤表达式（AST 白名单，非 eval）")
    p_filter.add_argument("-o", "--output")
    p_filter.add_argument("-f", "--format", choices=("csv", "json", "jsonl"), default="csv")
    p_filter.add_argument("--out-encoding", default="utf-8")
    p_filter.add_argument("--out-delimiter", default=",")
    p_filter.add_argument("--no-header", action="store_true")

    p_sort = sub.add_parser("sort", help="按列排序（数值感知）")
    _add_common_flags(p_sort)
    p_sort.add_argument("-k", "--keys", required=True, help="排序列，逗号分隔")
    p_sort.add_argument("--desc", action="store_true", help="降序")
    p_sort.add_argument("-o", "--output")
    p_sort.add_argument("--out-delimiter", default=",")
    p_sort.add_argument("--out-encoding", default="utf-8")
    p_sort.add_argument("--no-header", action="store_true")

    p_dedupe = sub.add_parser("dedupe", help="去重（整行或按 key 列）")
    _add_common_flags(p_dedupe)
    p_dedupe.add_argument("-k", "--keys", help="去重键列，逗号分隔（默认整行）")
    p_dedupe.add_argument("-o", "--output")
    p_dedupe.add_argument("--out-delimiter", default=",")
    p_dedupe.add_argument("--out-encoding", default="utf-8")
    p_dedupe.add_argument("--no-header", action="store_true")

    p_sample = sub.add_parser("sample", help="随机抽样 N 行（蓄水池算法，单遍流式）")
    _add_common_flags(p_sample)
    p_sample.add_argument("-n", "--rows", type=int, required=True, help="抽样行数")
    p_sample.add_argument("--seed", type=int, help="随机种子（可复现）")
    p_sample.add_argument("-o", "--output")
    p_sample.add_argument("--out-delimiter", default=",")
    p_sample.add_argument("--out-encoding", default="utf-8")
    p_sample.add_argument("--no-header", action="store_true")

    p_convert = sub.add_parser("convert", help="CSV ↔ JSON / JSONL / XLSX 互转")
    _add_common_flags(p_convert)
    p_convert.add_argument("-t", "--to", required=True, choices=("csv", "json", "jsonl", "xlsx"))
    p_convert.add_argument("-o", "--output", required=True, help="输出文件路径")

    p_validate = sub.add_parser("validate", help="结构校验：列数漂移、空值率；退出码可用于 CI")
    _add_common_flags(p_validate)
    p_validate.add_argument("--max-null-ratio", type=float, default=0.5, help="列空值率阈值（默认 0.5）")
    p_validate.add_argument("--strict", action="store_true", help="严格模式：列数不一致即失败")
    return parser


# --------------------------------------------------------------------------
# 子命令实现
# --------------------------------------------------------------------------

def cmd_info(args) -> int:
    header, rows = iter_rows(args.file, args.encoding, args.delimiter)
    if not header:
        print("空文件", file=sys.stderr)
        return 1
    stats = TableStats(header)
    for row in rows:
        stats.feed(row)
    profiles = stats.profiles()
    table_rows = [
        [
            p.name,
            p.type_hint,
            f"{p.total}/{p.total + p.missing}",
            f"{p.missing / max(p.total + p.missing, 1):.1%}",
            str(p.unique),
            f"{p.min_len}-{p.max_len}",
            ", ".join(f"{v!r}x{n}" for v, n in p.top_values),
        ]
        for p in profiles
    ]
    out_header = ["列名", "类型", "非空/总行", "空值率", "唯一值", "长度范围", "高频值"]
    print(f"文件: {args.file}  行数: {stats.row_count}  列数: {len(header)}")
    print(render_table(out_header, table_rows, color=not args.no_color))
    return 0


def cmd_stats(args) -> int:
    header, rows = iter_rows(args.file, args.encoding, args.delimiter)
    stats = TableStats(header)
    for row in rows:
        stats.feed(row)
    summary = stats.numeric_summary()
    if not summary:
        print("未发现数值列", file=sys.stderr)
        return 1
    table_rows = [
        [col, f"{s['min']:g}", f"{s['max']:g}", f"{s['mean']:g}",
         f"{s.get('median', '-')}", f"{s.get('std', '-')}"]
        for col, s in summary.items()
    ]
    print(f"文件: {args.file}  行数: {stats.row_count}")
    print(render_table(["数值列", "min", "max", "mean", "median", "std"],
                       table_rows, color=not args.no_color))
    return 0


def cmd_head(args) -> int:
    header, rows = iter_rows(args.file, args.encoding, args.delimiter)
    preview = []
    for i, row in enumerate(rows):
        if i >= args.rows:
            break
        preview.append(row)
    print(render_table(header, preview, color=not args.no_color))
    return 0


def cmd_tail(args) -> int:
    # 环形缓冲，流式 O(n) 时间 / O(k) 空间
    header, rows = iter_rows(args.file, args.encoding, args.delimiter)
    buf: list = []
    n = args.rows
    for row in rows:
        if len(buf) < n:
            buf.append(row)
        else:
            buf.pop(0)
            buf.append(row)
    print(render_table(header, buf, color=not args.no_color))
    return 0


def _emit(args, header, rows_iter, row_count=None) -> None:
    """统一输出分发。"""
    fmt = getattr(args, "format", "csv")
    out = getattr(args, "output", None)
    enc = getattr(args, "out_encoding", "utf-8")
    delim = getattr(args, "out_delimiter", ",")
    no_header = getattr(args, "no_header", False)

    if fmt == "csv":
        write_csv([] if no_header else header, rows_iter, out, enc, delim)
    elif fmt == "json":
        write_json([] if no_header else header, rows_iter, out, enc)
    else:
        write_jsonl([] if no_header else header, rows_iter, out, enc)


def cmd_select(args) -> int:
    header, rows = iter_rows(args.file, args.encoding, args.delimiter)
    indices = _resolve_columns(header, args.columns)
    if not indices:
        print("未匹配到任何列", file=sys.stderr)
        return 1
    new_header = [header[i] for i in indices]

    def gen():
        for row in rows:
            yield [row[i] if i < len(row) else "" for i in indices]

    _emit(args, new_header, gen())
    return 0


def _resolve_columns(header: list[str], spec: str) -> list[int]:
    """解析列选择表达式：支持列名与 1-based 序号（含 3-5 区间）。"""
    result: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part.isdigit():
            num = int(part)
            if 1 <= num <= len(header):
                result.append(num - 1)
            continue
        if "-" in part and part.split("-")[0].isdigit():
            a, b = part.split("-", 1)
            if a.isdigit() and b.isdigit():
                result.extend(range(int(a) - 1, int(b)))
                continue
        if part in header:
            result.append(header.index(part))
        else:
            print(f"警告: 列 {part!r} 不存在，已跳过", file=sys.stderr)
    # 去重保序
    seen = set()
    uniq = []
    for i in result:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq


def cmd_filter(args) -> int:
    header, rows = iter_rows(args.file, args.encoding, args.delimiter)
    try:
        predicate = compile_filter(args.where)
    except FilterSyntaxError as exc:
        print(f"过滤表达式不合法: {exc}", file=sys.stderr)
        return 2

    def gen():
        for row in rows:
            record = dict(zip(header, row))
            try:
                if predicate(record):
                    yield row
            except (TypeError, ZeroDivisionError):
                # 数值不匹配等数据问题：跳过该行而非崩溃
                continue

    _emit(args, header, gen())
    return 0


def cmd_sort(args) -> int:
    header, rows = iter_rows(args.file, args.encoding, args.delimiter)
    for key in args.keys.split(","):
        if key.strip() not in header:
            print(f"排序列 {key!r} 不存在", file=sys.stderr)
            return 1
    keys = [k.strip() for k in args.keys.split(",")]
    sorted_rows = sort_rows(rows, header, keys, descending=args.desc)
    out = getattr(args, "output", None)
    if out:
        write_csv(header, sorted_rows, out, args.out_encoding, args.out_delimiter)
    else:
        preview = sorted_rows[:PREVIEW_LIMIT]
        print(render_table(header, preview, color=not args.no_color))
        if len(sorted_rows) > PREVIEW_LIMIT:
            print(f"共 {len(sorted_rows)} 行，{_WARNING_TRUNCATED}", file=sys.stderr)
    return 0


def cmd_dedupe(args) -> int:
    header, rows = iter_rows(args.file, args.encoding, args.delimiter)
    keys = [k.strip() for k in args.keys.split(",")] if args.keys else None
    if keys:
        for key in keys:
            if key not in header:
                print(f"去重键列 {key!r} 不存在", file=sys.stderr)
                return 1
    kept, removed = dedupe_rows(rows, header, keys)
    out = getattr(args, "output", None)
    if out:
        write_csv(header, kept, out, args.out_encoding, args.out_delimiter)
    else:
        preview = kept[:PREVIEW_LIMIT]
        print(render_table(header, preview, color=not args.no_color))
        print(f"移除重复 {removed} 行，剩余 {len(kept)} 行", file=sys.stderr)
    return 0


def cmd_sample(args) -> int:
    header, rows = iter_rows(args.file, args.encoding, args.delimiter)
    sampled = reservoir_sample(rows, args.rows, seed=args.seed)
    out = getattr(args, "output", None)
    if out:
        write_csv(header, sampled, out, args.out_encoding, args.out_delimiter)
    else:
        print(render_table(header, sampled, color=not args.no_color))
    return 0


def cmd_convert(args) -> int:
    src = Path(args.file)
    if args.to == "csv":
        # JSON/JSONL → CSV
        header, rows = read_json_records(src, args.encoding or "utf-8")
        write_csv(header, rows, args.output, "utf-8", ",")
        print(f"已写出 {len(rows)} 行 → {args.output}", file=sys.stderr)
        return 0

    header, rows = iter_rows(src, args.encoding, args.delimiter)
    count = 0
    if args.to == "json":
        write_json(header, rows, args.output)
        # 行数统计：重新流式计数
        _, rows2 = iter_rows(src, args.encoding, args.delimiter)
        count = sum(1 for _ in rows2)
    elif args.to == "jsonl":
        write_jsonl(header, rows, args.output)
        _, rows2 = iter_rows(src, args.encoding, args.delimiter)
        count = sum(1 for _ in rows2)
    else:  # xlsx
        count = write_xlsx(header, rows, args.output)
    print(f"已写出 {count} 行 → {args.output}", file=sys.stderr)
    return 0


def cmd_validate(args) -> int:
    header, rows = iter_rows(args.file, args.encoding, args.delimiter)
    if not header:
        print("FAIL: 空文件或无表头", file=sys.stderr)
        return 1
    ncols = len(header)
    stats = TableStats(header)
    bad_rows = 0
    for row in rows:
        stats.feed(row)
        if len(row) != ncols:
            bad_rows += 1
    problems = []
    if args.strict and bad_rows:
        problems.append(f"{bad_rows} 行列数与表头({ncols})不一致")
    for prof in stats.profiles():
        total = prof.total + prof.missing
        ratio = prof.missing / max(total, 1)
        if ratio > args.max_null_ratio:
            problems.append(f"列 {prof.name!r} 空值率 {ratio:.1%} 超过阈值 {args.max_null_ratio:.0%}")
    if problems:
        print("FAIL:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"OK: {stats.row_count} 行 x {ncols} 列，结构校验通过"
          f"（列数漂移 {bad_rows} 行）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = {
        "info": cmd_info,
        "stats": cmd_stats,
        "head": cmd_head,
        "tail": cmd_tail,
        "select": cmd_select,
        "filter": cmd_filter,
        "sort": cmd_sort,
        "dedupe": cmd_dedupe,
        "sample": cmd_sample,
        "convert": cmd_convert,
        "validate": cmd_validate,
    }[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
