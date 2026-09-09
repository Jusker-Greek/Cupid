# CUPID 双目自监督汇报 Storyboard

状态：`DIAGRAM-FIRST REVIEW DECK BUILT / USER REVIEW REQUIRED`

本文档把原来的复现故障叙事改为面向师兄和老师的方法故事，规定每页目的、
证据边界和统一母图合同。2026-09-10 根据用户要求，Step 3 改成先画图、再用 slides
讲清楚改动/冻结边界、输入输出、梯度和 pose provider；当前 review deck 已构建，
但仍不批准某一种双目方法，也不把设计写成结果。

当前审查产物：

- `outputs/figures/cupid_stereo_ssl_explanation_pipeline_v01.drawio`
- `outputs/figures/cupid_stereo_ssl_explanation_pipeline_v01.png`
- `outputs/cupid_stereo_ssl_step3_review_v02.pptx`
- `outputs/cupid_stereo_ssl_step3_review_v02_contact_sheet.png`

## 故事主轴

- 北极星：讲清楚我们从哪个 CUPID baseline 出发，以及准备加入哪一个经过确认
  的双目自监督关系。
- 核心问题：双目信号应在 CUPID 的哪个接口施加约束，同时不改变原论文两阶段
  生成链的语义。
- 当前信息增量：CUPID 的论文/代码 baseline、上一项目的双目资料，以及首个
  same-time right-view reconstruction 接入规格均已定位；该规格仍待用户科学审核。
- 证据边界：论文和代码事实属于证据；reviewed diagram 属于经审核的表达；没有
  代码和实验结果的 integration diagram 仍是设计。
- 需要老师裁决：上一项目的故事层级、双目信号含义、loss/constraint 归属、
  CUPID 接入点，以及最小科学证据门。

## 九页主故事

### 1. CUPID 与双目自监督

- 页面目的：用一句话提出研究迁移问题。
- 暂定主旨：从 CUPID 的联合物体与相机生成模型出发，在保留原始生成链的前提
  下，把一个经过确认的双目关系作为训练信号加入模型。
- 视觉：沿用 Incremental Research Pipeline Slides 模板的极简封面。
- 当前状态：结构已起草；最终措辞等待用户确认任务 2 的故事层级。

### 2. CUPID baseline：联合物体与相机生成

- 页面目的：在任何项目改动出现前，先建立准确起点。
- 视觉：完整展示任务 1 通过静态 gate audit 的 CUPID baseline mother candidate，
  不用新的 slide shape 重画；用户批准前保持 `CANDIDATE`。
- 图外中文解释：CUPID 先预测粗结构与相机姿态，再以 pose-aligned conditioning
  生成几何和外观。
- 代码锚点：`cupid/pipelines/pipeline.py:305` 是 stage 1；
  `cupid/pipelines/pipeline.py:312` 是 stage 2；
  `cupid/pipelines/pipeline.py:324` 返回 pose 与解码后的 3D 输出。
- 当前状态：任务 1 candidate 已提交，但仍为 `NOT USER-APPROVED`，不能嵌入最终
  PPT。

### 3. CUPID 中与双目监督相关的接口

- 页面目的：只暴露双目约束可能接触的 baseline 对象。
- 视觉：从任务 1 的同一母图裁切；位置、名称、颜色、形状和连线全部继承，
  本页还不增加新路径。
- 必须保留的 baseline 对象：input image、DINOv2 conditioning、stage 1
  occupancy/UV outputs、PnP pose、pose-aligned conditioning、stage 2 generation、
  Gaussian/Mesh outputs。
- 代码锚点：`cupid/pipelines/pipeline.py:132` 生成图像 conditioning；
  `cupid/pipelines/pipeline.py:147` 将 UV 解码为 camera pose；
  `cupid/pipelines/pipeline.py:217` 使用预测的 extrinsics/intrinsics 投影稀疏坐标。
- 当前状态：接入点已由 `docs/CUPID_STEREO_INSERTION_SPEC_V1.md` 定义为 Stage 2
  denoiser 的 training-only render-loss branch，状态仍为 `DESIGN ONLY`。

### 4. 上一项目：双目观测、自监督重建与物理 baseline

- 页面目的：把上一项目中三个不同层级拆开，防止把它们误写成同一个 prior。
- 视觉：使用经确认来源中的公式或方法图，依次表达：
  `Stereo observation only`、`Self-supervised reconstruction`、
  `Stereo + physical baseline`。
- 必须讲清的边界：`left -> right` 只是 naive 单向重建；历史 joint I/O 是
  `[L_t0, R_t0] -> [L_t1, R_t1]`；`B = 0.25 m` 是独立的物理尺度锚点。
- 当前可见状态：来源事实标 `VERIFIED SOURCE`；尚未批准的连接标 `DESIGN ONLY`。
- 当前状态：资料审计已完成；最终选用哪一层仍需用户确认。

### 5. CUPID integration：一个局部增量

- 页面目的：让观众一眼看到新增内容与未变内容。
- 视觉：复制任务 1 完整母图，只加入用户批准的双目路径，并使用稳定项目色。
- baseline 区域：保持 CUPID 原有颜色与图形语义。
- 新增区域：使用唯一项目色；按 `docs/CUPID_STEREO_INSERTION_SPEC_V1.md` 暴露
  `One-step clean latent estimate`、fixed right-camera `Render` 和
  `Right-view L1 + LPIPS`，所有未实现接口仍用独立虚线并标注 `DESIGN ONLY`。
- 禁止内容：没有来源或代码依据的新模块名、推测箭头和 loss 位置。
- 当前状态：V1 insertion spec 已完成，但 baseline mother 与 integration 拓扑仍
  等待用户审核；不得把 spec 当作实现或结果。

### 6. CUPID 内部的双目监督合同

- 页面目的：在不重画系统的前提下，让训练信号可审计。
- 视觉：从 integration mother diagram 裁切双目增量区域。
- 当前 V1 只提出 same-time `L_t -> R_t` observation reconstruction：标出同步右图
  target、`E_R = T_R<-L E_L` fixed geometry、L1 + LPIPS、`stereo_valid AND
  cfg_conditioned` mask 与 renderer/gradient ownership；明确这是
  `DESIGN ONLY / S01 UNVERIFIED`。
- numeric `B = 0.25 m` / baseline-norm constraint 只作为后续独立 Gate 提及，
  不进入当前 integration crop。
- 必须区分 learned module、fixed geometry/conversion、renderer/consumer 和
  supervision contract，四者不能共用同一种 shape。
- `B = 0.25 m`、feature consistency、temporal quartet 和 learned relation head
  均保持 out of scope；批准前不放 `RESULT` 标签。

### 7. 改动边界：保留的 CUPID 与项目新增部分

- 页面目的：直接回答“在哪个 baseline 上，改了多少”。
- 视觉：一个原生双列表格，加一张 integration mother diagram 小缩略图。
- baseline 保留项：CUPID 两阶段生成、DINOv2 conditioning、UV-to-pose decoding、
  pose-aligned conditioning 和 3D output decoders。
- 项目改动项：精确同步 stereo pair carrier、right-view L1 + LPIPS、接入点、
  trainable ownership 和 left-only 推理行为；以 insertion spec 与实际实现代码
  填入，当前均标 `DESIGN ONLY`。
- 当前状态：baseline 列已有依据；改动列由 V1 spec 定义但仍是
  `DESIGN ONLY / NOT IMPLEMENTED`。

### 8. 证据状态：来源事实、设计与结果

- 页面目的：避免把架构设计讲成实验结果。
- 视觉：一个原生四级 evidence ladder。
- `VERIFIED SOURCE`：CUPID 论文/官方代码，以及上一项目 authority 中的事实。
- `REVIEWED FIGURE`：任务 1 baseline mother diagram 和之后审核通过的 integration
  mother diagram。
- `DESIGN ONLY`：尚无实现与实验依据的 stereo-to-CUPID 接入或 loss 路径。
- `RESULT`：只留给完成且可比较的科学评估；当前 deck 默认为空。
- 明确移除：复现故障、Slurm job、smoke、preflight 和 readiness 不进入主故事。

### 9. 最小证据门与讨论问题

- 页面目的：用最小可证伪实验收束，并把需要老师决定的点说清楚。
- 视觉：证据门与同一 integration mother diagram 缩略图对齐。
- 证据门字段：frozen baseline、single-variable adaptation、dataset/split、stereo pair
  构造、target/loss、metric、baseline row、adaptation row 和 failure boundary。
- 讨论字段：选择 project-level 4D distribution learning 或 current metric-scale
  camera path；选择 observation/reconstruction 或 numeric `B` anchor；确认术语、
  接入点与首个单变量比较。
- 当前状态：证据门结构已确定；具体值等待方法批准。

## 母图与术语合同

- 任务 1 经审核的 CUPID baseline `.drawio` 是唯一 baseline mother。
- `docs/CUPID_STEREO_INSERTION_SPEC_V1.md` 是当前 integration 的唯一架构合同；
  它冻结一个 right-view reconstruction 变量，不批准任何 learned module 名称。
- integration mother 必须从该 `.drawio` 复制；所有 crop/zoom 必须能回溯到它。
- 图内只用英文；中文标题和解释使用原生 slide 对象。
- 稳定颜色归属：CUPID source、previous-project source、project adaptation、fixed
  geometry、loss/supervision、pending/frozen path。
- 同一概念全 deck 只保留一个可见名称；代码别名只进入 speaker notes 或 backup。
- 当 `NEW_MODULE_NAME_APPROVAL=PENDING` 或任一接口缺少 authority 时，integration
  figure 不得进入最终 PPT。
- 可直接复用的术语限于已核验集合，例如 `PoseEnc`、`Render`、
  `Calibrated stereo observation`、`Physical rig baseline`、
  `Self-supervised reconstruction`、`Direct camera prediction`、
  `Raw metric-scale evaluation`、`No alignment`、`c2w` 和
  `Plucker ray conditioning`。
- `4D Distribution Learner`、`4D Encoder`、`4D Decoder` 属于另一层 project-level
  定义，未确认前不能混入 metric-scale pipeline。

## Speaker notes 来源映射

| Slide | `[Sources]` 最低要求 |
| --- | --- |
| 1 | CUPID 论文；用户确认的上一项目权威文档 |
| 2 | CUPID Figure 3；任务 1 `.drawio`、PNG、audit、commit；CUPID pipeline 代码 |
| 3 | 任务 1 母图；`pipeline.py` 的 conditioning、pose decode 和 projection 锚点 |
| 4 | 上一项目 authority、相关设计审计文档、准确公式/段落位置 |
| 5 | 任务 1 母图 commit；上一项目来源 commit；integration `.drawio` commit |
| 6 | loss/constraint 来源；实现文件与行号；integration crop 来源 |
| 7 | CUPID baseline 代码；项目改动 commit 与文件行号 |
| 8 | 每一个 evidence-state 的来源；明确 `DESIGN ONLY` 没有结果依据 |
| 9 | 实验设计 authority；后续结果存在时补充 checkpoint、split 与 evaluator |

## 原 deck 的处理

原 23 页 deck 只作为模板视觉和 provenance 来源保留。复现故障页、Slurm ledger、
smoke/preflight 证据和动态 job 状态全部从新主线移除。唯一可复用的内容事实是
CUPID baseline 来源，以及说明改动边界所需的代码证据。

## 最终构建门

只有 dependency manifest 同时记录下列信息，才能开始最终 PPTX：

1. 任务 1 final commit，以及 reviewed `.drawio`、导出图和 audit 的精确路径；
2. 用户确认的上一项目故事层级与文档来源；
3. 批准后的 stereo direction、loss/constraint、gradient ownership 与 CUPID 接入点；
4. 所有新增可见标签的 approved terminology register。

通过后，使用 Artifact Tool JS 从保留模板构建；每页写入 `[Sources]` speaker notes；
输出新文件名；运行 finalizer；渲染全部页面；检查 contact sheet 和全尺寸页面；
最后运行 template-fidelity 检查。
