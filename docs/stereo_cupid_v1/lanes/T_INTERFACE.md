# T Stage1 训练接口

独立实验 `STEREO_CUPID_STAGE1_TRAIN_V1`，当前为监督候选实现，未运行。
冻结推理 baseline `STEREO_CUPID_V1_SHARED_SS` 的文件没有修改。

## 训练契约与唯一科学选择

最小候选：官方 SUV flow 全参数监督微调；左右共享同一实例、SS target/noise/time；
UV target/noise 和条件各自独立。官方 `v=(1-sigma_min)*noise-x0`，
每眼每通道速度 MSE，SS/UV 按通道数加权，等于拼接后普通 MSE。
没有 GT 几何 loss、米制监督、GT 对齐或自动的 SSL 声明。
待控制器/用户确定的科学变量是训练目标选择；配置保留 objective factory 扩展接口，
不能将未来几何目标悄悄加进当前候选。

证据：`flow_matching/flow_matching.py:169` MSE；
`configs/generation/suv_flow_img_dit_L_16l8_fp16.json` 的16输入/输出、logitNormal(1,1)、p_uncond=.1；
`SparseUVStructureLatent.get_instance` 拼接SS与SUV latent；预编码使用posterior mean。
默认冻结 DINO、SS/UV encoder；decoder/Stage2未加入optimizer。训练只加载所需flow和编码器，
不修改官方资产，严格state_dict匹配；不从occupancy-only flow或旧HSSD checkpoint冒充初始化。
AdamW全部flow参数，bias/一维norm无weight decay，lr=1e-5，固定LR、clip=1，FP32主参数+AMP。
这是新微调候选，不声称精确复现官方训练（无EMA、无AdaptiveGradClipper）。

## 公共工厂

`data_factory(config['data']) -> {'train': Dataset, 'validation': Dataset, 'identity': JSON, 'collate_fn': optional}`。
Dataset为无内部隐藏状态的map-style CPU reader；预处理随机性只使用Python/NumPy/Torch CPU RNG。
自定义collate必须保留engine注入的`_pair_weight`并stack成[B]；不能过滤或重采样坏样本。
异常应直接失败，保留原pair身份。identity必须包含manifest/target-index/split/encoder哈希。

每sample：`ss_latent[8,16,16,16]`、`uv_latent[2,8,16,16,16]`、
`images[2,3,518,518]` float32 RGB黑底alpha复合[0,1]；可用`cond[2,N,1024]`替代images，
其DINO/crop来源也必须绑定。不做第二次crop或target归一化。

可选dense：`ss[1,64,64,64]`、`ssuv[2,1,64,64,64]`、`uv_volume[2,2,64,64,64]`。
T `OfficialTargetAdapter` 调官方SS/SUV encoder、sample_posterior=False。
配置`target_encoders.ss/uv`各含path（不含扩展名）、sha256、config_sha256。
D负责可证明canonical occupancy与逐侧canonical-to-CV相机；不自动修det=-1。

官方crop细节不能省略：`const_ssuv=true`为布尔true，支撑来自crop之前UV；
仅`const_ssuv='crop'`才随crop重建。先全图UV clamp，再仿射crop再clamp，
见`datasets/components.py:214`。encoder输入固定cat([ssuv,uv_volume])。
RGBA先按实际整数box crop，再LANCZOS resize518，最后RGB*alpha，见components.py:240。

`logger_factory(full_config,output_dir,rank)->callback(event,step,payload)`（工厂用位置参数兼容L）。
T adapter负责trackers生命周期，将train/validation映射为L的loss与optimizer事件，
checkpoint附真实SHA，pose未绑定显式UNVERIFIED。offline不等于S07，必须L/R server readback。

`eval_factory(full_config,output_dir,rank)->hook(model=bare_SharedStereoFlow,step=int,context=dict)`。
hook只在rank0调用、禁止collectives；直接接入L integration.eval_factory并保存其已评估结果。
可选`prediction_factory(full_config,output_dir,rank)->prediction_hook(model,step,context)`由I实现，
返回完整raw sample records；T同时传给L eval_hook与logger，不能将L已评估rows再次当raw。
未绑定prediction hook时，L eval明确UNVERIFIED，不能用FM validation loss替代pose评估。
所有rank进入边界，T广播rank0错误；其余rank不提前训练。context含config/device/data_identity/validation_dataset。
内置validation FM loss由全部rank无梯度执行并按真实pair数reduce，不使用DDP单rank forward。

## 启动与恢复

仅在R绑定的Slurm计算节点，使用已有overlay/env及fresh checkout：

```bash
"$CUPID_PYTHON" -m torch.distributed.run --standalone --nnodes=1 --nproc-per-node=1 \
  scripts/train_stereo_stage1.py --config "$BOUND_TRAIN_CONFIG" \
  --expected-commit "$CUPID_EXPECTED_COMMIT" --output-dir "$FRESH_OUTPUT"
```

配置模板拒绝直接运行，必须填真实target/assets并设`configuration_state=BOUND_FOR_EXECUTION`。
路径/hash来自R的计算节点核验，不在本地执行测试。训练入口不会联网下载。
`pretrained_init`只载官方SUV权重，step0和新optimizer；
`--resume-optimizer /absolute/step_00000010.pt`仅接收本engine完整可信checkpoint，
严格绑定相同配置/数据/预算/world size。恢复也必须新output root。
checkpoint含model/optimizer/scheduler/scaler/各rank Python+NumPy+CPU+CUDA RNG、step/epoch/batch游标。

20更新smoke可先加`--stop-after-updates 10`，再同配置新root恢复到20；
该运行上限不改变正式预算。需与不间断20更新对比checkpoint和下一batch/损失，
这才构成resume实证。双卡改配置world_size=2、每rank1pair、20更新；不沿用单卡optimizer恢复。
末尾padding样本权重0，全局loss分母只计真实pair；每完整epoch覆盖所有已绑定训练pair。

首轮训练预算必须由真实N与吞吐确定：若注册E个完整epoch，
updates=E*ceil(N/(pairs_per_rank*world_size))。还未得到有效target N和seconds/update，
因此当前只提供20更新smoke，不把任意100/1000步称full。

## 验证边界

本提交只有源码/接口审查，尚无导入、CPU、GPU、DDP、resume、W&B服务端证据。
R先Slurm CPU语法/接口检查，再1GPU 20更新、resume对照、2GPU 20更新与rank一致性检查。
I负责冻结接口后集成；R唯一GPU提交者。当前缺D可训练target、官方完整集群root与SSH恢复。

反思：最大未验证项是target canonical/crop正确性和真实GPU峰值内存；
速度MSE下降不证明UV物理对应、泛化或米制尺度正确。
