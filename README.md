# SOP Quality Auditor V11

审计底稿 SOP 质量审核 Skill。用于按 V11 规则审核 Markdown 格式 SOP，并按 100 分制输出结构扫描、分块扣分证据、RC 覆盖检查和整改建议。

## 直接使用

如果平台支持 Skill 目录结构，下载整个仓库并使用根目录：

```text
sop-quality-auditor-skill/
```

如果平台只支持粘贴提示词或上传单个文件，例如 Kimi、网页聊天、知识库提示词，直接使用：

```text
single-file-deploy.md
```

## 文件说明

- `SKILL.md`：标准 Skill 入口，要求模型先读取详细规则。
- `references/scoring_rules.md`：V11 完整评分规则。
- `scripts/sop_precheck.py`：长文 SOP 结构预检脚本。
- `single-file-deploy.md`：单文件部署版，适合发给其他平台直接使用。

## 预检脚本

```bash
python scripts/sop_precheck.py path/to/SOP.md --format markdown
```

脚本只做结构预检，不代替最终评分。最终打分必须根据 `references/scoring_rules.md` 分块审核后汇总。

## 部署建议

- 其他平台优先使用 `single-file-deploy.md`，避免漏传引用规则。
- 打分时设置低随机性，例如 `temperature=0`。
- 必须先结构扫描，再分块审核，最后汇总评分。
- 扣分必须包含具体位置、原文短摘录和对应规则；没有可定位证据时不要扣分。
