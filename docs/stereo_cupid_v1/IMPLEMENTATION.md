# Stereo-CUPID V1 实施与运行入口

2026-09-20。实验标识：`stereo_cupid_v1_pretrained`。基线：`cc95f36fc26b5d90054ffd920df6c1c1b54c3e4d`。

用户已授权审计与实施同时推进。此实现复用预训练权重，在同一物体的两张图之间共享结构、分别生成UV，采样结束后做外部标定几何。**没有新增训练loss、没有修改既有HSSD训练任务，也没有将未运行代码标为验证通过。**

## 已实现

- `cupid/pipelines/stereo.py::StereoCupid3DPipeline.run_stereo`：两图编码与同权重flow；Stage1可独立完成；可选调用原左相机恢复/Conditioner/Stage2 mesh decoder。
- `cupid/pipelines/samplers/stereo.py::sample_shared_structure`：复用现有Euler/CFG，初始SS相同，每步仅平均结构候选，左右UV保留。默认UV噪声独立，记录seed和参数。
- `cupid/pipelines/stereo.py::_decode_stereo`：occupancy只解码一次，两个UV decoder结果按同一组明确坐标键取值。保存原SS支撑和可能扩展的UV支撑，不按两个稀疏数组的行序假定对应。
- `processing.py`/`types.py`：原裁剪与de_crop行为保留，只新增PIL实际crop_box/source_size记录。
- `cupid/utils/stereo_geometry.py`：UV还原全图像素；一般标定三角化，支持非平行/不同内参；positive-depth、重投影、ray-angle等筛选；正尺度、proper rotation Umeyama；退化/失败码；保留全部点和mask。
- `scripts/run_stereo_cupid.py`：单pair命令行，原权重本地读取，保存`result.json`与`stage1_and_geometry.npz`；`--full-mesh`再输出canonical PLY和（若拟合成功）left-camera PLY。无纹理烘焙、无MoGe。
- `scripts/submit_stereo_cupid_pilot.sh`：复用既有集群runtime路径，默认1 GPU、8 CPU、64GB RAM、30分钟。先在同一Slurm任务内运行短测试，随后执行1对样本；尚未实际提交。

没有标定也可进行Stage1生成：`geometry_status=CALIBRATION_MISSING`，不输出伪米制物体。标定齐全时自动运行几何支路，不要求先完成全数据GT审计。Stage2失败保留Stage1数组并标为PARTIAL，进程非零退出；不会把降级当完整成功。

## 输入契约

`--pair-dir` 指向实际轨迹目录，必须含`left/000.png`、`right/000.png`（或指定frame）。GSO runner使用两图已有RGBA alpha，不触发rembg权重下载。原始NPY/GT depth不作为模型输入，也不自动猜测它们的坐标约定。

`--model-path`必须是已有本地Cupid模型目录（含pipeline.json）；`--dino-repo`是已有DINOv2本地源码（含hubconf.py）；`--dino-checkpoint`为与pipeline.image_cond_model匹配的已有直接state_dict。DINO以pretrained=False初始化再明确加载该文件，避免torch.hub自动下载。HF fallback设为offline，缺文件会真实报错。

可选相机JSON必需字段：

| 字段 | 含义 |
|---|---|
| K_left/K_right | 3×3，原图像素内参 |
| right_from_left | 4×4列向量CV刚体变换 |
| image_size_left/right | [width,height]，必须与原图一致 |
| camera_convention | 固定`opencv`：x向右、y向下、z向前 |
| distortion | `none`；有畸变时需先提供正确去畸变图与标定 |
| length_unit | `m`或`scene_unit`；后者输出不称为米制 |
| source | 外部标定的可追溯出处 |

没有提供伪造的GSO相机JSON。旧NPY的det=-1问题不能用任意flip自动修补；应从生成代码识别换基。

诊断默认`max_reprojection_px=2.0`、`min_ray_angle_deg=0.1`可由CLI覆盖并写入结果，**不是方法成功阈值**。低残差不证明真实同点/物理尺寸正确。当前无GT尺度成绩；H01仍未验证。

## 输出与frame

NPZ：原生coords、共同support_coords、x_local、左右原始UV、还原后pixels、各类mask、视差、三角化点、相似变换及拟合残差（若可用）。JSON：输入和模型路径、git commit、job id、seed、crop变换、CFG/schedule设置、长度单位、计数、失败状态。科学结论字段保持UNTESTED。

`mesh_canonical.ply`保留decoder原生坐标。`mesh_left_camera_m.ply`或`mesh_left_camera_scene_unit.ply`仅施加一次`scale * vertices @ rotation.T + translation`，未经过GLB轴变换。暂不输出GS的米制协方差/SH旋转，也不输出纹理GLB；原单图/多物体导出函数未修改。

## 测试与实测状态

新增测试覆盖：非校正且内参不同的已知几何、正确尺度/旋转/平移、负深度、坏点分母、退化失败、resize/crop/padding/半像素、真实PIL奇数裁剪、逐步SS共享但UV不平均、occupancy与扩展UV支撑不同。

本轮仅完成静态代码检查与`git diff --check`；按用户全局规则，没有本地执行测试或模型。集群SSH在banner阶段超时，无法取得计算节点，因此新增测试**尚未运行**。没有job id、没有startup evidence、没有模型结果。网络可用后在既有Slurm任务里运行上述测试与首对推理；普通代码错误应直接修复并重新同步，不升级成额外研究审批层。

## 提交入口

集群拉取本分支后，以下变量需由实际文件定位，不能用猜测路径：
`CUPID_PROJECT_DIR`、`CUPID_EXPECTED_COMMIT`、`CUPID_PAIR_DIR`、`CUPID_MODEL_PATH`、`CUPID_DINO_REPO`、`CUPID_DINO_CHECKPOINT`、`CUPID_OUTPUT_DIR`。

全部设置为真实值后，入口为`sbatch scripts/submit_stereo_cupid_pilot.sh`；`CUPID_CAMERA_JSON`可省略，`CUPID_FULL_MESH=1`启用Stage2。该命令尚未在集群验证，不声称复制即可运行。

用户提到“提交训练”，但交接V1原定不重训；已在对话询问是否实际指原权重双目实验。未经确定训练目标，不把既有HSSD训练launcher改名提交为Stereo-CUPID。
