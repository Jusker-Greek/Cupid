import argparse
import glob
import json
import math
import os
import random
import sys

import numpy as np
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from easydict import EasyDict as edict

from cupid import datasets, models, trainers
from cupid.utils.dist_utils import setup_dist


def find_ckpt(cfg):
    cfg["load_ckpt"] = None
    if cfg.load_dir != "":
        if cfg.ckpt == "latest":
            files = glob.glob(os.path.join(cfg.load_dir, "ckpts", "misc_*.pt"))
            if files:
                cfg.load_ckpt = max(
                    int(os.path.basename(path).split("step")[-1].split(".")[0])
                    for path in files
                )
        elif cfg.ckpt != "none":
            cfg.load_ckpt = int(cfg.ckpt)
    return cfg


def setup_rng(rank):
    torch.manual_seed(rank)
    torch.cuda.manual_seed_all(rank)
    np.random.seed(rank)
    random.seed(rank)


def get_model_summary(model):
    num_params = sum(param.numel() for param in model.parameters())
    num_trainable = sum(param.numel() for param in model.parameters() if param.requires_grad)
    return f"Parameters: {num_params}\nTrainable parameters: {num_trainable}\n"


def _assert_finite(value, path="step_log"):
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_finite(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_finite(child, f"{path}[{index}]")
    elif isinstance(value, torch.Tensor):
        if not torch.isfinite(value).all():
            raise RuntimeError(f"Non-finite tensor at {path}")
    elif isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        raise RuntimeError(f"Non-finite value at {path}: {value}")


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(child) for child in value]
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _optimizer_step_marker(optimizer):
    steps = []
    for state in optimizer.state.values():
        step = state.get("step")
        if isinstance(step, torch.Tensor):
            step = step.item()
        if isinstance(step, (int, float, np.number)):
            steps.append(float(step))
    return max(steps, default=0.0)


def run_smoke(trainer, smoke_steps, smoke_max_attempts):
    if trainer.is_master:
        print(
            "\nStarting bounded smoke test for "
            f"{smoke_steps} optimizer update(s) within {smoke_max_attempts} attempt(s)...",
            flush=True,
        )

    attempt_logs = []
    optimizer_updates = 0
    for attempt in range(1, smoke_max_attempts + 1):
        optimizer_step_before = _optimizer_step_marker(trainer.optimizer)
        log_scale_before = getattr(trainer, "log_scale", None)
        data_list = trainer.load_data()
        step_log = trainer.run_step(data_list)
        _assert_finite(step_log)
        trainer.step += 1

        optimizer_step_after = _optimizer_step_marker(trainer.optimizer)
        log_scale_after = getattr(trainer, "log_scale", None)
        optimizer_step_applied = optimizer_step_after > optimizer_step_before
        optimizer_updates += int(optimizer_step_applied)
        attempt_log = {
            "attempt": attempt,
            "trainer_step": trainer.step,
            "optimizer_step_before": optimizer_step_before,
            "optimizer_step_after": optimizer_step_after,
            "optimizer_step_applied": optimizer_step_applied,
            "optimizer_updates": optimizer_updates,
            "log_scale_before": log_scale_before,
            "log_scale_after": log_scale_after,
            "step_log": step_log,
        }
        attempt_logs.append(attempt_log)
        if trainer.is_master:
            print("SMOKE_ATTEMPT=" + json.dumps(_jsonable(attempt_log), sort_keys=True), flush=True)
        if optimizer_updates >= smoke_steps:
            break

    if optimizer_updates < smoke_steps:
        raise RuntimeError(
            f"Smoke completed {optimizer_updates}/{smoke_steps} required optimizer updates "
            f"after {smoke_max_attempts} attempts; final log_scale="
            f"{getattr(trainer, 'log_scale', None)}"
        )

    if trainer.is_master:
        trainer.save()
        checkpoint_paths = [
            os.path.join(trainer.output_dir, "ckpts", f"{name}_step{trainer.step:07d}.pt")
            for name in trainer.models
        ]
        checkpoint_paths.append(
            os.path.join(trainer.output_dir, "ckpts", f"misc_step{trainer.step:07d}.pt")
        )
        missing = [path for path in checkpoint_paths if not os.path.isfile(path)]
        if missing:
            raise RuntimeError(f"Smoke checkpoint files are missing: {missing}")
        result = {
            "status": "PASS",
            "required_optimizer_updates": smoke_steps,
            "optimizer_updates": optimizer_updates,
            "attempts": len(attempt_logs),
            "final_step": trainer.step,
            "final_log_scale": getattr(trainer, "log_scale", None),
            "logs": _jsonable(attempt_logs),
            "checkpoints": checkpoint_paths,
            "cuda_max_memory_gib": torch.cuda.max_memory_allocated() / 1024**3,
        }
        print("SMOKE_RESULT=" + json.dumps(result, sort_keys=True), flush=True)

    if dist.is_initialized():
        dist.barrier()


def main(local_rank, cfg):
    rank = cfg.node_rank * cfg.num_gpus + local_rank
    world_size = cfg.num_nodes * cfg.num_gpus
    if world_size > 1:
        setup_dist(rank, local_rank, world_size, cfg.master_addr, cfg.master_port)

    setup_rng(rank)
    dataset = getattr(datasets, cfg.dataset.name)(cfg.data_dir, **cfg.dataset.args)
    model_dict = {
        name: getattr(models, model.name)(**model.args).cuda()
        for name, model in cfg.models.items()
    }

    if rank == 0:
        for name, backbone in model_dict.items():
            model_summary = get_model_summary(backbone)
            print(f"\nBackbone: {name}\n{model_summary}")
            with open(os.path.join(cfg.output_dir, f"{name}_model_summary.txt"), "w") as fp:
                fp.write(model_summary)

    trainer = getattr(trainers, cfg.trainer.name)(
        model_dict,
        dataset,
        **cfg.trainer.args,
        output_dir=cfg.output_dir,
        load_dir=cfg.load_dir,
        step=cfg.load_ckpt,
    )

    if cfg.tryrun:
        return
    if cfg.profile:
        trainer.profile()
    elif cfg.smoke_steps > 0:
        run_smoke(trainer, cfg.smoke_steps, cfg.smoke_max_attempts)
    else:
        trainer.run()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Experiment config file")
    parser.add_argument("--output_dir", required=True, help="Output directory")
    parser.add_argument("--load_dir", default="", help="Checkpoint directory; defaults to output_dir")
    parser.add_argument("--ckpt", default="latest", help="Checkpoint step to resume")
    parser.add_argument("--data_dir", default="./data/", help="Dataset root or comma-separated roots")
    parser.add_argument("--auto_retry", type=int, default=3, help="Number of retries on error")
    parser.add_argument("--tryrun", action="store_true", help="Initialize without training")
    parser.add_argument("--profile", action="store_true", help="Profile training")
    parser.add_argument("--smoke_steps", type=int, default=0, help="Run bounded steps without snapshots")
    parser.add_argument(
        "--smoke_max_attempts",
        type=int,
        default=0,
        help="Maximum training attempts used to obtain the requested smoke optimizer updates",
    )
    parser.add_argument("--num_nodes", type=int, default=1)
    parser.add_argument("--node_rank", type=int, default=0)
    parser.add_argument("--num_gpus", type=int, default=-1)
    parser.add_argument("--master_addr", default="localhost")
    parser.add_argument("--master_port", default="12345")
    return parser.parse_args()


if __name__ == "__main__":
    opt = parse_args()
    if opt.smoke_steps < 0:
        raise ValueError("--smoke_steps must be non-negative")
    if opt.smoke_max_attempts < 0:
        raise ValueError("--smoke_max_attempts must be non-negative")
    if opt.smoke_steps > 0:
        if opt.smoke_max_attempts == 0:
            opt.smoke_max_attempts = opt.smoke_steps
        if opt.smoke_max_attempts < opt.smoke_steps:
            raise ValueError("--smoke_max_attempts must be at least --smoke_steps")
    opt.load_dir = opt.load_dir if opt.load_dir else opt.output_dir
    opt.num_gpus = torch.cuda.device_count() if opt.num_gpus == -1 else opt.num_gpus

    with open(opt.config) as fp:
        config = json.load(fp)
    cfg = edict()
    cfg.update(opt.__dict__)
    cfg.update(config)
    print("\nConfig:\n" + "=" * 80)
    print(json.dumps(cfg.__dict__, indent=4))

    if cfg.node_rank == 0:
        os.makedirs(cfg.output_dir, exist_ok=True)
        with open(os.path.join(cfg.output_dir, "command.txt"), "w") as fp:
            fp.write(" ".join(["python"] + sys.argv) + "\n")
        with open(os.path.join(cfg.output_dir, "config.json"), "w") as fp:
            json.dump(config, fp, indent=4)

    if cfg.auto_retry == 0:
        cfg = find_ckpt(cfg)
        if cfg.num_gpus > 1:
            mp.spawn(main, args=(cfg,), nprocs=cfg.num_gpus, join=True)
        else:
            main(0, cfg)
    else:
        for retry in range(cfg.auto_retry):
            try:
                cfg = find_ckpt(cfg)
                if cfg.num_gpus > 1:
                    mp.spawn(main, args=(cfg,), nprocs=cfg.num_gpus, join=True)
                else:
                    main(0, cfg)
                break
            except Exception as exc:
                print(f"Error: {exc}")
                print(f"Retrying ({retry + 1}/{cfg.auto_retry})...")
                if retry + 1 == cfg.auto_retry:
                    raise
