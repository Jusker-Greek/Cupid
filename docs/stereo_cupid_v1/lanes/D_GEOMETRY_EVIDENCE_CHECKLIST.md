# D：真实target最小缺证清单与判定

身份：`STEREO_CUPID_STAGE1_TRAIN_V1`，D负责解释/实现，R负责唯一运行调度。
本页是工程数据契约，不新增科学阈值、不请求额外审批、不要求为了档案齐全无限等待历史commit。
截止当前无新远端数据回收；下表现状来自基线审计与本轮源码。未知不等于数据不存在。

## 1. 六项最小输入

| ID | 当前已知 / 缺失 | R最小采集 | D可判定条件 / 下一动作 |
|---|---|---|---|
| G1 资产→canonical | Panda OBJ及normalization数值已有审计；导入轴`(x,y,z)→(x,-z,y)`仅有数值支持。全量其他对象未知。 | geometry_inventory的OBJ SHA、原始bounds、metadata SHA/normalization；renderer的load/import/normalize/对象transform调用；若存在，生成时保存的canonical mesh/scene transform。 | 原始资产身份一致，明确记录Xcanon=A·Xasset（完整矩阵、frame、单位）。可由保存的canonical mesh/生成变换直接闭合，或由精确生成代码+导入设置闭合。bbox/scale单独吻合不够。D按该矩阵生成新canonical PLY，保留原OBJ，不自由拟合GT，不用预测点对齐。 |
| G2 canonical→camera | Panda保存NPY是inv(left_pose)前三行；det≈-1。当前renderer翻一列的线索存在，真实渲染camera如何消费该矩阵未闭合。 | 左右原NPY；renderer构造pose、fixed_rot、add_camera_pose/set_matrix_world等实际调用与保存NPY代码；对应BlenderProc camera实现/version；若有生成scene里的camera.matrix_world则一并读出。 | 先写清每个坐标基底的手性及from/to。需要证明保存矩阵与实际渲染相机关系，并据代码推导CV变换；不能仅为det=+1任选翻轴。完整canonical→CV变换的rotation应proper；若反射属于资产基底，须在资产与相机链两边一致表达，并保留证据。D实现确定性适配；不能根据最低误差挑翻轴。 |
| G3 K/像素/depth | 当前K可由各轨迹resolution/fov和当前renderer推导，非所有样本直接保存；depth含1e10背景，语义待生成版本。 | 各样本metadata；renderer set_intrinsics及resolution/sensor_fit/pixel_aspect调用；depth输出设置及HDF5 keys/version。 | 确认FOV横/纵向、fx/fy、主点及fullpixel约定；K逐轨迹生成，左右是否共用必须有来源。depth明确Z或ray distance、单位和无效值；此处仅用于独立几何诊断，不从depth合成完整occupancy。scene_unit足以准备归一化训练，物理米未知不阻塞该训练。 |
| G4 canonical occupancy | 尚无已验GSO canonical voxel target。 | 首对象的canonical PLY及G1 receipt；既有远端TRELLIS voxelize.py路径/源码身份、open3d/utils3d等既有环境。 | 先验证PLY与G1映射和完整三角面，随后调用已固定官方voxelizer；产occupancy.npy/hash/源blob receipt。非空、64³索引合法、轴顺序与官方读取一致。GPU不参与这一步。原始mesh不是canonical时先完成G1；不使用可见depth、随机体素或左右occupancy平均。 |
| G5 target和image同crop | 官方代码和T接口已确认；真实pair cropbox还未生成。 | 双侧RGBA、明确的crop配置/实际PIL整数box及image_wh；配置身份。 | 同一个整数box用于image crop和UV仿射。保持原官方顺序：原图投影→UV clamp→crop→clamp；bool const_ssuv=True保留全图support。image先RGBA LANCZOS518再RGB*alpha。D生成dense target，T posterior mean编码；不二次crop。 |
| G6 split/身份/来源 | schema与hash绑定已实现，未真实执行全量。 | pairs.jsonl/summary/duplicates及source hashes；同对象其他版本asset hashes/别名信息（若发现）。 | 单pair输出只能是SMOKE数据；正式train/validation对象不重叠、同图内容无泄漏、源asset与metadata SHA绑定target。Panda一个对象不能强拆轨迹成对象级val。跨版本不因dataset_id不同免除对象重复检查。 |

## 2. R第一包需要返回什么

无需上传原始整套数据；回收小型JSON/text与精确集群产物路径即可：

1. `D_DATA_A1` job/node/exit、整合commit/tree、9项CPU测试完整结果；Panda audit summary与至少首条已验证record。
2. `stereo_data_geometry_inventory.py`的geometry_candidates.jsonl：先Panda首对，再大集至多3个不同对象；均注明scope。已有大集20个连续pair可能全属同一对象，不把它说成3对象抽样。
3. 保存renderer的完整源码hash与下列有界片段：OBJ导入/对象放置、normalize_scene、fixed_rot和左右pose构造、camera实际提交、K设置、depth渲染、NPY/HDF5写入。代码片段带路径/行号，不执行renderer（它可能修贴图并写原资产）。
4. 当前GSO代码Git HEAD/dirty/path；已知launcher内容/生成日志若存在。重点是可确认的生成关系，时间戳和当前commit本身均不证明历史生成版本。
5. 上述camera/import API的既有库源码与版本记录（仅命中调用函数即可）。不能从“当前安装Blender3.6.5”推出历史也相同。

`stereo_data_geometry_inventory.py`现仅返回候选数值与当前renderer hash；第三项代码片段是额外必要采集，不能误称脚本已闭合全部语义。

## 3. 收包后的D执行顺序

1. 先定位首个不一致：格式/路径错误直接本地修reader并push，新checkout重验；不变更target科学定义。
2. 依据源代码写出asset→canonical→renderer-camera→CV→fullpixel的显式矩阵乘法链及单位。缺一条则列出确切字段和持有文件；不把其他已闭合对象一并阻塞。
3. 用独立输入做确定性检查：asset点经已推导链投影与生成参考相符；可见表面depth比较须明确遮挡/背景，保留全部失败。检查用于发现工程错误，不按结果选择任意翻轴、拟合相机或重新缩放。容差来自浮点/保存精度或renderer栅格化分辨率，并在receipt记录，不能临时设研究通过率。
4. G1/G2/G3有明确证据后，生成该对象canonical mesh及mapping receipt，调用stereo_data_occupancy.py；随后逐pair生成geometry receipt/index，调用stereo_data_targets.py。
5. 将真实dense NPZ/index及hash交T/R运行encoder和训练；D验证crop/shape/target coverage，L收到同一canonical原点/frame/unit provenance。失败样本仍留审计分母。

若无法找到历史生成源码，但已保存的canonical mesh、实际相机及K足以直接确定变换链，可据这些独立文件闭合，不额外要求历史commit。
若两种来源都缺失且现存数据无法确定实际相机链，不能凭“图像看起来正确”给旧数据生成GT。D立即给控制器一份明确的最小补数据方案（独立新数据身份、保存实际canonical/相机/K、限定对象/帧数与资源），由控制器在既有授权范围内调度；是否改变科学数据定义交控制器判定。原数据保留，不悄悄覆盖/重渲染。

## 4. 当前唯一下一动作与责任

R恢复既有SSH后执行已协调D_DATA_A1，并返回上述第一包；D保持G1–G6解释及实现责任，收到证据后继续真实target生成。I负责集成，T负责posterior mean encoder适配，L只接有明确frame/unit的GT字段。没有新的worker或自动化。

反思：最不确定的是保存的反射矩阵与实际渲染camera之间是否存在库级分解；只看NPY和当前renderer的一行翻轴容易遗漏这一层。首对相对双目一致性不能证明完整canonical投影正确。
