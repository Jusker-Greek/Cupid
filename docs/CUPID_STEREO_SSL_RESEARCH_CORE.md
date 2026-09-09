# CUPID 双目自监督表征学习核心文档

状态：`STEP 3 COMPLETE / USER REVIEW REQUIRED / STEP 4 BLOCKED`

更新时间：2026-09-09

本文档是 CUPID 双目自监督新项目的核心研究记录。步骤 1、2 已经由用户审核通过；
本轮完成步骤 3：比较 Stage 1 UV/pose、Stage 2 structured-latent distribution、
VAE/decoder 与跨 Stage 1+2 端到端路径，并提出一个待审核的首个最小 Gate。
步骤 4 在用户审核步骤 3 后才修改 draw.io 母图。

## 0. 项目问题卡

### 0.1 当前基础与目标

CUPID 是一个联合建模 3D object 与 camera pose 的生成式 3D reconstruction 模型，
能够输出可渲染的 3D Gaussian、mesh 或 radiance field。当前项目希望保留已经学好的
CUPID 作为强 3D 生成先验，再研究：

> 能否用不带 task-specific 3D 标签的同步双目图像，在训练期构造左右目相互验证的
> novel-view-synthesis / differentiable-rendering 闭环，微调 CUPID 的 3D 表示或生成
> 分布，使同一个表示更一致地解释多个视角，并降低继续依赖大量 3D 渲染真值的程度？

这里的首个目标是 `pretrained supervised CUPID -> stereo SSL fine-tuning`，不是立即用
双目 SSL 从零替代 CUPID 的有监督预训练，也不是立即扩展到完整动态 4D world model。

### 0.2 四步审核流程

| 步骤 | 内容 | 当前状态 | 审核出口 |
| --- | --- | --- | --- |
| 1 | 读取旧 stereo SSL 文档与实时 Overleaf；定义 stereo、SSL、representation learning、学习条件、已有设计和已有成果；区分理论、模型与 CUPID 可迁移内容 | `APPROVED BY USER` | 已确认实时 Overleaf、核心目标和 static-object 第一阶段 |
| 2 | 拆解 CUPID 当前学习过程：最小模块、每部分输入、输出、预测对象、监督、训练参数、冻结参数和可微路径 | `APPROVED BY USER` | 已确认三层表示、pose/3DGS 双重身份与无新 3D label 目标 |
| 3 | 比较多个 stereo SSL 接入点；分别论证 pose、Stage 1 structure、Stage 2 distribution、3D decoder/render 路径；确定首个最小 Gate | `COMPLETE / REVIEW REQUIRED` | 用户批准唯一首选接入点、pose 提供方式与 matched controls |
| 4 | 在审核过的 draw.io 母图上增量添加 stereo SSL branch，输出 editable draw.io、PNG 和图例 | `BLOCKED_BY_STEP_3_REVIEW` | 用户审核最终 pipeline 图 |

## 1. 证据级别与来源

本文使用以下标签，防止把理论、设计和结果混为一谈：

- `USER-APPROVED PRINCIPLE`：用户已审核确认的项目上位原则。
- `SOURCE FACT`：文档原文或当前代码可直接验证的事实。
- `THEORY`：由观测模型、几何关系或概率模型给出的理论解释。
- `MODEL DESIGN`：尚待 CUPID 实现或实验验证的模型方案。
- `RESULT`：已经执行并有指标记录的旧项目结果。
- `HYPOTHESIS`：合理但尚未被 CUPID 实验证实的推测。

### 1.1 当前最高优先级来源

1. 实时 Overleaf：
   [Learning 4D World Representations and Distributions from Stereo Sequences](https://www.overleaf.com/project/6a3839d9359f19a962ba12b1)
   - 2026-09-09 实时编译版本，共 13 页。
   - 包含 `Problem Formulation`、`System Decomposition` 和新增的
     `Concrete Research Questions and First Prototype`。
   - 该实时版本是本轮的理论 authority。
2. 本地较早镜像：
   `/Users/ruikegu/.codex/worktrees/metric-scale-controller-cleanup/xfactor_reproduce_overfit/docs/overleaf/problem_formulation_v1/`
   - 只覆盖 problem formulation 与 system decomposition。
   - 不包含实时 Overleaf 新增的 world-prior / posterior / prototype-validation 章节，
     因此只能作为历史镜像，不能覆盖实时版本。
3. 旧 Stereo-XFactor 项目汇总：
   `/Users/ruikegu/.codex/worktrees/metric-scale-controller-cleanup/xfactor_reproduce_overfit/docs/dual_input_dual_output_stereo_xfactor_project_brief.md`
4. 旧 stereo SSL 形式化设定：
   `/Users/ruikegu/.codex/worktrees/metric-scale-controller-cleanup/xfactor_reproduce_overfit/docs/overleaf/stereo_ssl_setting_and_progress/sections/01_setting.tex`
5. 旧 stereo / temporal self-consistency losses：
   `/Users/ruikegu/.codex/worktrees/metric-scale-controller-cleanup/xfactor_reproduce_overfit/docs/overleaf/stereo_ssl_setting_and_progress/sections/02_strict_self_consistency_losses.tex`
6. metric-scale 与 baseline 分离原则：
   `/Users/ruikegu/.codex/worktrees/metric-scale-controller-cleanup/xfactor_reproduce_overfit/docs/overleaf/metric_scale_pose_motivation/main.tex`
7. 已知物理 baseline 的单变量合同：
   `/Users/ruikegu/.codex/worktrees/metric-scale-controller-cleanup/xfactor_reproduce_overfit/docs/research_logs/2026-07-10-r1b-stereo-prior-contract-audit.md`

### 1.2 需要降级处理的材料

- `docs/overleaf/stereo_ssl_setting_and_progress/main.pdf` 当前编译的是一个较短的
  DL3DV long-gap pose comparison 合同；完整的 stereo SSL 概念必须读取其未被当前
  PDF include 的 background `.tex`，不能只看该 PDF。
- `docs/CUPID_STEREO_INSERTION_SPEC_V1.md` 是此前形成的 Stage 2 右目重建候选，状态是
  `DESIGN ONLY / S01 UNVERIFIED / NOT IMPLEMENTED`。它不是本轮步骤 3 的已批准结论。
- 已有 `p02_cupid_same_time_right_recon_v03_candidate.drawio` 是提前产生的候选图，
  不能替代本轮步骤 4，也不能描述为用户已审核的最终 pipeline。

### 1.3 用户已确认的项目原则（2026-09-09）

1. 实时 Overleaf 项目是本轮 stereo SSL / 4D representation 理论的 authority。
2. 项目的核心目标是研究一种由双目图像相互监督、能够持续改善模型表示结构的方法。
3. reconstruction、NVS、3DGS、renderer 和 pose estimation 都是训练载体、解码路径或
   用于与其他方法比较的 probe；它们不是最终要优化或宣称的研究对象。
4. 研究的最终对象是 learned representation 的结构质量及其可持续改善能力。论文中的
   render、pose、geometry、NVS 等结果是为了把不可直接观察的表示导出并验证，而不是
   把其中任一个指标当作核心目标。
5. 第一阶段限定为 `static object O + camera C + CUPID 3DGS renderer`；暂不把动态
   motion `M`、relation `R` 或 continual-learning/non-forgetting 作为首个 CUPID claim。

这组原则是后续方法研讨、实验设计、图示和论文写作的上位约束。任何新增模块都必须
说明它是在改善 representation、构造训练信号，还是仅用于 readout / evaluation。

## 2. Step 1：Stereo、SSL 与 Representation Learning

### 2.1 Stereo 是什么

`SOURCE FACT`：实时 Overleaf 将输入写为同步双目序列

```text
Y_1:T = {I_t^L, I_t^R}_{t=1}^T
```

固定 rig 满足稳定的左右目关系：

```text
T_{R_t<-L_t} = T_LR
```

左右图不是两个无关样本，而是同一时刻 hidden scene state `X_t` 在两个投影参数下的
耦合测量：

```text
I_t^v = h(X_t, theta_t^v) + epsilon,  v in {L, R}
```

`THEORY`：stereo 本身不是一种 representation。它提供的是对同一隐藏 3D 状态的第二个
几何测量。只要左右目同步、标定和配对正确，右图会排除一些仅凭左图无法区分的 3D
解释。例如 near-small 与 far-large 物体在左图中可以具有相同投影大小，但在已知焦距
`f` 和 baseline `B` 的校正双目中，其 disparity 为 `d=fB/Z`，不同深度产生不同右图。

因此，stereo 的核心价值不是简单“多一张图”，而是增加一个与第一张图共享场景状态、
但投影条件不同的识别性约束。

### 2.2 本项目中 SSL 是什么

`SOURCE FACT`：旧形式化文档将 SSL target 分为三类：

1. `prediction vs prediction`：从不同 view、window 或 composed path 得到两个预测，
   比较其一致性；通常一侧 stop-gradient。
2. `prediction vs observation`：预测图像或特征与真实观测图像比较。观测图像不是 3D
   标签，因此仍属于 self-supervised reconstruction。
3. `prediction vs derived geometric diagnostic`：使用 pose metadata 训练 probe 或做
   evaluation。这不是核心 SSL training loss，必须和前两类分开。

`THEORY`：本项目所谓 SSL，不是“没有任何 target”，而是 target 可由原始观测和已知
采集关系自动构造，不需要 object 3D Gaussian、depth、mesh 或 ground-truth 3D state
作为训练标签。典型闭环是：

```text
unlabeled stereo observations
  -> infer/sample one hidden 3D explanation
  -> project/render it under left and right cameras
  -> compare predictions with the observed images or independent predictions
  -> send the consistency gradient back to the representation learner
```

实时 Overleaf 的 prototype objective 进一步明确：

```text
L_SSL(phi) = - sum_n log sum_k pi_k p_sigma(Y_n | w_k, C_n)
```

其中没有 ground-truth 3D state；3D mode 与 metric depth 只用于 evaluation。

### 2.3 Stereo 为什么能构成 SSL 信号

要使“左目监督右目 / 右目监督左目”成为有效 SSL，而不是捷径或错误监督，至少需要：

1. `同步与同一实例`：`I_t^L` 与 `I_t^R` 必须来自同一对象、同一 hidden state 和同一
   timestamp。随机的两个 render view 不能自动当作 stereo pair。
2. `几何关系可用`：需要已标定或可可靠估计的 `T_LR`、左右内参以及 crop/resize 后
   一致更新的相机参数。若相机关系错误，重建误差不能可靠归因于表示。
3. `共享隐藏解释`：左右图必须通过同一个 object/scene representation 被解释；如果
   左右分支各自记忆一张图，就没有迫使表示形成共同 3D 结构。
4. `可检查的投影路径`：decoder/renderer 必须把预测变量投影回 observation space，
   并允许 loss 对目标 trainable representation 形成真实梯度路径。
5. `独立证据`：prediction-vs-prediction 的两侧必须来自不同 view、不同 window 或不同
   composed path。若两侧由同一中间量代数复制，loss 会成为恒等式。
6. `遮挡与成像误差边界`：occlusion、reflection、background、exposure 与 non-Lambertian
   区域会让正确几何也无法逐像素完全匹配；mask 和 robust loss 必须有明确来源。
7. `动态场景额外条件`：若物体运动，必须区分 camera motion 与 object motion。当前
   static-object CUPID 第一阶段可暂时避开该问题，但不能把 static 结论写成 dynamic 4D
   结论。

### 2.4 Representation learning 在这里学什么

实时 Overleaf 将完整 4D explanation 写为：

```text
Z_1:T = (C_1:T, S_1:T)
S_1:T = (M_1:T, O_1:T, R_1:T)
```

- `C`：camera trajectory，是解释观测、对齐和渲染所需的 observation-conditioned
  variable。
- `M`：object/part motion。
- `O`：跨视角持久的 object/part properties，包括 geometry、shape、part structure、
  appearance、identity-like 与可选 semantic features。
- `R`：object、part、motion motif 之间的 relation / scene composition。

可复用世界分布定义在 scene factors 上：

```text
D_phi = p_phi(S) = p_phi(M, O, R)
```

camera 用于条件化和观察解释，但不属于可复用 scene distribution 本身。

`THEORY`：所谓“表示空间具有更好的结构”，不能只解释成 latent 更平滑。至少包含以下
可检验含义：

- `view factorization`：物体/场景属性与相机视角分离，同一对象换视角后仍保持同一
  object representation。
- `cross-view persistence`：几何、形状和身份相关属性可以同时解释左右图，而不是只
  拟合 conditioning view。
- `ambiguity reduction`：单目允许的多个 3D mode 中，与右目测量不相容的 mode 获得
  更低概率。
- `distribution structure`：跨样本重复出现的 scene/object factors 能形成可比较、
  可聚类、可条件采样的分布，而不是每个样本只有孤立 deterministic token。
- `geometry/pose compatibility`：3D 表示和相机变量组合后能通过 renderer 返回正确的
  observation；pose 不能只是与 content 纠缠的记忆编码。

### 2.5 SSL 信号的四个层次

实时 Overleaf 给出了四类互补约束：

| 层次 | 约束 | 对表示的作用 |
| --- | --- | --- |
| Measurement / stereo consistency | 左右图是在固定 rig relation 下对同一 hidden state 的测量 | 排除只适配单目的 3D 假设 |
| Temporal consistency | 相邻时间的变化应由 camera motion 与 object motion 的合理组合解释 | 形成跨时间持久性；当前 static CUPID 首 Gate 可不启用 |
| Decoder consistency | 预测变量必须重新投影到真实观测 | 使 latent 具备可观测、可反证的语义 |
| Structural consistency | camera、motion、object properties、relations 应解耦且保持相容 | 防止 content/pose/motion 纠缠 |

旧 Stereo-XFactor 文档还给出了更具体的 prediction-consistency 形式：

- left temporal pose prediction vs right temporal pose prediction；
- direct left path vs left-right-left stereo-exchange path；
- direct long-range pose vs composed short-range pose；
- rendered target pose vs independent cross-view pose target；
- prediction image vs observed target image。

这些是不同 Gate，不能在 CUPID 首次实验中一次全部加入。

### 2.6 NVS / reconstruction 是什么角色

实时 Overleaf 两次明确限定：

> image reconstruction serving as a consistency test rather than the final
> definition of 3D knowledge

以及：

> The expected result is not merely better image reconstruction.

`USER-APPROVED PRINCIPLE`：NVS 或 image reconstruction 是微调 representation 的一种
手段，也是把隐藏表示导出成可比较观测的一种 probe。3DGS、renderer、pose estimation、
depth 或 mesh 具有同样的从属地位：它们可以传递训练信号，也可以在论文中用于和其他
方法比较、说服读者表示确实更有结构，但都不是本项目最终追求的对象。

`THEORY`：这些 readout 回答“这个 representation 是否支持正确的跨视角解释、几何、
相机关系或下游预测”。然而低 pixel loss 或低 pose error 本身不自动证明表示整体结构
正确。模型仍可能依赖 texture copy、view memorization、错误 pose 与错误 geometry 的
互相补偿，或某个 decoder 的额外 capacity 来降低单项误差。

因此 CUPID 后续需要一个 probe battery，而不能让单个 PSNR、pose 或 3DGS 指标代表
全部 representation quality。每个 probe 都要声明它测试的结构属性；具体指标和主次
关系在步骤 3 冻结。

## 3. 理论、模型与成果的分类

### 3.1 可以作为新项目理论基础的内容

1. `Stereo identifiability`：第二个已标定视角可以区分单目投影相同、但 metric depth
   或真实尺寸不同的 3D modes。
2. `Observation likelihood`：通过固定 camera projection / renderer，把不带 3D 标签的
   图像转化为对 3D representation/distribution 的训练信号。
3. `Representation is not reconstruction`：重建是检验手段；最终目标是可复用、跨视角
   持久、与 pose 解耦的 3D scene/object knowledge。
4. `Population prior vs scene posterior`：跨对象/场景的 `p_phi(W)` 与单个场景接收更多
   观测后的 `b_t(W)` 是两个不同对象。微调全局 CUPID 参数不等于只更新某个实例的
   posterior。
5. `Claims must be separated`：stereo identifiability、persistent belief update、continual
   prior learning 是三个独立命题。stereo 本身不保证 neural fine-tuning 不遗忘。
6. `Single-variable gates`：先比较 mono 与 stereo observation；若再加入数值 baseline
   `B`、pose cycle、feature consistency 或动态 temporal loss，必须分别开 Gate。

### 3.2 已经提出的模型设计，但不是统一方案

| 设计 | 来源 | 当前判断 |
| --- | --- | --- |
| Same-time `I_L -> I_R` 或对称 `I_R -> I_L` reconstruction | 旧 stereo baseline / 当前 CUPID 候选 | 最小、直接，但只能证明同一时刻跨视角可渲染性 |
| `[L_t0,R_t0] -> [L_t1,R_t1]` dual-input dual-output NVS | Stereo-XFactor | 同时涉及 stereo 与 temporal learning，变量更多，不适合直接当 CUPID 首 Gate |
| 左右目 pose prediction consistency | strict SSL losses | 适合显式 pose learner；必须保证两侧证据独立 |
| left-right-left pose graph closure | strict SSL losses | 几何含义清楚，但需要统一、已验证的 transform convention |
| 已知数值 baseline-norm loss | metric-scale line | 可以提供物理尺度锚点，但必须晚于 stereo-observation-only Gate |
| Motion Decomposer + 4D Encoder + Distribution Learner + Decoder | 实时 Overleaf | 项目级 4D 角色分解，不是已冻结 neural architecture |
| finite stereo micro-world likelihood model | 实时 Overleaf prototype | 用于先证明 stereo identifiability；不是 CUPID end-to-end 实现 |

### 3.3 已有成果与未有成果

`RESULT`：旧 Stereo-XFactor 的最小 two-time dual-output 路径已经能运行，但 1k smoke
并未显示正向收益：

| 旧实验 | PSNR | L1 | LPIPS | 严格解释 |
| --- | ---: | ---: | ---: | --- |
| `[L0,R0] -> [L1,R1]` | 14.871 | 0.2721 | 0.7083 | plumbing 可运行；低于 matched single-target controls |
| `[L0,R0] -> L1` | 16.279 | 0.2280 | 0.6860 | single-target control |
| `[L0,R0] -> R1` | 16.477 | 0.2180 | 0.6769 | single-target control |

`RESULT`：旧 shifted-source feature/pose readout diagnostics 在部分 TartanAir/VKITTI2
设置上优于 direct readout，说明外部 window 中可能存在有用 pose 信息；但训练代理的
rotation/translation 改善不一致，尚不能作为稳定 stereo SSL 结论。

`SOURCE FACT`：实时 Overleaf 的 G0/G1/G2 是拟议、可证伪的 prototype protocol。
当前文档没有报告这些 Gate 已执行，也没有提供正向实验结果。

`SOURCE FACT`：当前没有证据证明 stereo SSL 已经改善 CUPID 的 representation、
distribution、pose 或 NVS。当前 CUPID stereo spec 和图全部是 `DESIGN ONLY`。

因此目前可以说“已有理论定义、旧模型设计和部分诊断结果”，不能说“我们已经证明
双目 SSL 可以把 CUPID 表示学得更好”。

## 4. 哪些内容可以迁移到 CUPID

### 4.1 直接可用的理论映射

| Overleaf 角色 | CUPID 当前近似对象 | 可迁移程度 |
| --- | --- | --- |
| object properties `O` | canonical 3D structured latent 及其 Gaussian/mesh/RF 输出 | 高；是当前 static-object 项目的核心 |
| camera factor `C` | CUPID Stage 1 的 UV / camera pose 路径 | 高；但是否参与 SSL 梯度要在步骤 3 比较 |
| 4D Distribution Learner | CUPID Stage 2 structured-latent generative model | 中到高；CUPID 是连续生成模型，但尚未证明其概率校准或 stereo identifiability |
| 4D Decoder | structured-latent decoder + Gaussian renderer | 高；已有 observation-space render 能力 |
| stereo measurement consistency | 同一个生成 3D 表示在 `C_L`、`C_R` 下渲染并与真实左右图比较 | 高；是最直接的训练闭环 |
| motion `M` | 当前 static single-object CUPID 无对应完整模块 | 低；后续动态 Gate |
| relation `R` / scene composition | 当前 CUPID 无明确 object-relation graph | 低；不能在首阶段声称学到 |
| persistent belief / continual learning | 当前 CUPID fine-tuning 不等于 Bayesian scene belief update | 低；需要独立方法与 non-forgetting Gate |

### 4.2 CUPID 具备的关键接口证据

下面只记录步骤 1 所需的迁移可行性，不在此决定最终接入点：

- `cupid/pipelines/pipeline.py:305`：Stage 1 从输入图像预测 coarse structure 与 pose。
- `cupid/pipelines/pipeline.py:312`：Stage 2 根据结构、图像条件与 pose-aligned UV 采样
  structured latent。
- `cupid/models/structured_latent_vae/decoder_gs.py:118`：structured latent 可以 decode
  为显式 Gaussian representation。
- `cupid/trainers/vae/structured_latent_vae_gaussian.py:162`：独立 VAE trainer 已经存在
  `latent -> Gaussian -> render -> L1/SSIM/LPIPS` 的 observation reconstruction 路径。
- `cupid/renderers/gaussian_render.py:60`：renderer 显式建立 screen-space gradient
  carrier，静态代码上具备作为可微 consumer 的候选条件；真实 backward 仍需后续
  cluster smoke 验证。
- `cupid/trainers/flow_matching/sparse_flow_matching.py:95`：当前 Stage 2 flow trainer
  只计算 velocity MSE，没有 decode/render image loss。
- `cupid/pipelines/pipeline.py:266`：完整 inference pipeline 被 `@torch.no_grad()` 包围，
  不能直接拿来做训练闭环。

### 4.3 当前可以提出的 CUPID 假设

`HYPOTHESIS`：给定同步、标定的 `(I_L, I_R)`，让 CUPID 产生一个共享 3D object
representation `W_hat`，再在左右相机下渲染：

```text
W_hat = CUPID(I_L)              # 或后续比较 joint stereo conditioning
I_L_hat = Render(W_hat, C_L)
I_R_hat = Render(W_hat, C_R)

L_stereo_obs = d(I_L_hat, I_L) + d(I_R_hat, I_R)
```

如果 conditioning view 已由原 CUPID 训练充分约束，最小新增信息可以只取 held-out
right-view term；对称 `L<->R` 可以作为后续 matched Gate。

这条假设可用于 CUPID 的原因是：CUPID 的 hidden variable 本身就是可渲染 3D 表示，
而右目是真实但不需要 3D 标注的新观测。若同一 `W_hat` 只能解释左图而不能解释右图，
则它不是与 stereo measurements 相容的 3D explanation。反向梯度有机会把概率质量或
生成结果推向同时解释两眼的 3D states。

但是，“更好的表示”必须由超出训练重建 loss 的指标证明。首选证据应包括：

- 未参与 conditioning 的 held-out eye/view predictive quality；
- rig / pose consistency；
- geometry、depth、shape 或 multi-view consistency；
- 原 CUPID generation/reconstruction 能力不显著退化；
- 若声称 distribution 改善，还需多样性、mode coverage、likelihood proxy 或校准指标，
  不能只展示单张 render。

### 4.4 关于“预测两个 pose”的当前边界

用户提出“预测出两个 pose，再通过左右目重新渲染并闭环监督”。这一方向成立，但存在
三个不同模型命题，必须在步骤 3 分开比较：

1. `一个预测 pose + 固定 rig transform`：预测 `C_L`，由标定的 `T_LR` 推导
   `C_R`。该方案把右目当独立测量，变量最少。
2. `两个独立预测 pose + rig consistency`：分别预测 `C_L_hat`、`C_R_hat`，再约束
   `C_R_hat C_L_hat^{-1}` 与固定 `T_LR` 一致。该方案可能微调 pose representation，
   但也增加 pose/geometry 互相补偿的风险。
3. `交叉预测与 cycle`：左目路径预测右目 pose/render，右目路径预测左目 pose/render，
   再做对称或 left-right-left closure。该方案最接近“相互监督”，但包含更多路径和
   stop-gradient 决策。

步骤 1 不预先宣布哪一个最好。步骤 3 必须把它们与 Stage 1/Stage 2/decoder 的梯度终点
一起比较后再选首个 Gate。

## 5. 不能直接搬到 CUPID 的内容

1. `完整动态 4D`：Motion Decomposer、motion motifs、camera-object motion decoupling、
   temporal relations 不属于当前 static single-object CUPID 的已有能力。
2. `Relation learning`：CUPID 当前没有明确的 object-relation-object 或 scene
   composition distribution，不能因 stereo reconstruction 自动声称学到了 `R`。
3. `Bayesian posterior`：CUPID 的 deterministic sample/latent 或 SGD fine-tuning 不是
   自动归一化的 multi-hypothesis posterior `b(W)`。
4. `Continual non-forgetting`：stereo 提供 observation likelihood，但不自动保护旧分布；
   若持续微调，需要单独 retention mechanism 与旧能力 guard。
5. `Metric scale`：stereo observation 与明确输入数值 baseline `B=0.25m` 是两个变量。
   第一项可以先测试；第二项必须作为独立 successor Gate。
6. `NVS 指标即 3D 结论`：更高 PSNR 不能单独证明 geometry、pose factorization 或
   distribution calibration 改善。

## 6. Step 1 暂定结论

### 6.1 建议用于 CUPID 立项的一句话定义

> 我们的核心目标是探索一种利用同步双目图像相互监督、能够随着无 3D 标签观测持续
> 改善模型表示结构的方法。CUPID 提供已经由有监督 3D 数据学到的强初始化；NVS、
> 3DGS renderer、pose、depth 和其他解码结果用于把双目观测变成微调信号，并作为
> representation probes 验证跨视角持久性、几何一致性、相机解耦和分布结构。最终
> claim 是 stereo mutual supervision 改善了 learned representation，而不是单独完成了
> 更好的渲染、3DGS 或 pose estimation。

### 6.2 当前最重要的边界

- reconstruction/NVS/3DGS/pose 是表示学习的手段和可反证 probe，不是最终研究目标。
- stereo 能增加 identifiability，但“增加了观测”不等于“神经分布一定学得更好”。
- CUPID 的 static object factor `O`、camera factor `C`、3D Gaussian decoder/renderer
  与这套理论高度对应；动态 `M`、关系 `R`、continual learning 暂不对应。
- 当前没有 CUPID stereo SSL 正向结果，只有设计可行性和旧项目的混合证据。
- 首个实验必须保持单变量，不能同时加入 stereo input、数值 baseline、两个新 pose
  head、cycle loss、feature loss 与 temporal 4D loss。

## 7. Step 1 用户审核记录

2026-09-09，用户确认：

1. 实时 Overleaf 是当前理论 authority。
2. reconstruction 是微调 representation 的手段；3DGS、renderer、NVS 和 pose
   estimation 也主要是训练接口或 probe，用于导出、比较和证明表示结构，而不是最终
   研究目标。
3. 核心目标是探索一种通过双目图像相互监督、能够持续改善 learned representation
   结构的方法。
4. 第一阶段接受 `static object O + camera C + CUPID 3DGS renderer` 的范围，不引入
   motion `M`、relation `R` 与 continual-learning/non-forgetting claim。

这里的“持续改善”首先指：随着可获得的无 3D 标签双目数据继续加入，模型可以继续被
微调并改善 representation structure。它不自动等价于已经解决 catastrophic forgetting
或严格 Bayesian continual learning；后两者只有在加入 retention 和专门评估后才能声称。

## 8. 核心文档持续维护协议

从本次方法研讨开始，本文档持续累积以下内容，并作为未来完整项目文档与 Overleaf
写作的直接素材库：

- 用户已批准的研究目标、术语和 claim boundary；
- CUPID baseline 的代码事实与版本锚点；
- 每个方法假设、最小 Gate、单一变量、冻结项和反证条件；
- 正向结果、负向结果、失败原因与仍未验证的推测；
- representation-level claim 与 render/pose/3DGS probe evidence 的对应关系；
- 可直接进入论文的 problem statement、method description、experiment rationale 和
  limitation；
- draw.io 母图、增量修改说明和图中每条监督路径的证据来源。

维护规则：新信息必须标记为 `SOURCE FACT`、`THEORY`、`MODEL DESIGN`、`RESULT` 或
`HYPOTHESIS`；失败实验与负结果也保留；旧判断被新证据推翻时更新状态但不伪装成从未
发生；任何 probe 指标都必须写清楚它验证 representation 的哪种结构属性。

## 9. Step 2：CUPID 当前模型与学习条件拆解

状态：`COMPLETE / USER REVIEW REQUIRED`

### 9.1 首先区分三个层面

当前 CUPID 不能只画成一条 `image -> 3DGS` 直线。需要区分：

1. `Representation construction`：用 3D object、voxel、render 和 camera 数据训练
   多个 VAE，定义 coarse structure、UV 与 structured latent 的表示空间。
2. `Conditional distribution learning`：用 image-conditioned flow matching 学习从图像
   条件到这些 latent distributions 的生成过程。
3. `Readout / verification`：把 latent 解码成 pose、3DGS、mesh、radiance field 或
   render image，用于内部对齐、训练信号和外部评估。

因此，CUPID 的“表示”不等于 3DGS，也不等于 pose。更接近研究核心的是多层 latent
spaces 及其 conditional generative distributions；3DGS 和 pose 是这些表示的可解释
接口。但是在当前 CUPID 计算图中，pose 还承担 Stage 1 到 Stage 2 的内部对齐作用，
3DGS renderer 还承担 structured-latent VAE 的训练信号作用，二者不是纯粹的事后可视化。

### 9.2 CUPID 推理 pipeline 的最小拆分

```text
single image
  -> [A] preprocessing / foreground crop
  -> [B] frozen DINOv2 + raw visual conditioning
  -> [C] Stage 1 sparse-structure/UV flow sampling
  -> [D] occupancy + UV decoding
  -> [E] analytic DLT/EPnP pose solve
  -> [F] pose-aligned per-voxel image conditioning
  -> [G] Stage 2 structured-latent flow sampling
  -> [H] Gaussian / mesh / radiance-field decoders
  -> [I] pose + 3D outputs + optional rendering/probes
```

| 模块 | 输入 | 直接输出 | 是否 learned | 当前作用 |
| --- | --- | --- | --- | --- |
| A. Image preprocessing | 单张 RGB/RGBA image、可选 mask | foreground RGBA、crop metadata | 否 | 去背景和 canonical crop；crop 会影响相机语义 |
| B. Image conditioning | processed image | DINO patch tokens、256-resolution raw visual tensor | DINO 冻结；raw tensor 非参数 | 为 Stage 1/2 提供 appearance/semantic condition |
| C. Stage 1 flow | noise、DINO condition | coarse structure + UV latent sample `z_s` | 是 | 学习图像条件下 coarse 3D support 与 view-linked UV latent 的分布 |
| D. Structure/UV decode | `z_s` | sparse occupancy coordinates、每个有效 voxel 的 UV | learned decoders，但推理时冻结 | 把 Stage 1 latent 变为 coarse canonical support 与 2D correspondence |
| E. Pose solve | canonical voxel centers + predicted UV | intrinsics、world-to-camera extrinsics | 否；DLT/EPnP 解析求解 | 将 UV correspondence 导出为 camera pose |
| F. Pose-aligned conditioning | occupancy coords、pose、DINO tokens、raw image | 每个 3D voxel 对应的 DINO/visual features | 部分冻结、部分 learned | 把 image evidence 按预测 pose 对齐到 canonical 3D support |
| G. Stage 2 flow | noisy structured latent、time、pose-aligned features、DINO condition | clean structured latent sample `z_slat` | 是 | 学习 fine object representation 的 conditional distribution |
| H. Output decoders | `z_slat` | 3D Gaussian、mesh、radiance field | 独立预训练；推理时冻结 | 将共享 latent 导出为不同 3D readouts |
| I. Render/probes | 3D readout + camera | RGB/depth/pose/geometry metrics | renderer/solver 通常无训练参数 | 验证和比较表示；不是项目最终目标 |

主要代码证据：

- `cupid/pipelines/pipeline.py:301-326` 给出 A-I 的实际推理顺序。
- `cupid/pipelines/processing.py:87-139` 的 DINO image encoder 是 `@torch.no_grad()`。
- `cupid/pipelines/processing.py:143-178` 从 predicted UV 解析得到 pose。
- `cupid/pipelines/pipeline.py:217-239` 用 pose 将 sparse coordinates 投影到图像并进行
  Stage 2 sampling。
- `cupid/models/structured_latent_flow.py:365-397` 从 DINO patch tokens 采样 voxel-aligned
  latent condition；该预训练 SLat encoder 被置于 eval 且 `@torch.no_grad()`。
- `cupid/models/structured_latent_flow.py:494-533` 同时从 raw visual image 采样多尺度
  voxel-aligned features；visual conv blocks 属于 Stage 2 denoiser，可训练。
- `cupid/pipelines/pipeline.py:155-175` 将同一个 structured latent 分别导出为 Gaussian、
  mesh 和 radiance field。

### 9.3 CUPID 不是端到端一次训练，而是多个独立学习阶段

#### T0. 3D 数据与监督材料构造

`SOURCE FACT`：当前 dataset contract 直接读取以下离线材料：

- canonical object voxels：`voxels/<instance>.ply`；
- 多视角 rendered RGBA images 与 camera transforms；
- canonical sparse per-voxel DINO features；
- 由各 VAE encoder 预计算的 cached latents；
- mesh 或其他 geometry artifact。

例如 `cupid/datasets/sparse_structure.py:39-45` 从 object voxel PLY 构建 occupancy；
`cupid/datasets/components.py:303-322` 从 render metadata 读取 camera；
`cupid/datasets/sparse_feat2render.py:76-98` 读取 canonical sparse features。

这说明 CUPID 目前对大量 3D/rendered ground truth 的依赖不是单一 loss，而是整个
representation construction 与 cached-target pipeline 的数据基础。

#### T1. Sparse structure VAE：定义 coarse geometry latent

| 字段 | 当前合同 |
| --- | --- |
| 输入 | 64^3 binary occupancy `ss`，由 canonical 3D voxel PLY 构建 |
| 预测 | occupancy reconstruction logits |
| 学习内容 | coarse 3D support 的 8-channel VAE latent space |
| Loss | Dice（当前 config）+ `lambda_kl=0.001` |
| Trainable | sparse structure VAE encoder + decoder |
| 不学习 | image-to-3D mapping、stereo relation、camera pose |

证据：`configs/vae/ss_vae_conv3d_16l8_fp16.json:1-63` 与
`cupid/trainers/vae/sparse_structure_vae.py:58-92`。

#### T2. UV structure VAE：定义 view-linked geometry/pose latent

| 字段 | 当前合同 |
| --- | --- |
| 输入 | `ssuv` 与 `uv_volume`；UV 由 canonical 3D voxel centers 使用真实 render camera 投影得到 |
| 预测 | valid UV support 与每个 voxel 的 2D UV coordinates |
| 学习内容 | 可由 canonical 3D support 解码出 image correspondence 的 8-channel UV latent |
| Loss | `ssuv` Dice + masked UV L1 + `lambda_kl=0.001` |
| Trainable | UV VAE encoder + decoder |
| Pose 地位 | 不直接回归 pose loss；pose 在推理时由 decoded UV 经 DLT/EPnP 求解 |

证据：`cupid/datasets/sparse_uv_structure.py:24-81`、
`cupid/trainers/vae/sparse_uv_structure_vae.py:118-175`、
`configs/vae/uv_vae_conv3d_16l8_fp16.json:40-80`。

#### T3. Structured-latent Gaussian VAE：定义 fine object latent

| 字段 | 当前合同 |
| --- | --- |
| 输入 | canonical sparse per-voxel DINO features、一个真实 render view、alpha、真实 camera |
| 中间表示 | sparse structured latent `z_slat`，8 channels per active voxel |
| 解码 | 每 voxel 生成多个 Gaussian parameters：position offset、color、scale、rotation、opacity |
| Loss | rendered image L1 + `0.2 SSIM` + `0.2 LPIPS` + KL + Gaussian volume/opacity regularization |
| Trainable | structured-latent encoder 与 Gaussian decoder |
| 学习内容 | 可通过 Gaussian renderer解释图像的 canonical fine object representation |

证据：`cupid/datasets/sparse_feat2render.py:60-127`、
`cupid/models/structured_latent_vae/encoder.py:55-73`、
`cupid/models/structured_latent_vae/decoder_gs.py:67-123`、
`cupid/trainers/vae/structured_latent_vae_gaussian.py:137-199`、
`configs/vae/slat_vae_enc_dec_gs_swin8_B_64l8_fp16.json:60-103`。

这里 3DGS/renderer 是构造和训练 `z_slat` 的 decoder/measurement interface；新项目
仍把 `z_slat` 的结构质量作为研究对象，而不是把 Gaussian 参数本身当最终目标。

#### T4. Stage 1 image-conditioned flow：学习 coarse structure/UV 分布

| 字段 | 当前合同 |
| --- | --- |
| 输入 | 单张 conditioning render 的 frozen DINO tokens、noise、flow time `t` |
| Target | cached sparse structure latent；CUPID UV 版本还包含 cached UV-structure latent |
| 预测 | flow velocity，采样后得到 joint coarse structure/UV latent |
| Loss | velocity MSE；无 pixel render loss、无 direct pose loss |
| Trainable | Stage 1 denoiser；DINO encoder 冻结 |
| 学习内容 | `p(z_structure, z_uv | image)` 的 flow-matching 近似 |

证据：`configs/generation/ss_flow_img_dit_L_16l8_fp16.json:21-68`、
`configs/generation/suv_flow_img_dit_L_16l8_fp16.json:21-85`、
`cupid/trainers/flow_matching/sparse_flow_matching.py:77-117`。

#### T5. Stage 2 image/pose-conditioned flow：学习 fine object distribution

| 字段 | 当前合同 |
| --- | --- |
| 输入 | cached normalized `x_0=z_slat`、sparse coords、单张 render、DINO condition、raw visual condition、由真实 camera 投影得到的 per-voxel UV |
| 预测 | structured-latent flow velocity；采样后得到 `z_slat` |
| Loss | 当前只有 velocity MSE |
| Trainable | `ElasticVisualLatentConditioningSLatFlowModel` denoiser，包括 visual conv 与 sparse transformer |
| Frozen/外置 | DINO encoder；用于 DINO voxel latent 的预训练 SLat encoder；target `x_0`；camera metadata |
| 当前未发生 | structured latent 没有在该 trainer 内 decode/render；没有 stereo、NVS 或 image reconstruction gradient |

证据：`configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond.json:27-124`、
`cupid/datasets/structured_latent.py:223-286`、
`cupid/trainers/flow_matching/sparse_flow_matching.py:95-117`。

一个关键训练/推理差异是：Stage 2 训练 dataset 使用真实 render camera 生成 pose-aligned
UV；完整推理则使用 Stage 1 predicted UV 解出的 pose 再重新投影。这意味着 CUPID 的两个
stage 目前不是通过最终 image loss 端到端联合训练，Stage 2 训练也不直接承受 Stage 1
pose error。这一边界会直接影响步骤 3 的 stereo SSL 接入点比较。

#### T6. Mesh / radiance-field decoders：共享 latent 的其他 readouts

Mesh 和 radiance-field decoder 使用同一 `z_slat` 作为输入，但通过各自 image/depth/
geometry losses 独立训练。它们说明 structured latent 可以支持多种 3D readout，也可在
后续作为 representation probe；它们不是首个 stereo SSL Gate 必须同时更新的模块。

### 9.4 当前 CUPID 学到的“表示”最小可分为三层

| 表示层 | 内容 | 与项目核心目标的关系 |
| --- | --- | --- |
| `z_structure` | coarse canonical occupancy/support | 表示物体在哪里存在；结构性最直接但外观信息弱 |
| `z_uv` | canonical voxel 到观察图像的 correspondence | 承载 view/camera-linked structure；可解析 pose，但不应只以 pose error 定义其好坏 |
| `z_slat` | canonical per-voxel fine geometry/appearance features | CUPID object representation 与 Stage 2 distribution 的主要载体，可导出 GS/mesh/RF |

与之对应有两个 conditional flow distributions：

```text
Stage 1: p_theta1(z_structure, z_uv | I)
Stage 2: p_theta2(z_slat | I, support, pose-aligned features)
```

严格来说，当前代码中的 flow matching 给出的是隐式生成过程，不是已经校准的显式
likelihood。因此后续可讨论“conditional generation distribution 得到改善”，但若要
声称 posterior calibration 或显式 probability improvement，需要另行设计指标。

### 9.5 哪些是核心学习对象，哪些是训练手段或 probe

| 对象 | 当前角色 | 后续论文中的正确定位 |
| --- | --- | --- |
| Stage 1/2 flow denoisers | 学习图像条件下 latent distribution | 主要可持续微调对象候选 |
| `z_structure / z_uv / z_slat` | model internal representations | 核心研究对象；需要通过多个 probe 验证结构质量 |
| VAE encoders/decoders | 定义 latent vocabulary 与 readout | 可以冻结作稳定 measurement interface，也可以另开 Gate 微调 |
| DINOv2 | frozen image prior/conditioner | 外部视觉先验，不是本项目要声称学到的 representation |
| Pose DLT/EPnP | Stage 1 到 Stage 2 的内部桥接，同时是 camera probe | 可用于验证 view factorization；pose 指标不是最终目标 |
| 3D Gaussian decoder/renderer | `z_slat` 的可微观察接口和 3D readout | 用于构造 SSL signal、render/NVS probe；3DGS 参数不是最终目标 |
| Mesh/RF decoders | alternative readouts | 检查收益是否只适配 GS decoder，防止 renderer-specific shortcut |
| PSNR/L1/LPIPS/pose/depth | measurement metrics | 必须明确分别验证 representation 的哪种属性 |

### 9.6 当前 supervised dependence 的准确位置

CUPID 对 3D supervision 的依赖不能只说成“训练时用了 3DGS”。更准确的是：

1. coarse occupancy target 来自 canonical 3D voxelization；
2. UV target 来自 canonical 3D points 与真实 render camera 的投影；
3. fine structured latent 的输入/target 来自 canonical sparse 3D features 与离线 VAE；
4. image-conditioned Stage 1/2 flows 都回归这些由 3D asset pipeline 产生的 cached latent；
5. Gaussian/mesh/RF decoder 的训练使用 rendered observations、camera，有些还使用 mesh/
   depth/TSDF 等 geometry target。

因此新项目真正要替代或减少的不是某一个 3DGS loss，而是 `必须依靠 3D assets 产生
latent target 才能持续更新 conditional representation/distribution` 的学习条件。

### 9.7 Step 2 的关键结论

1. CUPID 的核心 representation 载体是 `z_structure + z_uv + z_slat` 及其 Stage 1/2
   conditional flow distributions，不是最终 3DGS render 或 pose 数字。
2. pose 和 3DGS 有双重身份：它们是验证 probe，同时在当前计算图中分别承担跨 stage
   对齐和 latent-to-observation decoding。设计 SSL 时可以借用其可微/几何接口，但
   不能让论文目标退化成 pose estimation 或 NVS benchmark。
3. 当前 CUPID 不是 end-to-end image reconstruction trainer。Stage 1/2 flow 的直接
   监督都是 3D asset pipeline 生成的 cached latent，Stage 2 没有 renderer feedback。
4. 最接近“持续改善表示”的 trainable 对象是 Stage 1/2 flow denoisers；VAE latent
   vocabulary 和 decoders 是否冻结，是步骤 3 必须比较的设计变量。
5. 第一阶段 static scope 合理：`z_structure`、`z_uv`、`z_slat` 已覆盖 object support、
   camera-linked correspondence 与 fine object properties，不需要先引入动态 `M/R`。

## 10. Step 2 用户审核记录

2026-09-09，用户确认 Step 2 的三个审核项：

1. 同意把 CUPID 的核心 learned representation 拆为
   `z_structure / z_uv / z_slat`，并把 Stage 1/2 flow 视为这些表示的
   conditional distribution learner。
2. 同意 pose 和 3DGS 的双重身份，但进一步强调：它们与 reconstruction、
   NVS、renderer 一样，都从属于“学出结构更好的 representation”这个核心目标。
   它们可以是微调表示的手段，也可以是将表示导出后与其他方法比较的
   probe，但不能反客为主成为项目最终目标。
3. 同意把“减少 3D 监督依赖”定义为：保留 CUPID 已经学好的 3D 先验与
   pretrained components，但对后续新增的同步双目数据，不再要求新的 3D asset
   latent labels，而是依靠左右目观测继续修正 representation/distribution。

Step 2 因此结束。后续设计和论文表述必须将“representation improvement”作为
claim，而将 render、pose、3DGS、geometry 和 NVS 明确写成产生梯度或验证 claim 的
measurement interfaces。

## 11. Step 3：Stereo SSL 接入点比较

状态：`COMPLETE / USER REVIEW REQUIRED`

### 11.1 选择标准

首个接入点必须同时满足：

1. 梯度直接到达 CUPID 的 representation/distribution learner，而不是只改进一个独立
   renderer 或 pose head。
2. 新 stereo pair 可以不带 object 3DGS、mesh、depth、voxel 或真实 cached
   latent label。
3. 只改一个科学变量，并能将 Stage 1、Stage 2、pose、decoder 之间的责任分开。
4. 充分利用已有 3DGS decoder/renderer 作为可微观测接口，但冻结其权重，
   防止通过扭曲 decoder 来伪装 representation improvement。
5. 除了训练所用的 target-view reconstruction，还必须能在 held-out view、跨视角
   表示持久性和其他解码器上验证，否则不能声称表示结构变好。

### 11.2 四个接入位置的对比

| 候选位置 | 直接更新对象 | Stereo 信号 | 主要优点 | 当前障碍/混淆 | 结论 |
| --- | --- | --- | --- | --- | --- |
| A. Stage 1 `z_structure/z_uv` | Stage 1 flow denoiser | 左右独立预测的 support、UV、pose 与 rig relation 一致 | 最直接检验 camera/view factorization | DLT 路径可微，但 occupancy threshold/`argwhere` 是离散的；EPnP 使用 NumPy/OpenCV 不可微；主要改进 `z_uv` 而非 fine object representation | 第二顺位；用于后续 pose/view-factorization Gate |
| B. Stage 2 `z_slat` distribution | Stage 2 flow denoiser | 由同一 `z_slat` 解码的 3D 在另一目 pose 下渲染并匹配实际观测 | 直接作用于核心 fine representation/distribution；可复用冻结 GS decoder/renderer | 现有 trainer 只有 cached `x_0` flow MSE；完整 sampler 是 `no_grad`；需要一个不使用新真实 3D latent 的稳定微调路径 | **首选位置** |
| C. Structured-latent VAE / GS decoder | VAE encoder、GS decoder 或两者 | 左右 render reconstruction | renderer 路径已在 VAE trainer 中成熟存在 | 当前 VAE encoder 输入是 canonical sparse 3D features，不是新双目图像；微调 decoder 容易通过改变 readout 降低 loss，并破坏旧 flow latent vocabulary | 后置；只作 decoder-adaptation 或 latent-vocabulary 独立 Gate |
| D. 跨 Stage 1+2 端到端 | Stage 1、Stage 2，可能还包括 decoder | 两目双向 render、pose cycle、latent consistency | 长期上能同时改进 coarse/fine representation 和 camera factorization | `pipeline.run()`、sampler 是 `no_grad`；硬 occupancy 筛选与可变 sparse support 不利于端到端梯度；多个模块可互相补偿，无法归因 | 长期方案，不是首 Gate |

`SOURCE FACT`：上表的关键代码边界为：

- `cupid/pipelines/processing.py:166-175` 默认 DLT pose 求解在 PyTorch 中运行；
  `cupid/utils/pose_utils.py:28-30` 显示 EPnP/calibration 路径转为 NumPy/OpenCV。
- `cupid/pipelines/processing.py:205-230` 使用硬阈值和 `argwhere` 构造 sparse support，
  support topology 对 Stage 1 logits 不可微。
- `cupid/trainers/flow_matching/sparse_flow_matching.py:95-105` 当前 Stage 2 训练依赖
  `x_0` 并仅使用 velocity MSE。
- `cupid/pipelines/samplers/flow_euler.py:66-99` 的现有 sampler 使用 `@torch.no_grad()`，
  不能原样用于 observation loss 反传。
- `cupid/models/structured_latent_vae/decoder_gs.py:118-123` 可将 `z_slat` 解码为
  Gaussian；`cupid/renderers/gaussian_render.py:60-140` 为 Gaussian 参数提供渲染梯度路径。
- `cupid/trainers/vae/structured_latent_vae_gaussian.py:162-193` 已有
  `latent -> Gaussian -> render -> image loss` 的训练组织方式。

### 11.3 对旧右目重建候选规格的修正

`docs/CUPID_STEREO_INSERTION_SPEC_V1.md` 中的主干思路仍然有效：冻结 Stage 1、
Gaussian decoder 和 renderer，把 right-view observation loss 的梯度只送回 Stage 2
denoiser。但它不能原样作为新项目的首 Gate，因为其 source contract 仍要求：

- 由 3D asset pipeline 缓存的真实 `x_0=z_slat`；
- 用于生成 pose-aligned UV 的训练 camera metadata；
- 在这些真实 latent 上继续计算原 flow-matching loss。

因此旧 V1 只能作为“有 3D latent anchor 时，右目 loss 是否有追加价值”的
supervised-assist control，不能验证“无新 3D label 时可持续改善表示”。本节不删除该
历史设计，但将其降级为 matched control，不再把它当作已冻结的新项目方法。

### 11.4 首选位置：Stage 2 observation-corrected self-distillation

`MODEL DESIGN`：首个最小 Gate 暂命名为：

```text
CUPID-S2-STEREO-OBS-CORRECTION-G1
```

机制是：先用冻结的 pretrained CUPID teacher 在新左图上生成一个伪 latent，再用
实际右图观测纠正 student Stage 2 distribution。Teacher latent 不是 3D ground
truth，只是已学 CUPID prior 对该新观测的初始解释；真正新增的信息来自未被用作
conditioning 的右目。

单向 `L -> R` 的最小训练流为：

```text
synchronized pair (I_L, I_R)
  -> frozen CUPID teacher on I_L
       -> support q_L, source pose C_L_hat, pseudo latent z_L_teacher
  -> frozen CUPID Stage 1 on I_R
       -> target pose C_R_hat
  -> add noise to stopgrad(z_L_teacher)
  -> trainable Stage 2 student predicts velocity / clean latent z_L_student
  -> frozen Gaussian decoder
  -> render the same object representation under stopgrad(C_R_hat)
  -> compare with observed I_R
  -> update Stage 2 student only
```

相应的形式化为：

```text
z_tilde_L = stopgrad(Teacher_CUPID(I_L).z_slat)
x_t       = Diffuse(z_tilde_L, epsilon, t)
v_hat     = Student_S2(x_t, t, I_L, q_L, C_L_hat)
z_hat_L   = v_to_x0(x_t, t, v_hat)

I_hat_R   = Render(D_GS(z_hat_L), stopgrad(C_R_hat))

L_anchor  = ||v_hat - v_target(z_tilde_L, epsilon)||^2
L_stereo  = L1(I_hat_R, I_R) + lambda_p * LPIPS(I_hat_R, I_R)
L_total   = lambda_a L_anchor + lambda_s L_stereo
```

`L_anchor` 是 teacher self-distillation anchor，目的是在没有真实 `x_0` 时保持 CUPID 原有
latent vocabulary 与 flow training parameterization；`L_stereo` 才是新的科学变量。为了归因，
matched control 使用相同 teacher pseudo latent、数据、噪声、更新步数和 `L_anchor`，
唯一关闭 `lambda_s=0`。

这个 Gate 不需要新 object 3D label，但仍保留了已有 3D-pretrained prior、冻结
decoder 和 teacher 预测。因此它验证的是“已学 3D prior 能否被新 stereo observations
继续纠正”，不是 stereo-only from-scratch learning。

### 11.5 为什么首 Gate 只更新 Stage 2

1. `z_slat` 是 CUPID fine geometry/appearance representation 及其生成分布的直接载体，
   比只改 `z_uv` 更接近用户确认的核心目标。
2. 冻结 Stage 1 和两个 pose，可以暂时将“物体表示变好”与“相机预测变好”
   拆开，避免 pose 与 geometry 互相补偿后仅让 render loss 下降。
3. 冻结 GS decoder 使其成为稳定 measurement function；若 decoder 也更新，不能区分
   改善来自 latent/distribution 还是 renderer-specific adaptation。
4. teacher pseudo latent 提供局部、可控的起点，避免第一步就解除完整 50-step
   sampler 的 `no_grad` 并将整条生成链展开反传。
5. 训练分支可被完全移除；默认推理仍可保持原 CUPID 的单目输入 API，双目是
   持续微调时的 supervision source，而不是强制的 inference dependency。

### 11.6 两个 pose 如何使用

用户提出的“预测两个 pose”在首 Gate 中保留，但它们是冻结的 observation
variables，不是首个被优化的目标：

```text
C_L_hat = stopgrad(PoseStage1(I_L))
C_R_hat = stopgrad(PoseStage1(I_R))
```

- `C_L_hat` 用来生成左目 pose-aligned Stage 2 conditioning。
- `C_R_hat` 只用作右目 renderer camera，右图的 DINO/raw features 不进入 Stage 2
  student，避免把 target appearance 直接泄露给 object representation。
- 若数据提供标定 rig relation `T_R<-L`，首 Gate 先用它做独立 pose/rig
  guard，不将其误差加入 loss，也不更新 Stage 1。

这一选择的原因是：当前尚未确认 physical stereo baseline 与 CUPID canonical object
coordinates 之间的 scale conversion。直接使用
`C_R = T_R<-L C_L` 需要 baseline 的 translation 已经是 CUPID canonical units，且左右 crop
后的内参更新完全正确。在这个数据合同核验前，使用两个冻结 predicted poses 可以
先测试 object representation 的跨视角观测纠正。

但是，右目 pose 由右图预测，仍然存在 target-image leakage 和 pose/content entanglement 风险。
因此 successor Gate 必须在数据合同成立后，用“单个预测左目 pose + 已标定固定 rig
transform 推导右目 pose”复现结果。若两种 pose provider 得出不同结论，不能把改善
归因于 representation。

### 11.7 “左右目相互监督”的实验阶梯

完整方法可以是对称的，但不在首次实验中把两个方向绑在一起：

| Gate | 唯一变化 | 目的 |
| --- | --- | --- |
| G1-LR | 在 matched self-distillation control 上只加 `I_L -> z_L -> C_R -> I_R` | 确认右目观测能否纠正左目条件的 Stage 2 distribution |
| G1-RL | 交换左右路由，其他完全不变 | 排除某一目画质、pose bias 或遮挡结构造成的假改善 |
| G2-symmetric | 将已分别通过的 LR 和 RL 项组合为对称 loss | 形成真正的左右目 mutual supervision |
| G3-pose | 冻结 Stage 2，只更新 Stage 1 UV flow 并加 rig consistency | 单独验证 camera/view factorization 是否改善 |
| G4-joint | 在 G2 和 G3 各自成立后才解冻 Stage 1+2 | 检验联合优化是否有额外收益，而不是相互补偿 |

数值 baseline embedding/loss、feature consistency、learned confidence mask、temporal motion 和 relation
head 都不进入 G1-LR。

### 11.8 Representation improvement 的验证合同

训练 target-view L1/LPIPS 只能证明 supervision branch 在优化，不足以验证项目
核心 claim。每个实验必须区分两层通过条件：

1. `Mechanism pass`：target right-view reconstruction 改善，梯度非零且有限，无 render
   collapse，无左右路由错误，flow anchor 与原单目性能不越过预注册回退阈值。
2. `Representation pass`：至少在一个未参与训练的表示探针上改善，且其他关键
   probes 不显著退化。

建议的 probe battery 为：

| Probe | 使用什么 | 验证的 representation 属性 |
| --- | --- | --- |
| Held-out camera NVS | 用未进入 LR/RL loss 的第三视角渲染，报告 LPIPS/PSNR/SSIM | 改善是否超越记忆 target eye，体现跨视角可泛化性 |
| Cross-view persistence | 分别从 `I_L/I_R` 推断表示，比较 canonical occupancy、decoded geometry 或同实例检索 | 同一物体是否在换视角后保持相同结构/身份 |
| Pose/rig guard | 比较 `C_R_hat C_L_hat^-1` 与标定 rig relation | object representation 改善是否只是 pose 错误补偿 |
| Cross-decoder transfer | 将同一 `z_slat` 送入冻结 mesh/RF decoder 或 GS 之外的 geometry probe | 收益是否存在于共享 latent，而非只过拟合 GS renderer |
| Distribution guard | 多随机种子下测量 stereo compatibility、sample diversity 与 collapse rate | conditional distribution 是否被改善而不是压成单一模式 |
| Frozen downstream probe | 在有 shape/category/identity 标签的评估集上，冻结 representation 训练线性/轻量 probe | 表示是否更容易被下游解码，且改善不仅是像素指标 |

首 Gate 的 scientific primary 建议设为 held-out camera LPIPS，因为它不使用训练右目；
cross-view persistence 为必须同时通过的 representation guard。只有 target-right LPIPS 改善时，
结论必须限制为“右目 reconstruction branch 有效”，不能写成“representation 更好”。

### 11.9 当前不确定性与失败条件

`HYPOTHESIS`：observation-corrected self-distillation 可以让 Stage 2 distribution 从
单目 teacher mode 向同时兼容双目的 mode 移动。该命题尚未有 CUPID 实验支持。

以下任一情况都使首 Gate 失败：

- teacher 伪 latent 错误太大，学生只在错误局部 mode 附近微调；
- 单步 `v_to_x0` 在高噪声 `t` 上无法产生可用渲染，导致梯度噪声大或训练不稳定；
- 右目 predicted pose 泄露 target content，或 pose/scale/crop 误差主导 image loss；
- 只改善训练右目或 GS decoder probe，held-out view 与 cross-decoder 不改善；
- student distribution 收缩、多样性下降，或原 CUPID 单目能力显著回退。

若失败，只调试本 Gate 新增的 stereo branch：先检查 pose/crop/route、gradient
ownership、`t` 分布和 teacher sample quality，不在同一轮加 relation head、feature loss、
depth head 或 joint Stage 1 update。

## 12. 等待用户审核的 Step 3 问题

步骤 4 开始前，请审核：

1. 是否同意把 Stage 2 `z_slat` conditional distribution 选为首个 stereo SSL 接入点，
   而把 Stage 1 pose/UV、VAE/decoder 和端到端联合优化分别后置？
2. 是否同意首 Gate 使用“frozen teacher pseudo latent + trainable Stage 2 student +
   frozen GS decoder/renderer + right observation loss”，并把只有 teacher anchor、
   `lambda_s=0` 的行为作 matched control？
3. 是否同意首 Gate 使用两个冻结 predicted poses，将已标定 rig relation 先作
   evaluation guard；待 canonical-unit baseline/crop 合同核验后，再用单左目 pose +
   fixed rig transform 做必须的复现实验？
4. 是否同意先做单向 G1-LR，然后做完全 matched 的 G1-RL，两者各自成立
   后才组合对称 mutual-supervision loss？
5. 是否同意只有同时通过 mechanism pass 和 representation pass 才宣称表示改善，
   其中 held-out camera LPIPS 为建议 primary，cross-view persistence 为必须 guard？

用户确认后，Step 4 将从已有 CUPID baseline draw.io 母图增量添加：冻结 teacher、
左右双目输入、两个冻结 pose、teacher pseudo latent、Stage 2 student、共用冻结 GS
decoder/renderer、右目 observation loss 与只回传到 Stage 2 的 gradient arrow。
