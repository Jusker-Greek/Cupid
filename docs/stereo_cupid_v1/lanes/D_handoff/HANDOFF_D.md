# HANDOFF_D — Stereo Stage-1 数据

D task `01a0bfa4-b887-7df2-a39e-2b1b776e377c`；控制器 `01a0ba51-e1eb-7012-8147-c2cf36ad66b8`。
隔离worktree `/Users/ruikegu/.codex/worktrees/9506/Cupid`，branch `codex/stereo-stage1-lane-d`，基线 `0c77ae9c6648b918c820f79dbe15f80235c17709`。

## 已交付

1. `e05bb99a52daa5dfaf9faea60716084ba8d82b7f` / tree `44f35702082b2d417af2678eab8b88942adb85c2`：raw schema/reader、清单CPU入口、固定对象split、content hash重复审计。GitHub API和ls-remote exact-read通过。
2. `f8ffd521463ad9dadd7e052f275104bb7eadf9c1` / tree `c0f482136e70ee68b1795041bd626117d9a25b85`：T factory、dense/latent index、官方dense target入口、8项CPU contract checks。GitHub API和ls-remote exact-read通过。
3. 本handoff提交：geometry inventory入口与执行交接，精确SHA由控制器消息记录，避免文档自引用hash。

所有实现仅新增D责任文件；未修改冻结推理、训练器、采样器、logger、中央台账或共享Cupid workspace。详细字段见相邻 `../D_SCHEMA.md`。

## T/I集成

直接调用 `cupid.datasets.stereo_gso:build_stage1_datasets(config['data'])`。
data需要manifest/root/target_index/target_root，target_kind选择dense或latent。
返回train、validation、collate_fn、identity。T执行encoder posterior mean；D返回dense不占GPU。shape与官方bool const_ssuv裁剪语义已经经控制器确认。

I按顺序cherry-pick上述提交。仍需远端CPU测试，不能从commit或8项测试源码推断测试PASS。

## 当前证据边界

本轮两次已认证入口尝试均在banner前 `Connection closed by 10.10.7.1 port 22` / exit255，没拿到远端shell；未改SSH/VPN/代理/路由，未提交Slurm。没有真实全量清单统计或新target。阶段仅S02实现候选，CPU/runtime UNVERIFIED，不继承旧Panda304071测试PASS。

已实现读取/准备不等于GSO训练监督已闭合。原始w2c det=-1和历史canonical变换仍需实际数据/renderer核验；禁止静默翻轴后称GT。现有权重齐备也不能生成缺失的真实occupancy。

## 下一条执行链（R协调提交，D解释结果）

1. R SSH恢复后fresh squeue/sacct确认没有D重复job；新checkout绑定整合后的精确SHA/tree。D请求CPU身份 `D_DATA_A1`，资源参考已有CPU分区，1CPU/16GB/10min先单测及Panda；全量扫描另行CPU身份与充足时限，不占GPU。
2. 在Slurm shell复用 `scripts/submit_stereo_cupid_audit.sh` 已有Python/overlay环境设置，执行：

```bash
python scripts/stereo_data_contract_tests.py
python scripts/stereo_data_manifest.py --config configs/stereo/data_gso_stage1_v1.json --output "$D_DATA_OUTPUT/inventory_bounded" --max-pairs 20 --verify-content --hash-assets
```

`D_DATA_OUTPUT`必须为新结果目录。先20对是真实格式smoke，不是全量数量；若格式错误修首次错误、同步后fresh输出，不无修改重跑。

Panda125检查另用config把dataset_id/root改成gso_stereo_output_random对应路径，registry设null；配置源码应本地提交后同步，不远端写代码。主训练仍GSO_1K_200。

3. 数据内容通过后去掉max-pairs运行全量内容/重复审计，保留失败records和分母；足够CPU时限，不在登录节点遍历/哈希。读取summary的scope、counts和content_leakage_status；对象目录数/registry rows不可替代pairs。
4. 从同一清单采集canonical缺口：

```bash
python scripts/stereo_data_geometry_inventory.py --manifest "$D_DATA_OUTPUT/inventory_bounded/pairs.jsonl" --root /public/home/ricky/DATASET/GSO_1K_200 --output "$D_DATA_OUTPUT/geometry_bounded" --max-objects 3
```

只写候选证据，不生成虚假的geometry PASS receipt。读取Gazebo当前OBJ hash、当前renderer hash、normalization候选关系与保存矩阵，随后D/T定位官方voxelize路径和历史camera转换。镜像/反射语义需要逐数据版本证据，不能套Panda。
5. 真正已核canonical occupancy和CV外参后生成geometry receipt/index，CPU运行stereo_data_targets.py；T/R用生成dense NPZ执行官方encoder和训练。latent批量GPU由R唯一排队。

## 反思

- 当前不确定：GSO各版本canonical坐标与反射来源；数值归一化吻合只能支持假设，不能单独证明历史生成矩阵。
- 可能盲点：同名对象split+像素hash能发现明确泄漏，不能排除重命名资产或不同渲染的同一资产；需要asset hash分组复核。

## 后续独立实现：官方occupancy适配

`stereo_data_occupancy.py`已提供CPU入口：传现有官方voxelizer、真实canonical mesh及其映射证据receipt，校验官方source blob后调用其_voxelize，产occupancy.npy及receipt。精确源码与接口见D_SCHEMA末段。不是从depth生成替代目标；真实canonical mapping仍需采集验证。

R请求已落实：Panda配置`configs/stereo/data_panda125_audit_v1.json`已新增，直接传给stereo_data_manifest.py；不需要远端编辑config。当前CPU checks为9项，新增metadata变化拒绝；源hash契约含trajectory_metadata，避免旧target与已改相机元数据混用。factory identity只声明index核验，逐NPZ内容核验在on-access进行。

继续责任已明确：`../D_GEOMETRY_EVIDENCE_CHECKLIST.md`列出G1–G6最小缺证、R回收第一包、D判定与下一步实现链。历史精确commit不是额外人为门槛；已有canonical mesh/真实camera/K足以直接证明变换链时即可闭合。反之不能只根据det修正或bbox吻合制造GT。R返回证据后D继续真实目标生成，不把此问题留作无人负责的文档阻塞。

## 2026-09-22 Slurm target-manifest audit

统一 exact source：commit `85d2f5fcf7842758fcc37c6f057e69f1970d2178`，tree `df2c4ddfd9f0bf95c03a22a326861ad06640802a`。

- `309270`：首个 launcher 失败，ExitCode `0:53`；`--output` 父目录未预创建，未执行数据代码。保留为工程首错，不重用。
- `309271`：server14，COMPLETED `0:0`，9项 contract tests 全部通过。Panda manifest 为125/125 candidate、125/125 files complete、125/125 content verified、`proper_rotation_pairs=0`；唯一对象 `Android_Figure_Panda` 只进入 train，validation/test 为空。manifest SHA256 `68168c1020c47d9828f4764278a8ab6b3e565b58781d7ada496e3b3307b0e9cb`，summary SHA256 `45f3212e5852df7f98034c931ec6c8710db9ab0313bf0f71b7c6a49ce4195025`。
- `309271` GSO bounded：20 candidate/20 complete/19 content verified/1 content failed（并行文件系统 HDF5 lock）；`HDF5_USE_FILE_LOCKING=FALSE` 复核在 `309272` 后变为20/20。registry 1025 rows 明确记录为 `not_a_pair_count=true`。
- `309272`：server43，COMPLETED `0:0`，fresh GSO bounded manifest 与 blocker receipt。20/20 content verified；canonical occupancy 0、canonical-to-CV 0、proper-CV 0、valid target 0，20/20 `UNVERIFIED`。manifest SHA256 `5006ef3319d94448531cd2024bafa3bce8321eedb5675ad33bd8cd2162e07949`；receipt `/public/home/ricky/RESULTS/STEREO_CUPID_D_TARGET_AUDIT_85D2F5_A3/target_audit_receipt.json` SHA256 `847da0543dd7108872bdb68202c6f1fb25db30df9469f93325caed9fe44ef7d2`。

最短 blocker 已由 receipt 固定为：从有 provenance 的 canonical mesh 用 pinned official voxelizer 生成 occupancy；证明每侧 canonical-to-CV proper 外参与 K/depth provenance；绑定真实 crop box、renderer/source hashes。309242 的 `geometry_status=OK` / `scientific_claim=UNTESTED` 仅是预训练 pilot 输出，receipt 明确 `not_a_gt_target=true`，不能替代上述 target。
