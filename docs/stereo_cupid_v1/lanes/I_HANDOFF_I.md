# HANDOFF_I — A3 集成包

状态：D/T/L/R 首批及后继已整合并手工审阅；未在本地执行脚本或测试，集群验证 UNVERIFIED。
源提交与集成 SHA 映射见 I_DEPENDENCIES.json，最新执行说明见 I_REVIEW_A3.md。
训练 target 与外部网络尚未验证，T 尚有预测 provider/日志生命周期修复待接。本文件不声明训练就绪。

Owner task `01a0bfa4-bcf6-7761-a7a1-948b703719ee`；控制器 `01a0ba51-e1eb-7012-8147-c2cf36ad66b8`。
分支 `codex/stereo-cupid-lane-i-integration`，基线 `0c77ae9c6648b918c820f79dbe15f80235c17709`。
交付 commit/tree 由 GitHub exact-read 消息提供，避免在同一 commit 内自引用。

文件：`I_DEPENDENCIES.json` 登记 source→integration 依赖；`I_INTERFACE_CONTRACT.md` 登记责任/完成标准；`scripts/stereo_integration_check.py` 检查源码冻结与 frozen V1 推理产物。

## 下一条可执行命令（R 的 Slurm compute allocation 内）

在精确同步本分支后、已绑定既有 Python runtime/overlay 的计算节点环境中：

```bash
"$CUPID_PYTHON" scripts/stereo_integration_check.py \
  --output "$CUPID_INTEGRATION_CHECK_RECEIPT" source
```

`CUPID_INTEGRATION_CHECK_RECEIPT` 必须为独立 fresh 文件；本检查不加载模型、不提交 Slurm。
只有依赖实际整合后，才添加 `--require-lane D --require-lane T --require-lane L`。
未要求某 lane 不意味着该 lane 完成；receipt 明确列出每个 lane 状态。

V1 推理终态后：

```bash
"$CUPID_PYTHON" scripts/stereo_integration_check.py \
  --output "$CUPID_INFERENCE_CHECK_RECEIPT" inference \
  --run-root "$CUPID_OUTPUT_DIR" --run-commit "$CUPID_EXPECTED_COMMIT" \
  --run-job "$CUPID_PILOT_JOB_ID"
```

PASS 仅代表 receipt/NPZ/mesh 基本自洽，另读 `model_status`、`complete_model_path`、`geometry_success`。
本检查不验证实际预测准确率、GT 真实性、完整 mesh 拓扑或 scientific claim，也不能取代独立 evaluator。
未拿到真实产物时禁止创建假 receipt 冒充一次运行。

## 后续 owner

D/T/L 后继提交一旦到达，I 立即审阅公共接口并 cherry-pick；T 提供训练入口，R 提供通用 Slurm launcher，I 审阅绑定。
R 负责 SSH/资产/集群同步/唯一 GPU 提交。R 返回终态后 I 审阅并交控制器，控制器负责 E00。
任何 owner 首错附 source/integration SHA、JobID、失败日志与下一条修复命令，不以重复文档更新代替修复。

目前外部阻塞来自控制器最新证据：SSH 在 banner 前关闭，完整 25-file 模型根尚未形成。此处没有重探或新 job。
