# T 交接：Stage1训练候选

Owner task：`01a0bfa4-b891-78c0-8348-9e7d89235947`。
Controller：`01a0ba51-e1eb-7012-8147-c2cf36ad66b8`。
Worktree：`/Users/ruikegu/.codex/worktrees/7024/Cupid`。
Branch：`codex/stereo-stage1-train-t`，base `0c77ae9c6648b918c820f79dbe15f80235c17709`。

## 精确交付

T首实现 `950ed8716b2f64f2d9ac3f757467d5ed85b5f5c5` / tree
`19dd71bbcc51c8e9bb6bc3ce9db665125f725574`。
T接口及DDP/resume增强 `6794575a90ec5b2b8b731730eacb74ca3ab89e0b` / tree
`50fbd93847c860120e36db4e1d1cdd2621f84be1`。
两者均GitHub API SHA/tree与远端ref读回一致。最后一个跟进提交由本文件所在commit标识，
仅替换entry的git status检查为git diff HEAD/ls-files、保留失败rank诊断并补本交接。
I应cherry-pick两个T提交及本文件所在跟进提交，不应重复应用下面已集成的D/L提交。

依赖：D `e05bb99a52daa5dfaf9faea60716084ba8d82b7f`、
`f8ffd521463ad9dadd7e052f275104bb7eadf9c1`；L `b5264958493a5b1d712b88b73a64b5838e4a9654`、
`a8f275d9ae2b638f457881a8a274480fc0f1a8d8`。后续L fixture更新由I集成，不需T修改L文件。
没有修改冻结V1推理、中央台账、共享原Cupid或远端源码，没有提交Slurm。

## 已实现与边界

- 真正官方16通道SUV flow，两眼同一权重；共享SS target/noise/time，各自UV/条件；
  channel-weighted velocity MSE等同官方拼接MSE，无toy network、无几何SSL伪称。
- 官方权重严格载入；hash-bound SS/UV encoders posterior mean；DINO冻结，Stage2不入optimizer。
- AdamW、FP32主参数/AMP、真实更新计数；AMP溢出保存失败event，同batch/RNG降低scale再试，
  16次数值恢复耗尽真失败，不能将skip当optimizer step。
- 单rank/双rank NCCL，完整epoch无丢样本，末批零权重，正确DDP全局分母。
- checkpoint完整保存RNG/step/sampler/optimizer/scheduler/scaler；原子独占发布/不覆盖旧attempt。
  各rank模型byte SHA一致性、参数是否变化、checkpoint文件SHA写events。
- rank0 W&B/TB经L callback，训练和validation加权loss真实记录；eval hook显式调用。
  缺raw预测manifest记UNVERIFIED，不把FM val当pose，不把offline当S07。
- 20更新单/双卡模板、1完整数据epoch候选。epoch预算由有效N计算，未经批准不称正式full。

静态审查发现并修复：官方loader重复关键字的覆写风险、D自定义collate对float padding weight
收为list、L工厂关键字名称不一致、L已评估rows不能再次当raw、rank0 eval需no_grad+AMP、
日志需保全RNG。以上是源码审查，不是测试PASS。

## R唯一运行者：下一条命令

完成I集成后的fresh GitHub精确checkout，沿R现有overlay环境，在Slurm CPU allocation中：

```bash
"$CUPID_PYTHON" -m cupid.trainers.stereo_stage1_contract_tests
```

4项无模型CPU fixture验证完整唯一epoch、双rank末批、恢复suffix、dataset RNG、D collate接口；
未在本地运行。再做导入/语法检查及D/L现有fixture。失败保留attempt、回T根因修复。

真实target和官方资产绑定后，控制器登记目标/参数/split/budget，再由R唯一提交GPU：

```bash
"$CUPID_PYTHON" -m torch.distributed.run --standalone --nnodes=1 --nproc-per-node=1 \
  scripts/train_stereo_stage1.py --config "$BOUND_TRAIN_CONFIG" \
  --expected-commit "$CUPID_EXPECTED_COMMIT" --output-dir "$FRESH_OUTPUT"
```

单卡20更新/30min为首尝试预算，真实耗时以R日志为准，不承诺期限内完成。
保存`step_00000010.pt`、`step_00000020.pt`与`events.jsonl`、`evaluation.jsonl`、
`stereo_observability/events.jsonl`、TB和`tracking_receipt.json`。
`--stop-after-updates 10`后用同配置在新root `--resume-optimizer old/step_00000010.pt`到20，
比较连续与恢复的sampler/RNG/optimizer以及模型变化，CUDA数值确定性需实证。
双卡使用`train_stage1_smoke_2gpu.json`（一层extends、配置顶层key替换），nproc=2，
同机2GPU，每rank1pair，全局2pair；只能从官方初始化，不拿单卡optimizer变world size恢复。

模板当前仍有真实路径/DINO SHA/target绑定占位；必须冻结后设BOUND_FOR_EXECUTION。
不会因“文件存在”自动宣称target就绪，也不生成任何GT。

## 剩余归属

1. D：canonical occupancy、历史renderer轴/归一化、proper canonical-to-CV相机、crop语义和数据split闭合。
2. R：SSH恢复、完整权重组装、DINO SHA、Slurm CPU/1GPU/2GPU/resume与吞吐/峰值内存证据。
3. I：集成精确提交；可选prediction_factory从训练model.flow做真实采样并提供全部raw预测records。
4. L/R：online/offline恢复与W&B服务端readback，pose指标coverage/缺失声明。
5. Controller：唯一待选科学变量是监督候选或其它objective；正式登记真实N、epoch、预算和评估。

当前没有运行job/checkpoint/loss/W&B server记录。阶段只能报告实现/静态审查，S03–S10未验证。
当前阻塞不影响继续代码/接口检查，但没有真实targets就不能启动有效监督训练。

## 后续日志/迭代器修复

T追加修复先建立L durable callback，再初始化W&B；仅明确通信异常继续本地logging，
记录异常类型与UNVERIFIED，不持久化异常文本。配置/依赖/编程错误继续失败。
finish无论成功/通信失败/编程异常，writer.close均在finally执行。
tracking_receipt包含entity/project/id/mode，init/finish状态不等于服务端PASS。
缺pose输出对L METRICS全部逐项记录UNVERIFIED，含pose_scale与scale误差。
prediction provider只调用一次，返回iterator在no_grad内单次list物化；None与空manifest明确缺失，
L eval结果仅保存receipt，原raw list交logger。D最新25a51bc依赖已合并，identity只说
target_index_validated与content_validation=ON_ACCESS；不能据工厂构造推断全部内容已验证。

CPU fixture增至9项（仍未本地执行）：新增通信init失败保全日志、非通信错误不吞、
finish总关闭writer、全部pose缺失项、generator两样本含一失败仍保留num_expected=2/coverage=.5。
下一命令仍为Slurm内`python -m cupid.trainers.stereo_stage1_contract_tests`，结果交R/I核验。

反思：最不确定的是canonical target物理含义与GPU内存/数值稳定性；最容易误解的是
监督loss下降或共享SS自动证明双UV对应、泛化或米制尺度。三者都需要独立真实评估。
