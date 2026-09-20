# 当前运行状态

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
