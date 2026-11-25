"""数据画像与统计模块（info / stats 子命令的核心）。"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Iterator, Sequence


@dataclass
class ColumnProfile:
    """单列画像。"""

    name: str
    total: int = 0          # 非空值数量
    missing: int = 0        # 空值数量
    numeric: int = 0        # 可解析为数字的数量
    unique: int = 0         # 去重后取值数（有上限保护）
    min_len: int = 0        # 最短字符串长度
    max_len: int = 0        # 最长字符串长度
    top_values: list = field(default_factory=list)  # [(值, 次数)] top-3

    @property
    def type_hint(self) -> str:
        """类型推断提示：numeric 为主则 numeric，否则 text。"""
        if self.total and self.numeric / max(self.total, 1) >= 0.9:
            return "numeric"
        return "text"


class TableStats:
    """流式收集整表统计。

    说明：unique 计数与 top_values 依赖取值集合，极端高基数列
    可能占用较多内存；为控制风险，单列取值集合超过 _MAX_CARDINALITY
    时停止收集，unique 以“>=该值”呈现。
    """

    _MAX_CARDINALITY = 100_000

    def __init__(self, header: Sequence[str]):
        self.header = list(header)
        self.row_count = 0
        self._numeric_vals: dict[str, list[float]] = {c: [] for c in self.header}
        self._values: dict[str, dict[str, int]] = {c: {} for c in self.header}
        self._overflow: set[str] = set()
        self._profiles: dict[str, ColumnProfile] = {c: ColumnProfile(name=c) for c in self.header}

    def feed(self, row: Sequence[str]) -> None:
        """喂入一行，增量更新统计。"""
        self.row_count += 1
        for name, cell in zip(self.header, row):
            prof = self._profiles[name]
            if cell == "" or cell is None:
                prof.missing += 1
                continue
            prof.total += 1
            length = len(str(cell))
            if prof.total == 1:
                prof.min_len = prof.max_len = length
            else:
                prof.min_len = min(prof.min_len, length)
                prof.max_len = max(prof.max_len, length)

            # 数值尝试
            try:
                self._numeric_vals[name].append(float(cell))
                prof.numeric += 1
            except ValueError:
                pass

            # 取值集合（基数保护）
            if name not in self._overflow:
                counter = self._values[name]
                counter[cell] = counter.get(cell, 0) + 1
                if len(counter) > self._MAX_CARDINALITY:
                    self._overflow.add(name)
                    self._values[name] = {}

    def profiles(self) -> list[ColumnProfile]:
        """汇总各列画像。"""
        for name in self.header:
            prof = self._profiles[name]
            if name in self._overflow:
                prof.unique = self._MAX_CARDINALITY  # 触发上限，表示 >= 此值
            else:
                prof.unique = len(self._values[name])
                prof.top_values = sorted(
                    self._values[name].items(), key=lambda kv: kv[1], reverse=True
                )[:3]
        return [self._profiles[c] for c in self.header]

    def numeric_summary(self) -> dict[str, dict[str, float]]:
        """数值列的 min/max/mean/median/std 摘要。"""
        out: dict[str, dict[str, float]] = {}
        for name, vals in self._numeric_vals.items():
            if len(vals) < 1:
                continue
            summary: dict[str, float] = {
                "min": min(vals),
                "max": max(vals),
                "mean": round(statistics.fmean(vals), 4),
            }
            if len(vals) >= 2:
                summary["median"] = round(statistics.median(vals), 4)
                summary["std"] = round(statistics.stdev(vals), 4)
            out[name] = summary
        return out


def reservoir_sample(rows: Iterator[Sequence[str]], k: int, seed: int | None = None) -> list[Sequence[str]]:
    """蓄水池抽样：单遍流式随机抽取 k 行，无需预知总行数。"""
    import random

    rng = random.Random(seed)
    reservoir: list = []
    for index, row in enumerate(rows):
        if len(reservoir) < k:
            reservoir.append(row)
        else:
            j = rng.randint(0, index)
            if j < k:
                reservoir[j] = row
    rng.shuffle(reservoir)
    return reservoir


def sort_rows(
    rows: Iterator[Sequence[str]],
    header: Sequence[str],
    keys: list[str],
    descending: bool = False,
) -> list[Sequence[str]]:
    """按列排序（数值感知）。排序需全量物化，属固有代价。"""
    idx = [header.index(k) for k in keys]

    def sort_key(row):
        out = []
        for i in idx:
            cell = row[i] if i < len(row) else ""
            try:
                out.append((0, float(cell)))
            except ValueError:
                out.append((1, str(cell)))
        return out

    return sorted(rows, key=sort_key, reverse=descending)


def dedupe_rows(
    rows: Iterator[Sequence[str]],
    header: Sequence[str],
    keys: list[str] | None = None,
) -> tuple[list[Sequence[str]], int]:
    """去重：keys 为空按整行，否则按指定列。返回 (去重后行, 移除数)。"""
    idx = [header.index(k) for k in keys] if keys else None
    seen: set = set()
    kept: list = []
    removed = 0
    for row in rows:
        if idx is None:
            sig = tuple(row)
        else:
            sig = tuple(row[i] if i < len(row) else "" for i in idx)
        if sig in seen:
            removed += 1
            continue
        seen.add(sig)
        kept.append(row)
    return kept, removed
