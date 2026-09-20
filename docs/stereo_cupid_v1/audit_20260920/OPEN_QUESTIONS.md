# 尚未闭合的问题

**2026-09-21新增授权：五个独立任务已开始并行补齐训练缺口。** D数据、T训练器、L日志评估、R集群上传/唯一GPU运行、I集成晨报，真实thread/worktree/branch见CAMPAIGN_TASKS.json；工作顺序与自动修复交接见CONTINUOUS_EXECUTION.md。目标2026-09-21 08:00晨间可核验产物。用户已明确要求阶段完成自动推进、失败修复重试，旧“单卡后暂停等审核”仅历史状态，不再是本轮自动停止点。V1冻结推理基线保留，训练候选另立STEREO_CUPID_STAGE1_TRAIN_V1；没有继承已训练结果。用户目标选择仍可覆盖，暂按官方Stage1监督微调候选实现验证，真实GT/target/样本/steps配置必须落地，不能用toy或HSSD冒充。R独占本campaign GPU提交（先1卡smoke、再2卡DDP、正式优先1卡）；控制器不同时提交。

**2026-09-21 00:22：本地六个剩余权重全部下载完成并通过官方SHA，共4168403480字节。** `local_transfer_receipt.json` 为LOCAL_SUBSET_VERIFIED_UPLOAD_PENDING；PID33142正常完成退出，transfer_a5_download.log含六个LOCAL_VERIFIED。集群a12另有五个已校验权重3099847620字节，两地合计11个权重7268251100字节。仍未形成集群25文件完整root，不能把分散权重齐备称集群模型可用。ClashX7890完成剩余5文件约3分钟，观察到本次路线明显快于旧CMY传输，但不推断唯一根因。

上传阻塞仍为SSH：00:22再次Connection closed by10.10.7.1 port22。没有远端shell，无法核查先前上传是否留下job/incoming；不盲重提交、不安装、不改SSH/VPN/路由。用户校园网/VPN状态问题待答；下一轮先恢复只读SSH并审计上传job与目标，随后只上传已有校验文件，禁止重新下载完整权重。上传后在Slurm新根合并a12和local_upload_a1，补小JSON并全25文件官方SHA/pipeline引用校验，再新1GPU。当前没有任何Stereo模型运行/训练结果，最高S02，S03 DEBUGGING。

**2026-09-21 00:19：SUV flow 2239067672字节及SS decoder147591972字节已本地官方SHA通过，尚未上传成功。** CMYNetwork/MaccCore20890已关闭，scutil显示系统代理禁用；实测现有ClashX7890监听且官方API HTTP200/1.63秒。旧21404进程组已停止、lsof确认无writer后，新32204通过7890续传原2125938534断点并完成SUV SHA。上传SSH返回Connection closed by10.10.7.1 port22，32204已失败退出，日志transfer_a4.log，receipt为UPLOAD_UNVERIFIED；不能推断远端文件是否创建。三次SSH检查均在banner/keyexchange前关闭，TCP连接建立但无远端协议串。route只读显示10.10.7.1经utun8/gateway198.18.0.1，不能直接认定代理是唯一根因。未改VPN/SSH/系统配置，已向用户询问校园网/VPN是否仍连接。

为避免SSH故障阻塞其它下载，源码972bc8e61bd0d453864afc1d25b38382b8db1ea6已push/精确读回，新增显式--download-only：保留全部本地官方SHA及上传待办，不把本地完成当上传完成。新独立helper PID33142，日志transfer_a5_download.log，进程receipt transfer_process_a5.json，ClashX7890，从本地已校验SUV继续余下5文件；SS decoder已完成，SS encoder下载中。目标local_upload_a1不变但当前--download-only不提交上传job；待SSH恢复后先fresh squeue/sacct/远端incoming审计避免重复，再完成上传。旧306009/306014/5028不恢复。完整pipeline/root、模型运行、Stereo训练仍未完成。

**21:50本地续传已实际恢复至495266996字节。** 21:51消息工具恢复，E00完整包已发送（工具成功）；未读取中央台账ack。

**21:49恢复操作。** 原exec70764不存在，pgrep/lsof确认helper及该partial的writer均已退出；Mac未再次重启（boot18:34:57）。日志最后为HTTP/2 CANCEL/exit92，没有Python异常，因此工具会话消失与进程退出的具体因果仍未知。保留SUV partial304848052字节；本机20890仍由CMYNetwork/MaccCore监听。源码46e2d022e36eae00de007f75101e683e8efb1680已push/精确读回，将curl显式设HTTP/1.1以针对已观察HTTP/2重置；长期网络稳定性尚未证明。新helper PID21404以独立进程会话运行（start_new_session、stdin DEVNULL、fcntl锁），日志`transfer_a3.log`，进程receipt`transfer_process_a3.json`，继续同一partial，不重复下载已保存字节。无新Slurm/GPU提交，无上传成功证据；旧306009/306014/5028仍结束。

**21:36切换完成：集群SLAT flow 2401799952字节已VERIFIED。** 旧CPU306009已CANCELLED（1h5m48s），旧GPU306014已CANCELLED（0秒无节点），旧转发5028退出255、已关闭。这是用户要求本地下载上传后的主动切换，不是模型失败。a12保留5完整权重共3099847620字节；完整receipt仍非VERIFIED，余下六权重由本地helper70764续传。最新本地SUV partial166324845字节，已超过原83143277断点；本地完整SHA、实际上传和1GPU尚未完成。不得恢复旧306009/306014/5028。上传目标仍独立local_upload_a1，helper每文件在Slurm CPU分配接收/复核；最终须新根合并全量校验再提交新1GPU。

**21:33用户明确改为本地下载后上传集群，已实际开始。** 本地根 `/Users/ruikegu/Downloads/Cupid_official_1191de37_local_a1`，CMYNetwork/MaccCore既有代理127.0.0.1:20890。首个SUV flow持久化83143277字节后HTTP/2 CANCEL中断；文件保留，原exec83692终态92。官方manifest初次获取超时导致首helper启动缺文件，重取固定revision成功后，前台helper exec70764续传（`transfer_a2.log`），没有安装依赖。helper源码6b35172d38393d62b0dad623de899d1484246436已GitHub精确读回；只处理六个剩余官方safetensors，逐文件本地官方SHA后，通过独立1CPU/1GB/1h的Slurm srun接收及复核上传SHA，不在登录节点落盘/哈希。计划上传根 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_local_upload_a1`，尚无上传成功证据。每次incoming新身份、最终硬链接拒绝覆盖，保留失败证据；这是子集而非完整pipeline。

集群306009/a12继续完成当前SLAT flow（最新2399141888/2401799952，末块重试），306014仍依赖旧下载；只有SLAT全文件VERIFIED后才停止旧下载及其依赖、关闭转发5028，保留a12完整文件及缓存，避免重复下载剩余六文件。之后本地上传子集与旧根经新Slurm合并/全量官方校验、新GPU输出身份，不往活跃a12写入。模型执行源码仍3f9d24f/a22，尚无推理结果。下一轮先确认helper/文件增长；原curl已停，不得重复本地writer。本地首次可见83MB并非完成、也不证明更快；当前没有Stereo训练loss/optimizer/W&B。

20:33已有可用路线并在续传：CPU306009/本机20890转发，GPU306014等待。7999/直连的有界超时不代表所有代理或所有未来直连不可用。当前无需新的代理许可，保持主下载；本地落盘再上传是否更快需看下载+上传两段，1MiB/5.089s小样不足以证明优势，不重复下载已保存缓存。

最新探测已回答7999现状：305961四项7999/直连探测全超时，当前不能以切回7999恢复。是否另一个现有VPN/代理出口更稳定尚未实测，不擅自切换用户VPN或系统配置。完整权重下载仍待可用网络。

20:08待查证：7999代理当前能否通过HF TLS/小文件/Range探测，CPU305961已排队，尚无结果。旧转发20890路线失败不能当7999失败的最新证据，也不能用本机VPN开关推断集群下载会更快。无需重复下载授权。

19:26既有连接现已恢复并验证新字节下载：当前本机代理20890、新CPU305841、新GPU305845等待。仍须观察稳定性；完整权重和单卡模型尚未完成。最新身份以RUN_STATUS首段为准，无新增授权问题。

19:02确认恢复作业305794失败、305798取消，当前不在正常下载。已保存缓存，外部关键缺项仍是稳定的本机/集群连接；未发现新的下载资产要求。

18:59关键外部缺项为稳定的集群SSH/代理连接：新转发23722和4952均超时，旧本机代理仍配置7890。自动继续诊断既有连接，不猜新主机、不开新代理、不再询问权重下载授权。若网络侧需用户恢复校园/VPN连接，必须明确按实际超时证据请求，不能冒称资产缺失。

18:54更正：旧305609因连接中断失败、305611取消；本机重启时间与转发消失一致，后继CPU305794恢复通道及续传，不是新增资产或下载授权问题。目前没有发现官方bundle之外必需的新大型下载；训练目标、loader/target/split及训练日志仍需闭合。最新运行身份以RUN_STATUS首段为准。

17:31状态更正：305577网络超时FAILED、305583依赖取消。后继305609/305611和a9权重根详见RUN_STATUS；并发4→1只检验代理争用，尚不能保证解决上游停滞。下载授权已解决，不再重复询问。

## 需要用户决定

1. 已解决：用户明确允许在Slurm计算节点下载大型资产，禁止登录节点下载。固定官方版本 `hbb1/Cupid@1191de37cc33b60273a631d4e07fbbe7cee798c1`，逐文件校验官方SHA。17:21恢复作业为305577（复用4个校验通过权重并越过旧分块断点），单卡依赖305583；完整receipt仍DOWNLOADING，无需再次请求下载授权。DINO已找到，不需要上传数据集。
2. 训练路线：先拿原权重Stereo V1结果再确定微调；继续独立HSSD原方法训练；还是训练Stereo新模块？最后一种需要明确训练模块和监督目标。不能用原方法的单目训练冒充Stereo模型训练。

## 可继续查证，不是新增人工审批

- 历史renderer精确版本：当前脚本10帧与样本25帧不一致，存在单列翻轴反射。需要从历史源码/输出provenance闭合相机绝对坐标，不影响首先做相对标定推理诊断。
- Blender importer轴变换与物理扫描单位：可做CPU解析/无渲染导入检查，不能把scene_unit称m。
- 首对以外的数据质量、1025条planned记录实际完成率：本次不做大范围数据读数，也不把manifest计划数量当渲染总数。
- 完整模型采样、UV对应准确性、Stage2 mesh和尺度误差：必须在真实权重上运行；静态代码和理想几何测试不能回答。
- Stereo S07 evaluator需设计pose/scale/UV指标；已有W&B代码与本分支blob一致，但现有训练test/pose=N/A。

反思：最易混淆的是“已有合成stereo”与“完整标定/米制GT已验证”，以及“旧HSSD训练运行过”与“新Stereo代码验证通过”。当前最实质的不确定性是完整预训练pipeline资产与历史相机反射的准确语义。

## 2026-09-21 01:26 首次24小时停滞报告

V1保持S03/DEBUGGING、highest S02，STALLED_24H=YES；阶段时间仍2026-09-20 01:26，不因下载、代码或文档更新重置。最新SSH证据：2026-09-21T01:26:51+08:00 endpoint=ricky@10.10.7.1 strict_hostkeys=yes connect_timeout_seconds=12 attempts=1 exit=255 first_failed_predicate=PRE_BANNER_CONNECTION_CLOSED message="Connection closed by 10.10.7.1 port 22" remote_shell=NO new_jobs=0 network_configuration_changed=NO

R持续每5分钟有界检查；连接恢复立即fresh queue/incoming审计→固定A4 CPU37/Panda125→上传和25文件新根校验→冻结V1单卡。当前0项新测试/0新job/无模型结果，A4静态完成不是运行PASS。D继续真实canonical/renderer/properCV证据责任。用户校园网/VPN入口状态仍未确认；不修改配置或接受未知主机密钥。停滞报告不暂停；下一检查约5分钟，下一24小时报告阈值2026-09-22 01:26。完整包STALLED_24H_20260921.json，E00发送回执单独记录。
