"""Assemble or verify the fixed official release; run only on Slurm nodes.

No network, model imports, source mutation or existing-root repair. A failed
assembly remains a failed attempt; use a new output path after correction.
"""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import subprocess

REVISION = '1191de37cc33b60273a631d4e07fbbe7cee798c1'
MANIFEST_SHA256 = 'ce25e0cff494f4b0dce0966fa74e5ae815df752eaa6fb05950ffc98627600692'
MANIFEST = Path(__file__).resolve().parents[1] / 'docs/stereo_cupid_v1/lanes/R_runtime/R_official_manifest.json'


def release_items():
    raw = MANIFEST.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise RuntimeError('PINNED_MANIFEST_HASH_MISMATCH')
    manifest = json.loads(raw)
    items = manifest['siblings']
    if (manifest['id'] != 'hbb1/Cupid' or manifest['sha'] != REVISION
            or len(items) != 25 or sum(x['size'] for x in items) != 7268259545):
        raise RuntimeError('RELEASE_IDENTITY_MISMATCH')
    names = set()
    for item in items:
        name = item['rfilename']
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or str(p) != name or name in names:
            raise RuntimeError('UNSAFE_OR_DUPLICATE_MANIFEST_PATH')
        names.add(name)
    return items


def verify_file(path, item):
    if not path.is_file() or path.stat().st_size != item['size']:
        return False
    digest = hashlib.sha256() if 'lfs' in item else hashlib.sha1()
    if 'lfs' not in item:
        digest.update(f"blob {item['size']}\0".encode())
    with path.open('rb') as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
            digest.update(block)
    expected = item['lfs']['sha256'] if 'lfs' in item else item['blobId']
    return digest.hexdigest() == expected


def check_pipeline(root, items):
    names = {item['rfilename'] for item in items}
    pipeline = json.loads((root / 'pipeline.json').read_text())
    models = pipeline['args']['models']
    if not models:
        raise RuntimeError('EMPTY_PIPELINE_MODELS')
    for model in models.values():
        for suffix in ('.json', '.safetensors'):
            if model + suffix not in names or not (root / (model + suffix)).is_file():
                raise RuntimeError(f'PIPELINE_REFERENCE_NOT_IN_RELEASE: {model}{suffix}')
    return pipeline['args']['image_cond_model']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, action='append', default=[])
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('SLURMD_NODENAME'):
        raise RuntimeError('SLURM_COMPUTE_NODE_REQUIRED')
    items = release_items()
    if args.verify_only:
        receipt = json.loads((args.output / 'download_receipt.json').read_text())
        if (receipt.get('status') != 'VERIFIED' or receipt.get('revision') != REVISION
                or receipt.get('manifest_sha256') != MANIFEST_SHA256):
            raise RuntimeError('ROOT_NOT_VERIFIED')
        for item in items:
            if not verify_file(args.output / item['rfilename'], item):
                raise RuntimeError(f"ROOT_HASH_MISMATCH: {item['rfilename']}")
        check_pipeline(args.output, items)
        print('OFFICIAL_ROOT_REVERIFIED=25_FILES', flush=True)
        return
    if not args.source:
        parser.error('assembly requires at least one --source')
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = {
        'schema': 'stereo_cupid_official_assembly/v1', 'repo': 'hbb1/Cupid',
        'revision': REVISION, 'manifest_sha256': MANIFEST_SHA256,
        'status': 'ASSEMBLING', 'job': os.environ['SLURM_JOB_ID'],
        'host': socket.gethostname(), 'files': [], 'total_bytes': 7268259545,
        'source_roots': [str(x.resolve()) for x in args.source],
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
        'scientific_result_eligible': False,
    }

    def save():
        temporary = args.output / 'download_receipt.json.tmp'
        temporary.write_text(json.dumps(receipt, indent=2) + '\n')
        temporary.replace(args.output / 'download_receipt.json')

    save()
    try:
        for item in items:
            name = item['rfilename']
            selected = None
            for root in args.source:
                candidate = root / name
                if verify_file(candidate, item):
                    selected = candidate
                    break
            if selected is None:
                raise RuntimeError(f'NO_VERIFIED_SOURCE: {name}')
            target = args.output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(selected.resolve(), target)
                method = 'hardlink'
            except OSError as error:
                if error.errno != errno.EXDEV:
                    raise
                with selected.open('rb') as source, target.open('xb') as destination:
                    shutil.copyfileobj(source, destination, 8 * 1024 * 1024)
                method = 'copy_cross_filesystem'
            if not verify_file(target, item):
                raise RuntimeError(f'ASSEMBLED_HASH_MISMATCH: {name}')
            receipt['files'].append(dict(item, source=str(selected.resolve()), method=method))
            save()
            print(f'ASSEMBLED_VERIFIED {name}', flush=True)
        receipt['image_cond_model'] = check_pipeline(args.output, items)
        receipt['status'] = 'VERIFIED'
        save()
        print('CUPID_OFFICIAL_ASSEMBLY=VERIFIED', flush=True)
    except Exception as error:
        receipt.update(status='FAILED', first_failed_predicate=str(error))
        save()
        raise


if __name__ == '__main__':
    main()
