# Stereo-CUPID 明日进度报告（工程证据版）

报告用途：明日汇报当前可核验进度。本文不提交作业、不定义科学结果；所有运行状态按 `PASSED`、`UNVERIFIED`、`NOT_RUN`、`FAILED` 分开记录。
本次报告基线遵循控制器指定的 unified `edfcc2cfdd31df50bb64b035696c2bfde0ed5a6d/tree9b9736378be7d4dfeb3ec67a927fd9e8ba274f8d`；R 后续 `b1cbadb/tree62b62524` 与 T 本地 `188a8ba9` 因当前 GitHub 网络/exact-read 未完成，不能写成已纳入统一源码。

## 统一身份

| 字段 | 值 | 状态 |
|---|---|---|
| 统一 integration commit | `edfcc2cfdd31df50bb64b035696c2bfde0ed5a6d` | PASSED：控制器指定基线，GitHub exact-read 已有证据 |
| 统一 integration tree | `9b9736378be7d4dfeb3ec67a927fd9e8ba274f8d` | PASSED：控制器指定基线 |
| R 后续 tip | `b1cbadb/tree62b62524` | UNVERIFIED：本轮 GitHub 读取超时，未纳入统一源码 |
| T 后续协议 | `188a8ba9` | UNVERIFIED：local-only，尚未 GitHub exact-read，不能执行 |
| frozen inference | `STEREO_CUPID_V1_SHARED_SS` | PASSED：身份已登记；无科学终态 |
| training candidate | `STEREO_CUPID_STAGE1_TRAIN_V1` | PASSED：入口/参数契约已实现；无训练终态 |
| 运行 owner | R | PASSED：唯一 Slurm/GPU 提交者 |
| scientific gate | `UNVERIFIED` | PASSED：当前没有 accepted scientific result |

## 已完成的工程证据

| 证据 | 状态 | 边界 |
|---|---|---|
| A4 unified CPU contract | PASSED（控制器回读：37/37） | 仅工程契约；不是模型 smoke、训练有效或科学结果 |
| Panda125 内容审计 | PASSED（控制器回读：125/125） | 仅 manifest/content/hash 审计；不证明 canonical 几何、GT 合法性或泛化 |
| D 几何证据清单 | PASSED：已纳入统一源码 | 仍需真实 renderer/camera/坐标链证据；不得由清单推断 target 已闭合 |
| T Stage1 参数契约 | PASSED：唯一可训练组 `["suv_flow"]`，其余边界显式记录 | 尚未有真实 optimizer/loss/checkpoint 运行证据 |
| R CPU guard 修复 `d01406b` | PASSED：已集成到此前 I tip | 允许 `data-contract` 与 asset upload 并行审计；不等于作业已提交；R b1cbadb 后续差异待 exact-read |
| R source evidence helper | PASSED：源码已集成 | 尚未接入自动序列或生成远端 receipt |

## 失败与未运行

| 事件/项目 | 状态 | 证据与解释 |
|---|---|---|
| Slurm `308657` | FAILED：`PREEMPTED` | 失败属于调度终态；不能当作模型或科学失败，需保留两份 partial 字节产物及其路径/hash |
| d01406b 修复后的 CPU 作业 | NOT_RUN / UNVERIFIED | 修复已 exact-read 纳入，但当前未收到新 JobID、终态或 evidence root |
| 官方 25-file 完整 model root | UNVERIFIED | 本地/集群分散权重与 partial 不能合并宣称完整可用；须 fresh root、逐文件官方 SHA 和 pipeline 引用检查 |
| 预训练 Stereo inference | NOT_RUN / UNVERIFIED | 无可接受的 `result.json`、NPZ、mesh 和独立 I/L 评估 receipt |
| Stage1 单 GPU smoke | NOT_RUN / UNVERIFIED | 无 forward/backward、optimizer、checkpoint、heldout hook 终态 |
| Stage1 2-GPU DDP | NOT_RUN | 无 JobID 或两 rank 运行证据 |
| W&B/S07 | NOT_RUN | 无服务器 readback；本地日志或 URL 不足以通过 |
| full training / S09 / S10 | NOT_RUN | 未进入完整训练、终态评估或 Slides 科学同步 |

## 阶段判定

当前训练实验应报告为：`S01` 已登记；`S02` 代码实现、提交、同步和静态接口审阅完成；`S03/DEBUGGING` 正在处理运行入口/资产/调度问题。最高完成阶段保持 `S02`。`S05`、`S06`、`S07`、`S08`、`S09`、`S10` 尚未进入或尚未验证。

旧 `HSSD` 作业 `296164` 的 `PREEMPTED` 终态属于独立实验/复现身份，不得与当前 Stereo-CUPID 结果合并。`308657` 同样只报告为本轮调度失败和 partial 资产证据，不升级为科学结论。

## 下一步与回报字段

R 恢复入口后，先用当前统一 commit/tree 建立 fresh checkout，读回活动作业、旧 incoming/final 和 `308657` 两份 partial 的真实路径与 SHA；然后执行 d01406b 后的唯一 CPU `data-contract` 包。返回报告必须包含：`JobID`、partition/node、checkout commit/tree、mode、evidence root、Slurm state/exit code、37 项实际分项状态、Panda summary、首个失败 predicate、原始日志路径和 artifact SHA。

同步阻塞：I 本轮对 R/T 后续 exact-read 均遇到 GitHub 连接超时；在网络恢复并完成完整 SHA/tree 读回前，保留已验证 unified 基线，不把 local-only 代码放入远端执行包。

如果 CPU 包通过，只能将工程证据更新为 `PASSED`；仍需独立完成完整 model root、预训练 pilot、训练 smoke、DDP、W&B readback 和终态评估。任何缺失字段填写 `UNVERIFIED` 或 `NOT_RUN`，不得用总退出码、checkpoint、队列状态或输出目录代替真实证据。

反思：当前最大不确定性是远端资产/调度的可重复执行性；最容易误读的是把 37/37 与 125/125 的工程审计，或 308657 的 partial 文件，讲成模型/科学结果。
