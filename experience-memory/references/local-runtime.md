# 本地运行与以后迁移

当前以 config/storage.json 为唯一存储配置，backend=local。local_db 和 source_root 均相对配置文件目录解析；source_root 默认指向 Skill 根目录，source.file/snapshot 中的 data/... 路径均相对这个根目录，不跟随当前工作目录。查询返回 source_resolution，列出实际路径和 available/missing；available 只表示文件存在，引用时还须回查具体表行。无需飞书账号或联网。Python 标准库即可执行存取；Excel 导入底稿另需 openpyxl。

首次建空库：`python scripts/history_store.py init`。已存在时保留所有记录。查询不自动初始化，缺失库报 unavailable。
保存单条：`python scripts/history_store.py put --record record.json`。
批量保存：`python scripts/import_records.py --input records.json`；底稿含 batch_id、records，修订时增加 expected_revisions（记录编号到旧版本号）。输出 data/imports 下回执，区分 saved_local、unchanged、duplicate_source、failed。部分失败修正底稿后沿用 batch_id 重跑，已保存条目不重复新增；存储故障停止，先处理故障再续跑。
查询：`python scripts/history_store.py query --request query.json --output result.json`。
修订：put 传完整新记录及 `--expected-revision 上次revision_id`，保留同一 record_id 和修改原因。跨价格阶段另建记录。
迁移导出：`python scripts/history_store.py export-all --output data/migration.json`，包含全部旧版本、前驱及当前版本指针。export 只导出当前记录，不可替代完整迁移。

回标 Skill 必须调用这份 experience-memory 安装目录下的脚本和同一 config/storage.json；不另建库。运行宿主须有持久可写目录，不能靠聊天记忆保存数据。目录只读时将整个 data 搬到用户指定持久目录并调整 local_db，不静默放临时目录。

更新 Skill 前备份整个 data 和 storage.json，安装新版本后恢复，不能用安装包覆盖已有数据库。日常修改通过 put 执行，不直接改 SQLite。迁移或备份期间停止写入，保留数据库、原件、导入快照和完整版本导出。

本地成功显示 saved_local/not_synced，不代表等待自动同步。用户明确启用飞书后，再按 feishu-runtime.md 建立字段映射、依版本顺序迁移、回读核验数量与金额、核对当前版本；核验通过才切换 backend，保留本地备份。源记录编号、来源、缺失字段与待复核状态不变。

名称检索未命中时，AI 可根据本次清单生成合理同义词多次查询并按 record_id 去重；别名只帮助召回，不改变原名或自动判断可比性。

## 当前使用顺序

1. 同一项目建立并沿用 project_id，报价轮次使用稳定 round_id。用户不知道编号时由 AI 分配并写入项目底稿，无需询问内部编号；原材料无法判定是新轮次还是旧文件时先核对。不同日期或文件名本身不证明新轮次。
2. 回标统一底稿转换命令：`python scripts/bid_to_records.py --input bid.json --project-id 项目编号 --round-id 轮次编号 --output quote-records.json`。输出仅为报价草稿。用户要求保存时，AI 为该底稿附加稳定 batch_id 再批量导入。
3. 最终谈判结果由 AI 回查真实最终依据形成同规范 records，price_type=final_negotiated、关联原 project_id/供应商/item_key，使用新的 record_id，并可用 related_record_id 指向原报价；不把 quote 原记录改成最终阶段。仅总价确定时只存 level=total。
4. 同一记录价格更正沿用 record_id、携带 expected_revision 和 reason。已知项目/轮次/阶段/清单身份不能被修订改掉；unknown 价格阶段可根据真实证据补全。身份录入错误可先停用旧记录，再保存正确身份并说明关联。
5. 两个 Skill 新会话必须使用同一份配置；查询时传 exclude_project 排除本项目。调试价格和模拟最终结果只放隔离测试库。

## 存储核对与可比性

已整理资料保留 source.sha256（原工作簿或 PDF 内容哈希）和 sheet+row/cell 或页定位，重复解析不能因换一个 record_id 就增加样本；同来源内容冲突须沿用已有记录复核修订。没有来源哈希的材料仍能入库，但跨编号去重需 AI 核对，不能声称自动全量去重。

查询只提供候选。待复核、原件找不到、甲供乙装/乙供乙装混淆、税运条件缺失时，不直接参与价格正常性结论。
