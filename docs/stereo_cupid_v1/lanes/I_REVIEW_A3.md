# I A3：统一 CPU 执行包

2026-09-21 00:49 CST，静态审阅；没有新测试/模型实跑证据。

已整合 D 至25a51bc、T至0d69d72、L至44ccef7、R至dd6523e，完整映射见 I_DEPENDENCIES.json。
五个 V1 frozen 路径与0c77ae9无diff。以下命令只能由R在Slurm计算节点执行，fresh checkout/root，保留JobID与日志。

## A2首错处置

- `_pair_weight`：T6794575改为scalar float32 Tensor，D现有collate会stack为[B]；静态闭合，无需D重复改。
- factory：T位置传参调用L；不再受config/fullconfig关键字差异影响。
- evaluation：T把raw samples单独交logger，L evaluated receipt独立写evaluation.jsonl；无prediction则发evaluation_status=UNVERIFIED。
- I六项跨模块fixture直接使用实际T ExactPairDataset和_init_hooks，无mock CUDA、无强迫L重命名。

这是代码层闭合，Slurm回归仍待执行。T4项、D9项、L13项、I6项是**测试源码计数，不是通过计数**。

## 准确命令

```bash
"$CUPID_PYTHON" scripts/stereo_integration_check.py --output "$FRESH_SOURCE_RECEIPT" source \
  --require-lane D --require-lane T --require-lane L --require-lane R
"$CUPID_PYTHON" scripts/stereo_data_contract_tests.py
"$CUPID_PYTHON" scripts/stereo_evaluate_fixture.py
"$CUPID_PYTHON" -m cupid.trainers.stereo_stage1_contract_tests
"$CUPID_PYTHON" scripts/stereo_integration_contract_tests.py
"$CUPID_PYTHON" scripts/stereo_data_manifest.py \
  --config configs/stereo/data_panda125_audit_v1.json \
  --output "$FRESH_PANDA_AUDIT_ROOT" --verify-content --hash-assets
```

R的 `data-contract` mode 已完整封装以上源检查→D9→L13→T4→I6→Panda内容审计，1CPU/4GB/15min。
小 `contract` mode 仍只带源检查/一对数据/可选L fixture，不能与完整data-contract混淆。
Panda125是历史预期（1对象5轨迹），输出summary才是当前实读数量；单对象无法同时支持对象级train/validation。
即使程序exit0，也检查counts.content_failed/incomplete_records、全部候选分母和scope；不把“扫描完成”写成全量内容PASS。

## 尚未闭合的错误/外部依赖

| 项目 | 首失败/缺证据 | owner及下一动作 |
|---|---|---|
| 预测provider生成器 | T prediction_hook若返回iterator，L eval先消耗后logger得到空列表 | T：一次调用后materialize list，None保持缺失，非空heldout的空清单不可宣称EVALUATED成功 |
| tracker lifecycle | T logger先初始化/finish sinks，早于local durable初始化或未经异常隔离 | T/L：失败保留本地事件并显式tracker UNVERIFIED，不能把sink失败静默当S07 |
| SSH | 控制器/R报告banner前关闭；I未重探、无远端shell | R：既有入口恢复后fresh duplicate audit，不改VPN/SSH/路由、不重下已校验资产 |
| 真训练target | canonical occupancy/历史renderer变换/proper CV外参未闭合 | D：先真实数据与geometry inventory，再生成可追溯target；禁止将det=-1静默改成GT |
| 真实运行 | 无模型loss曲线/checkpoint/heldout/服务端readback | R执行后交I审阅；代码或fixture通过不能替代 |

## 已准备的训练路径

R支持train-smoke（1GPU）/train-ddp（2GPU），T入口torchrun、20 update模板、10 update bounded-stop/fresh-root optimizer resume。
配置仍须真实hash/manifest绑定为BOUND_FOR_EXECUTION，不能只改这一标志；I没有伪造bound配置。
恢复前后记录start.step、每个train.step、checkpoint hashes、actual pair分母与终态；pretrained_init不能写成resume。
首个epoch/full candidate不等于S08授权；先按S05/S06/S07证据推进。

晨间汇报优先真实推理NPZ/mesh、训练曲线/checkpoint、独立heldout。若SSH或target仍阻塞，只列已完成代码、实际测试与首错，不填虚构结果。
没有accepted full科学结果时，不改中央正式科学表或total slides；本I报告为工程证据。

反思：最不确定的是历史canonical监督而不是接口形状；最可能误报的边界是把FM validation loss写成pose/米制结果。
