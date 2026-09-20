"""Rank-0 evaluation adapter; T owns barriers/error broadcast and val FM loss."""
from .metrics import evaluate_sample, summarize


def eval_factory(fullconfig, output_dir, rank):
    """Return keyword-only hook(model=bare_model, step=int, context=dict).

    context['samples'] must contain EVERY expected sample, including failures.
    L deliberately never calls model: I/T may run frozen inference separately
    and pass raw records. Without records, availability is explicit UNVERIFIED.
    No collectives or hidden validation data loading happen in this hook.
    """
    def hook(*, model, step, context):
        if rank != 0:
            return dict(status='NOT_APPLICABLE', reason='rank0_only_hook')
        samples = context.get('samples')
        if samples is None:
            return dict(schema='stereo_eval_hook/v1', status='UNVERIFIED', step=step,
                        reason='raw_prediction_and_expected_sample_manifest_not_provided',
                        metrics_status='UNVERIFIED', s07_status='UNVERIFIED')
        rows = [evaluate_sample(sample) for sample in samples]
        return dict(schema='stereo_eval_hook/v1', status='EVALUATED', step=step,
                    samples=rows, summary=summarize(rows), s07_status='UNVERIFIED')
    return hook
