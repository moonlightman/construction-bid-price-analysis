# 工程回标分析与经验库 Skill

当前版本：**price-bid-analysis v6.1 / experience-memory v2.1**（2026-10-11）。

针对总价相近却存在清单内部高低价组合的情况，增加总价偏离、核心子目结构、结构联动和异常行为检测，并提供可选PCA、K-means、LOF、KDE诊断及贝叶斯阈值校准。AI选择方法、核查可比性和解释发现；程序计算；复核反馈经用户授权才进入经验库。

## 使用入口

- [price-bid-analysis v6.1 安装包](price-bid-analysis-v6.1.zip)
- [experience-memory v2.1 安装包](experience-memory-v2.1.zip)
- [配套助手提示词](assistant-prompt.txt)
- [更新日志与验证边界](CHANGELOG.md)
- [回标 Skill](price-bid-analysis/SKILL.md) / [经验 Skill](experience-memory/SKILL.md)

每个ZIP根目录均为SKILL.md，排除开发测试、真实数据与缓存。两个Skill由用户授权统一维护在此私有仓库；基于用户提供的两份ZIP更新，保留原包的固定飞书Base及三张表配置。配置不包含凭据，不等于飞书读写已验证；仓库内容不得在未处理专用配置前公开发布。

固定Word七节、Excel六张基础表及原文件名保持不变。实际运行按需要增加结构与算法页，重要发现回填结论、异常及澄清表。简单计算保留Excel公式，复杂模型输出明确标注并记录复算信息。

v6.1新增施工内容八维对照、双侧原文证据、可比性与排名准入约束，并要求输出施工内容对照页。53项回归测试通过；脚本验证AI形成的证据底稿，不代替语义复核。

## 新增方法与工具

| 入口 | 用途 |
|---|---|
| [四维体系](price-bid-analysis/references/structural-risk-system.md) | 总价、核心子目、关联与情景分析 |
| [算法协议](price-bid-analysis/references/algorithm-protocol.md) | 样本/特征、PCA/K-means/LOF/KDE与独立验证 |
| [数据契约](price-bid-analysis/references/algorithm-schema.md) | 新增工具输入、结果与Excel映射 |
| [经验反馈](experience-memory/references/algorithm-feedback.md) | 发现、复核、方法版本与真实价格分离 |

在price-bid-analysis目录运行：

```sh
python scripts/analyze_bids.py normalized-bids.json --output analysis.json
python scripts/analyze_structure.py normalized-bids.json --output structure.json
python scripts/structure_algorithms.py features.json --output diagnostics.json
python scripts/calibrate_threshold.py calibration.json --output calibration-result.json
```

前两项仅用标准库。后两项可在选定环境安装requirements-algorithms.txt，Skill运行不暗中安装或联网。贝叶斯工具只优化经审计的冻结分数阈值，不宣称自动训练完整评标系统。

## 验证

```sh
python -m unittest discover -s price-bid-analysis/tests -v
python -m unittest discover -s experience-memory/tests -v
```

算法测试需要上述可选依赖。共44项回归，全部使用虚构开发数据，不能作为真实报价或业务成效。实际文件提取、宿主Word/Excel渲染、飞书读写及真实项目模型效果不在本次验收范围。本仓库不保存用户投标原件或真实库数据。

旧版ZIP保留以便回溯，不覆盖。新增包文件哈希见 [发布清单](release-manifest.json)。
