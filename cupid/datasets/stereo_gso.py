"""Auditable GSO stereo records. No implicit camera conversion or augmentation.

This module deliberately has no torch/model dependency. Import the class from
this module directly; the historical dataset registry is unchanged.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

SCHEMA = 'STEREO_GSO_PAIR_V1'
SIDES = ('left', 'right')


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def object_split(object_id, seed='STEREO_CUPID_STAGE1_TRAIN_V1', fractions=(.8, .1, .1)):
    """Stable across dataset versions; never include root, trajectory or frame."""
    if len(fractions) != 3 or any(x < 0 for x in fractions) or not np.isclose(sum(fractions), 1):
        raise ValueError('split fractions must be three nonnegative values summing to one')
    value = int(hashlib.sha256((seed + '\0' + object_id).encode()).hexdigest()[:16], 16) / 2**64
    return 'train' if value < fractions[0] else 'validation' if value < sum(fractions[:2]) else 'test'


def confined_path(root, relative):
    path = (Path(root) / relative).resolve()
    path.relative_to(Path(root).resolve())
    return path


def discover_pairs(root, dataset_id, seed='STEREO_CUPID_STAGE1_TRAIN_V1', fractions=(.8, .1, .1)):
    """Yield observed candidates, including missing assets, without inventing frames.

    Metadata parse failures are recorded. Numeric filename stems pair PNG/NPY
    000 with HDF5 0; ambiguous aliases fail instead of choosing one silently.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    for obj in sorted(root.iterdir()):
        if not obj.is_dir() or obj.is_symlink():
            continue
        for trajectory in sorted(obj.iterdir()):
            if not trajectory.is_dir() or trajectory.is_symlink():
                continue
            metadata_path = trajectory / 'trajectory_info.json'
            errors, metadata = [], {}
            try:
                metadata = json.loads(metadata_path.read_text())
                if not isinstance(metadata, dict):
                    raise ValueError('trajectory metadata must be an object')
            except (OSError, ValueError) as exc:
                errors.append('metadata: ' + str(exc))
                metadata = {}
            files = {}
            for side in SIDES:
                for suffix, kind in (('png', 'rgba'), ('npy', 'extrinsics')):
                    files[side + '_' + kind] = list((trajectory / side).glob('*.' + suffix))
            files['depth'] = list(trajectory.glob('*.hdf5'))
            indexed = {}
            for kind, paths in files.items():
                indexed[kind] = {}
                for path in sorted(paths):
                    key = str(int(path.stem)) if path.stem.isdigit() else path.stem
                    indexed[kind].setdefault(key, []).append(str(path.relative_to(root)))
            keys = sorted(set().union(*(set(v) for v in indexed.values())))
            if not keys:
                keys = [None]  # retain empty/failed trajectory in audit denominator
            for key in keys:
                row_errors = list(errors)
                assets = {}
                for kind, index in indexed.items():
                    choices = index.get(key, [])
                    assets[kind] = choices[0] if len(choices) == 1 else None
                    if len(choices) != 1:
                        row_errors.append(f'{kind}: expected one asset, found {len(choices)}')
                pair_id = '/'.join((dataset_id, obj.name, trajectory.name, key or '__empty__'))
                yield {
                    'schema': SCHEMA, 'dataset_id': dataset_id, 'pair_id': pair_id,
                    'object_id': obj.name, 'trajectory_id': trajectory.name, 'frame_id': key,
                    'split': object_split(obj.name, seed, fractions),
                    'split_policy': {'seed': seed, 'fractions': list(fractions), 'key': 'object_id'},
                    'assets': assets, 'metadata': metadata,
                    'normalization': metadata.get('normalization'),
                    'unit': {'length': 'scene_unit', 'metric_meters_verified': False},
                    'provenance': {
                        'metadata_path': str(metadata_path.relative_to(root)),
                        'metadata_sha256': sha256_file(metadata_path) if metadata_path.is_file() else None,
                        'renderer_exact_revision': metadata.get('renderer_revision'),
                        'renderer_version': metadata.get('renderer_version'),
                        'historical_renderer_verified': False,
                    },
                    'validity': {'files_complete': not row_errors, 'errors': row_errors,
                                 'content_verified': False, 'training_target_ready': False},
                }


def _matrix(path):
    matrix = np.asarray(np.load(path, allow_pickle=False), dtype=np.float64)
    if matrix.shape == (3, 4):
        matrix = np.vstack([matrix, [0., 0., 0., 1.]])
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        raise ValueError(f'invalid camera matrix: {path}')
    if not np.allclose(matrix[3], [0, 0, 0, 1]):
        raise ValueError(f'invalid homogeneous matrix row: {path}')
    return matrix


def _intrinsics(metadata, width, height):
    """FOV-derived hypothesis, explicitly not a verified per-dataset calibration."""
    resolution = metadata.get('resolution')
    if resolution != [width, height]:
        raise ValueError(f'metadata resolution {resolution} disagrees with PNG {[width, height]}')
    fov = float(metadata['fov'])
    if not 0 < fov < 180:
        raise ValueError('invalid horizontal FOV')
    focal = width / (2 * np.tan(np.deg2rad(fov) / 2))
    return np.array([[focal, 0, width/2], [0, focal, height/2], [0, 0, 1]], dtype=np.float64)


def load_pair(record, root, *, depth_background=1e10, hash_assets=False):
    """Return raw fullpixel arrays plus diagnostics; never silently repair axes.

    RGBA: uint8 HWC; mask: bool alpha>127; depth: float32 HW; depth_valid:
    finite & positive & foreground & below explicit background sentinel.
    Invalid/depth background values remain unchanged in returned depth.
    """
    import h5py

    if record.get('schema') != SCHEMA or not record['validity']['files_complete']:
        raise ValueError('record is not a complete ' + SCHEMA + ': ' + record['pair_id'])
    if not np.isfinite(depth_background) or depth_background <= 0:
        raise ValueError('depth_background must be positive and finite')
    pack = {key: record[key] for key in ('pair_id', 'object_id', 'trajectory_id', 'frame_id',
                                        'split', 'unit', 'normalization')}
    pack['record'] = record
    pack['views'] = {}
    pack['provenance'] = dict(record['provenance'])
    pack['validity'] = dict(record['validity'])
    depth_path = confined_path(root, record['assets']['depth'])
    with h5py.File(depth_path, 'r') as handle:
        if 'depth' not in handle or handle['depth'].ndim != 3 or handle['depth'].shape[0] != 2:
            raise ValueError('expected HDF5 depth[2,H,W]: ' + str(depth_path))
        depths = np.asarray(handle['depth'], dtype=np.float32)
        colors = np.asarray(handle['colors']) if 'colors' in handle else None
        if 'blender_proc_version' in handle:
            version = handle['blender_proc_version'][()]
            pack['provenance']['blender_proc_version'] = str(version.decode() if isinstance(version, bytes) else version)
    for i, side in enumerate(SIDES):
        image_path = confined_path(root, record['assets'][side + '_rgba'])
        with Image.open(image_path) as image:
            if image.mode != 'RGBA':
                raise ValueError(f'{side}: expected RGBA, got {image.mode}')
            rgba = np.asarray(image).copy()
        height, width = rgba.shape[:2]
        if depths[i].shape != (height, width):
            raise ValueError(f'{side}: depth/PNG dimensions disagree')
        if colors is not None and (colors.shape[0] != 2 or not np.array_equal(colors[i], rgba)):
            raise ValueError(f'{side}: HDF5 colors/PNG disagree')
        mask = rgba[..., 3] > 127
        if not mask.any():
            raise ValueError(f'{side}: empty alpha mask')
        w2c = _matrix(confined_path(root, record['assets'][side + '_extrinsics']))
        determinant = float(np.linalg.det(w2c[:3, :3]))
        orthogonal = bool(np.allclose(w2c[:3, :3].T @ w2c[:3, :3], np.eye(3), atol=1e-5))
        K = _intrinsics(record['metadata'], width, height)
        valid_depth = mask & np.isfinite(depths[i]) & (depths[i] > 0) & (depths[i] < depth_background)
        pack['views'][side] = {
            'rgba': rgba, 'mask': mask, 'depth': depths[i], 'depth_valid': valid_depth,
            'K_fullpixel': K, 'K_status': 'DERIVED_HORIZONTAL_FOV_HYPOTHESIS',
            'w2c_saved': w2c, 'camera_convention': 'SAVED_RENDERER_AXES_UNVERIFIED',
            'rotation_determinant': determinant,
            'proper_rotation': orthogonal and abs(determinant - 1) < 1e-5,
            'crop_xyxy': [0, 0, width, height], 'fullpixel_to_input_pixel': np.eye(3),
            'input_uv_to_fullpixel': np.diag([width, height, 1.]),
            'preprocessing': 'NONE_FULLPIXEL', 'uv_convention': 'u*W,v*H',
            'depth_semantics': 'RENDERER_DEPTH_UNVERIFIED',
            'depth_background_exclusive': depth_background,
            'mask_semantics': 'VISIBLE_ALPHA_THRESHOLD_127_NOT_AMODAL',
        }
    pack['validity']['content_verified'] = True
    pack['validity']['calibration_verified'] = False
    pack['validity']['training_target_ready'] = False
    pack['validity']['proper_rotations'] = all(v['proper_rotation'] for v in pack['views'].values())
    if hash_assets:
        pack['asset_sha256'] = {key: sha256_file(confined_path(root, value)) for key, value in record['assets'].items()}
    return pack


class StereoGSOPairs:
    """Map-style dataset, one pair per row; compatible with torch DataLoader.

    Use collate_pairs to preserve metadata/variable image sizes. Default selects
    content-verified rows only. Failed samples are never replaced with another
    random item; the immutable audit manifest preserves their denominator.
    """
    def __init__(self, manifest, root, split=None, require_content_verified=True):
        self.root = Path(root)
        self.records = []
        seen = set()
        with open(manifest) as handle:
            for line in handle:
                row = json.loads(line)
                if row['pair_id'] in seen:
                    raise ValueError('duplicate pair_id: ' + row['pair_id'])
                seen.add(row['pair_id'])
                if split is not None and row['split'] != split:
                    continue
                if not row['validity']['files_complete']:
                    continue
                if require_content_verified and not row['validity']['content_verified']:
                    continue
                self.records.append(row)
        if not self.records:
            raise ValueError('no eligible pairs; inspect audit summary and requested split')

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        return load_pair(self.records[index], self.root)

    @staticmethod
    def collate_pairs(batch):
        return batch
