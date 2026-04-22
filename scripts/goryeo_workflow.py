#!/usr/bin/env python3
"""Goryeo Costume Reference Image Workflow"""
import sys
import os
os.environ['POSIXLY_CORRECT'] = '1'

import torch
from PIL import Image

KOREAN_SD15_ID = "Bingsu/my-korean-stable-diffusion-v1-5"

KOREAN_COSTUME_TERMS = [
    "고려 복식 Goryeo costume",
    "Korean court dress royal attire",
    "관모 hat crown traditional",
    "품대 sash belt",
    "각대 headgear gat",
    "chima jeogori",
    "수월관음 Water-Moon Avalokitesvara Buddhist"
]

NEGATIVE_PROMPT = "Chinese hanfu Song Chinese Ming Yuan Mongol Japanese kimono anime modern wrong costume generic Asian"

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Goryeo reference img2img")
    parser.add_argument("--reference", "-r")
    parser.add_argument("--prompt", "-p")
    parser.add_argument("--strength", "-s", type=float, default=0.6)
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--guidance", type=float, default=7.5)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", "-o")
    parser.add_argument("--list-models", action="store_true")

    args = parser.parse_args()

    if args.list_models:
        print("Cached models:")
        print(f"  {KOREAN_SD15_ID}")
        return 0

    if not args.reference or not args.prompt:
        print("Error: --reference and --prompt are required")
        parser.print_help()
        return 1

    ref_path = args.reference
    prompt = args.prompt

    if not os.path.exists(ref_path):
        print(f"Reference not found: {ref_path}")
        return 1

    print(f"Loading reference: {ref_path}")
    img = Image.open(ref_path).convert("RGB")
    print(f"  size: {img.size}")

    print(f"Loading Korean SD 1.5 from cache...")
    from diffusers import StableDiffusionImg2ImgPipeline
    pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
        KOREAN_SD15_ID,
        torch_dtype=torch.float16,
    )
    pipeline = pipeline.to("mps", torch.float16)
    print("Pipeline ready.")

    combined = f"{prompt}, {', '.join(KOREAN_COSTUME_TERMS)}"
    print(f"Prompt: {combined[:100]}...")

    gen = torch.Generator(device="mps")
    if args.seed:
        gen.manual_seed(args.seed)
        print(f"Seed: {args.seed}")

    print(f"Generating (strength={args.strength}, steps={args.steps}, cfg={args.guidance})...")

    out = pipeline(
        prompt=combined,
        image=img,
        negative_prompt=NEGATIVE_PROMPT,
        strength=args.strength,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        generator=gen,
        height=512,
        width=512,
    )

    if args.output:
        out.images[0].save(args.output)
        print(f"Saved: {args.output}")

    return 0

if __name__ == "__main__":
    sys.exit(main())