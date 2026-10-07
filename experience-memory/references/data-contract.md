# 记录规范 v2

一条价格记录对应一个项目、供应商、轮次/阶段、清单项及计价口径。`record_id` 稳定，`revision_id` 由内容哈希生成；同一记录修订采用 expected_revision 防止覆盖并发修改。跨阶段另建记录，不把报价变成合同价。

## 价格字段

- `record_id`、`project_id`、`project_name`、`supplier`、`bidder_id`、`round_id`、`item_key`。
- `kind`: price / experience / reference；只有 price 进入价格检索。
- `price_type`: quote / final_negotiated / awarded / contract / settlement / unknown。
- `level`: item / total；总价记录不能作为分项单价返回。
- `name`、`spec`、`unit`、`scope`、`region`、`plant`、`currency`、`tax_basis`、`freight_basis`、`installation_basis`、`discount_basis`。
- `pricing_date`：已知报价/定价日 YYYY-MM-DD；`valid_from`、`valid_to` 为合同适用期。年度或文件名不能推造精确日期。跨年度文件不直接判为未来数据，也不能仅凭开始年份认定可用。
- `quantity`、`unit_price`、`line_total`、`total_price`：有限数值或 null。保留原始精度；负数须解释为折扣等，不能混入正向工程单价统计。
- `material_unit_price`、`material_line_total`、`installation_unit_price`、`installation_line_total`、`price_basis`、`additivity_confirmed`：保留分列，不擅自拆分或合计。
- `source`：file/file_token/url 及 sheet+row/cell 或 page/location；可附 sha256。`report_url`、`confirmation` 关联真实报告与结果确认依据；没有 token 时先保留本地来源，标待同步。
- `status`: confirmed / pending / inactive；`reason` 为确认、修改或停用理由。

价格有来源即可作为 pending 保存；confirmed 要有可定位来源、明确价格阶段与至少一个价格数值。脚本只能校验字段，不能证明模型写的确认是真实的。AI 回查文件可确认读取准确，最终谈判阶段需真实最终结果依据。

经验记录用 title/name、lesson、applicability、source、status；参考手册用 title/name、出版/有效日期、适用范围、source。经验内容不得混成价格记录。

## 飞书关系

项目表：project_id、名称、厂区、报告链接、原件文件标识、项目状态。

价格版本表：record_id、revision_id、previous_revision、project_id、status、price_type、level、名称、规格、单位、单价、日期、地区及 payload_json、来源。payload_json 保存完整规范记录，常用列用于筛选。唯一写入键是 record_id + revision_id。

经验/参考表：独立 kind 分类，正文与来源；不与单价统计混用。

保留一个可确定的当前版本清单，旧版本不删。采用单写入者或平台互斥；冲突时暂停该条，不能静默覆盖。相同文件哈希/相同版本重复上传不重复增加价格样本。

已知 kind/project_id/level/price_type/bidder_id/round_id/item_key 构成记录身份，修订不可更换已知身份。缺失或 unknown 信息可依据原件补齐，并填写 reason。related_record_id 可关联同项目不同阶段记录。source.file/snapshot 的相对路径基准见 local-runtime.md。

## 可选算法反馈扩展

`analysis_feedback`只允许在experience/reference中，规范见 [算法反馈](algorithm-feedback.md)。原价格阶段、版本和关联契约不变；模型分数、参照价差和情景值不作为成交价格。
