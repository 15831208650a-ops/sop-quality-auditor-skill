# SOP Quality Auditor 零码部署说明

这是用于零码平台的审计底稿SOP质量审核Skill。零码支持Skill目录部署，因此本仓库不再维护单文件部署版。

## 部署方式

在零码中部署整个目录：

```text
sop-quality-auditor-skill/
```

目录内必须包含：

```text
SKILL.md
references/scoring_rules.md
scripts/sop_precheck.py
```

其中：

- `SKILL.md`：零码执行入口，只规定流程和优先级。
- `references/scoring_rules.md`：唯一打分细则来源。
- `scripts/sop_precheck.py`：结构预检脚本，可辅助识别明显结构问题。

## 使用方式

上传待审核的Markdown格式SOP后，使用类似提示：

```text
请使用SOP质量审核Skill审核该SOP，按100分制生成Markdown质量审核报告。必须先结构扫描，再分块审核，最后汇总评分；本次问答内必须输出报告结果，所有扣分问题都要逐条列出具体位置和整改建议。
```

如果需要强制生成文件：

```text
请生成Markdown格式审核报告文件，并给出文件路径。
```

## 核心执行逻辑

- 最终打分唯一依据是 `references/scoring_rules.md`。
- `SKILL.md` 不替代评分规则。
- 先结构扫描，再按六大板块分块审核，最后汇总评分。
- 扣分必须可定位、可复核、可解释。
- 触发任一0容忍问题时，最终结论必须为“必须修改”。
- 报告中必须在“关键扣分明细”前列出“0容忍必须修改问题”模块。
- 一次问答内必须产出报告结果，不得只停留在分析过程。
- 同类问题可以复用整改建议，但每条扣分必须逐条列出具体位置、原文短摘录和扣分值。

## 预检脚本

如果零码环境允许运行Python，可先执行：

```bash
python scripts/sop_precheck.py path/to/SOP.md --format markdown
```

脚本只做结构预检，不代替最终评分。

它主要识别：

- 必备模块缺失。
- PSP缺少基础操作指引。
- 草稿标记。
- 需拆分长句候选。
- 编号层级倒挂候选。
- 六级标题承载具体任务。
- GAAP Difference空表或缺少有效数据行。
- 表格存在性问题。

最终评分仍必须按 `references/scoring_rules.md` 执行。
