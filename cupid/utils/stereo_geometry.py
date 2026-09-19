"""CPU/Numpy calibrated stereo geometry, independent of model and GT assets.

Pixel convention: integer image indices are pixel centers (top-left = 0,0).
Transforms use column vectors and CV cameras (+X right, +Y down, +Z forward).
No camera parameters or units are inferred from file names or learned poses.
"""

from dataclasses import dataclass
import numpy as np


class GeometryError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _array(value, shape, name):
    value = np.asarray(value, dtype=np.float64)
    if value.shape != shape or not np.isfinite(value).all():
        raise GeometryError("INVALID_CALIBRATION", f"{name} must be finite {shape}")
    return value


@dataclass
class StereoCalibration:
    K_left: np.ndarray
    K_right: np.ndarray
    right_from_left: np.ndarray
    image_size_left: tuple
    image_size_right: tuple
    length_unit: str
    source: str

    @classmethod
    def from_dict(cls, data):
        required = {"K_left", "K_right", "right_from_left", "image_size_left",
                    "image_size_right", "length_unit", "source", "camera_convention", "distortion"}
        if required - data.keys():
            raise GeometryError("INVALID_CALIBRATION", f"Missing fields: {sorted(required - data.keys())}")
        if data["camera_convention"] != "opencv" or data["distortion"] != "none":
            raise GeometryError("UNSUPPORTED_CAMERA", "Supply undistorted pinhole CV images and their calibration")
        if data["length_unit"] not in ("m", "scene_unit") or not data["source"]:
            raise GeometryError("INVALID_CALIBRATION", "Require documented source and length_unit=m or scene_unit")
        left = _array(data["K_left"], (3, 3), "K_left")
        right = _array(data["K_right"], (3, 3), "K_right")
        transform = _array(data["right_from_left"], (4, 4), "right_from_left")
        for K in (left, right):
            if abs(np.linalg.det(K)) < 1e-12 or K[0, 0] <= 0 or K[1, 1] <= 0 or not np.allclose(K[2], [0, 0, 1]):
                raise GeometryError("INVALID_CALIBRATION", "Invalid pinhole intrinsic matrix")
        R = transform[:3, :3]
        if not np.allclose(transform[3], [0, 0, 0, 1]) or not np.allclose(R.T @ R, np.eye(3), atol=1e-6) or not np.isclose(np.linalg.det(R), 1, atol=1e-6):
            raise GeometryError("INVALID_CALIBRATION", "Extrinsic must be rigid and proper; no automatic axis/reflection repair")
        if np.linalg.norm(transform[:3, 3]) <= 1e-12:
            raise GeometryError("ZERO_BASELINE", "Stereo baseline is zero")
        sizes = []
        for key in ("image_size_left", "image_size_right"):
            size = _array(data[key], (2,), key)
            if (size <= 0).any() or not np.equal(size, np.floor(size)).all():
                raise GeometryError("INVALID_CALIBRATION", "Image sizes must be positive integer [width,height]")
            sizes.append(tuple(int(v) for v in size))
        return cls(left, right, transform, *sizes, data["length_unit"], str(data["source"]))


def crop_uv_to_pixels(uv, original_size, processed_size, crop_box):
    """Undo crop/resize using edge-normalized UV and integer-center pixels.

    The returned 3x3 affine maps [u_normalized,v_normalized,1] to original
    pixel centers. Crop box must be the actual rounded PIL box, including pad.
    """
    uv = np.asarray(uv, dtype=np.float64)
    if uv.ndim != 2 or uv.shape[1] != 2:
        raise ValueError("UV must have shape [N,2]")
    ow, oh = original_size
    pw, ph = processed_size
    x0, y0, x1, y1 = crop_box
    if min(ow, oh, pw, ph, x1 - x0, y1 - y0) <= 0:
        raise ValueError("Invalid image/crop dimensions")
    sx, sy = ow / pw, oh / ph
    affine = np.array([[(x1 - x0) * sx, 0, x0 * sx - 0.5],
                       [0, (y1 - y0) * sy, y0 * sy - 0.5], [0, 0, 1.0]])
    return np.c_[uv, np.ones(len(uv))].dot(affine.T)[:, :2], affine


def fit_similarity(source, target):
    """Unweighted Umeyama fit, target = scale * source @ R.T + translation."""
    source, target = np.asarray(source, float), np.asarray(target, float)
    if source.ndim != 2 or source.shape[1] != 3 or target.shape != source.shape or len(source) < 3:
        raise GeometryError("INSUFFICIENT_POINTS", "Need >=3 corresponding 3D points")
    if not np.isfinite(source).all() or not np.isfinite(target).all():
        raise GeometryError("NONFINITE_POINTS", "Similarity input is not finite")
    mu_x, mu_y = source.mean(0), target.mean(0)
    x, y = source - mu_x, target - mu_y
    if np.linalg.matrix_rank(x) < 2 or np.linalg.matrix_rank(y) < 2:
        raise GeometryError("DEGENERATE_POINTS", "Coincident/collinear support cannot determine a similarity")
    U, singular, Vt = np.linalg.svd(y.T @ x / len(x))
    signs = np.ones(3)
    signs[-1] = np.linalg.det(U @ Vt)
    rotation = U @ np.diag(signs) @ Vt
    scale = float(np.dot(singular, signs) / np.mean(np.sum(x * x, axis=1)))
    if not np.isfinite(scale) or scale <= 0:
        raise GeometryError("INVALID_SCALE", "Fit did not return positive scale")
    translation = mu_y - scale * rotation @ mu_x
    residuals = np.linalg.norm(scale * source @ rotation.T + translation - target, axis=1)
    return {"scale": scale, "rotation": rotation, "translation": translation,
            "residuals": residuals, "rmse": float(np.sqrt(np.mean(residuals ** 2)))}


def triangulate_and_fit(source, left_uv, right_uv, calibration, *, max_reprojection_px=2.0, min_ray_angle_deg=0.1):
    """General calibrated triangulation; retains all points and rejection masks.

    Thresholds are configurable diagnostic defaults, not scientific success
    thresholds. No depth, source mesh, GT visibility, or GT pose is consulted.
    """
    source = np.asarray(source, float)
    left, right = np.asarray(left_uv, float), np.asarray(right_uv, float)
    if source.ndim != 2 or source.shape[1] != 3 or left.shape != (len(source), 2) or right.shape != left.shape:
        raise ValueError("Expected matching source[N,3], left/right[N,2]")
    if not np.isfinite([max_reprojection_px, min_ray_angle_deg]).all() or max_reprojection_px <= 0 or not 0 <= min_ray_angle_deg < 90:
        raise ValueError("Invalid geometry filtering parameters")
    n = len(source)
    masks = {"finite_input": np.isfinite(source).all(1) & np.isfinite(left).all(1) & np.isfinite(right).all(1)}
    inside = np.ones(n, dtype=bool)
    for pixels, size in ((left, calibration.image_size_left), (right, calibration.image_size_right)):
        inside &= (pixels >= -0.5).all(1) & (pixels < np.asarray(size) - 0.5).all(1)
    masks["inside_images"] = inside
    indices = np.flatnonzero(masks["finite_input"] & inside)
    points = np.full((n, 3), np.nan)
    R, t = calibration.right_from_left[:3, :3], calibration.right_from_left[:3, 3]
    reproj = np.full((n, 2), np.nan)
    angles = np.full(n, np.nan)
    if len(indices):
        a = np.c_[left[indices], np.ones(len(indices))] @ np.linalg.inv(calibration.K_left).T
        b = np.c_[right[indices], np.ones(len(indices))] @ np.linalg.inv(calibration.K_right).T
        a /= a[:, 2:3]
        b /= b[:, 2:3]
        P = np.c_[np.eye(3), np.zeros(3)]
        Q = np.c_[R, t]
        A = np.stack((a[:, 0, None] * P[2] - P[0], a[:, 1, None] * P[2] - P[1],
                      b[:, 0, None] * Q[2] - Q[0], b[:, 1, None] * Q[2] - Q[1]), axis=1)
        _, _, Vt = np.linalg.svd(A)
        homogeneous = Vt[:, -1]
        finite_solution = np.abs(homogeneous[:, 3]) > 1e-12
        points[indices[finite_solution]] = homogeneous[finite_solution, :3] / homogeneous[finite_solution, 3:4]
        b_left = b @ R
        cosine = np.sum(a * b_left, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b_left, axis=1))
        angles[indices] = np.degrees(np.arccos(np.clip(cosine, -1, 1)))
    camera_right = points @ R.T + t
    masks["finite_solution"] = np.isfinite(points).all(1)
    masks["positive_depth"] = (points[:, 2] > 0) & (camera_right[:, 2] > 0)
    for view, (p, K, observed) in enumerate(((points, calibration.K_left, left), (camera_right, calibration.K_right, right))):
        projected = p @ K.T
        with np.errstate(divide="ignore", invalid="ignore"):
            predicted = projected[:, :2] / projected[:, 2:3]
        reproj[:, view] = np.linalg.norm(predicted - observed, axis=1)
    masks["reprojection"] = np.isfinite(reproj).all(1) & (reproj <= max_reprojection_px).all(1)
    masks["ray_angle"] = np.isfinite(angles) & (angles >= min_ray_angle_deg)
    valid = np.logical_and.reduce(list(masks.values()))
    result = {"status": "OK", "points_left_camera": points, "disparity_px": left[:, 0] - right[:, 0],
              "reprojection_px": reproj, "ray_angle_deg": angles, "masks": masks, "valid": valid,
              "num_input": n, "num_valid": int(valid.sum()), "length_unit": calibration.length_unit,
              "source_frame": "cupid_canonical", "target_frame": "left_camera_opencv",
              "thresholds": {"max_reprojection_px": max_reprojection_px, "min_ray_angle_deg": min_ray_angle_deg}}
    try:
        result["similarity"] = fit_similarity(source[valid], points[valid])
    except GeometryError as error:
        result.update(status=error.code, message=str(error), similarity=None)
    return result
