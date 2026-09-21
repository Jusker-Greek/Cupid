# D 静态契约审计

审计对象：`cf8cc24a414db6f86b20219c5c51000b960ef781` / tree `0f1c34894d14e01a4c339f6887e72812b26ed9b0`。

## 已闭合的工程契约

- `data_panda125_audit_v1.json` 和 `data_gso_stage1_v1.json` 都明确写出数据根、固定 seed、对象级 split、scene unit，以及 `metric_meters_verified=false`。
- `discover_pairs()` 只从实际目录生成记录；数字 stem 映射 `000` 与 HDF5 `0`，缺文件、空轨迹、元数据解析失败和别名冲突保留在清单中，不补造 frame。
- `load_pair()` 保留原始 RGBA、alpha mask、depth、saved w2c、FOV 推导 K 和 full-pixel 映射；会检查 trajectory metadata SHA、PNG/HDF5 colors 一致性、depth sentinel 和矩阵形状，不静默修正反射矩阵。
- `stereo_data_manifest.py` 的 bounded 运行会保留完整候选分母；`--verify-content --hash-assets` 才能声明内容已读和图像 hash 检查，summary 明确 scope，不把 registry 行数写成 pair 数量。
- target factory 绑定 pair/object/trajectory/frame/split、source asset hashes、target NPZ hash 和 geometry receipt；target 内容按访问重新校验。

## 下一阶段仍缺失的字段

1. `canonical_mapping`: 原始 OBJ 到 canonical mesh 的完整矩阵、坐标系、单位和证据文件；当前 normalization 数值与 bbox 只能作为候选线索。
2. `canonical_to_cv`: 每侧 proper CV 外参、from/to frame 和手性说明；saved NPY 的 determinant 约为 -1，不能直接喂 `project_cv`。
3. `intrinsics/depth_semantics`: renderer 实际 FOV 轴、主点、pixel aspect、depth 是 Z 还是 ray distance，以及生成版本身份。
4. `crop_xyxy`: 每侧真实整数 PIL crop，必须与官方 clamp 后 UV 仿射和 RGB*alpha 预处理绑定。
5. `occupancy`: 经固定 TRELLIS voxelizer 生成的 canonical 64^3 occupancy、mesh/source SHA 和 provenance receipt。

在这五项闭合前，清单可以支持数据格式/泄漏审计和 raw pair smoke，但不能生成训练监督或声称科学结果。Panda 单对象也不能被轨迹拆成正式 validation/test 对象。

## 首错与下一动作

当前没有新的运行首错；远端 CPU/renderer 证据仍为 `UNVERIFIED`。R 的下一动作是运行 Panda bounded audit 和 renderer source evidence，返回带 commit/tree、job、scope、summary、源文件 SHA 与有界行号片段的 receipt。D 随后依据上述字段决定是否生成 canonical occupancy 和 dense targets；缺字段时只提交精确补证方案。

本文件是静态工程审计，不是数据计数、CPU PASS 或科学结果。
