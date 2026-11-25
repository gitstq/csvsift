"""csvsift 单元测试。

运行方式：python -m unittest discover -s tests -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# 保证可从仓库根目录直接导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from csvsift.core.filter_expr import FilterSyntaxError, compile_filter  # noqa: E402
from csvsift.core.reader import detect_delimiter, detect_encoding, sniff  # noqa: E402
from csvsift.core.stats import dedupe_rows, reservoir_sample, sort_rows  # noqa: E402
from csvsift.cli import main as cli_main  # noqa: E402


def _write(tmp: str, text: str, encoding: str = "utf-8", name: str = "data.csv") -> Path:
    path = Path(tmp) / name
    path.write_text(text, encoding=encoding)
    return path


SAMPLE = (
    "name,age,city,score\n"
    "Alice,30,北京,88.5\n"
    "Bob,25,上海,72\n"
    "Carol,35,北京,91\n"
    "Dave,28,广州,66.5\n"
    "Eve,,上海,80\n"
)


class TestSniff(unittest.TestCase):
    """编码与分隔符嗅探。"""

    def test_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, SAMPLE)
            profile = sniff(path)
            self.assertEqual(profile.encoding, "utf-8-sig" if False else profile.encoding)
            self.assertIn(profile.encoding, ("utf-8", "utf-8-sig"))
            self.assertEqual(profile.delimiter, ",")

    def test_gbk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gbk.csv"
            path.write_text("姓名,城市\n张三,北京\n李四,上海\n", encoding="gb18030")
            profile = sniff(path)
            self.assertEqual(profile.encoding, "gb18030")

    def test_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bom.csv"
            path.write_text(SAMPLE, encoding="utf-8-sig")
            self.assertEqual(detect_encoding(path), "utf-8-sig")

    def test_delimiter_tsv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, "a\tb\tc\n1\t2\t3\n")
            self.assertEqual(detect_delimiter(path, "utf-8"), "\t")


class TestFilterExpr(unittest.TestCase):
    """安全过滤表达式：白名单求值 + 注入防护。"""

    def setUp(self):
        self.row = {"name": "Alice", "age": "30", "score": "88.5", "city": "北京"}

    def test_numeric_compare(self):
        pred = compile_filter("age > 25")
        self.assertTrue(pred(self.row))
        self.assertFalse(pred(dict(self.row, age="20")))

    def test_and_or_not(self):
        pred = compile_filter('age > 25 and city == "北京"')
        self.assertTrue(pred(self.row))
        pred = compile_filter('city in ("北京", "上海")')
        self.assertTrue(pred(self.row))
        pred = compile_filter("not (age > 25)")
        self.assertFalse(pred(self.row))

    def test_arithmetic(self):
        pred = compile_filter("age * 2 >= 60")
        self.assertTrue(pred(self.row))
        pred = compile_filter("score / 2 > 40")
        self.assertTrue(pred(self.row))

    def test_missing_column(self):
        pred = compile_filter("ghost > 1")
        self.assertFalse(pred(self.row))

    def test_injection_blocked(self):
        # 危险语法必须被拒绝
        for bad in (
            "__import__('os').system('ls')",
            "().__class__.__bases__",
            "open('/etc/passwd')",
            "lambda: 1",
            "age > 1; import os",
        ):
            with self.assertRaises(FilterSyntaxError):
                compile_filter(bad)


class TestOps(unittest.TestCase):
    """排序 / 去重 / 抽样。"""

    ROWS = [
        ["Alice", "30", "88.5"],
        ["Bob", "25", "72"],
        ["Carol", "35", "91"],
    ]
    HEADER = ["name", "age", "score"]

    def test_sort_numeric(self):
        out = sort_rows(iter(self.ROWS), self.HEADER, ["age"])
        self.assertEqual([r[0] for r in out], ["Bob", "Alice", "Carol"])
        out = sort_rows(iter(self.ROWS), self.HEADER, ["age"], descending=True)
        self.assertEqual([r[0] for r in out], ["Carol", "Alice", "Bob"])

    def test_sort_mixed(self):
        rows = [["b"], ["10"], ["a"]]
        out = sort_rows(iter(rows), ["c"], ["c"])
        # 数值优先于字符串
        self.assertEqual(out[0][0], "10")

    def test_dedupe_full_and_key(self):
        rows = [["a", "1"], ["a", "1"], ["a", "2"]]
        kept, removed = dedupe_rows(iter(rows), ["c1", "c2"])
        self.assertEqual(len(kept), 2)
        self.assertEqual(removed, 1)
        kept, removed = dedupe_rows(iter(rows), ["c1", "c2"], keys=["c1"])
        self.assertEqual(len(kept), 1)

    def test_sample_deterministic(self):
        big = [[str(i)] for i in range(1000)]
        a = reservoir_sample(iter(big), 10, seed=42)
        b = reservoir_sample(iter(big), 10, seed=42)
        self.assertEqual([r[0] for r in a], [r[0] for r in b])
        self.assertEqual(len(a), 10)
        c = reservoir_sample(iter(big), 10, seed=7)
        self.assertNotEqual([r[0] for r in a], [r[0] for r in c])


class TestCli(unittest.TestCase):
    """CLI 端到端测试（子进程 + 进程内）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.csv_path = _write(cls.tmp, SAMPLE)

    def _run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, "-m", "csvsift", *argv],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent.parent,
        )

    def test_info(self):
        r = self._run_cli("info", str(self.csv_path))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Alice", r.stdout)

    def test_stats(self):
        r = self._run_cli("stats", str(self.csv_path))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mean", r.stdout)

    def test_head_tail(self):
        r = self._run_cli("head", "-n", "2", str(self.csv_path))
        self.assertEqual(r.returncode, 0)
        self.assertIn("Alice", r.stdout)
        self.assertNotIn("Carol", r.stdout)
        r = self._run_cli("tail", "-n", "1", str(self.csv_path))
        self.assertIn("Eve", r.stdout)

    def test_filter_to_file(self):
        out = Path(self.tmp) / "filtered.csv"
        r = self._run_cli("filter", "-w", "age > 26", "-o", str(out), str(self.csv_path))
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        # 表头 + Alice(30) + Carol(35) + Dave(28)；Bob(25) 与 Eve(空) 被排除
        self.assertEqual(len(lines), 4)
        self.assertIn("Alice", lines[1])
        self.assertNotIn("Bob", out.read_text(encoding="utf-8"))

    def test_filter_bad_expr_exit_code(self):
        r = self._run_cli("filter", "-w", "__import__('os')", str(self.csv_path))
        self.assertEqual(r.returncode, 2)

    def test_select(self):
        r = self._run_cli("select", "-c", "name,score", str(self.csv_path))
        self.assertEqual(r.returncode, 0)
        self.assertIn("name", r.stdout)
        self.assertNotIn("city", r.stdout)

    def test_dedupe_to_file(self):
        dup = _write(self.tmp, SAMPLE + "Alice,30,北京,88.5\n", "utf-8", name="dup.csv")
        out = Path(self.tmp) / "dedup.csv"
        r = self._run_cli("dedupe", "-o", str(out), str(dup))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(out.read_text(encoding="utf-8").strip().splitlines()), 6)

    def test_sample_seed(self):
        r = self._run_cli("sample", "-n", "2", "--seed", "1", str(self.csv_path))
        self.assertEqual(r.returncode, 0)

    def test_convert_csv_to_json_roundtrip(self):
        out = Path(self.tmp) / "data.json"
        r = self._run_cli("convert", "-t", "json", "-o", str(out), str(self.csv_path))
        self.assertEqual(r.returncode, 0, r.stderr)
        records = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(records), 5)
        self.assertEqual(records[0]["name"], "Alice")
        # 回转 CSV
        back = Path(self.tmp) / "back.csv"
        r = self._run_cli("convert", "-t", "csv", "-o", str(back), str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(back.read_text(encoding="utf-8").strip().splitlines()), 6)

    def test_convert_jsonl(self):
        out = Path(self.tmp) / "data.jsonl"
        r = self._run_cli("convert", "-t", "jsonl", "-o", str(out), str(self.csv_path))
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 5)
        json.loads(lines[0])  # 每行均为合法 JSON

    def test_validate_ok_and_fail(self):
        r = self._run_cli("validate", str(self.csv_path))
        self.assertEqual(r.returncode, 0, r.stderr)
        # 严苛阈值触发失败
        r = self._run_cli("validate", "--max-null-ratio", "0", str(self.csv_path))
        self.assertEqual(r.returncode, 1)
        # 列数漂移触发失败
        broken = Path(self.tmp) / "broken.csv"
        broken.write_text("a,b\n1,2\n3\n", encoding="utf-8")
        r = self._run_cli("validate", "--strict", str(broken))
        self.assertEqual(r.returncode, 1)

    def test_in_process_main(self):
        rc = cli_main(["head", "-n", "1", str(self.csv_path)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
