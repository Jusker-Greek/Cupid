# 执行状态与下一步

最终复验：304071在server14运行11秒，COMPLETED 0:0，11项全部通过。最高完成S02；当前S03 USER_DECISION_REQUIRED（完整权重位置或下载授权）。

| 阶段 | 现状 |
|---|---|
| S01 | 已登记独立实验 STEREO_CUPID_V1_SHARED_SS；假设不是结论 |
| S02 | PASS：原权重双目推理实现已commit/push/同步；CPU集群11项复验通过 |
| S03 | 单GPU预训练模型smoke尚未提交；完整pipeline路径/下载授权待回答 |
| S04–S05 | 未进入真实单GPU修复/通过；CPU304070失败不能记为模型smoke |
| S06 | 尚无DDP；预训练推理不需要optimizer，若选择训练须实现并验双rank |
| S07 | 复用E00确认的现有logger/readback；Stereo pose/scale evaluator未完成 |
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
