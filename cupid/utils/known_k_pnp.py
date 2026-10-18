"""Opt-in single-sample implicit PnP component; not wired into CUPID training.

Fixed XYZ support and calibrated K; only UV receives gradients. Chart is
Rodrigues rotation plus direct translation (not an SE(3) twist translation).
Forward minimizes the same unweighted squared reprojection objective used in
backward. Full Hessian implicit differentiation, no RANSAC or GN approximation.
Inspired by the implicit-function formulation of Chen et al., CVPR 2020 BPnP;
implementation below is independent and deliberately rejects invalid samples.
"""
import cv2
import numpy as np
import torch
from torch.autograd.function import once_differentiable


def pose_matrix(xi):
    x, y, z = xi[:3].unbind()
    o = x * 0
    skew = torch.stack((o, -z, y, z, o, -x, -y, x, o)).reshape(3, 3)
    rotation = torch.matrix_exp(skew)
    return torch.cat((torch.cat((rotation, xi[3:, None]), dim=1),
                      xi.new_tensor([[0., 0., 0., 1.]])), dim=0)


def project(xi, xyz, K):
    T = pose_matrix(xi)
    camera = xyz @ T[:3, :3].T + T[:3, 3]
    pixels = camera @ K.T
    return pixels[:, :2] / pixels[:, 2:], camera[:, 2]


def objective(xi, uv, xyz, K):
    pred, _ = project(xi, xyz, K)
    return 0.5 * (pred - uv).square().sum()


def stationary_system(xi, uv, xyz, K):
    """Full 6x6 Hessian and stationarity vector, with autograd graph."""
    energy = objective(xi, uv, xyz, K)
    F = torch.autograd.grad(energy, xi, create_graph=True)[0]
    H = torch.stack([torch.autograd.grad(F[i], xi, retain_graph=True,
                                       create_graph=True)[0] for i in range(6)])
    return F, H


class _ImplicitPnP(torch.autograd.Function):
    @staticmethod
    def forward(ctx, uv, xyz, K):
        arrays = [np.ascontiguousarray(t.detach().cpu().double().numpy())
                  for t in (xyz, uv, K)]
        points, observations, camera = arrays
        ok, r, t = cv2.solvePnP(points, observations, camera, None,
                              flags=cv2.SOLVEPNP_EPNP)
        if not ok:
            raise RuntimeError('PnP EPNP initialization failed')
        ok, r, t = cv2.solvePnP(points, observations, camera, None, r, t, True,
                              flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            raise RuntimeError('PnP reprojection refinement failed')
        r, t = cv2.solvePnPRefineLM(points, observations, camera, None, r, t,
            criteria=(cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 100, 1e-12))
        xi = torch.as_tensor(np.concatenate((r.ravel(), t.ravel())),
                             dtype=torch.float64, device=uv.device)
        with torch.enable_grad():
            q = xi.detach().requires_grad_(True)
            F, H = stationary_system(q, uv.detach(), xyz, K)
            eig = torch.linalg.eigvalsh(H.detach())
            _, depth = project(q, xyz, K)
            if not (torch.isfinite(xi).all() and torch.isfinite(H).all()
                    and depth.min() > 1e-6 and F.detach().abs().max() < 1e-7
                    and eig.min() > 1e-10 and eig.max() / eig.min() < 1e10):
                raise RuntimeError('PnP invalid stationary point, depth, or Hessian')
        ctx.save_for_backward(xi, uv, xyz, K)
        return xi

    @staticmethod
    @once_differentiable
    def backward(ctx, grad_xi):
        xi, uv, xyz, K = ctx.saved_tensors
        with torch.enable_grad():
            q = xi.detach().requires_grad_(True)
            u = uv.detach().requires_grad_(True)
            F, H = stationary_system(q, u, xyz, K)
            # H^T lambda = dL/dxi; dL/du = -(dF/du)^T lambda.
            adjoint = torch.linalg.solve(H.detach().T, grad_xi)
            grad_uv = -torch.autograd.grad(F, u, grad_outputs=adjoint)[0]
        if not torch.isfinite(grad_uv).all():
            raise RuntimeError('PnP produced nonfinite UV gradient')
        return grad_uv, None, None


def known_k_pnp(uv, xyz, K):
    """Return differentiable 4x4 world-to-camera pose, float64 internal math.

    UV and K must use the same units (e.g. normalized crop coordinates).
    Proposed component thresholds above are not a frozen full-data contract.
    Second-order differentiation is explicitly unsupported. XYZ/K are fixed.
    """
    if xyz.requires_grad or K.requires_grad:
        raise ValueError('XYZ support and calibrated K must be fixed')
    if uv.ndim != 2 or uv.shape[1] != 2 or xyz.shape != (len(uv), 3) or K.shape != (3, 3) or len(uv) < 6:
        raise ValueError('Expected >=6 corresponding UV[N,2], XYZ[N,3], K[3,3]')
    if any(t.device != uv.device or not t.is_floating_point() or not torch.isfinite(t).all()
           for t in (uv, xyz, K)):
        raise ValueError('Inputs must be finite floating tensors on one device')
    if not (K[0, 0] > 0 and K[1, 1] > 0
            and torch.allclose(K[2], K.new_tensor([0, 0, 1]))
            and K[0, 1].abs() < 1e-12 and K[1, 0].abs() < 1e-12):
        raise ValueError('Expected positive-focal zero-skew calibrated pinhole K')
    u, X, k = uv.double(), xyz.double(), K.double()
    spectrum = torch.linalg.svdvals(X - X.mean(0))
    if spectrum[-1] <= 1e-8 or spectrum[0] / spectrum[-1] > 1e6:
        raise ValueError('Degenerate or near-planar support rejected by component contract')
    return pose_matrix(_ImplicitPnP.apply(u, X, k))
