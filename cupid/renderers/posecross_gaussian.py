"""Camera-gradient adapter for CUPID's SH0 Gaussian rasterizer.

The native extension differentiates primitives, but not camera settings. Move
means and covariances to camera coordinates in Torch and use an identity view.
This adapter does not solve poses, choose losses, or define a training method.
"""
import torch
from .gaussian_render import GaussianRenderer


def unpack_covariance(packed):
    xx, xy, xz, yy, yz, zz = packed.unbind(-1)
    return torch.stack((xx, xy, xz, xy, yy, yz, xz, yz, zz), -1).reshape(-1, 3, 3)


def pack_covariance(matrix):
    return torch.stack((matrix[:,0,0], matrix[:,0,1], matrix[:,0,2],
                        matrix[:,1,1], matrix[:,1,2], matrix[:,2,2]), -1)


class _CameraSpaceGaussian:
    """Read-only view of a Gaussian; source tensors retain their autograd graph."""
    def __init__(self, source, extrinsics):
        self.source = source
        self.rotation = extrinsics[:3,:3]
        self.translation = extrinsics[:3,3]
        self.active_sh_degree = 0
        self.max_sh_degree = 0

    @property
    def get_xyz(self):
        return self.source.get_xyz @ self.rotation.T + self.translation

    @property
    def get_features(self):
        return self.source.get_features

    @property
    def get_opacity(self):
        return self.source.get_opacity

    def get_covariance(self, scaling_modifier=1):
        covariance = unpack_covariance(self.source.get_covariance(scaling_modifier))
        camera_covariance = self.rotation[None] @ covariance @ self.rotation.T[None]
        return pack_covariance(camera_covariance).contiguous()


class CameraGradientGaussianRenderer(GaussianRenderer):
    """Fixed-known-K, SH0 renderer with explicit pose gradients through primitives.

    The base renderer and all existing callers are unchanged. SH>0 is rejected
    because rotating view-dependent SH requires a separate validated contract.
    """
    def __init__(self, rendering_options=None):
        super().__init__({} if rendering_options is None else rendering_options)
        self.pipe.compute_cov3D_python = True
        self.pipe.convert_SHs_python = False

    def render(self, gaussian, extrinsics, intrinsics, colors_overwrite=None):
        if gaussian.active_sh_degree != 0 or gaussian.sh_degree != 0:
            raise ValueError('Only native CUPID SH degree 0 is supported')
        if extrinsics.shape != (4,4) or intrinsics.shape != (3,3):
            raise ValueError('Expected object-to-camera 4x4 and normalized K 3x3')
        if intrinsics.requires_grad:
            raise ValueError('Known K must remain fixed; intrinsic gradients are unsupported')
        with torch.no_grad():
            if not torch.isfinite(extrinsics).all() or not torch.isfinite(intrinsics).all():
                raise ValueError('Camera contains nonfinite values')
            R = extrinsics[:3,:3]
            eye = torch.eye(3,device=R.device,dtype=R.dtype)
            if not torch.allclose(R @ R.T,eye,atol=1e-4,rtol=1e-4) or not torch.allclose(torch.det(R),R.new_tensor(1.),atol=1e-4):
                raise ValueError('Camera rotation must be proper SO(3)')
            if not torch.allclose(extrinsics[3],extrinsics.new_tensor([0,0,0,1]),atol=1e-6):
                raise ValueError('Invalid homogeneous camera row')
        view = _CameraSpaceGaussian(gaussian,extrinsics)
        identity = torch.eye(4,device=extrinsics.device,dtype=extrinsics.dtype)
        return super().render(view,identity,intrinsics,colors_overwrite=colors_overwrite)
