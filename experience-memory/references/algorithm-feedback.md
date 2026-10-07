# 结构分析与算法复核经验

仅在用户授权保存结果/导入历史材料的批次中处理；回标分析读库不触发保存。本规范不新增Base、表或字段，不自动训练模型。

## 分开保存四种东西

1. 原始报价/最终谈判/合同/结算价格：按原价格规范进入历史价格，各阶段保留独立身份。异常分数、聚类标签、情景差额、测算参照均不是成交价。
2. 分析发现：`kind=experience`，经验与参考表，关联项目。AI判断未被复核时保留pending；记录事实、解释、替代解释与限制，不将算法提示写成已证实问题。
3. 复核反馈：经验记录追加版本，保留原finding_id、复核来源、日期、确认/排除/仍存疑结论。排除异常不意味着该投标人其他项目均正常。
4. 方法/参数版本与验证摘要：`kind=reference`，经验与参考表，记录适用范围、特征定义、样本单位、独立项目数、项目隔离、模型/参数/依赖版本、验证指标和限制。一次项目结果不自动提升为通用规则。

## 可选扩展字段

在既有完整记录JSON中保存 `analysis_feedback` 对象；若经验表未提供该字段或可用正文/附件，报告具体映射缺口，交付待同步底稿，不擅自改表。

`analysis_feedback` 包含：

- `finding_id`、`analysis_run_id`、`dimension`（total/core_item/linkage/behavior）、`item_keys`。
- `method`、`method_version`、`input_sha256`、`parameters`、`sample_unit`、`sample_count`、`independent_project_count`、`evidence_refs`。
- `assessment_type`：exploratory / validated；validated需提供 `validation_evidence`，不能仅因为软件运行成功。
- `review_outcome`：unreviewed / confirmed_issue / cleared / unresolved。
- `review_source`、`reviewed_at`：confirmed_issue或cleared必须有真实复核来源和日期；unreviewed/unresolved不能记为confirmed经验。
- `applicability`、`alternative_explanations`、`affected_amount_basis`；未知留空。

本地history_store.py验证上述关键状态；它不证明来源真实。飞书宿主沿用相同约束，先查重后追加、再回读项目关联、状态、来源及JSON关键字段。批次授权不代表允许自动更新正式评审阈值。

## 查询用于新分析时

读取最新有效版本；区分事实、候选方法与已验证方法，不把历史算法输出当作人工真值。核对当前工程、规格、时间、价格阶段及数量口径。按来源、业务身份和项目去重，旧版本、同项目多轮不扩大独立项目数。

训练候选池排除pending、冲突、失效及未复核标签；它们仍可返回给AI作为带限制线索。查询/分析不自动生成或回写标签，不自动清洗源库，也不把“无争议”直接标为正常。
