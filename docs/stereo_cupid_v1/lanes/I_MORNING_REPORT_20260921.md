# 2026-09-21 08:00 CST 晨报骨架与首错交接

状态：待真实运行证据补齐的报告草稿，不是08:00已完成报告或执行receipt。
本次准备依据A4源码和控制器/R交接；本文件新增不改变冻结执行身份。
报告目标时间：2026-09-21 08:00 CST；实际证据截止时间：UNVERIFIED，发布时必须填写。
主控制器负责汇总并同步E00；I只提供集成证据及首错审阅。

## 固定身份

| 字段 | 当前值 |
|---|---|
| 推理 experiment_id | STEREO_CUPID_V1_SHARED_SS |
| 新训练 experiment_id | STEREO_CUPID_STAGE1_TRAIN_V1 |
| 冻结CPU执行 commit | a1bd82ef280edce3d9cd8e3ba3b9184df8ee9d2f |
| 冻结CPU执行 tree | 532c3f77f7122a84be0ddb77f3893ecf8f57377d |
| CPU mode / 资源 | data-contract / 1 CPU、4 GB、15 min |
| 唯一提交 owner | R |
| 责任边界 | D数据与target；T训练；L评估/记录；I集成与首错审阅；R运行 |
| 报告文档 commit | 在控制器交接消息记录；不可替代上述执行commit |

GitHub已读回A4完整commit/tree，5个冻结文件与0c77ae9基线无diff。
R后补source-evidence helper未纳入A4；不要从moving branch读取执行身份。
历史Job、CUPID结果、其他experiment或旧checkpoint不可填入本次运行字段。

## 可直接用于晨报的当前表述

已完成D/T/L/R独立源码整合与已报告接口缺陷的静态修复审阅。
CPU Job 309002 已真实通过 source contract；D9、L13、T9、I6 共37项通过。Panda candidate/files_complete/content_verified=`125/125/121`、content_failed=`4`；`scientific_evidence=false`、`proper_rotation_pairs=0`。这些是工程/资产证据，不是模型或科学结果。

Pilot Job 309127 使用 exact `85d2f5fc/tree df2c4ddf`：11/11 contract tests PASS，Stage1 25/25，geometry OK（11618→954）；Stage2 FAILED/ExitCode=2，首错为 `slat_flow` 未显式绑定本地 `slat_enc`，离线回退 `microsoft/TRELLIS-image-large` 触发 `LocalEntryNotFoundError`。输出 root 为 `/public/home/ricky/RESULTS/STEREO_CUPID_85D2F5_PILOT_A1/output`；`scientific_claim=UNTESTED`，不计 S05，R 正在修复。
此前R报告SSH在banner前关闭；最新网络状态需使用R带时间的原始日志更新。
模型完整root、真实canonical监督、GPU推理与训练终态均待证据，不从源码或准备工作推断完成。

## 运行证据登记（收到R原始产物后逐栏填写）

| 字段 | 当前状态 | 验收依据 |
|---|---|---|
| 最新SSH观测时间/结果/日志位置 | UNVERIFIED | R实际连接日志；区分banner、认证和执行阶段 |
| JobID / partition / node / requested resources | UNVERIFIED | job_id.txt、job_readback.txt、Slurm终态 |
| 远端checkout绝对路径 / commit / tree / clean | UNVERIFIED | 计算节点身份输出与source_contract.json |
| Python / overlay /依赖版本 | UNVERIFIED | 实际运行环境证据；不能只抄launcher默认值 |
| launcher / config路径与hash | UNVERIFIED | 本次checkout与提交参数；CPU使用data_panda125_audit_v1.json |
| evidence root / submission root | UNVERIFIED | R返回的真实绝对路径；不可预造目录为已存在 |
| 开始/结束时间、State、ExitCode | UNVERIFIED | sacct及作业输出交叉核对 |
| source契约 / shell语法 | UNVERIFIED | source_contract.json和runtime.log实际执行顺序 |
| D / L / T / I实际执行数、通过数、失败数、跳过数 | UNVERIFIED | 四模块各自终端输出；37只是计划数 |
| Panda实际pair/object数、损坏/缺失项、内容hash | UNVERIFIED | panda125_audit产物内容及summary |
| 首个失败谓词、异常与上下文行 | UNVERIFIED | 原始日志绝对路径、行号；区分根因与后续级联 |
| artifact大小/hash、采集时间与采集者 | UNVERIFIED | R计算节点采集证据与I只读审阅记录 |

当前launcher的产物相对位置：

- `<evidence>.submission/job_id.txt`、`job_readback.txt`、`queue.txt`、`capacity.txt`、`history.txt`、`slurm_<JobID>.out`。
- `<evidence>/runtime.log`、`terminal.txt`、`source_contract.json`、`panda125_audit/`。

路径来自`scripts/stereo_runtime_submit.sh`与`scripts/stereo_runtime_job.sh`的源码约定，不代表这些文件已经生成。
runtime脚本在校验checkout、创建evidence根后才设置EXIT trap，因此早期失败可能没有terminal.txt或runtime.log；此时检查submission的Slurm输出和sacct，不能把缺失terminal等同未提交。
顺序由`set -e`控制：前一模块失败会令后续模块未运行；缺失后续输出应记录NOT_RUN，不得记PASS或0失败。
如果37项全通过但Panda审计失败，应分别记录fixtures通过、真实数据审计失败，整个CPU包仍失败。

## CPU首错审阅与回流

1. 先核对JobID、A4完整commit/tree、checkout、mode与输出根；身份不符不接受为A4运行结果，也不覆盖旧证据。
2. 读取sacct、submission日志、runtime.log和已有receipt，定位第一个失败命令/谓词。先分为同步/环境、语法/配置、数据语义或算法逻辑，保留完整traceback。
3. I向主控制器交付一次首错包：观测时间、完整身份、失败命令、日志路径/行号、最小根因证据、受影响接口、责任owner、建议修复和待验证项。由主控制器路由，不由I并行抢修其他lane。
4. D处理reader/manifest/target内容与坐标；T处理objective/trainer/optimizer/DDP；L处理metric/denominator/callback/readback；R处理环境/资产/同步/Slurm；I处理集成checker与跨lane契约。跨lane时明确主owner和协作owner。
5. 只有根因成立后才做单一工程修复；本地修改、commit/push、GitHub完整SHA/tree读回。R用新checkout、新证据根和新JobID重跑，旧失败保留。不得以跳过模块、降级功能或改单位使检查通过。
6. 运行通过也只接受对应工程范围；不把CPU fixture通过提升到S05/S06/S07、训练有效或科学结论。阶段与最高完成阶段由控制器依据十阶段规则与全部证据判定。

首错包必填字段：`observed_at`、`experiment_id`、`job_id`、`commit`、`tree`、`checkout`、`launcher`、`mode`、`config_hash`（适用时）、`evidence_root`、`first_failed_command`、`first_failed_predicate`、`log_path_and_lines`、`root_cause_evidence`、`owner`、`proposed_fix`、`next_verification`。未取得的值填写UNVERIFIED，禁止合成运行receipt。

## GPU与科学结论的独立证据栏

| 事项 | 当前状态 | 需要的真实证据 |
|---|---|---|
| 25文件模型root | UNVERIFIED | 计算节点逐文件SHA验收与根路径 |
| 冻结完整Stage1+左Stage2 pilot | UNVERIFIED | 独立Job/身份、result.json、NPZ、mesh、I产物检查 |
| 几何/pose/scale | UNVERIFIED | 原始预测、失败分母、L独立评估、GT资格与单位，无GT对齐 |
| canonical训练target及object-disjoint划分 | UNVERIFIED | D真实来源、renderer/proper-CV链、manifest与hash |
| 1 GPU 20 update smoke | UNVERIFIED | forward/backward、optimizer变化、loss、checkpoint及hook |
| 10→20 optimizer恢复 | UNVERIFIED | 新输出根、完整optimizer/scaler/RNG/游标，与连续20步比较 |
| 2 GPU DDP | UNVERIFIED | 两rank实际执行、同步/分片/有效全局batch及退出证据 |
| W&B服务端读回 | UNVERIFIED | 本地durable记录与server history对应；URL不算通过 |
| full训练、accepted科学结果、S10 | UNVERIFIED | 完整训练预算与独立终态评估后由控制器验收 |

scene_unit不能表述为米；FM validation loss不等于pose质量；相同SS支撑不证明两视图UV为同一点。

## 08:00发布前核对

- 填写实际证据截止时间；明确哪些来自R/D/T/L交接，哪些由I直接读原始产物验证。
- 将每一处UNVERIFIED只替换为对应真实证据；区分NOT_RUN、FAILED、PASSED及无法验真的状态。
- 记录仍在执行的Job与当前状态，不将RUNNING或已保存checkpoint称为完成结果。
- 给出最早阻塞、当前owner和下一步；只报告本包新增证据，不重复升级旧结果。
- 由主控制器更新中央实验进度；本稿不修改E00或Slides，也不自行创建定时任务。

反思：当前最不确定的是远端可执行性与合法canonical监督。潜在盲点是仅汇总退出码而遗漏顺序执行导致的未运行模块，或将fixture通过误读为真实数据/模型有效。
