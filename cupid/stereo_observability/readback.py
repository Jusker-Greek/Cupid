"""Exact server history verification, extending the existing CUPID scan pattern.

No sampled history API: sparse events and repeated optimizer steps must survive.
The receipt proves telemetry delivery, never scientific validity or S07 alone.
"""
import json
import math
from pathlib import Path

from .logger import digest, IDENTITY_KEYS


def load_events(root):
    root = Path(root)
    identity = json.loads((root/'identity.json').read_text())
    events = [json.loads(line) for line in (root/'events.jsonl').read_text().splitlines()]
    if not events:
        raise ValueError('empty_event_log')
    for sequence, event in enumerate(events, 1):
        payload = event['payload']
        unsigned = {k: v for k, v in payload.items() if k != 'observability/payload_sha256'}
        if digest(unsigned) != payload.get('observability/payload_sha256'):
            raise ValueError('local_payload_digest_mismatch')
        if payload['observability/sequence'] != sequence:
            raise ValueError('noncontiguous_local_event_sequence')
        if any(payload.get('identity/'+k) != identity[k] for k in IDENTITY_KEYS):
            raise ValueError('local_identity_mismatch')
        if payload['observability/event_id'] != identity['attempt_id']+':'+str(sequence):
            raise ValueError('local_event_id_mismatch')
        if payload.get('observability/details_sha256') != digest(event.get('details')):
            raise ValueError('local_details_digest_mismatch')
    return identity, events


def same_value(a, b):
    if isinstance(a, (int, float)) and not isinstance(a, bool):
        return isinstance(b, (int, float)) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return a == b


def compare_history(events, rows):
    expected = {e['payload']['observability/event_id']: e['payload'] for e in events}
    seen, mismatched = set(), set()
    for row in rows:
        key = row.get('observability/event_id')
        if key not in expected:
            continue
        payload = expected[key]
        if all(name in row and same_value(value, row[name]) for name, value in payload.items()):
            seen.add(key)
        else:
            mismatched.add(key)
    missing = sorted(set(expected)-seen)
    return dict(status='READBACK_PASS' if not missing and not mismatched else 'UNVERIFIED',
                num_expected_events=len(expected), num_verified_events=len(seen),
                missing_event_ids=missing, mismatched_event_ids=sorted(mismatched),
                s07_status='UNVERIFIED', evidence_eligibility='ENGINEERING_TELEMETRY_ONLY / NO_SCIENCE')


def readback(root, run_path, api=None):
    """One bounded attempt; caller owns retry identity and network timeout policy."""
    identity, events = load_events(root)
    if api is None:
        import wandb
        api = wandb.Api(timeout=30)
    run = api.run(run_path)
    # Same full sparse-history scan as scripts/verify_cupid_wandb.py. Check actual
    # payload values and identity rather than accepting a URL or key presence.
    report = compare_history(events, run.scan_history(page_size=1000))
    report.update(schema='stereo_wandb_readback/v1', run_path=run_path,
                  identity={k: identity[k] for k in IDENTITY_KEYS}, state=run.state,
                  local_events_sha256=digest(events))
    return report


def replay(root, wandb_run):
    """Replay immutable local events into an EXISTING caller-owned run.

    Idempotence is semantic via event_id: interrupted replay can add duplicate
    identical rows. Readback rejects conflicting rows, accepts identical copies.
    Caller must verify that this run is the intended Stereo attempt, not HSSD.
    """
    _, events = load_events(root)
    for event in events:
        wandb_run.log(event['payload'])
    return dict(status='REPLAY_ENQUEUED_READBACK_REQUIRED', num_events=len(events))
