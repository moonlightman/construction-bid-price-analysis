# 工程回标分析 Skill

当前版本：**price-bid-analysis v5.5.1**。

- [下载当前安装包](price-bid-analysis-v5.5.1.zip)：ZIP 根目录包含 SKILL.md，可直接交给支持 ZIP 的 Skill 导入器。
- [查看技能入口](price-bid-analysis/SKILL.md)：中文业务流程，AI 主导分析，经验库和历史报价库可选只读。
- [公式与可编辑输入](price-bid-analysis/references/formula-policy.md)：派生结果使用 Excel 公式，原件值与测算值分开。
- [工程表格布局](price-bid-analysis/references/reference-layout.md)：固定六表、横向报价矩阵、字体与图表验收。

支持仅 Excel、仅 PDF 或双格式的读取复核；固定 Word 七节及 Excel 六张基础表，允许增加补充分析页。联网证据链接与价格记录对应。

`scripts/` 为可选计算助手，不是自动评标决策引擎；`tests/` 为虚构数据的开发回归测试，**不包含在安装包中，也不能当作报价或历史证据**。运行测试：在 `price-bid-analysis` 目录执行 `python -m unittest discover -s tests -v`。

需要宿主环境提供文件读取、OCR/视觉、文档和表格生成能力。本仓库不包含用户投标原件、真实报价表或经验库数据。实际辅助库尚需按其读取接口对接。

旧文件 `construction-bid-price-analysis.zip` 保留为历史版本，请使用上面的当前安装包。
