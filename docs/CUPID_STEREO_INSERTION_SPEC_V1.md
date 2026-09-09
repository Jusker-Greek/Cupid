# CUPID Stereo Insertion Specification V1

状态：`DESIGN ONLY / S01 UNVERIFIED / NOT IMPLEMENTED`

本文冻结 CUPID 首个双目自监督最小 Gate 的架构合同。它只定义训练期右目
重建路径，不声称代码已实现、训练已运行、指标已改善或物理尺度已经被学习。

## 1. Gate 定义

- Gate 名称：`CUPID-SAME-TIME-RIGHT-RECON-V1`。
- 机制假设：如果同一 CUPID Stage 2 生成分布产生的 3D 表示能够在已知右目
  相机下重建同步右图，那么右目观测可以约束该分布的跨视角可渲染性。
- 唯一新增变量：在现有 Stage 2 flow-matching loss 之外，增加一条
  `predicted clean structured latent -> frozen Gaussian decoder -> right-camera Render -> right-image reconstruction loss`
  的训练期分支。
- 反证条件：右目重建不能优于 matched control、生成退化、左目/原指标回退、
  梯度没有到达 Stage 2 denoiser，或只有依赖额外 learned head / feature loss / 数值
  baseline loss 才能工作。
- 科学边界：这是 same-time `L_t -> R_t` reconstruction，不是历史四视图
  `[L_t0, R_t0] -> [L_t1, R_t1]`，也不是 metric-scale `B=0.25 m` Gate。

## 2. Baseline 不变项

以下内容在 V1 中全部冻结：

1. CUPID 两阶段语义不变：Stage 1 仍预测 sparse structure / UV 并解码左目相机，
   Stage 2 仍在该结构和左目 pose-aligned conditioning 上生成 structured latent。
2. 左目仍是唯一 conditioning image；右图只作为训练 target，不进入 DINOv2、
   visual conditioning、Stage 1 或 classifier-free guidance conditioning。
3. `ElasticVisualLatentConditioningSLatFlowModel` 的网络拓扑、输入通道、cross
   attention、visual feature sampling、初始化和 checkpoint 不变。
4. 原 Stage 2 flow-matching MSE 保留，采样时间分布、`sigma_min`、噪声定义、
   optimizer、scheduler、EMA、batch、seed policy 和日志格式不变。
5. sparse coordinates / layout、structured-latent normalization、Gaussian decoder
   结构与权重、Gaussian renderer、渲染背景语义不变。
6. dataset split、实例集合和 object identity 不变；V1 只为同一实例补充同步、已
   标定的右目观测及固定相机 metadata。
7. 推理 API、采样器、采样步数、Stage 1 pose 输出和 Gaussian/Mesh/RF 输出不变。
8. 不新增 learned relation head、right-image encoder、pose head、confidence mask、
   disparity/depth head、feature-consistency loss 或 numeric baseline loss。

V1 允许新增的代码对象只有训练 glue、paired-data carrier、loss 配置和日志项；
这些都属于同一条 right-view reconstruction branch，不是新的 learned module。

## 3. Source / Sink 合同

### 3.1 Source

每个训练样本必须提供以下数据；字段名是 V1 的 proposed data contract，当前代码
尚未实现：

| Proposed field | 含义 | 梯度 |
| --- | --- | --- |
| `cond` | 左图 `I_L`，沿原 CUPID conditioning 路径使用 | image encoder 固定；不对图像求梯度 |
| `x_0` | 原 CUPID normalized structured latent 与 sparse support | data target，无梯度 |
| `uvs` | 由左目 `E_L, K_L` 投影得到的 pose-aligned sparse UV | fixed geometry，无梯度 |
| `right_image` | 同一实例、同一 timestamp 的右图 `I_R` | supervision target，无梯度 |
| `right_alpha` | 右图 deterministic alpha / foreground validity | fixed target metadata，无梯度 |
| `extrinsics`, `intrinsics` | 左目 world-to-camera `E_L` 与 `K_L` | fixed camera metadata，无梯度 |
| `stereo_transform_rl` | 已标定的 `T_{R<-L}` | fixed rig metadata，无梯度 |
| `right_intrinsics` | 右目 `K_R`，含右图 crop 后的精确更新 | fixed camera metadata，无梯度 |
| `stereo_valid` | 同步、标定、有限值且配对正确的 instance-level mask | fixed boolean，无梯度 |
| `cfg_conditioned` | 复用既有 CFG dropout 后，该样本是否仍保留左图条件 | pre-existing routing mask，无梯度 |

不得用随机的 `renders_cond` 视角冒充 stereo pair。配对器必须验证 same object、
same timestamp、left/right ordering、有限相机矩阵和有效 baseline；错误路由或非有限
值是 hard failure，不能通过 mask 静默丢弃。

### 3.2 Sink

唯一 sink 是 Stage 2 trainer 的总 loss：

```text
L_total = L_flow_matching + lambda_right * L_right_reconstruction
```

`L_right_reconstruction` 只更新现有 Stage 2 denoiser 参数。它不更新 Stage 1、
Gaussian decoder、renderer、camera metadata、右图 target 或 validity mask。

## 4. 固定几何与相机约定

CUPID dataset/renderer 中的 `extrinsics` 是 world-to-camera。记 `C_L, C_R` 为
camera-to-world，`E_L=C_L^-1`、`E_R=C_R^-1`，沿用 authority 中的方向定义：

```text
T_{R<-L} = C_R^-1 C_L = E_R E_L^-1
E_R       = T_{R<-L} E_L
```

因此 V1 用左目 `E_L` 和已标定、不可训练的 `T_{R<-L}` 确定右目 renderer camera。
若数据同时携带 `E_R`，它只能作为一致性校验，必须满足上式的预注册容差。`K_R`
来自右目标定；只有 metadata 明确声明共享内参时才能令 `K_R=K_L`。

左右图若经过 crop/resize，必须分别、确定性地更新 `K_L/K_R`。现有 crop 代码已
展示 normalized intrinsics 的焦距和主点更新语义，但 V1 不允许对左右图使用无法
回放的独立随机几何增强。

这里的 `T_{R<-L}` 只是 fixed renderer control。V1 不把 `B=0.25 m` 暴露为
learned input、embedding、loss、weight、mask 或结果声明；baseline-norm constraint
必须另开 successor Gate。

## 5. 训练时数据流

训练锚点是 Stage 2 flow trainer，而不是 `Cupid3DPipeline.run()`。当前 pipeline
入口和 sampler 均由 `@torch.no_grad()` 包围，不能直接承担训练监督。

1. paired dataset 读取原 `x_0`、左图 `I_L`、左目 `E_L/K_L`，并新增同步右图
   `I_R/alpha_R`、`T_{R<-L}`、`K_R` 与 `stereo_valid`。
2. `I_L` 继续经既有 DINOv2 与 visual-conditioning 路径得到 `cond`；右图不编码。
3. 既有 trainer 采样 `noise, t`，构造 `x_t`，denoiser 预测 `v_hat`。
4. 保留原 loss `L_FM=MSE(v_hat, v_target)`。
5. 在同一 autograd graph 内，用现有 Euler sampler 的代数反推出单步 clean-latent
   estimate；不得调用带 `@torch.no_grad()` 的 sampler：

```text
x0_hat_norm = (1 - sigma_min) * x_t
              - (sigma_min + (1 - sigma_min) * t) * v_hat
```

6. 按原 CUPID normalization 反变换：

```text
x0_hat = x0_hat_norm * std + mean
```

7. 将 `x0_hat` 和原 sparse coordinates 送入 frozen、eval-mode Gaussian decoder。
   decoder 参数 `requires_grad=False`，但本段禁止 `torch.no_grad()`，以保留对
   `x0_hat` 的梯度。
8. 用 fixed `E_R=T_{R<-L}E_L` 和 `K_R` 调用既有 `GaussianRenderer.render()`，
   得到 `I_R_hat`。renderer 与 VAE trainer 相同，背景颜色要同时用于 target
   compositing。
9. 在 `stereo_valid AND cfg_conditioned` 样本上计算右目 reconstruction loss，将其
   加到原 MSE。既有 CFG dropout 必须保留，但被 drop condition 的样本不能被要求
   重建某个特定右图；当前 CFG mixin 不暴露该 mask，这是实现 glue 的明确缺口。
10. `BasicTrainer.run_step()` 对 `L_total` 做一次 backward；不增加第二个 optimizer
    或交替更新阶段。

## 6. Loss 节点

Stage 2 flow baseline 当前只有 velocity MSE；V1 复用 CUPID VAE 中已存在的 image-loss
primitive 与背景合成语义，但不声称 Stage 2 baseline 已经有 image reconstruction
loss，也不加入 SSIM：

```text
I_R_gt = I_R * alpha_R + (1 - alpha_R) * bg

L_right_reconstruction =
    mean_over_valid_pairs(
        L1(I_R_hat, I_R_gt)
        + lambda_lpips * LPIPS(I_R_hat, I_R_gt)
    )

L_total = L_FM + lambda_right * L_right_reconstruction
```

- `lambda_lpips` 继承已核验 CUPID VAE loss family 的权重语义；当前代码默认值为
  `0.2`。V1 首次实现不得同时改 LPIPS 定义或引入 SSIM。
- `lambda_right` 是 Gate 强度，必须在第一次 scientific comparison 前固定并记录；
  baseline row 等价于 `lambda_right=0`，treatment row 使用一个预注册正值，不在
  首 Gate 做多超参搜索后挑最好结果。
- V1 mandatory sample mask 是 `stereo_valid AND cfg_conditioned`，像素 target 继续
  使用现有 alpha/background compositing。在没有可信 depth/visibility 时，不声称
  有 occlusion mask，也不增加 learned confidence mask。
- LPIPS/VGG 参数必须显式 `requires_grad_(False)`，但 forward 不能放进
  `torch.no_grad()`，否则会切断对 `I_R_hat` 的梯度。
- `NaN/Inf`、空 valid batch、左右路由错误或恒定 render 都是 hard failure。

## 7. Gradient Path

允许的完整梯度路径是：

```text
L_right
  -> I_R_hat
  -> GaussianRenderer
  -> frozen Gaussian decoder operations
  -> x0_hat
  -> v_hat
  -> existing Stage 2 denoiser
```

其中 frozen decoder 的参数无梯度，但其运算必须对输入可微。现有 Gaussian
rasterizer 显式构造 screen-space gradient carrier，并使用 Gaussian 的 position、
opacity、scale、rotation 与 appearance，因此可以作为候选可微 consumer；其真实
backward 可用性仍需在实现阶段通过 cluster smoke 验证，本文不把静态代码事实写成
运行结果。

明确禁止的梯度终点：

- Stage 1 sparse-structure/UV model 与 UV-to-pose decoder；
- DINOv2 image encoder；
- frozen Gaussian decoder 参数与 renderer 参数；
- `I_R`、`alpha_R`、`E_L`、`T_{R<-L}`、`E_R`、`K_R`、`stereo_valid`；
- CFG dropout 的 `cfg_conditioned` routing mask；
- 任何新增 relation head、pose head、target encoder 或 confidence mask。

这意味着 V1 约束的是现有 Stage 2 generation distribution，不是 camera prediction
path，也不能声称获得 metric-scale pose improvement。

## 8. 推理时路径

推理保持原 left-only CUPID：

```text
left image
  -> Stage 1 structure + UV-to-pose
  -> left pose-aligned Stage 2 generation
  -> structured latent
  -> existing Gaussian / Mesh / RF decoders
  -> pose + 3D outputs
```

`right_image`、`stereo_transform_rl`、right-camera Render 和 reconstruction loss 全部
是 training-only supervision，推理 API 不新增参数。V1 不保留第二个 decoder、
不输出右图，也不要求 stereo input。评估时可以读取右图计算 guard metrics，但这
不是 inference dependency。

## 9. CUPID 精确代码锚点与拟议改动位置

### 9.1 已核验 baseline 锚点

| 文件与行号 | 代码事实 | V1 含义 |
| --- | --- | --- |
| `cupid/pipelines/pipeline.py:305` | Stage 1 从左图 conditioning 预测 structure 和 pose | 冻结 |
| `cupid/pipelines/pipeline.py:312` | Stage 2 采样 structured latent | 冻结推理语义 |
| `cupid/pipelines/pipeline.py:217` | 以 extrinsics/intrinsics 投影 sparse coords 得到 UV | 左目 pose-aligned conditioning 冻结 |
| `cupid/pipelines/pipeline.py:266` | 完整 pipeline `run()` 是 `@torch.no_grad()` | 不能作为训练插入点 |
| `cupid/trainers/flow_matching/sparse_flow_matching.py:95` | Stage 2 trainer 构造 noise、`t` 和 `x_t` | 复用 |
| `cupid/trainers/flow_matching/sparse_flow_matching.py:100` | denoiser 预测 velocity | 新梯度回到此模型 |
| `cupid/trainers/flow_matching/sparse_flow_matching.py:104` | 当前唯一 loss 是 velocity MSE | V1 branch 在此后相加 |
| `cupid/trainers/flow_matching/mixins/classifier_free_guidance.py:40` | CFG 随机决定 condition dropout，但当前不返回 mask | V1 glue 需暴露 `cfg_conditioned` |
| `configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond.json:28` | 官方 pose-conditioned Stage 2 dataset 是 `ImageConditionedSLatWithUVTransforms` | baseline data/config reference；不直接覆盖 |
| `configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond.json:62` | 官方 trainer 入口是 `VisualImageConditionedSparseFlowMatchingCFGTrainer` | V1 专用 config 应复制后局部替换 |
| `cupid/pipelines/samplers/flow_euler.py:31` | 已有 `v -> x0` 精确代数 | 在 trainer 内复用公式 |
| `cupid/pipelines/samplers/flow_euler.py:66` | sampler step 是 `@torch.no_grad()` | 不得直接调用作训练 |
| `cupid/datasets/structured_latent.py:152` | 读取 cached structured latent | 保留 `x_0` source |
| `cupid/datasets/structured_latent.py:157` | dataset 对 latent 做 `(feats-mean)/std` | 决定训练反归一化 |
| `cupid/datasets/structured_latent.py:234` | 现有 dataset 只为单个 view 计算 UV | paired carrier 需新增右目字段 |
| `cupid/datasets/components.py:341` | 训练时从可用 view 随机选一个 frame | 不能当作 calibrated stereo pairing |
| `cupid/utils/pose_utils.py:275` | frame `c2w` 转换为 renderer 所用 world-to-camera | 固定相机约定 |
| `cupid/models/structured_latent_vae/decoder_gs.py:118` | structured latent 解码为 Gaussian list | 作为 frozen training consumer |
| `cupid/renderers/gaussian_render.py:169` | renderer 接收 Gaussian、extrinsics、intrinsics | 右目 fixed-camera 渲染接口 |
| `cupid/renderers/gaussian_render.py:60` | rasterizer 设置 screen-space gradient carrier | 支持候选可微路径 |
| `cupid/trainers/vae/structured_latent_vae_gaussian.py:162` | VAE trainer 已有 decode -> render 训练路径 | 复用成熟组织方式 |
| `cupid/trainers/vae/structured_latent_vae_gaussian.py:169` | target 使用 alpha 与 renderer background 合成 | V1 复用 |
| `cupid/trainers/vae/structured_latent_vae_gaussian.py:172` | 已有 L1 / LPIPS image-loss primitive | V1 复用，不加 SSIM |
| `cupid/trainers/basic.py:442` | `training_losses` 的总 loss 进入 backward | V1 唯一 sink |

### 9.2 实现位置合同

实现阶段应做最窄的局部增量；本文不批准类名或模块名：

1. `cupid/datasets/structured_latent.py`：增加一个 paired-data variant，复用
   `ImageConditionedSLatWithUVTransforms` 的左目行为，额外返回 3.1 节右目字段。
   不改原 dataset 类和原 baseline config。
2. `cupid/trainers/flow_matching/sparse_flow_matching.py`：在一个专用 trainer
   variant 中复用现有 `training_losses` 的 noise/time/denoiser/MSE 语义，并在
   velocity MSE 后追加第 5-7 节分支。最终类名在实现 review 时确定。
3. decoder 通过 `cupid.models.from_pretrained()` 加载到 trainer 的非优化器属性，
   `eval().requires_grad_(False)`；不得把它作为新的 trainable model 加入 optimizer。
4. `cupid/renderers/gaussian_render.py` 与
   `cupid/models/structured_latent_vae/decoder_gs.py` 原则上零修改；若真实 backward
   暴露兼容性问题，先报告根因，不得通过 detach/no-grad 绕过。
5. 新建 V1 专用 config，引用 paired dataset 和专用 trainer；不覆写
   `configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond*.json` baseline 文件。

## 10. 为什么选择此位置

1. 它直接作用于需要验证的对象：Stage 2 structured-latent generation distribution。
2. 单步 `x0_hat` 已由 flow 参数化唯一确定，不需要把 50-step sampler 改成可微训练
   图，因此只新增一条监督分支。
3. 它复用 CUPID 已有 Gaussian decoder、renderer、alpha/background 和 L1/LPIPS
   primitive，不要求新的 learned geometry 或 relation head。
4. 训练分支可完全移除，推理 API 和两阶段生成链不变。
5. 梯度 ownership 清楚：只回到现有 Stage 2 denoiser，不会把 right reconstruction
   与 Stage 1 camera-scale learning 混成一个实验。

## 11. 拒绝或后置的替代位置

最多保留以下两个替代项，不与 V1 同时启用：

1. **拒绝：在完整 50-step sampler 终点加 render loss。** 当前 sampler 的 step 和
   full sample 都是 `@torch.no_grad()`；解除它并跨全部采样步反传会同时改变训练
   协议、显存、计算预算和优化动力学，破坏最小 Gate。
2. **后置：DINO/voxel/latent feature consistency。** 它测试的是表示一致性而不是
   右目可渲染性，并引入新的 target feature、层选择、stop-gradient 和权重定义。
   只有 V1 单独通过或保持 baseline 后才能作为 successor Gate。

Numeric `B=0.25 m` / baseline-norm loss 属于另一科学层级，明确 out of scope；它
不是 V1 的调参项，也不能作为 V1 失败后的同-run 补丁。

## 12. 最小评估合同

- baseline：同一 checkpoint、dataset split、seed policy、预算与 config，关闭
  right branch；精确运行 commit/checkpoint 在实现阶段登记。
- treatment：只打开 V1 right branch，使用同一其余条件。
- primary：valid-pair right-view L1 与 LPIPS。
- guards：原 flow MSE、原 CUPID evaluator 指标、finite rate、non-constant render、
  valid-pair coverage、left-path preservation、gradient-to-denoiser 非零且有限。
- success：预注册的 right-view 指标改善，同时所有 guards 通过。
- neutral：right-view 稳定但无显著改善；只能声称接通监督，不能声称学到正确 3D
  或 metric scale。
- failure：路由/相机约定错误、空 mask、非有限值、render collapse、原指标回退、
  梯度 ownership 错误，或需要添加第二个科学变量才能成立。

## 13. 可视化 Delta 清单

integration mother diagram 必须从任务 1 的 approved baseline mother 复制；在用户
批准前只可标 `DESIGN ONLY`。图内全部使用以下英文可见标签：

- 保留 baseline 的所有节点、位置、颜色、形状和连接，不重画 Stage 1/Stage 2。
- 在左图旁新增 `Synchronized right observation (train target)`，不得连到 DINOv2
  或 Stage 1。
- 在左目相机旁新增 fixed-geometry 节点 `Calibrated T_R<-L`，使用 fixed geometry
  shape；连接为 `E_R = T_R<-L E_L`。
- 从 Stage 2 denoiser 输出新增小节点 `One-step clean latent estimate`，不要画成
  learned module。
- 复用 baseline `Gaussian Decoder` 与 `3D Gaussians` 节点，并标 `Frozen for V1
  supervision`；不要复制第二套 decoder。
- 新增 consumer `Render (right camera)`，输入来自 `3D Gaussians` 与 fixed `E_R,K_R`。
- 新增 supervision 节点 `Right-view L1 + LPIPS`，同时接收 rendered right view 与
  synchronized right target。
- 用单一 project color 高亮所有 V1 delta；fixed geometry、renderer/consumer、loss
  必须使用不同 shape 语义。
- 画一条 backward-only gradient arrow，从 loss 回到 `Stage 2 generation`；明确
  截止于 Stage 2，不指向 Stage 1、camera pose 或 fixed decoder weights。
- 加 `TRAIN ONLY` bracket 包住 right target、fixed right-camera render 与 loss；
  推理路径加 `Inference unchanged: left only`。
- 不出现 `Relation Head`、`Stereo Encoder`、`B = 0.25 m loss`、feature consistency、
  depth/pose supervision 或 historical four-view arrows。
- 图注必须同时写 `DESIGN ONLY / NOT IMPLEMENTED`；只有实现与科学证据通过后才能
  改为 implementation/result 状态。

## 14. 规格释放条件

V1 当前只允许进入 diagram review。进入实现前仍需：

1. 用户批准任务 1 baseline mother；
2. 用户批准本 V1 insertion 和可见术语；
3. 数据 owner 提供真实 calibrated stereo pair schema，而不是随机多视角替代；
4. 实现 owner 登记 exact baseline checkpoint、split、`lambda_right` 与 success margin；
5. 后续测试严格通过 GitHub 同步到 cluster 并在 Slurm compute node 执行。
