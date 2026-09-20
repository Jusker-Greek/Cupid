# Lane I：集成与依赖交接协议

登记时间：2026-09-21 00:30 CST。目标：08:00 CST 晨间汇报。所有时间目标均不是完成证据。

独立 worktree `/Users/ruikegu/.codex/worktrees/dc7f/Cupid`，分支 `codex/stereo-cupid-lane-i-integration`。
共同基线、精确 authority 和各 lane 已接收提交见 `I_DEPENDENCIES.json`。
用户本轮实施授权覆盖旧 handoff 的只读/等待限制；I 不写中央 E00、不提交 GPU、不改其它 worker 的源码。

## 执行清单

- [x] 保留原工作区状态，从 GitHub 取已 push 共同基线，建立独立集成分支。
- [x] 登记冻结 V1 与独立训练候选、接口语义、责任人和完成标准。
- [ ] 收到 D/T/L/R 的 exact commit/tree、接口和 owner 自检证据后，审阅并逐个 `cherry-pick -x`。
- [ ] 将公共接口的可执行最小闭环交 R；不等待文档美化，不把缺少科学分数当工程实现阻塞。
- [ ] R 在 Slurm 计算节点验证实际数据、forward/backward、optimizer、checkpoint、heldout 与日志。
- [ ] 汇总真实产物/首错/验证边界并交控制器；accepted full result 才进入正式科学表和 S10。

## 两种实验身份

`STEREO_CUPID_V1_SHARED_SS` 冻结现有 pretrained 推理，保留共同 SS、分离 UV、原左 Stage2 路径。
`STEREO_CUPID_STAGE1_TRAIN_V1` 是新增候选，训练路径和输出根独立；不可继承原 HSSD 作业、V1 推理或 CPU304071 的训练 PASS。
I 不选新 loss 权重、阈值、数据规模或训练预算；以 T/D 发布并由控制器冻结的配置为准。
共享支撑只保证坐标索引一致，不保证左右真实同点；scene_unit 不自动等于米；GT 对齐诊断不算原始预测成绩。

## 最小语义契约（映射 owner 原生字段，不强迫重命名）

| 边界 | 必需语义 | owner / 首错去向 |
|---|---|---|
| D → T | sample/object/pair ID；左右图像、mask/crop/UV 约定；相机 frame/单位；target 来源、shape/dtype、有效 mask；对象级 split 与实际有效/拒绝样本计数 | D：数据缺失、target、split、坐标 |
| T → L | experiment/run/attempt ID；init 类型与权重来源；resume checkpoint 与恢复 step；各项 loss、实际 optimizer step、LR、epoch、样本累计；checkpoint 与 heldout 事件 | T：梯度/optimizer/恢复/事件调用；L：字段映射 |
| L → I | 全部分母和失败；pose/scale 的值或明确 NOT_APPLICABLE/UNVERIFIED 原因；原始预测与 oracle 分开；本地记录、W&B/TensorBoard 产物、服务器读回 | L：评测/日志/归因 |
| I → R | 集成 SHA/tree、依赖映射、配置、可执行入口、最小验证、环境/数据/资产 receipt、独立输出身份 | I：cherry-pick/静态接口；R：环境/同步/调度 |
| R → I | checkout/commit/tree、JobID、host、exit、完整日志、实际 sample/step 数、曲线、checkpoint、heldout 与读取命令 | R：真实运行、资产和网络 |

owner 交付公共接口即可先接，不要求全部报告完成。每个 handoff 至少包含 source commit/tree、文件清单、公共 API、配置、测试命令及是否真正运行；缺失运行证据写 UNVERIFIED。

## 运行与审查顺序

1. I 审阅 source diff 和接口，保留 source→integration commit 的 `-x` 映射。冲突退回 owner/控制器协调，不丢弃 owner 逻辑。
2. I commit/push；`git ls-remote` 读 full SHA 后从 GitHub fetch 精确提交并读 tree。R 创建新 cluster checkout，不改远端源码。
3. R fresh `squeue/sacct` 查本实验活动作业和旧上传 incoming；不恢复 306009/306014/5028，不重复健康作业。
4. R 在已协调的 CPU allocation 或单卡作业内执行 `scripts/stereo_integration_check.py source`，随后执行 D/T/L 的真实契约检查。I 检查器只做静态和产物一致性，不代替模型实跑。
5. R 按已有资源范围先 frozen V1 真实推理；D/T/L 接口就绪即交 R 新训练候选单卡。预训练初始化、resume、planned steps、completed optimizer steps、有效训练/heldout pair 数必须分别记录。
6. 首错保留日志，按表回 owner。修根因后新的 SHA/checkout/attempt，不以同错无改重试。

## 验证边界与结果

无 GPU/CPU 测试在本地运行。I 的手工源码审阅和 Git diff 仅为静态检查。
推理产物契约通过仅证明记录与文件自洽；geometry_status 非 OK 必须公开，失败仍留分母。
单卡前向、loss 或 checkpoint 不证明泛化/米制恢复，未执行 W&B server readback 不得称 S07。
晨间报告允许写代码完成、真实工程曲线/产物和未验证项；科学表只收 accepted full evaluation。

Slides 固定终点为 `/Users/ruikegu/.codex/worktrees/total-slides-results-integration-20260831/docs/overleaf/xfactor_full_experiment_ledger_stereo_reorg_2026_08_21/main.pdf`。
没有 accepted 科学结果时不改中央 Slides 科学表；后续需更新 editable 源、遵守母图/Draw.io 技能、集群编译与视觉核验。

## 当前反思

- 最不确定的是 D 的全量有效 target 数与 T/L 的真实 GPU 路径，均需集群证据。
- 易忽略的失败是“文件已生成”被误写为完整 checkpoint 恢复或 heldout 评估通过；报告必须展示实际 step 与分母。
