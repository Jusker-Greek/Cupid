# 官方 CUPID 到双目流程的逐项迁移

2026-09-29。官方权重推理，没有微调。固定原先三对 GSO 样本、seed=42、官方 25+25 步采样、512px 左图评价和原有指标。三个样本已经反复用于开发，不能再称为干净的最终 held-out 确认。

预先声明的工程排查阈值：平均 PSNR 相对官方基线或上一项下降超过 0.5 dB，停止叠加并诊断。这不是统计显著性判据。保留全部低分及失败记录。

## 结果

| Job | 配置 | PSNR dB | Mask IoU % | SSIM | LPIPS VGG |
|---|---|---:|---:|---:|---:|
| 327312 | 官方单目裁剪 | 21.051730 | 91.7777 | 0.862792 | 0.129084 |
| 327312 | 左图复制两路，共享噪声 | 21.398279 | 92.1333 | 0.865583 | 0.126830 |
| 327312 | 真实双目，右结构占 10% | 21.706001 | 92.2080 | 0.867468 | 0.124430 |
| 327312 | 真实双目，右结构占 25% | 21.573938 | 92.3349 | 0.865561 | 0.128093 |
| 327312 | 真实双目，右结构占 50% | 20.667428 | 89.1594 | 0.864517 | 0.129869 |
| 327323 | 重测官方单目 | 21.045228 | 见 JSON | 见 JSON | 见 JSON |
| 327323 | 重测 10% 共享 UV 噪声 | 21.707307 | 见 JSON | 见 JSON | 见 JSON |
| 327323 | 仅改为独立 UV 噪声 | 21.169813 | 见 JSON | 见 JSON | 见 JSON |
| 327330 | 重测官方单目 | 21.046192 | 91.7785 | 0.862745 | 0.129233 |
| 327330 | 重测 10% 共享噪声、左 DLT | 21.707842 | 92.2061 | 0.867483 | 0.124337 |
| 327330 | 仅替换为双目 Sim(3) 定位 | 14.030871 | 60.0718 | 0.613410 | 0.303691 |

本地原始结果与对照图：`outputs/stereo_migration_{327274,327312,327323,327330}/evaluation.json`、`comparison.png`。JSON 包含每样本结果、可见点云 CD/F-score、几何覆盖率和停止原因。

远端不可变输出分别为 `/public/home/ricky/RESULTS/STEREO_CUPID_MIGRATION_A4AFF1A_A2`、`STEREO_CUPID_MIGRATION_FCD532D_A1`、`STEREO_CUPID_MIGRATION_687BFB7_A1`、`STEREO_CUPID_MIGRATION_D25C36D_A1`。每个配置/样本目录保留 mesh、render、pose、sampling、geometry 和 metrics。官方 Stage1 权重 SHA256 为 `e3d0b50ffbb70295b5f6528180d0671d0d71bcf55a19e8c51e0fd19229aab459`。报告顶层的 step809 checkpoint 是旧 evaluator 的资产校验字段；本轮 migration 模式没有加载该微调权重。

## 实施与原因

保留官方 alpha 内容裁剪；UV 经 crop-to-full-image 变换回原图，标定 K 对应原图。Stage2 继续使用原版左 UV → DLT → Conditioner → mesh。

原版 Stage1 在 CPU 生成噪声，旧双目在 GPU 生成；相同 seed 不保证相同初始样本。新增 `noise_source="official_cpu"` 匹配左侧原版抽样；右侧抽样通过 `fork_rng(devices=[])` 不改变后续 Stage2 CPU RNG 状态。默认 device 模式不变。

右结构融合在每一步 Euler 更新后计算 `(1-w)*left_SS + w*right_SS`。两边下一步共用结构，UV 不平均。默认 w=0.5 不变，候选显式指定 w=0.1。

```python
prediction = pipe.run_stereo(
    left, right, crop=True, stage2=True, seed=42, calibration=calibration,
    noise_source="official_cpu", uv_noise="shared", ss_right_weight=0.1,
)
# 当前候选使用 prediction['pose_left'] 渲染 canonical_outputs.mesh。
```

代码依据：`cupid/pipelines/stereo.py` 的 run_stereo、`cupid/pipelines/samplers/stereo.py` 的 sample_shared_structure、`scripts/eval_stereo_paper_metrics.py` 的 migration 系列实验。指标函数没有改动。

左图复制哨兵没有增加信息，其约 +0.35 dB 不能解释为双目收益。双 batch 的浮点数差异、占据阈值和 Stage2 支持集合可能引起变化；尚未证明逐张量等价。10% 真实右图相对同接口复制左图约 +0.308 dB，更接近引入右图的增量。

50% 融合的退化主要集中在 GELBlur33：327274 中 PSNR 21.310→18.816，Mask IoU 94.18%→83.94%，图中轮廓偏移；10% 恢复该样本。独立 UV 噪声在 327323 中使均值下降 0.537 dB，因此不继续叠加。融合影响结构、左 UV 和相机恢复的耦合，但网络内部唯一机制尚未证明。

327330 的相机替换实验保留共享 UV 噪声和 10% 融合，改为 Sim(3)+已知 K 渲染后下降 7.677 dB。与 DLT 分支使用同样生成参数、重新按相同 seed 推理，存在微小的 GPU 数值非确定性；未宣称两次 mesh 字节完全相同。

| 样本 | 通过三角化筛选/输入 | Sim(3) 尺度 | 3D 拟合 RMSE | Sim(3) PSNR |
|---|---:|---:|---:|---:|
| GELBlur33 | 496/6041 | 23.4065 | 18.5566 | 7.4348 |
| GELLinksmaster | 7939/8183 | 0.7532 | 0.0940 | 17.9378 |
| Adrenaline | 2133/5770 | 0.9430 | 0.0692 | 16.7200 |

代码中 `cupid/utils/stereo_geometry.py::triangulate_and_fit` 只按有限解、正深度、双侧重投影 <=2px、夹角 >=0.1deg 筛点；`fit_similarity` 是未加权 Umeyama。筛选通过不等于对应点正确或整体刚性一致，且没有拟合残差上限。第一样本极大的尺度与残差直接对应图中放大的错误定位。小夹角深度敏感和非刚性/异常对应点是需要进一步分离的原因，不宣称已经证明唯一原因。其他两样本即使 RMSE 较小仍有明显投影误差，不能只修第一样本然后宣布定位可靠。

当前冻结的开发候选为裁剪+官方 CPU 噪声兼容+10% 右结构融合+共享 UV 初始噪声+左 DLT，约 21.71 dB。Sim(3) 分支继续保留为负结果，不进入候选。下一步先在未参与选择的对象确认该部分迁移，再独立修复双目对应与稳健定位；不得用 GT 变换掩盖推理误差。

## 作业与错误

- 327249：基线已算出，控制代码误读 psnr 而非 psnr_db；已修复。
- 327263：依赖下载代理 TLS 失败；改用仓库内离线 wheel。
- 327273：基线和复制左图完成，诊断 JSON 无法保存 ndarray；已转为列表，无效点存 null 并保留有效性掩码。
- setuptools 缺失源码：每个 Slurm 作业使用私有 overlay 安装仓库内 75.8.2，导入 setuptools/Triton 验证通过，不修改其他作业环境。
- Git 多层共享对象 clone 曾超过嵌套限制；改从原始 paper checkout 建独立目录。失败目录没有提交作业。
- 327274：a4aff1a7476a2f16c8355bd11feebc228eb92582，COMPLETED 0:0，2:54。
- 327312：fcd532d95d0357c96a3f1cad34606b6773a13581，COMPLETED 0:0，3:28。
- 327323：687bfb7f9bb80b4bfe168c8c055594eb449688ea，COMPLETED 0:0，2:38。
- 327330：d25c36d7ca55b3bbcdc210c298962fdaee26bf8a，COMPLETED 0:0，2:59。

以上均 server13，1 GPU。程序错误、环境错误与正常完成后的质量退化分别记录。所有执行代码先本地 commit/push GitHub，再在集群固定 checkout 执行；训练未修改。

反思：结果只覆盖三只鞋和一个种子，尚未验证其他对象、novel view 或完整 3D。应冻结候选后，用未参与选择的样本确认，不能把开发集上的参数选择当成论文 benchmark 提升。
