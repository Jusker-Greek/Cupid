#!/usr/bin/env python3
"""Synthetic known-K component only; no pretrained model or optimizer."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import cv2
import torch
from cupid.utils.known_k_pnp import known_k_pnp, pose_matrix, project, stationary_system


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and torch.cuda.is_available()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(108)
    device = 'cuda'
    xyz = (torch.rand(32, 3, dtype=torch.float64, device=device) - .5) * .8
    K = torch.tensor([[1.2, 0., .48], [0., 1.1, .52], [0., 0., 1.]], dtype=torch.float64, device=device)
    records = []
    passed = True
    for idx, values in enumerate(([.13, -.09, .04, .1, -.06, 2.7], [-.19, .07, .11, -.12, .08, 3.1])):
        xi = torch.tensor(values, dtype=torch.float64, device=device)
        ideal, _ = project(xi, xyz, K)
        uv = (ideal + torch.randn_like(ideal) * 1e-4).requires_grad_()
        T = known_k_pnp(uv, xyz, K)
        weights = T.new_tensor([[.2, -.1, .3, .5], [.1, .4, -.2, -.3], [.3, .2, -.1, .2], [0., 0., 0., 0.]])
        grad = torch.autograd.grad((T * weights).sum(), uv)[0]
        observations = []
        for point, axis in ((0, 0), (0, 1), (9, 0), (15, 1), (24, 0), (31, 1)):
            for eps in (1e-4, 3e-5, 1e-5):
                plus, minus = uv.detach().clone(), uv.detach().clone()
                plus[point, axis] += eps
                minus[point, axis] -= eps
                fd = (((known_k_pnp(plus, xyz, K) - known_k_pnp(minus, xyz, K)) * weights).sum() / (2 * eps)).item()
                analytic = grad[point, axis].item()
                error = abs(fd - analytic) / max(abs(fd), abs(analytic), 1e-8)
                observations.append(dict(point=point, axis=axis, epsilon=eps, fd=fd, analytic=analytic, relative_error=error))
        changed_K = K.clone()
        changed_K[0, 0] *= 1.1
        changed = known_k_pnp(uv.detach(), xyz, changed_K)
        camera = xyz @ T[:3, :3].T + T[:3, 3]
        pixels = camera @ K.T
        pred = pixels[:, :2] / pixels[:, 2:]
        solved_r, _ = cv2.Rodrigues(T[:3, :3].detach().cpu().numpy())
        solved_xi = torch.cat((T.new_tensor(solved_r.ravel()), T[:3, 3].detach())).requires_grad_()
        F, H = stationary_system(solved_xi, uv.detach(), xyz, K)
        eig = torch.linalg.eigvalsh(H.detach())
        local_pass = bool(torch.isfinite(grad).all() and grad.norm() > 0
                          and max(x['relative_error'] for x in observations) < .01
                          and (T - changed).abs().max() > 1e-4
                          and torch.det(T[:3, :3]) > .999999
                          and (pred - uv).square().mean().sqrt() < 5e-4)
        passed &= local_pass
        records.append(dict(pose=idx, pass_gate=local_pass,
            uv_grad_norm=grad.norm().item(), pose_max_error=(T-pose_matrix(xi)).abs().max().item(),
            reprojection_rmse=(pred-uv).square().mean().sqrt().item(),
            determinant=torch.det(T[:3, :3]).item(),
            orthogonality_error=(T[:3,:3].T@T[:3,:3]-torch.eye(3,device=device)).abs().max().item(),
            minimum_depth=camera[:,2].min().item(),
            stationarity_inf_norm=F.detach().abs().max().item(),
            full_hessian_eigenvalues=eig.tolist(),
            full_hessian_condition=(eig.max()/eig.min()).item(),
            xyz_centered_singular_values=torch.linalg.svdvals(xyz-xyz.mean(0)).tolist(),
            fixed_K_change_pose_max_difference=(T-changed).abs().max().item(), fd=observations))
    rejected = {}
    for name, X, k in [('planar', xyz * xyz.new_tensor([1, 1, 0]), K),
                        ('learnable_K', xyz, K.clone().requires_grad_())]:
        try:
            known_k_pnp(uv, X, k)
            rejected[name] = False
        except ValueError as error:
            rejected[name] = str(error)
    passed &= all(bool(x) for x in rejected.values())
    result = dict(scope='SYNTHETIC_COMPONENT_ONLY_NOT_MAIN_S05', passed=passed,
                  job=os.environ['SLURM_JOB_ID'], head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
                  torch=torch.__version__, gpu=torch.cuda.get_device_name(),
                  criteria='two poses; six UV coordinates x three eps; every relative error <1%; K sensitivity; invalid rejection',
                  poses=records, invalid_rejections=rejected)
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2), flush=True)
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
