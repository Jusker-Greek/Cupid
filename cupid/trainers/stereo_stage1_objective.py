"""Supervised SUV flow-matching candidate; no geometric SSL claim.

Same pretrained flow is used for both eyes. SS target/noise and time are shared
within a pair; each eye has its own UV target/noise and image condition.
"""
import torch
from torch import nn


class SharedStereoFlow(nn.Module):
    def __init__(self, flow):
        super().__init__()
        self.flow = flow

    def forward(self, x, t, cond):
        b, eyes, channels, d, h, w = x.shape
        if eyes != 2:
            raise ValueError("Exactly two views per object are required")
        pred = self.flow(x.reshape(b * 2, channels, d, h, w),
                         t[:, None].expand(b, 2).reshape(-1) * 1000,
                         cond.flatten(0, 1))
        return pred.reshape_as(x)


class SupervisedSUVFlowMatching:
    """Returns unreduced per-pair losses for correct padded DDP reduction."""
    def __init__(self, sigma_min=1e-5, t_mean=1.0, t_std=1.0, p_uncond=0.1):
        if not 0 <= sigma_min < 1 or not 0 <= p_uncond <= 1 or t_std <= 0:
            raise ValueError("Invalid flow matching schedule")
        self.sigma_min, self.t_mean, self.t_std = sigma_min, t_mean, t_std
        self.p_uncond = p_uncond

    def __call__(self, model, batch, training=True):
        ss, uv, cond = (batch[k] for k in ("ss_latent", "uv_latent", "cond"))
        if ss.ndim != 5 or uv.ndim != 6 or uv.shape[1] != 2:
            raise ValueError("Expected SS[B,C,D,H,W], UV[B,2,C,D,H,W]")
        if ss.shape[0] != uv.shape[0] or ss.shape[2:] != uv.shape[3:]:
            raise ValueError("SS/UV latent lattice mismatch")
        if cond.ndim != 4 or cond.shape[:2] != uv.shape[:2]:
            raise ValueError("Expected condition[B,2,tokens,channels]")
        for value in (ss, uv, cond):
            if not torch.isfinite(value).all():
                raise ValueError("Nonfinite latent/condition")
        b, cs, cu = ss.shape[0], ss.shape[1], uv.shape[2]
        x0 = torch.cat((ss[:, None].expand(-1, 2, -1, -1, -1, -1), uv), dim=2)
        ns = torch.randn_like(ss)[:, None].expand(-1, 2, -1, -1, -1, -1)
        noise = torch.cat((ns, torch.randn_like(uv)), dim=2)
        t = torch.sigmoid(torch.randn(b, device=ss.device) * self.t_std + self.t_mean)
        tv = t[:, None, None, None, None, None]
        xt = (1 - tv) * x0 + (self.sigma_min + (1 - self.sigma_min) * tv) * noise
        if training and self.p_uncond:
            # Pair-level CFG dropout retains the same conditioning regime per eye.
            keep = torch.rand(b, 1, 1, 1, device=ss.device) >= self.p_uncond
            cond = cond * keep
        pred = model(xt, t, cond)
        if pred.shape != x0.shape:
            raise ValueError("SUV prediction shape mismatch")
        target = (1 - self.sigma_min) * noise - x0
        error = (pred.float() - target.float()).square()
        ss_loss = error[:, :, :cs].flatten(1).mean(1)
        uv_loss = error[:, :, cs:].flatten(1).mean(1)
        return {"loss_total": (ss_loss * cs + uv_loss * cu) / (cs + cu),
                "loss_ss": ss_loss, "loss_uv": uv_loss,
                "loss_uv_left": error[:, 0, cs:].flatten(1).mean(1),
                "loss_uv_right": error[:, 1, cs:].flatten(1).mean(1)}


class OfficialTargetAdapter:
    """Frozen official encoders, posterior means (same as stored official latents).

    Dataset owns camera/crop/projection correctness. Dense input keys are
    ss[B,1,64,64,64], ssuv[B,2,1,64,64,64], uv_volume[B,2,2,64,64,64].
    Pre-encoded latents may be supplied instead. No target is synthesized here.
    """
    def __init__(self, dino, ss_encoder=None, uv_encoder=None):
        self.dino, self.ss_encoder, self.uv_encoder = dino, ss_encoder, uv_encoder
        for module in (dino, ss_encoder, uv_encoder):
            if module is not None:
                module.eval().requires_grad_(False)

    @torch.no_grad()
    def __call__(self, batch, device):
        result = {k: v.to(device) if isinstance(v, torch.Tensor) else v
                  for k, v in batch.items()}
        if "ss_latent" not in result:
            if self.ss_encoder is None or self.uv_encoder is None:
                raise ValueError("Dense targets require both official encoder assets")
            result["ss_latent"] = self.ss_encoder(result["ss"].float(), sample_posterior=False).float()
            uv_input = torch.cat((result["ssuv"].float(), result["uv_volume"].float()), dim=2)
            b = uv_input.shape[0]
            latent = self.uv_encoder(uv_input.flatten(0, 1), sample_posterior=False)
            result["uv_latent"] = latent.reshape(b, 2, *latent.shape[1:]).float()
        if "cond" not in result:
            images = result["images"]
            if images.ndim != 5 or images.shape[1:] != (2, 3, 518, 518):
                raise ValueError("images must be [B,2,3,518,518], preprocessed with target-matched crop")
            if not torch.isfinite(images).all() or images.min() < 0 or images.max() > 1:
                raise ValueError("images must be finite alpha-composited RGB in [0,1]")
            mean = images.new_tensor([0.485, 0.456, 0.406])[None, :, None, None]
            std = images.new_tensor([0.229, 0.224, 0.225])[None, :, None, None]
            features = self.dino((images.flatten(0, 1) - mean) / std, is_training=True)["x_prenorm"]
            features = torch.nn.functional.layer_norm(features, features.shape[-1:])
            result["cond"] = features.reshape(images.shape[0], 2, *features.shape[1:]).float()
        return result
