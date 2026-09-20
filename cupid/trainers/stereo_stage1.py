"""Independent Stage1 engine. Execute only inside a Slurm compute allocation.

No implicit downloads, no legacy HSSD resume, no automatic GPU submission.
Public factories/callbacks are documented in lanes/T_INTERFACE.md.
"""
import hashlib
import importlib
import json
import math
import os
import random
import subprocess
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel
from torch.utils.data import DataLoader, Dataset

from .stereo_stage1_objective import OfficialTargetAdapter, SharedStereoFlow, SupervisedSUVFlowMatching

EXPERIMENT_ID = "STEREO_CUPID_STAGE1_TRAIN_V1"
FORMAT = "STEREO_STAGE1_CHECKPOINT_V1"


def resolve(name):
    module, attribute = name.split(":", 1)
    return getattr(importlib.import_module(module), attribute)


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(4 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def rng_state():
    return {"python": random.getstate(), "numpy": np.random.get_state(),
            "torch": torch.get_rng_state(), "cuda": torch.cuda.get_rng_state_all()}


def restore_rng(state):
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"])
    torch.cuda.set_rng_state_all(state["cuda"])


def model_digest(model):
    """Byte-exact replica/update evidence, computed only at checkpoint boundaries."""
    hasher = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        value = value.detach().contiguous().cpu()
        hasher.update(name.encode())
        hasher.update(str((tuple(value.shape), value.dtype)).encode())
        hasher.update(value.reshape(-1).view(torch.uint8).numpy().tobytes())
    return hasher.hexdigest()


class ExactPairDataset(Dataset):
    """Deterministic map-style samples; zero-weight padding never drops pairs."""
    def __init__(self, source, seed, epoch):
        self.source, self.seed, self.epoch = source, seed, epoch

    def __len__(self):
        return len(self.source)

    def __getitem__(self, key):
        index, weight = key
        # Dataset transforms must use CPU RNGs, not launch CUDA work.
        py_state, np_state, th_state = random.getstate(), np.random.get_state(), torch.get_rng_state()
        sample_seed = self.seed + self.epoch * len(self) + index
        try:
            random.seed(sample_seed)
            np.random.seed(sample_seed % (2**32))
            torch.random.default_generator.manual_seed(sample_seed)
            item = dict(self.source[index])
        finally:
            random.setstate(py_state)
            np.random.set_state(np_state)
            torch.set_rng_state(th_state)
        if "_pair_weight" in item:
            raise ValueError("Reserved engine key _pair_weight")
        item["_pair_weight"] = torch.tensor(float(weight), dtype=torch.float32)
        return item


class ExactBatchSampler:
    def __init__(self, size, local_batch, rank, world, seed, epoch, start=0, shuffle=True):
        self.size, self.local_batch, self.rank, self.world = size, local_batch, rank, world
        self.seed, self.epoch, self.start, self.shuffle = seed, epoch, start, shuffle
        self.total = math.ceil(size / (local_batch * world))
        if size <= 0 or not 0 <= start <= self.total:
            raise ValueError("Empty dataset or invalid sampler cursor")

    def __len__(self):
        return self.total - self.start

    def __iter__(self):
        gen = torch.Generator().manual_seed(self.seed + self.epoch)
        order = torch.randperm(self.size, generator=gen).tolist() if self.shuffle else list(range(self.size))
        gb = self.local_batch * self.world
        for batch in range(self.start, self.total):
            offset = batch * gb + self.rank * self.local_batch
            yield [(order[pos % self.size], int(pos < self.size))
                   for pos in range(offset, offset + self.local_batch)]


def load_asset(spec, device, *, flow=False):
    from .. import models
    from safetensors.torch import load_file
    stem = Path(spec["path"]).resolve(strict=False)
    for suffix, hash_key in ((".json", "config_sha256"), (".safetensors", "sha256")):
        path = Path(str(stem) + suffix)
        if not path.is_file() or digest(path) != spec[hash_key]:
            raise ValueError(f"Missing or mismatched official asset: {path}")
    with open(str(stem) + ".json") as handle:
        definition = json.load(handle)
    kwargs = dict(definition["args"])
    if flow:
        if definition["name"] != "SparseStructureFlowModel" or kwargs["in_channels"] != 16:
            raise ValueError("Initialization requires the official joint SS+UV flow, not occupancy-only flow")
        kwargs.update(use_fp16=False, use_checkpoint=True)
    model = getattr(models, definition["name"])(**kwargs)
    model.load_state_dict(load_file(str(stem) + ".safetensors"), strict=True)
    return model.to(device)


class StereoStage1Trainer:
    def __init__(self, config, output_dir, resume=None):
        self.config, self.output = config, Path(output_dir)
        self.rank, self.world = dist.get_rank(), dist.get_world_size()
        self.device = torch.device("cuda", int(os.environ.get("LOCAL_RANK", "0")))
        if config["experiment_id"] != EXPERIMENT_ID:
            raise ValueError("Training must have its independent Stage1 identity")
        if config["precision"] not in ("fp16", "bf16", "fp32"):
            raise ValueError("Unsupported precision")
        if config["expected_world_size"] != self.world:
            raise ValueError("World size differs from frozen configuration")
        self.local_batch = int(config["pairs_per_rank"])
        if self.local_batch < 1 or config["eval_every"] < 1 or config["save_every"] < 1:
            raise ValueError("Batch size, eval/save intervals must be positive")
        self.dtype = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}[config["precision"]]
        self.step, self.epoch, self.batch_index = 0, 0, 0
        self.logger, self.eval_hook, self.prediction_hook = None, None, None
        self.rank0(lambda: self.output.mkdir(parents=True, exist_ok=False))
        seed_all(config["seed"] + self.rank)
        pack = resolve(config["data_factory"])(config["data"])
        self.train_data, self.val_data = pack["train"], pack["validation"]
        self.collate = pack.get("collate_fn")
        self.data_identity = pack["identity"]
        if not len(self.train_data) or not len(self.val_data):
            raise ValueError("Training and validation splits must both be nonempty")
        # Exact identity includes dataset/split/target hashes supplied by D.
        self.contract = {"config": config, "data_identity": self.data_identity,
                         "train_pairs": len(self.train_data), "validation_pairs": len(self.val_data)}
        self.contract_hash = hashlib.sha256(json.dumps(self.contract, sort_keys=True).encode()).hexdigest()
        hashes = [None] * self.world
        dist.all_gather_object(hashes, self.contract_hash)
        if len(set(hashes)) != 1:
            raise ValueError("Rank dataset/config identities disagree")
        self.steps_per_epoch = math.ceil(len(self.train_data) / (self.local_batch * self.world))
        budget = config["budget"]
        if set(budget) == {"epochs"}:
            self.max_steps = int(budget["epochs"]) * self.steps_per_epoch
        elif set(budget) == {"updates"}:
            self.max_steps = int(budget["updates"])
        else:
            raise ValueError("Budget must specify exactly epochs or updates")
        if self.max_steps < 1:
            raise ValueError("Empty training budget")
        flow = load_asset(config["pretrained_init"], self.device, flow=True)
        # FP32 optimizer/master parameters; AMP executes attention at configured dtype.
        flow.float()
        flow.dtype = self.dtype
        self.bare_model = SharedStereoFlow(flow)
        self.model = DistributedDataParallel(self.bare_model, device_ids=[self.device.index],
                                             broadcast_buffers=False, find_unused_parameters=False)
        decay, no_decay = [], []
        for name, parameter in self.bare_model.named_parameters():
            (no_decay if parameter.ndim <= 1 or name.endswith(".bias") else decay).append(parameter)
        self.optimizer = torch.optim.AdamW([
            {"params": decay}, {"params": no_decay, "weight_decay": 0.0}], **config["optimizer"])
        self.scheduler = torch.optim.lr_scheduler.LambdaLR(self.optimizer, lambda _: 1.0)
        self.scaler = torch.amp.GradScaler("cuda", enabled=config["precision"] == "fp16")
        objective = config["objective"]
        self.objective = (SupervisedSUVFlowMatching(**objective["args"]) if objective["name"] == "supervised_suv_fm"
                          else resolve(objective["factory"])(**objective["args"]))
        dino_spec = config["dino"]
        if digest(dino_spec["checkpoint"]) != dino_spec["sha256"]:
            raise ValueError("DINO checkpoint hash mismatch")
        dino = torch.hub.load(dino_spec["repo"], dino_spec["name"], source="local", pretrained=False)
        dino.load_state_dict(torch.load(dino_spec["checkpoint"], map_location="cpu", weights_only=True), strict=True)
        encoders = config.get("target_encoders", {})
        self.adapter = OfficialTargetAdapter(dino.to(self.device),
            load_asset(encoders["ss"], self.device) if "ss" in encoders else None,
            load_asset(encoders["uv"], self.device) if "uv" in encoders else None)
        self.rank0(self._init_hooks)
        if resume:
            self.load_checkpoint(resume)
        self.initial_model_sha256 = model_digest(self.bare_model)
        if self.step >= self.max_steps:
            raise ValueError("Resume already meets budget; refuse empty replacement run")
        self.emit("start", {**self.contract, "world_size": self.world,
            "global_pairs_per_update": self.local_batch * self.world,
            "steps_per_epoch": self.steps_per_epoch, "budget_updates": self.max_steps,
            "initialization_mode": "resume_optimizer" if resume else "pretrained_init",
            "resume_path": str(resume) if resume else None,
            "initial_model_sha256": self.initial_model_sha256,
            "git_commit": self.git("rev-parse", "HEAD"), "git_tree": self.git("rev-parse", "HEAD^{tree}"),
            "job_id": os.environ["SLURM_JOB_ID"], "contract_sha256": self.contract_hash})

    @staticmethod
    def git(*args):
        return subprocess.check_output(["git", *args], text=True).strip()

    def _init_hooks(self):
        for field, attr in (("logger_factory", "logger"), ("eval_factory", "eval_hook"),
                            ("prediction_factory", "prediction_hook")):
            if self.config.get(field):
                setattr(self, attr, resolve(self.config[field])(self.config, str(self.output), 0))

    def rank0(self, operation):
        result = [None]
        if self.rank == 0:
            try:
                operation()
            except Exception as error:
                result[0] = f"{type(error).__name__}: {error}"
        dist.broadcast_object_list(result, src=0)
        if result[0] is not None:
            raise RuntimeError(f"Rank-zero operation failed: {result[0]}")

    def emit(self, event, payload):
        def write():
            record = {"event": event, "step": self.step, "timestamp": time.time(), **payload}
            with open(self.output / "events.jsonl", "a", encoding="utf8") as handle:
                handle.write(json.dumps(record, allow_nan=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            if self.logger:
                self.logger(event, self.step, payload)
        state = rng_state()
        try:
            self.rank0(write)
        finally:
            # Logging must not perturb stochastic training or resume equivalence.
            restore_rng(state)

    def autocast(self):
        return torch.autocast("cuda", dtype=self.dtype, enabled=self.dtype != torch.float32)

    def loader(self, source, epoch, start=0, shuffle=True):
        sampler = ExactBatchSampler(len(source), self.local_batch, self.rank, self.world,
                                   self.config["seed"], epoch, start, shuffle)
        # No worker/prefetch cursor to lose on resume. Dataset augmentations seeded per index.
        return DataLoader(ExactPairDataset(source, self.config["seed"], epoch),
                          batch_sampler=sampler, num_workers=0, collate_fn=self.collate,
                          generator=torch.Generator().manual_seed(self.config["seed"] + epoch))

    def reduce_terms(self, terms, weights):
        names = sorted(terms)
        values = torch.stack([(terms[name].detach().double() * weights).sum() for name in names]
                             + [weights.double().sum()])
        dist.all_reduce(values)
        if not torch.isfinite(values).all() or values[-1] <= 0:
            raise ValueError("Nonfinite loss or empty global batch")
        return {name: (values[i] / values[-1]).item() for i, name in enumerate(names)}, values[-1]

    def validate(self):
        state = rng_state()
        was_training = self.bare_model.training
        try:
            seed_all(self.config["validation_seed"] + self.rank)
            self.bare_model.eval()
            sums, count = {}, 0.0
            with torch.no_grad():
                for raw in self.loader(self.val_data, 0, shuffle=False):
                    with self.autocast():
                        batch = self.adapter(raw, self.device)
                        terms = self.objective(self.bare_model, batch, training=False)
                    metrics, n = self.reduce_terms(terms, batch["_pair_weight"])
                    count += n.item()
                    for name, value in metrics.items():
                        sums[name] = sums.get(name, 0.0) + value * n.item()
            self.emit("validation", {"metrics": {"validation/" + k: v / count for k, v in sums.items()},
                                     "evaluated_pairs": int(count), "epoch": self.epoch})
            def evaluate():
                if self.eval_hook:
                    context = {"device": self.device, "config": self.config,
                               "data_identity": self.data_identity, "validation_dataset": self.val_data}
                    with torch.no_grad(), self.autocast():
                        if self.prediction_hook:
                            context["samples"] = self.prediction_hook(model=self.bare_model,
                                                                     step=self.step, context=context)
                        result = self.eval_hook(model=self.bare_model, step=self.step, context=context)
                    # Hook outputs go through the same local durable event stream.
                    with open(self.output / "evaluation.jsonl", "a") as handle:
                        handle.write(json.dumps({"step": self.step, "result": result}, allow_nan=False) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    if self.logger:
                        if context.get("samples") is not None:
                            self.logger("evaluation", self.step, {"split": "validation", "samples": context["samples"]})
                        else:
                            self.logger("evaluation_status", self.step, result)
            self.rank0(evaluate)
        finally:
            self.bare_model.train(was_training)
            restore_rng(state)

    def checkpoint(self):
        hashes = [None] * self.world
        dist.all_gather_object(hashes, model_digest(self.bare_model))
        if len(set(hashes)) != 1:
            raise ValueError("DDP model replicas differ at checkpoint boundary")
        states = [None] * self.world
        dist.all_gather_object(states, rng_state())
        path = self.output / f"step_{self.step:08d}.pt"
        file_hash = [None]
        def save():
            payload = {"format": FORMAT, "experiment_id": EXPERIMENT_ID,
                "model": self.bare_model.state_dict(), "optimizer": self.optimizer.state_dict(),
                "scheduler": self.scheduler.state_dict(), "scaler": self.scaler.state_dict(),
                "step": self.step, "sampler": {"epoch": self.epoch, "batch_index": self.batch_index},
                "rng_by_rank": states, "world_size": self.world,
                "model_sha256_by_rank": hashes,
                "contract": self.contract, "contract_sha256": self.contract_hash,
                "git_commit": self.git("rev-parse", "HEAD"), "git_tree": self.git("rev-parse", "HEAD^{tree}")}
            temporary = Path(str(path) + ".partial")
            with open(temporary, "xb") as handle:
                torch.save(payload, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, path)  # exclusive publication; never overwrite an attempt
            temporary.unlink()
            file_hash[0] = digest(path)
        self.rank0(save)
        dist.broadcast_object_list(file_hash, src=0)
        self.emit("checkpoint", {"path": str(path), "sha256": file_hash[0],
                                 "model_sha256_by_rank": hashes,
                                 "model_changed_since_init_or_resume": hashes[0] != self.initial_model_sha256,
                                 "epoch": self.epoch, "batch_index": self.batch_index})
        return path

    def load_checkpoint(self, path):
        # Trusted checkpoint produced by this engine; includes Python/NumPy RNG state.
        state = torch.load(path, map_location="cpu", weights_only=False)
        if state.get("format") != FORMAT or state.get("experiment_id") != EXPERIMENT_ID:
            raise ValueError("Not a Stereo Stage1 optimizer checkpoint; pretrained_init is separate")
        if state["contract_sha256"] != self.contract_hash or state["world_size"] != self.world:
            raise ValueError("Resume requires exact scientific/data/budget/topology contract")
        self.bare_model.load_state_dict(state["model"], strict=True)
        if model_digest(self.bare_model) != state["model_sha256_by_rank"][self.rank]:
            raise ValueError("Checkpoint model content hash mismatch")
        self.optimizer.load_state_dict(state["optimizer"])
        self.scheduler.load_state_dict(state["scheduler"])
        self.scaler.load_state_dict(state["scaler"])
        self.step = state["step"]
        self.epoch, self.batch_index = state["sampler"]["epoch"], state["sampler"]["batch_index"]
        if self.step != self.epoch * self.steps_per_epoch + self.batch_index:
            raise ValueError("Checkpoint step/sampler cursor mismatch")
        restore_rng(state["rng_by_rank"][self.rank])

    def update_batch(self, batch):
        state = rng_state()
        for numeric_attempt in range(16):
            # An AMP overflow is not an optimizer update. Retry identical targets,
            # noise, time and CFG mask with a lower numerical scale, on every rank.
            restore_rng(state)
            self.optimizer.zero_grad(set_to_none=True)
            with self.autocast():
                terms = self.objective(self.model, batch, training=True)
            weights = batch["_pair_weight"]
            metrics, denominator = self.reduce_terms(terms, weights)
            loss = (terms["loss_total"] * weights).sum() * self.world / denominator
            self.scaler.scale(loss).backward()
            self.scaler.unscale_(self.optimizer)
            norm = torch.nn.utils.clip_grad_norm_(self.bare_model.parameters(), self.config["grad_clip"])
            finite = torch.isfinite(norm).to(torch.int32)
            dist.all_reduce(finite, op=dist.ReduceOp.MIN)
            if finite.item():
                self.scaler.step(self.optimizer)
                self.scaler.update()
                return metrics, denominator, norm
            if not self.scaler.is_enabled():
                raise FloatingPointError("Nonfinite unscaled gradient; no optimizer update performed")
            old_scale = self.scaler.get_scale()
            self.scaler.update(new_scale=old_scale / 2)
            self.emit("amp_overflow", {"numeric_attempt": numeric_attempt + 1,
                                      "old_scale": old_scale, "new_scale": old_scale / 2,
                                      "optimizer_step_applied": False})
        raise FloatingPointError("AMP scale recovery exhausted; no optimizer update performed")

    def run(self, stop_after_updates=None):
        self.model.train()
        self.validate()
        started, start_step = time.monotonic(), self.step
        stop_step = self.max_steps if stop_after_updates is None else min(self.max_steps, self.step + stop_after_updates)
        if stop_step <= self.step:
            raise ValueError("stop_after_updates must be positive")
        while self.step < stop_step:
            if self.batch_index == self.steps_per_epoch:
                self.epoch += 1
                self.batch_index = 0
            for raw in self.loader(self.train_data, self.epoch, self.batch_index):
                with self.autocast():
                    batch = self.adapter(raw, self.device)
                metrics, denominator, norm = self.update_batch(batch)
                self.scheduler.step()
                self.step += 1
                self.batch_index += 1
                self.emit("train", {"metrics": {"train/" + k: v for k, v in metrics.items()},
                    "lr": self.optimizer.param_groups[0]["lr"], "grad_norm": norm.item(),
                    "amp_scale": self.scaler.get_scale(),
                    "epoch": self.epoch, "batch_index": self.batch_index,
                    "global_valid_pairs": int(denominator.item()),
                    "seconds_per_update": (time.monotonic() - started) / (self.step - start_step)})
                if self.step % self.config["eval_every"] == 0 or self.step == stop_step:
                    self.validate()
                if self.step % self.config["save_every"] == 0 or self.step == stop_step:
                    self.checkpoint()
                if self.step >= stop_step:
                    break
        self.emit("complete" if self.step == self.max_steps else "bounded_stop",
                  {"completed_updates": self.step, "evidence_eligibility": "ENGINEERING_ONLY_PENDING_EVALUATION"})


def run_training(config, output_dir, resume=None, stop_after_updates=None):
    if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("SLURMD_NODENAME"):
        raise RuntimeError("Use a Slurm compute node; local/login execution is forbidden")
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    torch.cuda.set_device(local_rank)
    # torchrun supplies rank/env even for a single GPU.
    dist.init_process_group("nccl", timeout=timedelta(minutes=10))
    try:
        trainer = StereoStage1Trainer(config, output_dir, resume)
        trainer.run(stop_after_updates)
    finally:
        dist.destroy_process_group()
