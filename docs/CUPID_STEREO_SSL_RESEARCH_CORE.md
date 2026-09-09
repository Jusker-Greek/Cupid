# CUPID 双目自监督表征学习核心文档

状态：`STEP 1 COMPLETE / USER REVIEW REQUIRED / STEPS 2-4 BLOCKED`

更新时间：2026-09-09

本文档是 CUPID 双目自监督新项目的核心研究记录。当前只完成步骤 1：厘清
stereo、self-supervised learning（SSL）与 representation/distribution learning 的
关系，并判断哪些旧设计可以迁移到 CUPID。步骤 2、3、4 在用户审核步骤 1 前不展开，
避免过早冻结模型接入点或 pipeline 图。

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
| 1 | 读取旧 stereo SSL 文档与实时 Overleaf；定义 stereo、SSL、representation learning、学习条件、已有设计和已有成果；区分理论、模型与 CUPID 可迁移内容 | `COMPLETE / REVIEW REQUIRED` | 用户确认概念、证据边界与第一阶段研究范围 |
| 2 | 拆解 CUPID 当前学习过程：最小模块、每部分输入、输出、预测对象、监督、训练参数、冻结参数和可微路径 | `BLOCKED_BY_STEP_1_REVIEW` | 用户确认 CUPID baseline 图和模块表 |
| 3 | 比较多个 stereo SSL 接入点；分别论证 pose、Stage 1 structure、Stage 2 distribution、3D decoder/render 路径；确定首个最小 Gate | `BLOCKED_BY_STEP_2_REVIEW` | 用户批准唯一首选接入点与 matched controls |
| 4 | 在审核过的 draw.io 母图上增量添加 stereo SSL branch，输出 editable draw.io、PNG 和图例 | `BLOCKED_BY_STEP_3_REVIEW` | 用户审核最终 pipeline 图 |

## 1. 证据级别与来源

本文使用以下标签，防止把理论、设计和结果混为一谈：

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

`THEORY`：NVS 或 image reconstruction 是把隐藏表示变成可比较观测的 measurement
likelihood / consistency test。它回答“这个 3D explanation 能否解释另一只眼看到的
图像”，但低 pixel loss 本身不自动证明表示具有正确 3D 结构。模型仍可能依赖 texture
copy、view memorization、错误 pose 与错误 geometry 的互相补偿，或 renderer capacity
来降低误差。

因此 CUPID 后续不能只报告 PSNR/L1/LPIPS。至少还要有 held-out cross-view、pose/rig
consistency、geometry 或 distribution-level 指标，具体指标在步骤 3 冻结。

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

> 我们把同步双目看作同一隐藏 3D object state 在固定几何关系下的两个观测，而不是
> 两个独立训练样本。CUPID 先由已有有监督训练获得强 3D 生成先验，再通过可微 3DGS
> 新视角渲染，将无 3D 标签的左右图转化为 observation-consistency likelihood。训练
> 目标不是把右图像素记住，而是让同一个 object representation 与 camera factors
> 同时解释两个视角，从而排除只与单目相容的 3D modes，并微调 CUPID 的 object
> representation / generation distribution。

### 6.2 当前最重要的边界

- reconstruction/NVS 是 representation 的可反证测试，不是 representation 本身。
- stereo 能增加 identifiability，但“增加了观测”不等于“神经分布一定学得更好”。
- CUPID 的 static object factor `O`、camera factor `C`、3D Gaussian decoder/renderer
  与这套理论高度对应；动态 `M`、关系 `R`、continual learning 暂不对应。
- 当前没有 CUPID stereo SSL 正向结果，只有设计可行性和旧项目的混合证据。
- 首个实验必须保持单变量，不能同时加入 stereo input、数值 baseline、两个新 pose
  head、cycle loss、feature loss 与 temporal 4D loss。

## 7. 等待用户审核的问题

步骤 2 开始前，请审核以下三项：

1. 是否确认实时 Overleaf
   `Learning 4D World Representations and Distributions from Stereo Sequences`
   就是本轮应作为核心理论 authority 的文档？
2. 是否同意把“reconstruction 是 consistency test，不是 3D representation 的最终
   定义”作为 CUPID 新项目的核心表述？
3. 是否同意第一阶段只研究 `static object O + camera C + CUPID 3DGS renderer`，暂不
   引入 motion `M`、relation `R` 和 continual-learning/non-forgetting claim？

用户批准后，下一步只执行步骤 2：逐模块拆解 CUPID baseline，并给出每个模块的输入、
输出、学习条件、监督、trainable/frozen 状态和最小可拆分 pipeline 图。
