"""Check shared SS updates without changing per-view CFG/UV evolution."""

import unittest
import torch

from cupid.pipelines.samplers.flow_euler import FlowEulerCfgSampler, FlowEulerGuidanceIntervalSampler
from cupid.pipelines.samplers.stereo import sample_shared_structure


class RecordingVelocity(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.states = []

    def forward(self, state, time, cond):
        self.states.append(state.clone())
        return torch.ones_like(state) * cond[:, None, None, None, None]


class StereoSamplerTest(unittest.TestCase):
    def test_interval_sampler_preserves_default_cfg_strength(self):
        model = RecordingVelocity()
        result = sample_shared_structure(FlowEulerGuidanceIntervalSampler(sigma_min=1e-5), model,
            torch.zeros(2, 2, 1, 1, 1), cond=torch.tensor([1., 3.]), neg_cond=torch.zeros(2),
            ss_channels=1, steps=2, cfg_interval=(0.0, .75))
        # t=1 outside interval: velocity=[1,3]; t=.5: default CFG gives [4,12].
        torch.testing.assert_close(result[:, :1], torch.full_like(result[:, :1], -5))
        torch.testing.assert_close(result[0, 1:], torch.full_like(result[0, 1:], -2.5))
        torch.testing.assert_close(result[1, 1:], torch.full_like(result[1, 1:], -7.5))

    def test_guidance_and_structure_shared_at_every_step_uv_stays_separate(self):
        model = RecordingVelocity()
        noise = torch.zeros(2, 4, 1, 1, 1)
        noise[1, :2] = 100  # discarded: one shared initial structure
        noise[1, 2:] = 10
        # guided velocities are 2*[1,3]-0=[2,6]; structure mean=4.
        result = sample_shared_structure(FlowEulerCfgSampler(sigma_min=1e-5), model, noise,
            cond=torch.tensor([1., 3.]), neg_cond=torch.zeros(2), ss_channels=2, cfg_strength=1., steps=4)
        for state in model.states:
            torch.testing.assert_close(state[0, :2], state[1, :2])
        torch.testing.assert_close(result[:, :2], torch.full_like(result[:, :2], -4))
        torch.testing.assert_close(result[0, 2:], torch.full_like(result[0, 2:], -2))
        torch.testing.assert_close(result[1, 2:], torch.full_like(result[1, 2:], 4))
        torch.testing.assert_close(noise[1, :2], torch.full_like(noise[1, :2], 100))


if __name__ == '__main__':
    unittest.main()
