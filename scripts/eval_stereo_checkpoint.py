#!/usr/bin/env python3
"""Checkpoint -> existing stereo inference -> existing pose evaluator, Slurm only."""
import argparse
import gc
import hashlib
import math
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from train_stereo_stage1 import load_config
from run_stereo_cupid import save_ply, write_json


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--checkpoint')
    p.add_argument('--checkpoint-sha256')
    p.add_argument('--official-baseline', action='store_true',
                   help='Keep official Stage1 weights; otherwise identical stereo evaluation')
    p.add_argument('--output', required=True)
    p.add_argument('--split', choices=['test', 'validation'], default='test')
    p.add_argument('--limit', type=int, default=3)
    p.add_argument('--selection-seed', type=int, help='Fixed hash-ranked sample selection, independent of training RNG')
    p.add_argument('--render-metrics', action='store_true', help='Original CUPID PSNR/SSIM/LPIPS and rendered mask IoU')
    args = p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or args.limit < 1:
        p.error('Slurm compute and positive sample limit required')
    if args.official_baseline and (args.checkpoint or args.checkpoint_sha256):
        p.error('Official baseline cannot also load a fine-tuned checkpoint')
    if not args.official_baseline and not (args.checkpoint and args.checkpoint_sha256):
        p.error('Fine-tuned evaluation requires checkpoint and SHA256')
    import numpy as np
    import torch
    from PIL import Image
    from cupid.datasets.stereo_gso import load_pair, confined_path, sha256_file
    from cupid.pipelines import StereoCupid3DPipeline
    from cupid.stereo_observability.metrics import evaluate_sample, summarize
    from cupid.utils.stereo_geometry import StereoCalibration

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    config = load_config(args.config)
    data = config['data']
    for key, expected in [('manifest', config['preflight_contract']['merged_manifest_sha256']),
                          ('target_index', config['preflight_contract']['target_index_sha256'])]:
        if sha256_file(data[key]) != expected:
            raise ValueError(key + ' SHA mismatch')
    if args.official_baseline:
        args.checkpoint = config['pretrained_init']['path'] + '.safetensors'
        args.checkpoint_sha256 = config['pretrained_init']['sha256']
        if sha256_file(config['pretrained_init']['path'] + '.json') != config['pretrained_init']['config_sha256']:
            raise ValueError('Official model config SHA mismatch')
    if sha256_file(args.checkpoint) != args.checkpoint_sha256:
        raise ValueError('Checkpoint SHA mismatch')
    rows = [json.loads(line) for line in Path(data['manifest']).read_text().splitlines()]
    key = (lambda r: r['pair_id']) if args.selection_seed is None else (
        lambda r: hashlib.sha256(f"{args.selection_seed}:{r['pair_id']}".encode()).hexdigest())
    selected = sorted((r for r in rows if r['split'] == args.split), key=key)[:args.limit]
    if not selected:
        raise ValueError('Selected evaluation split is empty')
    targets = {r['pair_id']: r for r in map(json.loads, Path(data['target_index']).read_text().splitlines())}
    write_json(out/'selected_samples.json', selected)
    root = Path(config['pretrained_init']['path']).parent.parent
    pipeline = StereoCupid3DPipeline.from_pretrained(str(root), dino_repo=config['dino']['repo'],
                                                    dino_checkpoint=config['dino']['checkpoint'])
    # Existing Stage2 lazy encoder must use the local official asset.
    pipeline.models['slat_flow_model'].pretrained_slat_enc = str(root/'ckpts/slat_enc_swin8_B_64l8_fp16')
    step = 0
    if not args.official_baseline:
        state = torch.load(args.checkpoint, map_location='cpu', weights_only=False, mmap=True)
        if state['format'] != 'STEREO_STAGE1_CHECKPOINT_V1':
            raise ValueError('Unexpected checkpoint format')
        weights = state['model']
        if not weights or not all(k.startswith('flow.') for k in weights):
            raise ValueError('Expected SharedStereoFlow state dictionary')
        pipeline.models['sparse_structure_flow_model'].load_state_dict(
            {k[len('flow.'):]: v for k, v in weights.items()}, strict=True)
        step = state['step']
        del weights, state
    gc.collect()
    pipeline.cuda()
    render_evaluator = None
    if args.render_metrics:
        from cupid.stereo_observability.checkpoint_render_metrics import CheckpointRenderMetrics, summarize_render_metrics
        render_evaluator = CheckpointRenderMetrics()
    report = dict(checkpoint=args.checkpoint, checkpoint_sha256=args.checkpoint_sha256,
                  initialization='OFFICIAL_WEIGHTS_STEREO_SAMPLER' if args.official_baseline else 'STEREO_FINETUNED',
                  checkpoint_step=step, commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
                  job_id=os.environ['SLURM_JOB_ID'], split=args.split, expected=len(selected), selection_seed=args.selection_seed,
                  scope='BOUNDED_HELD_OUT_EMPIRICAL_GSO_CANONICAL', length_unit='scene_unit',
                  sampler='existing_pipeline_default_25_steps', samples=[])
    records = []
    if render_evaluator is not None:
        report['render_protocol'] = dict(self_check=render_evaluator.check,
            functions='cupid.utils.loss_utils.psnr/ssim/lpips; VGG LPIPS',
            image='native 512px full frame, black alpha composite, RGB [0,1], no image alignment',
            left_dlt='original CUPID decoded left pose and predicted intrinsic',
            stereo_sim3='stereo-estimated scale/rotation/translation; known stereo calibration for right camera',
            claim='input-view reconstruction, not held-out novel-view synthesis or exact paper benchmark')
    for number, row in enumerate(selected):
        directory = out/f'sample_{number:03d}'
        directory.mkdir()
        item = dict(sample_id=row['pair_id'], prediction_status='FAILED')
        extra = dict(sample_id=row['pair_id'], status='FAILED')
        try:
            pack = load_pair(row, data['root'], hash_assets=True)
            target = targets[row['pair_id']]
            if pack['asset_sha256'] != target['source_asset_sha256']:
                raise ValueError('Source identity changed')
            provenance = target['provenance']
            shift = np.eye(4)
            shift[0,3] = provenance['saved_camera_x_shift_baseline_factor'] * row['metadata']['baseline']
            cameras = [np.asarray(provenance['camera_axis_to_cv']) @ shift @ pack['views'][s]['w2c_saved']
                       @ np.asarray(provenance['canonical_world_mirror']) for s in ('left','right')]
            images = [Image.fromarray(pack['views'][s]['rgba']) for s in ('left','right')]
            camera = dict(K_left=pack['views']['left']['K_fullpixel'].tolist(),
                          K_right=pack['views']['right']['K_fullpixel'].tolist(),
                          right_from_left=(cameras[1] @ np.linalg.inv(cameras[0])).tolist(),
                          image_size_left=list(images[0].size), image_size_right=list(images[1].size),
                          length_unit='scene_unit', source='target provenance '+provenance['geometry_receipt_sha256'],
                          camera_convention='opencv', distortion='none')
            write_json(directory/'camera.json', camera)
            for side, im in zip(('left','right'), images):
                im.save(directory/(side+'.png'))
            # Dense targets use the full image. Keep preprocessing identical to training.
            with torch.inference_mode():
                prediction = pipeline.run_stereo(*images, crop=False, stage2=True, seed=42,
                                                calibration=StereoCalibration.from_dict(camera))
            arrays = {k: prediction[k].cpu().numpy() for k in ('coords','support_coords','x_local','uv_left','uv_right')}
            arrays.update(pixels_left=prediction['pixels_left'], pixels_right=prediction['pixels_right'])
            np.savez_compressed(directory/'prediction.npz', **arrays)
            target_path = confined_path(data['target_root'], target['npz'])
            if sha256_file(target_path) != target['sha256']:
                raise ValueError('Target NPZ SHA mismatch')
            with np.load(target_path, allow_pickle=False) as dense:
                gt_occ = dense['ss'][0] > 0
            pred_occ = np.zeros_like(gt_occ)
            ijk = arrays['coords'][:,1:]
            pred_occ[tuple(ijk.T)] = True
            union = np.logical_or(gt_occ,pred_occ).sum()
            extra.update(status='PREDICTED', occupancy_iou=float(np.logical_and(gt_occ,pred_occ).sum()/union) if union else None,
                         gt_occupied=int(gt_occ.sum()), predicted_occupied=int(pred_occ.sum()),
                         stage2_status=prediction.get('stage2_status'), stage2_error=prediction.get('stage2_error'),
                         geometry_status=prediction['geometry']['status'])
            xyz = arrays['x_local']
            for i, side in enumerate(('left','right')):
                camxyz = xyz @ cameras[i][:3,:3].T + cameras[i][:3,3]
                projected = camxyz @ pack['views'][side]['K_fullpixel'].T
                valid = camxyz[:,2] > 1e-6
                pixel_gt = projected[valid,:2]/projected[valid,2:]
                errors = np.linalg.norm(arrays['pixels_'+side][valid]-pixel_gt,axis=1)
                extra[side+'_projection_mean_px'] = float(errors.mean()) if len(errors) else None
                extra[side+'_projection_count'] = int(valid.sum())
            geom = prediction['geometry']
            fit = geom.get('similarity')
            canonical = provenance['canonical_frame']
            item = dict(sample_id=row['pair_id'], prediction_status='OK' if fit is not None else 'FAILED',
                        failure_reason=geom['status'], prediction_uses_gt_alignment=False,
                        prediction={} if fit is None else dict(rotation=fit['rotation'].tolist(),
                          translation=fit['translation'].tolist(), scale=float(fit['scale']),
                          canonical_id=canonical, target_frame='left_camera_opencv', length_unit='scene_unit'),
                        gt=dict(rotation=cameras[0][:3,:3].tolist(), translation=cameras[0][:3,3].tolist(),
                          scale=1., canonical_id=canonical,target_frame='left_camera_opencv',length_unit='scene_unit',
                          verified=True, metric_unit_verified=False,
                          provenance='EMPIRICAL target mapping '+provenance['geometry_receipt_sha256']))
            if 'canonical_outputs' in prediction:
                mesh = prediction['canonical_outputs']['mesh'][0]
                save_ply(directory/'mesh_canonical.ply', mesh.vertices.cpu().numpy(), mesh.faces.cpu().numpy())
                extra['mesh_vertices'] = len(mesh.vertices)
                extra['mesh_faces'] = len(mesh.faces)
                if render_evaluator is not None:
                    extra['render_metrics'] = render_evaluator.evaluate(prediction, pack, camera, directory)
            if fit is not None:
                extra['triangulation_valid'] = geom['num_valid']
                extra['similarity_fit_rmse'] = float(fit['rmse'])
            del prediction
            torch.cuda.empty_cache()
        except Exception as error:
            extra['status'] = 'FAILED'
            item['prediction_status'] = 'FAILED'
            extra['error'] = str(error)
            item['failure_reason'] = str(error)
            (directory/'traceback.txt').write_text(traceback.format_exc())
            traceback.print_exc()
        records.append(item)
        extra['pose_metrics'] = evaluate_sample(item)
        report['samples'].append(extra)
        write_json(directory/'result.json',extra)
        write_json(out/'prediction_manifest.json',records)
        report['pose_summary'] = summarize([evaluate_sample(r) for r in records])
        write_json(out/'evaluation.json',report)
        print(json.dumps(extra), flush=True)
    report['status'] = 'COMPLETED' if all(s['status']=='PREDICTED' and s['stage2_status']=='OK' for s in report['samples']) else 'PARTIAL_OR_FAILED'
    if render_evaluator is not None and not all(
            s.get('render_metrics', {}).get(label, {}).get('status') == 'OK'
            for s in report['samples'] for label in render_evaluator.labels):
        report['status'] = 'PARTIAL_OR_FAILED'
    summary = {'expected_pairs': len(selected),
               'prediction_success_fraction': sum(s['status']=='PREDICTED' for s in report['samples'])/len(selected),
               'mesh_success_fraction': sum(s.get('stage2_status')=='OK' for s in report['samples'])/len(selected)}
    for name in ('occupancy_iou', 'left_projection_mean_px', 'right_projection_mean_px',
                 'triangulation_valid', 'similarity_fit_rmse'):
        values = [s[name] for s in report['samples'] if s.get(name) is not None and math.isfinite(s[name])]
        summary[name + '_coverage'] = len(values)/len(selected)
        if values:
            summary[name] = sum(values)/len(values)
    for name, metric in report['pose_summary']['metrics'].items():
        summary[name + '_coverage'] = metric['coverage']
        if metric['mean'] is not None:
            summary[name] = metric['mean']
    report['scalar_summary'] = summary
    if render_evaluator is not None:
        summary.update(summarize_render_metrics(report['samples']))
    write_json(out/'evaluation.json',report)
    return 0 if report['status']=='COMPLETED' else 2


if __name__ == '__main__':
    sys.exit(main())
