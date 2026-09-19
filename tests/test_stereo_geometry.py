"""Analytical geometry fixtures. Run only in a cluster CPU allocation."""

import unittest
import numpy as np

from cupid.utils.stereo_geometry import StereoCalibration, crop_uv_to_pixels, fit_similarity, triangulate_and_fit, GeometryError


def camera(rotation=None):
    transform = np.eye(4)
    transform[:3, :3] = np.eye(3) if rotation is None else rotation
    transform[0, 3] = -0.2
    return StereoCalibration.from_dict({
        'K_left': [[700, 0, 319.5], [0, 710, 239.5], [0, 0, 1]],
        'K_right': [[720, 0, 310.5], [0, 705, 244.5], [0, 0, 1]],
        'right_from_left': transform.tolist(), 'image_size_left': [640, 480], 'image_size_right': [640, 480],
        'length_unit': 'm', 'source': 'analytical fixture, not GSO calibration',
        'camera_convention': 'opencv', 'distortion': 'none'})


def project(points, K):
    pixels = points @ K.T
    return pixels[:, :2] / pixels[:, 2:3]


class StereoGeometryTest(unittest.TestCase):
    def setUp(self):
        self.source = np.array([[-.3, -.2, .1], [.3, -.2, -.1], [-.2, .3, -.1], [.2, .2, .3], [0, 0, -.2]])
        angle = .3
        self.rotation = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
        self.target = .4 * self.source @ self.rotation.T + [0.02, -.03, 2.0]

    def test_nonrectified_unequal_intrinsics_known_metric_transform(self):
        angle = .06
        cam = camera(np.array([[np.cos(angle), 0, np.sin(angle)], [0, 1, 0], [-np.sin(angle), 0, np.cos(angle)]]))
        left = project(self.target, cam.K_left)
        right_xyz = self.target @ cam.right_from_left[:3, :3].T + cam.right_from_left[:3, 3]
        right = project(right_xyz, cam.K_right)
        result = triangulate_and_fit(self.source, left, right, cam)
        self.assertEqual(result['status'], 'OK')
        self.assertTrue(result['valid'].all())
        np.testing.assert_allclose(result['points_left_camera'], self.target, atol=1e-9)
        self.assertAlmostEqual(result['similarity']['scale'], .4, places=9)
        np.testing.assert_allclose(result['similarity']['rotation'], self.rotation, atol=1e-9)
        np.testing.assert_allclose(result['similarity']['translation'], [.02, -.03, 2], atol=1e-9)

    def test_degenerate_fit_does_not_return_identity(self):
        with self.assertRaises(GeometryError) as error:
            fit_similarity(np.zeros((4, 3)), np.ones((4, 3)))
        self.assertEqual(error.exception.code, 'DEGENERATE_POINTS')

    def test_invalid_correspondence_remains_in_failure_denominator(self):
        cam = camera()
        left = project(self.target, cam.K_left)
        right = project(self.target + [-.2, 0, 0], cam.K_right)
        left[0] = [np.nan, np.nan]
        right[1] = [9000, 9000]
        result = triangulate_and_fit(self.source, left, right, cam)
        self.assertEqual(result['num_input'], 5)
        self.assertFalse(result['valid'][0])
        self.assertFalse(result['valid'][1])
        self.assertEqual(len(result['points_left_camera']), 5)

    def test_pixels_include_resize_padding_and_half_pixel(self):
        # Preprocess 1000x800 -> 500x400; crop -10,20..91,121 (101x101).
        pixels, affine = crop_uv_to_pixels([[0, 0], [.5, .5], [1, 1]], (1000, 800), (500, 400), (-10, 20, 91, 121))
        np.testing.assert_allclose(pixels, [[-20.5, 39.5], [80.5, 140.5], [181.5, 241.5]])
        np.testing.assert_allclose(np.linalg.inv(affine) @ [80.5, 140.5, 1], [.5, .5, 1])

    def test_reflection_camera_rejected(self):
        with self.assertRaises(GeometryError):
            camera(np.diag([1, 1, -1]))

    def test_negative_depth_rejected(self):
        cam = camera()
        behind = self.target.copy()
        behind[:, 2] *= -1
        result = triangulate_and_fit(self.source, project(behind, cam.K_left), project(behind + [-.2, 0, 0], cam.K_right), cam)
        self.assertEqual(result['num_valid'], 0)
        self.assertEqual(result['status'], 'INSUFFICIENT_POINTS')


if __name__ == '__main__':
    unittest.main()
