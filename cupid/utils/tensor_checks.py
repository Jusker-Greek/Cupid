# Copyright (c) 2019,20-21-22-25 NVIDIA CORPORATION & AFFILIATES.
# Licensed under the Apache License, Version 2.0.


def check_tensor(tensor, shape=None, dtype=None, device=None, throw=True):
    """Validate tensor shape, dtype, and device using Kaolin 0.18 semantics."""
    if shape is not None:
        if len(shape) != tensor.ndim:
            if throw:
                raise ValueError(
                    f"tensor have {tensor.ndim} ndim, should have {len(shape)}"
                )
            return False
        for i, dim in enumerate(shape):
            if dim is not None and tensor.shape[i] != dim:
                if throw:
                    raise ValueError(
                        f"tensor shape is {tensor.shape}, should be {shape}"
                    )
                return False
    if dtype is not None and dtype != tensor.dtype:
        if throw:
            raise TypeError(f"tensor dtype is {tensor.dtype}, should be {dtype}")
        return False
    if device is not None and device != tensor.device.type:
        if throw:
            raise TypeError(
                f"tensor device is {tensor.device.type}, should be {device}"
            )
        return False
    return True
