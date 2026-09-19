# GSO 资产与渲染器定位记录

2026-09-20。用户确认上一轮找到的`CUPID+Hi3DGen/gso_stereo_output_random/Android_Figure_Panda`就是本轮GSO-toy副本。已确认的125对计数仍仅针对该副本。

## 本地查到什么

1. 当前Cupid目录、同级项目的GSO文件名检索、用户文档目录Spotlight文件名检索：找到GSO消费端loader/config，未找到与该trajectory_info相关的生成脚本或原始mesh。没有全盘递归、没有解压大ZIP、没有把其他项目结果并入本实验。
2. 同级`Stereo_Foundation_Model/data/dataset_stereo_gso.py:20-27`明确支持`object/trajectory/{left,right}/000.png,000.npy`和trajectory_info.json，匹配该副本结构。
3. 该文件:386-418把NPY称为c2w，遇det<0执行`R @ diag(1,1,-1)`并翻转第三个平移分量；README:175-178记载过反射修正。**这是历史消费端实现，不是生成器证据**；不要据此自动套用到新双目几何。
4. 同级`Stereo_Foundation_Model/docs/TRAINING_CONFIGURATION_FINAL.md:122`给出历史集群数据路径`/public/home/ricky/DATASET/gso_stereo_output/Android_Figure_Panda`。
5. 同级`xfactor_reproduce_overfit/train/configs/config_2v_GSO_left_right_only.py:30`给出`/public/home/ricky/DATASET/GSO_1K_200`；Stereo_Foundation_Model README:69另有gso_stereo_normalized_zaxis_5traj_7f_1。**这些是后续远端定向查找入口，尚未验证存在，不能等同random副本。**

目前仍未定位：真实原始3D文件绝对路径、生成脚本绝对路径/commit、renderer运行命令。集群无法进入，不能伪造这些结果。

## 联网核对的源码入口

- [Google Research 官方数据说明](https://research.google/blog/scanned-objects-by-google-research-a-dataset-of-3d-scanned-common-household-items/)：公开资产为引用Wavefront OBJ/PNG的SDF模型，经Gazebo发布。公开GSO资产与用户定制双目渲染流水线是两件事；该文不能证明用户保存的baseline/normalization约定。
- [BlenderProc 官方双目示例](https://github.com/DLR-RM/BlenderProc/blob/main/examples/advanced/stereo_matching/main.py)：设置K、PARALLEL stereo、depth和segmentation并写HDF5，适合比对生成器API和字段。该示例使用SUNCG场景及不同参数，**不能直接当作本GSO-toy原脚本**。
- [lyltc1/BlenderProcGSO](https://github.com/lyltc1/BlenderProcGSO)：第三方针对GSO的BlenderProc2渲染项目；README列出`BlenderProc/resources/GoogleScannedObjects/<object>/materials`资产布局。没有证据表明用户采用这一仓库。源码scripts子页本次获取失败，不假造脚本文件名。

没有下载资产、安装BlenderProc、克隆这些仓库或运行网上代码。查询精确字符串`gso_stereo_output_random`/`trajectory_info.json`未找到对应公开实现。

## 连接证据

- 依据全局AGENTS执行一次既有SSH入口，选项`BatchMode=yes,StrictHostKeyChecking=yes,ConnectTimeout=10`。
- exit 255：`Connection timed out during banner exchange`。尚未到认证/远端shell，不能说密码错误或作业已提交。
- `ssh -G`白名单读取确认显式入口与已配置GridServer具有同一hostname/user/port（地址不在本共享文档展开）；未换主机、账号或端口试探。
- `git ls-remote fork refs/heads/codex/cupid-cuda118-toolkit-a49`成功返回基线cc95f36，GitHub网络与凭据可用。

## 恢复后的有界顺序

在既有连接恢复后先读远端适用规则和登录目录一层清单，定位用户记忆中的gso目录。只在已确认项目/资产根查找名称包含gso、Android_Figure_Panda和render的文件；优先读manifest/README/作业脚本。用上述历史数据路径和BlenderProc API作为线索，绝不把候选路径当已验证路径。

同时可以运行已实现的无标定Stage1生成分支；单位/GT补齐只影响米制解释和评测，不阻止导出共享支撑与双UV。训练目标若需改变应由用户明确，不因联网找不到原renderer就自行发明监督。
