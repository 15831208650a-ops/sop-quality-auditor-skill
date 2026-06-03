# SOP Quality Auditor Skill

审计底稿SOP质量审核 skill，用于按100分制审核 Markdown 格式 SOP，支持长文 SOP 的结构预检、分块审核和汇总评分。

## Files

- `SKILL.md`: 标准 skill 入口。
- `references/scoring_rules.md`: 评分细则。
- `scripts/sop_precheck.py`: 长文SOP结构预检脚本。
- `single-file-deploy.md`: 只支持单文件提示词平台的部署版。

## Precheck

```bash
python scripts/sop_precheck.py path/to/SOP.md --format markdown
```

## Notes

- 完整 skill 部署时使用 `SKILL.md`、`references/` 和 `scripts/`。
- 单文件平台可直接使用 `single-file-deploy.md`。
