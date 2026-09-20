# 当前运行状态

**首批已集成并转CPU检查：** I的4de419aa/tree53f68678已集成D/L/R并push exactread（worker回执），无冲突且冻结五路径无diff，仅静态非测试。已立即交R源接口检查与1pair数据检查；L的a8f275d新增11项CPUfixture/evalhook/readback、R的71967e资产审计与选择上传已交I继续集成。当前监控切到R最小CPU包及I后继集成，不等T训练器完工；SSH仍是实际运行外部阻碍，尚无新增测试/GPU结果。

**五任务首轮自动交接：** D已交e05bb99原始pair接口、L已交b526495 logger/evaluator接口（worker报告push/exactread）；已立即派I精确集成、T接入。T报告真实训练engine/DDP/checkpoint代码已写但尚未提交/实跑，不能计S02完成。D继续targetfactory、L继续CPUfixture/readback、R继续SSH/运行准备。当前重点已从等待初始实现切到首批集成；详细负责人见CAMPAIGN_TASKS.json。

**2026-09-21新增授权：五个独立任务已开始并行补齐训练缺口。** D数据、T训练器、L日志评估、R集群上传/唯一GPU运行、I集成晨报，真实thread/worktree/branch见CAMPAIGN_TASKS.json；工作顺序与自动修复交接见CONTINUOUS_EXECUTION.md。目标2026-09-21 08:00晨间可核验产物。用户已明确要求阶段完成自动推进、失败修复重试，旧“单卡后暂停等审核”仅历史状态，不再是本轮自动停止点。V1冻结推理基线保留，训练候选另立STEREO_CUPID_STAGE1_TRAIN_V1；没有继承已训练结果。用户目标选择仍可覆盖，暂按官方Stage1监督微调候选实现验证，真实GT/target/样本/steps配置必须落地，不能用toy或HSSD冒充。R独占本campaign GPU提交（先1卡smoke、再2卡DDP、正式优先1卡）；控制器不同时提交。

**2026-09-21 00:22：本地六个剩余权重全部下载完成并通过官方SHA，共4168403480字节。** `local_transfer_receipt.json` 为LOCAL_SUBSET_VERIFIED_UPLOAD_PENDING；PID33142正常完成退出，transfer_a5_download.log含六个LOCAL_VERIFIED。集群a12另有五个已校验权重3099847620字节，两地合计11个权重7268251100字节。仍未形成集群25文件完整root，不能把分散权重齐备称集群模型可用。ClashX7890完成剩余5文件约3分钟，观察到本次路线明显快于旧CMY传输，但不推断唯一根因。

上传阻塞仍为SSH：00:22再次Connection closed by10.10.7.1 port22。没有远端shell，无法核查先前上传是否留下job/incoming；不盲重提交、不安装、不改SSH/VPN/路由。用户校园网/VPN状态问题待答；下一轮先恢复只读SSH并审计上传job与目标，随后只上传已有校验文件，禁止重新下载完整权重。上传后在Slurm新根合并a12和local_upload_a1，补小JSON并全25文件官方SHA/pipeline引用校验，再新1GPU。当前没有任何Stereo模型运行/训练结果，最高S02，S03 DEBUGGING。

**2026-09-21 00:19：SUV flow 2239067672字节及SS decoder147591972字节已本地官方SHA通过，尚未上传成功。** CMYNetwork/MaccCore20890已关闭，scutil显示系统代理禁用；实测现有ClashX7890监听且官方API HTTP200/1.63秒。旧21404进程组已停止、lsof确认无writer后，新32204通过7890续传原2125938534断点并完成SUV SHA。上传SSH返回Connection closed by10.10.7.1 port22，32204已失败退出，日志transfer_a4.log，receipt为UPLOAD_UNVERIFIED；不能推断远端文件是否创建。三次SSH检查均在banner/keyexchange前关闭，TCP连接建立但无远端协议串。route只读显示10.10.7.1经utun8/gateway198.18.0.1，不能直接认定代理是唯一根因。未改VPN/SSH/系统配置，已向用户询问校园网/VPN是否仍连接。

为避免SSH故障阻塞其它下载，源码972bc8e61bd0d453864afc1d25b38382b8db1ea6已push/精确读回，新增显式--download-only：保留全部本地官方SHA及上传待办，不把本地完成当上传完成。新独立helper PID33142，日志transfer_a5_download.log，进程receipt transfer_process_a5.json，ClashX7890，从本地已校验SUV继续余下5文件；SS decoder已完成，SS encoder下载中。目标local_upload_a1不变但当前--download-only不提交上传job；待SSH恢复后先fresh squeue/sacct/远端incoming审计避免重复，再完成上传。旧306009/306014/5028不恢复。完整pipeline/root、模型运行、Stereo训练仍未完成。

**21:50本地续传已实际恢复至495266996字节。** 21:51消息工具恢复，E00完整包已发送；现已收到E00中央台账回执：commit8f076d9661a9ec255af4f6ca29fd54f89da8b3ce/treee2a37a7e59e7e6feb114479fd228c158ce41431e，E00报告GitHub exact-read PASS，仍S03/DEBUGGING、highestS02、NO_SCIENCE。

**21:49恢复操作。** 原exec70764不存在，pgrep/lsof确认helper及该partial的writer均已退出；Mac未再次重启（boot18:34:57）。日志最后为HTTP/2 CANCEL/exit92，没有Python异常，因此工具会话消失与进程退出的具体因果仍未知。保留SUV partial304848052字节；本机20890仍由CMYNetwork/MaccCore监听。源码46e2d022e36eae00de007f75101e683e8efb1680已push/精确读回，将curl显式设HTTP/1.1以针对已观察HTTP/2重置；长期网络稳定性尚未证明。新helper PID21404以独立进程会话运行（start_new_session、stdin DEVNULL、fcntl锁），日志`transfer_a3.log`，进程receipt`transfer_process_a3.json`，继续同一partial，不重复下载已保存字节。无新Slurm/GPU提交，无上传成功证据；旧306009/306014/5028仍结束。

**21:36切换完成：集群SLAT flow 2401799952字节已VERIFIED。** 旧CPU306009已CANCELLED（1h5m48s），旧GPU306014已CANCELLED（0秒无节点），旧转发5028退出255、已关闭。这是用户要求本地下载上传后的主动切换，不是模型失败。a12保留5完整权重共3099847620字节；完整receipt仍非VERIFIED，余下六权重由本地helper70764续传。最新本地SUV partial166324845字节，已超过原83143277断点；本地完整SHA、实际上传和1GPU尚未完成。不得恢复旧306009/306014/5028。上传目标仍独立local_upload_a1，helper每文件在Slurm CPU分配接收/复核；最终须新根合并全量校验再提交新1GPU。

**21:33用户明确改为本地下载后上传集群，已实际开始。** 本地根 `/Users/ruikegu/Downloads/Cupid_official_1191de37_local_a1`，CMYNetwork/MaccCore既有代理127.0.0.1:20890。首个SUV flow持久化83143277字节后HTTP/2 CANCEL中断；文件保留，原exec83692终态92。官方manifest初次获取超时导致首helper启动缺文件，重取固定revision成功后，前台helper exec70764续传（`transfer_a2.log`），没有安装依赖。helper源码6b35172d38393d62b0dad623de899d1484246436已GitHub精确读回；只处理六个剩余官方safetensors，逐文件本地官方SHA后，通过独立1CPU/1GB/1h的Slurm srun接收及复核上传SHA，不在登录节点落盘/哈希。计划上传根 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_local_upload_a1`，尚无上传成功证据。每次incoming新身份、最终硬链接拒绝覆盖，保留失败证据；这是子集而非完整pipeline。

集群306009/a12继续完成当前SLAT flow（最新2399141888/2401799952，末块重试），306014仍依赖旧下载；只有SLAT全文件VERIFIED后才停止旧下载及其依赖、关闭转发5028，保留a12完整文件及缓存，避免重复下载剩余六文件。之后本地上传子集与旧根经新Slurm合并/全量官方校验、新GPU输出身份，不往活跃a12写入。模型执行源码仍3f9d24f/a22，尚无推理结果。下一轮先确认helper/文件增长；原curl已停，不得重复本地writer。本地首次可见83MB并非完成、也不证明更快；当前没有Stereo训练loss/optimizer/W&B。

**20:33已恢复续传，并行探测不再阻塞下载。** CPU **306009 RUNNING server14**，GPU **306014 PENDING afterok:306009**、kill-on-invalid-dep=yes。当前可用路线为计算节点loopback49694→SSH→本机实测20890代理；前台转发exec **5028**，严格既有主机密钥 `/tmp/stereo_cupid_hostkeys.VcqF15`，未改SSH/系统/VPN配置。4完整权重698047668字节及旧SLATflow1589641216字节复用后，20:33:25已到1598029824，实际新增8388608字节；完整receipt仍DOWNLOADING，最高S02。当前有可用路线，不能把7999/直连失败概括成所有代理不可用。

运行源码 `3f9d24f7945e7de4e7c7a33ce2a00a33fac16f5d` / tree `6e10d28bb9d579b6725e8d685f545dde3c7f3ecf`，新checkout `/public/home/ricky/CODE/stereo_cupid_3f9d24f_a22`；新权重根 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a12` 只读复用停止a11。单卡新输出 `/public/home/ricky/RESULTS/STEREO_CUPID_PILOT_3F9D24F_A8`，1GPU30min完整Stage1+左Stage2，既有Panda/DINO/scene_unit。代码只将临时网络错误的重试恢复窗口扩至10分钟，使5分钟跟进有机会重连；每请求时限和全部校验保留，非网络完整性错误仍5次耗尽。已真实执行新分块传输，超5次后重连的分支尚未实测，不宣称长期稳定。

使用该分配中的1CPU srun --overlap同时检查7999/直连，两者config/1MiB Range仍HTTP000/bytes0/exit28，但未停止主下载。用户提出本地下载再上传，本次仅在本机做1MiB公共文件连通/速度样本：HTTP206，5.089秒，丢弃内容；不改变主权重只写集群的路径。整套7.27GB、当前单文件2.40GB，本地中转是否更快尚无完整吞吐/上传证据；现有下载已借用同一本机代理，先落本地未必加速，但能将HF下载与SSH断线分开。证据 `audit_20260920/network_resume_306009.txt`。a21同步即时配置检查失败，后续只读匹配但仍保留partial未使用；独立a22全部通过。

**最新探测终态：305961 COMPLETED0:0（server14/19秒），但四项网络探测全部失败。** 7999代理与直连访问官方config/1MiB权重Range，均HTTP000、bytes0、curl exit28（连接超时）；探测脚本正常结束只表示记录完成，不能称路线可用。结果 `audit_20260920/transport_305961.txt`。因此不能宣称换回7999会恢复或加VPN一定更快。当前下载305841已失败、305845取消、49409退出，无健康下载；保留a11缓存。下一步需恢复并验证可用的既有代理线路，再按新身份续传；不在登录节点测试大型下载、不盲重提旧失败路径。E00完整包已记录探测终态，消息工具尚不可用。

**20:08当前：下载305841于19:45:30 FAILED1:0（20m24s），305845依赖取消、0秒无GPU。** SLATflow已保留1589641216字节，另有4完整权重698047668字节；首次末段错误SSLError，后续ConnectionError/ProxyError，转发49409已退出，不能称仍在下载。用户询问7999代理后新增有界CPU探测作业 **305961**，最新PENDING、尚无分配/结果，不重复提交。探测只从Slurm计算节点比较 `http://hkuhpc.com:7999` 与直连，读取官方pipeline.json和至多1MiB权重Range，丢弃响应体，只记状态/字节/时间/退出码；不是权重完整校验或下载速度保证。

探测源码 `b93bbf64c8acf1c96ccfa01c90f9b73d7065423f` / tree `1eb990de873a1610d40078099bd85178a0b17e81` 已push并同步至 `/public/home/ricky/CODE/stereo_cupid_b93bbf6_a20`；唯一新增代码 `scripts/probe_cupid_transport.sh`，模型和下载算法未改。旧本机转发路线实际export为计算节点loopback49693，经SSH到本机20890，并未使用7999；脚本默认7999但由CUPID_DOWNLOAD_PROXY覆盖。7999此前TLS失败，当前能否使用等待305961实测；不能断言加VPN更快。所有大权重仍只写集群。

**19:26已实际恢复下载：CPU305841 RUNNING server14；单卡305845 PENDING Dependency。** 19:23本次SSH成功，旧305794/305798终态且squeue无本实验活动作业。本机 `scutil --proxy` 显示当前HTTP/HTTPS代理为127.0.0.1:**20890**，`lsof`确认该loopback端口监听；与此前7890不同，何时切换未核验。本次转发使用实测当前20890，不改系统/SSH/代理配置。4完整权重698047668字节已重新VERIFIED_REUSED，SLAT flow复用1312817152字节后于19:26:02实际达到1329594368字节，新增16777216字节；不能把缓存算新增流量。完整receipt仍DOWNLOADING，最高S02，模型未执行。

运行源码 **40c09dc779f636df1a2c41781b5699e4043fc763** / tree **a71680c5af7855f71dc34c49a0b8d0c3d48a45a0**；下载及模型算法未变。GitHub→verified bundle→新checkout `/public/home/ricky/CODE/stereo_cupid_40c09dc_a19` 核验通过。新权重根 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a11`，只读复用停止a10。单卡依赖afterok:305841、kill-on-invalid-dep=yes，1GPU30min完整Stage1+左Stage2，新输出 `/public/home/ricky/RESULTS/STEREO_CUPID_PILOT_40C09DC_A7`。

当前前台SSH反向转发exec session **49409**：实际分配server14的127.0.0.1:49693→本机127.0.0.1:20890；严格使用既有主机密钥文件 `/tmp/stereo_cupid_hostkeys.VcqF15`。下载终态关闭连接。若再次中断，先确认实际代理端口与监听及Slurm节点，再按既有认证恢复；不猜端口/主机，不重复提交健康作业。短时恢复不代表长期网络故障已完全解决。E00工具仍缺，完整进度包继续保存待发送。

**19:02终态读回：305794 FAILED1:0（4m5s），305798 CANCELLED0秒、未分配GPU。** 同一offset1312817152连接失败，没有越过旧断点。两个临时转发均已退出，当前没有正在成功传输的下载作业。保留a9/a10全部缓存和日志；主要阻塞是本机到集群及代理的间歇连接。下一轮先恢复并验证既有网络通道，再按新作业身份续传；不得把这个终态当健康RUNNING或声称已完成下载。自动跟进保持启用，不需要新的下载授权。

**18:59连接再次失败，不能称下载恢复。** 新CPU305794最新18:58:58读回RUNNING server14，但offset1312817152连续ReadTimeout/ConnectionError，尚未看到超过旧根的新字节；新GPU305798 PENDING Dependency。转发23722因server14不响应退出255，按同一已分配节点重建的4952也在banner交换超时退出255；无存活转发。登录节点只读SSH也多次超时，当前主要阻塞是稳定的集群网络连接，不能通过重提作业解决。继续先读fresh sacct，再仅在实际分配仍有效时恢复转发；不重复305794/305798，未查终态不换根重提。最后明确的模型状态是未运行。E00完整包已保存 `audit_20260920/E00_PROGRESS_PENDING.json`，消息工具缺失尚未发送。

**18:54故障恢复：305609于18:36:27 FAILED1:0（1h5m26s），305611依赖取消、0秒无GPU。** 首失败offset1312817152，ConnectionError后4次ReadTimeout。本机 `sysctl kern.boottime` 为18:34:57；旧exec98390、SSH转发进程及/tmp主机公钥文件均已不存在，支持本机重启导致转发消失的判断，不是权重SHA错误，也不能归因于并发1失效。保留4个完整权重698047668字节及1312817152字节分块，共约2.01GB/7.27GB；剩余约5.26GB。先前4–6小时估计偏乐观，按最近一小时有效速度约7–10小时纯下载，排队/中断另计，不能承诺ETA。

恢复不改模型或下载算法：已有GitHub源码 `e1bd1ed462978616cb5c68123059d9c1f3c9ad4a` / tree `3fec0a2d41dd8f4312e65a583deccc56c16e3d41` 已通过bundle同步新checkout `/public/home/ricky/CODE/stereo_cupid_e1bd1ed_a18`；下载器blob与cbb4cbf相同。新CPU **305794**，新根 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a10`，只读复用停止的a9；将重建失去的转发49692，开头等待代理600秒。新公钥临时文件 `/tmp/stereo_cupid_hostkeys.VcqF15` 来自登录节点既有known_hosts，严格验证，不改SSH配置。最终节点/转发/单卡身份以本文件后续首段为准。

本次另实查DINO repo可读、checkpoint1217607321字节、Python可执行、Panda metadata可读、GSO_1K_200目录存在。静态Stereo入口使用本地DINO且要求RGBA，当前完整官方bundle之外未发现新增大型资产必需项；仍需真实推理确认。Stereo训练loader/split/target、loss/optimizer及W&B/pose evaluator仍未实现，不能把下载完成当训练就绪。新工具清单暂缺send_message_to_thread，E00完整进度包将保存待发送，不能称已同步中央台账。

**17:32实测恢复：305609 RUNNING server14，305611 PENDING Dependency。** 新转发exec session **98390** 已按实际分配节点建立：server14 loopback49691→本机既有7890，严格既有host key；下载终态后关闭。4个完整权重已VERIFIED_REUSED；SLAT flow在复用528482304字节后已到557842432，越过541065216旧失败offset。receipt仍DOWNLOADING，单路网络是否长期稳定尚待观察。heartbeat已经指向305609/305611，不重提。新运行身份和恢复原因见下段；证据 `audit_20260920/download_305609_recovery_1732.txt`。

**17:31再恢复：305577 FAILED1:0（7m39s），305583取消、0秒无节点。** 首失败为offset541065216连续5次ReadTimeout；另3路并发连接也无完整分块进展，300秒总时限没有解决网络停滞。已保留4个完整校验权重698047668字节及SLAT flow分块528482304字节，合计约1.23GB；全套仍未完成。源码 `cbb4cbf75233fb7fa8602625a01c17ed7fc345f7` / tree `5bf38b04f947a423ecf2085f4dda55bdc339e04f` 将并发4→1，检验共享代理争用假设，尚不能称根因已验证；4MiB持久化、时限、重试和全文件SHA保持不变。GitHub精确读回及新checkout `/public/home/ricky/CODE/stereo_cupid_cbb4cbf_a17` 已通过。新CPU **305609** 已提交，新权重根 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a9`、只读复用a8；新单卡 **305611**，afterok:305609/kill-on-invalid-dep=yes，输出 `/public/home/ricky/RESULTS/STEREO_CUPID_PILOT_CBB4CBF_A5`。旧转发98813已结束；新端口49691须按实际分配节点建立。最新待分配/连接状态见后续记录，禁止重复提交。过去成功传输速度只能粗估剩余4–6小时，网络停滞及排队会额外延长，不能承诺完成时间。

**17:21恢复已实际验证：305577 RUNNING server14；新单卡305583 PENDING Dependency，afterok:305577，1GPU/30min，尚无GPU分配。** 新下载已重新校验并复用4个完整权重（698047668字节）；SLAT flow分块从旧根复用406847488字节后，已推进至524288000/2401799952字节，越过旧作业失败位置。完整receipt仍为DOWNLOADING，不能称全量权重完成。运行源码仍为下述a8e799e/a16；单卡新输出 `/public/home/ricky/RESULTS/STEREO_CUPID_PILOT_A8E799E_A4`。临时SSH转发exec session **98813** 存活：实际分配节点server14 `127.0.0.1:49690` → 本机既有 `127.0.0.1:7890`，严格校验既有主机密钥，未改配置。下载终态后关闭转发。禁止重复提交305577/305583；heartbeat已更新为这两个作业。证据 `audit_20260920/download_305577_recovery_1721.txt`。最高完成S02、当前S03 DEBUGGING；仍无模型smoke或Stereo训练结果。

**17:15恢复：305505 FAILED 1:0（50m14s），305510依赖取消、0秒无节点。** 首个失败条件为SLAT flow权重offset406847488的4MiB分块在5次尝试中触发90秒总时限，完整权重SHA未出现不匹配。代码 `a8e799ee815b061283cf38804a30ea0db13a9fa4` / tree `5ea1c8cf383be78abdc7f7dbaf86c0d32386fd60` 将单块总时限改为300秒，保留40秒socket读超时和全部完整性检查；已push并同步至 `/public/home/ricky/CODE/stereo_cupid_a8e799e_a16`。新CPU下载 **305577** 已提交，权重根 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a8`，只读复用已停止a7中的完整权重及持久化分块。旧session27758已随作业结束关闭。失败证据 `audit_20260920/download_305505_terminal.txt`。完整权重、模型smoke仍未完成。

**16:31重查：第二个完整权重 `slat_dec_mesh_swin8_B_64l8m256c_fp16.safetensors`（181903412字节）已通过官方SHA，正在下载第三个RF decoder。** 中途若干Range出现ReadTimeout/RANGE_DEADLINE，下载器自动重试后完成该文件，未重提305505、未重下已落盘分块；本次实际验证了超时恢复。session27758仍存活，日志更新至16:30:45；305505 RUNNING、完整receipt仍DOWNLOADING，305510 PENDING且无GPU分配。脱敏证据 `audit_20260920/download_305505_retry_recovery_1631.txt`。最高完成仍S02，没有模型运行结果。

**16:23实际验证：305505的首个完整权重 `slat_dec_gs_swin8_B_64l8gs32_fp16.safetensors`（171450952字节）已通过官方SHA校验，继续下载下一文件。** 证明新Range实现完成了真实分块传输、拼接与全文件校验；其余权重仍未齐备，305510仍PENDING Dependency。脱敏记录：`audit_20260920/download_305505_verified_snapshot.txt`。

**16:20恢复更新：CPU下载305505 RUNNING server14；单卡305510已提交，依赖afterok:305505。** 旧305474因SSH转发超时、Xet长时间无进展而取消（29m58s）；旧305481取消，0秒无节点，未执行模型。新代码 `94c4d0550e077977ec650f15c972b5b9ef8ce891` / tree `bc02ca8ebe94a796fd3bb39127b24008a5347a1f` 已通过GitHub→集群同步，checkout `/public/home/ricky/CODE/stereo_cupid_94c4d05_a15`。改用4MiB HTTP Range、Content-Range/字节数检查、每块落盘并记录摘要、完整文件官方SHA校验。新权重根 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a7`，只读复用已停止a6中校验通过的文件；原数据保留。临时转发exec session **27758**，server14 `127.0.0.1:49689` → 本机既有 `127.0.0.1:7890`；旧7388/55431连接已结束。新单卡输出 `/public/home/ricky/RESULTS/STEREO_CUPID_PILOT_94C4D05_A3`。当前仅分块下载已实际验证，尚未完成全部权重校验或模型smoke。

**16:00更正与数据/日志核查：用户明确限制的是“不得在登录节点下载大型资产”，不是全面禁止大型资产。允许在Slurm计算节点下载所需官方资产；不再设置额外下载确认。** 本次下载确实在server14的Slurm作业内。训练数据与W&B核查见 `audit_20260920/DATASETS_AND_LOGGING.md`：Stereo主训练候选为GSO_1K_200（实查903个顶层对象目录，非1025个已完成对象）；当前smoke仍用Panda125对小集。原CUPID训练默认HSSD，有W&B和TensorBoard训练loss记录；当前Stereo推理入口没有接入W&B，Stereo训练loss、val/test loss、pose error曲线尚未实现，不能标完成。

**15:56 CST最新：单卡作业305481已提交，PENDING(Dependency)，`afterok:305474`且失败依赖自动取消。** 1GPU/30min，完整Stage1+左Stage2 mesh；源码 `2fa36a1180c3f57480c6597c4bcf2df044a4059c` / tree `258e1deabfb6299d335b68887a4f7260377b0a3e`，已同步checkout `/public/home/ricky/CODE/stereo_cupid_2fa36a1_a14`；新输出 `/public/home/ricky/RESULTS/STEREO_CUPID_PILOT_2FA36A1_A2`。当前305474仍下载中，305481没有节点、没有模型执行。heartbeat已更新为跟踪这两个作业，不重复提交。之后的纯文档提交不改变这两个作业绑定的运行源码。

## 2026-09-20 15:52 CST 更新：官方权重下载中

用户已明确授权下载官方权重，无需再次确认。最高完成仍为 S02，当前 S03/DEBUGGING；真实模型尚未执行。

- 官方源：`hbb1/Cupid@1191de37cc33b60273a631d4e07fbbe7cee798c1`。官方清单25文件、7,268,259,545字节；下载后独立核验LFS SHA256/小文件Git blob SHA1。
- 当前 CPU 作业 **305474**，server14，RUNNING；输出 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a6`。`download_receipt.json` 尚非 VERIFIED。大文件在Xet内部分块传输，不能用未完成文件大小推断完成比例；网络较慢且仍可能失败。
- 运行源码 `bc458f27e14cf6fc999506846d2fb386cbb95bec`，tree `e57415a208203e76085ed535f90a26054908dcec`；checkout `/public/home/ricky/CODE/stereo_cupid_bc458f2_a13`，GitHub及远端同步核验通过。
- 复用已安装的官方 `huggingface_hub`/`hf_xet`，未安装依赖。固定版本、逐文件哈希及完整pipeline引用检查仍保留。
- 集群既有代理与直连均无法完成HF TLS连接；本机既有代理可用。当前通过有认证的临时SSH会话反向转发：Slurm节点server14的 `127.0.0.1:49688` → 本机既有 `127.0.0.1:7890`。本任务exec session `7388` 持有该前台连接；权重仅写集群，不修改SSH或代理配置。下载结束后关闭连接。临时主机公钥文件 `/tmp/stereo_cupid_hostkeys.Fzi11a` 来自登录节点既有known_hosts，用于严格校验，未接受未知密钥。
- 下载305442：缺charset_normalizer，已通过现有完整overlay修复。305444：旧代理TLS失败。305453：集群7890代理TLS失败、直连失败。305462：临时端口连接失败。305465：HTTP长流中断后重试，替代客户端确认分块传输后主动取消，旧根a5保留、旧转发关闭。
- GPU依赖作业305446在305444失败后取消，0秒、无节点、无模型执行。未把该作业当作单卡验证。
- 同步a10/a11导入后即时检查失败，保留partial未运行；后来只读检查均通过，首个瞬时失败条件未定位。项目同步helper已原样纳入本仓库并增加失败命令诊断；新a12/a13完整通过。不能声称已查清或修复a10/a11根因。
- 跟进 automation `stereo-cupid` 已启动，每5分钟在本任务检查并推进；状态无变化时静默。下载全量校验后提交1GPU/30min完整Stage1+左Stage2 mesh，首错修复、GitHub同步、新checkout/输出重跑。模型smoke尚不等于训练。

当前无需用户再确认下载。剩余技术步骤：权重下载/校验 → 真实单卡推理/mesh验证。训练模块、监督loss和训练数据协议仍待后续科学决策，不能擅自提交不对应本V1的完整训练。未更新正式结果Slides。

以下为此前CPU审计记录；其中“下载授权待确认”和“smoke尚未提交”已由上述更新取代。

2026-09-20：集群SSH已经恢复，已真实同步并在Slurm计算节点验证。旧00:41“无远端shell”的状态已过时，历史仍保存在Git。

- 实验：STEREO_CUPID_V1_SHARED_SS；最高完成S02。
- 已通过运行代码：238fe8ac2d882dd7c54e2190eaa52df44db5361a，tree fbda08ce0c670f20aeb6bd54a2a509545f9a30b6。
- 集群checkout：`/public/home/ricky/CODE/stereo_cupid_238fe8a_a4`。
- CPU304070：样本读取成功，8测试通过/2个rembg导入错误，FAILED1:0。
- 修复延迟导入后CPU304071：server14，COMPLETED0:0，11项通过。
- 原始OBJ、renderer、小集路径已找到；Panda小集1对象5轨迹125对，首对含RGBA/深度。数据与代码漏洞详见审计报告。
- 历史记录：当时完整hbb1/Cupid pipeline路径未知，曾询问约7.27GB下载授权；将限制写成全面禁止大型下载不准确，已按用户澄清更正为禁止在登录节点下载。
- Stereo训练目标待用户选择。现有V1是预训练推理，没有新optimizer/loss；不能将原HSSD训练或CPU测试当Stereo训练证据。
- 原HSSD296164已PREEMPTED，日志到42000/1000000；不重提其它任务训练。

三份报告：`audit_20260920/INSPECTION_REPORT.md`、`OPEN_QUESTIONS.md`、`NEXT_SESSION.md`；同目录保存脱敏命令、同步receipt和测试/样本读数。E00已登记独立实验，现有logger/readback代码blob与E00一致，无需重复merge。

仍无Stereo科学结果、DDP通过或完整训练结果；未更新正式结果slides。下一动作是解决完整权重入口并提交1GPU/30min单对推理smoke。所有实验/测试继续只在Slurm计算节点进行。
