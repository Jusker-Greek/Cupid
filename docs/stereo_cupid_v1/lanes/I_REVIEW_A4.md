# I A4：当前统一执行交接

2026-09-21 00:53 CST。取代A3的“待T接口修复”状态；历史提交与失败分析均保留。

已完成独立分支的 D/T/L/R 整合、逐次 `cherry-pick -x`、源码语义审阅、依赖映射和GitHub同步。
I发现的 `_pair_weight` 张量问题、T/L factory/返回协议问题，由T679修复；L发现的generator双消费与tracker初始化/退出问题，由Te45d232修复。
I与L分别静态确认：provider仅调用一次并在no_grad/autocast内物化，None/空manifest保持UNVERIFIED；raw记录供两consumer，evaluated receipt独立保存；local logger先创建，transport错误保留类型与UNVERIFIED，非transport错误继续失败。
这只关闭已列静态缺陷，不等于运行测试通过。

## 统一源码与责任

| lane | 已纳入的最新源提交 | 下一责任 |
|---|---|---|
| D | 25a51bc8a5474190662c50ca20a9c9ef634461cc | 真实Panda/GSO内容、canonical/renderer/proper-CV证据及target生成 |
| T | e45d232f564b5deaefa7fa95abf6e0153440fc62 | R返回的真实CPU/GPU首错、optimizer恢复证据 |
| L | 44ccef770d6f3ab78b0b074ffa0bfb27600dba42 | 原始预测/GT资格、分母、W&B服务器读回 |
| R | dd6523ec291296434e953bc70dcc0c09506ad505 | 唯一CPU/GPU调度、上传/完整root、新checkout与终态 |

完整源→集成提交映射在 `I_DEPENDENCIES.json`；本包执行SHA/tree在控制器的 exact-read handoff 消息中，不从moving branch名称推断。

## R立即承接

使用本包exact SHA/tree同步新checkout，配置 `CUPID_RUNTIME_MODE=data-contract` 和独立 `CUPID_RUNTIME_EVIDENCE`，由R在登录节点执行已有 `scripts/stereo_runtime_submit.sh`。
该脚本fresh duplicate audit后申请1CPU/4GB/15min，**不依赖模型权重或训练target**。
计算节点已封装：

1. I source契约与shell语法检查；
2. `scripts/stereo_data_contract_tests.py`：D 9项；
3. `scripts/stereo_evaluate_fixture.py`：L 13项；
4. `-m cupid.trainers.stereo_stage1_contract_tests`：T 9项；
5. `scripts/stereo_integration_contract_tests.py`：I 6项；
6. `scripts/stereo_data_manifest.py --config configs/stereo/data_panda125_audit_v1.json --verify-content --hash-assets`：完整Panda root重新审计。

合计37项**已准备、0项本轮实跑**。输出为各组件日志和Panda summary，不是把总exit当全部内容PASS。
Panda历史125对必须重读；train/validation保持对象级划分，不用同一Panda对象伪造独立heldout。
R恢复SSH后仅提交一个此CPU包；旧9ff/aa3等身份如果已实际提交，则保留并读终态，不抢跑重复作业。

## GPU执行与结果边界

冻结推理仍是 `STEREO_CUPID_V1_SHARED_SS`，5个核心文件逐路径与0c77ae9无diff。
R可在25文件root全SHA通过后独立运行完整Stage1+左Stage2；不等待新训练target。
其NPZ/mesh经I artifact checker、L无GT对齐评估，geometry失败仍保留分母；scene_unit不等于米。

新训练 `STEREO_CUPID_STAGE1_TRAIN_V1` 的entry、shared-flow目标、encoder均值、rank padding、loss记录、heldout FM loss、checkpoint和恢复接口已接通。
实际启动仍需要D真实target/划分及R真实asset哈希；不将模板改个BOUND标志就称就绪。
R train-smoke/train-ddp已接torchrun 1/2进程；20 update smoke、10→20 optimizer resume均未执行。
pretrained初始化是新optimizer从0开始；resume必须包含原optimizer/scheduler/scaler/RNG/游标，且新输出根。
FM validation loss不等于pose评测；prediction provider未绑定时所有pose字段保持UNVERIFIED。

## 晨间结果盘点（本包截止时刻）

| 项目 | 已有证据 | 尚无证据 |
|---|---|---|
| 代码集成 | GitHub exact提交、无冲突映射、静态修复审阅 | 当前Slurm CPU PASS |
| 资产 | 控制器/R报告本地六权重+14小文件校验、集群a12五权重 | 本包未获得完整cluster root验收/上传成功 |
| 运行 | R报告SSH在banner前关闭；I没有新SSH或Job | 模型推理、loss曲线、checkpoint、heldout结果 |
| 科学/Slides | 身份和no-alignment/单位边界保留 | accepted full result、正式科学表、S10 |

上述资产/网络是控制器与R交接证据，I本轮没有重新运行网络/哈希，不能当I独立实测。
R terminal到达后I负责审阅真实产物与失败，再交控制器推进；不因本交接文件完成而宣称整体研究完成。

反思：最大剩余不确定性是合法canonical监督与真实GPU路径；最可能的误判是将工程loss/已写checkpoint升级为泛化或米制恢复结论。
