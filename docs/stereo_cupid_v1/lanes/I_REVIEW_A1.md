# I 首批集成审阅 A1

时间：2026-09-21 00:38 CST。证据等级：手工源码审阅与 Git 元数据；未执行 Python/shell 测试。

| lane | source commit | integration commit | 审阅结果 |
|---|---|---|---|
| D | e05bb99a52daa5dfaf9faea60716084ba8d82b7f | ec7f1f1c10701e71807bf843fa76f634c010154a | raw pair reader 可独立用于 CPU 审计；不可直接输入 Stage1 trainer |
| L | b5264958493a5b1d712b88b73a64b5838e4a9654 | a854af0c28e690b498f22dad5f71724097e7f553 | callable 五种事件已发布；无 collectives，rank>0 无写盘 |
| R | e867ff20a5f1f710a7b746b12bbffc951d5bb03c | 23b2ad0ed9bb109bae7a632d48481a9cf3cae9f7 | assemble/pilot 支持 fresh roots、提交锁、重复活动 job 审计与全量 SHA；训练 mode 待 T |

三次 cherry-pick 均无冲突，包含 `-x` 原提交映射。`git diff --check` 无输出，五个 frozen 路径与基线无 diff。
source 原提交的 GitHub SHA/tree 由控制器/R 发布；I 从 fork fetch exact SHA 后审阅。集成分支的最终 GitHub exact-read 另随 milestone 发布。

## 已查到的真实接口缺口

1. D 的 `load_pair` 输出 raw RGBA/mask/depth/w2c/K 和 `training_target_ready=False`；`collate_pairs` 返回 list。
   T 的 factory 必须返回 train/validation/identity/collate_fn，训练 batch 必须含 ss/uv/images 或 dense ss/ssuv/uv_volume。
   因此这不是通过命名重映射就可直接运行的训练包。D 正在提供 target factory；不将 raw reader 标为训练就绪。
2. L `logger_factory(config, output_dir, rank)` 要求 config.identity 五字段：experiment_id、attempt_id、git_commit、git_tree、slurm_job_id。
   T 必须传入既有 writer/wandb_run；L 不负责初始化/finish，不应期待仅 import logger 即有 W&B。
   `callback(event,step,payload)` 事件严格为 loss/optimizer/checkpoint/status/evaluation。
3. D 保存的反射矩阵和 FOV 推导 K 保持 UNVERIFIED；L 要求同 canonical（轴、origin、normalization）且 GT verified/provenance 完整才算误差。
   这一约束兼容，不应把 D 的 w2c_saved 直接填入 L 的 verified GT。
4. R 暂无训练 mode；本包可做 CPU source/raw 数据检查和 frozen V1 推理，不具备训练恢复/optimizer/heldout 的实跑证据。

## 立即交 R 的最小 CPU 包

无需等待权重，可在 R 协调的现有/新 CPU allocation 内，用既有 Python 及 numpy/PIL/h5py overlay：

```bash
"$CUPID_PYTHON" scripts/stereo_integration_check.py \
  --output "$CUPID_INTEGRATION_CHECK_RECEIPT" source \
  --require-lane D --require-lane L --require-lane R

"$CUPID_PYTHON" scripts/stereo_data_manifest.py \
  --config configs/stereo/data_gso_stage1_v1.json \
  --output "$CUPID_RAW_PAIR_AUDIT_ROOT" --verify-content --hash-assets --max-pairs 1
```

两个输出变量均由 R 分配新的绝对路径。第二条只核验一个实际候选，不据此宣称全量有效 pair 数、无全量泄漏或 heldout 就绪。
此处只是待执行命令；未提交 JobID，I 不单独申请 CPU/GPU。

## 后继

T 发布入口、D target factory、L evaluator/readback 一到即继续 integration。
R 若得到 V1 结果则运行 I inference checker 和 L 原始预测评估，工程产物可立即汇报，不等训练全链。

反思：核心剩余风险是 canonical target 的实证来源，不能由 shape 检查或 scene_unit 标签消除；SSH 恢复也不会自动关闭该风险。
