from __future__ import annotations


def _models(cfg: dict):
    return (
        cfg["model"]["unet"],
        cfg["model"]["clip"],
        cfg["model"]["vae"],
    )


def text_to_image(prompt: str, seed: int, cfg: dict, filename_prefix: str) -> dict:
    unet, clip, vae = _models(cfg)
    width = int(cfg["image"]["width"])
    height = int(cfg["image"]["height"])
    steps = int(cfg["generation"]["steps"])

    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": clip, "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "cfg": 1.0}},
        "7": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "9": {"class_type": "Flux2Scheduler", "inputs": {"steps": steps, "width": width, "height": height}},
        "10": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["7", 0], "guider": ["6", 0], "sampler": ["8", 0],
            "sigmas": ["9", 0], "latent_image": ["10", 0],
        }},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"filename_prefix": filename_prefix, "images": ["12", 0]}},
    }


def image_edit(prompt: str, seed: int, cfg: dict, filename_prefix: str, uploaded_image_name: str) -> dict:
    unet, clip, vae = _models(cfg)
    width = int(cfg["image"]["width"])
    height = int(cfg["image"]["height"])
    steps = int(cfg["generation"]["steps"])

    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": clip, "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "4": {"class_type": "LoadImage", "inputs": {"image": uploaded_image_name}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "7": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["3", 0]}},
        "8": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": ["7", 0]}},
        "9": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["6", 0], "latent": ["7", 0]}},
        "10": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["8", 0], "negative": ["9", 0], "cfg": 1.0}},
        "11": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "12": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "13": {"class_type": "Flux2Scheduler", "inputs": {"steps": steps, "width": width, "height": height}},
        "14": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "15": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["11", 0], "guider": ["10", 0], "sampler": ["12", 0],
            "sigmas": ["13", 0], "latent_image": ["14", 0],
        }},
        "16": {"class_type": "VAEDecode", "inputs": {"samples": ["15", 0], "vae": ["3", 0]}},
        "17": {"class_type": "SaveImage", "inputs": {"filename_prefix": filename_prefix, "images": ["16", 0]}},
    }
