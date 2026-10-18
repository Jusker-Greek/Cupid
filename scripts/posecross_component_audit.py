#!/usr/bin/env python3
"""Slurm-only diagnostic of existing CUPID components; never a training smoke.

Synthetic primitives/correspondences isolate renderer and pose-solver contracts.
No pretrained decoder, flow, optimizer or GSO model result is exercised.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('SLURMD_NODENAME'):
        parser.error('Slurm compute node required')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema='SC_POSECROSS_COMPONENT_AUDIT_V1', status='RUNNING',
                   scope='SYNTHETIC_NATIVE_COMPONENTS_ONLY_NOT_MODEL_SMOKE',
                   scientific_evidence=False, experiment_stage_pass=False,
                   job=os.environ['SLURM_JOB_ID'], node=os.environ['SLURMD_NODENAME'],
                   commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip())
    try:
        import torch
        from cupid.representations.gaussian import Gaussian
        from cupid.renderers.gaussian_render import GaussianRenderer
        from cupid.utils.pose_utils import calibrate_camera_dlt
        if not torch.cuda.is_available():
            raise RuntimeError('GPU required')
        torch.manual_seed(1842)
        device = 'cuda'
        receipt['runtime'] = dict(torch=torch.__version__, cuda=torch.version.cuda,
                                  device=torch.cuda.get_device_name())
        renderer = GaussianRenderer(dict(resolution=64, near=.1, far=10., ssaa=1, bg_color=[0, 0, 0]))
        xyz = torch.tensor([[-.21,-.11,.03],[.13,.17,.11],[.02,-.16,-.09]], device=device, requires_grad=True)
        gs = Gaussian([-.5,-.5,-.5,1.,1.,1.], sh_degree=0, device=device)
        gs.from_xyz(xyz)
        gs.from_scaling(torch.full((3,3), .06, device=device))
        gs.from_rotation(torch.tensor([[1.,0,0,0]]*3, device=device))
        gs.from_opacity(torch.full((3,1), .8, device=device))
        gs.from_features(torch.tensor([[[1.],[0.],[.3]],[[0.],[1.],[.1]],[[.2],[.3],[1.]]], device=device))
        K = torch.tensor([[.9,0,.5],[0,.9,.5],[0,0,1.]], device=device)
        pose = torch.eye(4, device=device)
        pose[2,3] = 2.
        pose.requires_grad_(True)
        weights = torch.linspace(.2, 1.3, 64, device=device)[None,None,:]
        def scalar(camera):
            return (renderer.render(gs, camera, K)['color'] * weights).mean()
        value = scalar(pose)
        gx, gp = torch.autograd.grad(value, (xyz, pose), allow_unused=True)
        receipt['native_renderer'] = dict(scalar=float(value.detach()),
            primitive_gradient_norm=None if gx is None else float(gx.norm()),
            primitive_gradient_finite=gx is not None and bool(torch.isfinite(gx).all()),
            camera_gradient_present=gp is not None,
            camera_gradient_norm=None if gp is None else float(gp.norm()),
            camera_gradient_finite=gp is not None and bool(torch.isfinite(gp).all()),
            translation_x_autograd=None if gp is None else float(gp[0,3]), finite_difference=[])
        with torch.no_grad():
            for eps in (1e-2, 3e-3, 1e-3):
                plus, minus = pose.detach().clone(), pose.detach().clone()
                plus[0,3] += eps
                minus[0,3] -= eps
                fd = float((scalar(plus)-scalar(minus))/(2*eps))
                receipt['native_renderer']['finite_difference'].append(dict(eps=eps, translation_x=fd))
        points = torch.rand(1,32,3,device=device) * .7 - .35
        cam = points + torch.tensor([.1,-.04,2.],device=device)
        homogeneous = cam @ K.T
        uv = (homogeneous[...,:2] / homogeneous[...,2:]).detach()
        uv = (uv + .0005 * torch.randn_like(uv)).requires_grad_(True)
        k1, t1, residual = calibrate_camera_dlt(points, uv, initial_camera_matrix=K[None])
        k2, t2, _ = calibrate_camera_dlt(points, uv, initial_camera_matrix=(K * 1.1)[None])
        guv, = torch.autograd.grad(t1.square().sum(), (uv,), allow_unused=True)
        receipt['native_dlt'] = dict(reprojection_error=float(residual.mean()),
            changed_K_output_K_max_delta=float((k1-k2).abs().max()),
            changed_K_output_T_max_delta=float((t1-t2).abs().max()),
            ignores_initial_K=bool(torch.equal(k1,k2) and torch.equal(t1,t2)),
            uv_gradient_present=guv is not None,
            uv_gradient_finite=guv is not None and bool(torch.isfinite(guv).all()),
            uv_gradient_norm=None if guv is None else float(guv.norm()))
        if gx is None or not torch.isfinite(gx).all() or gx.norm() <= 0:
            raise RuntimeError('Native primitive gradient missing/nonfinite/zero: fixture invalid')
        receipt['status'] = 'DIAGNOSTIC_COMPLETED'
        receipt['model_gate'] = 'NOT_TESTED'
        receipt['native_camera_contract'] = 'PASS' if gp is not None and torch.isfinite(gp).all() and gp.norm() > 0 else 'FAIL'
        receipt['known_K_contract'] = 'FAIL' if receipt['native_dlt']['ignores_initial_K'] else 'REQUIRES_SEPARATE_ACCURACY_TEST'
    except Exception as exc:
        receipt.update(status='ERROR', error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        (output/'receipt.json').write_text(json.dumps(receipt, indent=2, allow_nan=False)+'\n')
        print(json.dumps(receipt, indent=2, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
