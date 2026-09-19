# 当前运行状态

时间：2026-09-20 00:41 Asia/Shanghai。

| 项目 | 实际状态 |
|---|---|
| 实施分支 | codex/stereo-cupid-v1-20260920 |
| 基线 | cc95f36fc26b5d90054ffd920df6c1c1b54c3e4d |
| 初次代码提交 | d902070，已正常推送fork同名分支 |
| 后续静态修正 | 显式保持原CFG/interval默认参数并补测试；与本状态文档一同提交 |
| 本地检查 | git diff --check通过；读过新增调用链与测试fixture |
| 测试 | 新增10个测试，尚未执行；未违反cluster-only规则转到本地运行 |
| 集群 | 唯一既有入口SSH banner exchange timeout，exit255；无可用远端shell |
| 作业 | **未提交；没有job id、没有startup evidence** |
| 训练 | 未新增loss/optimizer；“原权重双目实验还是微调”澄清仍待用户回复 |
| 数据 | 用户确认本地Android_Figure_Panda副本；真实源mesh/renderer路径仍未找到 |
| 后台/自动化 | 无 |

当前阻塞是实际网络连接，不是新增研究审核门。已发起用户侧连接恢复信息请求，未索取凭据。没有因为GT未知而阻止代码实现：Stage1不要求外部相机JSON，也不会伪造米制输出。

连接恢复后，先从远端用户目录的一层清单和已知DATASET路径定位gso/Cupid及已有模型环境，拉取已推送分支；然后可提交1对原权重pilot。源mesh/renderer与GT溯源可继续同时进行。无完整标定时结果是生成诊断；有明确标定时自动执行几何后处理。

复现入口和变量见IMPLEMENTATION.md；网络/路径证据与公开渲染代码链接见ASSET_DISCOVERY.md。

反思：新代码尚未经过真实runtime验证，最可能的工程问题是预训练pipeline/DINO文件与既有overlay不匹配；科学上主要不确定性仍是共享结构对应的双UV是否准确，而不是代码是否能返回文件。
