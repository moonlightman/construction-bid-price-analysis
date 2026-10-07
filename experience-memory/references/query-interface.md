# 供回标分析使用的只读接口

## 本地后端

```text
python scripts/history_store.py --config config/storage.json query --request query.json --output result.json
```

query.json：`library_type` 为 history_price / experience / reference；价格查询需 `name`；`as_of` 为本次已知计价日，未知时留空，只返回附时间限制的候选，不得据此确认历史基准，可带 spec、unit、scope、region、plant、currency、tax_basis、installation_basis、price_type 和 exclude_project。

名称只用于召回，不证明可比。脚本返回当前非停用记录，排除明确晚于 as_of 的定价；日期未知的仍作为带限制的候选返回，不参与确定基准。不同规格/地区等与查询不一致的记录列入 candidate_limitations，AI 可解释合理调整，不能被脚本自动认定不可用或直接可比。

返回统一对象：`schema`、`library_type`、`status`、`records`、`total_matches`、`truncated`、`limitations`。status: not_configured（未指定库）、unavailable（路径不存在/错误）、empty（库内该类无记录）、no_match（无本次候选）、available。缺配置与空库不同；查询不能新建一个空库冒充原库为空。

返回记录包含 revision_id、源字段、source_resolution（本地实际路径和文件存在状态）、candidate_limitations、requires_comparability_review=true。同一项目多家/多轮不是多个独立项目；AI 比价时分价格类型与口径，按项目去重再统计，保留所选记录编号和调整过程。不设至少三个项目的入库或使用门槛。

## 飞书后端

由配置定位多维表格，使用平台获批查询能力筛选候选并分页读取，解析 payload_json 为同一数据结构。不得只读第一页便称没有历史。发生权限失败返回 unavailable，不静默切换成空本地库。

返回当前版本；版本、同步状态不明的记录只作候选。读取后的数据统一给 AI 判断，不把搜索命中等同于可比。引用报告时写实际云盘/记录链接与原件表行定位。

## 与回标 Skill 的职责

回标 Skill 只执行 query 或飞书只读查询，不执行 put、导入或迁移。最终结果已确定且任务授权保存时由 experience-memory 接管写入；没有授权不暗中回写。库为空也继续控制价、同行、市场及其他适用分析。

## 算法经验查询

有analysis_feedback时连同review_outcome、assessment_type及来源返回；未复核标签不供训练或作为已证实风险。独立项目数按来源和业务项目去重，不以记录/版本数替代。详见 [算法反馈](algorithm-feedback.md)。
