"""Durable callbacks around the existing CUPID TensorBoard/W&B objects.

No credential handling, new tracker initialization, model imports, or collectives.
Local JSONL is authoritative for recovery; a W&B call/URL is not server proof.
"""
import hashlib
import json
import math
import os
from pathlib import Path

from .metrics import evaluate_sample, summarize

IDENTITY_KEYS = ('experiment_id', 'attempt_id', 'git_commit', 'git_tree', 'slurm_job_id')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def scalar(value):
    if hasattr(value, 'item'):
        value = value.item()
    value = float(value)
    return value if math.isfinite(value) else None


def scalar_fields(key, value):
    value = scalar(value)
    if value is None:
        return {key + '/status': 'UNVERIFIED', key + '/reason': 'nonfinite_value'}
    return {key: value}


class StereoLogger:
    def __init__(self, output_dir, identity, rank=0, writer=None, wandb_run=None):
        self.rank, self.writer, self.wandb_run = rank, writer, wandb_run
        self.identity = {k: str(identity[k]) for k in IDENTITY_KEYS}
        if any(not v for v in self.identity.values()):
            raise ValueError('complete_run_identity_required')
        self.sequence = 0
        self.root = Path(output_dir) / 'stereo_observability'
        if rank != 0:
            return
        self.root.mkdir(parents=True, exist_ok=False)
        self.path = self.root / 'events.jsonl'
        self.path.touch(exist_ok=False)
        self._append('identity.json', dict(schema='stereo_observability/v1', **self.identity), mode='x')

    def _append(self, name, value, mode='a'):
        with (self.root / name).open(mode) as stream:
            stream.write(canonical(value) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def _emit(self, event, step, payload, details=None):
        if self.rank != 0:
            return None
        if isinstance(step, bool) or int(step) != step or step < 0:
            raise ValueError('step_must_be_nonnegative_integer')
        self.sequence += 1
        flat = dict(payload)
        flat['observability/details_sha256'] = digest(details)
        flat.update({'identity/'+k: v for k, v in self.identity.items()})
        flat.update({'observability/event': event, 'observability/sequence': self.sequence,
                     'train/global_step': int(step)})
        flat['observability/event_id'] = self.identity['attempt_id'] + ':' + str(self.sequence)
        flat['observability/payload_sha256'] = digest(flat)
        record = dict(schema='stereo_event/v1', payload=flat, details=details)
        # Network/disk errors cannot erase the pre-existing local record.
        self._append('events.jsonl', record)
        if self.writer is not None:
            try:
                for key, value in flat.items():
                    if isinstance(value, (float, int)):
                        self.writer.add_scalar(key, value, step)
                    else:
                        self.writer.add_text(key, str(value), step)
                self.writer.flush()
            except Exception as error:
                self._append('sink_failures.jsonl', dict(sequence=self.sequence, sink='tensorboard', error_type=type(error).__name__))
        if self.wandb_run is not None:
            try:
                # W&B owns its history row counter; several callbacks share a train
                # step. Passing step=step here would drop later rows at that step.
                self.wandb_run.log(flat)
            except Exception as error:
                # Do not persist exception text: transport errors can contain secrets.
                self._append('sink_failures.jsonl', dict(sequence=self.sequence, sink='wandb', error_type=type(error).__name__))
        return record

    def log_losses(self, step, *, split, total, components, epoch, learning_rates=None, num_samples=None):
        if split not in ('train', 'validation', 'test'):
            raise ValueError('split_must_be_train_validation_or_test')
        values = scalar_fields(split+'/loss_total', total)
        values.update(scalar_fields('train/epoch', epoch))
        for key, value in components.items():
            values.update(scalar_fields(split+'/loss/'+key, value))
        if learning_rates is not None:
            for index, lr in enumerate(learning_rates):
                values.update(scalar_fields('train/learning_rate/group_'+str(index), lr))
            if learning_rates:
                values.update(scalar_fields('train/learning_rate', learning_rates[0]))
        if num_samples is not None:
            values[split+'/num_samples'] = int(num_samples)
        return self._emit('loss', step, values)

    def log_optimizer(self, step, *, applied, grad_norm, amp_log_scale=None, amp_scale=None, reason=None):
        if not isinstance(applied, bool):
            raise ValueError('optimizer_applied_must_be_bool')
        values = {'optimizer/step_applied': int(applied)}
        if grad_norm is not None:
            values.update(scalar_fields('optimizer/grad_norm', grad_norm))
        else:
            values.update({'optimizer/grad_norm/status': 'UNVERIFIED', 'optimizer/grad_norm/reason': 'not_measured'})
        if reason:
            values['optimizer/reason'] = str(reason)
        if amp_log_scale is not None:
            values.update(scalar_fields('amp/log_scale', amp_log_scale))
        if amp_scale is not None:
            values.update(scalar_fields('amp/scale', amp_scale))
        return self._emit('optimizer', step, values)

    def log_checkpoint(self, step, *, path, status, sha256=None):
        if status not in ('WRITTEN', 'FAILED', 'RELOADED'):
            raise ValueError('invalid_checkpoint_status')
        return self._emit('checkpoint', step, {'checkpoint/path': str(path), 'checkpoint/status': status,
            'checkpoint/sha256': sha256 or 'UNVERIFIED'})

    def log_status(self, step, *, metric, status, reason):
        if status not in ('NOT_APPLICABLE', 'UNVERIFIED') or not reason:
            raise ValueError('explicit_nonvalue_status_and_reason_required')
        return self._emit('status', step, {metric+'/status': status, metric+'/reason': reason})

    def log_evaluation(self, step, *, samples, split='validation'):
        if split not in ('validation', 'test', 'inference'):
            raise ValueError('invalid_evaluation_split')
        evaluated = [evaluate_sample(x) for x in samples]
        summary = summarize(evaluated)
        prefix = split+'/pose/'
        values = {split+'/num_expected': summary['num_expected'], split+'/num_prediction_ok': summary['num_prediction_ok']}
        for name, metric in summary['metrics'].items():
            for key in ('status', 'reason', 'num_valid', 'num_expected'):
                values[prefix+name+'/'+key] = metric[key]
            if metric['unit'] is not None:
                values[prefix+name+'/unit'] = metric['unit']
            if metric['mean'] is not None:
                values[prefix+name] = metric['mean']
            if metric['coverage'] is not None:
                values[prefix+name+'/coverage'] = metric['coverage']
        return self._emit('evaluation', step, values, dict(samples=evaluated, summary=summary))

    def __call__(self, event, step, payload):
        if self.rank != 0:
            return None
        handlers = {'loss': self.log_losses, 'optimizer': self.log_optimizer,
                    'checkpoint': self.log_checkpoint, 'evaluation': self.log_evaluation, 'status': self.log_status}
        if event not in handlers:
            raise ValueError('unknown_stereo_event: '+event)
        return handlers[event](step, **payload)


def logger_factory(config, output_dir, rank):
    """T contract. config holds identity plus existing writer/wandb_run objects.

    Create on all ranks; nonzero ranks return a pure no-op without touching disk.
    Pass tensors detached/scalar at the call site. This adapter never reduces DDP
    values; caller must reduce loss/grad metrics before rank-0 emission.
    """
    if rank != 0:
        return lambda event, step, payload: None
    return StereoLogger(output_dir, config['identity'], rank=rank,
                        writer=config.get('writer'), wandb_run=config.get('wandb_run'))
