# experience-memory v2 读取接入

回标分析为只读端，experience-memory 为写入维护端。两个 Skill 共用已配置的库，不按各自安装目录创建两个空库。

## 本地已配置库

使用 experience-memory 安装目录中的实际脚本路径执行：

```text
python <experience-memory目录>/scripts/history_store.py --db <已配置历史库.sqlite> query --request query.json --output history-result.json
```

query.json 的 `library_type` 为 history_price，`name` 为通用项目名，`as_of` 为本次计价日，其他可选字段 spec/unit/scope/region/currency/tax_basis/installation_basis/price_type/exclude_project。实际路径来自平台配置，不猜路径。无当前计价日时先澄清或仅作无日期确认的候选阅读，不使用今天替代。

经验查询采用同一命令，library_type=experience，name 为核查主题；参考手册用 reference。结果包含 status、records、revision_id、candidate_limitations、requires_comparability_review、truncated。available 不等于已确认可比；数量被截断时缩小查询或增加 limit 后读取完整必要候选，不能据当前第一页推断全库。

AI 结合规格、工作范围、价格阶段和日期挑选证据，按项目去重、分组比较；保存原价、调整过程、原件来源及库版本。只返回总价的记录不能用于分项单价比价。

## 飞书配置库

从 experience-memory 的实际运行配置获取 folder_token/base_token/table_id/字段映射。使用当前环境已授权飞书只读工具分页读取当前版本，解析 payload_json 并按上述相同字段处理。不存在真实目标/权限时返回 not_configured/unavailable，不能声称空库或已查询。不得仅凭用户上传一个 Skill ZIP 就假定云端库已部署。

回标过程中不调用 put、导入、同步、usage 等写操作。用户授权保存最终谈判结果时，再由 experience-memory 工作流处理，保持同一 project_id。不要把用户在 Excel 中手改的测算价自动作为真实谈判价回写。
