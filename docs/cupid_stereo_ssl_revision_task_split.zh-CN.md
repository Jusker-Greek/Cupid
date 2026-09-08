# CUPID 双目自监督汇报重构：任务分工与交接协议

## 1. 目标

本轮工作的目标不是汇报 CUPID 的工程复现过程，而是让师兄和老师能够明确回答以下问题：

1. 当前工作从哪个 CUPID baseline 出发。
2. 上一项目提供了什么双目自监督思想和证据边界。
3. 本项目具体在 CUPID 的哪一处加入了什么信号、接口或训练目标。
4. 新增双目关系如何为模型学习场景或生成分布提供先验。

当前最保守的贡献表述为：

> 我们从 CUPID 论文和官方代码 baseline 出发，把上一项目中的双目自监督思想迁移到 CUPID，明确新增双目关系信号、接口和训练归属，先建立可审计的双目 SSL 架构。当前汇报展示基线继承与架构改动，不宣称已有科学结果。

## 2. 汇报主线

主线按以下顺序组织：

1. CUPID baseline 的来源：论文 Figure 3、官方代码及对应模块名称。
2. CUPID baseline 的可编辑母图：输入、姿态与占据预测、PnP、pose-aligned conditioning、几何与外观生成、Gaussian/Mesh 输出。
3. 上一项目的双目 SSL 依据：明确观测、预测目标、共享几何关系、自监督信号和训练归属。
4. CUPID 上的 proposed integration：在同一 baseline 母图上仅标出新增局部。
5. Baseline 与 proposed integration 对照：哪些路径保持不变，哪些模块、信号、loss 或 gradient path 新增。
6. 当前设计状态、待确认项及最小验证 gate。

以下内容不进入主 PPT：

- CUPID 依赖安装和环境修复过程。
- smoke、preflight、readiness 或 Slurm job ledger。
- 尚未达到正式训练和正式评估门槛的数值。
- 任何“已复现论文结果”或“已获得性能提升”的未验证表述。

这些内容如需保留，只能放在内部工程记录或独立 backup 文件，并标记为 `DEBUG_ONLY / NO_SCIENCE`。

## 3. 三个协作任务

### Task 1：重建 CUPID 论文基线母图

- Owner：独立 Codex 任务 1。
- 任务 ID：`01a08097-df8d-7d50-9069-c56ed3532252`。
- 工作分支：`codex/cupid-baseline-mother-v02`。
- 输入：CUPID 论文 Figure 3、官方仓库代码命名、现有候选图 `outputs/figures/p02_cupid_repro_paper_pipeline_v01_candidate.drawio`。
- 输出：真正由可编辑对象组成的 CUPID baseline `.drawio` 母图、渲染预览、来源和审核记录。
- 必须保留：input、DINOv2、Occupancy & Pose Generation、UV/Occupancy cube、PnP、Pose-aligned Conditioning、Geometry & Appearance Generation、Gaussian/Mesh outputs。
- 边界：不修改 PPT，不加入未经核实的双目 SSL 模块，不运行实验、测试或 Slurm。
- 状态：`IN_PROGRESS / CANDIDATE`。原生可编辑 v02 和 PNG 预览已经生成，正在做排版修订与 gate 审计；现有旧候选图只是嵌入原始论文图的单图源，不是已审核的可编辑母图。

### Task 2：识别上一项目双目 SSL 依据

- Owner：独立 Codex 任务 2。
- 任务 ID：`01a08099-b372-7b23-8be9-a037a617a34c`。
- 输入：用户提供的 Overleaf 项目 `https://www.overleaf.com/project/6a48048c08f96f16d4c14c49`，以及上一项目本地文档。
- 上一项目路径：`/Users/ruikegu/Library/CloudStorage/OneDrive-个人/文档/Code/新建文件夹/linear/Archived/250520stereoworld/xfactor_reproduce_overfit`。
- 权威代码快照：`origin/codex/metric-scale-controller-cleanup`，本机可核验提交 `d88b19e0414aaf482b21f5630b64df604dc2c57a`。
- 输出：候选文档名和路径、核心输入输出关系、已验证事实、冲突项、待用户确认项。
- 边界：用户确认前不修改 CUPID 图或 PPT，不把工程 smoke/readiness 当科学结果，不运行或提交 Slurm。
- 状态：`AUDIT_COMPLETE / USER_CONFIRMATION_REQUIRED`。

Task 2 已发现需要用户确认的口径冲突：

- 仓库中存在直接写出 `left[t] -> right[t]` 的路线，但对应文档把它称为 naive left-to-right baseline，而不是现行 joint-stereo 目标。
- “学习分布”在另一份 4D 项目定义文档中有正式定义。
- 用户提供的 Overleaf 项目 README 声明其内容与该 4D 项目定义文档相互独立。

因此，在 Task 2 完成精确文档识别且用户确认前，不能把“左目预测右目”“joint stereo”“4D distribution learner”合并描述为同一个已经验证的方案。

### Task 3：重构 CUPID 双目 SSL 汇报故事

- Owner：独立 Codex 任务 3。
- 任务 ID：`01a0809a-2f0d-7a13-8e28-998cc2cf73ca`。
- 工作分支：`codex/cupid-stereo-ssl-slides-storyboard`。
- 输入：现有内部 PPT、Task 1 baseline 母图、Task 2 文档审计结果及用户确认。
- 输出：新的页序和 dependency manifest、同一母图派生的 baseline/integration/zoom 图、最终 PPTX、渲染预览和逐页视觉审核结果。
- 边界：不得把旧 PPT 中的工程问题页、smoke、preflight、Slurm ledger 或复现状态作为主科学故事；不得在用户确认前冻结双目模块名称或接口。
- 状态：`STORYBOARD_IN_PROGRESS / BLOCKED_BY_USER_CONFIRMATION`。页序和 dependency manifest 已开始落盘，但最终集成图必须等待 Task 1、Task 2 和用户确认。

## 4. 交接顺序

```text
Task 1: CUPID baseline mother diagram
                     \
                      -> user confirms stereo SSL contract -> Task 3 integration and deck
                     /
Task 2: prior-project document audit
```

具体门槛如下：

1. Task 1 提交 baseline candidate，并完成 `INIT_GATE`、`PRE_EDIT_GATE` 和 `POST_RENDER_GATE`。
2. Task 2 提交文档审计，精确区分 left-to-right baseline、joint stereo 和 distribution learning 三层概念。
3. 用户确认 CUPID 本轮采用的双目自监督 contract，至少确认 prediction target、监督信号进入点和对外使用的模块名称。
4. Task 3 复制 Task 1 的母图对象，在相同坐标、模块、颜色和连接语义上增量加入双目 SSL 局部。
5. Task 3 生成 PPTX，完成 render、contact sheet、逐页视觉检查和 finalizer。

任何下游任务不得绕过上游门槛自行补全缺失语义。

## 5. 图源与审核状态

- `.drawio` 是唯一可编辑 pipeline 图源。
- PNG、SVG 和 PDF 只作为导出物，不作为后续修改源。
- 图内可见文字使用英文；中文解释、结论、风险和改动说明使用 PPT 原生对象。
- 所有 pipeline 页必须继承同一 reviewed mother diagram。允许裁切和局部放大，但不允许重新画一套不同视觉语法的方框图。
- 新增模块名称在用户确认前标记为 `NEW_MODULE_NAME_APPROVAL=PENDING`。
- candidate 不得称为 approved。用户审核通过后，才能冻结 `_approved.drawio`。
- 当前 Figure 3 图片源：`outputs/figures/paper_figure3_original.png`。
- 当前图片源 SHA256：`eca27971013150c77b06921f041666bca2d4839b4665542dab09206887d21dcd`。

## 6. 建议页序

1. 封面：CUPID baseline 与双目 SSL integration。
2. 工作起点：论文 Figure 3 与官方代码 baseline。
3. CUPID baseline 可编辑 pipeline。
4. 上一项目双目 SSL 的准确问题定义。
5. 双目观测、预测目标和共享关系。
6. CUPID proposed integration：baseline 母图上的局部新增。
7. 新增信号进入的模块、latent、loss 和 gradient path。
8. Baseline 与 integration：保持不变项和新增项。
9. 当前设计状态、待确认项和最小验证 gate。
10. Backup：术语、图源 provenance 和候选 contract 对照。

页序可以在内容审计后压缩，但不能改变“来源先于改动、思想先于接口、设计先于结果”的顺序。

## 7. 当前项目迭代状态

- 本轮处于架构定义和汇报重构阶段，不处于科学结果汇报阶段。
- CUPID baseline 工程工作与本轮科研故事分开维护。
- 本轮先冻结一项科学变量：双目自监督信号如何接入 CUPID。其余数据、baseline 路径、生成器和评估协议暂时保持不变。
- 在文档 contract 未确认前，所有 integration 都是 planning-only，不构成实验已经实现或有效的证据。

## 8. 下一次同步所需信息

下一次同步至少包含：

- Task 1 的 baseline candidate 路径和渲染预览。
- Task 2 的候选文档、关键原文位置和冲突解释。
- 用户对双目 SSL contract 的确认。
- Task 3 的页序、dependency manifest 和待填素材清单。
