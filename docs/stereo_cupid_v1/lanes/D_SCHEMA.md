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
