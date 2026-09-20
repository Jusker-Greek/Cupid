# Stereo-CUPID 接管与集群实查

**2026-09-21 00:19：SUV flow 2239067672字节及SS decoder147591972字节已本地官方SHA通过，尚未上传成功。** CMYNetwork/MaccCore20890已关闭，scutil显示系统代理禁用；实测现有ClashX7890监听且官方API HTTP200/1.63秒。旧21404进程组已停止、lsof确认无writer后，新32204通过7890续传原2125938534断点并完成SUV SHA。上传SSH返回Connection closed by10.10.7.1 port22，32204已失败退出，日志transfer_a4.log，receipt为UPLOAD_UNVERIFIED；不能推断远端文件是否创建。三次SSH检查均在banner/keyexchange前关闭，TCP连接建立但无远端协议串。route只读显示10.10.7.1经utun8/gateway198.18.0.1，不能直接认定代理是唯一根因。未改VPN/SSH/系统配置，已向用户询问校园网/VPN是否仍连接。

为避免SSH故障阻塞其它下载，源码972bc8e61bd0d453864afc1d25b38382b8db1ea6已push/精确读回，新增显式--download-only：保留全部本地官方SHA及上传待办，不把本地完成当上传完成。新独立helper PID33142，日志transfer_a5_download.log，进程receipt transfer_process_a5.json，ClashX7890，从本地已校验SUV继续余下5文件；SS decoder已完成，SS encoder下载中。目标local_upload_a1不变但当前--download-only不提交上传job；待SSH恢复后先fresh squeue/sacct/远端incoming审计避免重复，再完成上传。旧306009/306014/5028不恢复。完整pipeline/root、模型运行、Stereo训练仍未完成。

**21:50本地续传已实际恢复至495266996字节。** 21:51消息工具恢复，E00完整包已发送（工具成功）；未读取中央台账ack。

**21:49恢复操作。** 原exec70764不存在，pgrep/lsof确认helper及该partial的writer均已退出；Mac未再次重启（boot18:34:57）。日志最后为HTTP/2 CANCEL/exit92，没有Python异常，因此工具会话消失与进程退出的具体因果仍未知。保留SUV partial304848052字节；本机20890仍由CMYNetwork/MaccCore监听。源码46e2d022e36eae00de007f75101e683e8efb1680已push/精确读回，将curl显式设HTTP/1.1以针对已观察HTTP/2重置；长期网络稳定性尚未证明。新helper PID21404以独立进程会话运行（start_new_session、stdin DEVNULL、fcntl锁），日志`transfer_a3.log`，进程receipt`transfer_process_a3.json`，继续同一partial，不重复下载已保存字节。无新Slurm/GPU提交，无上传成功证据；旧306009/306014/5028仍结束。

**21:36切换完成：集群SLAT flow 2401799952字节已VERIFIED。** 旧CPU306009已CANCELLED（1h5m48s），旧GPU306014已CANCELLED（0秒无节点），旧转发5028退出255、已关闭。这是用户要求本地下载上传后的主动切换，不是模型失败。a12保留5完整权重共3099847620字节；完整receipt仍非VERIFIED，余下六权重由本地helper70764续传。最新本地SUV partial166324845字节，已超过原83143277断点；本地完整SHA、实际上传和1GPU尚未完成。不得恢复旧306009/306014/5028。上传目标仍独立local_upload_a1，helper每文件在Slurm CPU分配接收/复核；最终须新根合并全量校验再提交新1GPU。

**21:33用户明确改为本地下载后上传集群，已实际开始。** 本地根 `/Users/ruikegu/Downloads/Cupid_official_1191de37_local_a1`，CMYNetwork/MaccCore既有代理127.0.0.1:20890。首个SUV flow持久化83143277字节后HTTP/2 CANCEL中断；文件保留，原exec83692终态92。官方manifest初次获取超时导致首helper启动缺文件，重取固定revision成功后，前台helper exec70764续传（`transfer_a2.log`），没有安装依赖。helper源码6b35172d38393d62b0dad623de899d1484246436已GitHub精确读回；只处理六个剩余官方safetensors，逐文件本地官方SHA后，通过独立1CPU/1GB/1h的Slurm srun接收及复核上传SHA，不在登录节点落盘/哈希。计划上传根 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_local_upload_a1`，尚无上传成功证据。每次incoming新身份、最终硬链接拒绝覆盖，保留失败证据；这是子集而非完整pipeline。

集群306009/a12继续完成当前SLAT flow（最新2399141888/2401799952，末块重试），306014仍依赖旧下载；只有SLAT全文件VERIFIED后才停止旧下载及其依赖、关闭转发5028，保留a12完整文件及缓存，避免重复下载剩余六文件。之后本地上传子集与旧根经新Slurm合并/全量官方校验、新GPU输出身份，不往活跃a12写入。模型执行源码仍3f9d24f/a22，尚无推理结果。下一轮先确认helper/文件增长；原curl已停，不得重复本地writer。本地首次可见83MB并非完成、也不证明更快；当前没有Stereo训练loss/optimizer/W&B。

日期：2026-09-20，Asia/Shanghai。实验 `STEREO_CUPID_V1_SHARED_SS`。

20:33：通过本机20890代理的续传306009已恢复并超过1589641216旧断点，306014等待依赖。并行CPU小探测7999/直连仍超时，但不影响主下载；“所有代理不可用”不成立。源码3f9d24f/a22只改临时网络重试窗口，完整性检查与模型未改。用户本地中转备选只做1MiB公共文件小样，未全量下载，速度优劣尚未证明。证据network_resume_306009.txt。

最新实测：CPU305961在server14完成记录，7999代理与直连四项传输均超时、0字节；不能称任一路可用。旧下载失败与新探测失败均为工程/网络证据，无科学结论；保留缓存后继续恢复既有网络。

20:08更新：305841在20m24s后连接失败，305845取消0秒无GPU，转发49409退出。4完整权重及SLATflow1589641216字节缓存保留。现提交CPU305961有界探测7999代理和直连，PENDING尚无结果；源码b93bbf6/a20，只新增探测脚本，无模型或下载算法改动。最新状态见RUN_STATUS。

19:26实测恢复：现有系统代理端口20890且loopback监听，SSH已通。使用新转发49409/计算节点49693，CPU305841在复用4完整权重和1312817152分块后实际新增16777216字节。GPU305845等待依赖；源码40c09dc/a19、根a11复用a10，详情RUN_STATUS首段。只能称恢复传输，不能称全部权重完成或模型运行通过。

19:02终态：恢复下载305794 FAILED1:0/4m5s，305798取消且无GPU；未超出旧断点，不能称恢复成功，需解决间歇网络。仍无模型运行或科学结果。

18:59：新305794虽已提交/分配，却在旧断点连续连接错误；两次转发均超时退出，暂无新下载字节证据。当前网络阻塞、模型未运行，不能把“已提交恢复”写成“恢复成功”。

18:54更新：单路305609持续下载后因连接错误失败，时间与本机18:34:57重启、转发消失一致；305611取消未分配GPU。完整权重仍只有4个、698047668字节另加1312817152分块可续传。恢复CPU305794、根a10、checkoute1bd1ed/a18，算法未变，恢复丢失的网络通道。故障证据download_305609_terminal.txt；后续实时身份见RUN_STATUS。DINO/数据入口本次仍可读，完整模型和训练尚未验证。

17:31最新：305577因网络读取超时失败、305583依赖取消；4个完整权重和528482304字节SLAT flow分块保留。后继源码cbb4cbf/a17只将并发4→1以检验代理争用，CPU305609和依赖单卡305611已提交，模型根a9复用a8。完整权重仍未完成，详情以RUN_STATUS首段为准。失败证据download_305577_terminal.txt。

17:21恢复实证：305577 RUNNING server14，4个完整权重重新校验后复用，SLAT flow持久化分块已到524288000字节，超过旧失败断点406847488。305583 PENDING afterok:305577，无GPU分配；完整receipt仍DOWNLOADING。新checkout a8e799e/a16、权重根a8和转发session98813详见RUN_STATUS。没有完整权重或模型推理通过的证据。

**最终CPU复验：304071在server14运行11秒，COMPLETED 0:0，11项测试全部通过，S02完成。** 修复后已重跑全部测试，没有跳过。下面按证据保留首轮失败经过；后续不再处于“CPU复验中”。

**17:15更新：下载305505因慢速range连续超过90秒时限失败，依赖305510取消且无模型执行。** 已保留旧证据，将单range时限改为300秒、保留40秒socket超时、分块和官方SHA检查，push/同步后提交新CPU305577并从a7复用完整权重和分块；未安装依赖。完整权重和模型运行尚未完成。最新路径、失败记录和跟进方式见 `../RUN_STATUS.md`。下文关于下载禁令和待授权的问题属于历史状态，已按用户澄清更正为仅禁止登录节点大型资产下载。

补充实测：HDF5记录BlenderProc版本2.8.0，两张colors与左右PNG逐像素相等。按OBJ轴映射 `(x,y,z)->(x,-z,y)` 独立计算scale=13.2032374338，offset与元数据最大差5.29e-8，支持该归一化映射；tight bbox约x±0.401121、y±0.5、z±0.305536。尚未证明历史完整场景矩阵或物理扫描单位。

## 结论与证据等级

上轮只读到了本地 GSO 副本，代码只推送到 GitHub；没有集群拉取、模型推理或训练证据。本轮已实际 SSH 到 `ricky@10.10.7.1`，主机 `mgmtserver01`，并通过 Slurm 在 `server14` 读取样本、执行测试。

- 本轮代码已通过 GitHub -> verified incremental Git bundle -> 新集群 checkout 的路径同步；不是拷贝源码目录。
- `304070` 已读取完整首对样本及五条轨迹清单；随后接口测试 8 项通过、2 项导入失败，终态 FAILED。失败原因是 RGBA 不需要的 rembg 被模块级强制导入。
- 修复提交 `238fe8ac2d882dd7c54e2190eaa52df44db5361a` 把 rembg 导入延迟到真实 RGB 去背景路径。没有 mock、跳过测试、安装依赖或删除去背景功能。后续复验见 NEXT_SESSION 和测试日志。
- 尚无真实预训练模型推理、单卡训练、双卡 DDP 或 Stereo 科学结果。不能将 CPU 测试记为 S05。

## 规则和版本

已读取用户的 AGENTS 指令、`~/.codex/AGENTS.md`、仓库 README、完整交接文档、GSO README/环境/双目规范，以及用户指定 `.../Documents/Codex/2026-09-20/xian/outputs/default.rules.txt`。后者是命令 prefix allowlist，不是让历史 reset/作业命令重新执行的指令。仓库没有额外 AGENTS/Cursor rule 文件命中。交接文档不覆盖当前规则；用户后续授权已将范围从只读审计扩展至代码修复、同步和 Slurm 运行。按用户16:00澄清，限制是不得在登录节点下载大型资产；允许Slurm计算节点下载，不能再将其写成全面禁令或索要重复许可。

十阶段技能使用的 GitHub authority 为 `StereoWorld_RayZer` 分支 `codex/metric-scale-controller-cleanup` 提交 `d88b19e0414aaf482b21f5630b64df604dc2c57a`：AGENTS、十阶段规则及 Operating System 的相关同步/恢复/提交章节。历史实验的独立身份不赋予本实验旧 PASS。

本地分支：`codex/stereo-cupid-v1-20260920`。交接基线 `cc95f36fc26b5d90054ffd920df6c1c1b54c3e4d`；先前实现 `240028ae6e2ac6b4beca92ae0947dae0d25c81af`。初次集群审计源码 `d70919675d66c98ce3ec401bc6278bd4a2910808`，tree `fc8f5d91c790629a363e076d9296521f9aa83442`。修复 tree `fbda08ce0c670f20aeb6bd54a2a509545f9a30b6`。

`/public/home/ricky/CODE/Cupid` 不是可识别的 Git checkout；不能用它假定最新代码。已确认历史运行 checkout `/public/home/ricky/CODE/Cupid_0905d28_a64_s08_v2` 实际 HEAD 是 cc95f36，tracked clean。本轮新建目录，不修改原目录。本地原有 `.DS_Store`、交接文件和 `stereo_cupid_audit_20260919_234339/` 等 untracked 文件保持原状，没有回退。

## 真实数据和原模型路径

| 用途 | 集群绝对路径 | 本轮核验 |
|---|---|---|
| 小集 | `/public/home/ricky/DATASET/gso_stereo_output_random` | 根目录 1 个对象，Panda 5 条轨迹 |
| 完整首对 | `/public/home/ricky/DATASET/gso_stereo_output_random/Android_Figure_Panda/random_linear_0` | left/right/000.png、000.npy、0.hdf5、trajectory_info.json |
| 原始 OBJ | `/public/home/ricky/DATASET/Gazebo/Android_Figure_Panda/meshes/model.obj` | 925665 bytes；5311 顶点；SHA256 见 JSON |
| 材质与贴图 | 同一模型下 `meshes/model.mtl`、`meshes/texture.png`、`materials/textures/texture.png` | 目录与大小已查；未修改 |
| 原模型身份 | 同一模型下 `model.sdf`、`model.config`、`metadata.pbtxt` | SDF name=Android_Figure_Panda，mesh URI=meshes/model.obj |
| 大集候选 | `/public/home/ricky/DATASET/GSO_1K_200` | 根目录存在；未做完整图像计数 |
| 大集登记表 | `/public/home/ricky/CODE/GSO_dataset/task_allocations/GSO_1K_200/object_registry.tsv` | 1025 行/唯一对象，status 全是 planned；不能当作已完成产量 |
| 另一份 GSO mesh | `/data/group_gao/trellis/GSO_mesh/gso_models/Android_Figure_Panda` | 可列出模型文件夹；内容未逐文件比对 |

小集五份清单各 25 帧，逐目录文件名计数各 25 left PNG、25 right PNG、两侧各25 NPY、25 HDF5；合计 125 对、250 PNG、250 NPY、125 HDF5。只读取第一对内容，不代表其余124对或大集全部有效。

本地副本位于仓库同级 `CUPID+Hi3DGen/gso_stereo_output_random`。首对 PNG SHA256 与集群完全相同：left `3a86530449135a6188b833f2ea5aa119b07fb2eda19d4fccb1c511301ff55e49`，right `caf78957b9107a6cb1cabe1c70a4bcf72c1382c01df523bd69361487145da285`。这只证明这两个文件相同，不是整个目录一致证明。

## 首对标定、深度与归一化

图像均为512×512 RGBA。alpha>127的像素数 left=122086、right=113373；bbox分别[0,0,406,443]、[0,0,348,443]。图像顶端/左端裁切，不能作为完整物体轮廓。alpha可用作前景mask，但没有单独实例ID标注；对象身份来自目录与模型SDF。

HDF5有 `colors[2,512,512,4] uint8`、`depth[2,512,512] float32`、`blender_proc_version`，无独立 pose/K/instance segmentation 字段。深度最小0.75953424、最大1e10；**背景1e10是有限数，不能只用 isfinite 过滤**。未宣称alpha就是完整可见性真值。

当前 renderer 1755–1765行设置 `f = (width/2)/tan(fov/2)`，FOV51°给出 fx=fy=536.7151613665727，cx=cy=256。该 K 是当前源码与历史元数据联合推导，非样本直接存储的 K。

源码2498–2505行明确 `left_w2c = np.linalg.inv(left_pose)[:3,:]` 后保存NPY；左右相对变换 `W_R @ inv(W_L)` 数值为 `R≈I, t=(-0.1,0,0)`。baseline=0.1是归一化渲染场景长度；尚不能称为实际扫描物体的0.1米。

两侧保存矩阵 determinant均为 -1.000000279，正交误差约2.99e-7。根因线索已在 renderer 394–398行找到：`fixed_rot[:,1] = -fixed_rot[:,1]`，翻转单列产生反射。因此不允许直接把该矩阵当 proper SE(3) 真值，也不照搬相邻 Stereo_Foundation_Model 消费代码把 w2c称为c2w并翻轴的做法。

按当前K、0.1基线、正向深度、左减视差投到右图，每8像素抽样、过滤0<depth<100及图外，检查1767点；最近邻右深度绝对差中位数0.00019604，99.3209%小于0.01场景单位。该结果支持首对的相对左右顺序/基线/深度一致性；不是遮挡严格评估、完整姿态校准或物理米制证明，阈值没有用于挑选模型结果。

`normalize_scene` 423–481行：先按最大bbox边长倒数缩放，再重新计算中心、加 offset。保存scale=13.2032376129，offset=[-0.0046277493,0.5000527998,0.0006204993]。若以导入后坐标 X 为输入，映射为 `scale*X + offset`。原OBJ边界是[-0.03003,-0.023188,0.000004]到[0.030731,0.023094,0.075743]；OBJ导入轴变换尚需与历史Blender版本绑定。JSON的aabb是硬编码目标立方体，不是每对象测量tight bbox。

## Renderer 与生成版本

真正主脚本：`/public/home/ricky/CODE/GSO_dataset/render_stereo_gazebo.py`，SHA256 `bb9c170dee05521002404452a6903a289ed02d4921182f44f92c375749cc745a`。

对应小集入口：`/public/home/ricky/CODE/GSO_dataset/scripts/test_random_linear_trajectory.sh`，绑定Gazebo/Panda和该输出目录、FOV51、baseline0.1、normalize-scene。**现脚本 num-frames=10，而现数据=25**；renderer修改日期2026-03-18，数据清单2026-02-04。脚本路径明确，历史生成精确版本未闭合。

环境文档列 Blender3.6.5 和 BlenderProc2.8.0；当前安装 ObjectLoader 使用 `bpy.ops.wm.obj_import`。原脚本还包含 `fix_gazebo_textures`，会复制贴图，因此本轮没有执行渲染脚本。历史参考代码在 `original_code_for_reference/Stereo_Foundation_Model-9dbee9fc28cbd332d57a5d39b939bb1cb3625388/`，不等价于样本精确版本。无需依赖网上泛用GSO渲染器来猜路径。

## 代码接口审查

- `cupid/pipelines/samplers/stereo.py` 使用现有Euler `sample_once`，同一时刻共享SS通道，UV保持各自状态；CFG默认参数显式继承。测试覆盖逐步SS共享和不同UV轨迹。
- `cupid/pipelines/stereo.py` 只解一次SS，占用coords与扩展UV支持coords分别导出；两视图UV按同一显式索引取值，voxel center为 `(ijk+.5)/resolution-.5`。共享支持不保证UV物理对应正确。
- 原UV监督在 `cupid/datasets/sparse_uv_structure.py:53,75` 使用 `utils3d.torch.project_cv`，随后clamp到[0,1]。原pose decoder默认DLT；称为epnp的路径也不是“已知K的标准solvePnP”。
- `processing.py` 记录真实PIL crop box；`stereo_geometry.py` 做像素坐标还原、非等K/非平行双目DLT、proper similarity及失败mask。相机反射会拒绝，不会静默修成单位矩阵。
- `scripts/run_stereo_cupid.py` 保存raw coords/UV、每类几何过滤mask和失败分母；可选Stage2沿原左视图条件。canonical PLY与左相机placed PLY分开；相似变换只应用一次。未调用昂贵GLB纹理烘焙路径。
- 新增实现没有optimizer、stereo监督loss或DDP训练入口。它是交接V1的原权重推理实现；训练目标不能由“代码可运行”推导出来。

## 原训练和可复用组件

原HSSD复现job296164实查 PREEMPTED，server01，运行1:47:59，日志到42000/1000000。它使用cc95f36、8GPU、global batch64，从40000恢复，仍无本实验的结果。

E00回执确认可复用组件已在本分支原样存在，无需再merge：

| 文件 | blob |
|---|---|
| `cupid_train.py` | `5f28bb94eeb7bf324753c5bfb5f588d3db478002` |
| `scripts/verify_cupid_wandb.py` | `9e9a8c86e6ccecb17bd89d673eae81ee91b27056` |
| `scripts/lib/wandb_env.sh` | `11025d4cda09a9c7852005079b89900eee3aefc9` |

这些是logger/readback，不是Stereo科学evaluator；原CUPID对test/pose标注N/A，不能因此声称已有用户要求的所有指标。

已定位DINO源码 `/public/home/ricky/.cache/torch/hub/facebookresearch_dinov2_7764ea0f912e53c92e82eb78a2a1631e92725fc8` 和 checkpoint `/public/home/ricky/.cache/torch/hub/checkpoints/dinov2_vitl14_reg4_pretrain.pth`（1217607321 bytes）。采用既有v21r2 overlay和portable Python，无依赖安装。

完整hbb1/Cupid pipeline尚未在已检查的用户cache/CHECKPOINT/ENVIRONMENT、原CODE/Cupid或可读共享缓存中定位。官方仓库约7.27GB：[模型文件清单](https://huggingface.co/hbb1/Cupid/tree/main)。共享 `/data/group_gao/trellis/HSSD` 与 `/data/group_gao/trellis/GSO` 本次登录节点列目录 Permission denied，未绕过；历史能训练不等于当前身份仍有读权限。

## 当前边界

已完成真实集群接管、源码交付、样本数据读数和失败复现。官方权重已在Slurm计算节点下载中，下载许可不是阻塞。下一条Stereo训练的目标及数据适配尚未落地。最新数据集和日志接入状态见 `DATASETS_AND_LOGGING.md`；不能把原CUPID的logger或HSSD训练当成Stereo已完成的训练。
