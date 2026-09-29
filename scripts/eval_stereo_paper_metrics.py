#!/usr/bin/env python3
"""Slurm input-view metrics: original mono, official stereo, step809 stereo."""
import argparse
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from train_stereo_stage1 import load_config


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def summarize(records):
    import numpy as np
    groups = {}
    for mode in sorted({r['mode'] for r in records}):
        group = [r for r in records if r['mode'] == mode]
        stats = dict(expected=len(group), completed=sum(r['status'] == 'OK' for r in group))
        for section in ('image', 'aligned_geometry'):
            names = sorted({k for r in group for k in r.get(section, {})})
            stats[section] = {}
            for name in names:
                values = [r[section][name] for r in group if isinstance(r.get(section, {}).get(name), (float, int))]
                if values:
                    stats[section][name] = dict(mean=float(np.mean(values)), median=float(np.median(values)), count=len(values))
        groups[mode] = stats
    return groups


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--config', default='configs/stereo/train_stage1_full_gso_engineering_candidate.json')
    p.add_argument('--checkpoint', default='/public/home/ricky/RESULTS/STEREO_CUPID_2DE057A_FULL_A8/output/step_00000809.pt')
    p.add_argument('--checkpoint-sha256', default='8d477ffe6cad8582d5474bc12c5c9a6493d9a775933dfcf22b43607fe54d8c5c')
    p.add_argument('--output', required=True)
    p.add_argument('--limit', type=int, default=3)
    p.add_argument('--asset-root', default='/public/home/ricky/DATASET/Gazebo')
    args = p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or args.limit < 1:
        p.error('Slurm compute job and positive sample count required')
    import numpy as np
    import torch
    import trimesh
    from PIL import Image, ImageDraw
    from cupid.datasets.stereo_gso import load_pair, sha256_file
    from cupid.pipelines import StereoCupid3DPipeline
    from cupid.renderers import MeshRenderer
    from cupid.representations.mesh import MeshExtractResult
    from cupid.stereo_observability.paper_metrics import evaluate_view, self_check
    from cupid.utils.stereo_geometry import StereoCalibration

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    config = load_config(args.config)
    data = config['data']
    for path, expected in ((data['manifest'], config['preflight_contract']['merged_manifest_sha256']),
                           (data['target_index'], config['preflight_contract']['target_index_sha256']),
                           (config['pretrained_init']['path'] + '.safetensors', config['pretrained_init']['sha256']),
                           (args.checkpoint, args.checkpoint_sha256)):
        if sha256_file(path) != expected:
            raise ValueError('Asset SHA mismatch: ' + path)
    selected = sorted((json.loads(l) for l in Path(data['manifest']).read_text().splitlines()
                       if json.loads(l)['split'] == 'test'), key=lambda r: r['pair_id'])[:args.limit]
    if len(selected) != args.limit:
        raise ValueError('Insufficient test samples')
    targets = {r['pair_id']: r for r in map(json.loads, Path(data['target_index']).read_text().splitlines())}
    write(out/'selected_samples.json', selected)
    report = dict(job_id=os.environ['SLURM_JOB_ID'], commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  expected_pairs=len(selected), checkpoint=args.checkpoint, checkpoint_sha256=args.checkpoint_sha256,
                  official_weight_sha256=config['pretrained_init']['sha256'], samples=[], data_checks=[],
                  protocol=dict(scope='SAME_METRIC_FAMILIES_NOT_EXACT_PUBLISHED_BENCHMARK',
                    image='original 512px left image, black alpha composite, full frame, no GT alignment',
                    renderer='original CUPID colored MeshRenderer, ssaa=1, near=.01, far=100',
                    lpips='original CUPID loss_utils.lpips VGG',
                    mask='mesh alpha > .5 vs source PNG alpha > .5',
                    geometry='all visible unprojected z-depth points; normalized intrinsics; pixel centres at x+.5,y+.5',
                    alignment='MoGe scale + xyz shift, inverse GT distance weights, 512 fixed overlap pixels; NO rotation',
                    cd='mean of two directional mean Euclidean NN distances, scene_unit; also squared variant',
                    fscore='harmonic mean precision/recall at .01 and .05 scene_unit',
                    aggregation='equal sample weight; mean and median across samples',
                    unresolved_paper_details=['exact sample/camera list', 'render representation and background', 'CD display multiplier and threshold normalization']))
    renderer = MeshRenderer(dict(resolution=512, near=.01, far=100., ssaa=1))
    report['self_check'] = self_check(renderer)
    write(out/'evaluation.json', report)
    print('METRIC_SELF_CHECK_PASS', flush=True)

    root = Path(config['pretrained_init']['path']).parent.parent
    pipe = StereoCupid3DPipeline.from_pretrained(str(root), dino_repo=config['dino']['repo'], dino_checkpoint=config['dino']['checkpoint'])
    pipe.models['slat_flow_model'].pretrained_slat_enc = str(root/'ckpts/slat_enc_swin8_B_64l8_fp16')
    pipe.cuda()
    report['samplers'] = dict(stage1=pipe.sparse_structure_sampler_params, stage2=pipe.slat_sampler_params)
    packs = []
    for row in selected:
        pack = load_pair(row, data['root'], hash_assets=True)
        target = targets[row['pair_id']]
        if pack['asset_sha256'] != target['source_asset_sha256']:
            raise ValueError('Source identity mismatch')
        provenance = target['provenance']
        shift = np.eye(4)
        shift[0, 3] = provenance['saved_camera_x_shift_baseline_factor'] * row['metadata']['baseline']
        cameras = [np.asarray(provenance['camera_axis_to_cv']) @ shift @ pack['views'][s]['w2c_saved']
                   @ np.asarray(provenance['canonical_world_mirror']) for s in ('left', 'right')]
        images = [Image.fromarray(pack['views'][s]['rgba']) for s in ('left', 'right')]
        w, h = images[0].size
        if (w, h) != (512, 512):
            raise ValueError('This protocol explicitly requires native 512 square images')
        k = pack['views']['left']['K_fullpixel'].copy()
        k[:2] /= 512
        calibration = StereoCalibration.from_dict(dict(K_left=pack['views']['left']['K_fullpixel'].tolist(),
            K_right=pack['views']['right']['K_fullpixel'].tolist(), right_from_left=(cameras[1] @ np.linalg.inv(cameras[0])).tolist(),
            image_size_left=[w,h], image_size_right=list(images[1].size), length_unit='scene_unit',
            source=provenance['geometry_receipt_sha256'], camera_convention='opencv', distortion='none'))
        # Independently check stored depth against source-mesh rasterization.
        mesh_path = Path(args.asset_root)/row['object_id']/'meshes/model.obj'
        if sha256_file(mesh_path) != provenance['asset_sha256']:
            raise ValueError('Source mesh identity mismatch')
        tm = trimesh.load(str(mesh_path), force='mesh', process=False, skip_materials=True)
        matrix = np.asarray(provenance['raw_obj_to_canonical'])
        verts = np.asarray(tm.vertices) @ matrix[:3,:3].T + matrix[:3,3]
        gt_mesh = MeshExtractResult(torch.tensor(verts, device='cuda', dtype=torch.float32), torch.tensor(np.asarray(tm.faces), device='cuda'))
        with torch.no_grad():
            gt_raster = renderer.render(gt_mesh, torch.tensor(cameras[0], device='cuda', dtype=torch.float32),
                                       torch.tensor(k, device='cuda', dtype=torch.float32), return_types=['mask','depth'])
        depth = pack['views']['left']['depth']
        valid = pack['views']['left']['depth_valid']
        raster_mask = gt_raster['mask'].cpu().numpy() > .5
        raster_z = gt_raster['depth'].cpu().numpy()
        overlap = raster_mask & valid
        relative = np.abs(raster_z[overlap] - depth[overlap]) / depth[overlap]
        check = dict(sample_id=row['pair_id'], mask_iou=float(np.sum(raster_mask & pack['views']['left']['mask']) /
                     np.sum(raster_mask | pack['views']['left']['mask'])), source_mesh_sha256=provenance['asset_sha256'],
                     z_depth_relative_median=float(np.median(relative)), z_depth_relative_p95=float(np.quantile(relative, .95)),
                     historical_renderer_exact_revision_verified=False)
        check['empirical_z_depth_check'] = bool(check['mask_iou'] > .9 and check['z_depth_relative_median'] < .02)
        report['data_checks'].append(check)
        packs.append((row, pack, images, k, calibration))
        del gt_mesh, gt_raster, tm
    write(out/'evaluation.json', report)

    panels = {}
    modes = ('official_mono_crop', 'official_mono_full', 'official_stereo', 'finetuned_stereo')
    for mode in modes:
        if mode == 'finetuned_stereo':
            state = torch.load(args.checkpoint, map_location='cpu', weights_only=False, mmap=True)
            if state['format'] != 'STEREO_STAGE1_CHECKPOINT_V1' or not all(k.startswith('flow.') for k in state['model']):
                raise ValueError('Unexpected checkpoint format')
            pipe.models['sparse_structure_flow_model'].load_state_dict({k[5:]: v for k,v in state['model'].items()}, strict=True)
            del state
            gc.collect()
        for index, (row, pack, images, k, calibration) in enumerate(packs):
            directory = out/mode/f'sample_{index:03d}'
            directory.mkdir(parents=True)
            try:
                with torch.inference_mode():
                    if 'mono' in mode:
                        prediction = pipe.run(images[0], seed=42, formats=['mesh'], preprocess_image=mode.endswith('crop'))
                        mesh = prediction['mesh'][0]
                        render_poses = [(mode, prediction['pose'][0])]
                    else:
                        prediction = pipe.run_stereo(*images, crop=False, seed=42, stage2=True, calibration=calibration)
                        if prediction.get('stage2_status') != 'OK':
                            raise ValueError(str(prediction.get('stage2_error', prediction.get('stage2_status'))))
                        mesh = prediction['canonical_outputs']['mesh'][0]
                        render_poses = [(mode + '_left_dlt', prediction['pose_left'])]
                        fit = prediction['geometry'].get('similarity')
                        if fit is None:
                            raise ValueError('Stereo similarity missing: ' + prediction['geometry']['status'])
                        sim = torch.eye(4, device='cuda')
                        sim[:3,:3] = torch.tensor(fit['rotation'], device='cuda') * float(fit['scale'])
                        sim[:3,3] = torch.tensor(fit['translation'], device='cuda')
                        render_poses.append((mode + '_stereo_sim3', dict(extrinsic=sim, intrinsic=torch.tensor(k, device='cuda', dtype=torch.float32))))
                    if mesh.vertex_attrs is None or mesh.vertex_attrs.shape[1] < 3:
                        raise ValueError('Original mesh decoder did not provide RGB attributes')
                    np.savez_compressed(directory/'mesh.npz', vertices=mesh.vertices.cpu().numpy(), faces=mesh.faces.cpu().numpy(),
                                        attrs=mesh.vertex_attrs.cpu().numpy())
                    for label, pose in render_poses:
                        rendered = renderer.render(mesh, pose['extrinsic'], pose['intrinsic'], return_types=['mask','depth','color'])
                        view = pack['views']['left']
                        result = evaluate_view(rendered, pose['intrinsic'].cpu().numpy(), view['rgba'], view['depth'], view['depth_valid'], k)
                        record = dict(mode=label, sample_id=row['pair_id'], status='OK', image=result['image'], geometry=result['geometry'])
                        if result['geometry']['status'] == 'OK':
                            record['aligned_geometry'] = result['geometry']['aligned']
                        record['gt_depth_empirically_checked'] = report['data_checks'][index]['empirical_z_depth_check']
                        report['samples'].append(record)
                        write(directory/(label+'_metrics.json'), record)
                        write(directory/(label+'_pose.json'), {key: value.cpu().tolist() for key,value in pose.items()})
                        np.savez_compressed(directory/(label+'_render.npz'), **{key:value.cpu().numpy() for key,value in rendered.items()})
                        array = (rendered['color'].clamp(0,1).cpu().permute(1,2,0).numpy()*255).round().astype(np.uint8)
                        rgb = Image.fromarray(array)
                        rgb.save(directory/(label+'_rgb.png'))
                        panels[(index,label)] = rgb
                        Image.fromarray((rendered['mask'].clamp(0,1).cpu().numpy()*255).round().astype(np.uint8)).save(directory/(label+'_mask.png'))
                        print(json.dumps(record, allow_nan=False), flush=True)
                del prediction, mesh, rendered
                torch.cuda.empty_cache()
            except Exception as error:
                traceback.print_exc()
                (directory/'traceback.txt').write_text(traceback.format_exc())
                report['samples'].append(dict(mode=mode, sample_id=row['pair_id'], status='FAILED', error=str(error)))
            report['summary'] = summarize(report['samples'])
            write(out/'evaluation.json', report)
    labels = ['official_mono_crop', 'official_mono_full', 'official_stereo_left_dlt', 'official_stereo_stereo_sim3',
              'finetuned_stereo_left_dlt', 'finetuned_stereo_stereo_sim3']
    sheet = Image.new('RGB', (256*7, 286*len(packs)), 'white')
    draw = ImageDraw.Draw(sheet)
    for index, (_, pack, _, _, _) in enumerate(packs):
        rgba = pack['views']['left']['rgba'].astype(np.float32)
        rgb = Image.fromarray((rgba[...,:3] * rgba[...,3:4]/255).astype(np.uint8))
        for column, label in enumerate(['GT']+labels):
            panel = rgb if label == 'GT' else panels.get((index,label))
            if panel is not None:
                sheet.paste(panel.resize((256,256)), (column*256,index*286+30))
            draw.text((column*256+3,index*286+5), label, fill='black')
    sheet.save(out/'comparison.png')
    report['status'] = 'COMPLETED' if len(report['samples']) == len(selected)*6 and all(r['status']=='OK' for r in report['samples']) else 'PARTIAL_OR_FAILED'
    write(out/'evaluation.json', report)
    return 0 if report['status']=='COMPLETED' else 2


if __name__ == '__main__':
    sys.exit(main())
