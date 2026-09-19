"""A deliberately sparse occupancy fixture checks common UV coordinate keys."""

from types import SimpleNamespace
import unittest
import torch

from cupid.pipelines.stereo import StereoCupid3DPipeline
from cupid.pipelines.processing import SparseStructureDecoder


class OccupancyDecoder:
    def __call__(self, latent):
        result = torch.full((1, 1, 2, 2, 2), -.01)
        result[0, 0, 0, 0, 0] = 1
        return result


class UVDecoder:
    def __call__(self, latent):
        result = torch.zeros(2, 3, 2, 2, 2)
        result[:, 1] = torch.arange(8).reshape(2, 2, 2) / 10
        result[1, 1] += .5
        result[1, 2] = -.5
        return result


class StereoSupportTest(unittest.TestCase):
    def test_expanded_uv_support_is_shared_but_distinct_from_occupancy(self):
        pipeline = StereoCupid3DPipeline()
        pipeline.structure_decoder = SparseStructureDecoder(OccupancyDecoder(), UVDecoder(), expand_min_num_activated=2)
        pipeline.pose_decoder = SimpleNamespace(resolution=2)
        result = pipeline._decode_stereo(torch.zeros(2, 2, 1, 1, 1), 1, 1)
        self.assertEqual(len(result['coords']), 1)
        self.assertEqual(len(result['support_coords']), 8)
        expected = torch.sigmoid(torch.arange(8) / 10)
        torch.testing.assert_close(result['uv_left'][:, 0], expected)
        torch.testing.assert_close(result['uv_right'][:, 0], torch.sigmoid(torch.arange(8) / 10 + .5))
        torch.testing.assert_close(result['x_local'], (result['support_coords'][:, 1:].float() + .5) / 2 - .5)


if __name__ == '__main__':
    unittest.main()
