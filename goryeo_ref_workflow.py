#!/usr/bin/env python3
"""
Goryeo Costume Reference Image Workflow
========================================
Phase 1 baseline test — use img2img with historically verified Goryeo
reference images to guide SDXL toward accurate Korean costume generation.

No training required. Tests whether reference-guided approach can fix
Chinese costume bias before committing to LoRA training.

Usage:
    python3 goryeo_ref_workflow.py --reference /path/to/ref.jpg --prompt "Goryeo princess"
"""

import argparse
import os
import sys
from pathlib import Path

import torch
from PIL import Image

# Use SDXL img2img pipeline (available in standard diffusers)
from diffusers import StableDiffusionXLImg2ImgPipeline, AutoencoderKL
from diffusers.models.normalization import FP32LayerNorm
from transformers import CLIPTextModel, CLIPTextModelWithProjection, CLIPVisionModelWithProjection
from transformers import AutoTokenizer, CLIPImageProcessor

# Model IDs — using stabilityai SDXL base
MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
VAE_ID = "stabilityai/sdxl-vae-fp16-fix"

# Korean costume vocabulary from deep research report
KOREAN_COSTUME_TERMS = [
    "고려 복식", "Goryeo costume", "Korean court dress",
    "관모", "hat/crown", "품대", "sash belt",
    "각대", "headgear", "chima", "jeogori",
    "수월관음", "Water-Moon Avalokitesvara costume"
]

# Negative prompt to avoid Chinese costume
NEGATIVE_PROMPT = """
Chinese hanfu, Chinese Song dynasty clothing, Yuan dynasty influence,
Ming dynasty costume, Japanese kimono, anime style, modern clothing,
incorrect Korean costume, generic Asian clothing
"""


def load_reference_image(path: str, size: int = 1024) -> Image.Image:
    """Load and preprocess reference image."""
    img = Image.open(path).convert("RGB")
    # Resize to reasonable size for img2img
    if max(img.size) > size:
        img.thumbnail((size, size), Image.LANCZOS)
    return img


def load_pipeline():
    """Load SDXL img2img pipeline."""
    print("Loading SDXL pipeline...")

    # Load text encoders
    text_encoder = CLIPTextModel.from_pretrained(
        MODEL_ID, subfolder="text_encoder", torch_dtype=torch.float16
    )
    text_encoder_2 = CLIPTextModelWithProjection.from_pretrained(
        MODEL_ID, subfolder="text_encoder_2", torch_dtype=torch.float16
    )

    # Load VAE
    vae = AutoencoderKL.from_pretrained(VAE_ID, torch_dtype=torch.float16)

    # Load image encoder for img2img guidance (not used directly but required)
    image_encoder = CLIPVisionModelWithProjection.from_pretrained(
        MODEL_ID, subfolder="image_encoder", torch_dtype=torch.float16
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, subfolder="tokenizer")
    tokenizer_2 = AutoTokenizer.from_pretrained(MODEL_ID, subfolder="tokenizer_2")
    image_processor = CLIPImageProcessor.from_pretrained(MODEL_ID, subfolder="image_encoder")

    # Load pipeline with img2img
    pipeline = StableDiffusionXLImg2ImgPipeline(
        vae=vae,
        text_encoder=text_encoder,
        text_encoder_2=text_encoder_2,
        tokenizer=tokenizer,
        tokenizer_2=tokenizer_2,
        image_encoder=image_encoder,
        image_processor=image_processor,
    )

    # Move to Metal (Apple Silicon)
    pipeline = pipeline.to("mps", torch.float16)
    print("Pipeline loaded on MPS (Apple Metal).")
    return pipeline


def generate(
    pipeline,
    reference_image: Image.Image,
    prompt: str,
    prompt_2: str = None,
    negative_prompt: str = NEGATIVE_PROMPT,
    strength: float = 0.6,
    num_inference_steps: int = 30,
    guidance_scale: float = 7.5,
    seed: int = None,
    output_path: str = None
):
    """Generate image using reference-guided img2img."""

    # Build the combined prompt with Korean vocabulary
    combined_prompt = f"{prompt}, {', '.join(KOREAN_COSTUME_TERMS[:6])}"
    prompt_2 = prompt_2 or combined_prompt

    generator = torch.Generator(device="mps")
    if seed is not None:
        generator.manual_seed(seed)

    print(f"Generating with prompt: {combined_prompt[:100]}...")
    print(f"Reference image size: {reference_image.size}, strength: {strength}")

    output = pipeline(
        prompt=combined_prompt,
        prompt_2=prompt_2,
        image=reference_image,
        negative_prompt=negative_prompt,
        strength=strength,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        generator=generator,
        height=1024,
        width=1024,
    )

    if output_path:
        output.images[0].save(output_path)
        print(f"Saved to: {output_path}")

    return output.images[0]


def main():
    parser = argparse.ArgumentParser(description="Goryeo costume reference image workflow")
    parser.add_argument("--reference", "-r", required=True, help="Path to reference image")
    parser.add_argument("--prompt", "-p", required=True, help="Main prompt describing the scene")
    parser.add_argument("--prompt-2", help="Secondary prompt (optional)")
    parser.add_argument("--strength", "-s", type=float, default=0.6,
                        help="img2img strength (0-1, lower = closer to reference)")
    parser.add_argument("--steps", type=int, default=30, help="Inference steps")
    parser.add_argument("--guidance", type=float, default=7.5, help="CFG scale")
    parser.add_argument("--seed", type=int, help="Random seed")
    parser.add_argument("--output", "-o", help="Output path")
    parser.add_argument("--list-models", action="store_true", help="List available models and exit")

    args = parser.parse_args()

    if args.list_models:
        print("Available approach: StableDiffusionXLImg2ImgPipeline")
        print(f"Default model: {MODEL_ID}")
        return

    # Load reference image
    if not os.path.exists(args.reference):
        print(f"Error: Reference image not found: {args.reference}")
        return 1

    reference = load_reference_image(args.reference)
    print(f"Loaded reference: {reference.size}")

    # Load pipeline
    pipeline = load_pipeline()

    # Generate
    output = generate(
        pipeline=pipeline,
        reference_image=reference,
        prompt=args.prompt,
        prompt_2=args.prompt_2,
        strength=args.strength,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        seed=args.seed,
        output_path=args.output
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())