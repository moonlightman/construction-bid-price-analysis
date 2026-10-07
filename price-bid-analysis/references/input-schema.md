# 统一底稿数据约定

字段键保持英文，说明中文。脚本只处理 JSON 数值，不接受带逗号的数字字符串；由提取环节保留原始文本并转换数值。未知用 `null`，不能填零。原件行和修改记录另存，不覆盖。

## 项目与投标人

`project` 保存 `project_id`、`name`、`pricing_date`、`region`、`currency`、`tax_basis`、`round_id` 和 `thresholds`。阈值键及默认值见分析方法。供经验库保存时须有稳定 project_id 和 round_id，由 AI 在项目底稿中分配并持续沿用；不要求用户提供内部编号。

原件可识别时同时保留 freight_basis（运费）、installation_basis（甲供/乙供及安装范围）、tax_rate、discount_basis、payment_terms、plant、valid_from/valid_to。项目默认条件只适用于确实共用的范围；具体报价条件放 bids，其次清单项、投标人层级。显式 null 表示未知，不用上层条件覆盖。实际来源 source 仍独立保留，不从汇总表定位猜分项来源。

`bidders` 为列表，每家包含：

| 键 | 含义 |
|---|---|
| bidder_id / name | 本次唯一标识 / 原始名称 |
| stated_total | 原件独立读取的声明总价 |
| source | 声明总价来源定位 |
| stated_total_review_status | confirmed / pending |
| coverage_confirmed | 是否确认明细及汇总覆盖完整 |
| total_comparable | 是否确认各家的总价范围、币种、税费可比 |
| total_adjustments | 未计入明细的税费、折扣、暂列等；每项 amount、source、review_status、reason |

只把明细之外且不重复计取的调整放入 `total_adjustments`。负数可用于有依据的折扣。未知调整使汇总不可完整核对。不能只因目前提取行相加等于总价，就宣布覆盖完整。

费率与暂估金额按 [计价规则](rate-pricing.md) 处理。`total_adjustments` 继续保存原件金额与状态，不能用补齐测算覆盖原件空白。可在项目底稿另外保存 `rate_pricing`（mode、fixed_amount 或 provisional_base、rate_convention、source），在各投标人另存 `comparison_adjustments`（amount、reason、rule_source、confirmation_status），用于有依据的同口径测算。`analyze_bids.py` 不解释这两个可选字段，也不会据此自动修正原价或产生正式排名；由 AI 按项目规则组织工作簿公式并复核。

## 清单项目

`items` 为列表，每项有 `item_key`、`name`、`spec`、`unit`、`scope`、`tender_quantity`、`mapping_confirmed` 和 `bids`。

`item_key` 由正式清单及范围或经复核组合生成，不按序号自动映射。不同单位工程重复编码需要加入分部/范围标识。`mapping_confirmed` 只有核对名称、规格、单位和范围后才能设为 true。保留映射方法与原件定位在底稿。

可选 `control_unit_price` 和 `control_comparable`：有可查来源且计价口径兼容时后者为 true，来源保存在 `control_source`。市场、历史或独立估值不强塞到控制价字段，另存证据表。

每个 `bids` 报价记录包含：

| 键 | 含义 |
|---|---|
| bidder_id | 关联投标人，同项目每家至多一条有效记录 |
| quoted_quantity | 原件投标工程量；缺失不自动用招标量冒充 |
| unit_price / line_total | 原件综合单价 / 原件综合合价 |
| material_unit_price / material_line_total | 材料单价 / 合价 |
| installation_unit_price / installation_line_total | 施工单价 / 合价 |
| price_basis | comprehensive（综合价）、split_additive（材料施工分别计取）、unknown（待确认） |
| additivity_confirmed | split_additive 时是否确认两部分不重叠、可以相加 |
| review_status | confirmed、pending、excluded |
| comparable | 该报价是否与当前项目其他报价可比 |
| source | 来源对象：file 加 sheet/row/cell，或 page/location；可追加 paired_source |

单位价格与金额原值保留。split_additive 且可加关系确认后，脚本在结果中派生两部分合计，不修改输入；不得以数量×单价填充缺失原始合价来制造“校验通过”。同一材料在多个表出现时先去重，重复报价不能直接求和。

费用组成、付款阶段、变更情景等按实际方法增加字段或独立底稿；统一脚本不自动生成独立估值、历史基准或不平衡认定。`confirmed` 表示 AI 原件回查/受控确认已完成，不等于用户对每个数字签字。

## 最小计算示例

```json
{
  "project": {"project_id": "P001", "round_id": "R1", "currency": "CNY"},
  "bidders": [{
    "bidder_id": "A", "name": "示例投标人", "stated_total": 1200,
    "source": {"file": "报价.xlsx", "sheet": "汇总", "cell": "B2"},
    "stated_total_review_status": "confirmed", "coverage_confirmed": true,
    "total_comparable": true
  }],
  "items": [{
    "item_key": "管道-DN80-m", "name": "合金钢管", "spec": "DN80", "unit": "m",
    "tender_quantity": 10, "mapping_confirmed": true,
    "bids": [{
      "bidder_id": "A", "quoted_quantity": 10,
      "material_unit_price": 100, "material_line_total": 1000,
      "installation_unit_price": 20, "installation_line_total": 200,
      "price_basis": "split_additive", "additivity_confirmed": true,
      "review_status": "confirmed", "comparable": true,
      "source": {"file": "报价.xlsx", "sheet": "清单", "row": 2}
    }]
  }]
}
```

## 双格式复核底稿

根字段 `pairs` 为已人工/AI 核实匹配的行或汇总组，`coverage_confirmed` 为文件登记覆盖确认，`unmatched` 保存未配对页/行及原因。数值容差 `numeric_tolerance` 默认 0；非零时必须提供 `tolerance_reason`。

每组字段：`pair_id`、`same_version_confirmed`、`fields`（待核对字段名列表），以及 `excel`、`pdf`。两侧各有 `source`、`review_status` 和 `values`（独立提取的字段值字典）。名称、规格、单位和所有适用数值都要登记；不适用字段不放进 fields，适用但未读出填 null。

```json
{
  "coverage_confirmed": false,
  "pairs": [{
    "pair_id": "A-本轮-总价", "same_version_confirmed": true,
    "fields": ["stated_total"],
    "excel": {"source": {"file": "报价.xlsx", "cell": "B2", "sheet": "汇总"}, "review_status": "confirmed", "values": {"stated_total": 1200}},
    "pdf": {"source": {"file": "报价.pdf", "page": 1}, "review_status": "confirmed", "values": {"stated_total": 1200}}
  }],
  "unmatched": [{"scope": "明细页", "reason": "尚未配对"}]
}
```

示例只能得到“已登记总价字段一致”，不能声称整份文件已核对。脚本输出中的差异不自动决定采用哪份文件。

## v6结构与算法可选扩展

新增结构关系、情景、特征矩阵及独立校准输入见 [算法扩展数据契约](algorithm-schema.md)。原字段和原始值不变；新脚本与原analyze_bids.py分开输出，兼容旧底稿。
