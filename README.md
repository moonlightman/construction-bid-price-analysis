# 工程回标分析 Skill

当前版本：**price-bid-analysis v5.9-local**。

- [下载当前安装包](price-bid-analysis-v5.9-local.zip)：ZIP 根目录包含 SKILL.md，可直接交给支持 ZIP 的 Skill 导入器。
- [查看技能入口](price-bid-analysis/SKILL.md)：中文业务流程，AI 主导分析，经验库和历史报价库可选只读。
- [公式与可编辑输入](price-bid-analysis/references/formula-policy.md)：派生结果使用 Excel 公式，原件值与测算值分开。
- [工程表格布局](price-bid-analysis/references/reference-layout.md)：固定六表、横向报价矩阵、字体与图表验收。

支持仅 Excel、仅 PDF 或双格式的读取复核；固定 Word 七节及 Excel 六张基础表，允许增加补充分析页。联网证据链接与价格记录对应。

`scripts/` 为可选计算助手，不是自动评标决策引擎；`tests/` 为虚构数据的开发回归测试，**不包含在安装包中，也不能当作报价或历史证据**。运行测试：在 `price-bid-analysis` 目录执行 `python -m unittest discover -s tests -v`。

需要宿主环境提供文件读取、OCR/视觉、文档和表格生成能力。本仓库不包含用户投标原件、真实报价表或经验库数据。已提供 experience-memory v2 的只读查询约定；实际飞书目标及权限仍需配置。

旧文件 `construction-bid-price-analysis.zip` 保留为历史版本，请使用上面的当前安装包。

历史库接入见 [联动说明](price-bid-analysis/references/history-integration.md)：共用配置、保留来源和版本、候选需核对可比性、回标不写库。

费率计价见 [费率与暂估金额](price-bid-analysis/references/rate-pricing.md)：区分固定暂估金额直接计入与开放下浮率报价；同口径测算不覆盖原件金额。
