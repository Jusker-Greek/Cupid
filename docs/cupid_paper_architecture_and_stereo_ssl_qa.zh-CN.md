# CUPID 论文架构与双目自监督问答整理

状态：`RESEARCH SUMMARY / DESIGN-ONLY STEREO EXTENSION / NO NEW CUPID RESULT`

更新时间：2026-09-14

本文将已经完成的 13 个论文/架构问答整理成一份可供师兄、老师审核的技术记录。目的
不是把讨论内容写成已经完成的科学结果，而是明确：我们从哪个 CUPID baseline 出发，
论文和代码实际做了什么，上一项目的双目自监督思想可以怎样迁移，以及当前 proposed
架构还缺什么证据。

## 0. 证据标签与来源

本文统一使用以下标签：

- `[论文事实]`：CUPID 原论文、Figure、章节、公式或附录明确写出的内容。
- `[代码事实]`：官方仓库和配置可以直接核对的实现行为。
- `[通用知识]`：Flow Matching、透视投影、PnP、双目几何等一般知识。
- `[架构推断]`：根据论文、代码和项目目标提出的解释或设计，不等于原论文方法。
- `[待验证]`：需要实现、GPU smoke、正式训练或独立评估后才能下结论的内容。

主要来源：

1. CUPID 原论文：Huang et al., *CUPID: Generative 3D Reconstruction via Joint Object
   and Pose Modeling*, arXiv:2510.20776v2。重点是 Figure 3（PDF p.4）、§3.1--§3.3
   （PDF pp.4--5）、component-aligned scene reconstruction（PDF p.6）和 Appendix A.1
   （PDF p.13）。
2. 官方代码仓库：`github.com/cupid3d/Cupid`，本次审计的 `origin/main` 为
   `10af9b2`；本地协调分支为 `71743cc`。
3. 上一项目双目材料：
   `/Users/ruikegu/.codex/worktrees/metric-scale-controller-cleanup/xfactor_reproduce_overfit/docs/dual_input_dual_output_stereo_xfactor_project_brief.md`、
   `docs/overleaf/stereo_ssl_setting_and_progress/sections/01_setting.tex`、
   `02_strict_self_consistency_losses.tex`，以及用户确认的实时 Overleaf
   [Learning 4D World Representations and Distributions from Stereo Sequences](https://www.overleaf.com/project/6a3839d9359f19a962ba12b1)。
4. 项目内协调与设计记录：
   - `docs/cupid_stereo_ssl_revision_task_split.zh-CN.md`
   - `/Users/ruikegu/.codex/worktrees/c27f/Cupid/docs/CUPID_STEREO_SSL_RESEARCH_CORE.md`
   - `/Users/ruikegu/.codex/worktrees/c27f/Cupid/docs/CUPID_STEREO_INSERTION_SPEC_V1.md`

## 1. 一句话结论

`[论文事实][代码事实]` CUPID 不是“两个 Flow Matching 组成的 autoencoder”。准确说法是：

> CUPID 是一个两阶段、条件化的 Flow Matching 生成系统。第一阶段在 canonical
> object frame 中生成粗结构和 3D--2D 对应关系，再由 DLT/PnP 恢复相机；第二阶段在
> 结构和姿态对齐的图像条件下生成细粒度 geometry/appearance structured latent，最后
> 由 Gaussian、Mesh 或 radiance-field decoder 导出 3D 表示。

`[论文事实]` 论文中的 encoder \(\phi\) 是把 3D object 与 pose 编码为可解码表示的
3D/VAE encoder，不是 Stage 1 Flow Model 的 image encoder，也不是把两个 Flow Model
拼成互逆的 encoder--decoder。

`[架构推断]` 向老师解释时可以使用“Flow Matching 生成器 + 3D 表示 codec”的类比，
但不要说“两个 Flow Matching 本身是 autoencoder”。

## 2. CUPID 的真实宏观数据流

```text
single image
  -> preprocessing / foreground crop
  -> frozen DINOv2 + raw visual condition
  -> Stage 1 conditional Flow Matching
  -> z_s = coarse structure/UV latent
  -> occupancy + UV decoders
  -> canonical occupancy + 3D-to-2D UV correspondence
  -> DLT/PnP
  -> camera intrinsics/extrinsics
  -> pose-aligned voxel features
  -> Stage 2 conditional Flow Matching
  -> z_slat = sparse fine geometry/appearance latent
  -> Gaussian / Mesh / Radiance-Field decoder
  -> 3D outputs and optional renders
```

`[代码事实]` 关键 pipeline 锚点：

- `cupid/pipelines/processing.py:87-139`：DINOv2 图像编码与 raw visual tensor。
- `cupid/pipelines/processing.py:143-178`：从 UV sparse tensor 解码 camera pose。
- `cupid/pipelines/pipeline.py:143-175`：`z_s` 解码为 occupancy/UV，并将 `z_slat`
  解码为多种输出。
- `cupid/pipelines/pipeline.py:217-239`：根据 pose 将 sparse coordinates 投影到图像。
- `cupid/pipelines/pipeline.py:266`：完整 `run()` 使用 `@torch.no_grad()`。
- `cupid/pipelines/pipeline.py:301-326`：Stage 1、pose、Stage 2、输出 decoder 的顺序。

### 2.1 Stage 1：粗结构与姿态桥接

`[论文事实]` Figure 3 和 §3.3 称第一阶段为 occupancy and pose generation：先生成
occupancy cube 与 UV cube。

`[代码事实]` CUPID 的 Stage 1 最终配置
`configs/generation/suv_flow_img_dit_L_16l8_fp16.json` 使用：

- `SparseStructureFlowModel`；
- `resolution=16`；
- `in_channels=16`、`out_channels=16`；
- dense latent state，外部形状为 `[B,16,16,16,16]`；
- 16 个输出通道由 occupancy latent 和 UV-structure latent 两部分组成，通常各为
  8 个 channel。

Stage 1 的 Flow Model 不直接回归一个 6D pose token。它的输出经过 occupancy/UV decoder，
再把 canonical voxel center 与预测 UV 作为 3D--2D correspondence 输入 DLT/PnP。

### 2.2 Stage 2：细粒度几何与外观分布

`[论文事实]` §3.3 将第二阶段描述为 pose-aligned geometry and appearance generation，
在 active voxel 上生成每个 voxel 的 DINO/structured feature。

`[代码事实]` pose-conditioned 配置
`configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond.json` 使用：

- `ElasticVisualLatentConditioningSLatFlowModel`；
- `resolution=64`；
- 外部 noisy SLat state `in_channels=8`、`out_channels=8`；
- sparse active voxel 数量为可变的 `L`，不是固定 dense batch tensor；
- `cond_latent_channels=8`；
- `visual_feat_channels=[4,4,4,4]`，四层 visual feature 总计 16 个 channel；
- `model_channels=1024`、24 个 sparse transformer blocks。

因此“两个 Flow 结构相同，只是换了 encoder”不准确。它们都使用 timestep modulation、
cross-attention 和 velocity prediction，但 Stage 1 是 dense 的 joint structure/UV flow，
Stage 2 是 sparse 的 per-active-voxel SLat flow，并有额外的 pose-aligned local conditioning。

## 3. 两个 Flow Model 的逐项对照

| 项目 | Stage 1 | Stage 2 |
| --- | --- | --- |
| 目标分布 | `[论文事实]` coarse occupancy/UV latent | `[论文事实]` fine geometry/appearance SLat |
| state | `[代码事实]` dense `x_t`，16 channels，16^3 | `[代码事实]` sparse `x_t`，8 channels，active voxel 数量 L |
| condition | 图像 DINO 条件 | DINO global condition、UV 对齐 DINO latent、UV 对齐 raw visual features、结构/pose 产生的 UV |
| 直接输出 | flow velocity，采样后为 `z_s` | flow velocity，采样后为 `z_slat` |
| 后续解码 | occupancy decoder、UV decoder | Gaussian/Mesh/RF decoder |
| pose 关系 | UV correspondence 经 DLT/PnP 得到 pose | 消费 Stage 1 pose；不再有独立 pose head |
| 训练目标 | cached latent 上的 velocity MSE | cached SLat 上的 velocity MSE |
| 主要空间 | canonical coarse support + view-linked UV | canonical active voxels 上的 fine features |
| 训练参数 | flow denoiser；DINO 冻结 | flow denoiser（包括 visual conv）；DINO 和 SLat condition encoder 冻结 |

`[代码事实]` 两阶段都在 `cupid/trainers/flow_matching/sparse_flow_matching.py:77-117`
或其父类中按 `noise -> x_t -> denoiser -> target velocity -> MSE` 训练，但模型的 state
space、稀疏性、decoder 和 condition 不同。

## 4. Conditioner 到底是什么

`[论文事实]` Figure 3 中的 `Conditioner` 是一个概念框，不对应一个“把所有东西简单
拼接”的单独类。

`[代码事实]` Stage 2 的真实张量流如下：

```text
noisy SLat x_t                         [L, 8]
global DINO patch tokens               [B, 1374, 1024]
  -> remove special tokens             [B, 1369, 1024]
  -> reshape                            [B, 1024, 37, 37]
  -> bilinear sample at UV              [L, 1024]
  -> frozen SLatEncoder                 [L, 8]
raw visual_cond                        [B, 3, 256, 256]
  -> four Conv2d scales + UV sampling   [L, 4] x 4 = [L, 16]
concat                                  [L, 8 + 8 + 16] = [L, 32]
  -> sparse input projection
  -> 24 sparse transformer blocks
```

同时，每个 transformer block 还接收：

- `t_emb`：由 `TimestepEmbedder` 产生，进入 AdaLN 调制，不直接拼到 feature channel；
- 全局 DINO token sequence：作为 cross-attention context；
- sparse voxel token：当前 noisy state 与局部条件拼接后的 token。

代码锚点：`cupid/models/structured_latent_flow.py:349-397`、`:488-533`。

`[代码事实]` `uvs` 本身主要作为 `grid_sample` 的索引；occupancy cube 不直接作为每个
token 的 feature 拼接，而是决定 active sparse coordinates。PnP 得到的 \(K,R,t\) 也不
以一个 12D pose token 直接送入 Stage 2，而是用来重新投影 voxel 并生成 UV-aligned features。

因此可以向老师说：

> Conditioner 是“全局 DINO cross-attention + 基于 pose/UV 的局部特征采样 + frozen
> SLat latent condition + timestep modulation”的组合操作，而不是一个单一的 encoder。

## 5. Flow Matching：输入、输出和 latent 语义

### 5.1 通用 Flow Matching 规则

`[通用知识][代码事实]` 官方 trainer 对每个 clean latent `x_0`、随机噪声 \(\epsilon\) 和
时间 \(t\in[0,1]\) 构造：

\[
x_t=(1-t)x_0 + [\sigma_{min}+(1-\sigma_{min})t]\epsilon,
\]

\[
v^*(x_t,t)=(1-\sigma_{min})\epsilon-x_0.
\]

denoiser 接收 `x_t`、`t*1000` 和 condition，输出与 `x_t` 同形状的 velocity：

\[
\mathcal L_{FM}=\|v_\theta(x_t,t,c)-v^*(x_t,t)\|_2^2.
\]

代码：`cupid/trainers/flow_matching/flow_matching.py:61-106`、
`cupid/trainers/flow_matching/sparse_flow_matching.py:77-117`。

`[代码事实]` Euler sampler 通过 ODE 更新状态，并可从 velocity 代数恢复 clean latent：

\[
\hat x_0=(1-\sigma_{min})x_t-
[\sigma_{min}+(1-\sigma_{min})t]\hat v.
\]

代码：`cupid/pipelines/samplers/flow_euler.py:31-39`、`:66-99`。采样器和完整 pipeline
由 `@torch.no_grad()` 包围，因此不能直接拿推理 sampler 作为新的训练反传路径。

### 5.2 它是否就是 diffusion？

`[通用知识]` 可以说它与 diffusion 一样从噪声、时间条件和多步积分开始，但 CUPID 的
网络输出是 velocity \(dx_t/dt\)，不是 score、noise 或直接的 \(x_0\)。采样是 ODE/Euler，
不是标准 reverse-SDE 或 DDIM。

Flow Matching 的通用定义来自 Lipman et al., *Flow Matching for Generative Modeling*：
ODE（Eq.1）、FM objective（Eq.5）、Conditional FM（Eq.9）和线性 Gaussian/OT path
（Eq.20--22）。Rectified Flow 则提供线性路径与速度回归的常用实现形式。

### 5.3 “学习的分布”由谁定义

`[通用知识]` Flow Matching 只规定如何在给定数据分布与概率路径上学习速度场，不能
自己决定 latent 是“形状”还是“相机”。

`[论文事实][代码事实]` CUPID 的语义由以下链条定义：

```text
3D asset / rendered view
  -> occupancy / UV / DINO-per-voxel data
  -> VAE encoder and decoder define latent vocabulary
  -> cached normalized x_0
  -> conditional Flow Matching learns p(z | image, structure, pose-aligned condition)
  -> decoder maps latent to occupancy, UV, Gaussian, Mesh or RF
```

因此不同任务中“denoise 后 latent 的含义不同”的根本来源是 target representation 和
decoder 不同，而不是 Flow Matching 算法本身改变了语义。

## 6. 三层表示：不要把 latent 简化成“一个 pose、一个 shape”

### 6.1 `z_structure` / Occupancy

`[论文事实]` Occupancy cube 表示 canonical 3D 网格中 active/inactive voxel support，
不是完整物体形状 latent，也不是 pose latent。

`[代码事实]` `cupid/datasets/sparse_structure.py:39-45` 从 voxel PLY 构造：

```text
position in canonical cube
  -> coords = ((position + 0.5) * R).int()
  -> ss shape [1, R, R, R], dtype int
  -> ss[..., coord_x, coord_y, coord_z] = 1
```

训练数据通常为 `R=64` 的 binary occupancy；Stage 1 VAE latent 再压缩到 16^3、8-channel
结构 latent。

`[代码事实]` canonical voxel center 常写成：

\[
x_{ijk}=((i+0.5)/R-0.5,\ (j+0.5)/R-0.5,\ (k+0.5)/R-0.5).
\]

occupancy 的值由物体几何/support 决定，不由光照决定；单图预测时图像只提供推断条件，
并不改变 occupancy 的目标定义。

### 6.2 `z_uv` / UV Cube

`[论文事实]` UV cube 是 canonical voxel 到输入图像的 3D--2D correspondence，不是
texture UV、RGB 或深度图。对每个 canonical point \(x_i\)，保存归一化图像坐标
\(u_i=(u_i,v_i)\)。

`[代码事实]` `cupid/datasets/sparse_uv_structure.py:63-81` 对整个网格做投影：

\[
\tilde u_i \sim K[R|t]\,[x_i,1]^T,
\qquad u_i=\operatorname{normalize}(\tilde u_i)
\]

得到 `uv_volume` shape `[2,R,R,R]`，并 clamp 到 `[0,1]`；另有 `ssuv` shape
`[1,R,R,R]` 作为有效 support。UV VAE 配置的三路输出是 support/UV channels（support
或 `ssuv`、`u`、`v`），不是三个姿态分量。

UV 的数值主要由 canonical geometry、camera intrinsics/extrinsics 和 crop/resize 后的
图像坐标共同决定，不由光照决定。图像外观只影响模型如何从单图估计它。

### 6.3 `z_slat` / Structured Latent

`[论文事实][代码事实]` structured latent 是 sparse tensor：

```text
z_slat = {(x_i, f_i)}_{i=1}^L
x_i: active voxel coordinate
f_i: 8-channel learned feature
```

`x_i` 是显式 canonical coordinate；`f_i` 是分布在多个 channel 和空间位置中的神经
特征。没有证据表明某个 channel 固定等于“旋转”“颜色”“深度”或“pose”。

`[代码事实]` Stage 2 data/config 中对 cached SLat 做 `(feats-mean)/std` normalization；
mean/std 在 `configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond.json` 中
给出。`z_slat` 的 target 来自预训练 SLat encoder/cached latent，不是当前 Flow
trainer 现场从 Gaussian 或 Mesh 反解出来的。

更准确的口径是：

> `z_structure` 表示粗空间支撑；`z_uv` 表示 view-linked 3D--2D correspondence；
> `z_slat` 表示 canonical active voxels 上的细粒度 geometry/appearance neural feature。
> pose 主要由 UV correspondence 经 DLT/PnP 得到，Gaussian/Mesh 语义来自 decoder。

## 7. PnP、相机矩阵与可逆关系

### 7.1 输入与输出

`[论文事实]` CUPID 将 pose 写成投影矩阵：

\[
P=K[R|t],
\]

并把 pose 重参数化为 canonical 3D voxel 与 image UV 的 dense correspondence。

`[代码事实]` `cupid/pipelines/processing.py:158-175` 对每个 UV sparse sample：

1. 将 sparse coordinate 变为 canonical voxel center；
2. 以 UV feature 作为 2D correspondence；
3. 默认调用 `calibrate_camera_dlt`；
4. 可选 `epnp` 分支调用 calibration helper；
5. 返回 3x3 intrinsic 与 4x4 extrinsic。

默认代码因此更准确地说是“未知/待估内参的 DLT calibration”，而不是只使用已知内参
的标准 EPNP。代码还要求至少有足够的非退化 correspondence（实现中少于 6 个点会失败）。

### 7.2 矩阵方向

`[代码事实]` renderer 使用 world/object-to-camera 的 extrinsics；数据中常见的 `c2w`
需要先转换为 renderer 所用的 world-to-camera。若用 `C_L,C_R` 表示 camera-to-world，
用 `E_L=C_L^{-1}, E_R=C_R^{-1}` 表示 world-to-camera，则相对变换必须显式写清方向：

\[
T_{R\leftarrow L}=C_R^{-1}C_L=E_RE_L^{-1},
\qquad E_R=T_{R\leftarrow L}E_L.
\]

不能仅凭“左右方向相同、只差一个 translation”就交换 pose；旋转、坐标原点、内参、
crop 和矩阵方向都必须一致。

### 7.3 哪些转换确定、哪些需要 learned decoder

| 转换 | 结论 |
| --- | --- |
| canonical coordinate + `K,R,t` -> UV | 确定性透视投影（代码随后可能 clamp） |
| UV correspondence -> `P` | 在 support 足够且非退化时由固定 DLT/PnP 求解；不是严格无损一一映射 |
| occupancy -> active coordinates | threshold/`argwhere` 后可直接取得，但对 logits 不可微 |
| UV latent -> UV cube | 需要 learned UV decoder |
| structure/UV latent -> SLat | 需要 learned Stage 2 Flow；带随机采样 |
| SLat -> Gaussian/Mesh/RF | 需要各自 learned decoder；通常不可逆 |
| Gaussian/Mesh -> pose | 不能直接由 CUPID 解析得到，仍需要 UV/image/额外配准 |

## 8. 坐标系、尺度和多视角共享

### 8.1 可以确认的性质

`[论文事实]` CUPID 使用 object-centric、view-agnostic 的 canonical representation，并
在该 frame 中生成 occupancy/UV；同一对象的不同 render view 可以引用相同 canonical
voxel coordinates，再由各自 camera 投影到不同图像。

`[代码事实]` voxelization 使用归一化 cube 坐标，相关可视化 AABB 为 `[-0.5,0.5]^3`；
不同输入 view 的 camera metadata 产生不同 UV，但不应改变同一 asset 的 canonical voxel
位置。

### 8.2 不能直接宣称的性质

以下说法没有足够证据，不能写进论文事实：

- 所有物体具有相同的真实世界物理尺寸；
- 所有物体共享严格一致的 front-facing orientation；
- structured latent 被一个显式 front-view loss 强制到“正面坐标系”；
- 代码中存在完整的 multi-view joint inference 或 identity-level contrastive loss；
- canonical cube 单位等于米，或 pose translation 已经是 metric scale。

`[架构推断]` 看起来一致的 orientation 可能来自数据艺术家约定、canonical voxelization、
预训练 decoder 和训练分布偏置共同作用，而不是一个单独的 canonicalizer。论文提到的
ground-plane/canonical 约定与代码中的 bbox-centered normalization 还需要逐项核对，
不能把二者自动视为同一个坐标定义。

## 9. 训练监督、decoder 与输出角色

### 9.1 训练阶段分层

| 阶段 | 主要输入 | 直接监督 | 训练/冻结关系 |
| --- | --- | --- | --- |
| Sparse structure VAE | binary occupancy | Dice + KL | VAE encoder/decoder 训练 |
| UV structure VAE | `ssuv` + UV volume | support Dice + masked UV L1 + KL | UV VAE 独立训练 |
| SLat Gaussian VAE | canonical sparse DINO features + render + camera | rendered L1 + SSIM + LPIPS + KL + Gaussian regularization | SLat encoder/GS decoder 独立训练 |
| SLat Mesh/RF decoder | SLat + mesh/geometry/render data | mask/depth/normal/color/geometry losses | 各 decoder 独立训练 |
| Stage 1 Flow | cached structure/UV latent + image condition | velocity MSE | 主要优化 Stage 1 denoiser |
| Stage 2 Flow | cached normalized SLat + image/UV/pose-aligned condition | velocity MSE | 主要优化 Stage 2 denoiser |

代码锚点：

- `cupid/trainers/flow_matching/flow_matching.py:141-178`：dense flow velocity MSE；
- `cupid/trainers/flow_matching/sparse_flow_matching.py:77-117`：sparse flow velocity MSE；
- `cupid/trainers/vae/structured_latent_vae_gaussian.py:137-199`：SLat -> Gaussian -> render -> image loss；
- `cupid/trainers/vae/structured_latent_vae_mesh_dec.py:227-280`：mesh geometry/readout losses；
- `cupid/models/structured_latent_vae/decoder_gs.py:67-123`：SLat 到 Gaussian 参数；
- `cupid/pipelines/pipeline.py:155-175`：Gaussian/Mesh/RF 输出选择。

### 9.2 Gaussian 与 Mesh 是什么

`[论文事实]` Appendix A.1 说明 structured latent 可以通过 SLat decoder 解码成高质量
triangle mesh 或 Gaussian splats。

`[代码事实]` 对主 Flow 来说，Gaussian/Mesh/RF 是 `z_slat` 的 readout/output，不是
Stage 1/Stage 2 的直接 target。它们在各自 VAE/decoder 预训练中可以作为渲染或几何
监督接口；这与主 Flow trainer 的 velocity MSE 必须分开描述。

所以当前论文/项目不应写成：

```text
Flow Model 直接预测 mesh/Gaussian，并用它们作为主 Flow 的 ground truth
```

而应写成：

```text
Flow Model 学习 cached latent 的 velocity distribution
latent decoder 将其转换为 Gaussian/Mesh/RF
decoder/render loss 主要属于表示 codec 训练或 proposed observation branch
```

### 9.3 Object (O) 与 camera pose \(\theta\) 到底由什么监督

这是最容易被“联合建模”这句话误导的地方。论文中的

\[
I=P(O,\theta),\qquad p(O,\theta\mid I_{\mathrm{cond}})
\]

是问题定义，不等于代码里有一个网络直接输出两个变量、再分别计算一个
`object loss` 和一个 `pose loss`。

| 量 | 训练时实际使用的 target | 是否直接回归 | 监督来源 |
| --- | --- | --- | --- |
| 物体粗结构 | canonical occupancy cube；由 3D asset 的 voxel PLY 构造 | 否；先编码为 structure latent，再由 Stage 1 Flow 生成 | 3D asset/occupancy 标签，属于数据监督 |
| 相机因素 | 与 canonical voxel 配对的 UV cube，`u_i=pi(P,x_i)` | 否；Stage 1 生成 UV latent，解码后用 DLT/PnP 求 `P=K[R|t]` | 渲染相机的 intrinsics/extrinsics 通过投影生成 UV target，属于间接 pose 监督 |
| 物体细节 | canonical active voxel 上的 DINOv2 聚合特征，经 SLat VAE 得到 cached `z_slat` | 否；Stage 2 生成 SLat latent，之后由 decoder 读出 Gaussian/Mesh | 3D asset、multi-view render 和预训练 SLat codec |
| 最终 Gaussian/Mesh | Stage 2 latent 的 decoder 输出 | 不是 Stage 1/2 Flow 的直接 target | decoder/VAE 阶段的渲染、几何、正则损失 |

`[论文事实]` 论文 §3.2--§3.3 明确把物体写成
`O={(x_i,f_i)}`，把 pose 重参数化成 `{(x_i,u_i)}`，并说明第一阶段生成 occupancy
cube 与 UV cube，第二阶段生成 active voxel 的 feature `f_i`。因此 pose 的“ground
truth”首先以 UV correspondence 形式进入训练，而不是以一个独立的 6D/12D pose
回归标签进入 Flow loss。

`[代码事实]` `cupid/datasets/sparse_structure.py:39-45` 从 canonical voxel PLY 构造
occupancy；`cupid/datasets/sparse_uv_structure.py:63-81` 使用 `extrinsics`、`intrinsics`
把 voxel center 投影成 UV volume；`cupid/datasets/sparse_structure_latent.py:168-173`
和 `cupid/datasets/sparse_uv_structure_latent.py:216-229` 读取 cached latent 作为
`x_0`。`cupid/pipelines/processing.py:158-175` 再把预测 UV 通过 DLT/EPnP 解成相机
pose。

`[论文事实][代码事实]` Flow 阶段的直接损失是 latent 上的 Conditional Flow Matching
velocity MSE：

\[
\mathcal L_{\mathrm{CFM}}
 =\left\|v_\phi(x_t,t,I_{\mathrm{cond}})-v^*(x_t,t)\right\|_2^2,
\qquad
v^*=(1-\sigma_{\min})\epsilon-x_0 .
\]

也就是说，`x_0` 是由 3D asset/camera pipeline 生成或缓存的 latent target；Gaussian、
Mesh 和显式 pose 矩阵不会在主 Flow trainer 中单独提供一个直接回归损失。

#### 哪些是预训练的，哪些需要重新训练

| 组件 | 原 CUPID 中的状态 | 是否在主 Flow 训练中更新 |
| --- | --- | --- |
| DINOv2 image encoder | 外部预训练视觉 encoder | 通常冻结；只提取 conditioning feature |
| occupancy VAE / decoder | 由 occupancy reconstruction + KL 训练好的 codec | 通常冻结；提供 structure latent 和解码 |
| UV VAE / decoder | 由 UV/support reconstruction + KL 训练好的 codec | 通常冻结；提供 pose latent 和 UV 解码 |
| SLat encoder/decoder | TRELLIS 风格的独立 3D latent codec，使用 render/geometry 等损失训练 | 通常冻结；提供 `z_slat` 与 Gaussian/Mesh readout |
| Stage 1 `G_S` | 以 TRELLIS checkpoint 初始化，再在 CUPID 数据上训练/微调 | 需要训练 |
| Stage 2 `G_L` | 以 TRELLIS checkpoint 初始化，再在 pose-aligned 条件上训练/微调 | 需要训练 |
| DLT/PnP | 确定性几何求解器 | 不训练 |

`[论文事实]` Appendix A.1 写明：数据来自约 260K 个 3D assets；每个 asset 通过
occupancy grid 和 structured latent 编码，并从随机视角渲染 conditioning images；模型
使用 TRELLIS 预训练权重初始化，随后分别训练 `G_S` 与 `G_L`。因此“已经有预训练模型，
所以两个量都不用训练”不准确：预训练模型提供表示 codec、DINO 特征和初始化权重，
但 CUPID 的两个 Flow denoiser 仍然要训练。

#### “有监督”还是“自监督”

- `[论文事实]` **原 CUPID 的主训练不是纯自监督。** 它依赖 3D asset、canonical voxel、
  渲染相机参数和 cached latent；更准确的说法是“3D-data-supervised / latent-supervised
  conditional generative training”。
- `[代码事实]` **Stage 1/Stage 2 的 Flow 训练**使用 `x_0` latent 与随机噪声构造 CFM
  target，再优化 velocity MSE；因此虽然损失形式不是 mesh loss，它仍然有来自 3D 数据
  pipeline 的 target，不应称为 stereo self-supervision。
- `[代码事实]` **VAE/decoder 训练**使用 occupancy、UV、渲染 RGB、mask/depth/normal 和
  geometry 等重建或正则信号，属于表示 codec 的有监督/重建训练。
- `[通用知识]` DINOv2 的预训练本身使用其作者定义的自监督视觉目标，但在 CUPID 中它是
  冻结的外部 feature extractor；不能因此把 CUPID 整体称为自监督。
- `[架构推断]` 我们的双目扩展才引入“新增样本不提供 mesh/Gaussian/depth label”的
  observation-level self-supervision：右目真实图像作为 target，已有 CUPID 3D prior、
  decoder 和相机关系作为固定条件。首个 Gate 计划只微调 Stage 2 denoiser；这属于
  “基于预训练 3D 先验的双目自监督增量训练”，不是从零 stereo-only 学习。

给老师的最短口径是：

> 原 CUPID 确实同时学习 object 和 camera 因素，但不是两个独立回归头。object 由
> occupancy/UV/SLat latent 表示，pose 由 UV correspondence 间接表示并通过 DLT/PnP
> 求出。Flow 的直接监督是这些由 3D asset 和渲染相机产生的 cached latent 的 velocity
> MSE；DINO、VAE、decoder 是预训练或独立训练的组件，真正需要在 CUPID 阶段重新训练的
> 是 Stage 1 和 Stage 2 两个 Flow denoiser。双目方案新增的才是右目 observation-level
> self-supervision，首 Gate 先只更新 Stage 2。

## 10. 上一项目的双目 SSL 思想如何映射

`[来源事实]` 用户确认的实时 Overleaf 和旧 stereo 文档共同支持以下层次区分：

1. stereo 是同一隐藏场景在两个已标定相机下的耦合观测，不是 representation 本身；
2. `prediction vs observation` 可以用真实右图作为 target，不需要新的 object 3D label；
3. `prediction vs prediction` 可以比较不同 view/window/path 的独立预测，但必须避免
   两侧由同一个中间量代数复制；
4. reconstruction/NVS 是把隐藏表示投影回 observation space 的 consistency test，
   不是 representation quality 的充分定义；
5. stereo identifiability、metric-scale baseline、continual non-forgetting 是三个
   不同命题，不能一次合并成一个 claim。

第一阶段建议只研究 static object：

```text
object representation O  ~=  CUPID z_structure / z_uv / z_slat
camera factor C          ~=  CUPID UV -> DLT/PnP path
decoder/readout          ~=  frozen SLat Gaussian decoder + renderer
stereo observation       ~=  synchronized I_L, I_R + calibrated rig relation
```

动态 motion `M`、object relation `R`、Bayesian scene posterior 和 continual learning
暂不属于 CUPID 首个可验证 claim。

## 11. CUPID 双目扩展：候选方案与当前推荐

### 11.1 三种架构候选

| 方案 | 结构 | 优点 | 主要风险 | 当前判断 |
| --- | --- | --- | --- | --- |
| A. 两套完全独立 CUPID | 左右各自 Stage 1/2/decoder | 直观，便于分别预测 | 表示不共享，容易各自记忆图像；参数和归因复杂 | 不推荐首 Gate |
| B. Siamese/paired CUPID | 两路共享权重，分别处理 `I_L/I_R`，再对齐 common latent | 真正利用双目 paired representation | 需要定义 latent matching、pose provider、stop-gradient 和双路 loss | 后续 successor |
| C. 单路 CUPID + 右目 target branch | 保持左目 conditioning，在右相机下 render，与真实 `I_R` 比较 | 变量最少；直接检验跨视角解释；推理 API 不变 | 可能只学到 target-view shortcut；需要 held-out/cross-decoder guard | 首个最小 Gate |

### 11.2 当前 primary design（仍是 design-only）

`[架构推断][待验证]` 核心文档将首个 research Gate 收敛为：

```text
synchronized (I_L, I_R)
  -> frozen CUPID teacher on I_L
  -> pseudo structured latent z_teacher
  -> trainable Stage 2 student predicts velocity / clean z_student
  -> frozen Gaussian decoder
  -> fixed right-camera render
  -> right-view L1 + LPIPS
  -> gradient only to Stage 2 student
```

形式化为：

\[
\tilde z_L=\operatorname{stopgrad}(\operatorname{Teacher}(I_L).z_{slat}),
\]

\[
\hat z_L=\operatorname{v\_to\_x0}(x_t,t,v_\theta),
\qquad
\hat I_R=\operatorname{Render}(D_{GS}(\hat z_L),\operatorname{stopgrad}(C_R)),
\]

\[
\mathcal L_{total}=\lambda_a\mathcal L_{anchor}+
\lambda_s[ L_1(\hat I_R,I_R)+\lambda_p\operatorname{LPIPS}(\hat I_R,I_R)].
\]

这里的 teacher latent 是已训练 CUPID prior 对新图像的伪解释，不是真实 3D ground truth；
新的科学变量是右目 observation term。matched control 关闭 `lambda_s`，保持 teacher、
噪声、数据、更新步数和 anchor 完全相同。

### 11.3 历史 V1 insertion spec 的定位

`[项目事实]` `/Users/ruikegu/.codex/worktrees/c27f/Cupid/docs/CUPID_STEREO_INSERTION_SPEC_V1.md`
中较早的 `CUPID-SAME-TIME-RIGHT-RECON-V1` 仍保留为 supervised-assist matched control：

```text
Stage 2 velocity
  -> one-step clean latent estimate
  -> frozen Gaussian decoder
  -> fixed right-camera render
  -> right-view L1 + LPIPS
  -> Stage 2 denoiser
```

但该版本仍使用 cached true `x_0=z_slat` 和原 flow anchor，不能单独证明“新增双目数据
不需要 3D latent label”。因此它不能冒充当前 primary SSL 方法，也不能被写成已实现或
已有收益。

### 11.4 训练/推理边界

首 Gate 的冻结边界：

- 冻结 Stage 1、UV/occupancy decoder、DINOv2、SLat encoder、Gaussian decoder 和 renderer 参数；
- 右图只作为同步 target，不进入 DINO、Stage 1 或 Stage 2 visual conditioning；
- 右目相机由两个冻结 predicted poses 或后续 rig-derived pose 提供，首 Gate 不更新 pose；
- 推理仍保持 left-only CUPID，右图、rig transform 和 right-camera render 是 training-only；
- 不加入 `B=0.25 m` loss、feature consistency、learned relation head、temporal quartet、
  confidence mask 或新的 pose head。

可允许的梯度路径：

```text
L_right
  -> right render
  -> frozen Gaussian decoder operations
  -> clean z_slat estimate
  -> Stage 2 denoiser
```

`[待验证]` frozen decoder 的参数可以没有梯度，但其运算必须保持对 latent 输入可微；
Gaussian rasterizer 的完整 backward、显存和 CFG mask glue 需要远端 GPU smoke 验证。

## 12. 用户提出的两个收益猜想审计

### 12.1 “双目互相监督可以代替显式 3D supervision”

结论：**部分成立，但不能按强版本表述。**

- `[架构推断]` 对已有 CUPID prior 的增量微调，右目 observation 可以替代“新增样本的
  object 3DGS/mesh/depth/cached latent label”，因为 target 是原始同步右图和已知相机关系。
- `[通用知识]` 这不等于从零训练时完全不需要 3D 先验。首 Gate 仍依赖 pretrained CUPID
  teacher、VAE vocabulary、decoder 和 canonical coordinate convention。
- `[通用知识]` photometric ambiguity、遮挡、反射、无纹理区域、背景、错误 pose/crop、
  texture-copy 和 geometry/pose compensation 都可能产生退化解。
- `[待验证]` 只有 held-out view、cross-view persistence、cross-decoder transfer 等
  representation probes 同时改善，才能说“representation 更好”；训练右图 PSNR/LPIPS
  变好只能说 observation branch 在工作。

因此推荐口径是：

> 双目观测可以减少后续新增数据对显式 3D 标签的依赖，并提供额外的跨视角约束；它不
> 自动保证正确几何，也不等于已经实现 stereo-only 3D learning。

### 12.2 “固定双目间距提供跨物体大小统一尺度先验”

结论：**固定 baseline 提供 metric-depth 可观测性，但不直接等于 object-size prior。**

`[通用知识]` 在理想校正双目中：

\[
d=\frac{fB}{Z},
\qquad Z=\frac{fB}{d},
\]

其中 `B` 是相机中心间距，`f` 是对应内参焦距，`d` 是 disparity。要成立，必须有
可靠的左右内参、外参、时间同步、crop/resize 后的 calibration 更新和可匹配的像素。

不能直接推出：

- 小物体和大物体会自动被映射到可比较的 canonical physical size；
- canonical cube 的尺度就是米；
- 固定 `B=0.25 m` 可以解决所有 object distance/size ambiguity；
- crop 后仍可复用未经更新的 `K`。

远物体/小目标的 disparity 可能接近像素噪声，近物体/大目标可能有遮挡和匹配困难；
不同焦距、图像裁剪和物体 canonical normalization 还会改变“图上大小”和真实尺度的
关系。因此 `B=0.25 m` 必须作为独立 successor Gate，而不是首个 stereo observation
Gate 的同时变量。

## 13. 最小实验与证据门

推荐逐级执行，而不是一次复制两套完整 autoencoder：

| Gate | 唯一变化 | 主要问题 |
| --- | --- | --- |
| G0 matched control | teacher/anchor 保持不变，`lambda_stereo=0` | 建立无右目 loss 的同条件基线 |
| G1-LR | 只加 `I_L -> z_L -> fixed C_R -> render -> I_R` | 右目 observation 是否纠正 Stage 2 distribution |
| G1-RL | 完全交换左右路由 | 排除单目画质、遮挡和 pose bias |
| G2-symmetric | 组合已分别通过的 LR 与 RL | 才称为真正双向 mutual supervision |
| G3-pose | 冻结 Stage 2，只更新 Stage 1 UV/pose，并加 rig guard | 单独测试 camera/view factorization |
| G4-joint | G2 与 G3 各自成立后解冻 Stage 1+2 | 测试联合优化，检查相互补偿 |
| G5-metric | 独立加入 baseline normalization / metric-depth probes | 测试尺度命题，不与 G1 混合 |

每个 Gate 必须同时有两类通过条件：

1. `Mechanism pass`：target-view loss 改善、梯度非零有限、没有恒定 render、没有路由
   错误，原 CUPID 单目 guard 不显著回退。
2. `Representation pass`：held-out camera NVS、cross-view persistence、pose/rig guard、
   cross-decoder transfer 或 frozen downstream probe 中至少一个主 probe 改善，且没有
   关键 probe 退化。

建议 primary probe 为 held-out camera LPIPS；cross-view persistence 为必须 guard。只有
   mechanism pass 而没有 representation pass 时，结论只能写“右目重建分支有效”。

## 14. 面向老师的简洁讲解版本

### 14.1 三层版本

1. **粗空间与姿态层**：CUPID 生成 canonical occupancy 和 UV correspondence。
2. **姿态求解层**：利用 3D--2D correspondence 通过 DLT/PnP 恢复相机投影矩阵。
3. **细节生成层**：将 active voxel 的图像特征按 pose 对齐，生成 SLat，再由 Gaussian、
   Mesh 或 RF decoder 输出 3D 表示。

### 14.2 我们的改动应如何说

> 我们从 CUPID 的两阶段 conditional Flow Matching baseline 出发，把上一项目的
> “同步双目观测可以作为第二个几何约束”迁移到 Stage 2 表示分布。首个最小方案不复制
> 两套独立 autoencoder，而是保留原左目生成链，在固定右目相机下渲染同一个预测表示，
> 用真实右图构造训练期 L1/LPIPS observation loss，并把梯度限制在 Stage 2 denoiser。
> 当前这仍是 design-only；需要 held-out view 和表示级 probe 通过后，才能声称表示改善。

### 14.3 不要使用的说法

- “两个 Flow Model 组成一个 autoencoder”；
- “第一个 latent 就是 pose，第二个 latent 就是 shape”；
- “Gaussian/Mesh 是两个 Flow Model 直接预测的 ground truth”；
- “固定 0.25 m baseline 自动统一所有物体大小”；
- “右目重建变好就证明 3D representation 变好了”；
- “论文原方法已经包含我们 proposed 的右目 L1+LPIPS 分支”。

## 15. 13 个问答任务与本文件章节映射

| 对话 | 问题 | 本文件位置 |
| --- | --- | --- |
| 1 | 宏观架构、autoencoder 类比、Gaussian/Mesh 角色 | §1--§3、§9 |
| 2 | Stage 1/Stage 2 结构、维度、condition、denoiser | §3 |
| 3 | Conditioner 的真实输入、融合和 shape | §4 |
| 4 | Flow Matching 的 noisy state、velocity、采样、latent 语义 | §5 |
| 5 | ground truth、decoder 训练和主 Flow 监督 | §9 |
| 6 | Flow Matching 分布语义由谁定义 | §5.3 |
| 7 | Occupancy Cube | §6.1 |
| 8 | UV Cube | §6.2 |
| 9 | Structured Latent | §6.3 |
| 10 | PnP、pose 矩阵和可逆转换 | §7 |
| 11 | canonical frame、尺度、多视角共享 | §8 |
| 12 | 双目双路架构、交叉监督和两项收益 | §10--§13 |
| 13 | Object 与 pose 的 ground truth、预训练、重新训练和监督类型 | §9.3 |

## 16. 当前状态、图稿和责任边界

`[项目事实]` 当前图稿是候选图，不是用户批准的最终图：

- baseline mother：`/Users/ruikegu/.codex/worktrees/5986/Cupid/outputs/figures/p02_cupid_repro_paper_pipeline_v02_candidate.drawio`
- integration candidate：`/Users/ruikegu/.codex/worktrees/5986/Cupid/outputs/figures/p02_cupid_same_time_right_recon_v03_candidate.drawio`
- storyboard：`/Users/ruikegu/.codex/worktrees/c27f/Cupid/docs/cupid_stereo_ssl_slides_storyboard.md`
- integration audit：`/Users/ruikegu/.codex/worktrees/5986/Cupid/outputs/figures/p02_cupid_same_time_right_recon_v03_candidate_audit.md`

责任链已经明确：

1. 论文/代码审计负责确认 baseline 事实；
2. 上一项目文档负责确认 stereo SSL 的来源、层次和已有结果边界；
3. architecture owner 负责决定接入位置、loss 和 gradient ownership；
4. Draw.io owner 只实现已确认的局部 delta，不自行改变科研语义；
5. 用户/老师负责最终科学 contract、术语和图稿 approval。

当前没有 CUPID stereo SSL 正向训练结果。smoke、preflight、Slurm、readiness 和复现
故障不属于本文件的科学结果证据。

## 17. 最终结论与待确认项

### 已经可以确认

- CUPID 是两阶段 conditional Flow Matching + 多个 3D representation codec；不是两个 Flow 的 autoencoder。
- Stage 1 主要产生 coarse structure/UV 并通过 DLT/PnP 得到 pose；Stage 2 产生 sparse fine SLat。
- Conditioner 是 global DINO attention、UV-aligned latent/RGB features 和 timestep modulation 的组合。
- 主 Flow trainer 的直接监督是 cached latent 上的 velocity MSE；Gaussian/Mesh 是 decoder readout。
- canonical voxel frame 与 view-dependent UV/pose 必须分开；真实 metric scale 和 front-view gauge 未被充分证明。
- 双目可以减少新增 3D label 依赖，但不能自动保证正确 geometry，也不能自动统一 object size。

### 必须在实现/实验前确认

- 首 Gate 使用 pseudo-latent primary design，还是先跑 true-`x_0` supervised-assist control；
- 右目 pose 先用两个冻结 predicted poses，还是直接用经验证的 fixed rig transform；
- crop/resize 后左右内参和 stereo transform 的可回放数据合同；
- Gaussian decoder/rasterizer 的实际可微 backward 和显存预算；
- representation primary probe、回退阈值和 distribution diversity guard；
- 何时、以何种独立 Gate 引入 `B=0.25 m` metric-scale 变量。

## 18. 反思

- 当前不确定性：公开论文对 released checkpoint 的所有 crop-latent 细节、pose metric 定义和多视角 runtime API 并不完整；需要继续以代码和可复现实验核对。
- 可能的盲点：右目重建、pose 误差或 3DGS 视觉质量改善，都可能来自 decoder/pose compensation，而不是 shared representation 变好。
- 最可能的失败模式：一次同时加入双路输入、pose cycle、feature consistency、baseline loss 和 temporal loss，导致即使指标变化也无法归因；首 Gate 必须保持单一变量。
