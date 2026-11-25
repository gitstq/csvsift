"""终端表格渲染模块：对齐输出 + 可选 ANSI 着色。"""

from __future__ import annotations

import os
import shutil
from typing import Sequence


def use_color() -> bool:
    """仅在 TTY 且未显式禁用、NO_COLOR 未设置时启用颜色。"""
    return (
        sys_stdout_is_tty()
        and os.environ.get("NO_COLOR") is None
        and os.environ.get("CSVSIFT_NO_COLOR") is None
    )


def sys_stdout_is_tty() -> bool:
    import sys

    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def render_table(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    color: bool = True,
    max_width: int = 0,
) -> str:
    """渲染对齐表格；max_width>0 时单列超宽截断。"""
    if not header:
        return "(空表)"
    if max_width <= 0:
        max_width = shutil.get_terminal_size((100, 24)).columns // max(len(header), 1) or 20
    max_width = max(max_width, 8)

    def _display(cell: str) -> str:
        text = str(cell)
        return text if len(text) <= max_width else text[: max_width - 1] + "…"

    disp_rows = [[_display(c) for c in row] for row in rows]
    disp_header = [_display(c) for c in header]
    widths = [
        max(len(disp_header[i]), *(len(r[i]) for r in disp_rows)) if disp_rows else len(disp_header[i])
        for i in range(len(header))
    ]

    colorize = color and use_color()
    lines = []

    def fmt_row(cells, header_row=False, sep="│"):
        parts = []
        for i, cell in enumerate(cells):
            if colorize and header_row:
                parts.append(f"\033[1;36m{cell:<{widths[i]}}\033[0m")
            elif colorize:
                parts.append(f"{cell:<{widths[i]}}")
            else:
                parts.append(f"{cell:<{widths[i]}}")
        return " " + f" {sep} ".join(parts) + " "

    divider = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    lines.append(divider)
    lines.append(fmt_row(disp_header, header_row=True))
    lines.append(divider)
    for row in disp_rows:
        lines.append(fmt_row(row))
    lines.append(divider)
    return "\n".join(lines)
