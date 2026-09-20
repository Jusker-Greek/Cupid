#!/usr/bin/env python3
"""Finite Stereo evaluation/readback; execute only inside a Slurm allocation."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.stereo_observability.metrics import evaluate_sample, summarize, from_v1_result
from cupid.stereo_observability.readback import readback


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--samples', type=Path, help='JSON list of all expected sample records')
    p.add_argument('--v1-manifest', type=Path, help='JSON list: sample_id, result_path, optional gt/canonical_id')
    p.add_argument('--wandb-root', type=Path, help='stereo_observability directory')
    p.add_argument('--run-path', help='entity/project/run_id from existing run receipt')
    p.add_argument('--output', type=Path, required=True, help='Fresh JSON receipt; refuses overwrite')
    args = p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        p.error('Requires Slurm compute allocation')
    if sum(x is not None for x in (args.samples, args.v1_manifest, args.wandb_root)) != 1:
        p.error('Choose exactly one of --samples, --v1-manifest, --wandb-root')
    if args.output.exists():
        p.error('Output exists; preserve old attempt and choose a new path')
    if args.wandb_root:
        if not args.run_path or len(args.run_path.split('/')) != 3:
            p.error('--run-path must be entity/project/run_id')
        try:
            report = readback(args.wandb_root, args.run_path)
        except Exception as error:
            report = dict(status='UNVERIFIED', s07_status='UNVERIFIED', error_type=type(error).__name__,
                          reason='readback_failed_no_server_evidence', evidence_eligibility='NO_SCIENCE')
        code = 0 if report['status'] == 'READBACK_PASS' else 2
    else:
        if args.samples:
            samples = json.loads(args.samples.read_text())
        else:
            manifest = json.loads(args.v1_manifest.read_text())
            samples = []
            for item in manifest:
                path = Path(item['result_path'])
                if not path.is_absolute():
                    path = args.v1_manifest.parent/path
                try:
                    receipt = json.loads(path.read_text())
                    sample = from_v1_result(receipt, item['sample_id'], item.get('gt'), item.get('canonical_id'))
                except (OSError, ValueError, TypeError):
                    sample = dict(sample_id=item['sample_id'], prediction_status='FAILED',
                                  failure_reason='result_missing_or_unreadable')
                samples.append(sample)
        evaluated = [evaluate_sample(x) for x in samples]
        report = dict(schema='stereo_evaluation/v1', status='EVALUATED', samples=evaluated,
                      summary=summarize(evaluated), alignment='NONE',
                      evidence_eligibility='RAW_METRICS_REQUIRE_CONTROLLER_REVIEW')
        code = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=report['status'], output=str(args.output))))
    return code


if __name__ == '__main__':
    sys.exit(main())
