"""流式读取与写出模块。

核心设计：所有读写均为生成器/逐行流式，内存占用恒定，
百 MB 级文件也能稳定处理。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from .reader import sniff

# 数值列预览超限提示
_WARNING_TRUNCATED = "（结果仅显示前 40 行）"


def iter_rows(
    path: Path,
    encoding: str | None = None,
    delimiter: str | None = None,
) -> tuple[list[str], Iterator[list[str]]]:
    """流式读取 CSV，返回 (表头, 行迭代器)。

    嗅探编码与分隔符；行迭代器被消费完毕前文件句柄保持打开。
    """
    profile = sniff(Path(path), encoding, delimiter)
    fh = open(path, "r", encoding=profile.encoding, newline="")
    reader = csv.reader(fh, delimiter=profile.delimiter)
    try:
        header = next(reader)
    except StopIteration:
        fh.close()
        return [], iter([])
    return header, _row_gen(reader, fh)


def _row_gen(reader: csv.reader, fh) -> Iterator[list[str]]:
    """包装生成器，确保耗尽后关闭文件句柄。"""
    try:
        for row in reader:
            yield row
    finally:
        fh.close()


def open_writer(path: str | None, encoding: str, delimiter: str):
    """根据输出目标返回 csv.writer；path 为 None 时输出到 stdout。"""
    if path in (None, "-"):
        return csv.writer(sys.stdout, delimiter=delimiter, lineterminator="\n")
    fh = open(path, "w", encoding=encoding, newline="")
    return fh, csv.writer(fh, delimiter=delimiter, lineterminator="\n")


def write_csv(
    header: Sequence[str],
    rows: Iterable[Sequence[str]],
    out: str | None,
    encoding: str = "utf-8",
    delimiter: str = ",",
) -> None:
    """将 (表头, 行序列) 写为 CSV。"""
    if out in (None, "-"):
        writer = csv.writer(sys.stdout, delimiter=delimiter, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
        return
    with open(out, "w", encoding=encoding, newline="") as fh:
        writer = csv.writer(fh, delimiter=delimiter, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def write_json(
    header: Sequence[str],
    rows: Iterable[Sequence[str]],
    out: str | None,
    encoding: str = "utf-8",
    indent: int | None = 2,
) -> None:
    """将行序列写为 JSON 数组（对象数组，键为表头）。"""
    # JSON 需要整体序列化，超大文件建议走 jsonl
    records = [dict(zip(header, row)) for row in rows]
    payload = json.dumps(records, ensure_ascii=False, indent=indent)
    if out in (None, "-"):
        sys.stdout.write(payload + "\n")
    else:
        with open(out, "w", encoding=encoding) as fh:
            fh.write(payload + "\n")


def write_jsonl(
    header: Sequence[str],
    rows: Iterable[Sequence[str]],
    out: str | None,
    encoding: str = "utf-8",
) -> None:
    """将行序列写为 JSON Lines（每行一个对象，天然流式）。"""
    if out in (None, "-"):
        for row in rows:
            sys.stdout.write(json.dumps(dict(zip(header, row)), ensure_ascii=False) + "\n")
        return
    with open(out, "w", encoding=encoding) as fh:
        for row in rows:
            fh.write(json.dumps(dict(zip(header, row)), ensure_ascii=False) + "\n")


def write_xlsx(
    header: Sequence[str],
    rows: Iterable[Sequence[str]],
    out: str,
) -> int:
    """写出 XLSX（需要可选依赖 openpyxl）。返回写入行数。"""
    try:
        from openpyxl import Workbook  # noqa: 延迟导入，可选依赖
    except ImportError as exc:
        raise SystemExit(
            "导出 XLSX 需要可选依赖 openpyxl：pip install 'csvsift[xlsx]' 或 pip install openpyxl"
        ) from exc

    wb = Workbook()
    ws = wb.active
    ws.title = "data"
    ws.append(list(header))
    count = 0
    for row in rows:
        ws.append(_coerce_numbers(row))
        count += 1
    wb.save(out)
    return count


def _coerce_numbers(row: Sequence[str]) -> list:
    """纯数字字符串转为数值类型，便于 Excel 中直接计算。"""
    out = []
    for cell in row:
        try:
            out.append(int(cell))
        except ValueError:
            try:
                out.append(float(cell))
            except ValueError:
                out.append(cell)
    return out


def read_json_records(path: Path, encoding: str = "utf-8") -> tuple[list[str], list[list[str]]]:
    """读取 JSON / JSONL 文件为 (表头, 行矩阵)，供转换为 CSV。"""
    text = Path(path).read_text(encoding=encoding)
    if path.suffix.lower() in (".jsonl", ".ndjson") or (text.lstrip().startswith("{") and "\n{" in text):
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        records = json.loads(text)
    if not isinstance(records, list) or not records:
        raise SystemExit("JSON 文件必须是对象数组且非空")
    # 取所有键的并集，保持首条记录键序
    header: list[str] = []
    seen = set()
    for rec in records:
        for key in rec:
            if key not in seen:
                seen.add(key)
                header.append(key)
    rows = [[str(rec.get(k, "")) for k in header] for rec in records]
    return header, rows
