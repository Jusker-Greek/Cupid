"""Stereo-CUPID V1: shared structure, separate UV, geometry after sampling."""

import torch
from pathlib import Path

from .pipeline import Cupid3DPipeline
from .processing import ImageEncoder
from .samplers.stereo import sample_shared_structure
from ..modules import sparse as sp
from ..utils.stereo_geometry import crop_uv_to_pixels, triangulate_and_fit


class StereoCupid3DPipeline(Cupid3DPipeline):
    @staticmethod
    def from_pretrained(path, *, dino_repo, dino_checkpoint):
        # Load the existing local DINO implementation without triggering a
        # torch.hub repository or checkpoint download.
        pipeline = StereoCupid3DPipeline()
        pipeline.dino_repo = str(Path(dino_repo).resolve(strict=True))
        pipeline.dino_checkpoint = str(Path(dino_checkpoint).resolve(strict=True))
        return Cupid3DPipeline.from_pretrained(path, cls=lambda: pipeline)

    def _init_image_cond_model(self, name):
        model = torch.hub.load(self.dino_repo, name, source="local", pretrained=False)
        model.load_state_dict(torch.load(self.dino_checkpoint, map_location="cpu", weights_only=True))
        model.eval()
        self.image_encoder = ImageEncoder(model, self.visual_cond_resolution)
        self.image_encoder.to(self.device)
        self.models['image_cond_model'] = self.image_encoder

    def _prepare_view(self, image, mask, crop):
        original_size = image.size
        if mask is not None:
            if mask.size != image.size:
                raise ValueError("Mask and original image must have identical size")
            image = image.copy()
            image.putalpha(mask.split()[-1])
        processed = self.preprocess_image(image)
        processed_size = processed.image.size
        if crop:
            processed = self.crop_image(processed)
            box = processed.crop_params.box
            if box is None or processed.image.size != (box[2] - box[0], box[3] - box[1]):
                raise ValueError("Recorded crop does not match the actual PIL image")
        else:
            box = (0, 0, *processed_size)
        trace = {"original_size": list(original_size), "processed_size": list(processed_size),
                 "crop_box": list(box), "network_crop_size": list(processed.image.size),
                 "pixel_convention": "integer_center", "uv_convention": "edge_normalized",
                 "crop_enabled": crop}
        return processed, trace

    @torch.no_grad()
    def _decode_stereo(self, latent, ss_channels, uv_channels):
        # Decode occupancy once. Both UV fields are gathered by the same
        # explicit [batch=0,i,j,k] keys, including any support expansion.
        decoder = self.structure_decoder
        logits = decoder.structure_decoder(latent[:1, :ss_channels])
        uv_logits = decoder.uv_decoder(latent[:, ss_channels:ss_channels + uv_channels])
        if not torch.isfinite(logits).all() or not torch.isfinite(uv_logits).all():
            raise ValueError("Nonfinite Stage1 decoder output")
        if logits.shape[1] != 1 or uv_logits.shape[1] != 3 or logits.shape[2:] != uv_logits.shape[2:]:
            raise ValueError("Expected occupancy[B,1,D,H,W] and UV[B,3,D,H,W] on the same grid")
        resolution = logits.shape[2]
        if logits.shape[2:] != (resolution,) * 3 or self.pose_decoder.resolution != resolution:
            raise ValueError("Stage1 decoder and Stage2 coordinate resolutions differ")
        occupied = (logits > 0).int()
        coords = torch.argwhere(occupied)[:, [0, 2, 3, 4]].int()
        if logits[0].numel() < decoder.expand_min_num_activated:
            raise ValueError("Minimum UV support exceeds grid size")
        expanded = decoder._expand_sparse_uv(logits, occupied)
        support = torch.argwhere(expanded)[:, [0, 2, 3, 4]].int()
        spatial = support[:, 1:].long()
        views = []
        for view in range(2):
            dense_uv = uv_logits[view, 1:3].permute(1, 2, 3, 0)
            views.append(torch.sigmoid(dense_uv[spatial[:, 0], spatial[:, 1], spatial[:, 2]]))
        return {"coords": coords, "support_coords": support, "uv_left": views[0], "uv_right": views[1],
                "x_local": (spatial.float() + 0.5) / resolution - 0.5, "resolution": resolution}

    @torch.no_grad()
    def run_stereo(
        self, left, right, *, mask_left=None, mask_right=None, seed=42,
        crop=True, stage2=False, calibration=None, sampler_params=None,
        slat_sampler_params=None, uv_noise="independent",
        max_reprojection_px=2.0, min_ray_angle_deg=0.1,
    ):
        """Always return raw Stage1 support and both UV fields.

        Missing calibration does not block generation: geometry receives a
        CALIBRATION_MISSING status. If requested, original left-view pose,
        Conditioner and Stage2 produce a canonical mesh. No inferred GT is used.
        """
        if uv_noise not in ("independent", "shared"):
            raise ValueError("uv_noise must be independent or shared")
        if calibration is not None and (left.size != calibration.image_size_left or right.size != calibration.image_size_right):
            raise ValueError("Calibration dimensions must match original input images")
        processed_left, trace_left = self._prepare_view(left, mask_left, crop)
        processed_right, trace_right = self._prepare_view(right, mask_right, crop)
        torch.manual_seed(seed)
        cond, visual = self.get_cond([processed_left, processed_right])
        flow = self.models['sparse_structure_flow_model']
        ss_channels = self.structure_decoder.structure_decoder.latent_channels
        uv_channels = self.structure_decoder.uv_decoder.latent_channels
        if flow.in_channels != ss_channels + uv_channels:
            raise ValueError("The checkpoint must be joint SS+UV, not an occupancy-only flow")
        noise = torch.randn(2, flow.in_channels, *([flow.resolution] * 3), device=self.device)
        if uv_noise == "shared":
            noise[1, ss_channels:] = noise[0, ss_channels:]
        params = {**self.sparse_structure_sampler_params, **(sampler_params or {})}
        params.setdefault("verbose", True)
        latent = sample_shared_structure(self.sparse_structure_sampler, flow, noise, ss_channels=ss_channels, **cond, **params)
        result = self._decode_stereo(latent, ss_channels, uv_channels)
        for side, trace in (("left", trace_left), ("right", trace_right)):
            pixels, affine = crop_uv_to_pixels(result[f'uv_{side}'].cpu().numpy(),
                trace['original_size'], trace['processed_size'], trace['crop_box'])
            trace['full_pixel_from_uv'] = affine.tolist()
            result[f'pixels_{side}'] = pixels
        result['preprocessing'] = {"left": trace_left, "right": trace_right}
        result['sampling'] = {"seed": seed, "uv_noise": uv_noise, "parameters": params,
                              "ss_channels": ss_channels, "uv_channels": uv_channels,
                              "sampler": type(self.sparse_structure_sampler).__name__,
                              "structure_sharing": "equal_mean_after_each_guided_euler_update",
                              "support_source": "shared_structure_decoder_with_minimum_support_expansion",
                              "stage2_requested": stage2}
        if calibration is None:
            result['geometry'] = {"status": "CALIBRATION_MISSING", "similarity": None,
                                  "message": "Raw support and UV saved; external camera contract was not supplied"}
        else:
            result['geometry'] = triangulate_and_fit(result['x_local'].cpu().numpy(),
                result['pixels_left'], result['pixels_right'], calibration,
                max_reprojection_px=max_reprojection_px, min_ray_angle_deg=min_ray_angle_deg)
        if stage2:
            if not len(result['coords']):
                result['stage2_status'] = "EMPTY_OCCUPANCY"
                return result
            try:
                self._run_left_stage2(result, cond, visual, processed_left, slat_sampler_params)
            except Exception as error:
                # Preserve completed Stage1 evidence while explicitly reporting
                # a failed requested Stage2, rather than returning fake success.
                result['stage2_status'] = 'FAILED'
                result['stage2_error'] = f'{type(error).__name__}: {error}'
        return result

    def _run_left_stage2(self, result, cond, visual, processed_left, slat_sampler_params):
        # Original left UV camera recovery and left conditioner stay intact.
        left_uv = sp.SparseTensor(feats=result['uv_left'], coords=result['support_coords'])
        poses = self.decode_uv(left_uv)
        left_cond = {key: value[:1] for key, value in cond.items()}
        slat_cond = {**left_cond, 'extrinsic': poses[0].extrinsic.unsqueeze(0),
                     'intrinsic': poses[0].intrinsic.unsqueeze(0), 'visual_cond': visual[:1]}
        slat = self.sample_slat(slat_cond, result['coords'], slat_sampler_params)
        outputs = self.decode_slat(slat, formats=['mesh'])
        if not outputs.get('mesh') or not len(outputs['mesh'][0].vertices):
            raise ValueError('Stage2 did not produce a nonempty mesh')
        result['canonical_outputs'] = outputs
        result['pose_left'] = poses[0].de_crop(processed_left.crop_params).as_dict()
        result['stage2_status'] = "OK"
