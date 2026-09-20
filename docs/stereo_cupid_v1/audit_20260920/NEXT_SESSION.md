# 执行状态与下一步

18:59最优先：23722和4952转发均已退出255；登录节点SSH多次超时。305794最后18:58:58 RUNNING但没有超过1312817152新字节，305798 PENDING。先核验fresh状态及网络再恢复，禁止依据提交成功/旧RUNNING推断健康，不重复提交。详见RUN_STATUS首段。

18:54最新覆盖下方：本机18:34:57重启、旧转发98390消失；305609/305611失败或取消，无GPU。后继CPU305794，模型根a10只读复用停止a9，源码e1bd1ed/a18（下载算法未变）。恢复网络转发49692，主机密钥文件/tmp/stereo_cupid_hostkeys.VcqF15来自既有信任记录；必须先查实际Slurm节点。新单卡/转发session见RUN_STATUS最新首段。约2.01GB已保存，全部权重仍未完成。send_message_to_thread目前不在工具清单，需后续发送保存的E00包，不能冒称中央已更新。

17:32转发已建立：session98390，实际server14 loopback49691→本机既有7890；305609已越过旧失败offset，完整receipt仍DOWNLOADING。结束后关闭此转发。以RUN_STATUS首段和下载日志为准。

17:31当前入口替代下方旧记录：CPU305609/依赖单卡305611，checkoutcbb4cbf/a17、模型根a9复用停止的a8，单卡输出STEREO_CUPID_PILOT_CBB4CBF_A5。旧305577 FAILED、305583取消、转发98813结束；新的转发按实际Slurm节点连接49691。此次只将网络并发4→1，检验争用假设；不能把推测当根因结论。以RUN_STATUS最新首段和fresh sacct为准，未完成前不称全部权重可用，不重复提交健康作业。

17:21当前入口：305577 RUNNING server14；305583 PENDING afterok:305577，无GPU分配。完整4个权重已重新校验复用，SLAT flow已从旧断点406847488推进至524288000字节。继续跟踪a8根的receipt和脱敏日志，不重提健康作业。转发session98813、计算节点loopback49690，下载终态后关闭。单卡输出 `/public/home/ricky/RESULTS/STEREO_CUPID_PILOT_A8E799E_A4`，checkout a8e799e/a16；详情以RUN_STATUS首段为准。

最终CPU复验：304071在server14运行11秒，COMPLETED 0:0，11项全部通过。最高完成S02；当前S03 DEBUGGING。用户已允许官方权重下载，不能继续以缺授权阻塞。

17:15接续覆盖下方旧入口：305505在50m14s因同一range连续5次超过90秒失败，305510自动取消且未分配GPU。已将单range时限调到300秒、保留40秒无数据超时，源码a8e799e、checkout `/public/home/ricky/CODE/stereo_cupid_a8e799e_a16`。新下载305577使用新根a8、CUPID_REUSE_WEIGHTS_FROM=a7；确认复用成功并越过原失败offset，再继续依赖单卡。不要重下已完整校验的4个权重，也不要把部分权重齐备当整套模型可用。最新作业和转发身份以RUN_STATUS首段为准。

16:20最新入口：跟踪CPU305505和GPU依赖305510；旧305474/305481已取消。权重根a7，运行checkout `/public/home/ricky/CODE/stereo_cupid_94c4d05_a15`；临时SSH session27758、计算节点server14、loopback49689。下载改为4MiB持久化Range，若之后中断，应确认旧作业停止后以 `CUPID_REUSE_WEIGHTS_FROM` 指向a7，在新输出根复用已验证文件和带摘要的完整分块，不能丢弃旧证据或默认重新下载全文件。只有完整官方SHA全部通过才可称下载完成。详见RUN_STATUS最新首段。

15:52接续入口：先检查CPU305474、`/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a6/download_receipt.json` 和临时转发exec session7388。运行源码bc458f2，checkout `/public/home/ricky/CODE/stereo_cupid_bc458f2_a13`。全量SHA通过后关闭下载转发，提交1GPU/30min单对完整Stage1+左Stage2 mesh，使用现有DINO路径和 `configs/stereo/gso_panda_random_linear_0_scene_unit.json`。下方表格和旧路径保留为CPU审计历史，以 `../RUN_STATUS.md` 最新更新为准。下载/单卡循环由本任务automation `stereo-cupid` 每5分钟跟进，不占用新任务。

| 阶段 | 现状 |
|---|---|
| S01 | 已登记独立实验 STEREO_CUPID_V1_SHARED_SS；假设不是结论 |
| S02 | PASS：原权重双目推理实现已commit/push/同步；CPU集群11项复验通过 |
| S03 | 单GPU305583已提交，等待CPU305577完成全量权重校验；授权已具备 |
| S04–S05 | 未进入真实单GPU修复/通过；CPU304070失败不能记为模型smoke |
| S06 | 尚无DDP；预训练推理不需要optimizer，若选择训练须实现并验双rank |
| S07 | 原CUPID logger/readback可复用；Stereo入口尚无W&B和训练loss/optimizer，pose/scale evaluator未完成 |
| S08 | 未提交Stereo完整训练；原HSSD296164是独立PREEMPTED终态 |
| S09 | 无Stereo完整结果 |
| S10 | 未修改slides，不能把工程证据放成正式结果 |

已同步运行源码：`d70919675d66c98ce3ec401bc6278bd4a2910808`，集群 `/public/home/ricky/CODE/stereo_cupid_d709196_a2`。
CPU作业304070、输出 `/public/home/ricky/RESULTS/STEREO_CUPID_AUDIT_D709196_A1`，日志 `/public/home/ricky/RESULTS/stereo_cupid_audit_304070.out`。样本JSON已回收到本目录，不含原始图像/深度/凭据。

修复源码：`238fe8ac2d882dd7c54e2190eaa52df44db5361a`，tree `fbda08ce0c670f20aeb6bd54a2a509545f9a30b6`。
同步a3在新checkout即时验证阶段失败，保留partial，不运行该目录。采用原稳定cc95f36基线进行独立a4同步并成功，不能把a3标成功或原地修复。

实际通过的运行checkout：`/public/home/ricky/CODE/stereo_cupid_238fe8a_a4`。CPU304071输出 `/public/home/ricky/RESULTS/STEREO_CUPID_AUDIT_238FE8A_A2`；日志 `/public/home/ricky/RESULTS/stereo_cupid_audit_304071.out`。本目录 `tests_304071.txt`、`sample_inspection_304071.json`、`sync_238fe8a_a4.json`保留终态、数据读数和代码身份。后续仅文档提交不要求重复测试同一源码。

下一轮最小动作：读取本次CPU复验终态；若失败，保留日志、修首错、本地commit/push、GitHub exact-read、fresh远端checkout及输出重跑。若通过且完整模型入口已解决，使用 `scripts/submit_stereo_cupid_pilot.sh` 提交1GPU/30分钟单对Stage1，保存UV和几何失败分母，再按实际结果推进左Stage2。缺标定不能静默估计GT；首次可保存CALIBRATION_MISSING状态，场景单位的显式相对标定可单独验证。

同步路径：本地 -> GitHub fork `Jusker-Greek/Cupid` -> 项目既有 `sync_verified_git_bundle.sh` -> 新远端镜像/checkout；当前集群HTTPS代理和直连均TLS失败。不复制源码树，不编辑远端源码。helper的slurm_submission_authorized=false仅说明同步工具不提交作业，实际运行依据用户本轮明确授权另行提交。

Slides终点保留用户给定路径：`/Users/ruikegu/.codex/worktrees/total-slides-results-integration-20260831/docs/overleaf/xfactor_full_experiment_ledger_stereo_reorg_2026_08_21/main.pdf`。S10必须更新可编辑源、远端编译并视觉核验，不能仅覆盖PDF。
