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
