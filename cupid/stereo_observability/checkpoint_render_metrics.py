"""Render a stereo checkpoint's colored mesh and call original CUPID metrics."""
import json
import math
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from cupid.renderers import MeshRenderer
from cupid.utils.loss_utils import psnr, ssim, lpips


class CheckpointRenderMetrics:
    labels = ('left_dlt', 'left_stereo_sim3', 'right_stereo_sim3')

    def __init__(self):
        from .paper_metrics import self_check
        self.renderer = MeshRenderer(dict(resolution=512, near=.01, far=100., ssaa=1))
        self.check = self_check(self.renderer)

    @torch.no_grad()
    def evaluate(self, prediction, pack, camera, output):
        mesh = prediction['canonical_outputs']['mesh'][0]
        if mesh.vertex_attrs is None or mesh.vertex_attrs.shape[1] < 3:
            raise ValueError('Colored mesh attributes required for image metrics')
        if not len(mesh.vertices) or not len(mesh.faces):
            raise ValueError('Empty predicted mesh')
        device = mesh.vertices.device
        poses = {'left_dlt': ('left', prediction['pose_left'])}
        fit = prediction['geometry'].get('similarity')
        if fit is not None:
            left = torch.eye(4, device=device)
            left[:3, :3] = torch.as_tensor(fit['rotation'], device=device) * float(fit['scale'])
            left[:3, 3] = torch.as_tensor(fit['translation'], device=device)
            right = torch.as_tensor(camera['right_from_left'], device=device, dtype=left.dtype) @ left
            for side, extrinsic in [('left', left), ('right', right)]:
                k = pack['views'][side]['K_fullpixel'].copy()
                k[:2] /= 512
                poses[side + '_stereo_sim3'] = (side, dict(extrinsic=extrinsic,
                    intrinsic=torch.as_tensor(k, device=device, dtype=torch.float32)))
        results = {}
        for label in self.labels:
            if label not in poses:
                results[label] = dict(status='NOT_AVAILABLE', reason='stereo_similarity_missing')
                continue
            side, pose = poses[label]
            rgba = pack['views'][side]['rgba']
            if rgba.shape != (512, 512, 4):
                raise ValueError('Render protocol requires native full-frame 512x512 RGBA')
            rendered = self.renderer.render(mesh, pose['extrinsic'], pose['intrinsic'], return_types=['color', 'mask'])
            rgb = rendered['color'].float().clamp(0, 1)
            gt = torch.as_tensor(rgba.copy(), device=device).float() / 255
            gt_rgb = (gt[..., :3] * gt[..., 3:]).permute(2, 0, 1)
            pm, gm = rendered['mask'] > .5, gt[..., 3] > .5
            if not gm.any():
                raise ValueError('GT foreground missing')
            score = float(psnr(rgb[None], gt_rgb[None]))
            if math.isnan(score) or score == -math.inf:
                raise ValueError('Invalid PSNR')
            metrics = dict(psnr_db=score if math.isfinite(score) else None,
                psnr_perfect_match=score == math.inf, ssim=float(ssim(rgb[None], gt_rgb[None])),
                lpips_vgg=float(lpips(rgb[None], gt_rgb[None])),
                mask_iou=float((pm & gm).sum() / (pm | gm).sum()))
            results[label] = dict(status='OK', view=side, metrics=metrics,
                extrinsic=pose['extrinsic'].cpu().tolist(), intrinsic=pose['intrinsic'].cpu().tolist())
            def to_image(tensor):
                return Image.fromarray((tensor.cpu().permute(1, 2, 0).numpy() * 255).round().astype(np.uint8))
            pred_image, gt_image = to_image(rgb), to_image(gt_rgb)
            pred_image.save(Path(output) / (label + '_rgb.png'))
            comparison = Image.new('RGB', (1024, 512))
            comparison.paste(gt_image, (0, 0))
            comparison.paste(pred_image, (512, 0))
            comparison.save(Path(output) / (label + '_gt_prediction.png'))
        (Path(output) / 'render_metrics.json').write_text(json.dumps(results, indent=2, allow_nan=False))
        return results


def summarize_render_metrics(samples):
    result = {}
    for label in CheckpointRenderMetrics.labels:
        rows = [s.get('render_metrics', {}).get(label, {}) for s in samples]
        result['render/' + label + '/success_fraction'] = sum(r.get('status') == 'OK' for r in rows) / len(rows)
        for key in ('psnr_db', 'ssim', 'lpips_vgg', 'mask_iou'):
            values = [r['metrics'][key] for r in rows if r.get('status') == 'OK'
                      and r['metrics'].get(key) is not None and math.isfinite(r['metrics'][key])]
            prefix = 'render/' + label + '/' + key
            result[prefix + '_coverage'] = len(values) / len(rows)
            if values:
                result[prefix] = sum(values) / len(values)
    return result
