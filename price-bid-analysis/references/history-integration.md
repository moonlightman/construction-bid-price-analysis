# experience-memory v2 读取接入

回标分析为只读端，experience-memory 为写入维护端。两个 Skill 共用已配置的库，不按各自安装目录创建两个空库。

## 本地已配置库（用户选择本地运行时）

用户明确选择本地运行时采用 experience-memory 的 local 配置，无需飞书授权。正式数据位于其 data 目录。安装位置由宿主技能位置确定；读取失败不另外初始化空库。

使用 experience-memory 安装目录中的实际脚本路径执行：

```text
python <experience-memory目录>/scripts/history_store.py --config <experience-memory目录>/config/storage.json query --request query.json --output history-result.json
```

query.json 的 `library_type` 为 history_price，`name` 为通用项目名，`as_of` 为本次计价日，其他可选字段 spec/unit/scope/region/currency/tax_basis/installation_basis/price_type/exclude_project。实际路径来自平台配置，不猜路径。无当前计价日时先澄清或仅作无日期确认的候选阅读，不使用今天替代。

经验查询采用同一命令，library_type=experience，name 为核查主题；参考手册用 reference。结果包含 status、records、revision_id、candidate_limitations、requires_comparability_review、truncated。available 不等于已确认可比；数量被截断时缩小查询或增加 limit 后读取完整必要候选，不能据当前第一页推断全库。

AI 结合规格、工作范围、价格阶段和日期挑选证据，按项目去重、分组比较；保存原价、调整过程、原件来源及库版本。只返回总价的记录不能用于分项单价比价。

## 飞书配置库

飞书工作伙伴优先读取本包 `config/feishu-library.json`，执行 [固定库调用规则](feishu-host-library.md)。下面的运行配置不指本地 SQLite 的 storage.json。

从 experience-memory 的实际运行配置获取 folder_token/base_token/table_id/字段映射。使用当前环境已授权飞书只读工具分页读取当前版本，解析 payload_json 并按上述相同字段处理。不存在真实目标/权限时返回 not_configured/unavailable，不能声称空库或已查询。不得仅凭用户上传一个 Skill ZIP 就假定云端库已部署。

回标过程中不调用 put、导入、同步、usage 等写操作。用户授权保存最终谈判结果时，再由 experience-memory 工作流处理，保持同一 project_id。不要把用户在 Excel 中手改的测算价自动作为真实谈判价回写。

## 本地试跑的核对

调用查询时携带本次 project_id 作为 exclude_project，沿用底稿中同一项目编号。查看 records 中 source_resolution.file/snapshot 的实际路径；source.file 的相对路径不能按当前回标项目目录拼接。文件存在仍需核对 source.member、sheet/row/cell 或 page；来源缺失的记录保留限制，不充作已经核验的基准。

读取 source、installation_basis、freight_basis、tax_basis、price_basis 等原始口径，不能只拿单价。默认保存仍属经验库任务：报告完成后最终结果尚未提供，报告注明结果待补即可，不自动保存为最终谈判价格。用户随后提供最终清单时，沿用项目编号并按新阶段保存。
