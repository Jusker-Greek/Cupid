"""T integration adapter for L's single callback protocol."""
import json
import math
import os
import subprocess
from pathlib import Path

from ..stereo_observability.logger import logger_factory
from ..stereo_observability.metrics import METRICS


class Stage1LoggingAdapter:
    def __init__(self, config, output_dir, rank):
        self.rank = rank
        self.writer = self.run = None
        self.transport_errors = (ConnectionError, TimeoutError)
        self.output = Path(output_dir)
        self.last_step = 0
        self.config = config
        if rank != 0:
            return
        identity = dict(experiment_id=config["experiment_id"], attempt_id=Path(output_dir).name,
            git_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            git_tree=subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
            slurm_job_id=os.environ["SLURM_JOB_ID"])
        tracking = config["logging"]
        # Establish the durable local sink before any optional tracker operation.
        self.callback = logger_factory({"identity": identity}, output_dir, rank)
        if tracking.get("tensorboard", True):
            from torch.utils.tensorboard import SummaryWriter
            self.writer = SummaryWriter(str(Path(output_dir) / "tensorboard"))
            self.callback.writer = self.writer
        mode = tracking.get("wandb_mode", "disabled")
        if mode not in ("disabled", "offline", "online"):
            raise ValueError("Invalid W&B mode")
        self.receipt = {"identity": identity, "mode": mode,
            "entity": tracking.get("wandb_entity"), "project": tracking.get("wandb_project"),
            "id": None, "run_id": None, "run_url": None,
            "initialization": "NOT_STARTED" if mode != "disabled" else "DISABLED",
            "finish": "NOT_STARTED", "server_readback": "UNVERIFIED"}
        self._write_receipt()
        try:
            if mode != "disabled":
                import wandb
                from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout
                self.transport_errors += (wandb.errors.CommError, RequestsConnectionError, Timeout)
                self.receipt["initialization"] = "FAILED"
                try:
                    self.run = wandb.init(project=tracking["wandb_project"], entity=tracking.get("wandb_entity"),
                        name=identity["attempt_id"], mode=mode, dir=str(output_dir),
                        config={"identity": identity, "training": config}, resume="never")
                except self.transport_errors as error:
                    self.receipt["initialization"] = "UNVERIFIED"
                    self._tracker_failure("initialization", error)
                if self.run is not None:
                    self.callback.wandb_run = self.run
                    self.receipt.update(entity=self.run.entity, project=self.run.project,
                        id=self.run.id, run_id=self.run.id,
                        run_url=self.run.url if mode == "online" else None, initialization="INITIALIZED")
        except Exception:
            # Cleanup only: dependency/configuration/programming errors still fail.
            try:
                if self.writer is not None:
                    self.writer.close()
            finally:
                self.writer = self.callback.writer = None
            raise
        finally:
            self._write_receipt()

    def _write_receipt(self):
        path = self.output / "tracking_receipt.json"
        temporary = self.output / "tracking_receipt.json.partial"
        with temporary.open("w") as handle:
            json.dump(self.receipt, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    def _tracker_failure(self, phase, error):
        # Persist types only; exception text can contain transport credentials.
        with (self.output / "tracking_failures.jsonl").open("a") as handle:
            handle.write(json.dumps({"phase": phase, "error_type": type(error).__name__,
                                     "status": "UNVERIFIED", "step": self.last_step}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.callback("status", self.last_step, dict(metric="tracking/" + phase,
            status="UNVERIFIED", reason="transport_failure_" + type(error).__name__))

    def _missing_pose(self, step, reason):
        for name in METRICS:
            self.callback("status", step, dict(metric="validation/pose/" + name,
                                               status="UNVERIFIED", reason=reason))

    def __call__(self, event, step, payload):
        if self.rank != 0:
            return
        self.last_step = step
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
        elif event == "evaluation_status":
            self._missing_pose(step, payload.get("reason", "raw_prediction_manifest_unavailable"))
        elif event == "amp_overflow":
            self.callback("optimizer", step, dict(applied=False, grad_norm=None,
                amp_scale=payload["new_scale"], amp_log_scale=math.log2(payload["new_scale"]),
                reason="nonfinite_gradient_retry_same_batch_with_lower_amp_scale"))
        elif event == "start":
            self.callback("status", step, dict(metric="test/loss_total", status="UNVERIFIED",
                                               reason="held_out_test_not_executed_by_training_loop"))
            if not self.config.get("eval_factory") or not self.config.get("prediction_factory"):
                self._missing_pose(step, "pose_sampling_evaluator_not_bound")
        elif event in ("complete", "bounded_stop"):
            self.close()

    def close(self):
        if self.rank != 0:
            return
        run, self.run = self.run, None
        self.callback.wandb_run = None
        try:
            if run is not None:
                self.receipt["finish"] = "FAILED"
                try:
                    run.finish()
                except self.transport_errors as error:
                    self.receipt["finish"] = "UNVERIFIED"
                    self._tracker_failure("finish", error)
                else:
                    self.receipt["finish"] = "FINISHED_PENDING_SERVER_READBACK"
        finally:
            try:
                if self.writer is not None:
                    self.writer.close()
            finally:
                self.writer = self.callback.writer = None
                self._write_receipt()


def stage1_logger_factory(config, output_dir, rank):
    return Stage1LoggingAdapter(config, output_dir, rank)
