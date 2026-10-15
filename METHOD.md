# 课程与模型训练方法

本项目实现 `CURRICULUM_METHOD`：给定公开学习单元，生成固定数量、固定顺序的结构化题目参数。验证者的可信程序计算答案、生成讲解和图表，并使用任务冻结的 Qwen3.5-4B、LoRA 配方、预算和训练随机种子训练模型。

## 输入与产物

入口为 `generator.py --request REQUEST_JSON --output OUTPUT_DIR`。输入使用当前计算工作进程的 `learning-unit.v5` 格式；其中 `v5` 是学习单元的输入格式版本，当前协作任务仍使用该格式。

输入包含 `unit`、`source_ids`、`output` 和公开 `public_diagnostics`。正式执行时 `generation_seed` 由任务冻结流程供应；本项目要求具体整数，拒绝尚未冻结的 `null`。同一输入、相同源码和 Python 3.11 环境生成相同顺序的 `problem_specs.jsonl`。

| 能力 | 输出结构 | 可信执行侧的训练内容 |
| --- | --- | --- |
| ratio_scaling | direct_scale | 同比例缩放与步骤解释 |
| ratio_transfer | unit_rate | 单位量、分数与情境迁移 |
| linear_modeling | linear_equation | 线性关系代入与建模 |
| 数学 clarification | missing_condition，scale=null | 指出信息不足并请求缩放条件 |
| chinese_reading | subject_practice / chinese | 信息提取、因果理解、概括 |
| english_language | subject_practice / english | 主谓一致、过去时、比较表达 |
| physics_reasoning | subject_practice / physics | 速度、功、密度 |
| chemistry_reasoning | subject_practice / chemistry | 质量守恒、质量分数、粒子计数 |
| biology_reasoning | subject_practice / biology | 放大倍数、细胞分裂、生态计数 |

五门非数学学科由可信渲染器按 FOUNDATION / TRANSFER / GROWTH 选择具体教学内容。数学题型按 `capability` 选择，避免把非数学 GROWTH 单元错误输出成线性方程。所有学科覆盖 solution、hint、correction、clarification；语言、年龄组、图像输入、先修知识与题量遵循公开任务。

## 可改进的课程策略

当前起点策略为：在合法参数空间内无放回抽样；按数量大小和复杂度安排顺序；TRANSFER / GROWTH 每两道较复杂题插入一道较简单的检索练习。不会重复同一组参数以填充题量。`curriculum.py` 是矿工主要修改的位置。

数学参数 `a,b` 使用 2–400，scale 使用 2–20，线性题 offset 使用 1–16；五门学科的 `a,b` 使用其 schema 允许的 2–80。每单元数学支持最多 100000 条，五门学科各支持最多 6241 条不重复题目；超出方法能力时直接报错。当前项目预置的每单元 1–512 条在范围内。

题目 id 在单元内唯一。课程排序是训练顺序的一部分，摘要不同或顺序调整都应提交新 commit。本项目不利用隐藏评测或伪造题族；参数变化不会自动产生新的独立题族。公开诊断字段作为输入保留，当前起点策略不据此自报改进。

## 训练模型的执行方式

验证者执行的每条路径为：冻结公共父模型 → FOUNDATION → TRANSFER → GROWTH。同一方法、同一训练种子继承自己的前一阶段检查点；阶段边界按冻结配方重置优化器。模型权重与最终成绩由现有 CapabilityForge Compute / Validator 产生。

矿工通过课程的题目选择和顺序影响训练，不在仓库中替换优化器、学习率、步数、底座模型或推理参数。无需在投稿仓库提供 `train.py`、模型权重、GPU 环境或自报分数。需要实际训练实验时，使用已有可信计算部署和对应任务政策；本模板不自动启动训练。

## 本地数据与正式审核的边界

`tools/export_training_data.py` 复用已安装公共包的 schema、求解器和渲染器，导出 messages、答案、教学步骤、来源和真实图表，便于人工阅读或后续训练实验。使用与执行节点匹配的公共包版本，才能得到一致的渲染行为。

本地导出不读取私有评测，不检查隐藏题族隔离，不执行冻结 token/像素消费核算、模型训练、独立复训或评分。导出清单明确写入 `development_only=true`、`formal_audit_performed=false`。这些开发材料不能代替正式审核证据，也不保证方法产生正贡献或获得奖励。
