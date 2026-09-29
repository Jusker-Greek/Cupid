"""Explicit input-view protocol using CUPID render/loss code and MoGe alignment.

Same metric families as the paper, not a claim of exact benchmark reproduction:
the paper's mesh-vs-GS choice, background, CD display scaling and sample list
are not specified by a released evaluator. Never align RGB or masks to GT.
"""
import numpy as np
import torch
from scipy.spatial import cKDTree

from cupid.utils.loss_utils import psnr, ssim, lpips
from .vendor.moge_alignment import align_points_scale_xyz_shift


def unproject(depth, intrinsics):
    """OpenCV z-depth and normalized edge-coordinate intrinsics."""
    h, w = depth.shape
    y, x = np.mgrid[:h, :w]
    uv1 = np.stack(((x + .5) / w, (y + .5) / h, np.ones_like(x)), -1)
    return (uv1 @ np.linalg.inv(intrinsics).T) * depth[..., None]


def cloud_distances(pred, gt):
    if not len(pred) or not len(gt):
        raise ValueError('Empty visible point cloud')
    forward = cKDTree(gt).query(pred, workers=4)[0]
    backward = cKDTree(pred).query(gt, workers=4)[0]
    result = dict(cd_l1_scene_unit=float((forward.mean() + backward.mean()) / 2),
                  cd_l2_squared_scene_unit2=float((np.square(forward).mean() + np.square(backward).mean()) / 2))
    for threshold in (.01, .05):
        precision, recall = float(np.mean(forward < threshold)), float(np.mean(backward < threshold))
        result[f'fscore_{threshold}'] = 2 * precision * recall / (precision + recall) if precision + recall else 0.
    return result


@torch.no_grad()
def evaluate_view(rendered, pred_k, rgba, gt_depth, gt_valid, gt_k):
    """Return scalar metrics and alignment. All image metrics are full-frame."""
    rgb = rendered['color'].float().clamp(0, 1)
    alpha = rendered['mask'].float().clamp(0, 1)
    device = rgb.device
    gt_alpha = torch.as_tensor(rgba[..., 3].copy(), device=device).float() / 255
    gt_rgb = torch.as_tensor(rgba[..., :3].copy(), device=device).permute(2, 0, 1).float() / 255
    gt_rgb = gt_rgb * gt_alpha[None]  # black background, as in CUPID image encoder
    if rgb.shape != gt_rgb.shape:
        raise ValueError('Rendered and GT image dimensions differ')
    p_mask, g_mask = alpha > .5, gt_alpha > .5
    union = (p_mask | g_mask).sum()
    metrics = dict(mask_iou=float((p_mask & g_mask).sum() / union),
                   psnr_db=float(psnr(rgb[None], gt_rgb[None])),
                   ssim=float(ssim(rgb[None], gt_rgb[None])),
                   lpips_vgg=float(lpips(rgb[None], gt_rgb[None])),
                   predicted_mask_pixels=int(p_mask.sum()), gt_mask_pixels=int(g_mask.sum()))
    pred_depth = rendered['depth'].float().cpu().numpy()
    pred_valid = p_mask.cpu().numpy() & np.isfinite(pred_depth) & (pred_depth > 0)
    gt_valid = gt_valid & g_mask.cpu().numpy()
    pred_xyz = unproject(pred_depth, pred_k)
    gt_xyz = unproject(gt_depth, gt_k)
    overlap = pred_valid & gt_valid
    geometry = dict(status='FAILED', alignment='MoGe shared xyz scale + xyz shift, no rotation',
                    alignment_pixels=int(overlap.sum()), pred_points=int(pred_valid.sum()),
                    gt_points=int(gt_valid.sum()))
    if pred_valid.any() and gt_valid.any():
        geometry['raw'] = cloud_distances(pred_xyz[pred_valid], gt_xyz[gt_valid])
    if overlap.sum() >= 8:
        # Deterministic bounded fit; evaluate distances on ALL valid points.
        source, target = pred_xyz[overlap], gt_xyz[overlap]
        selection = np.linspace(0, len(source) - 1, min(512, len(source)), dtype=np.int64)
        p = torch.tensor(source[selection], device=device, dtype=torch.float32)
        g = torch.tensor(target[selection], device=device, dtype=torch.float32)
        scale, shift = align_points_scale_xyz_shift(p, g, 1 / g.norm(dim=-1).clamp_min(1e-8))
        scale, shift = float(scale), shift.cpu().numpy()
        geometry.update(scale=scale, shift=shift.tolist(), alignment_fit_points=len(selection))
        if np.isfinite(scale) and scale > 0 and np.isfinite(shift).all():
            geometry['aligned'] = cloud_distances(pred_xyz[pred_valid] * scale + shift, gt_xyz[gt_valid])
            geometry['status'] = 'OK'
        else:
            geometry['reason'] = 'nonpositive_or_nonfinite_alignment_scale'
    else:
        geometry['reason'] = 'insufficient_mask_overlap_for_correspondence_alignment'
    return dict(image=metrics, geometry=geometry)


@torch.no_grad()
def self_check(renderer):
    """Nontrivial invariants: known similarity, identical images, raster camera."""
    from cupid.representations.mesh import MeshExtractResult
    rng = np.random.default_rng(43)
    xyz = rng.normal(size=(100, 3)).astype(np.float32)
    p = torch.tensor(xyz, device='cuda')
    shift_gt = torch.tensor([.2, -.1, .4], device='cuda')
    scale, shift = align_points_scale_xyz_shift(p, p * 2 + shift_gt, torch.ones(100, device='cuda'))
    assert torch.allclose(scale, scale.new_tensor(2.), atol=1e-4)
    assert torch.allclose(shift, shift_gt, atol=1e-4)
    assert cloud_distances(xyz, xyz)['fscore_0.01'] == 1
    assert cloud_distances(xyz, xyz)['cd_l1_scene_unit'] == 0
    im = torch.rand(1, 3, 64, 64, device='cuda')
    assert torch.isinf(psnr(im, im)) and abs(float(ssim(im, im)) - 1) < 1e-5
    assert abs(float(lpips(im, im))) < 1e-5
    # Off-centre triangle detects accidental image flips as well as z-depth errors.
    verts = torch.tensor([[.05, -.3, 1], [.35, -.3, 1], [.2, -.05, 1]], device='cuda')
    faces = torch.tensor([[0, 1, 2]], device='cuda')
    attrs = torch.tensor([[1., 0., 0.]] * 3, device='cuda')
    mesh = MeshExtractResult(verts, faces, attrs)
    k = torch.tensor([[1., 0, .5], [0, 1., .5], [0, 0, 1.]], device='cuda')
    result = renderer.render(mesh, torch.eye(4, device='cuda'), k, return_types=['mask', 'depth', 'color'])
    n = renderer.rendering_options.resolution
    yy, xx = torch.where(result['mask'] > .5)
    assert abs(float(xx.float().mean() / n) - .7) < .02
    assert abs(float(yy.float().mean() / n) - (.5 - .65 / 3)) < .02
    assert torch.allclose(result['depth'][result['mask'] > .99], torch.ones_like(result['depth'][result['mask'] > .99]), atol=1e-4)
    return dict(status='PASS', checks=['known_scale_shift', 'identical_clouds', 'identical_image_metrics', 'offcentre_camera_raster_and_zdepth'])
