"""Verify real PIL crop bounds match the exported pixel mapping."""

import unittest
import numpy as np
from PIL import Image

from cupid.pipelines.processing import ImageProcessor
from cupid.pipelines.types import ProcessedImage
from cupid.utils.stereo_geometry import crop_uv_to_pixels


class StereoCropTest(unittest.TestCase):
    def test_existing_alpha_preprocessing_preserves_input(self):
        rgba = Image.new('RGBA', (16, 16), (12, 34, 56, 0))
        rgba.putpixel((8, 8), (80, 90, 100, 255))
        result = ImageProcessor().preprocess(rgba)
        np.testing.assert_array_equal(np.asarray(result.image), np.asarray(rgba))

    def test_rounded_odd_crop_and_padding(self):
        rgba = np.zeros((80, 100, 4), dtype=np.uint8)
        rgba[0:32, 0:32] = [255, 255, 255, 255]
        processed = ImageProcessor().crop_to_content(ProcessedImage.from_image(Image.fromarray(rgba)))
        box = processed.crop_params.box
        self.assertEqual(processed.image.size, (box[2] - box[0], box[3] - box[1]))
        # A particular original pixel center should survive crop and inverse mapping.
        uv = [[(10.5 - box[0]) / processed.image.width, (12.5 - box[1]) / processed.image.height]]
        pixels, _ = crop_uv_to_pixels(uv, (100, 80), (100, 80), box)
        np.testing.assert_allclose(pixels, [[10, 12]])


if __name__ == '__main__':
    unittest.main()
