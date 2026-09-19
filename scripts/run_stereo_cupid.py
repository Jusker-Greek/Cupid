#!/usr/bin/env python3
"""Run one Stereo-CUPID pair; execute on a Slurm compute allocation."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def save_ply(path, vertices, faces):
    """Write decoder triangles directly; no remeshing, baking, or rendering."""
    vertices, faces = np.asarray(vertices), np.asarray(faces)
    if not np.isfinite(vertices).all():
        raise ValueError("Cannot export nonfinite vertices")
    with path.open('w') as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {len(vertices)}\nproperty float x\nproperty float y\nproperty float z\nelement face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n")
        np.savetxt(f, vertices, fmt='%.9g')
        np.savetxt(f, np.c_[np.full(len(faces), 3), faces], fmt='%d')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pair-dir', type=Path, required=True, help='One trajectory directory containing left/ and right/')
    p.add_argument('--frame', default='000')
    p.add_argument('--model-path', type=Path, required=True, help='Existing local Cupid directory with pipeline.json')
    p.add_argument('--dino-repo', type=Path, required=True, help='Existing local dinov2 repository with hubconf.py')
    p.add_argument('--dino-checkpoint', type=Path, required=True, help='Existing DINO state dict matching pipeline image_cond_model')
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--camera-json', type=Path, help='Explicit external CV pinhole camera contract; optional for generation')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--steps', type=int, help='Omit to use checkpoint sampler setting')
    p.add_argument('--full-mesh', action='store_true', help='Also run original left Stage2 and export canonical/placed triangle meshes')
    p.add_argument('--no-crop', action='store_true')
    p.add_argument('--uv-noise', choices=('independent', 'shared'), default='independent')
    p.add_argument('--max-reprojection-px', type=float, default=2.0)
    p.add_argument('--min-ray-angle-deg', type=float, default=0.1)
    args = p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        p.error('Run in a Slurm compute allocation, not a local machine or login node')
    if not args.frame.isdigit():
        p.error('--frame must be a numeric filename stem')
    frame = args.frame.zfill(3)
    for file in (args.model_path/'pipeline.json', args.dino_repo/'hubconf.py', args.dino_checkpoint,
                 args.pair_dir/'left'/f'{frame}.png', args.pair_dir/'right'/f'{frame}.png'):
        if not file.is_file():
            p.error(f'Required local file not found: {file}')
    # Offline prevents HF fallbacks in existing model loaders from downloading.
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ.setdefault('SPCONV_ALGO', 'native')
    from cupid.utils.stereo_geometry import StereoCalibration
    calibration_data = json.loads(args.camera_json.read_text()) if args.camera_json else None
    calibration = StereoCalibration.from_dict(calibration_data) if calibration_data else None
    args.output_dir.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    receipt = {'schema': 'stereo_cupid/v1', 'status': 'STARTED', 'run_class': 'PRETRAINED_STEREO_PILOT',
               'scientific_claim': 'UNTESTED', 'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
               'slurm_job_id': os.environ['SLURM_JOB_ID'], 'pair_dir': str(args.pair_dir.resolve()),
               'frame': frame, 'model_path': str(args.model_path.resolve()),
               'dino_repo': str(args.dino_repo.resolve()), 'dino_checkpoint': str(args.dino_checkpoint.resolve()),
               'camera_contract': calibration_data, 'seed': args.seed, 'full_mesh': args.full_mesh}
    write_json(args.output_dir/'result.json', receipt)
    started = time.monotonic()
    try:
        from cupid.pipelines import StereoCupid3DPipeline
        pipeline = StereoCupid3DPipeline.from_pretrained(str(args.model_path),
            dino_repo=args.dino_repo, dino_checkpoint=args.dino_checkpoint)
        pipeline.cuda()
        with Image.open(args.pair_dir/'left'/f'{frame}.png') as image:
            left = image.copy()
        with Image.open(args.pair_dir/'right'/f'{frame}.png') as image:
            right = image.copy()
        # GSO RGBA provides alpha; do not silently invoke rembg/downloads on RGB.
        if any(im.mode != 'RGBA' or im.getchannel('A').getextrema() == (255, 255) for im in (left, right)):
            raise ValueError('This GSO runner requires RGBA foreground alpha for both images')
        output = pipeline.run_stereo(left, right, seed=args.seed, crop=not args.no_crop,
            stage2=args.full_mesh, calibration=calibration, uv_noise=args.uv_noise,
            sampler_params={'steps': args.steps} if args.steps is not None else None,
            max_reprojection_px=args.max_reprojection_px, min_ray_angle_deg=args.min_ray_angle_deg)
        arrays = {key: output[key].cpu().numpy() for key in ('coords', 'support_coords', 'x_local', 'uv_left', 'uv_right')}
        arrays.update(pixels_left=output['pixels_left'], pixels_right=output['pixels_right'])
        geometry = output['geometry']
        receipt.update(sampling=output['sampling'], preprocessing=output['preprocessing'],
                       geometry_status=geometry['status'], stage2_status=output.get('stage2_status', 'NOT_REQUESTED'))
        if 'valid' in geometry:
            for key in ('valid', 'points_left_camera', 'disparity_px', 'reprojection_px', 'ray_angle_deg'):
                arrays[key] = geometry[key]
            for key, value in geometry['masks'].items():
                arrays['mask_' + key] = value
            receipt.update(num_input=geometry['num_input'], num_valid=geometry['num_valid'],
                filter_counts={key: int(value.sum()) for key, value in geometry['masks'].items()},
                geometry_thresholds=geometry['thresholds'], length_unit=geometry['length_unit'])
        fit = geometry.get('similarity')
        if fit is not None:
            arrays.update(scale=np.array(fit['scale']), rotation=fit['rotation'], translation=fit['translation'], fit_residuals=fit['residuals'])
            receipt['similarity'] = {'scale': fit['scale'], 'rotation': fit['rotation'].tolist(),
                                    'translation': fit['translation'].tolist(), 'rmse': fit['rmse'],
                                    'source_frame': 'cupid_canonical', 'target_frame': 'left_camera_opencv'}
        if 'pose_left' in output:
            receipt['pose_left_predicted'] = {key: value.cpu().numpy().tolist() for key, value in output['pose_left'].items()}
        if 'stage2_error' in output:
            receipt['stage2_error'] = output['stage2_error']
        # Persist Stage1 before any optional mesh export can fail.
        np.savez_compressed(args.output_dir/'stage1_and_geometry.npz', **arrays)
        if 'canonical_outputs' in output:
            mesh = output['canonical_outputs']['mesh'][0]
            vertices, faces = mesh.vertices.cpu().numpy(), mesh.faces.cpu().numpy()
            save_ply(args.output_dir/'mesh_canonical.ply', vertices, faces)
            receipt['canonical_mesh_transform_applied'] = False
            if fit is not None:
                placed = fit['scale'] * vertices @ fit['rotation'].T + fit['translation']
                name = f"mesh_left_camera_{geometry['length_unit']}.ply"
                save_ply(args.output_dir/name, placed, faces)
                receipt['placed_mesh'] = {'file': name, 'transform_applied_once': True,
                                          'source_frame': 'cupid_canonical', 'target_frame': 'left_camera_opencv'}
        partial = args.full_mesh and receipt['stage2_status'] != 'OK'
        receipt.update(status='PARTIAL' if partial else 'COMPLETED', elapsed_seconds=time.monotonic() - started)
        write_json(args.output_dir/'result.json', receipt)
        print(json.dumps({'status': receipt['status'], 'geometry_status': receipt['geometry_status'],
                          'output_dir': str(args.output_dir), 'scientific_claim': 'UNTESTED'}), flush=True)
        return 2 if partial else 0
    except Exception as error:
        receipt.update(status='FAILED', error_type=type(error).__name__, error=str(error), elapsed_seconds=time.monotonic() - started)
        write_json(args.output_dir/'result.json', receipt)
        raise


if __name__ == '__main__':
    sys.exit(main())
