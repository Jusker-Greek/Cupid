"""Two-view occupancy sharing using the existing Euler/CFG update."""

import numpy as np
import torch

from .flow_euler import FlowEulerSampler, FlowEulerCfgSampler, FlowEulerGuidanceIntervalSampler


def resolved_stereo_params(sampler, params=None):
    """Keep defaults normally supplied by sampler.sample, which we bypass."""
    resolved = dict(params or {})
    resolved.setdefault('steps', 50)
    resolved.setdefault('rescale_t', 1.0)
    resolved.setdefault('verbose', False)
    if isinstance(sampler, (FlowEulerCfgSampler, FlowEulerGuidanceIntervalSampler)):
        resolved.setdefault('cfg_strength', 3.0)
    if isinstance(sampler, FlowEulerGuidanceIntervalSampler):
        resolved.setdefault('cfg_interval', (0.0, 1.0))
    return resolved


@torch.no_grad()
def sample_shared_structure(
    sampler, model, noise, cond, ss_channels, *, steps=50,
    rescale_t=1.0, verbose=False, **kwargs,
):
    """Return [2,C,D,H,W]; only the SS slice is shared at every step.

    Each view keeps its own UV state and conditioning. Calling sample_once
    preserves the original velocity parameterization, CFG and guidance interval.
    Averaging candidate SS states equals averaging velocities because both
    branches start each step with exactly the same SS state and time step.
    """
    if not isinstance(sampler, FlowEulerSampler):
        raise TypeError("Stereo sharing currently supports FlowEulerSampler subclasses only")
    resolved = resolved_stereo_params(sampler, kwargs)
    for key in ('steps', 'rescale_t', 'verbose'):
        resolved.pop(key)
    kwargs = resolved
    if noise.ndim != 5 or noise.shape[0] != 2:
        raise ValueError("Expected exactly two views in [2,C,D,H,W]")
    if not 0 < ss_channels < noise.shape[1]:
        raise ValueError("Need nonempty structure and UV channel slices")
    if int(steps) != steps or steps < 1 or not np.isfinite(rescale_t) or rescale_t <= 0:
        raise ValueError("steps must be positive integer; rescale_t must be positive")
    state = noise.clone()
    state[1, :ss_channels] = state[0, :ss_channels]
    times = np.linspace(1.0, 0.0, int(steps) + 1)
    times = rescale_t * times / (1 + (rescale_t - 1) * times)
    for index in range(int(steps)):
        candidate, _ = sampler.sample_once(
            model, state, float(times[index]), float(times[index + 1]),
            cond=cond, **kwargs,
        )
        shared = candidate[:, :ss_channels].mean(dim=0, keepdim=True)
        state = torch.cat((shared.expand(2, *shared.shape[1:]), candidate[:, ss_channels:]), dim=1)
        if verbose:
            print(f"STEREO_STAGE1_STEP={index + 1}/{steps}", flush=True)
    return state
