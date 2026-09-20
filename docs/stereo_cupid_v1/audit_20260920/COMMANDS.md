# 脱敏命令记录

日期2026-09-20；命令仅记录与本实验有关的读取/同步/作业。未打印环境变量总表、token、SSH私钥、W&B凭据；未复制原始图像、深度或OBJ到外部服务。文件清单只记录有界范围，未扫描其他主机。

## 入口与规则

```sh
cat /Users/ruikegu/.codex/AGENTS.md
cat /Users/ruikegu/Documents/Codex/2026-09-20/xian/outputs/default.rules.txt
git status --short
git rev-parse HEAD
git fetch origin codex/metric-scale-controller-cleanup # 在E00所属XFactor仓库读取规则
git ls-remote origin refs/heads/codex/metric-scale-controller-cleanup
git show d88b19e0414aaf482b21f5630b64df604dc2c57a:AGENTS.md
git show d88b19e0414aaf482b21f5630b64df604dc2c57a:docs/controller_work/IDEA_EXPERIMENT_10_STAGE_PROGRESS_RULE_V1.zh-CN.md
git show d88b19e0414aaf482b21f5630b64df604dc2c57a:docs/controller_work/METRIC_SCALE_RESEARCH_OPERATING_SYSTEM.md
```

长规则文件工具显示曾截断；随后按章节/关键词补读当前适用内容，没有把截断输出称作全文逐行检查。

## 集群只读

```sh
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 ricky@10.10.7.1 'hostname; pwd; ls -d */; /opt/gridview/slurm/bin/squeue -u ricky -o "%.18i %.12P %.40j %.10T %.20N"'
ssh ricky@10.10.7.1 'find CODE/GSO_dataset -maxdepth 2 -type f; ls DATASET | grep -i gso'
ssh ricky@10.10.7.1 'cat CODE/GSO_dataset/README.md CODE/GSO_dataset/ENVIRONMENT_SETUP.md'
ssh ricky@10.10.7.1 'sed -n "364,485p;1750,1782p;2415,2505p" CODE/GSO_dataset/render_stereo_gazebo.py'
ssh ricky@10.10.7.1 'cat CODE/GSO_dataset/scripts/test_random_linear_trajectory.sh'
ssh ricky@10.10.7.1 'find DATASET/Gazebo/Android_Figure_Panda -maxdepth 4 -type f -printf "%p %s bytes\n"'
ssh ricky@10.10.7.1 'cat DATASET/Gazebo/Android_Figure_Panda/model.sdf'
ssh ricky@10.10.7.1 'cat DATASET/gso_stereo_output_random/Android_Figure_Panda/random_linear_0/trajectory_info.json'
ssh ricky@10.10.7.1 '/opt/gridview/slurm/bin/sacct -j 296164 -X --format=JobID,State,ExitCode,Elapsed,NodeList; tail -25 RESULTS/cupid_gl_full_v7_296164.out'
ssh ricky@10.10.7.1 'git -C CODE/Cupid_0905d28_a64_s08_v2 rev-parse HEAD; git -C CODE/Cupid_0905d28_a64_s08_v2 status --short'
```

结果：mgmtserver01；发现GSO_dataset、Gazebo原模型、小集、大集；原训练296164 PREEMPTED。`CODE/Cupid`不识别为git；可读稳定基线为cc95f36。共享HSSD/GSO目录Permission denied，未更改权限或身份。

模型定位范围：用户 `.cache/huggingface`、`.cache/torch/hub`、CHECKPOINT、ENVIRONMENT、DATASET的有界目录，CODE/Cupid及可读 `/data/haobin/huggingface/hub`；没有找到完整hbb1/Cupid pipeline。DINO源码与vitl14_reg4权重已定位。已命中的路径见报告。

## 同步与故障恢复

1. `git push fork HEAD`，`git ls-remote fork refs/heads/codex/stereo-cupid-v1-20260920`：d709196及238fe8a均成功。
2. 集群 `timeout 45 git ls-remote https://github.com/Jusker-Greek/Cupid.git ...`，使用既有hkuhpc代理；失败gnutls_handshake。
3. 清空仅该命令代理变量并 `git -c http.version=HTTP/1.1 ls-remote ...`；同样TLS失败，没有关闭TLS验证。
4. 已有同步helper初次本地origin仍指官方仓库，branch readback失败，尚未创建远端intent。修复为独立本地Git克隆，其origin明确为用户fork。
5. 使用原项目helper `/Users/ruikegu/.codex/worktrees/ee5e/xfactor_reproduce_overfit/scripts/sync_verified_git_bundle.sh`，本地clean clone `/Users/ruikegu/.codex/worktrees/stereo-cupid-sync-20260920`。

成功首次同步的关键参数：

```text
--work-tree /Users/ruikegu/.codex/worktrees/stereo-cupid-sync-20260920
--branch codex/stereo-cupid-v1-20260920
--expected d70919675d66c98ce3ec401bc6278bd4a2910808
--base cc95f36fc26b5d90054ffd920df6c1c1b54c3e4d
--remote-host ricky@10.10.7.1
--remote-base-checkout /public/home/ricky/CODE/Cupid_0905d28_a64_s08_v2
--remote-mirror /public/home/ricky/CODE/.verified-bundle-mirrors/stereo_cupid_d709196_a2.git
--remote-checkout /public/home/ricky/CODE/stereo_cupid_d709196_a2
--remote-staging-root /public/home/ricky/CODE/.verified-bundle-staging/stereo_cupid_a2
```

d709196增量包29364bytes，SHA256 `85f073a1baab328b57a4b2fd24419b77ce1d36674aab6545b3635f1a60f7ed9b`。修复238fe8a以新d709196为base的a3在即时checkout验证阶段退出1；稍后读到HEAD/tree与diff正常，但无成功receipt，因此未使用/未修复/未删除该partial。具体即时失败条件未复现，不能声称根因已完全证明。

下一次a4改用已稳定的cc95f36基线，expected238fe8a、新mirror/checkout/staging a4；成功。增量包30602bytes，SHA256 `0eea49e8a90bea1a5deb1c336d88acd28032b94cac63fcef7c12be4c9be3fcf4`，独立remote verification已保存本目录。没有远端源码修改。

## Slurm真实执行

```sh
export CUPID_PROJECT_DIR=/public/home/ricky/CODE/stereo_cupid_d709196_a2
export CUPID_EXPECTED_COMMIT=d70919675d66c98ce3ec401bc6278bd4a2910808
export CUPID_OUTPUT_DIR=/public/home/ricky/RESULTS/STEREO_CUPID_AUDIT_D709196_A1
/opt/gridview/slurm/bin/sbatch --parsable "$CUPID_PROJECT_DIR/scripts/submit_stereo_cupid_audit.sh"
```

以上在SSH内执行，返回304070。CPU4/16G/10min，无GPU、固定节点或constraint。提交前squeue与本实验sacct无活动重复，fresh output不存在；scontrol读回PENDING后server14运行，13秒FAILED，原因rembg导入，非数据读数失败。数据JSON完整保留。

修复后同样资源：checkout `/public/home/ricky/CODE/stereo_cupid_238fe8a_a4`，expected238fe8a，fresh output `/public/home/ricky/RESULTS/STEREO_CUPID_AUDIT_238FE8A_A2`，返回304071。终态见复验日志。

CPU计算只发生在Slurm执行脚本内。本地仅编辑、Git、metadata读取、SSH及接收JSON/文本审计结果。原始数据只在集群读取；没有下载资产、GPU推理、训练、批量渲染或后台实验。

## E00

按已应用的十阶段技能向“E00 进度与验收控制”发送完整进度包。E00登记独立实验，并返回3个现有logger/readback blob；本地 `git rev-parse HEAD:<file>`完全匹配。没有修改中央ledger或触发其它任务修改本地Cupid源码。

## 官方权重下载授权后的脱敏命令记录（2026-09-20 15:52 CST）

15:56追加：a14同步2fa36a1180c3f57480c6597c4bcf2df044a4059c通过，bundle SHA256 `090360dc8cbb59e730300cd53bf56fd132f11b0efb5dcc2400649b43f931ab9c`、66452字节。`sbatch --parsable --dependency=afterok:305474 --kill-on-invalid-dep=yes /public/home/ricky/CODE/stereo_cupid_2fa36a1_a14/scripts/submit_stereo_cupid_pilot.sh` 返回305481；readback PENDING Dependency，无节点。环境指向Panda/random_linear_0、a6官方权重、既有DINO、显式scene_unit相对标定，CUPID_FULL_MESH=1，fresh输出STEREO_CUPID_PILOT_2FA36A1_A2。将队列状态与模型执行严格分开。

- 官方API `https://huggingface.co/api/models/hbb1/Cupid/revision/1191de37cc33b60273a631d4e07fbbe7cee798c1?blobs=true`：25文件，7268259545字节。只回收元数据，权重写集群。
- `sbatch --parsable scripts/submit_cupid_weights.sh`：305442(依赖缺失)、305444(TLS)、305453(TLS/直连)、305462(临时代理连接)失败；305465长流发生ChunkedEncodingError，替代客户端启动后scancel取消；305474使用现有HF/Xet，RUNNING server14。每次使用独立输出根，不删旧证据。
- `ssh -N -T -J ricky@10.10.7.1 -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/tmp/stereo_cupid_hostkeys.Fzi11a -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -R 127.0.0.1:49688:127.0.0.1:7890 ricky@server14`：在Slurm确认节点后建立临时前台转发。主机密钥取自登录节点既有known_hosts；没有禁用TLS/SSH验证。
- 305465的2小时下载预算尝试延长到4小时：`scontrol update JobId=305465 TimeLimit=04:00:00` 返回Access/permission denied，没有延长或提升权限。305474仍为2小时；如超时，需保留证据并利用可校验缓存恢复，不把未完成下载说成完成。
- `bash scripts/sync_verified_git_bundle.sh ... --expected bc458f27e14cf6fc999506846d2fb386cbb95bec ...`：a13核验通过；bundle SHA256 `05083a258e39e159ef9cc9bc740055bb8f5a0d6b81d663b9ce0060af65fd70b9`，62213字节。完整参数语义与此前同步记录相同，使用新目标root。
- 远端日志读取仅保留状态、文件名、字节数、错误类别；Xet诊断先去除URL和认证字段，不打印凭据或签名URL。未执行本地测试、未安装依赖、未修改远端源码。
- 本任务heartbeat `stereo-cupid` 已创建，5分钟间隔，持续检查下载并推进单卡推理；无变化静默，完成授权范围后暂停。

## 16:00 数据集与logger核查

通过已有SSH读取DATASET顶层目录；对表中9个GSO根仅执行 `find <root> -mindepth 1 -maxdepth 1 -type d | wc -l`，对两组已定位对象/轨迹有限列举PNG/NPY/HDF5并读取trajectory_info.json。GSO_1K_200注册表1026行含表头，status=planned；损坏清单 `awk 'END {print NR}'` 为4，末行无换行。没有将目录数换算为完整pair数量。

直接读取HSSD已知metadata开头2200字节、stat一个transforms.json和对应latent；ObjaverseXL仅stat两份metadata。未全量解析CSV、未在登录节点加载图像/NPY/权重。对四个本地/远端源码使用 `git rev-parse HEAD:<path>` 核验blob一致。详情与实际路径见DATASETS_AND_LOGGING.md。

## 16:20 下载停滞恢复

- `write_stdin(session7388)`返回SSH timeout；sacct显示305474仍RUNNING，但Xet日志停在08:06:58 UTC，无新的完整权重文件。
- 在实际Slurm节点server14恢复严格认证的临时转发（短暂session55431），计算节点 `curl --proxy http://127.0.0.1:49688 --max-time 20 --connect-timeout 5 -s -o /dev/null -w 'HF_HTTP=%{http_code}' <固定官方pipeline.json>` 返回200；Xet仍无进展。取消305474（29m58s）和依赖305481（0秒无节点），关闭旧转发，保留a6。
- 修复代码94c4d0550e077977ec650f15c972b5b9ef8ce891、tree bc02ca8ebe94a796fd3bb39127b24008a5347a1f，GitHub精确读回和a15同步成功。bundle76170字节，SHA256 f5ed8c82cf5bebf9b3ee1960db8c5c2f3e998d79bd0954d78ca930492c5f5d4e。
- 新CPU `sbatch --parsable scripts/submit_cupid_weights.sh` 返回305505；CUPID_DOWNLOAD_CLIENT=ranges，CUPID_MODEL_PATH=/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a7，CUPID_REUSE_WEIGHTS_FROM=/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a6，CUPID_DOWNLOAD_PROXY=http://127.0.0.1:49689。Slurm实际分配server14后建立session27758转发；实际4MiB range写入、4小文件校验/复用记录逐步出现。
- `sbatch --parsable --dependency=afterok:305505 --kill-on-invalid-dep=yes scripts/submit_stereo_cupid_pilot.sh` 返回305510；相同a15源码，fresh输出STEREO_CUPID_PILOT_94C4D05_A3，1GPU/30min、CUPID_FULL_MESH=1。不能把pending算模型验证。
- 没有运行本地测试或改远端源码；本次运行验证为Slurm内真实HTTP range传输、长度/Content-Range检查及文件SHA流程，完整模型仍待权重齐备。

## 17:21 慢速分块时限修复与复用验证

后续17:32更正：该次305577最终FAILED，305583取消。新恢复详见本文件最后一节，不能继续把上述作业写为运行中。

- `sacct -j 305505,305510 --format=JobID,State,ExitCode,Elapsed,NodeList -P`：305505 FAILED1:0、50m14s；305510取消、0秒无节点。脱敏尾部记录见download_305505_terminal.txt。第一失败条件为offset406847488的4MiB分块5次超过90秒，不是完整文件SHA不匹配。
- 本地修改 `scripts/cupid_range_download.py`：总时限90→300秒，保留40秒socket读超时和5次重试及全部完整性检查。commit/push `a8e799ee815b061283cf38804a30ea0db13a9fa4`，tree `5ea1c8cf383be78abdc7f7dbaf86c0d32386fd60`。既有verified bundle helper从GitHub精确验证后同步至新checkout `/public/home/ricky/CODE/stereo_cupid_a8e799e_a16`；bundle81511字节、SHA256 `8f24832352f47cff892a1ccf8e0f2d833dabbae5fe89cf7e517e339f0ed97c2e`。
- 远端仅提交GitHub同步后的launcher：`sbatch --parsable scripts/submit_cupid_weights.sh` →305577，CUPID_MODEL_PATH=/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a8，CUPID_REUSE_WEIGHTS_FROM=/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a7，CUPID_DOWNLOAD_PROXY=http://127.0.0.1:49690，CPU/4核/8GB/2h。
- squeue确认实际server14后，`ssh -N -T -J ricky@10.10.7.1 -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/tmp/stereo_cupid_hostkeys.Fzi11a -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -R 127.0.0.1:49690:127.0.0.1:7890 ricky@server14` 建立exec session98813；既有公钥文件和既有本地代理，未修改SSH/代理配置。旧27758已结束。
- `sbatch --parsable --dependency=afterok:305577 --kill-on-invalid-dep=yes scripts/submit_stereo_cupid_pilot.sh` →305583，新输出 `/public/home/ricky/RESULTS/STEREO_CUPID_PILOT_A8E799E_A4`，相同a16源码/1GPU/30min/完整Stage1+左Stage2。
- fresh sacct/scontrol、筛选VERIFIED_REUSED和receipt status、tail自定义分块日志，保存download_305577_recovery_1721.txt：四完整权重698047668字节重新校验复用，分块复用406847488字节后已推进到524288000。receipt DOWNLOADING、GPU PENDING；无原始数据/签名URL/凭据记录。forward session98813空轮询仍存活。

## 17:32 并发隔离恢复

- fresh sacct确认305577 FAILED1:0、7m39s，305583 CANCELLED0秒无节点；尾部首错为offset541065216连续5次ReadTimeout，另外3路并发未完成。保存download_305577_terminal.txt。旧exec98813退出255/Broken pipe；不能将上游代理停滞误称已确证争用。
- 本地仅将ThreadPoolExecutor max_workers=4改1，保留4MiB缓存格式/300秒总时限/40秒读超时/5重试/所有SHA检查。commit cbb4cbf75233fb7fa8602625a01c17ed7fc345f7，tree5bf38b04f947a423ecf2085f4dda55bdc339e04f；GitHub→verified bundle→新a17同步通过。bundle87551字节，SHA7a8355dbcb82f7096a6d0258e48de462d57fc7eb7d6f2cc14cde200f65485b4f。
- `squeue -u ricky -h -o "%i %j %T %N"`筛选本实验无旧活动作业；`sbatch --parsable scripts/submit_cupid_weights.sh`→305609，新模型根a9，CUPID_REUSE_WEIGHTS_FROM=a8，代理loopback49691。保持CPU4核/8GB/2h。
- `sbatch --parsable --dependency=afterok:305609 --kill-on-invalid-dep=yes scripts/submit_stereo_cupid_pilot.sh`→305611，新输出STEREO_CUPID_PILOT_CBB4CBF_A5，相同a17源码、1GPU/30min、完整Stage1+左Stage2/Panda/既有DINO/scene_unit标定。
- `squeue -j 305609,305611 -h -o "%i %T %N %R"`实查CPU server14；随后使用与上一轮相同严格主机密钥选项建立 `ssh -N -T -J ricky@10.10.7.1 -R 127.0.0.1:49691:127.0.0.1:7890 ricky@server14`，exec session98390。旧配置未改，文件只写集群。
- 17:32:26只读sacct+筛选VERIFIED_REUSED+tail+receipt status：4完整权重698047668字节重新校验复用，流分块从528482304增至557842432。只有新增加的29360128字节是此处观察的新网络传输，不能把复用缓存计入吞吐。该短时恢复未证明整个网络故障根因已经修复。
- 估时依据：旧恢复成功增量约121634816字节/数分钟，约0.3–0.4MB/s有效速度；剩余约6GB只可粗估4–6小时，不包含失败、排队和恢复。新单路速度样本尚短，不能承诺ETA。使用xfactor-experiment-progress技能同步E00，最高S02/S03 DEBUGGING/NO_SCIENCE不变。

## 18:46–18:57 本机重启后的连接恢复

- fresh sacct发现305609在18:36:27 FAILED1:0/1h5m26s，305611取消0秒无节点；分块停在1312817152，ConnectionError后4次ReadTimeout。保存download_305609_terminal.txt。
- 本地只读 `sysctl kern.boottime`=18:34:57，旧exec98390已不存在，精确转发进程匹配无结果，旧/tmp主机公钥文件也不存在。本机重启切断临时转发的判断与错误时间一致；无权重SHA不匹配证据。本次不改算法或模型，通过恢复实际失去的网络通道继续。
- 新同步已有GitHub e1bd1ed462978616cb5c68123059d9c1f3c9ad4a/tree3fec0a2d41dd8f4312e65a583deccc56c16e3d41，经既有verified bundle helper到checkout /public/home/ricky/CODE/stereo_cupid_e1bd1ed_a18；bundle91098字节，SHA07cb4b6f910c26007222c4ae3bc221754c6419e7c4e1265ef6ee737ca9be1cdf。下载器blob与cbb4cbf相同，无本地测试/模型执行。
- 从登录节点既有known_hosts经已认证SSH读取server14既有公钥，保存在新临时文件 /tmp/stereo_cupid_hostkeys.VcqF15；不扫描/接受新主机密钥，不改SSH配置。
- 旧作业终态和squeue无本实验活动行后，`sbatch --parsable scripts/submit_cupid_weights.sh`→305794。新权重根a10只读复用a9；CUPID_DOWNLOAD_PROXY=http://127.0.0.1:49692，CUPID_WAIT_LOCAL_PROXY_SECONDS=600，CPU4核/8GB/2h不变。
- `sbatch --parsable --dependency=afterok:305794 --kill-on-invalid-dep=yes scripts/submit_stereo_cupid_pilot.sh`→305798；输出STEREO_CUPID_PILOT_E1BD1ED_A6，1GPU30min完整Stage1+左Stage2，其余Panda/DINO/scene_unit参数不变。
- fresh squeue305794确认RUNNING server14后，使用BatchMode/StrictHostKeyChecking=yes/UserKnownHostsFile=/tmp/stereo_cupid_hostkeys.VcqF15/ExitOnForwardFailure=yes/ServerAliveInterval15/CountMax3的 `ssh -N -T -J ricky@10.10.7.1 -R 127.0.0.1:49692:127.0.0.1:7890 ricky@server14`，exec23722。某次只读SSH查询发生连接超时，未重复提交作业。
- 只读test/stat确认DINO repo hubconf.py可读、checkpoint1217607321字节、Python可执行、Panda metadata可读、GSO主数据候选存在。`cupid/pipelines/stereo.py:24`本地torch.hub source=local/pretrained=False，runner要求RGBA，不额外调用u2net。完整bundle之外当前未发现新增大型资产必需项，真实推理仍未运行。
- 工具发现ALL_TOOLS中send_message_to_thread缺失，完整E00包保存E00_PROGRESS_PENDING.json待工具恢复发送；不冒称已更新中央台账，不因通知工具缺失停止下载。
- 18:58:58读回305794 RUNNING/server14、305798 PENDING；下载同一旧断点1312817152连续ReadTimeout后ConnectionError，没有新增分块证据。转发23722随后返回Timeout/server14 not responding退出255；替代4952使用显式ProxyCommand给登录跳板也设10秒ConnectTimeout，banner交换超时退出255。多次登录SSH查询亦timeout。两转发均关闭，不能称已恢复；先解决既有网络并读回终态，不猜测新主机/不重复提交。

## 19:23–19:26 当前代理端口核验与续传

- SSH fresh sacct读回305794 FAILED、305798 CANCELLED，squeue无本实验活动作业。`scutil --proxy`显示HTTP/HTTPS端口20890；`lsof -nP -iTCP:20890 -sTCP:LISTEN`确认127.0.0.1监听。何时由7890切换未核验，不把端口变化推定为全部历史故障原因。
- 使用已push源码40c09dc779f636df1a2c41781b5699e4043fc763/treea71680c5af7855f71dc34c49a0b8d0c3d48a45a0，通过既有verified bundle helper同步新checkout /public/home/ricky/CODE/stereo_cupid_40c09dc_a19。bundle99112字节、SHA30458a637f1f5ca848e9bcb2194fdc51d76b53c8970d3f1badbd1d181b471485；模型与下载算法不变，无本地测试或依赖安装。
- fresh duplicate audit后`sbatch --parsable scripts/submit_cupid_weights.sh`→305841；新模型根a11，只读复用停止a10。CUPID_DOWNLOAD_PROXY=http://127.0.0.1:49693，wait600sec，CPU4核8GB2h不变。
- `sbatch --parsable --dependency=afterok:305841 --kill-on-invalid-dep=yes scripts/submit_stereo_cupid_pilot.sh`→305845；新输出STEREO_CUPID_PILOT_40C09DC_A7，1GPU30min完整Stage1+左Stage2，既有Panda/DINO/scene_unit不变。
- squeue确认305841实际server14后，用StrictHostKeyChecking=yes、既有UserKnownHostsFile=/tmp/stereo_cupid_hostkeys.VcqF15及显式有时限ProxyCommand的`ssh -N -T -R 127.0.0.1:49693:127.0.0.1:20890 ricky@server14`建立exec49409；只改会话参数，系统/SSH/代理配置未改。
- 19:26:02 fresh日志：4完整权重VERIFIED_REUSED共698047668字节；SLAT flow在旧1312817152字节基础新增16777216字节至1329594368，完整receipt DOWNLOADING。旧字节不计吞吐，短时恢复不等于全量下载或科学验证完成。

## 20:08 7999代理重新验证

- 用户询问官方来源/VPN/是否export7999。实际源码固定hbb1/Cupid@1191de37；launcher默认7999，但旧305841 CUPID_DOWNLOAD_PROXY覆盖为loopback49693，SSH到本机20890。实查scontrol/log记录configured_proxy/49693。
- 305841于19:45:30 FAILED1:0/20m24s，末尾offset1589641216先SSLError再ConnectionError/ProxyError，305845依赖取消0秒无节点，49409连接退出。尝试在旧分配做小型srun探测时返回allocation expired，没有实际探测执行。
- 新增本地scripts/probe_cupid_transport.sh，CPU1核256M3min，仅比较7999和直连，官方小型config与至多1MiB Range，各35s超时，输出只含HTTP/字节/耗时/退出码，无响应体、重定向URL或凭据。commit b93bbf64c8acf1c96ccfa01c90f9b73d7065423f/tree1eb990de873a1610d40078099bd85178a0b17e81。
- GitHub直连fetch/readback两次超时；scutil/lsof重新确认本机20890后，使用git -c http.proxy=http://127.0.0.1:20890 fetch成功；仅给同步helper进程export http_proxy/https_proxy相同地址，不改Git/SSH/系统配置。失败发生在GitHub读回前，未创建远端staging。修复后verified bundle完整同步a20，bundle103865字节、SHA908cb9b14cf04308e5da20c24bf4b06391e2dffe542866abdbee4e7dd082b8fe。
- fresh duplicate audit无活动Stereo作业后，sbatch probe_cupid_transport.sh返回305961。最新sacct PENDING，无分配且日志不存在；不能称7999或直连通过，等待Slurm正常调度。

## 20:22–20:33 先续传并行找路线

- 用户明确要求不要等待代理对比阻塞断点续传，并提出本地电脑下载后上传备选。先查scutil和lsof确认本机20890代理监听，fresh sacct确认旧305841/305845/305961均终态且无活动重复作业。
- 本机仅按备选评估读取固定官方文件1MiB Range（curl --proxy http://127.0.0.1:20890 --range 0-1048575 --max-filesize1048576 --max-time25 --output /dev/null），HTTP206/1048576bytes/5.089026秒。没有整套权重本地落盘；该小样不能当全文件速度、也未测上传速度。
- 本地脚本修改：requests异常及RANGE_DEADLINE的恢复窗口最少600秒，保持单请求40秒无数据超时/300秒总时限、4MiB块、1并发、官方SHA；非临时完整性错误仍最多5次。原5次40秒错误加短backoff会在5分钟跟进前耗尽，此修复给会话重连留下时间。实际超5次后重连分支尚未验真，不能称长期恢复保证。commit3f9d24f7945e7de4e7c7a33ce2a00a33fac16f5d/tree6e10d28bb9d579b6725e8d685f545dde3c7f3ecf已push。
- 同步a21初次git config检查失败，随后只读commit/tree/remote.origin.url均匹配但未使用或原地修复；保留partial。新a22通过完整helper，bundle108966bytes，SHA cdfc72e9fa08d4a87886f2eba8902669c354f879451a87ad8a57362942c65d53。
- 新CPU sbatch返回306009，roota12只读复用停止a11，loopback49694/wait600sec，4CPU8GB2h。GPU sbatch afterok:306009 kill-on-invalid-dep=yes返回306014，输出STEREO_CUPID_PILOT_3F9D24F_A8、1GPU30min完整Stage1+左Stage2/Panda/DINO/scene_unit。
- fresh squeue确认server14后，用既有严格hostkey和有时限ProxyCommand建立exec5028，server14:49694→本机20890；没有修改配置。旧转发不复用。
- 既有306009分配内srun --overlap --nodes1 --ntasks1 --cpus-per-task1 --mem256M运行已同步probe脚本，step306009.0完成16秒，7999与直连各2次全部HTTP000/0bytes/exit28。与此同时主下载复用1589641216流分块后增至1598029824，完整receiptDOWNLOADING。并行探测不作为主下载前置审批，不因失败取消健康下载。

## 21:26–21:33 本地下载授权切换
**21:33用户明确改为本地下载后上传集群，已实际开始。** 本地根 `/Users/ruikegu/Downloads/Cupid_official_1191de37_local_a1`，CMYNetwork/MaccCore既有代理127.0.0.1:20890。首个SUV flow持久化83143277字节后HTTP/2 CANCEL中断；文件保留，原exec83692终态92。官方manifest初次获取超时导致首helper启动缺文件，重取固定revision成功后，前台helper exec70764续传（`transfer_a2.log`），没有安装依赖。helper源码6b35172d38393d62b0dad623de899d1484246436已GitHub精确读回；只处理六个剩余官方safetensors，逐文件本地官方SHA后，通过独立1CPU/1GB/1h的Slurm srun接收及复核上传SHA，不在登录节点落盘/哈希。计划上传根 `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_local_upload_a1`，尚无上传成功证据。每次incoming新身份、最终硬链接拒绝覆盖，保留失败证据；这是子集而非完整pipeline。

集群306009/a12继续完成当前SLAT flow（最新2399141888/2401799952，末块重试），306014仍依赖旧下载；只有SLAT全文件VERIFIED后才停止旧下载及其依赖、关闭转发5028，保留a12完整文件及缓存，避免重复下载剩余六文件。之后本地上传子集与旧根经新Slurm合并/全量官方校验、新GPU输出身份，不往活跃a12写入。模型执行源码仍3f9d24f/a22，尚无推理结果。下一轮先确认helper/文件增长；原curl已停，不得重复本地writer。本地首次可见83MB并非完成、也不证明更快；当前没有Stereo训练loss/optimizer/W&B。


本地用户授权的网络传输与官方资产SHA，不是本地模型测试。查看scutil --proxy/CMYNetwork process，Downloads空余88GiB。curl显式--proxy 127.0.0.1:20890，固定官方revision。helper70764命令见RUN_STATUS；首次启动错误保存在本地transfer.log，后续日志transfer_a2.log。无凭据、无原始数据外发。

## 21:36 集群旧下载收尾
**21:36切换完成：集群SLAT flow 2401799952字节已VERIFIED。** 旧CPU306009已CANCELLED（1h5m48s），旧GPU306014已CANCELLED（0秒无节点），旧转发5028退出255、已关闭。这是用户要求本地下载上传后的主动切换，不是模型失败。a12保留5完整权重共3099847620字节；完整receipt仍非VERIFIED，余下六权重由本地helper70764续传。最新本地SUV partial166324845字节，已超过原83143277断点；本地完整SHA、实际上传和1GPU尚未完成。不得恢复旧306009/306014/5028。上传目标仍独立local_upload_a1，helper每文件在Slurm CPU分配接收/复核；最终须新根合并全量校验再提交新1GPU。

scancel 306014 306009 后fresh sacct确认两者CANCELLED；5028退出255。没有GPU执行。helper70764存活、partial增长166324845bytes。

## 21:49 独立进程续传恢复
**21:49本地续传恢复。** 原exec70764不存在，pgrep/lsof确认helper及该partial的writer均已退出；Mac未再次重启（boot18:34:57）。日志最后为HTTP/2 CANCEL/exit92，没有Python异常，因此工具会话消失与进程退出的具体因果仍未知。保留SUV partial304848052字节；本机20890仍由CMYNetwork/MaccCore监听。源码46e2d022e36eae00de007f75101e683e8efb1680已push/精确读回，将curl显式设HTTP/1.1以针对已观察HTTP/2重置；长期网络稳定性尚未证明。新helper PID21404以独立进程会话运行（start_new_session、stdin DEVNULL、fcntl锁），日志`transfer_a3.log`，进程receipt`transfer_process_a3.json`，继续同一partial，不重复下载已保存字节。无新Slurm/GPU提交，无上传成功证据；旧306009/306014/5028仍结束。


## 2026-09-21 00:13–00:19 代理切换及上传首错
**2026-09-21 00:19：SUV flow 2239067672字节及SS decoder147591972字节已本地官方SHA通过，尚未上传成功。** CMYNetwork/MaccCore20890已关闭，scutil显示系统代理禁用；实测现有ClashX7890监听且官方API HTTP200/1.63秒。旧21404进程组已停止、lsof确认无writer后，新32204通过7890续传原2125938534断点并完成SUV SHA。上传SSH返回Connection closed by10.10.7.1 port22，32204已失败退出，日志transfer_a4.log，receipt为UPLOAD_UNVERIFIED；不能推断远端文件是否创建。三次SSH检查均在banner/keyexchange前关闭，TCP连接建立但无远端协议串。route只读显示10.10.7.1经utun8/gateway198.18.0.1，不能直接认定代理是唯一根因。未改VPN/SSH/系统配置，已向用户询问校园网/VPN是否仍连接。

为避免SSH故障阻塞其它下载，源码972bc8e61bd0d453864afc1d25b38382b8db1ea6已push/精确读回，新增显式--download-only：保留全部本地官方SHA及上传待办，不把本地完成当上传完成。新独立helper PID33142，日志transfer_a5_download.log，进程receipt transfer_process_a5.json，ClashX7890，从本地已校验SUV继续余下5文件；SS decoder已完成，SS encoder下载中。目标local_upload_a1不变但当前--download-only不提交上传job；待SSH恢复后先fresh squeue/sacct/远端incoming审计避免重复，再完成上传。旧306009/306014/5028不恢复。完整pipeline/root、模型运行、Stereo训练仍未完成。


## 2026-09-21 00:22 本地六文件终态
**2026-09-21 00:22：本地六个剩余权重全部下载完成并通过官方SHA，共4168403480字节。** `local_transfer_receipt.json` 为LOCAL_SUBSET_VERIFIED_UPLOAD_PENDING；PID33142正常完成退出，transfer_a5_download.log含六个LOCAL_VERIFIED。集群a12另有五个已校验权重3099847620字节，两地合计11个权重7268251100字节。仍未形成集群25文件完整root，不能把分散权重齐备称集群模型可用。ClashX7890完成剩余5文件约3分钟，观察到本次路线明显快于旧CMY传输，但不推断唯一根因。

上传阻塞仍为SSH：00:22再次Connection closed by10.10.7.1 port22。没有远端shell，无法核查先前上传是否留下job/incoming；不盲重提交、不安装、不改SSH/VPN/路由。用户校园网/VPN状态问题待答；下一轮先恢复只读SSH并审计上传job与目标，随后只上传已有校验文件，禁止重新下载完整权重。上传后在Slurm新根合并a12和local_upload_a1，补小JSON并全25文件官方SHA/pipeline引用校验，再新1GPU。当前没有任何Stereo模型运行/训练结果，最高S02，S03 DEBUGGING。


## 新授权并行训练补缺
**2026-09-21新增授权：五个独立任务已开始并行补齐训练缺口。** D数据、T训练器、L日志评估、R集群上传/唯一GPU运行、I集成晨报，真实thread/worktree/branch见CAMPAIGN_TASKS.json；工作顺序与自动修复交接见CONTINUOUS_EXECUTION.md。目标2026-09-21 08:00晨间可核验产物。用户已明确要求阶段完成自动推进、失败修复重试，旧“单卡后暂停等审核”仅历史状态，不再是本轮自动停止点。V1冻结推理基线保留，训练候选另立STEREO_CUPID_STAGE1_TRAIN_V1；没有继承已训练结果。用户目标选择仍可覆盖，暂按官方Stage1监督微调候选实现验证，真实GT/target/样本/steps配置必须落地，不能用toy或HSSD冒充。R独占本campaign GPU提交（先1卡smoke、再2卡DDP、正式优先1卡）；控制器不同时提交。

创建5个Codex独立project worktree对话，均收到已启动回执；公共D/T/L接口提案转发，R已知I task ID。authority live ls-remote=d88b19e0414aaf482b21f5630b64df604dc2c57a，未修改SSH/VPN，不新增GPU job。
