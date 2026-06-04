#!/usr/bin/env python3
"""Precheck Markdown SOP structure before model-based scoring."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


NON_PSP_TITLES = {
    "使用说明",
    "工作流程图",
    "PBC示例",
    "GAAP Difference",
    "Review Checklist",
    "常用网站",
}

REQUIRED_MODULES = [
    "使用说明",
    "工作流程图",
    "PBC示例",
    "基础操作指引",
    "进阶实操提示",
    "易错点",
    "GAAP Difference",
    "Review Checklist",
    "常用网站",
]

CHINESE_NUMERAL_RE = re.compile(r"^[一二三四五六七八九十百]+[、.．]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
COMMENT_PATTERNS = [
    ("Markdown注释", re.compile(r"<!--.*?-->", re.S)),
    ("代码注释", re.compile(r"^\s*//|/\*|\*/", re.M)),
    ("草稿标记", re.compile(r"TODO|FIXME|待补充|审核中", re.I)),
]
LONG_CONNECTOR_RE = re.compile(r"且|并|同时|另外|此外|同步|以及")


@dataclass
class Heading:
    line: int
    level: int
    title: str


@dataclass
class PspSection:
    title: str
    line: int
    modules: dict[str, int]
    steps: int


def read_text(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace"


def iter_headings(text: str) -> list[Heading]:
    headings: list[Heading] = []
    for idx, line in enumerate(text.splitlines(), 1):
        match = HEADING_RE.match(line)
        if match:
            headings.append(Heading(idx, len(match.group(1)), match.group(2).strip()))
    return headings


def is_psp_h2(title: str) -> bool:
    clean = title.strip()
    without_number = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", clean)
    if clean in NON_PSP_TITLES or without_number in NON_PSP_TITLES:
        return False
    if clean.startswith(("附录", "参考资料", "版本记录")):
        return False
    return clean == "汇总" or bool(CHINESE_NUMERAL_RE.match(clean))


def collect_psps(headings: list[Heading]) -> list[PspSection]:
    psps: list[PspSection] = []
    h2_indexes = [i for i, h in enumerate(headings) if h.level == 2]
    for pos, idx in enumerate(h2_indexes):
        h2 = headings[idx]
        if not is_psp_h2(h2.title):
            continue
        next_idx = h2_indexes[pos + 1] if pos + 1 < len(h2_indexes) else len(headings)
        child_headings = headings[idx + 1 : next_idx]
        modules = {}
        steps = 0
        for h in child_headings:
            if h.level == 3 and re.search(r"^第.+步[:：]", h.title):
                steps += 1
            if h.level == 4 and h.title in ("基础操作指引", "进阶实操提示", "易错点"):
                modules[h.title] = h.line
        psps.append(PspSection(h2.title, h2.line, modules, steps))
    return psps


def find_required_modules(headings: Iterable[Heading]) -> dict[str, list[int]]:
    found = {name: [] for name in REQUIRED_MODULES}
    for h in headings:
        title = h.title.strip()
        for name in REQUIRED_MODULES:
            if title == name or title.endswith(name):
                found[name].append(h.line)
    return found


def find_comments(text: str) -> list[dict[str, object]]:
    issues = []
    for label, pattern in COMMENT_PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            excerpt = match.group(0).replace("\n", " ")[:80]
            issues.append({"type": label, "line": line, "excerpt": excerpt})
    return issues


def strip_markdown(line: str) -> str:
    line = re.sub(r"`[^`]*`", "", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
    line = re.sub(r"https?://\S+", "", line)
    line = re.sub(r"[*_#>|-]", "", line)
    return re.sub(r"\s+", "", line)


def sentence_candidates(text: str) -> list[dict[str, object]]:
    candidates = []
    for idx, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("|"):
            continue
        if HEADING_RE.match(line):
            continue
        for sentence in re.split(r"(?<=[。！？!?；;])", line):
            clean = strip_markdown(sentence)
            if len(clean) > 100 and (LONG_CONNECTOR_RE.search(clean) or len(clean) > 120):
                candidates.append(
                    {
                        "line": idx,
                        "length": len(clean),
                        "has_connector": bool(LONG_CONNECTOR_RE.search(clean)),
                        "excerpt": sentence.strip()[:120],
                    }
                )
    return candidates[:100]


def table_after_heading(lines: list[str], heading_line: int) -> bool:
    window = lines[heading_line : min(len(lines), heading_line + 12)]
    return any(line.strip().startswith("|") and line.count("|") >= 2 for line in window)


def table_checks(text: str, headings: list[Heading]) -> dict[str, object]:
    lines = text.splitlines()
    result = {}
    for module in ("GAAP Difference", "Review Checklist", "常用网站"):
        module_headings = [h for h in headings if h.title == module or h.title.endswith(module)]
        result[module] = [
            {"line": h.line, "has_nearby_table": table_after_heading(lines, h.line)}
            for h in module_headings
        ]
    return result


def build_report(path: Path) -> dict[str, object]:
    text, encoding = read_text(path)
    headings = iter_headings(text)
    required = find_required_modules(headings)
    psps = collect_psps(headings)
    missing_required = [name for name, lines in required.items() if not lines]
    psp_missing = [
        {
            "title": p.title,
            "line": p.line,
            "missing_modules": [
                name
                for name in ("基础操作指引",)
                if name not in p.modules
            ],
        }
        for p in psps
        if any(name not in p.modules for name in ("基础操作指引",))
    ]
    title = next((h.title for h in headings if h.level == 1), "")
    return {
        "file": str(path),
        "encoding": encoding,
        "title": title,
        "line_count": text.count("\n") + 1,
        "char_count": len(text),
        "heading_count": len(headings),
        "psp_count": len(psps),
        "required_modules": required,
        "missing_required_modules": missing_required,
        "psp_sections": [asdict(p) for p in psps],
        "psp_missing_core_modules": psp_missing,
        "comments_or_draft_marks": find_comments(text),
        "long_sentence_candidates": sentence_candidates(text),
        "table_checks": table_checks(text, headings),
    }


def print_markdown(report: dict[str, object]) -> None:
    print("# SOP结构预检报告")
    print()
    print(f"- 文件：`{report['file']}`")
    print(f"- 编码：`{report['encoding']}`")
    print(f"- 标题：{report['title'] or '未识别'}")
    print(f"- 行数：{report['line_count']}")
    print(f"- 字符数：{report['char_count']}")
    print(f"- 标题数：{report['heading_count']}")
    print(f"- PSP数：{report['psp_count']}")
    print()
    print("## 必备模块")
    print()
    print("| 模块 | 出现行号 |")
    print("|------|----------|")
    for name, lines in report["required_modules"].items():
        line_text = ", ".join(str(x) for x in lines) if lines else "缺失"
        print(f"| {name} | {line_text} |")
    print()
    print("## PSP基础操作指引缺失")
    print()
    missing = report["psp_missing_core_modules"]
    if not missing:
        print("未发现PSP基础操作指引缺失。")
    else:
        print("| PSP | 行号 | 缺失模块 |")
        print("|-----|------|----------|")
        for item in missing:
            print(f"| {item['title']} | {item['line']} | {', '.join(item['missing_modules'])} |")
    print()
    print("## 注释或草稿标记")
    print()
    comments = report["comments_or_draft_marks"]
    if not comments:
        print("未发现。")
    else:
        print("| 类型 | 行号 | 摘录 |")
        print("|------|------|------|")
        for item in comments[:50]:
            print(f"| {item['type']} | {item['line']} | `{item['excerpt']}` |")
    print()
    print("## 长句候选")
    print()
    candidates = report["long_sentence_candidates"]
    if not candidates:
        print("未发现明显长句候选。")
    else:
        print("| 行号 | 长度 | 含连接词 | 摘录 |")
        print("|------|------|----------|------|")
        for item in candidates[:30]:
            connector = "是" if item["has_connector"] else "否"
            excerpt = str(item["excerpt"]).replace("|", "\\|")
            print(f"| {item['line']} | {item['length']} | {connector} | {excerpt} |")
    print()
    print("## 表格检查")
    print()
    print("| 模块 | 行号 | 附近是否有表格 |")
    print("|------|------|----------------|")
    for module, checks in report["table_checks"].items():
        if not checks:
            print(f"| {module} | 缺失 | 否 |")
            continue
        for item in checks:
            print(f"| {module} | {item['line']} | {'是' if item['has_nearby_table'] else '否'} |")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    report = build_report(args.path)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_markdown(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
