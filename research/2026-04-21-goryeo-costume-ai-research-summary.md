# Goryeo Costume AI Generation: Research Summary

**Date:** 2026-04-21

---

## Problem Statement

Open source image generation models (trained predominantly on Chinese data) consistently generate Song Chinese hanfu, Chinese hairstyles, and Chinese jewelry when asked for historically accurate Goryeo Korean costume — e.g., "Goryeo princess wearing yellow chima" always produces incorrect Chinese costume.

---

## Hillary Resources

| Resource | Specification |
|----------|---------------|
| Hardware | Apple M3 Ultra, 80 GPU cores, 512GB unified RAM |
| OS | macOS 26.3.1 |
| Python | 3.14.3 |
| ML Libraries | mlx, mlx-metal, torch, torchvision, transformers, diffusers |

MLX-native LoRA training is viable but slower than cloud NVIDIA (~$12/step vs ~$3/step on A100). For one-off training runs, it's acceptable.

---

## Deep Research Report Synthesis

The "deep-research-report goryeo chatgpt.md" (on fuchitalee at `/Users/fuchitalee/development/goryeo-model/research/`) establishes:

- **1218 Goryeo context** requires triangulation across: primary texts (especially *Goryeodogyeong*), excavated objects, slightly later Goryeo paintings (esp. Buddhist paintings), and filtered modern reconstructions.
- **Critical caution:** Do NOT back-project late 13th-14th century Yuan/Mongol-influenced styles into 1218. Late Goryeo visual material reflects later East Asian fashion exchange, not 1218 accuracy.
- **Best legal training candidates:** CC0/public-domain museum images from Met, Cleveland, Smithsonian. KBS VOD explicitly prohibits AI learning. NMK requires permission. KOGL Type 1 materials are clean.
- **Top source stack (ranked):** NMK Collection DB → Heritage Portal → NRICH → *Goryeodogyeong* → JKAA open-access scholarship → Met/Cleveland/Smithsonian CC0 holdings.
- **Licensing hierarchy:** CC0 (Met, Cleveland, Smithsonian) > KOGL Type 1 > Permission-based (NMK) > Prohibited (KBS VOD, DBpia, KISS unauthorized).
- **Workflow:** Build two separate corpora — (1) reference-viewing corpus for human note-taking, (2) training-eligible corpus limited to CC0/public domain + KOGL Type 1 + explicitly permitted materials.
- **Source vocabulary for costume/hair:** `고려 복식`, `고려 관복`, `고려 평복`, `고려 머리모양`, `고려 불화 복식`, `수월관음 복식`, `관모`, `품대`, `각대`, `경번갑`.

---

## Tooling Research

### MLX LoRA Training on Hillary (M3 Ultra)

| Tool | Status | Notes |
|------|--------|-------|
| mflux (filipstrand) | **Active development** — best choice | MLX-native diffusers port, supports Z-Image, FLUX.2, LoRA training |
| ai-toolkit (ostris) | Experimental Mac support | `run_mac.zsh` script, broad model support |
| Draw Things app | Works, GUI only | Easiest but not scriptable |
| mlx-examples SD | **Inference only, no training** | Apple official — only txt2img, no LoRA |
| apple mlx-examples lora | LLM only, not diffusion | LoRA training exists for LLMs only |

### Existing Korean Costume LoRAs on HuggingFace

| Model | Base | Verdict |
|-------|------|---------|
| seawolf2357/hanbok | FLUX.1-dev | Existing LoRAs are "horrible" per user |
| daeunn/hanbok-LoRA | SD 1.5 | Not usable |
| gdvstd/korean-style-sketch-sd3-lora | SD3 Medium | Not usable |

**Conclusion:** No existing pre-trained LoRA adequately solves the Chinese→Goryeo costume problem.

---

## Approach Analysis

### SDXL LoRA — Is It The Right Approach?

**Not necessarily.** The core issue is that SDXL's Chinese costume associations are baked into the U-Net at a fundamental level. LoRA on top only adds competing patterns — it cannot fully override strong existing associations.

| Problem | Why it matters |
|---------|---------------|
| Chinese visual associations baked into U-Net | LoRA competes with already-strong learned patterns, not replaces them |
| Dataset curation is the real bottleneck | 50 carefully curated + accurately captioned images > 500 sloppily scraped images |
| 1218 specificity risk | Late Goryeo paintings may teach Yuan-influenced styles that are wrong for 1218 |

### Alternatives Considered

| Option | Approach | Verdict |
|--------|----------|---------|
| **A — VLM fine-tune** | Fine-tune a smaller vision-language model (CLIP variant) to discriminate Korean vs Chinese costume | Good concept, more research needed on tooling |
| **B — Reference image approach** | Use verified Goryeo images (from Met/Cleveland CC0) as img2img/ControlNet reference + careful Korean vocabulary prompts | **Recommended first step** — zero training cost, tests baseline quickly |
| **C — LoRA + VLM critic** | Train SDXL LoRA + train a small VLM critic to score "Goryeo vs Chinese" for filtering | More complex, good for later iteration |
| **D — Knowledge distillation** | Use GPT-4V to generate accurate costume descriptions as training labels | Addresses caption accuracy problem |

---

## Recommended Path Forward

### Phase 1: Baseline Test (No Training Required)

1. **Build a reference library** from CC0 sources:
   - Met Open Access Goryeo holdings (Buddhist paintings, hair ornaments)
   - Cleveland Museum CC0 Goryeo celadon and burial objects
   - Smithsonian NMAA Goryeo Buddhist paintings

2. **Test img2img / IP-Adapter approach** on Hillary with SDXL:
   - Use historically verified Goryeo image as reference
   - Prompt with research report vocabulary: `고려 복식`, `관모`, `품대`, `각대`
   - Negative prompt: `Chinese hanfu, Song dynasty clothing, Yuan influence`

3. **Evaluate** how far reference-guided generation gets you before committing to training.

### Phase 2: Dataset Curation (The Real Work)

If Phase 1 is insufficient:

1. **Download CC0 public-domain images** from Met, Cleveland, Smithsonian — these are legally clean for training.
2. **Apply 5-axis scoring** from the deep research report:
   - Date fit (is it near 1218 or later Goryeo?)
   - Provenance (securely Goryeo or merely "Korean-looking"?)
   - Social rank (royal, aristocratic, monastic, military?)
   - Material directness (excavated object / contemporary text vs. later stylization)
   - Rights status (CC0/KOGL Type 1 only for training)
3. **Caption with Korean vocabulary** — `고려 복식`, `수월관음`, `관모`, `품대`, `각대` — paired with English for cross-language alignment.

### Phase 3: LoRA Training

If dataset is ready:

1. **Base model:** SDXL — most mature tooling, best for historical/realistic generation.
2. **Training:** mflux on Hillary (slower but functional) or cloud NVIDIA if speed matters.
3. **Captioning strategy:** Explicit "Korean Goryeo costume" not generic "hanbok" — override Chinese associations through precision.
4. **Negative training:** Include Chinese costume images with negative labels to actively suppress Chinese visual patterns.

---

## Key Vocabulary Reference

### Korean Terms for Costume/Hair

| Korean | English |
|--------|---------|
| `고려 복식` | Goryeo costume |
| `고려 관복` | Goryeo official dress |
| `고려 평복` | Goryeo civilian dress |
| `고려 머리모양` | Goryeo hairstyle |
| `수월관음 복식` | Water-Moon Avalokitesvara costume |
| `관모` | hat/crown |
| `품대` | sash/belt |
| `각대` | headgear |
| `경번갑` | armor belt |

### Search Queries (from deep research report)

```
site:museum.go.kr 고려 청자 향로
site:museum.go.kr 수월관음 고려 불화
site:heritage.go.kr 만월대 고려시대 도면
site:portal.nrich.go.kr 고려시대 성곽유적 자료집
site:db.history.go.kr 고려사 팔관회
site:encykorea.aks.ac.kr 백관복 품대 각대
site:uhpress.hawaii.edu Xu Jing Koryo
```

---

## Files Referenced

- Deep research source: `/Users/fuchitalee/development/goryeo-model/research/deep-research-report goryeo chatgpt.md`
- Hillary system: Apple M3 Ultra, 80 cores, 512GB RAM, macOS 26.3.1, Python 3.14.3
- ML libraries: mlx, mlx-metal, torch, torchvision, transformers, diffusers

---

*Generated: 2026-04-21*