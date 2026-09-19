# 当前运行状态

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
