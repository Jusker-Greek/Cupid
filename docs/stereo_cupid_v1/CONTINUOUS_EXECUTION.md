# Stereo-CUPID 持续实施与监控

用户于2026-09-21明确授权独立对话并行补齐训练缺口、连续阶段推进与修复重试，争取08:00晨间结果。本授权扩展先前仅权重和推理范围；不修改既有V1冻结推理定义，新的训练使用独立实验身份。没有承诺网络、排队或实验效果必定在晨间完成。

## 独立负责人

机器可读身份、初始任务全文及创建状态见CAMPAIGN_TASKS.json。5个独立项目worktree任务均已返回启动消息和真实threadId，已发送公共接口交接。CAMPAIGN_TASKS.json登记各自worktree/branch。clientThreadId只保留创建证据，不再作为运行身份；不得重复创建。

| Lane | 责任与交付 | 立即承接者 |
| --- | --- | --- |
| D | GSO pair清单、对象划分、loader、target/latent准备接口 | T、L、I |
| T | 训练协议候选、真实Stage1训练器、optimizer/checkpoint/resume、DDP | L、I、R |
| L | W&B/TensorBoard与服务端读回、有效GT下的pose/scale评估 | T、I、R |
| R | SSH恢复、已校验权重上传与新root组装、环境、唯一GPU提交 | I、控制器 |
| I | 集成精确提交、端到端检查、运行交接、晨间报告及合规Slides | R、控制器 |

所有worker只修改各自责任文件；I在独立integration branch合并。源码本地→GitHub→新集群checkout。现有权重不重下，所有模型与测试工作负载只在Slurm。E00仅由本控制器同步，不并发写中央台账。

## 自动推进规则

唯一现有heartbeat stereo-cupid每5分钟检查所有lane和当前stage，不另建相互竞争的监控。任务完成可通过worker消息触发控制器立即交接；定时检查是最多约5分钟的兜底，不是实时事件订阅。

1. 读CAMPAIGN_TASKS和RUN_STATUS，核对真实thread状态、提交/日志/receipt/job，不能把对话结束当PASS。
2. 若worker正在有证据地推进，保留其工作。若完成可交付接口，立即把精确SHA与下一输入发给下游；不等其它无关工作完成。
3. 若worker结束但交付不完整或仍有明确可实施下一步，send_message_to_thread继续同一worker；不要放置为无人负责，也不要重复新建。
4. 若发生错误，保存失败身份和首错，明确归属到D/T/L/R/I，发具体修复任务；修根因→GitHub同步→新checkout/output/job重试。禁止无差别重提同一失败命令、删除功能绕过错误或覆盖旧证据。
5. 同时有多个完成任务时，I集成兼容提交，R依据唯一运行队列执行；控制器不与R并发提交GPU。
6. 每次stage或主要依赖完成后更新CAMPAIGN_TASKS.current_focus、RUN_STATUS，并调用automation_update改写heartbeat当前监控对象/任务/JobID/下一动作。不得仍监控已终态旧PID或旧job。
7. 外部SSH/权限故障保留恢复owner R，其它数据接口、训练代码、日志、集成继续；缺用户独有信息才问，不能凭空填入。当前训练目标偏好已异步询问，通用实现并行推进。

## 运行顺序及真实证据

两条支线并行：R先上传组装→完整冻结V1单卡推理；D/T/L同时实现训练。训练合并可运行后立即进入单卡训练smoke（含forward/backward/optimizer/checkpoint/eval）→错误修复循环→双卡DDP短smoke→日志server readback→绑定真实数据清单/初始化/目标/完整步长的低卡训练→结果评估→必要单变量后续实验→汇报。

最多一个本campaign GPU作业活跃或排队；先1GPU限时smoke，DDP2GPU限时，正式训练优先1GPU。正式训练的样本、steps、初始化、loss和资源必须由T基于实际数据/吞吐形成reviewable配置，控制器登记后R执行；不借旧HSSD的1000000step或checkpoint冒充Stereo。未验证研究阈值不当作工程启动门；真实shape/梯度/数据泄漏/正确性错误必须修复。

原实验STEREO_CUPID_V1_SHARED_SS最高S02/currentS03 DEBUGGING。训练候选STEREO_CUPID_STAGE1_TRAIN_V1从独立S01登记，不能继承V1训练证据。初始化官方权重不是resume已有Stereo优化器；实际没有训练checkpoint时明确写pretrained_init。schema只在D/T接口协商后冻结，不把903对象目录叫903个训练样本。

## 失败和晨间交付

监控必须记录last_evidence_at、next_action、owner、attempt、job/commit/tree/output、下游接受情况。一个检查周期没有新证据时先查真实作业/任务状态；连续两个周期无行动且有可执行工作，触发具体继续/诊断指令，而不是重复报状态。运行中慢任务不因此取消或盲重启。

原S03最后阶段迁移2026-09-20 01:26，2026-09-21 01:26达到24小时必须按技能报告STALLED_24H并继续恢复，不通过文档时间重置时钟。新训练lane使用自己的登记时间。

08:00 CST无论是否已有科学结果，I都必须交可查看的晨间报告：实际产物、曲线、checkpoint、样本/step、明确的工程与科学证据界限；若仍外部阻塞，则交完成代码及运行入口、最后真实首错和负责人，不能编结果。08:00不是停止工作时点；用户明确停止或约定完整流程达到终点才停止自动跟进。

指定正式Slides路径沿用用户main.pdf；accepted科学结果进入正式表，工程进度清楚标识，遵守editable source/编译/视觉核验规则。不要仅替换PDF或制造未获得的研究结论。
