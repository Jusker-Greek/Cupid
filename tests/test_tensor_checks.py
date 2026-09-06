import unittest

import torch

from cupid.utils.tensor_checks import check_tensor


class CheckTensorTest(unittest.TestCase):
    def setUp(self):
        self.tensor = torch.zeros((2, 3), dtype=torch.float32)

    def test_accepts_exact_shape_and_none_wildcard(self):
        self.assertTrue(check_tensor(self.tensor, shape=(2, 3)))
        self.assertTrue(check_tensor(self.tensor, shape=(None, 3)))

    def test_shape_failures_honor_throw(self):
        self.assertFalse(check_tensor(self.tensor, shape=(2,), throw=False))
        self.assertFalse(check_tensor(self.tensor, shape=(3, 2), throw=False))
        with self.assertRaisesRegex(ValueError, "tensor have 2 ndim, should have 1"):
            check_tensor(self.tensor, shape=(2,))
        with self.assertRaisesRegex(ValueError, "tensor shape is"):
            check_tensor(self.tensor, shape=(3, 2))

    def test_dtype_failure_honors_throw(self):
        self.assertTrue(check_tensor(self.tensor, dtype=torch.float32))
        self.assertFalse(
            check_tensor(self.tensor, dtype=torch.float16, throw=False)
        )
        with self.assertRaisesRegex(TypeError, "tensor dtype is torch.float32"):
            check_tensor(self.tensor, dtype=torch.float16)

    def test_device_failure_honors_throw(self):
        self.assertTrue(check_tensor(self.tensor, device="cpu"))
        self.assertFalse(check_tensor(self.tensor, device="cuda", throw=False))
        with self.assertRaisesRegex(TypeError, "tensor device is cpu"):
            check_tensor(self.tensor, device="cuda")


if __name__ == "__main__":
    unittest.main()
