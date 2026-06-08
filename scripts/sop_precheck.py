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
LONG_CONNECTOR_RE = re.compile(r"且|并|同时|另外|此外|同步|以及|并且|然后|再")
CONDITION_RE = re.compile(r"若|如|如果|当|对于|针对|在.+?时")
JUDGMENT_RE = re.compile(r"判断|确认|核对|检查|识别|评估|比较|分析|复核")
ACTION_RE = re.compile(
    r"获取|打开|进入|登录|下载|上传|导出|填写|录入|选择|点击|保存|提交|"
    r"检查|核对|确认|判断|比较|计算|分析|生成|编制|复核|记录|留存|归档"
)
EVIDENCE_RE = re.compile(r"留痕|截图|记录|保存|归档|底稿|证据|复核|签字|审批")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*|[①②③④⑤⑥⑦⑧⑨⑩])")
PUNCT_RE = re.compile(r"[，,；;、（）()]")
ALPHA_ITEM_RE = re.compile(r"^\s*[a-zA-Z][.)、]\s*")
CIRCLED_ITEM_RE = re.compile(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩]")
PLACEHOLDER_RE = re.compile(r"^\s*(?:|[-/]|N/?A|NA|TBD|待补充|同上)\s*$", re.I)


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
    current_h2 = ""
    current_h4 = ""
    current_h5 = ""
    for idx, line in enumerate(text.splitlines(), 1):
        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if level == 2:
                current_h2 = title
                current_h4 = ""
                current_h5 = ""
            elif level == 4:
                current_h4 = title
                current_h5 = ""
            elif level == 5:
                current_h5 = title
            continue
        if not line.strip() or line.lstrip().startswith("|"):
            continue
        if current_h4 not in ("基础操作指引", "进阶实操提示"):
            continue
        threshold = 80 if current_h4 == "基础操作指引" else 90
        severe_threshold = 120 if current_h4 == "基础操作指引" else 130
        ultra_threshold = 180 if current_h4 == "基础操作指引" else None
        for sentence in re.split(r"(?<=[。！？!?；;])", line):
            clean = strip_markdown(sentence)
            if len(clean) <= threshold:
                continue
            reasons = []
            connector = bool(LONG_CONNECTOR_RE.search(clean))
            punct_count = len(PUNCT_RE.findall(clean))
            action_count = len(ACTION_RE.findall(clean))
            element_count = sum(
                1
                for pattern in (CONDITION_RE, JUDGMENT_RE, ACTION_RE, EVIDENCE_RE)
                if pattern.search(clean)
            )
            if connector and action_count >= 2:
                reasons.append("连接词串联多个动作")
            if action_count >= 3:
                reasons.append("包含三个以上操作/检查动作")
            if element_count >= 3:
                reasons.append("条件/判断/操作/留痕要素过多")
            if punct_count >= 4:
                reasons.append("多个标点分隔操作点")
            if LIST_ITEM_RE.match(line) and (action_count >= 2 or punct_count >= 2):
                reasons.append("单个列表项承载多个步骤")
            if len(clean) > severe_threshold and (connector or action_count >= 2 or punct_count >= 2):
                reasons.append("超过严重长句阈值")
            if ultra_threshold and len(clean) > ultra_threshold:
                reasons.append("超过超长句阈值")
            if reasons:
                candidates.append(
                    {
                        "line": idx,
                        "module": current_h4,
                        "context": " -> ".join(
                            part for part in (current_h2, current_h4, current_h5) if part
                        ),
                        "length": len(clean),
                        "has_connector": connector,
                        "reasons": reasons,
                        "excerpt": sentence.strip()[:120],
                    }
                )
    return candidates[:100]


def table_after_heading(lines: list[str], heading_line: int) -> bool:
    window = lines[heading_line : min(len(lines), heading_line + 12)]
    return any(line.strip().startswith("|") and line.count("|") >= 2 for line in window)


def table_lines_after_heading(lines: list[str], heading_line: int) -> list[str]:
    window = lines[heading_line : min(len(lines), heading_line + 40)]
    table_lines = []
    started = False
    for line in window:
        if line.strip().startswith("|") and line.count("|") >= 2:
            table_lines.append(line)
            started = True
            continue
        if started:
            break
        if line.strip():
            continue
    return table_lines


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_separator_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells if cell.strip())


def is_filled(cell: str) -> bool:
    return not PLACEHOLDER_RE.fullmatch(cell.strip())


def gaap_table_content_check(lines: list[str], heading_line: int) -> dict[str, object]:
    table_lines = table_lines_after_heading(lines, heading_line)
    if not table_lines:
        return {"valid_data_rows": 0, "issue": "未发现Markdown表格"}

    rows = [split_table_row(line) for line in table_lines]
    header = next((row for row in rows if not is_separator_row(row)), [])
    data_rows = [row for row in rows[1:] if not is_separator_row(row)]
    normalized = [re.sub(r"\s+", "", cell).lower() for cell in header]
    core_indexes = {}
    for expected in ("分类", "差异项", "prc", "hkfrs"):
        try:
            core_indexes[expected] = normalized.index(expected)
        except ValueError:
            core_indexes[expected] = None

    missing_columns = [name for name, index in core_indexes.items() if index is None]
    valid_data_rows = 0
    for row in data_rows:
        filled_core = 0
        for name in ("差异项", "prc", "hkfrs"):
            index = core_indexes[name]
            if index is not None and index < len(row) and is_filled(row[index]):
                filled_core += 1
        if filled_core >= 2:
            valid_data_rows += 1

    issue = ""
    if missing_columns:
        issue = "缺少核心列：" + "、".join(missing_columns)
    elif not data_rows:
        issue = "只有表头和分隔行"
    elif valid_data_rows == 0:
        issue = "无有效差异内容行"
    return {
        "valid_data_rows": valid_data_rows,
        "data_rows": len(data_rows),
        "missing_columns": missing_columns,
        "issue": issue,
    }


def table_checks(text: str, headings: list[Heading]) -> dict[str, object]:
    lines = text.splitlines()
    result = {}
    for module in ("GAAP Difference", "Review Checklist", "常用网站"):
        module_headings = [h for h in headings if h.title == module or h.title.endswith(module)]
        checks = []
        for h in module_headings:
            item = {"line": h.line, "has_nearby_table": table_after_heading(lines, h.line)}
            if module == "GAAP Difference":
                item.update(gaap_table_content_check(lines, h.line))
            checks.append(item)
        result[module] = checks
    return result


def hierarchy_inversion_candidates(text: str) -> list[dict[str, object]]:
    issues = []
    lines = text.splitlines()
    current_h2 = ""
    current_h4 = ""
    current_h5 = ""
    for idx, line in enumerate(lines, 1):
        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if level == 2:
                current_h2 = title
                current_h4 = ""
                current_h5 = ""
            elif level == 4:
                current_h4 = title
                current_h5 = ""
            elif level == 5:
                current_h5 = title
            continue
        if current_h4 not in ("基础操作指引", "进阶实操提示"):
            continue
        if not ALPHA_ITEM_RE.match(line):
            continue
        alpha_indent = len(line) - len(line.lstrip())
        for next_idx in range(idx, min(len(lines), idx + 8)):
            next_line = lines[next_idx]
            if not next_line.strip():
                continue
            if HEADING_RE.match(next_line) or ALPHA_ITEM_RE.match(next_line):
                break
            if CIRCLED_ITEM_RE.match(next_line):
                circled_indent = len(next_line) - len(next_line.lstrip())
                if circled_indent > alpha_indent or line.rstrip().endswith(("：", ":")):
                    issues.append(
                        {
                            "line": idx,
                            "child_line": next_idx + 1,
                            "context": " -> ".join(
                                part for part in (current_h2, current_h4, current_h5) if part
                            ),
                            "parent_excerpt": line.strip()[:100],
                            "child_excerpt": next_line.strip()[:100],
                        }
                    )
                break
    return issues[:100]


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
        "hierarchy_inversion_candidates": hierarchy_inversion_candidates(text),
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
    print("## 需拆分长句候选")
    print()
    candidates = report["long_sentence_candidates"]
    if not candidates:
        print("未发现明显需拆分长句候选。")
    else:
        print("| 行号 | 模块 | 上下文 | 长度 | 触发原因 | 摘录 |")
        print("|------|------|--------|------|----------|------|")
        for item in candidates[:30]:
            module = str(item.get("module", "")).replace("|", "\\|")
            context = str(item.get("context", "")).replace("|", "\\|")
            reasons = "；".join(str(x) for x in item.get("reasons", [])).replace("|", "\\|")
            excerpt = str(item["excerpt"]).replace("|", "\\|")
            print(
                f"| {item['line']} | {module} | {context} | "
                f"{item['length']} | {reasons} | {excerpt} |"
            )
    print()
    print("## 编号层级倒挂候选")
    print()
    hierarchy_issues = report["hierarchy_inversion_candidates"]
    if not hierarchy_issues:
        print("未发现明显编号层级倒挂候选。")
    else:
        print("| 父项行号 | 子项行号 | 上下文 | 父项摘录 | 子项摘录 |")
        print("|----------|----------|--------|----------|----------|")
        for item in hierarchy_issues[:30]:
            context = str(item["context"]).replace("|", "\\|")
            parent = str(item["parent_excerpt"]).replace("|", "\\|")
            child = str(item["child_excerpt"]).replace("|", "\\|")
            print(f"| {item['line']} | {item['child_line']} | {context} | {parent} | {child} |")
    print()
    print("## 表格检查")
    print()
    print("| 模块 | 行号 | 附近是否有表格 | GAAP有效数据行 | GAAP问题 |")
    print("|------|------|----------------|----------------|----------|")
    for module, checks in report["table_checks"].items():
        if not checks:
            print(f"| {module} | 缺失 | 否 | - | - |")
            continue
        for item in checks:
            valid_rows = item.get("valid_data_rows", "-")
            issue = str(item.get("issue", "-") or "-").replace("|", "\\|")
            print(
                f"| {module} | {item['line']} | "
                f"{'是' if item['has_nearby_table'] else '否'} | {valid_rows} | {issue} |"
            )


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
