# D 数据接口 V1

实验候选 `STEREO_CUPID_STAGE1_TRAIN_V1`；冻结推理基线 `STEREO_CUPID_V1_SHARED_SS`。

任务清单：公共schema/单pair reader → 清单/固定split/坏样本与重复审计 → 与T对齐官方target契约 → Slurm真实数据验证 → 交接R批量target任务。

假设：同物体左右输入可复用官方SS目标，并分别生成官方SUV目标。基线是原官方单图target契约；数据适配是本lane唯一变化，不改flow/loss/sampler/logger。工程验收为可读成对数据、可追溯target和无split泄漏；不设研究成绩阈值。失败保留候选行和原因，修reader根因后新输出重新审计。

## 公共接口

`from cupid.datasets.stereo_gso import StereoGSOPairs, discover_pairs, load_pair`

- `discover_pairs(root,dataset_id,seed,fractions)`：逐行JSON兼容record。pair身份为dataset/object/trajectory/数字frame；数字PNG `000`与HDF5 `0`精确配对，别名冲突失败。保留缺文件和空轨迹；不从planned数量合成不存在帧。
- `load_pair(record,root)`：返回pair/object/trajectory/frame/split、views、normalization、unit、provenance、validity。每侧 `rgba` HWC uint8、`mask` HW bool、`depth` HW float32、`depth_valid`、`K_fullpixel`、`w2c_saved`、crop和pixel映射。
- `StereoGSOPairs(manifest,root,split)`：默认只选content_verified行；`collate_pairs`保留list及可变尺寸。trainer factory另行适配，不改历史dataset registry。
- K仅从该trajectory的resolution/fov计算并标 `DERIVED_HORIZONTAL_FOV_HYPOTHESIS`；无Panda fallback。w2c原样保留，det<0不会静默翻轴。`calibration_verified=False`、`training_target_ready=False`。
- raw reader无crop/resize，映射是全图identity和UV乘W/H；真实训练crop必须另记映射并同时变换K/target。
- foreground alpha>127不等于amodal；depth保留原值，valid mask排除非有限、非正、alpha背景、>=1e10。1e10是已有Panda审计背景值，本配置显式记录，不是研究阈值；全量若不同须按真实renderer修配置。
- 单位scene_unit；不宣称米。不把normalization.scale当GT物理尺度。

## 审计与split

`scripts/stereo_data_manifest.py --config configs/stereo/data_gso_stage1_v1.json --output NEW_ROOT --verify-content --hash-assets`

必须在Slurm计算节点执行。输出pairs.jsonl（全部候选/失败）、summary.json、duplicates.jsonl、磁盘SHA索引。未给verify-content只能报文件清单，不报有效内容数。使用对象ID+固定seed哈希80/10/10，所有轨迹及同名不同版本对象固定同split；单对象Panda不可能同时满足对象级train/val/test。SHA重复审计覆盖被扫描图像的跨对象/跨split完全相同内容，不证明重命名且重渲染资产无泄漏。不同版本应合并审计后再报告跨版本无泄漏。

现有903目录、1025 planned和Panda125清单均为历史审计范围，不能当本实现运行结果。本实现尚未执行；SSH检查2026-09-21仍Connection closed before banner。没有新job。

## 官方target链与未闭合输入

`cupid/datasets/sparse_uv_structure.py`从64³ voxel centers分别用`utils3d.torch.project_cv`得到UV，clamp[0,1]；const_ssuv模式用UV在[.01,.99]的体素投影支撑。非const模式读canonical voxel PLY，再按投影过滤。`SparseUVStructureLatent`分别载SS/SUV latent并concat；不能将左右UV平均。

当前GSO记录只有renderer归一化及保存相机，缺精确历史canonical资产变换闭合，Panda w2c det≈-1。不能直接给官方CV投影/encoder输入并宣称GT；需要可追溯canonical occupancy、每侧canonical-to-CV外参、对应crop K。目标契约与T协商中。

## 反思

- 未验证：全量有效pairs、标定轴变换、canonical occupancy与UV encoder训练契约。
- 风险：只按目录ID分split无法识别重命名的同一资产；内容hash也不能证明不同渲染无资产泄漏。

## 与T确认后的训练factory

`build_stage1_datasets(config['data']) -> {train, validation, collate_fn, identity}`。
配置需要 `manifest,root,target_index,target_root`，可选`target_kind='dense'|'latent'`、`ss_channels=8,uv_channels=8,image_size=518`。

每sample为 `images[2,3,518,518]` 与以下之一：

- latent：`ss_latent[8,16,16,16]`、`uv_latent[2,8,16,16,16]`；各侧posterior mean，未做额外normalization。
- dense：`ss[1,64,64,64]`、`ssuv[2,1,64,64,64]`、`uv_volume[2,2,64,64,64]`。T的OfficialTargetAdapter负责encoder，D不创建GPU作业。

collate在前面增加B维，保留pair_id/object/frame/unit/provenance list。target index每行包含schema（STEREO_GSO_DENSE_V1或STEREO_GSO_LATENT_V1）、pair/object/trajectory/frame/split、相对`npz`、文件`sha256`、全部`source_asset_sha256`、provenance。NPZ须有对应目标及整数`crop_xyxy[2,4]`。latent provenance额外必须有sample_posterior=false、latent_normalization='none'及两encoder SHA；两类均需geometry_receipt_sha256。

目标缺失、哈希变化、身份不一致、latent shape错误、train/validation对象或完全相同图像泄漏均显式失败，不随机补样。完整训练必须由全量清单的目标coverage验收；bounded smoke另建有范围声明的清单，不改原清单。factory要求train/validation均非空，Panda单对象无法用于科学对象级validation；不可伪拆轨迹绕过。

## Dense目标生成入口

`scripts/stereo_data_targets.py --manifest PAIRS --root DATA_ROOT --geometry-index GEOMETRY_INDEX --geometry-root GEOMETRY_ROOT --output NEW_ROOT`。

GEOMETRY_INDEX每行：pair_id、receipt（相对路径）、receipt_sha256。每份receipt是`STEREO_GSO_GEOMETRY_V1`，包含pair_id、source_asset_sha256、occupancy_npy/occupancy_sha256、w2c_cv[2,4,4]、K_fullpixel[2,3,3]、image_wh[2,2]、crop_xyxy[2,4]、const_ssuv=true、validity(canonical_occupancy_verified/canonical_to_cv_verified)、provenance(canonical_frame/asset_sha256/renderer_provenance/geometry_evidence)。现有数据不自动具备这些字段；D尚无真实可提交receipt。

已核官方语义：SparseUVStructure先对64³中心project_cv，原始UV算全图ssuv，clamp UV后再仿射crop/clamp；bool const_ssuv=true保留全图ssuv。仅字符串'crop'重新算support。D保持该顺序，不能用crop K重投影替换。images先真实整数PIL crop，再RGBA LANCZOS resize518，最后RGB*alpha黑底。此语义已经控制器转达T确认。

CPU回归入口`scripts/stereo_data_contract_tests.py`使用临时合成fixture，覆盖数字帧配对、重复别名、缺文件、反射保留、1e10背景、HDF5/PNG一致性、split稳定和路径限制。仅Slurm运行，测试fixture不是训练target或科学结果。
