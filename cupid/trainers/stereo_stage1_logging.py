"""T integration adapter for L's single callback protocol."""
import json
import math
import os
import subprocess
from pathlib import Path

from ..stereo_observability.logger import logger_factory


class Stage1LoggingAdapter:
    def __init__(self, config, output_dir, rank):
        self.rank = rank
        self.writer = self.run = None
        self.config = config
        if rank != 0:
            return
        identity = dict(experiment_id=config["experiment_id"], attempt_id=Path(output_dir).name,
            git_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            git_tree=subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
            slurm_job_id=os.environ["SLURM_JOB_ID"])
        tracking = config["logging"]
        if tracking.get("tensorboard", True):
            from torch.utils.tensorboard import SummaryWriter
            self.writer = SummaryWriter(str(Path(output_dir) / "tensorboard"))
        mode = tracking.get("wandb_mode", "disabled")
        if mode not in ("disabled", "offline", "online"):
            raise ValueError("Invalid W&B mode")
        if mode != "disabled":
            import wandb
            self.run = wandb.init(project=tracking["wandb_project"], entity=tracking.get("wandb_entity"),
                name=identity["attempt_id"], mode=mode, dir=str(output_dir),
                config={"identity": identity, "training": config}, resume="never")
        self.callback = logger_factory({"identity": identity, "writer": self.writer,
                                       "wandb_run": self.run}, output_dir, rank)
        with open(Path(output_dir) / "tracking_receipt.json", "x") as handle:
            json.dump({"identity": identity, "mode": mode,
                "run_id": self.run.id if self.run else None,
                "run_url": self.run.url if self.run and mode == "online" else None,
                "server_readback": "UNVERIFIED"}, handle, indent=2)

    def __call__(self, event, step, payload):
        if self.rank != 0:
            return
        if event in ("train", "validation"):
            split = "train" if event == "train" else "validation"
            metrics = payload["metrics"]
            prefix = split + "/"
            self.callback("loss", step, dict(split=split, total=metrics[prefix + "loss_total"],
                components={k[len(prefix):]: v for k, v in metrics.items() if k != prefix + "loss_total"},
                epoch=payload.get("epoch"), learning_rates=[payload["lr"]] if "lr" in payload else None,
                num_samples=payload.get("global_valid_pairs", payload.get("evaluated_pairs"))))
            if event == "train":
                self.callback("optimizer", step, dict(applied=True, grad_norm=payload["grad_norm"],
                    amp_log_scale=math.log2(payload["amp_scale"]), amp_scale=payload["amp_scale"],
                    reason="grad_norm_measured_after_unscale_before_clipping"))
        elif event == "checkpoint":
            self.callback("checkpoint", step, dict(path=payload["path"], status="WRITTEN", sha256=payload["sha256"]))
        elif event == "evaluation":
            self.callback("evaluation", step, payload)
        elif event == "start":
            self.callback("status", step, dict(metric="test/loss_total", status="UNVERIFIED",
                                               reason="held_out_test_not_executed_by_training_loop"))
            if not self.config.get("eval_factory"):
                for name in ("rotation_error_deg", "translation_direction_error_deg", "translation_norm", "scale"):
                    self.callback("status", step, dict(metric="validation/pose/" + name,
                        status="UNVERIFIED", reason="pose_sampling_evaluator_not_bound"))
        elif event in ("complete", "bounded_stop"):
            self.close()

    def close(self):
        if self.run is not None:
            self.run.finish()
            self.run = None
        if self.writer is not None:
            self.writer.close()
            self.writer = None


def stage1_logger_factory(config, output_dir, rank):
    return Stage1LoggingAdapter(config, output_dir, rank)
