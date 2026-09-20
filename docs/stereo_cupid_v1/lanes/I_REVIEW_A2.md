# I 第二批审阅 A2（待 owner 修复）

2026-09-21，静态 review。整合 T950ed87、D f8ffd52、L a8f275d、R71967eb/9248378。
精确 source→integration 映射见 `I_DEPENDENCIES.json`。本轮没有本地或远端测试，无新 JobID。

## 两个真实接口缺陷

1. D `collate_stage1_pairs` 把 T `ExactPairDataset` 注入的 float `_pair_weight` 保留为 list。
   T `reduce_terms` 调用 `weights.double()`，首个 validation batch 就会失败。
   已交控制器转 D，要求显式 [B] floating tensor，不改 padding/分母语义。
2. L `eval_factory(fullconfig,...)` 与 T `_init_hooks(config=...)` 关键字不兼容。
   L hook 返回 evaluation receipt，T 直接转发 L `log_evaluation`，导致额外关键字/已评价 rows 被当 raw sample。
   已交控制器转 T/L；缺 raw prediction 时应明确 UNVERIFIED，不空填 samples 假装评估通过。

以上通过源码调用链确定，不是 Slurm 实跑错误。原提交保留，修复必须由 owner 提交后继续 cherry-pick。
`eval_factory=null` 暂不触发第2项，但不等于它已被修复。

## 已通过人工语义核对

D `official_dense_targets` 与官方 `SparseUVStructure.get_instance`、`ImageConditionedMixin.crop_image/get_image_cond` 对照：
布尔 `const_ssuv=True` 支撑来自 crop 前 UV；clamp→crop affine→clamp；只有字符串 `crop` 重算支撑。
D loader 使用保存的整数 box，一次 crop RGBA、LANCZOS resize518，再 RGB*alpha；T adapter 仅 DINO normalize/encode，未再次 crop。
T frozen encoder 调用 `sample_posterior=False`，dense concat([ssuv,uv_volume])；双目 SS/noise/time 共享而 UV 分离。
这是公式/源码一致性，尚非数据 target 正确或模型运行证据。

## 立即执行包与后继

R 的计算节点可先执行：

```bash
"$CUPID_PYTHON" scripts/stereo_integration_check.py --output "$FRESH_SOURCE_RECEIPT" source --require-lane D --require-lane T --require-lane L --require-lane R
"$CUPID_PYTHON" scripts/stereo_data_contract_tests.py
"$CUPID_PYTHON" scripts/stereo_evaluate_fixture.py
"$CUPID_PYTHON" scripts/stereo_integration_contract_tests.py
```

最后一条新增六项跨模块回归，包含上述两个已知缺陷的复现；owner 修复前预期失败，不能把 AST 通过当接口通过。
临时合成 fixture 使用 TemporaryDirectory 自动清理，固定标记 SYNTHETIC/fixture，无模型结果含义。
R 原始数据小审计仍只 `--max-pairs 1`，JSON content_failed 不能被 exit0 掩盖。

训练 CLI 以 `T_INTERFACE.md` 为准。模板需真实 target/asset hashes 绑定为 BOUND_FOR_EXECUTION；
当前 D 未提供经历史 canonical/renderer/proper CV 闭合的真实 target，不能用反射矩阵生成伪目标。
10→20更新的 fresh-root optimizer resume、20更新单卡/双卡均仅待执行方案。

I checker 根据 R 环境经验，使用 `git diff --quiet HEAD` 与 `git ls-files` 避免 legacy mirror 上的 `git status`；
同时要求 SLURM_JOB_ID 与 SLURMD_NODENAME。历史 git status 异常根因未在本轮重现。
