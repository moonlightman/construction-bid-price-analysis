# v6.1 施工内容对照（2026-10-11）

- 新增施工内容八维对照流程、双侧证据字段及实际成果页要求。
- analyze_bids和结构分析接入施工内容准入：差异/待核实不得直接进入价格基准和原价排名；算术复核独立。
- 旧底稿兼容但标not_run；新流程必须启用scope_review_required。
- 工作伙伴提示词同步增加施工内容比较要求。
- 53项回归通过，其中新增13项；程序校验证据底稿，不代替AI语义识别或原件提取。

# 更新日志

## 2026-10-08 — price-bid-analysis v6.0 / experience-memory v2.1

### 基线与兼容

- 基于用户上传的price-bid-analysis.zip、experience-memory.zip，与仓库v5.9-local比较后更新；将上传包的固定飞书入口配置纳入版本管理，两个Skill共用原Base及原三表，不迁库、不读写真实业务数据。
- 用户明确授权两个Skill在moonlightman/construction-bid-price-analysis私有仓库统一维护。
- 原price-bid-analysis/v5底稿及experience-memory/v2价格身份/版本接口保持；四维和算法使用独立v1扩展，旧输入仍可运行。
- 固定Word七节、Excel六基础表、文件名、只读查询和授权后入库边界保留。旧ZIP不覆盖。

### 回标逻辑

- 每次评估总价偏离、核心子目结构、结构联动和异常行为四个维度，记录方法适用性与缺失条件，不机械执行所有算法。
- 增加同行单价指数、总体CV、留一参照敏感性、统一量价差、共同可比子集覆盖、正负/净/绝对价差与工程量情景。
- 明确关联业务依据、参照种类、替代解释、同一发现去重与金额不跨投标人累加。
- 核心发现回填基础结论和澄清建议；模型结果与单元格公式区分，输入改变后需重算模型。

### 算法实现

- 新增analyze_structure.py：沿用原分析器准入，对账、单价指数、结构价差、关联及情景只读计算。
- 新增structure_algorithms.py：显式复核特征矩阵、RobustScaler、PCA载荷/残差、K-means多k与种子敏感性、LOF邻居数敏感性、逐特征留一KDE带宽敏感性。输出来源、哈希、样本/项目数、版本及参数；不自动认定风险。
- 新增calibrate_threshold.py：对冻结项目外分数进行贝叶斯阈值校准，检查项目/时间隔离、人工标签与最终留出集，按项目等权衡量漏报/误报/复核负担，输出候选参数和基线对照，不自动部署。
- 当前批内探索与独立项目验证明确分开；公开文章是方法参考，不是本Skill效果证明。

### 经验与提示词

- 新增algorithm-feedback.md和可选analysis_feedback校验，阻止算法分数伪装价格、未复核发现写为confirmed、无证据声称validated。
- 复核反馈追加版本保留项目、来源、方法与finding_id；保存与查询均不自动训练模型。
- 新增assistant-prompt.txt，可直接替换原助手提示词；强调配置/上下文不等于实际读写验证。

### 验证与限制

- 回标23项既有回归及17项结构/算法回归通过，共40项。
- 经验反馈4项回归通过，含版本追加及本地回读。
- 两个Skill入口通过quick_validate（Windows使用Python UTF-8模式）；安装包校验根目录SKILL.md、内部引用、配置一致、无测试/缓存/真实数据库。
- 算法测试环境：Python 3.11.15、NumPy 2.4.6、SciPy 1.17.1、scikit-learn 1.9.1、scikit-optimize 0.10.2。版本用于重现，不代表未来升级无需回归。
- 所有测试仅为虚构数据的开发验证；没有把模拟结果写为实际准确率、节省金额或应用项目成效。
- 本次未执行真实PDF/OCR提取、Word/Excel业务报告视觉验收、飞书权限/读写/新会话检索验证，也未进行真实项目上的算法验收。没有安装到宿主或自动更换用户现用Skill。

### 参考

- [海安清单结构研究](https://www.cecbid.org.cn/periodicals/details/C12C056B066244FBBDD8B4722A6182F8)
- [算法一手文档与适用边界](price-bid-analysis/references/algorithm-protocol.md)

来源ZIP哈希与发布包哈希见release-manifest.json。本仓库不包含真实价格库或报价原件。
