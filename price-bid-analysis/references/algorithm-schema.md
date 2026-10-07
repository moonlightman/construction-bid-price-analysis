# 算法扩展数据契约 v1

字段均为可选扩展，不改变原 `price-bid-analysis/v5` 输入和历史价格记录身份。原值保留；JSON数值必须有限，未知为null。计算程序均只读文件，输出到指定路径。

## 结构分析输入

沿用 normalized-bids.json。可加 `structural_analysis`：

- `relationships` 列表：每项有 `relationship_id`、`numerator_item`、`denominator_item`（两个现有item_key）、`reason`、`confirmed`、`source`。source沿用file及页码/表行定位。只计算两个子目的相对同行指数之比；不混用物理消耗比。
- `scenarios` 列表：每项有 `scenario_id`、`item_key`、`delta_quantity`（可为负，但原量加增减量不能负）、`basis_confirmed`、`source`。这是来源明确的条件假设，不代表实际会发生。不确认或无来源输出not_evaluable。

原始数量和声明金额不得被情景覆盖。没有扩展时仍计算总价/核心子目及共同子集结构。

## 特征矩阵：features.json

顶层必须包含：

| 键 | 定义 |
|---|---|
| sample_unit | bidder_project 或 comparable_item |
| cohort_basis / cohort_confirmed | 比较群的工程、时间、单位、阶段等依据及确认 |
| feature_names | 唯一有序字段名 |
| feature_definitions | 每个字段的中文业务含义、单位、来源、计算与变换，键与feature_names完全一致 |
| feature_basis_confirmed | 特征口径已复核 |
| samples | 样本列表 |

每个sample有 `sample_id`、`entity_key`（去重业务身份，不能按版本另造样本）、`project_id`、`review_status`、`comparable`、`source_refs`（非空来源定位/记录版本列表）、`values`（与feature_names等长）。未经确认、不可比、缺来源/项目或含null的样本列明排除。输入重复sample_id或entity_key报错。没有自动填补。source_refs需在AI底稿中确认为有效，不是任意字符串的真实性认证。

来源可连接结构脚本的 item_structure / bidder_profiles；AI按业务选择及聚合，工具不自动把全部报价行混成训练样本。需要的标签、类别和外部知识不由脚本臆造。

## 阈值校准：calibration.json

顶层：`score_definition`（冻结算法/预处理/参数与分数来源）、`score_direction= higher_more_unusual`、`scores_oof_confirmed=true`、`validation_source`（项目外评分审计来源）、`holdout_project_ids`、`baseline_threshold`（验证前登记）、`loss_weights`（false_negative/false_positive/review三个非负数，非全零）、`samples`。

每个sample：`sample_id`、`project_id`、`score`、`label`（整数0/1）、`label_status=confirmed`、`label_source`、`model_training_project_ids`、`training_cutoff`、`scored_at`（后两者YYYY-MM-DD）。训练项目不能包含当前项目或任何最终留出项目；训练截止早于评分日。预处理和模型选择也须满足该隔离声明；脚本只能检查声明，不会证明评分文件内容真实。

同一项目包含多个样本时，loss按项目等权汇总：`(漏报权重*FN+误报权重*FP)/样本数 + 复核权重*被标记比例`；再平均所有校准项目。复核量是数量代理，不声称实际耗时。缺失、待复核、算法自打标签不得进入。批内探索分数不自动转换为独立项目评分。

## 结果与Excel映射

结构脚本输出 `total_statistics`、`total_analysis`、`item_statistics`、`item_structure`、`bidder_profiles`、`relationships`、`scenarios`，金额为原币种，百分比为小数。指数、差额、CV、占比在Excel用公式重现，不把JSON静态数值作为最终公式列。

复杂模型分数、簇、载荷、KDE和贝叶斯轨迹可作为“模型计算输出”导入数值，不伪装成Excel原生重算公式。邻列提供输入哈希、特征、参数、程序/依赖版本、样本来源和复算命令；输入修改后标注“模型待重新计算”，禁止仍称最新结果。模型输出后的简单金额和排序仍用公式。必须区分计算引擎输出与可编辑单元格公式。
