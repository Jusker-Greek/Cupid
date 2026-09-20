# 当前运行状态

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
- 单卡真实模型smoke尚未提交：完整hbb1/Cupid pipeline路径未知；已询问已有位置或约7.27GB下载授权（此前禁止大型下载）。
- Stereo训练目标待用户选择。现有V1是预训练推理，没有新optimizer/loss；不能将原HSSD训练或CPU测试当Stereo训练证据。
- 原HSSD296164已PREEMPTED，日志到42000/1000000；不重提其它任务训练。

三份报告：`audit_20260920/INSPECTION_REPORT.md`、`OPEN_QUESTIONS.md`、`NEXT_SESSION.md`；同目录保存脱敏命令、同步receipt和测试/样本读数。E00已登记独立实验，现有logger/readback代码blob与E00一致，无需重复merge。

仍无Stereo科学结果、DDP通过或完整训练结果；未更新正式结果slides。下一动作是解决完整权重入口并提交1GPU/30min单对推理smoke。所有实验/测试继续只在Slurm计算节点进行。
