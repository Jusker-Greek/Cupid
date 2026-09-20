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


class StereoGSOLatents:
    """Training adapter for hash-bound, independently encoded left/right targets.

    Missing targets are hard failures. Index coverage is explicit; callers may
    supply a deliberately bounded pair manifest, never silently trim it here.
    """
    def __init__(self, manifest, root, target_index, target_root, split,
                 ss_channels=8, uv_channels=8, image_size=518, target_kind='latent'):
        self.raw = StereoGSOPairs(manifest, root, split=split)
        self.target_root = Path(target_root)
        self.ss_channels, self.uv_channels = ss_channels, uv_channels
        self.image_size = image_size
        if target_kind not in ('latent', 'dense'):
            raise ValueError('target_kind must be latent or dense')
        self.target_kind = target_kind
        if image_size != 518:
            raise ValueError('Stage-1 image contract requires 518x518')
        self.targets = {}
        with open(target_index) as handle:
            for line in handle:
                row = json.loads(line)
                if row.get('schema') != ('STEREO_GSO_LATENT_V1' if target_kind == 'latent' else 'STEREO_GSO_DENSE_V1'):
                    raise ValueError('unsupported target schema')
                if row['pair_id'] in self.targets:
                    raise ValueError('duplicate target pair_id: ' + row['pair_id'])
                self.targets[row['pair_id']] = row
        for row in self.raw.records:
            target = self.targets.get(row['pair_id'])
            if target is None:
                raise ValueError('target missing: ' + row['pair_id'])
            for key in ('object_id', 'trajectory_id', 'frame_id', 'split'):
                if row[key] != target[key]:
                    raise ValueError('target identity mismatch: ' + key)
            if not row.get('asset_sha256') or row['asset_sha256'] != target.get('source_asset_sha256'):
                raise ValueError('target must bind all audited source asset hashes')
            provenance = target['provenance']
            if target_kind == 'latent' and provenance.get('sample_posterior') is not False:
                raise ValueError('cached target must use encoder posterior mean')
            if target_kind == 'latent' and provenance.get('latent_normalization') != 'none':
                raise ValueError('expected official unnormalized SS/SUV latents')
            hash_keys = ('geometry_receipt_sha256', 'ss_encoder_sha256', 'uv_encoder_sha256') if target_kind == 'latent' else ('geometry_receipt_sha256',)
            for key in hash_keys:
                value = provenance.get(key, '')
                if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                    raise ValueError('missing provenance SHA256: ' + key)

    def __len__(self):
        return len(self.raw)

    def __getitem__(self, index):
        import torch
        record = self.raw.records[index]
        target = self.targets[record['pair_id']]
        pack = load_pair(record, self.raw.root, hash_assets=True)
        if pack['asset_sha256'] != target['source_asset_sha256']:
            raise ValueError('source assets changed since target encoding')
        path = confined_path(self.target_root, target['npz'])
        if sha256_file(path) != target['sha256']:
            raise ValueError('latent NPZ hash mismatch')
        with np.load(path, allow_pickle=False) as data:
            crop = np.asarray(data['crop_xyxy'], dtype=np.float64)
            shapes = ({'ss_latent': (self.ss_channels,16,16,16), 'uv_latent': (2,self.uv_channels,16,16,16)}
                      if self.target_kind == 'latent' else {'ss': (1,64,64,64), 'ssuv': (2,1,64,64,64), 'uv_volume': (2,2,64,64,64)})
            tensors = {}
            for key, shape in shapes.items():
                array = np.asarray(data[key], dtype=np.float32)
                if array.shape != shape or not np.isfinite(array).all():
                    raise ValueError('target shape/finiteness mismatch: ' + key)
                if key in ('ss', 'ssuv') and not np.isin(array, [0,1]).all():
                    raise ValueError('expected binary target: ' + key)
                if key == 'uv_volume' and ((array < 0) | (array > 1)).any():
                    raise ValueError('UV target outside [0,1]')
                tensors[key] = torch.from_numpy(array.copy())
        if crop.shape != (2, 4) or not np.isfinite(crop).all() or not np.equal(crop, np.round(crop)).all():
            raise ValueError('crop must be exact PIL integer xyxy boxes')
        images, maps = [], []
        for i, side in enumerate(SIDES):
            x0, y0, x1, y1 = crop[i].astype(int)
            if x1 <= x0 or y1 <= y0:
                raise ValueError('empty target crop')
            # Official ImageConditionedMixin: crop RGBA, resize RGBA, then RGB*alpha.
            image = Image.fromarray(pack['views'][side]['rgba']).crop((x0,y0,x1,y1))
            image = np.asarray(image.resize((518,518), Image.Resampling.LANCZOS), dtype=np.float32) / 255
            images.append(torch.from_numpy((image[...,:3] * image[...,3:]).transpose(2,0,1).copy()))
            maps.append([[x1-x0, 0, x0], [0, y1-y0, y0], [0,0,1]])
        return {**tensors,
                'images': torch.stack(images),
                'pair_id': record['pair_id'], 'object_id': record['object_id'],
                'trajectory_id': record['trajectory_id'], 'frame_id': record['frame_id'],
                'split': record['split'], 'unit': record['unit'],
                'provenance': target['provenance'],
                'input_uv_to_fullpixel': torch.tensor(maps, dtype=torch.float64),
                'validity': {'training_target_ready': True, 'metric_meters_verified': False}}


def collate_stage1_pairs(batch):
    import torch
    tensors = [key for key, value in batch[0].items() if isinstance(value, torch.Tensor)]
    result = {key: torch.stack([sample[key] for sample in batch]) for key in tensors}
    result.update({key: [sample[key] for sample in batch] for key in batch[0] if key not in tensors})
    return result


def build_stage1_datasets(config):
    """T factory(config)->train/validation/collate_fn/identity; no encoder jobs."""
    kwargs = {key: config[key] for key in ('manifest', 'root', 'target_index', 'target_root')}
    kwargs.update({key: config[key] for key in ('ss_channels', 'uv_channels', 'image_size', 'target_kind') if key in config})
    train = StereoGSOLatents(**kwargs, split='train')
    validation = StereoGSOLatents(**kwargs, split='validation')
    train_objects = {row['object_id'] for row in train.raw.records}
    val_objects = {row['object_id'] for row in validation.raw.records}
    if train_objects & val_objects:
        raise ValueError('object leakage between training and validation')
    image_splits = {}
    for dataset in (train, validation):
        for row in dataset.raw.records:
            for side in SIDES:
                digest = row['asset_sha256'][side + '_rgba']
                prior = image_splits.setdefault(digest, row['split'])
                if prior != row['split']:
                    raise ValueError('identical image content across train/validation')
    return {'train': train, 'validation': validation, 'collate_fn': collate_stage1_pairs,
            'identity': {'schema': SCHEMA, 'manifest_sha256': sha256_file(config['manifest']),
                         'target_index_sha256': sha256_file(config['target_index']),
                         'train_pairs': len(train), 'validation_pairs': len(validation),
                         'training_target_ready': True, 'length_unit': 'scene_unit',
                         'metric_meters_verified': False}}


def official_dense_targets(occupancy, w2c_cv, K_fullpixel, image_wh, crop_xyxy, *, const_ssuv=True):
    """Official const-SSUV recipe, full-image support retained during crop.

    Only accept caller-verified canonical occupancy and canonical->CV cameras.
    Raw GSO saved matrices are deliberately not passed through this interface.
    Uses the same project_cv implementation and clamp-before-crop order as
    SparseUVStructure + ImageConditionedMixin; no stereo averaging.
    """
    import torch
    import utils3d
    if const_ssuv not in (True, 'crop'):
        raise ValueError('supported official contract: const_ssuv=True or crop')
    ss = torch.as_tensor(occupancy, dtype=torch.float32)
    if ss.shape != (1,64,64,64) or not torch.isfinite(ss).all() or not ((ss == 0) | (ss == 1)).all() or not ss.any():
        raise ValueError('expected nonempty binary canonical occupancy[1,64,64,64]')
    xyz = (torch.arange(64, dtype=torch.float32) + .5) / 64 - .5
    centers = torch.stack(torch.meshgrid(xyz, xyz, xyz, indexing='ij'), dim=-1).reshape(-1,3)
    cameras = np.asarray(w2c_cv, dtype=np.float64)
    intrinsics = np.asarray(K_fullpixel, dtype=np.float64)
    sizes = np.asarray(image_wh, dtype=np.float64)
    crops = np.asarray(crop_xyxy, dtype=np.float64)
    if cameras.shape != (2,4,4) or intrinsics.shape != (2,3,3) or sizes.shape != (2,2) or crops.shape != (2,4):
        raise ValueError('invalid stereo calibration dimensions')
    if not all(np.isfinite(a).all() for a in (cameras, intrinsics, sizes, crops)) or (sizes <= 0).any():
        raise ValueError('nonfinite camera/crop or invalid image size')
    uv_volumes, supports = [], []
    for i in range(2):
        rotation = cameras[i,:3,:3]
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5) or not np.isclose(np.linalg.det(rotation),1,atol=1e-5) or not np.allclose(cameras[i,3], [0,0,0,1]):
            raise ValueError('canonical-to-CV camera must have a proper rotation')
        K = intrinsics[i].copy()
        if K[0,0] <= 0 or K[1,1] <= 0 or not np.allclose(K[2], [0,0,1]):
            raise ValueError('invalid pinhole K')
        K[0] /= sizes[i,0]
        K[1] /= sizes[i,1]
        uv, _ = utils3d.torch.project_cv(centers, torch.tensor(cameras[i],dtype=torch.float32), torch.tensor(K,dtype=torch.float32))
        if not torch.isfinite(uv).all():
            raise ValueError('nonfinite projected UV')
        uv = uv.T.reshape(2,64,64,64)
        support = ((uv >= .01) & (uv <= .99)).all(dim=0, keepdim=True)
        uv = uv.clamp(0,1)
        lower = torch.tensor(crops[i,:2] / sizes[i],dtype=torch.float32)[:,None,None,None]
        upper = torch.tensor(crops[i,2:] / sizes[i],dtype=torch.float32)[:,None,None,None]
        if not (upper > lower).all() or not np.equal(crops[i], np.round(crops[i])).all():
            raise ValueError('crop must be nonempty exact PIL box')
        uv = ((uv-lower)/(upper-lower)).clamp(0,1)
        if const_ssuv == 'crop':
            support = ((uv >= .01) & (uv <= .99)).all(dim=0, keepdim=True)
        uv_volumes.append(uv)
        supports.append(support.float())
    return {'ss': ss, 'ssuv': torch.stack(supports), 'uv_volume': torch.stack(uv_volumes)}
