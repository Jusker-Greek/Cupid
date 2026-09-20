# 集群数据与loss/W&B核查

时间：2026-09-20 16:00 CST。通过现有SSH读取文件名、清单、小型JSON及代码；本轮未做新的数据内容计算、模型测试或训练。官方权重下载305474仍在Slurm计算节点server14运行，305481等待其成功后执行单卡推理。

## 下载限制更正

用户明确：禁止在登录节点下载大型资产，允许在Slurm计算节点下载。此前将限制写成“全面禁止大型下载”不准确。本轮没有再次索要下载许可，未更改SSH/代理/权限配置。

## 数据集目录和实际证据

下列GSO路径均以 `/public/home/ricky/DATASET/` 为前缀。数字为本次 `find -mindepth 1 -maxdepth 1 -type d | wc -l` 的顶层目录数，不能当作完整有效对象数或图对总数。

| 根目录 | 实查范围 | 用途判断 |
|---|---|---|
| `gso_stereo_output_random` | 前次清单核验1对象、5轨迹、125对；本次仍为smoke配置路径 | Panda最小调试/推理；不足以支持泛化训练结论 |
| `GSO_1K_200` | 903个对象目录；注册表1025条planned记录；损坏清单4条（末行无换行，wc显示3不能当作3条） | Stereo主训练候选，尚未接入现有训练loader |
| `gso_stereo_normalized_zaxis_5traj_7f_1` | 1003个对象目录 | 不同轨迹/基线配置的候选评估数据；未核验全量可用图对 |
| `gso_stereo_output_random_1000` | 389个对象目录 | 历史渲染版本；名字1000不是完成数量 |
| `gso_stereo_output_random_1000_10f` | 501个对象目录 | 历史10帧版本，未全量校验 |
| `gso_stereo_output_random_1000_10f_0.6m` | 502个对象目录，存在损坏清单 | 路径中的0.6m不能单凭名字解释为基线或物理单位 |
| `gso_stereo_output_random_1000_10f_1m` | 3个对象目录 | 小规模历史版本，未全量校验 |
| `GSO_pred_poses_10` / `GSO_shared_poses_10` / `GSO_single_100traj` | 各1个对象目录 | 特定调试版本，不能据名称判定GT或训练用途 |
| `Gazebo` | 原始3D资产根；此前已核验Panda `meshes/model.obj` | 原模型、canonical/渲染变换审计来源 |

另发现 `gso_10k_single_gpu_batch_test`、`gso_10k_test`、`gso_10k_test_100gpu`、`gso_50k_test_50gpu`、`gso_stereo_output`、`DL3DV`、`RayZer` 等目录，本次只确认存在，不认定数量、完整性或CUPID兼容性。未无边界递归扫描。

共享训练数据：

- `/data/group_gao/trellis/HSSD`：本次直接读取已知 `metadata.csv` 成功，能列出 `renders_cond` 和 `latents`。此前仅根目录listing失败，不能外推所有已知子路径均不可读。首条对象 `001065d01ce8bf908b78a03f32ae36d4e866faee1252ced8488b1225666f7d52` 的 `renders_cond/<id>/transforms.json` 为24366字节、`latents/dinov2_vitl14_reg_slat_enc_swin8_B_64l8_fp16/<id>.npz` 为985384字节。没有在登录节点加载NPZ或全量解析metadata；样本读取不等于全量可用。
- `/data/group_gao/trellis/ObjaverseXL_github/metadata.csv` 与 `/data/group_gao/trellis/ObjaverseXL_sketchfab/metadata.csv` 文件存在，分别359646888和185570716字节。只做stat，未读取大型内容或认定配套latent齐备。

## 两组额外配置抽查

1. `GSO_1K_200/HP_Card_Invitation_Kit` 有200个轨迹目录。只核查其中 `random_linear_94`：左右各10 PNG、10 NPY，顶层10 HDF5和trajectory_info.json。JSON为num_frames=10、baseline=0.1、resolution=512×512、fov=51°、normalized=true；scale=5.090302079959133。原始JSON中的m文字未独立证明物理米制。本次未打开像素、相机矩阵或HDF5内容，不能算投影验证。
2. `gso_stereo_normalized_zaxis_5traj_7f_1/HP_Card_Invitation_Kit` 有5轨迹目录。只核查 `traj1_yneg03_z_sweep`：左右各7 PNG、7 NPY，7 HDF5；baseline=0.06、resolution=512×512、fov=51°。与上组基线不同，不能共用Panda的0.1相对标定文件。

GSO_1K_200损坏清单现有4条：Now_Designs_Snack_Bags_Bicycle_2_count/random_linear_7、PARENT_ROOM_FURNITURE_SET_1/random_linear_7、Perricone_MD_No_Mascara_Mascara/random_linear_3、Sootheze_Cold_Therapy_Elephant/random_linear_42。只是已有名单，不是全量坏样本统计。

## 准备用哪个训练

**建议下一条Stereo训练以GSO_1K_200为主数据源；当前实际作业仍是Panda单对预训练推理，没有已经启动的Stereo训练。** 应先建立有效pair清单、按对象身份固定train/validation/test划分，并处理损坏记录。同一对象的不同轨迹/不同GSO版本不能假装独立对象做跨集测试；另一个1003目录版本只可在处理对象重叠后用于评估。

现成原CUPID训练脚本 `scripts/submit_cupid_gl_full.sh:22` 默认HSSD，dataset为ImageConditionedSLatWithUVTransforms。其接口读取 `metadata.csv`（`cupid/datasets/components.py:48`）、`renders_cond/<id>/transforms.json`（同文件:305）和latent NPZ（`cupid/datasets/structured_latent.py:154`）。GSO_1K_200根没有metadata.csv，本次看到的是对象/轨迹/双目渲染组织，不能只改data_dir就训练。

还需具体实现成对GSO loader、所选训练目标及其target/latent准备、对象级split和评估接口。现有SUV配置也引用预编码SS/UV latent及旧权重路径，不是已经可用的GSO Stereo训练方案。这里没有替用户决定新的loss权重或训练模块，也没有用HSSD复现替代Stereo实验。

## Loss可视化与W&B：实际完成边界

| 项目 | 原CUPID训练入口 | 当前Stereo入口 |
|---|---|---|
| W&B初始化、online run receipt | 已有，cupid_train.py:400-429 | scripts/run_stereo_cupid.py没有wandb接入 |
| total/component training loss、LR、step | 已有，base trainer日志分支；TensorBoard和W&B同时写入 | 当前是推理，无optimizer和训练loss |
| validation/test loss | 当前GL contract明确NOT_APPLICABLE；不是已实现评估 | 尚未实现Stereo训练/评估loss |
| pose error、pose scale/norm | GL contract声明相机是条件输入，非预测target | 本地保存预测pose/similarity，但无GT误差计算与W&B曲线 |
| 服务端readback | scripts/verify_cupid_wandb.py已有GL smoke检查 | 无Stereo W&B run/服务端读回证据 |

实际代码：

```python
# cupid_train.py:405：配置了project后，主rank初始化
wandb_run = wandb.init(...)
# cupid/trainers/base.py:428-436：按i_log写入均值训练标量
log_show['train/loss_total'] = log_show['loss/loss']
self.writer.add_scalar(key, value, self.step)
self.wandb_run.log(log_show, step=self.step)
```

原Flow Matching训练的核心loss是预测速度与target的MSE（`cupid/trainers/flow_matching/flow_matching.py:169-170`），并记录时间bin MSE。`log_scale`是混合精度数值缩放，不是pose scale，不能混称。

本地与远端 `/public/home/ricky/CODE/stereo_cupid_2fa36a1_a14` 的4个文件blob逐项一致：

- cupid_train.py: `5f28bb94eeb7bf324753c5bfb5f588d3db478002`
- cupid/trainers/base.py: `7fffae70c5861f11e40ed0693ad773f95120c29e`
- scripts/run_stereo_cupid.py: `37acacd77c8cf68c0e250f10051620fddef5af90`
- scripts/verify_cupid_wandb.py: `9e9a8c86e6ccecb17bd89d673eae81ee91b27056`

结论是“原CUPID的W&B/训练loss代码已同步，Stereo所要求的完整日志仍缺接入”，不能写成“已经全部加上”。此轮检查没有改模型或日志源码，避免把静态检查冒充实际新增/验证。

## 反思

- 尚不确定：903个目录中完整可训练pair的数量、各版本重叠和预编码训练target的可用性。
- 主要风险：直接沿用GL的NOT_APPLICABLE声明或把混合精度log_scale当pose scale，会造成看似有曲线但缺少用户要求的Stereo指标。
