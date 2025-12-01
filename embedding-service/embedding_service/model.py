import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Optional

import torch
import timm
from PIL import Image
from timm.data import create_transform, resolve_model_data_config


logger = logging.getLogger(__name__)


@dataclass
class ModelBundle:
    model: torch.nn.Module
    transform: Callable[[Image.Image], torch.Tensor]
    device: torch.device
    name: str
    dimension: int


_MODEL_BUNDLE: Optional[ModelBundle] = None


def ensure_device(device_name: str) -> torch.device:
    device = torch.device(device_name)
    if device.type != "cuda":
        raise RuntimeError("CUDA device is required for embeddings")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA device is not available")
    return device


def _resolve_dimension(model: torch.nn.Module, device: torch.device, input_size: tuple[int, int, int]) -> int:
    if hasattr(model, "num_features"):
        num_features = getattr(model, "num_features")
        if isinstance(num_features, int) and num_features > 0:
            return num_features

    dummy = torch.zeros((1, input_size[0], input_size[1], input_size[2]), device=device)
    with torch.no_grad():
        output = model(dummy)
    return int(output.shape[-1])


def _build_model(model_name: str, device: torch.device) -> ModelBundle:
    name = _normalize_model_name(model_name)
    model = timm.create_model(name, pretrained=True, num_classes=0, global_pool="token")
    model.eval()
    model.to(device)

    data_config = resolve_model_data_config(model)
    transform = create_transform(**data_config, is_training=False)
    input_size = data_config.get("input_size", (3, 224, 224))
    dimension = _resolve_dimension(model, device, input_size)

    return ModelBundle(
        model=model,
        transform=transform,
        device=device,
        name=name,
        dimension=dimension,
    )


def _normalize_model_name(model_name: str) -> str:
    aliases = {
        "dinov2_vitb14": "vit_base_patch14_dinov2",
        "dinov2-vitb14": "vit_base_patch14_dinov2",
    }
    return aliases.get(model_name, model_name)


async def load_model(model_name: str, device_name: str) -> ModelBundle:
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE is not None:
        return _MODEL_BUNDLE

    device = ensure_device(device_name)
    bundle = await asyncio.to_thread(_build_model, model_name, device)
    _MODEL_BUNDLE = bundle
    logger.info(
        "Loaded embedding model",
        extra={
            "event": "embedding.model.loaded",
            "model_name": bundle.name,
            "device": bundle.device.type,
            "dimension": bundle.dimension,
        },
    )
    return bundle


def get_model_bundle() -> ModelBundle:
    if _MODEL_BUNDLE is None:
        raise RuntimeError("Embedding model is not loaded")
    return _MODEL_BUNDLE


async def generate_embedding(image: Image.Image) -> list[float]:
    bundle = get_model_bundle()

    def _forward() -> list[float]:
        tensor = bundle.transform(image).unsqueeze(0).to(bundle.device)
        with torch.no_grad():
            output = bundle.model(tensor)
            if isinstance(output, (tuple, list)):
                output = output[0]
            vector = output.squeeze(0).detach().cpu().float().tolist()
        return vector

    return await asyncio.to_thread(_forward)
