import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5"))
import convnext_tiny_unet as definition
import series_5_a_sidewalkpilot_trainer as base
import series_5_c_sidewalkpilot_trainer as trainer


class ConvNeXtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def config(self):
        args = SimpleNamespace(**trainer.DEFAULTS, smoke=True, workers=0)
        return base.training_config(args, "fp32", model_definition=definition)

    def test_encoder_skip_shapes_and_full_resolution_output(self):
        model = definition.make_model("none").eval()
        image = torch.randn(1, 3, 65, 97)
        with torch.inference_mode():
            features = model.backbone(image)
            result = model(image)["out"]
        self.assertEqual([v.shape[1] for v in features], [96, 192, 384, 768])
        self.assertEqual([tuple(v.shape[-2:]) for v in features], [(16, 24), (8, 12), (4, 6), (2, 3)])
        self.assertEqual(tuple(result.shape), (1, 2, 65, 97))
        self.assertEqual(result.dtype, torch.float32)
        self.assertTrue(torch.isfinite(result).all())
        self.assertGreater(sum(p.numel() for p in model.parameters()), 27000000)

    def test_full_fp32_forward_and_backward_even_in_external_amp(self):
        model = definition.make_model("none").train()
        with torch.autocast("cpu", dtype=torch.bfloat16):
            result = model(torch.randn(2, 3, 64, 96))["out"]
        self.assertEqual(result.dtype, torch.float32)
        result.square().mean().backward()
        for module in (model.backbone, model.classifier):
            gradients = [p.grad for p in module.parameters() if p.grad is not None]
            self.assertTrue(gradients)
            self.assertTrue(all(g.dtype == torch.float32 and torch.isfinite(g).all() for g in gradients))
            self.assertTrue(all(p.dtype == torch.float32 for p in module.parameters()))
        self.assertFalse(torch.backends.cuda.matmul.allow_tf32)
        self.assertFalse(torch.backends.cudnn.allow_tf32)

    def test_reduced_precision_input_and_parameters_rejected(self):
        model = definition.make_model("none")
        with self.assertRaisesRegex(ValueError, "Input must be FP32"):
            model(torch.randn(1, 3, 32, 32).half())
        model.half()
        with self.assertRaisesRegex(ValueError, "parameters must remain FP32"):
            model(torch.randn(1, 3, 32, 32))

    def test_configuration_is_explicit_not_auto_or_mobile(self):
        cfg = self.config()
        self.assertEqual(cfg["architecture"], "convnext_tiny_unet")
        self.assertEqual(cfg["model_name"], "5.C")
        self.assertEqual(cfg["precision"], "fp32")
        self.assertEqual(cfg["backbone_weights"], "ConvNeXt_Tiny_Weights.IMAGENET1K_V1")
        self.assertFalse(cfg["precision_policy"]["autocast"])
        args = SimpleNamespace(**trainer.DEFAULTS, smoke=True, workers=0)
        for precision in ("auto", "fp16", "bf16"):
            with self.assertRaisesRegex(ValueError, "explicit fp32"):
                base.training_config(args, precision, model_definition=definition)

    def test_checkpoint_round_trip_and_cross_architecture_rejection(self):
        model = definition.make_model("none").eval()
        path = self.root / "best.pt"
        state = dict(schema="sidewalkpilot-series5-binary-checkpoint-v1", config=self.config(), model=model.state_dict())
        base.atomic_checkpoint(path, state)
        restored, _ = base.load_checkpoint(path, model_definition=definition)
        restored.eval()
        image = torch.randn(1, 3, 32, 64)
        with torch.inference_mode():
            torch.testing.assert_close(model(image)["out"], restored(image)["out"], rtol=0, atol=0)
        with self.assertRaisesRegex(ValueError, "supported Series 5"):
            base.load_checkpoint(path)
        name = next(iter(state["model"]))
        state["model"][name] = state["model"][name].half()
        base.atomic_checkpoint(path, state)
        with self.assertRaisesRegex(ValueError, "non-FP32"):
            base.load_checkpoint(path, model_definition=definition)

    def test_cli_rejects_fp16_and_bf16(self):
        for mode in ("fp16", "bf16", "auto"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                trainer.parser().parse_args(["predict", "--checkpoint", "dummy.pt", "--image", "a.jpg",
                                             "--output", "out", "--precision", mode])

    def test_full_training_refuses_unready_dataset(self):
        (self.root / "manifest.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "10,000-label"):
            trainer.run_training(SimpleNamespace(precision="fp32", smoke=False, dataset=self.root))

    def test_new_trainer_smoke_stores_fp32_model_gradients_and_optimizer(self):
        dataset = self.root / "data"
        dataset.mkdir()
        labels = np.zeros((32, 64), dtype=np.uint8)
        labels[:, 32:] = 1
        Image.fromarray(np.repeat(labels[:, :, None] * 255, 3, axis=2)).save(dataset / "source.jpg")
        Image.fromarray(labels).save(dataset / "mask.png")
        (dataset / "manifest.json").write_text("{}")
        (dataset / "split.json").write_text("{}")
        strong = dict(id="strong", image="source.jpg", mask="mask.png", supervision="binary-reference")
        weak = dict(id="weak", image="source.jpg", mask="mask.png", supervision="pseudo-binary")
        parts = dict(train=[strong] + [{**weak, "id": f"weak-{i}"} for i in range(5)],
                     validation=[strong], test=[])
        args = SimpleNamespace(**{**trainer.DEFAULTS, "weights": "none", "width": 64, "height": 32,
                    "dataset": dataset, "split": dataset / "split.json", "output": self.root / "smoke",
                    "device": "cpu", "workers": 0, "smoke": True, "resume": False, "wandb": False})
        with patch.object(trainer, "load_partition", return_value=parts), contextlib.redirect_stdout(io.StringIO()):
            trainer.run_training(args)
        model, state = base.load_checkpoint(args.output / "last.pt", model_definition=definition)
        self.assertEqual(state["config"]["architecture"], definition.ARCHITECTURE)
        self.assertEqual(state["config"]["precision"], "fp32")
        self.assertEqual(state["scaler"], {})
        self.assertTrue(all(p.dtype == torch.float32 for p in model.parameters()))
        for values in state["optimizer"]["state"].values():
            for value in values.values():
                if torch.is_tensor(value) and value.is_floating_point():
                    self.assertEqual(value.dtype, torch.float32)
        runtime = json.loads((args.output / "runtime.json").read_text())
        self.assertEqual(runtime["purpose"], "SMOKE TEST ONLY")


if __name__ == "__main__":
    unittest.main()
