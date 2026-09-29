"""Explicit budget extension without changing the optimization experiment."""
import hashlib
import json


def check_resume_contract(state, contract, world, checkpoint_sha256):
    old = state['contract']
    old_hash = hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
    if old_hash != state['contract_sha256'] or state['world_size'] != world:
        raise ValueError('Checkpoint contract integrity or topology mismatch')
    if old == contract:
        return 'exact'
    policy = contract['config'].get('resume_extension', {})
    if checkpoint_sha256 != policy.get('source_checkpoint_sha256'):
        raise ValueError('Budget extension requires the explicitly bound source checkpoint')
    mutable = {'budget', 'eval_every', 'save_every', 'checkpoint_evaluation',
               'eval_factory', 'prediction_factory', 'resume_extension', 'runtime_estimate'}
    old_config, new_config = old['config'], contract['config']
    if {k: v for k, v in old.items() if k != 'config'} != {k: v for k, v in contract.items() if k != 'config'}:
        raise ValueError('Dataset identity changed during budget extension')
    if {k: v for k, v in old_config.items() if k not in mutable} != {k: v for k, v in new_config.items() if k not in mutable}:
        raise ValueError('Optimization or model contract changed during budget extension')
    steps_per_epoch = (old['train_pairs'] + world * old_config['pairs_per_rank'] - 1) // (world * old_config['pairs_per_rank'])
    old_budget = old_config['budget'].get('updates', old_config['budget'].get('epochs', 0) * steps_per_epoch)
    new_budget = new_config['budget'].get('updates', new_config['budget'].get('epochs', 0) * steps_per_epoch)
    if new_budget <= max(old_budget, state['step']):
        raise ValueError('Budget extension must increase the total update budget')
    return 'authorized_budget_extension'
