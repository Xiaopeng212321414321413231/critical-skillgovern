# Laya 非自回归路由（System-1 Routing）

> **把路由从"AR 模型读全部描述自己挑"换成"非自回归判决器一次前向出概率"**，
> 并用调用结果反向改进每个技能的路由定义。
> 实测环境：AMD Ryzen AI 7 H 350 / 31GB LPDDR5X UMA / 纯 CPU / Windows 11。
> 全部数字均为 2026-10-10 同机实测，脚本与原始日志在本仓库 `scripts/` 与 `data/`。

---

## 1. 解决什么

`docs/routing-optimization.md` 的前提是：**描述不给够决策信号，模型就会选错**。
但在技能库 > 10 个之后，还有第二个成本被忽略：

| 路由方式 | 每次路由的成本 | 是"判决"还是"生成" |
|---|---|---|
| AR 大模型读全部描述（现状） | 全部描述进上下文 + 一次生成 | 生成（自回归，逐 token） |
| **laya 411M 非自回归判决器（本方案）** | **一次前向，与描述总长无关** | 判决（并行出全部候选概率） |

laya 一次前向**同时**回答所有候选项的概率，实测 10 个候选约 **0.9 s**（本机 CPU、8 线程），
且**随候选数增加几乎不变**（预算是共享的）。这让"每来一条请求都问一次路由器"变成可接受的开销。

---

## 2. 三层结构：非自回归判决 → 自回归执行

```
                ┌─────────────────────────────────────────────┐
   用户请求 ───▶ │ L0  laya（非自回归 · 421M · 纯 CPU）          │
                │     一次前向 → 每个技能一个概率 + 置信度       │
                └───────────────┬─────────────────────────────┘
                                │ conf ≥ τ            │ conf < τ
                                ▼                     ▼
                ┌───────────────────────┐  ┌──────────────────────┐
                │ L1 本地 AR 模型        │  │ L2 云端 AR agent      │
                │ （Gemma-26B-A4B, 18t/s）│  │ （接管 / 复核 / 审计） │
                │ 执行被选中的技能        │  │                      │
                └───────────┬───────────┘  └──────────┬───────────┘
                            │       执行结果 / 用户纠正   │
                            └──────────┬────────────────┘
                                       ▼
                        ┌──────────────────────────────┐
                        │ 定义回灌（refine）            │
                        │ 反推 route_text 与负样本补丁   │
                        └──────────────────────────────┘
```

**关键分工**：laya **不生成任何文字**，它只回答"这批候选项里哪个最合"。
真正的生成式产出交给自回归层 ✅ 这就是本方案叫"建立自回归系统"的位置。

---

## 3. ⚠️ 三条硬约束（来自 laya 实现内部，调参绕不开）

### 3.1 选项 token 预算是**共享**的，且技能越多越小

laya 的 `build_sequence()` 把所有选项塞进 `head_max_len` 的**共享**预算里，
每个选项开头还要占一个 `[MASK]`；放不下时按 `per = max(4, (H-16)//N)` 硬切。
`H` 由检查点决定：**english=192、multilingual=256**（读 `rl_agent_config.json` 得到，别硬编码）。
**实测：**

| 技能库规模 | english(192) 每项 token | multilingual(256) 每项 token |
|---|---|---|
| 4 | 48 | 64 |
| 10 | 19 | 25 |
| **66（本机真实技能库）** | **2** ☠️ | **3** ☠️ |

⇒ **66 个技能无法 flat 路由**：english 每项剩 2 token、multilingual 也只剩 3 token，等于把描述全砍掉。
⇒ 两条可行路径：**分级路由**（大类 ≤7 → 子类 ≤10 → 技能）或 **shortlist 粗筛后再精判**（本仓已实现，见 §4.5）。

### 3.2 选项 ≥ 11 时 confidence 不可信

english 档官方为此档位标定的温度是 `choice:11+ = 0.1006`（< 1 表示**锐化** logits 约 10 倍），
SDK 以 `TEMP_MIN=0.5` 强制抬回，并抛 `RuntimeWarning`（本机实测每次加载都出现）。
⇒ **english 档把候选数控制在 ≤10**。
✅ **multilingual 档没有 `temperature_by_options` 这个键，故不受此约束**——这让 multilingual
成为大库路由更安全的选择（但 §3.1 的预算墙依然存在，仍需 shortlist）。

### 3.3 语言：english 检查点读不了中文描述

官方数据：MASSIVE 意图 non-en 仅 0.306，接近随机（0.05~0.25 视选项数），
但**报告高置信度**（印地语 ECE 0.855）。本机 65 个技能库里 **40 个（61%）的
route_text 是中文** ⇒ 直接用 english 档扁平路由这批技能，结果不可用。
⇒ 中文技能库必须换 **`laya-multilingual`（mmBERT-base, `head_max_len=256`, 100+ 语言）**，
或为每个技能维护**双语 `route_text`**（见 §5；"双语"是 2026-10-10 大库实测出来的关键，见 §4.5）。
✅ 本机已于 2026-10-10 补齐 `laya-multilingual` 权重（`models/multilingual/multilingual/`：
`model.safetensors` 614MB + `tokenizer.json` 32.8MB），中文路由已可用。

---

## 4. 实测结果（真实技能库，非构造数据）

语料：`.workbuddy/plugins/cache` 下的内置/插件技能 + 用户级技能 + Trae 技能，
按 canonical `name`（frontmatter）去重后 **66 个**（含本仓自带的 `skill-govern`）。

### 4.1 结论一：**不要直接拿 description 当前几个词喂 laya**

第一版 `compress_route_text` 直接取 description 的首句/前 9 词，结果：

| 指标 | 数值 |
|---|---|
| top-1 | **33.3%**（4 选 1，随机基线 25%） |
| 喂进去的 route_text | `'This skill provides guidance for creating effective skills. ##'` ← 带 markdown 残留 |

**根因**：实测 65 个技能里 **0 个**有四层描述（`【触发场景】`…），
description 是"功能说明"而不是"触发条件"。**必须先从 `Use when…` / `当…时` / `用于…`
从句里挖判别性短语**，再压缩。修好后同样 10 个候选：

| 版本 | top-1 | top-3 | 正确项置信度区间 |
|---|---|---|---|
| 直接取首句 | 33.3% | 33.3% | 0.03 ~ 0.18 |
| **从句提取 + 压缩（≤9 词）** | **83.3%** | **100.0%** | **0.35 ~ 0.94** |

### 4.2 结论二：中英对照（同一批技能、同一批语义、只换查询语言）

10 个技能候选，每选项预算 19 token，12 条用例：

| 查询语言 | top-1 | top-3 | 正确项置信度 |
|---|---|---|---|
| 英文 | **83.3%** | 100% | 0.35 ~ 0.94 |
| 中文 | **66.7%** | 91.7% | 0.22 ~ 0.99（分布变宽、不可靠） |

⚠️ 注意这条实验的**不对称性**：候选文本是英文，只有查询是中文。
即便如此，中文查询的置信度已经明显失稳 ⇒ 中文场景**不能**只靠调阈值兜底。

### 4.3 结论三：英文 `route_text` 覆盖只提升置信度，不提升准确率

把 4 个中文 `route_text` 手工译成英文（`data/route_text_overrides.json`）后重测：

| 版本 | EN top-1 | EN 正确项置信度 | ZH top-1 |
|---|---|---|---|
| A：中文 route_text 原样 | 83.3% | 0.70 ~ 0.94 | 66.7% |
| B：**英文覆盖** | 83.3% | **0.77 ~ 0.98** | 66.7% |

**读法**：准确率没动，但置信度整体抬升 ⇒ 阈值 τ 更容易挡住误判（B 版在 τ=0.40 时
覆盖率 83%、这部分 top-1 为 90%）。**A/B 只改变置信度分布，不改变排序**——这是本轮最反直觉的发现。

### 4.4 顽固误路由都在"同一家族内"

两版都错的 2 条，都是 `tencent-docs-*` 家族互相抢：

| 请求 | 期望 | 实际 |
|---|---|---|
| analyse my existing xlsx and add a pivot chart | `tencent-docs-sheetagent` | `tencent-docs-sheet-generation` |
| write a formal 20 page report in Word format | `tencent-docx` | `tencent-docs-sheet-generation` |

⇒ 421M 非自回归模型对"生成表格 vs 生成文档"这类**同族近邻语义**有分辨上限，
**加长描述解决不了**，只能靠回灌判别性负样本（§5）。
这也正好证明本框架原有的"负样本指向替代技能"原则依然成立——只是现在它有了**量化闭环**。

### 4.5 大库真实路由（66 技能）：flat 25% → shortlist 66.7%，**双语 route_text 是胜负手**

这是本方案第一次在**完整 66 技能库**上端到端跑通「判决 + 回灌」，用 multilingual 档、12 条中文用例：

| 方案 | 候选数 | 每项预算 | top-1 | top-3 | 粗筛召回 |
|---|---|---|---|---|---|
| flat 全量 | 66 | 3 token | **25.0%** | 66.7% | — |
| shortlist K=10（首版，route_text 多为英文） | 10 | 25 token | 41.7% | 41.7% | **41.7%** ❌ |
| **shortlist K=10（补双语 route_text 后）** | 10 | 25 token | **66.7%** | **83.3%** | **100.0%** ✅ |

**最关键的一条：粗筛是整条链路的真上限。** 首版短名单只召回 41.7%，根因是
**英文 route_text 与中文查询零重叠**——`agent-browser` / `find-skills` / `cloud-service` /
`buddy-image-processing` / `opencli-setup` 这几个都是英文描述，中文查询一条都捞不到，
laya 再准也无济于事。修法**不是调参，而是回灌双语 route_text**：
给这些技能补上中文关键词（浏览器/打开网页/截图 · 技能市场/安装 · 数据库/用户登录 · 水印/修图 …）后，
**召回 41.7% → 100%，top-1 41.7% → 66.7%**。

更关键的是——**这次改进完全走了框架自己的闭环**（§5）：
`eval → 误路由 → 补双语 overrides → 重扫 → 复测`，没有手改任何技能本体。
置信度阈值扫描（K=10 双语版）：`τ≈0.30` 覆盖 **75%** 流量、这部分 top-1 **88.9%**，其余 25% 升级给 AR 层。

**残留 4 条误路由**（下一轮迭代目标）：`find-skills→marketplace-skill-installer`（同族近邻）、
`tencent-docs-sheetagent→pdf`、`cloud-service→agent-browser`、`buddy-image-processing→local-image-ocr`
——全部是"同族/近邻"混淆，与 §4.4 的结论一致。

**代价与局限**：词法粗筛对跨语言无效（本机用双语 route_text 绕过，可维护但费手工）；
技能库继续膨胀后，正解是**用 mmBERT 编码器做向量召回**（跨语言、免维护双语文本）——见 §4.6（已实测）。

---

### 4.6 mmBERT 向量召回实测：**未做句向量微调的编码器不能直接用**

把 §4.5 留下的"下一步"做掉了：直接复用 laya 检查点里的 **mmBERT-base 编码器**
（`model.safetensors` 的 `encoder.*` 共 134 个张量 → `ModernBertModel`，0 缺失/0 多余；tokenizer 用同目录的 `tokenizer/tokenizer.json`）做句向量召回。

**坑一：原始 mean-pool 不可用。** off-diagonal 余弦相似度均值 **0.713**、最高 **0.961** —— 严重**各向异性**：
中文查询对**任意**英文描述都有约 0.7 的"地板相似度"，recall@10 只有 **34%**（还不如词法）。
根因：它是被 laya 的 masked-choice 头微调过的 masked-LM，**表征不是句向量**。

**坑二：All-but-the-top（ABTT）是解药。** 减均值 + 去掉前 k 个主成分后余弦：

| 后处理 | recall@5 | recall@10 | recall@15 |
|---|---|---|---|
| raw mean-pool | 34% | 34% | 43% |
| mean + ABTT(k=2) | 57% | 69% | 80% |
| **mean + ABTT(k=5)**（默认） | 69% | **80%** | 83% |
| mean + whitening | 60% | 71% | 74% |

**但端到端仍然输给词法**（68 技能库，35 用例，全程遵从 laya 判断）：

| 召回方法 | 实际候选 | top-1 | top-3 | 召回@10 | laya 读入 | 延迟中位 |
|---|---|---|---|---|---|---|
| flat 全量 | 68 | 25.7% | 45.7% | 100% | ~266 tok | 474 ms |
| **词法 shortlist K=10** | 10 | **62.9%** | **91.4%** | **100%** | ~239 tok | 407 ms |
| mmBERT 向量 K=10 | 10 | 42.9% | 71.4% | 80% | ~179 tok | 434 ms |
| 混合（词法∪向量）K=6 | 10.2 | 62.9% | 85.7% | 100% | ~210 tok | 429 ms |

**为什么向量输？** 因为 §4.5 已把双语 overrides 铺满——**override 是"为词面匹配量身定制"的**，
词法因此吃满 100% 召回；向量的 80% 受限于编码器本身不是句向量（ABTT 只是补救，替代不了微调）。

**向量真正该赢的场景是"没有双语覆盖"时。** 在**去掉 overrides 的 70 技能单语原始库**上：

| 路由表 | 词法@10 | 向量@10 | 并集@10 | 词法@15 | 向量@15 | 并集@15 |
|---|---|---|---|---|---|---|
| 无覆盖（70 技能，43 条中文 route_text） | 71% | **74%** | **86%** | 74% | **83%** | 89% |
| 有双语覆盖（68 技能） | **100%** | 83% | **100%** | 100% | 89% | 100% |

**结论：两路互补**——并集在所有表上都是最高（86%~100%）。
落地策略：**生产默认走词法**（已到顶、零依赖），把**向量作为"双语覆盖还没铺到的新技能"的兜底**，
或对召回敏感的场合直接上**并行并集**（代价是候选变多、每项预算被摊薄，见 §3.1）。

> 运行依赖：`vecshortlist` / `hybrid` 需要 **laya-test 的 venv**（torch + transformers + tokenizers + safetensors）。
> 技能向量按 `route_text` 内容哈希缓存在 `data/emb_cache/`，命中后秒级。

### 4.7 给编码器做**检索式对比学习微调**：向量召回反超词法，端到端 82.9% → 100%

§4.6 的结论是「ABTT 只是补救，替代不了微调」。那就真去微调。

**做法**（`scripts/finetune_mmbert.py`）：
- 监督对比学习，**全库当负样本**：每个 query 与全部 68 篇技能 `route_text` 算余弦，
  `sim = normalize(q) @ normalize(docs).T / τ`（τ=0.05），softmax 后取正确文档的 NLL。
- 训练对由 `scripts/make_ft_pairs.py` 从 `route_text` 关键词 + 中英模板生成，**355 对**；
  与 35 条审计用例做了泄漏检查（**0 重叠**）。
- CPU 可行：**冻结 layers.0..15**，只训 layers.16..21 + final_norm（37 个张量）。
  lr=1e-4、batch=32、6 epoch，约 12 分钟（8 线程），产出 120 MB 权重。

**留出 35 条用例的召回**（`scripts/eval_ft_recall.py`）：

| 编码器 | raw@1 | raw@3 | raw@10 | ABTT5@1 | ABTT5@10 |
|---|---|---|---|---|---|
| 原始 mmBERT | 11% | 26% | 34% | 49% | 86% |
| 微调（conservative, lr=2e-5×3ep） | 29% | 43% | 66% | 40% | 83% |
| **微调 v2（lr=1e-4×6ep）** | **63%** | **80%** | **100%** | **77%** | **94%** |

**两个反直觉的点**：
1. **微调后 raw 反超 ABTT**（v2 raw@10=100% > ABTT@10=94%）。对比学习本身就在"去各向异性"，
   ABTT 变成冗余操作、还会削掉有用方向。→ **FT 权重下应把 `abtt_k` 设为 0（原始余弦）**。
2. 但 **top-1 场景 ABTT 仍更准**（v2 ABTT@1=77% > raw@1=63%）：去主成分压制了"近似技能"的误命中。

**端到端路由审计**（68 技能，35 用例，全程遵从 laya 判断，`scripts/laya_route_audit.py --method vecshortlist --vec-abtt 0 --ft ...`）：

| 召回方法 | 候选 | top-1 | top-3 | 召回 | laya 读入 |
|---|---|---|---|---|---|
| 词法 shortlist K=6（此前最佳） | 6.0 | 62.9% | 85.7% | 100% | ~210 tok |
| **向量FT raw K=6** | 6.0 | **85.7%** | 94.3% | 97.1% | **~134 tok** |
| 向量FT raw K=8 | 8.0 | 80.0% | **97.1%** | **100%** | ~172 tok |
| 向量FT raw K=10 | 10.0 | 77.1% | 97.1% | 100% | ~215 tok |
| 混合（词法∪向量FT）K=5 | 8.2 | 77.1% | 94.3% | 100% | ~190 tok |

**微调把 top-1 从 62.9% 拉到 85.7%，token 反而更省**（134 < 210）——最好的召回器同时是最便宜的。

**协同 vs 单独**（`scripts/cascade_eval.py`：conf ≥ τ 信 laya，conf < τ 由 L2 接管）：

| 前端 | 方案 | top-1 | 升级流量 |
|---|---|---|---|
| 词法 K=10 | laya 单独 | 62.9% | — |
| 词法 K=10 | 协同（L2=FT 检索器，τ=0.40） | **88.6%** | 34% |
| 向量FT raw K=8 | laya 单独 | 82.9% | — |
| 向量FT raw K=8 | 协同 τ=0.30 | 97.1% | 17% |
| 向量FT raw K=8 | **协同 τ=0.40** | **100.0%**（35/35） | 20% |
| 向量FT raw K=8 | 协同 τ=0.50 | 97.1% | 29% |

**结论**：
- 微调是这一层的**真正胜负手**，比换召回算法（词法 vs ABTT 向量）重要得多。
- laya 的 `confidence` 是**可用的升级信号**：τ=0.40 时，只放走 20% 流量就补到 100%。
- K=6 vs K=8 是**精度/召回权衡**：K=6 solo 更高（85.7%）但余量小；K=8 solo 略低（82.9%）却能靠协同补满。
- **诚实边界**：训练对与审计用例**同源**（都由 `route_text` 关键词派生），且审计集只有 35 条，
  100% 是**乐观上界**；换成完全独立分布的真实用户话术，一定会掉。落地要留出独立的 blind set 复测。

> 产物：`data/finetuned/mmbert-retrieval-v2.pt`（推荐）、`data/ft-recall.md`、
> 审计报告 `data/route-audit-vecft{6,8,10}raw.md`、级联报告 `data/route-audit-cascade-ft-t0.*.md`。

### 4.8 泛化检验：**"100%"里约一半是同源红利**（必读）

§4.7 的 100% 有一个硬伤：训练对与审计用例**同源**（都由 `route_text` 派生）。另造两个**不参与训练**的
查询集重测，并保留原始编码器 / 未微调向量 / 词法做对照（详见 `data/laya-ft-overfit-report.md`）：

| 测试集 | 条数 | 构造 |
|---|---|---|
| 同源 `cases_audit` | 35 | 与训练对同源 |
| 自然话术 `cases_holdout_natural` | 28 | 换句式，**保留领域名词**（PDF/Excel/股价…） |
| 改话术（硬）`cases_holdout` | 56 | **刻意规避 route_text 原词**：口语化、间接、只给场景 |

**编码器级召回（不经过 laya）**：

| 测试集 | 原始 raw@10 | 微调 v2 raw@10 | 原始 ABTT@10 | 微调 v2 ABTT@10 |
|---|---|---|---|---|
| 同源 35 | 34% | **100%** | 83% | 94% |
| 自然话术 28 | 32% | **93%** | 79% | **96%** |
| 改话术（硬）56 | 30% | **64%** | 61% | 66% |

**端到端路由 top-1 / 粗筛召回**：

| 测试集 | 词法 K=10 | 未微调向量 K=10 | 向量 FT K=8 | 词法召回 | FT 召回 |
|---|---|---|---|---|---|
| 同源 35 | 62.9% | 42.9% | **80.0%** | 100% | 100% |
| 自然话术 28 | 57.1% | 46.4% | **67.9%** | 89.3% | 89.3% |
| 改话术（硬）56 | 28.6% | **32.1%** | 30.4% | **53.6%** | **66.1%** |

**结论**：

1. **过拟合存在，但只吞掉约一半**：微调 v2 的 raw@10 从同源 100% 掉到 93%（自然）、64%（硬）。
   不过在最硬的集上仍从 30%→64%（+34pt）——微调学到了**可迁移**的语义检索，不是纯记忆。
2. **词法前端对"用词"极度脆弱**：召回 100%→89.3%→**53.6%**。同源集上"词法=FT"是
   `route_text` 双语覆盖为词面匹配量身定制的假象。
3. **FT 只是"不那么靠词面"，没解决"抽象意图"**：自然档 FT 明确最优（+10.8pt）；
   硬集上与词法打平（30.4% vs 28.6%）。
4. **协同在低召回档救不动**：硬集上 30.4%→33.9%（同源集是 82.9%→100%）。
   因为 **L2 用同一个检索器**——召回错了，L2 换谁选都没用。
5. **落地预期**：真实流量接近"自然话术"档 → **top-1 约 55%~70%**。
   想再抬：① 给技能补**多样化 `route_text`**（规范句 + 口语句 + 英文关键词，零训练成本，直接抬共同上限）；
   ② 训练数据加**同义改写 + 硬负样本**（当前 355 对词面太窄）。
6. **评测纪律**：任何"提升"必须在**独立分布**集合上复现；同源集只用于回归。

---

## 5. 定义回灌：让技能定义像权重一样被"梯度下降"

`route_text` 与 SKILL.md 的长描述是**两种东西**，不要混：

| 面向 | 载体 | 语言 | 长度 |
|---|---|---|---|
| 人 / AR 模型 | `SKILL.md` 的 description（四层） | 中文优先 | 长，可读 |
| **laya 判决器** | `data/route_text_overrides.json` 的 `route_text` | 英文（或 multilingual 档下的中文） | **≤ 9 词** |

闭环：

```
route / eval  ──▶ data/routing_log.jsonl（每次判决的分布 + 结果）
                          │
       feedback --query X --expected Y --got Z   ← 人工/AR 层纠正
                          ▼
                    refine（挖判别性词）
                          ▼
              data/routing_patches.md（补丁提案）
                          │
                   ⭐ 用户审批（方法论第 3 阶段）⭐
                          ▼
        改 route_text_overrides.json ──▶ 重跑 eval 复测 top-1
```

`refine` 的判别力判据（这是踩坑换来的）：**候选词必须不出现在其他任何技能的 route_text 里**，
否则它无法把两个技能区分开。不加这道过滤，会挖出 `two` / `into` / `can` / `add` 这类零信息词。

**实测产物**：

- `--min-support 2`（首轮，24 条日志 → 14 条误路由 → **5 组**，见下表）
- `--min-support 1`（2026-10-10 大库轮，日志累积后 → **27 组**，落 `data/routing_patches.md`）

| 误选 | 应选 | 证据 | 挖出的判别性词 |
|---|---|---|---|
| tencent-docs-sheet-generation | tencent-docs-sheetagent | 2 | pivot, chart |
| tencent-docs-sheet-generation | tencent-docx | 2 | formal, format, 报告文档 |
| cloud-service | agent-browser | 2 | website, screenshot, fill, form |
| skill-creator | find-skills | 2 | search, marketplace, install |
| tencent-docx | pdf | 2 | merge, remove, password |

---

## 6. 与 `validate-routing.py` 的分工

| | validate-routing.py | laya_router.py |
|---|---|---|
| 管什么 | **形**：四层描述、tags、模板残余、负样本长度 | **效**：真实请求下能不能选对（top-1） |
| 是否需要模型 | 否（纯静态） | 是（需要 laya 检查点） |
| 输出 | 合规/不合规 | 准确率 + 置信度阈值 + 回灌补丁 |
| 何时跑 | 改技能后 | 建库后定基线；改 route_text 后复测 |

**两者都不能替代对方**：描述全合规也可能全选错（本轮实测 65/65 合规性未知但 top-1 只有 33%）。

---

## 7. 用法

```bash
# 必须用装了 laya 的解释器（本机：$USERPROFILE\laya-test\.venv\Scripts\python.exe）
PY="$USERPROFILE/laya-test/.venv/Scripts/python.exe"

# 1) 扫描技能目录 → 路由表（含预算体检、语言体检；--model-dir 决定预算按 192 还是 256 算）
$PY scripts/laya_router.py scan --skills ~/.workbuddy/skills ~/.trae-cn/skills \
    --model-dir "$USERPROFILE\laya-test\models\multilingual\multilingual"

# 2) 路由一条请求（大库用 shortlist，小库用 flat/tree）
$PY scripts/laya_router.py route --query "把两个PDF合并" --method shortlist --k 10 \
    --model-dir "$USERPROFILE\laya-test\models\multilingual\multilingual"

# 3) 在标注用例上测准确率 + 置信度阈值扫描（大库务必 --method shortlist）
$PY scripts/laya_router.py eval --cases data/cases_zh.jsonl --method shortlist --k 10 --sweep \
    --model-dir "$USERPROFILE\laya-test\models\multilingual\multilingual"

# 3b) 换召回方法：vecshortlist（mmBERT 向量 + ABTT）/ hybrid（词法∪向量）—— 见 §4.6
$PY scripts/laya_router.py eval --cases data/cases_zh.jsonl --method vecshortlist --k 10 \
    --model-dir "$USERPROFILE\laya-test\models\multilingual\multilingual"

# 3c) 遵从 laya 判断的「路由审计」（额外算 token 账单 + 升级阈值），--out 落 markdown 报告
$PY scripts/laya_route_audit.py --cases data/cases_audit.jsonl --method hybrid --k 6 \
    --model-dir "$USERPROFILE\laya-test\models\multilingual\multilingual" --out data/route-audit-hybrid.md

# 3d) 微调检索编码器（§4.7）→ 评测 → 带 FT 权重的路由审计
$PY scripts/make_ft_pairs.py                       # 由 route_text 生成训练对（含与审计集的泄漏检查）
$PY scripts/finetune_mmbert.py --epochs 6 --batch 32 --lr 1e-4 --threads 8 \
    --out data/finetuned/mmbert-retrieval-v2.pt    # CPU 约 12 min
$PY scripts/eval_ft_recall.py                      # 原始 vs 微调的 recall@k 对比表
$PY scripts/laya_route_audit.py --cases data/cases_audit.jsonl --method vecshortlist --k 8 \
    --vec-abtt 0 --ft data/finetuned/mmbert-retrieval-v2.pt --out data/route-audit-vecft8raw.md
# 注：FT 权重下用 --vec-abtt 0（raw 余弦）；原始 mmBERT 才用默认 5

# 3e) 协同 vs 单独：先 dump（前端可换 --method/--ft），再 report（L2 可换 --l2 retriever/picks）
$PY scripts/cascade_eval.py --dump-only --method vecshortlist --k 8 --vec-abtt 0 --ft ... \
    --dump data/cascade_dump_ft.json
$PY scripts/cascade_eval.py --report-only --dump data/cascade_dump_ft.json \
    --l2 retriever --ft data/finetuned/mmbert-retrieval-v2.pt --threshold 0.40 \
    --out data/route-audit-cascade-ft-t0.40.md

# 4) 记录一次纠正（expected=应该选谁，got=实际选了谁）
$PY scripts/laya_router.py feedback --query "..." --expected pdf --got tencent-docx

# 5) 生成回灌补丁（只提案，不落盘；按方法论第 3 阶段由用户审批）
$PY scripts/laya_router.py refine --min-support 2
```

判定阈值 τ 的取法：跑 `eval --sweep`，选"覆盖率 × 该部分的 top-1"最划算的那一行。
本机 EN 实测建议 **τ ≈ 0.40**（覆盖 83% 流量，这部分 top-1 90%，其余 17% 升级给 AR 层）。

---

## 8. 已验证 / 未验证（三态声明）

| 状态 | 条目 |
|---|---|
| ✅ 已验证 | 10 候选 top-1 83.3% / top-3 100%（EN）；中文查询 66.7%；延迟中位 0.4~0.9 s；**66 技能 flat 仅 25%，shortlist K=10 双语版 66.7%（top-3 83.3%、召回 100%）**；预算公式（english 2 / multilingual 3 token/项）；**双语覆盖把召回 41.7%→100%**；英文覆盖只抬置信度不改排序；multilingual 已下载可用；**68 技能 shortlist K=10 审计 top-1 62.9 / top-3 91.4%（读入 ~239 tok，生成 0，省 96.4%）**；**mmBERT 向量召回：raw mean-pool 不可用（recall@10 34%、off-diag 余弦 0.71），ABTT(k=5) 后 80%；无双语覆盖时向量(74%)>词法(71%)@10，并集 86%**；**检索式对比学习微调（68 负样本、冻结 layers.0..15、355 对、0 泄漏）：留出集 random-pool recall@10 34%→100%、raw@1 11%→63%、ABTT@10 83%→94%；端到端 68 技能路由 top-1 62.9%→85.7%（向量FT raw K=6，读入 134 tok）；级联 τ=0.40 使 laya 单独 82.9%→协同 100%（35/35，升级 20%）**；**泛化检验（另造 28 条自然话术 + 56 条刻意改话术集，均不参与训练）：微调 raw@10 100%→93%→64%，路由 top-1 80.0%→67.9%→30.4%；词法召回 100%→89.3%→53.6% —— 同源红利约占一半，微调仍带来可迁移增益（硬集 raw@10 30%→64%），真实流量 top-1 预期 55%~70%** |
| ⚠️ 未验证（推测） | "中文选项文本会吸收误路由"——A/B 中两版误选都落在 sheet-generation，与其中文 route_text 相关，但**单次 A/B 不足以定因**，需重复测失败率；**同源集上的 100% 属乐观上界，已确认约一半是词面过拟合；真实分布下的泛化区间（55%~70%）本身也是在小样本（28/56 条）上估的，且两个 holdout 均由被测方人工编写 → 只可作为量级参考，正式验收需第三方独立标注的 blind set** |
| ❌ 已验证失败 | 直接取 description 首句当 route_text（top-1 33.3%）；flat 路由 66 个技能（2~3 token/项 → 25%）；english 档路由中文选项文本；**纯词法粗筛对"中文查询 vs 英文 route_text"**（召回 41.7%）；**mmBERT raw mean-pool 句向量直接检索**（recall@10 34%，各向异性严重） |
| 🚧 未实现 | `refine --apply` 自动落盘（刻意不做，防"改坏不回归"）；hybrid 的**动态候选裁剪**（当前并集把每项预算摊薄，见 §3.1） |
