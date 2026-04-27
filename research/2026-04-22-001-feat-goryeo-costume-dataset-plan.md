# Goryeo Costume AI Dataset: Text + Drama Reference Pipeline

**Target repo:** goryeo-model
**Status:** active
**Date:** 2026-04-22
**Augmented:** 2026-04-22 (video corpus processing section added)

---

## Overview

Build two complementary data pipelines to produce training data for historically accurate Goryeo Korean costume image generation:

1. **Scenario 1 (Text)**: Scholarly "design bible" describing Goryeo vs Song costume differences, translated into structured training captions for Stable Diffusion LoRA fine-tuning
2. **Scenario 2 (Drama)**: Extract reference images from historically accurate Korean sageuk dramas, categorized and curated for img2img reference use

These pipelines are independent and can run in parallel. Both feed into the same goal: generating historically accurate Goryeo costume imagery without Chinese (Song) costume drift.

## Context

This plan is grounded in prior research (see `research/2026-04-21-goryeo-costume-ai-research-summary.md`).

**Core problem**: Open-source image generation models trained predominantly on Chinese data default to Song dynasty hanfu, Chinese hairstyles, and Chinese jewelry when asked to generate Goryeo Korean costume (e.g., "Goryeo princess wearing yellow chima").

**Why museum CC0 images alone are insufficient**: Existing Met/Cleveland/Smithsonian downloads are too abstracted (Buddhist paintings, celadon bowls) — surviving Goryeo-era artwork depicts Buddha figures and royalty, not everyday court dress. Bridging from Buddhist robe to young princess's dress requires either scholarly text guidance or contemporary Korean drama reference.

**Private use context**: All work is for private use only. No IP concerns apply to reference extraction from owned drama content.

---

## Problem Frame

The model needs to learn Goryeo-specific visual patterns that are nearly absent from its training distribution. Available CC0 visual references are insufficient. Two paths forward exist:

| Path | Data Type | Advantage | Disadvantage |
|------|-----------|-----------|--------------|
| Scenario 1 | Scholarly text | Theoretically precise; triangulates from primary sources | Indirect — text describes, doesn't show |
| Scenario 2 | Drama reference images | Direct visual patterns; accurate Korean costume on real actors | Dramas mix in anachronisms; requires curation |

**Recommended approach**: Execute both in parallel. Scenario 2 provides faster iterations on image quality. Scenario 1 builds the scholarly foundation for caption quality and eventual LoRA training.

---

## Scope Boundaries

- **In scope**: Goryeo dynasty period (918–1392 CE), specifically late Goryeo (1170–1300) for drama references (closest to 1218 screenplay setting)
- **Out of scope**: Joseon dynasty costume (even though most available Korean dramas are Joseon-period); full LoRA training execution (pipeline setup only)
- **Private use only**: This pipeline produces reference data for private image generation. No distribution of copyrighted drama frames.

---

## Key Decisions

- **Primary drama target: 고려거란전쟁 (A-, KBS2 2023-24)** — highest-rated Goryeo costume accuracy; professor 임용한 ( history) consulted for period accuracy; academic praise for costume reconstruction; namu.wiki "역사 탐구" page documents historical accuracy analysis
- **Secondary drama: 무인시대 (B+, KBS1 2003-04)** — best early-2000s Goryeo accuracy; covers late Goryeo military regime period (1170–1219) — closest to 1218 screenplay setting
- **Caption format: weighted keyword syntax** — `(keyword:1.2)` emphasis in LoRA training, standard negative caption format for exclusions
- **Reference resolution: 768×768** — balances SDXL compatibility with portrait orientation of drama frames
- **img2img strength: 0.35–0.5** — preserves actor face + costume silhouette while allowing model creative interpretation
- **Video processing: 2160p HEVC source → transcode to ProRes proxy for extraction → extract frames/clips** — bypasses GPU decode bottleneck

---

## High-Level Technical Design (Existing Pipeline)

```
SCENARIO 1: Text Pipeline
=========================
Scholarly Sources (Goryeodogyeong, JKAA, KCI costume papers)
    → Manual text extraction
    → LLM processing (extract visual attributes)
    → Structured costume descriptions
    → Kohya SS weighted captions (train_data/captions/)
    → LoRA training dataset (future phase)

SCENARIO 2: Drama Reference Pipeline
===================================
Drama episodes (owned, private use)
    → Storage assessment (local vs network mount)
    → 2160p HEVC → ProRes 422 proxy (hw decode, no re-encode for ML)
    → ffmpeg frame extraction (timestamps from manual curation)
    → Categorization (character × costume type × scene type)
    → Reference image library (train_data/reference_library/)
    → img2img generation on Hillary (M3 Ultra)
    → Output curation → approved reference board
```

---

## Implementation Units

- [ ] **Unit 1: Scenario 1 — Compile Goryeo-Song Costume Scholarly Design Bible**

**Goal:** Produce a structured text document cataloging every known visual distinction between Goryeo and Song dynasty court costume, covering collar direction, waistline, hats, hair ornaments, colors, and fabric patterns.

**Requirements:** R1 (costume differentiation from Song), R2 (captionable visual attributes for training)

**Dependencies:** None

**Files:**
- Create: `research/goryeo-song-costume-design-bible.md`
- Create: `data/costume-text/goryeodogyeong-extracts.md`
- Create: `data/costume-text/korean-costume-terminology.md`
- Create: `data/costume-text/caption-vocabulary.md`

**Approach:**
1. Compile primary source extracts from Goryeodogyeong (Xu Jing 1123 account) describing Goryeo court dress — direct observer comparison of Goryeo vs Song
2. Translate Korean costume terminology: `치마`, `저고리`, `웃통`, `관모`, `품대`, `갓`, `경번갑`, `꽂外形`, `norigae`
3. For each garment element, write a structured visual description: color, fabric, cut, ornamentation, and the specific Goryeo-vs-Song differentiator
4. Format as a "design bible" with sections for each garment type and period-specific notes (early Goryeo vs late Goryeo, accounting for Yuan influence in 1200s)

**Test scenarios:**
- Happy path: Document covers ≥8 garment categories (collar, skirt, jacket, hat, belt, hair ornaments, jewelry, footwear)
- Edge case: Late Goryeo (1200s) Yuan-influenced elements are clearly labeled as post-1218
- Verification: Each Goryeo-specific claim is traceable to a named source (text citation, object citation, or "reconstructed from [period] cross-reference")

---

- [ ] **Unit 2: Scenario 1 — Produce Caption Templates for LoRA Training**

**Goal:** Convert the design bible into ready-to-use training captions using Stable Diffusion LoRA caption formats.

**Requirements:** R1 (differentiate from Song), R2 (precise visual captions)

**Dependencies:** Unit 1

**Files:**
- Create: `data/captions/goryeo-court-lady-captions.csv`
- Create: `data/captions/goryeo-court-lady-negatives.csv`
- Create: `data/captions/keyword-weights.md`

**Test scenarios:**
- Happy path: ≥20 caption variants covering ≥5 costume types (royal woman, court lady, civil official, military official, ceremonial)
- Edge case: Late Goryeo Yuan-influenced garments are explicitly labeled with date range
- Verification: Each caption includes at least one Goryeo-specific visual differentiator (collar direction, waist height, hat type) absent from Song convention

---

- [ ] **Unit 3: Scenario 2 — Set Up Drama Frame Extraction Pipeline**

**Goal:** Build automated ffmpeg-based frame extraction infrastructure on Hillary for processing drama episodes into reference images.

**Requirements:** R2 (direct visual references), R3 (Hillary M3 Ultra video processing)

**Dependencies:** None

**Files:**
- Create: `scripts/drama_extract_frames.py` — batch frame extraction from video
- Create: `scripts/drama_timestamp_manifest.csv` — master timestamp list per drama per episode
- Create: `scripts/validate_extracted_frames.py` — quality checks on extracted images

**Test scenarios:**
- Happy path: Extract ≥100 frames from one drama episode with zero corruption errors
- Edge case: Handle episodes with different codec (H.264 vs H.265 vs ProRes) without manual intervention
- Error path: Missing episode file → log error and continue batch, do not crash
- Verification: All outputs are valid PNG, ≥768×768, RGB

---

- [ ] **Unit 4: Scenario 2 — Compile and Rate Drama Source List**

**Goal:** Produce an exhaustive, graded list of Korean sageuk dramas set in the Goryeo period with historical accuracy ratings.

**Requirements:** R2 (accurate drama sources)

**Dependencies:** None

**Files:**
- Create: `research/sageuk-drama-accuracy-ratings.md`
- Modify: `README.md`

**Test scenarios:**
- Happy path: Document covers ≥14 dramas with grade, period, channel, and specific costume accuracy notes
- Verification: Each grade is traceable to named source

---

- [ ] **Unit 5: Scenario 2 — Categorize and Curate Reference Library**

**Goal:** Organize extracted drama frames into a structured reference library with metadata for img2img use.

**Requirements:** R2 (direct visual references), R3 (structured for img2img workflow)

**Dependencies:** Unit 3, Unit 4

**Files:**
- Create: `data/reference_library/{drama}/metadata.csv`
- Create: `data/reference_library/curated-reference-board.md`
- Create: `data/reference_library/costume-type-index.md`

**Test scenarios:**
- Happy path: ≥50 curated frames covering ≥5 costume types from Priority 1-2 dramas
- Edge case: 무인시대 frames with Hangul visible flagged as `anachronism-Hangul` rather than rejected

---

- [ ] **Unit 6: Scenario 2 — Integration Test with img2img Generation**

**Goal:** Validate the complete drama reference pipeline by running img2img generations on Hillary using extracted drama references.

**Requirements:** R2 (visually accurate outputs), R3 (generation on Hillary M3 Ultra)

**Dependencies:** Unit 5

**Files:**
- Create: `scripts/goryeo_drama_workflow.py`
- Create: `data/generation_tests/test_batch_001.md`

**Test scenarios:**
- Happy path: Generation using 고려거란전쟁 reference + weighted Goryeo caption produces distinctly Korean silhouette
- Verification: Each test batch documented with qualitative accuracy score (1–5)

---

## Requirements Trace

- **R1**: Costume imagery is visually distinguishable from Song Chinese costume — addressed by Units 1, 2 (text foundation) and Units 3–5 (visual references)
- **R2**: Reference images are directly usable for img2img generation on Hillary — addressed by Units 3, 5, 6
- **R3**: Pipeline runs on Hillary M3 Ultra (Apple Silicon) — addressed by Unit 3 (ffmpeg), Unit 6 (existing MPS-based workflow)

---

## System-Wide Impact

- **Drama frame storage**: Extracted frames at 768×768 PNG average ~500KB–2MB per frame. 500 frames ≈ 250MB–1GB. 5,000 frames ≈ 2.5–10GB. Allocate storage accordingly.
- **Caption library**: CSV format; minimal storage (~KB).
- **No external API dependencies**: Frame extraction uses local ffmpeg. No cloud APIs.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Drama frames are still historically mixed (Joseon elements in Goryeo drama) | Explicit curation per frame; accuracy notes in metadata; use only A- and B+ dramas as primary sources |
| Women's costume accuracy even in best dramas (B+) uses Joseon-style chima | Prioritize men's official/ceremonial frames for early training; flag women's frames as "requires verification" |
| Text design bible has gaps (no surviving Goryeo paintings of everyday court dress) | Label each garment claim with confidence level; use late-period Goryeo visual evidence triangulated from primary sources |
| Goryeo→Song drift returns at certain img2img strengths | Test multiple strengths (0.2–0.7); document threshold where drift returns |

---

## Dependencies / Prerequisites

1. **Owned drama episodes**: All frame extraction requires local access to episode video files.
2. **Korean costume expertise**: Human curation of drama frames requires Korean costume history knowledge.
3. **Python 3.14 package compatibility**: Test ffmpeg-python and PIL on Hillary.

---

## Success Metrics

- [ ] Design bible covers ≥8 garment categories with Goryeo-vs-Song visual differentiators
- [ ] Caption library contains ≥20 caption variants across ≥5 costume types
- [ ] ≥50 curated drama reference frames extracted and categorized
- [ ] img2img generation using drama reference + weighted caption produces Goryeo costume (not Song hanfu) in ≥70% of test cases
- [ ] Generation pipeline runs on Hillary M3 Ultra at ≤15 seconds per image at 512×512

---

## Sources & References

- **Research summary**: `research/2026-04-21-goryeo-costume-ai-research-summary.md`
- **Deep research report**: `research/deep-research-report goryeo chatgpt.md`
- **Graded drama ratings source**: KCI academic database, 나무위키 (namu.wiki) "역사 탐구" page, Daum news articles
- **Caption format reference**: Kohya SS documentation
- **Goryeo-Song costume scholarship**: JKAA, 고려거란전쟁 costume director 이석근 interviews
- **Korean costume terminology**: AKS EncyKorea / KOSTMA (encykorea.aks.ac.kr)

---

## File Manifest

```
goryeo-model/
├── research/
│   ├── 2026-04-21-goryeo-costume-ai-research-summary.md
│   ├── deep-research-report goryeo chatgpt.md
│   ├── sageuk-drama-accuracy-ratings.md
│   └── goryeo-song-costume-design-bible.md        # [NEW] Unit 1
├── data/
│   ├── costume-text/
│   │   ├── goryeodogyeong-extracts.md            # [NEW] Unit 1
│   │   ├── korean-costume-terminology.md          # [NEW] Unit 1
│   │   └── caption-vocabulary.md                  # [NEW] Unit 1
│   ├── captions/
│   │   ├── goryeo-court-lady-captions.csv        # [NEW] Unit 2
│   │   ├── goryeo-court-lady-negatives.csv       # [NEW] Unit 2
│   │   └── keyword-weights.md                    # [NEW] Unit 2
│   ├── reference_library/
│   │   └── (structured per drama per episode)   # [NEW] Units 3, 5
│   └── video-corpus/                              # [NEW] Section below
├── scripts/
│   ├── goryeo_workflow.py
│   ├── drama_extract_frames.py                   # [NEW] Unit 3
│   ├── validate_extracted_frames.py              # [NEW] Unit 3
│   ├── drama_timestamp_manifest.csv              # [NEW] Unit 3
│   ├── goryeo_drama_workflow.py                 # [NEW] Unit 6
│   └── video_processing/                         # [NEW] Section below
│       ├── transcode_to_proxy.py
│       ├── extract_stills.py
│       └── extract_clips.py
└── README.md
```

---

# PART 2: Large-Scale Video Corpus Processing (150GB / 32 Episodes)

## Context

The drama 고려거란전쟁 (Goryeo-Khitan War, KBS2 2023-24, Grade A-) exists as a 32-episode corpus totaling approximately **160GB** (32 × ~5GB) at **2160p (4K) HEVC (H.265)** resolution via Netflix Web-DL. The goal is to extract:

1. **Still frames** — individual PNG/JPEG images of costume moments, suitable for img2img reference
2. **Short video clips** — 1–5 second MP4 clips of costume movement (drapery, walking, bowing), useful for understanding how garments behave in motion and for video diffusion training
3. **Metadata** — timestamps, episode, character, costume type for every extracted asset

This section supersedes Unit 3's lightweight extraction approach and addresses the full pipeline from raw 4K HEVC → usable training assets on Hillary's M3 Ultra.

---

## Corpus Specifications

| Property | Value |
|----------|-------|
| Drama | 고려거란전쟁 (Goryeo-Khitan War) |
| Episodes | 32 (S01E01–S01E32) |
| Source resolution | 2160p (3840×2160) HEVC (H.265) Web-DL |
| Average episode size | ~5 GB |
| Total corpus size | ~160 GB |
| Format | MKV container |
| Frame rate | 23.976 fps (standard film NTSC) |
| Color space | BT.709 (SDR) |
| Available storage | Hillary: 5.2TB free on /dev/disk3s5 (Data volume) |

---

## Key Technical Decisions

### Decision 1: Proxy Workflow (4K HEVC → ProRes 422 Proxy)

**Decision:** Transcode all episodes to a **ProRes 422 Proxy** intermediate before frame extraction, rather than decoding 4K HEVC directly during extraction.

**Rationale:** HEVC decode on Apple Silicon via VideoToolbox is efficient, but 4K resolution is far beyond what's needed for costume reference extraction (768×768 or 1024×1024 target). Decoding at full 4K wastes I/O bandwidth and storage on frames that will be downscaled anyway. ProRes 422 Proxy:
- Is decoded natively via Apple's Media Engine (hardware-accelerated, ~3× faster than software HEVC decode)
- Preserves full color fidelity and sharp edges critical for costume texture
- Proxy at ~1GB/episode (vs 5GB HEVC) cuts storage for intermediate files to ~32GB

**Pipeline shape:**
```
[Episode N].mkv (4K HEVC, 5GB)
    → transcode_to_proxy.py (VideoToolbox hw decode + ProRes 422 Proxy encode)
    → [Episode N]_proxy.mov (~1GB, fast decode)
    → extract_stills.py / extract_clips.py (frame-accurate extraction from proxy)
```

### Decision 2: ProRes 422 Proxy (Not ProRes 422 LT or H.264)

**Decision:** Use **ProRes 422** (not 422 LT, not H.264) for the intermediate.

**Rationale:**
- ProRes 422: ~110 Mbps at 2160p24 ≈ 0.75 GB per 55-second clip → 1GB per episode at full length is conservative
- ProRes 422 LT: ~75 Mbps — smaller file but slightly lower quality for edge/detail extraction
- H.264 proxy: Wrong color space artifacts possible; more CPU-intensive to decode
- 422 maintains 4:2:2 chroma subsampling (vs 4:2:0 in H.264) — important for costume color accuracy

### Decision 3: Frame Storage as JPEG (Quality 95) + PNG (Lossless Detail)

**Decision:** Extract stills in **dual format**: JPEG at quality 95 for catalog browsing, PNG for a subset with exceptional costume detail.

**Rationale:**
- JPEG q=95 is visually lossless for costume color and most texture detail (SSIM > 0.99 vs PNG on photographic content)
- PNG lossless for detail close-ups (embroidery, fabric weave, jewelry)
- At 768×768, JPEG q=95 ≈ 150–300KB vs PNG ≈ 1–2MB — storage savings without quality loss for catalog
- Target extraction resolution: **768×768** (square crop from 16:9 source, centered on costume region)

### Decision 4: Extract Both Stills AND Short Clips

**Decision:** Extract both individual frames AND 1–5 second video clips.

**Rationale:**
- Stills: established img2img reference workflow (existing Unit 6)
- Clips: valuable for (a) training video diffusion models (future phase), (b) understanding garment motion/drapery, (c) comparing static vs in-motion costume behavior
- Extract clips at **720×720** (square), H.264, for manageable file size (~2–5MB per 3-second clip)
- Label clips with `[start_time]_[end_time]_[scene_description].mp4`

### Decision 5: All Processing on Hillary — No Cloud

**Decision:** Entire pipeline runs on Hillary (M3 Ultra, 512GB RAM, 5.2TB storage).

**Rationale:**
- No data leaves the machine (private content)
- M3 Ultra Media Engine provides excellent HEVC decode + ProRes encode throughput
- 512GB unified memory handles large batch buffers without swapping
- ffmpeg with VideoToolbox on macOS is the standard toolchain for this workflow

---

## Storage Architecture

```
/Users/admin/goryeo-model/video-corpus/
├── raw/                          # Original 4K HEVC episodes (160GB total)
│   ├── Korea-Khitan.War.S01E01.mkv   (5.4 GB)
│   ├── Korea-Khitan.War.S01E02.mkv   (5.1 GB)
│   └── ... (32 episodes)
├── proxies/                      # ProRes 422 Proxy intermediates (~32GB)
│   ├── S01E01_proxy.mov              (~1 GB)
│   ├── S01E02_proxy.mov              (~1 GB)
│   └── ...
├── stills/                       # Extracted still frames (~10–50GB at 768×768 JPEG+PNG)
│   ├── S01E01/
│   │   ├── S01E01_00-12-34_공주_궁중복_001.jpg   (JPEG q=95, ~200KB)
│   │   ├── S01E01_00-12-34_공주_궁중복_001.png   (PNG lossless, ~1MB)
│   │   └── metadata.csv
│   └── ...
├── clips/                         # Short video clips (~50–100GB at 720×720 H.264)
│   ├── S01E01/
│   │   ├── S01E01_00-10-00_00-12-00_공주_입복.mp4  (~3MB)
│   │   └── metadata.csv
│   └── ...
└── timestamps/                   # Curation manifests
    ├── S01E01_timestamps.csv
    └── all_episodes_master.csv
```

**Storage budget:**

| Stage | Per Episode | All 32 Episodes |
|-------|------------|-----------------|
| Raw (4K HEVC) | 5 GB | 160 GB |
| ProRes proxy | 1 GB | 32 GB |
| Stills (JPEG+PNG) | 0.3–1.5 GB | 10–50 GB |
| Clips (H.264 720p) | 1.5–3 GB | 50–100 GB |
| **Total (all stages)** | **~8.8 GB** | **~280 GB** |

**Available on Hillary:** 5.2TB free — no storage constraint.

---

## Pipeline Architecture

### Stage 1: Organize Source Files

**Unit 7 (new): Organize raw episode files**

Before processing, verify all 32 episode files are present and named consistently. Build a manifest of file paths, sizes, and checksums.

**Files:**
- Create: `scripts/video_processing/verify_manifest.py`
- Create: `data/video-corpus/episode_manifest.csv`

**Approach:**
1. Scan source directory for `.mkv` / `.mp4` files matching `Korea-Khitan.War.S01Exx.*`
2. Record: filename, path, size_bytes, sha256, episode_number
3. Validate: 32 episodes present, no duplicates, no corrupted files (sha256 match if known)
4. Output: `episode_manifest.csv` with `episode,filename,path,size,status`

**Test scenarios:**
- Happy path: 32 episodes verified, all SHA match known values (if available)
- Error path: Missing episode → report which episode number is absent and which file is missing
- Edge case: Duplicate files with different extensions (.mkv vs .mp4) → resolve to single source

---

### Stage 2: Transcode to ProRes Proxy

**Unit 8 (new): Transcode all episodes from 4K HEVC to ProRes 422 Proxy**

**Goal:** Create a fast-decodeable intermediate for all extraction work, using M3 Ultra's Media Engine.

**Files:**
- Create: `scripts/video_processing/transcode_to_proxy.py`
- Modify: `data/video-corpus/episode_manifest.csv` (add `proxy_status` column)

**Approach:**
1. For each episode in manifest:
   - Skip if `proxy.mov` already exists and is valid
   - Run ffmpeg with VideoToolbox hardware decode/encode
   - Preserve original resolution (3840×2160) and framerate (23.976fps)
   - Output: ProRes 422 (not LT) in MOV container
2. Process episodes sequentially (I/O bound, not GPU-bound — Media Engine is fast enough)
3. Store proxies in `video-corpus/proxies/`
4. Update manifest with `proxy_path`, `proxy_size`, `transcode_complete`

**Technical design:**
```bash
# Core ffmpeg command for ProRes 422 Proxy transcoding
ffmpeg -hwaccel videotoolbox \
  -c:v hevc_videotoolbox -drc_scale 1 \
  -i "${episode}.mkv" \
  -c:v prores_ks -profile:v 1 \
  -pix_fmt yuv422p10le \
  -vendor apl0 \
  "${episode}_proxy.mov"

# Hardware-accelerated decode + ProRes encode
# -prores_ks with profile:v 1 = ProRes 422 Proxy
# -pix_fmt yuv422p10le = 10-bit 4:2:2 (full color fidelity)
# -vendor apl0 = Apple-specific flag for compatibility
```

**Key ffmpeg flags:**
- `-hwaccel videotoolbox` — use Apple VideoToolbox for hardware decode/encode
- `-c:v hevc_videotoolbox` — decode HEVC via Media Engine
- `-c:v prores_ks -profile:v 1` — encode ProRes 422 Proxy
- `-an` — drop all audio (proxy is video-only, audio not needed for extraction)
- `-drc_scale 1` — maintain dynamic range (no compression of HDR-like content)

**Performance expectations on M3 Ultra:**
- HEVC decode: ~3–5× realtime via Media Engine (e.g., 55-minute episode decodes in ~11–18 minutes)
- ProRes encode: ~1.5–2× realtime
- **Total transcode time per episode: ~25–40 minutes**
- **All 32 episodes: ~13–21 hours sequential**

**Parallel processing opportunity:** Process 2 episodes concurrently — M3 Ultra has enough RAM (512GB) and Media Engine threads. 2× parallel reduces total time to ~7–10 hours.

**Test scenarios:**
- Happy path: All 32 episodes transcoded successfully, proxy plays back at correct framerate and resolution
- Edge case: Corrupt HEVC stream → ffmpeg fails gracefully with error log; skip episode; continue batch
- Error path: Disk full → detect before starting transcodes, report required space
- Verification: `ffprobe` confirms proxy: codec=ProRes 422, resolution=3840×2160, fps=23.976

---

### Stage 3: Timestamp Curation

**Unit 9 (new): Build timestamp manifest for costume-relevant moments**

**Goal:** Create a curated list of timestamps (not automated scene detection) where costume-rich scenes occur, for precise extraction.

**Requirements:** R2 (accurate drama sources), R3 (structured for extraction pipeline)

**Dependencies:** Unit 8 (proxies must exist before timestamp work)

**Files:**
- Create: `data/video-corpus/timestamps/all_episodes_master.csv`
- Modify: `scripts/video_processing/extract_stills.py` (read from timestamp manifest)

**Approach:**
1. **Watch all 32 episodes** using VLC (or mpv) at 2× speed, noting timestamps of:
   - Court scenes with visible full-body costume
   - Close-ups on costume details (collar, belt, jewelry, embroidery)
   - Scene changes that show different garment types
   - Note character name and costume type per timestamp
2. **Output:** CSV with columns: `episode,timestamp_start,timestamp_end,character,costume_type,scene_description,accuracy_notes`
3. **Target extraction rate:** ~10–20 timestamps per episode = 320–640 total extraction points
4. **Include motion clips:** Flag 3–5 second clips per episode where garment movement is visible

**Timestamp CSV format:**
```
episode,t_start,t_end,character,costume_type,scene_desc,clip_flag,accuracy_grade
S01E01,00:12:34,00:12:45,Princess,royal_yellow,Court entrance full body,FALSE,A-
S01E01,00:15:20,00:15:25,Princess,royal_yellow,Close-up collar crossing,TRUE,A-
S01E01,00:18:10,00:18:30,General,official_military,Battle armor full,TRUE,A-
S01E02,...(similar)
```

**Test scenarios:**
- Happy path: ≥320 timestamps across 32 episodes, ≥64 flagged as clip sources
- Edge case: Episode with no costume-rich scenes → log and continue; reduce target count for that episode
- Verification: Each timestamp in CSV corresponds to a valid seek point in the proxy

---

### Stage 4: Still Frame Extraction

**Unit 10 (new): Extract still frames from proxies using timestamp manifest**

**Goal:** Extract high-quality still frames at each curated timestamp, in both JPEG and PNG format.

**Files:**
- Create: `scripts/video_processing/extract_stills.py`
- Create: `data/video-corpus/stills/{episode}/metadata.csv`

**Approach:**
1. Read timestamp manifest (Unit 9)
2. For each timestamp:
   - Seek to `t_start` using `-ss` before `-i` (fast seek)
   - Extract single frame at full proxy resolution (3840×2160)
   - **Crop to 1:1 aspect ratio** (768×768 or 1024×1024) — crop the center region (face + costume)
   - Save JPEG q=95 and PNG lossless
   - Filename: `{episode}_{timestamp}_{character}_{costume_type}_{seq}.{ext}`
3. Write metadata CSV per episode tracking: frame_path, timestamp, character, costume_type, accuracy_grade, notes
4. Run validation (Unit 11) on extracted frames

**Technical design:**
```bash
# Extract single frame, crop to square, dual format
ffmpeg -ss "${timestamp}" -i "${proxy}.mov" \
  -frames:v 1 \
  -vf "crop=min(in_h\,in_w):min(in_h\,in_w):(in_w-min(in_w,in_h))/2:(in_h-min(in_w,in_h))/2,scale=768:768" \
  -q:v 95 "${output}.jpg"

ffmpeg -ss "${timestamp}" -i "${proxy}.mov" \
  -frames:v 1 \
  -vf "crop=min(in_h\,in_w):min(in_w,in_h):(in_w-min(in_w,in_h))/2:(in_h-min(in_w,in_h))/2,scale=768:768" \
  "${output}.png"
```

**Performance:** Frame extraction is nearly instantaneous (~0.1s per frame) since proxy decodes fast. 640 extractions ≈ ~2 minutes total.

**Storage per still:** JPEG q95 at 768×768 ≈ 200–400KB; PNG ≈ 1–2MB. 640 stills ≈ 400MB–1.3GB (JPEG+PNG combined).

**Test scenarios:**
- Happy path: ≥640 stills extracted, all valid images, all timestamps match CSV
- Edge case: Timestamp seek lands on blurred frame → extract 2 frames: t and t±0.5s; take sharpest
- Error path: Proxy missing for an episode → skip those timestamps; log warning; continue
- Verification: All outputs are ≥768×768, valid JPEG/PNG, RGB color

---

### Stage 5: Video Clip Extraction

**Unit 11 (new): Extract 1–5 second video clips for motion reference**

**Goal:** Extract short H.264 clips of garment movement, useful for video diffusion training and drapery analysis.

**Files:**
- Create: `scripts/video_processing/extract_clips.py`
- Create: `data/video-corpus/clips/{episode}/metadata.csv`

**Approach:**
1. Read timestamp manifest — filter rows where `clip_flag=TRUE`
2. For each clip:
   - Seek to `t_start`
   - Extract `t_end - t_start` duration (typically 2–5 seconds)
   - Encode as H.264 at 720×720, CRF 18 (high quality), AAC audio dropped
   - Filename: `{episode}_{t_start}_{t_end}_{character}_{costume_type}.mp4`
3. Write metadata CSV: clip_path, t_start, t_end, character, costume_type, duration_seconds, accuracy_grade

**Technical design:**
```bash
# Extract clip, crop to square, encode H.264
ffmpeg -ss "${t_start}" -i "${proxy}.mov" \
  -t "${duration}" \
  -vf "crop=min(in_h\,in_w):min(in_w,in_h):(in_w-min(in_w,in_h))/2:(in_h-min(in_w,in_h))/2,scale=720:720" \
  -c:v libx264 -preset medium -crf 18 \
  -c:a none \
  -movflags +faststart \
  "${output}.mp4"
```

**Performance:** H.264 encode at 720p is fast on M3 Ultra (~1–2× realtime). 64 clips × 3 seconds avg ≈ 192 seconds of encode ≈ ~5–10 minutes total.

**Storage per clip:** H.264 720p CRF18 ≈ 1–2MB per 3-second clip. 64 clips ≈ 64–128MB.

**Test scenarios:**
- Happy path: ≥64 clips extracted, all playable, duration matches CSV
- Edge case: Clip shorter than 2 seconds (scene cut inside window) → extend window or skip
- Error path: Frame seek instability at cut point → re-encode with `-ss` before `-i` (input seek, not output) for frame-accurate start
- Verification: All outputs are ≥720×720, valid H.264 MP4, duration ±0.5s of expected

---

### Stage 6: Automated Quality Validation

**Unit 12 (new): Validate all extracted stills and clips**

**Goal:** Automated QA pipeline confirms all extracted assets meet minimum quality thresholds before entering curation workflow.

**Files:**
- Create: `scripts/video_processing/validate_all_extractions.py`
- Create: `data/video-corpus/validation_report.md`

**Approach:**
1. **Stills validation:**
   - Resolution: ≥768×768
   - Format: valid JPEG or PNG
   - Color space: RGB (not grayscale, not CMYK)
   - Sharpness: Laplacian variance > threshold (detect blurry frames)
   - Aspect ratio: 1:1 (±1% tolerance)
   - File size: JPEG > 50KB (ensures not blank/damaged), PNG > 200KB
2. **Clips validation:**
   - Duration: 1–6 seconds (outside this range → flag)
   - Resolution: ≥720×720
   - Codec: H.264
   - Playable: ffprobe can read stream (no corruption)
3. **Output:** Validation report listing pass/fail per asset, with failure reason for each failed asset

**Test scenarios:**
- Happy path: ≥95% of extracted stills and clips pass all validation checks
- Edge case: Entire episode's extractions fail validation → investigate proxy corruption or timestamp seek issue
- Error path: Storage full during validation → report, do not crash
- Verification: Failed assets are moved to `data/video-corpus/rejected/` with reason in filename

---

### Stage 7: Integrate with Curation and img2img (Units 5–6)

The extracted stills and clips from Units 10–11 feed directly into Units 5 and 6 (categorization, curation, img2img testing).

**Workflow:**
```
Stage 4 (stills) + Stage 5 (clips)
    → Unit 5 (categorization: royal, official, ceremonial, detail)
    → Unit 5 (curated reference board)
    → Unit 6 (img2img generation tests)
```

Clips are additionally useful as:
- **Motion reference** for garment behavior (drapery folds, walking rhythm)
- **Future phase:** Training data for video diffusion models (AnimateDiff, SVD)

---

## Decoupled Execution Order

```
Week 1
├── Day 1-2: Unit 7 — Verify episode manifest (1 hour)
├── Day 2-3: Unit 8 — Start transcode (batch, overnight)  ← longest step (~10-20 hours)
└── Day 3-4: Watch episodes, build timestamp manifest (Unit 9)  ← human curation

Week 2
├── Day 5-6: Unit 10 — Extract stills (~30 min)
├── Day 6-7: Unit 11 — Extract clips (~30 min)
├── Day 7: Unit 12 — Validation (~15 min)
└── Day 7: Unit 5 — Categorization, curation board
└── Day 7-8: Unit 6 — img2img integration tests
```

**Longest pole:** Unit 8 (transcoding) at 10–20 hours. Everything else is minutes to hours.

---

## Deferred to Implementation

- **Exact crop coordinates:** Center crop is a starting point; face detection (MediaPipe/VNDetectFaceRectanglesRequest) could center crop on detected face region for better framing. Deferred — implement if center crop produces poorly framed results.
- **Automated scene detection:** Could supplement manual timestamp curation with `scenedetect` (ffmpeg-based) to flag scene changes automatically. Deferred — manual curation is higher accuracy for costume-specific selection.
- **Motion debanding/degrain:** 4K HEVC web-dl may have compression artifacts. Could apply `ffmpeg hqdn3d` filter before extraction for cleaner frames. Deferred — assess on first episode; add if artifact level is high.
- **Video diffusion training:** Clips from Stage 5 can train AnimateDiff-style models. This is a future phase beyond current scope.

---

## Risks & Mitigations (Video Corpus Section)

| Risk | Mitigation |
|------|------------|
| Transcode takes 10–20 hours (overnight) | Run 2 episodes in parallel; start overnight; verify proxies in morning |
| 4K HEVC files are large (160GB) — slow copy to Hillary | Use rsync with checksum verification; copy to Data volume (fast SSD) |
| ProRes proxy storage (~32GB) fills drive | Keep raw + proxies on Data volume (5.2TB free); delete proxies after extraction complete |
| Center crop misses costume detail (face-centric framing) | Extract full-resolution frames; apply crop at configurable offset in post; start with center crop |
| Human timestamp curation takes 8–16 hours of watching | Accelerate with 2× playback; skip scenes with no costume visibility |
| H.265 HEVC hardware decode instability on macOS | Test decode on episode 1 before full batch; fall back to software decode (`ffmpeg -c:v libx265`) if needed |
| Crop to square loses costume context (too tight) | Extract at 1024×1024 crop from 4K proxy before downscale; allows looser framing |

---

## Success Metrics (Video Corpus Section)

- [ ] All 32 episodes have valid ProRes 422 proxies (32/32)
- [ ] ≥640 still frames extracted at 768×768 JPEG+PNG, all passing validation
- [ ] ≥64 video clips extracted at 720×720 H.264, all passing validation
- [ ] Timestamp manifest covers all 32 episodes with costume-type labels
- [ ] Extraction pipeline total runtime: <24 hours from raw files to validated assets
- [ ] Storage footprint after proxy deletion (keeping only stills+clips): <100GB

---

## Dependencies / Prerequisites (Video Corpus Section)

1. **Source files accessible on Hillary**: All 32 episode files must be on Hillary's Data volume before pipeline starts. Estimated time to copy 160GB: ~30–60 minutes over local network.
2. **ffmpeg with VideoToolbox support**: Verify `ffmpeg -decoders | grep videotoolbox` shows HEVC decode support. Should be present in Homebrew's ffmpeg on macOS.
3. **rsync or equivalent**: For verifying file transfer integrity.

---

*Last updated: 2026-04-22*

---

## Text Corpus Crawler Section

### Purpose

This section augments the plan with a detailed crawler strategy for building the **Scenario 1 (Text) pipeline** — the scholarly design bible and caption corpus. The 20 ranked sources from the deep research report provide the material; the crawler translates them into structured training data for Stable Diffusion LoRA fine-tuning.

**Private use only**: All crawlers are for personal research and training data generation. No distribution of copyrighted material. KBS VOD, DBpia, KISS explicitly prohibit unauthorized crawling — those sources are marked accordingly and handled via manual retrieval or institution-authenticated access only.

**Context**: `cross-post` contains TypeScript/Node.js tooling with established patterns for content fetching, error handling, and structured output. The crawler framework should be built in Python (httpx + BeautifulSoup) for easier integration with the existing Python-based image pipeline, but should mirror the architectural patterns from cross-post (`src/shared/errors.ts`, `src/core/chunker.ts`).

---

### Source Ranking

The 20 sources from the deep research report are ranked below on two axes:

| Difficulty | Criteria | Sources |
|---|---|---|
| **Easiest** | Public API or open endpoint; no auth; CC0/KOGL-1 licensing; static HTML | Met, Cleveland, Smithsonian NMAA, JKAA |
| **Easy** | Structured search UI; rate-limited but accessible; some KOGL restrictions | Heritage Portal, NRICH portal, NMK DB, AKS EncyKorea |
| **Medium** | Requires Korean-language scraping; Korean character encoding; search-form navigation | Gugak Archive, Goryeodogyeong portals, NIKH DB |
| **Hard** | Subscription/institution auth; terms prohibit unauthorized copying; CAPTCHA or login required | RISS, DBpia, KISS, UH Press books |
| **Hardest** | No public API; platform prohibits AI learning; login/paywall for full content | KBS VOD, Hangeul Museum (audio) |

### Quality Ranking (Best Material for Goryeo Costume Training)

| Rank | Source | Quality Rationale | Best For |
|---|---|---|---|
| 1 | NMK Collection DB | Object-level visual truth; zoomable images; costume elements, hair ornaments, celadon contexts | Visual reference + metadata |
| 2 | JKAA | Open-access scholarly articles on Goryeo costume; diagrams; figure plates with detailed costume element annotations | Caption authority; design bible text |
| 3 | NRICH portal | Excavation reports; tomb furnishings; costume-adjacent finds; actual material forms from period | Material accuracy; garment shapes |
| 4 | Heritage Portal | Designated heritage photos; architecture; costume-adjacent site photography | Spatial context; palace interior hints |
| 5 | Goryeodogyeong | Primary source; 1123 eyewitness description of Goryeo court dress vs Song; most direct period text | Design bible foundation; collar/window/size distinctions |
| 6 | AKS EncyKorea/KOSTMA | Controlled vocabulary; costume terminology with Korean/English translations; no-fluff definitions | Caption vocabulary; terminology accuracy |
| 7 | Cleveland OA | CC0 Goryeo celadon; tomb objects; practical vessels (not just masterworks); material culture depth | Object reference; pottery context for costume setting |
| 8 | Met Open Access | CC0 Goryeo Buddhist paintings; hair ornaments; high-res public domain images | Buddhist costume; hair ornament reference |
| 9 | Gugak Archive | Court music; instrument forms; performance video (KOGL varies) | Audio context; ceremonial scene captioning |
| 10 | Korean costume papers (KCI/RISS) | Academic diagrams; costume shape studies; specific visual comparisons with Song | Design bible detail; collar direction proof |
| 11 | Smithsonian NMAA | Goryeo Buddhist paintings; research publications; public domain | Secondary visual reference |
| 12 | NIKH DB | Chronology; office titles; court ritual references; educational video | Text accuracy; scene context captions |
| 13 | RISS | Discovery layer; bibliography only; actual articles behind paywalls | Academic search; finding Korean costume papers |
| 14 | UH Press translations | Purchased books; high quality but not crawleable | Reference only; not for corpus ingestion |
| 15 | KBS VOD | Explicitly prohibits AI learning; no-crawl policy | Analyst-only reference; do not process |
| 16 | DBpia | Prohibits unauthorized copying; subscription required | Manual retrieval only if institution access available |
| 17 | KISS | Prohibits unauthorized copying; subscription required | Manual retrieval only if institution access available |
| 18 | Hangeul Museum | No period-authentic audio exists; archive is for method not content | Excluded from audio corpus |
| 19 | UNESCO pages | Macro site documentation only; not specific enough for costume | Supplement only |
| 20 | Substack/etc | N/A for Korean Goryeo content | Not relevant |

### Task Priority Order (Best -> Worst, Refers to Above Table)

**Task 1: Met / Cleveland / Smithsonian NMAA** — CC0, public API, highest quality
**Task 2: JKAA** — Free PDFs, scholarly authority on costume
**Task 3: NMK Collection DB** — Object-level visual truth, KOGL-1 items
**Task 4: NRICH portal** — Excavation reports, material forms
**Task 5: Heritage Portal** — Architecture photos, site context
**Task 6: AKS EncyKorea/KOSTMA** — Controlled vocabulary, caption terms
**Task 7: Goryeodogyeong (ITKC + UH Press)** — Primary text, design bible anchor
**Task 8: Korean costume papers (KCI-open)** — Academic diagrams, costume shape
**Task 9: Gugak Archive** — Court music, ceremonial context
**Task 10: NIKH DB** — Chronology, educational video, scene context

**Excluded from crawler (manual retrieval or do-not-process):**
- KBS VOD — explicitly prohibits AI learning
- DBpia / KISS — subscription + terms prohibit unauthorized copying
- UH Press — purchase required, not crawleable
- Hangeul Museum audio — no period-authentic content exists
- UNESCO — supplement only, too macro-level

---

### Crawler Architecture

```
CRAWLER FRAMEWORK (Python)
==========================
src/
├── framework/
│   ├── fetcher.py        # httpx async HTTP with rate limiting + retry
│   ├── parser.py         # BeautifulSoup + Korean character handling
│   ├── storage.py        # Save to train_data/text_corpus/ with metadata YAML
│   ├── errors.py         # Structured error types (cf cross-post src/shared/errors.ts)
│   └── robots.py         # Respect robots.txt, with ignore list for Korean gov sites
├── sources/
│   ├── met_cma_smithsonian.py   # Task 1: Museum open access APIs
│   ├── jkaa.py                   # Task 2: JKAA article + figure extraction
│   ├── nmk.py                    # Task 3: National Museum of Korea collection DB
│   ├── nrich.py                  # Task 4: NRICH excavation reports + images
│   ├── heritage_portal.py        # Task 5: Heritage Portal site scraping
│   ├── aks.py                    # Task 6: AKS EncyKorea terminology extraction
│   ├── goryeodogyeong.py         # Task 7: ITKC text extraction
│   ├── kci_costume_papers.py     # Task 8: KCI costume paper PDFs
│   ├── gugak_archive.py          # Task 9: Gugak audio/archive scraping
│   └── nikh.py                   # Task 10: NIKH DB text + video extraction
├── pipelines/
│   ├── text_to_design_bible.py   # LLM-assisted extraction from crawled text -> design bible sections
│   └── text_to_captions.py       # Design bible -> Kohya SS weighted caption CSV
└── run.py                 # Orchestrator: run tasks in priority order

Output structure:
train_data/text_corpus/
├── museum_open_access/     # Met, Cleveland, Smithsonian images + metadata
├── jkaa_articles/         # JKAA PDFs + extracted figure descriptions
├── nmk_objects/           # NMK collection items + KOGL status
├── nrich_reports/         # Excavation report PDFs + images
├── heritage_sites/         # Site photos + descriptions
├── aks_vocabulary/        # Terminology YAML (KO/EN + visual notes)
├── goryeodogyeong/        # Extracted text sections by topic
├── costume_papers/        # KCI open-access article extracts
├── gugak_audio/           # Audio metadata + transcript excerpts
└── nikh_db/               # Chronology entries + video transcript
```

**Parallel to cross-post patterns:**
- `errors.py` mirrors `cross-post/src/shared/errors.ts` (PublishError -> CrawlError with code, message, retryable, details)
- `fetcher.py` mirrors the HTTP client pattern in cross-post platforms (httpx vs the platform-specific HTTP clients)
- `storage.py` uses YAML frontmatter + plain text, similar to how cross-post uses Markdown + frontmatter for posts
- Korean character encoding handled via `encoding="utf-8"` in BeautifulSoup; fallback to `euc-kr` for older Korean government sites

---

### Tools Required

| Tool | Purpose | Installation |
|---|---|---|
| **httpx** | Async HTTP client with built-in retry, timeout, connection pooling | `pip install httpx` |
| **BeautifulSoup4** | HTML parsing; Korean government sites, archive pages | `pip install beautifulsoup4` |
| **lxml** | Fast XML/HTML parser backend for BeautifulSoup | `pip install lxml` |
| **Playwright** | Headless browser for JavaScript-rendered pages (KBS VOD, some KR portals) | `pip install playwright; playwright install chromium` |
| **PyYAML** | Metadata YAML frontmatter on all crawled content | `pip install pyyaml` |
| **tiktoken** | Token counter for LLM processing (ensure prompts < context window) | `pip install tiktoken` |
| **python-magic** | MIME type detection for downloaded files | `pip install python-magic` |
| **pathlib** | Standard library; all file path operations | (built-in) |

**Optional / Future:**
- **Selenium** (fallback if Playwright insufficient for Korean site JS)
- **scrapy** (if site count grows beyond 20; overkill for current scope)
- **marisa-trie** (if we need to do Korean text dedup at scale)

---

### Key Crawling Decisions

**Decision 1: Respect robots.txt for Korean government sites.**
Korean heritage/government sites (Heritage Portal, NRICH, NMK) typically allow crawlers but request self-identification. Set `User-Agent` to identify the project and contact email in requests. Do not crawl KBS VOD regardless of robots.txt status — KBS explicitly prohibits AI learning on VOD pages.

**Decision 2: Institution-authenticated sources (DBpia, KISS) -> manual retrieval only.**
Both DBpia and KISS prohibit unauthorized copying in their terms and require institutional login. Do not attempt to bypass paywalls. If the user has institutional access (university library proxy), these can be retrieved manually and fed into the pipeline as PDFs.

**Decision 3: Rate limiting.**
All HTTP clients respect 1 request/second minimum between requests. Korean archive sites get 2-second minimum. This protects against IP blocks and respects server resources.

**Decision 4: LLM processing is a second pass after raw corpus is crawled.**
Crawled text -> raw `.txt` files with YAML frontmatter (source URL, date_crawled, rights_status, text_type). Then a separate LLM-assisted pass extracts visual descriptions and structures them into the design bible. This keeps the crawler simple and the LLM layer independent.

**Decision 5: Image downloads vs text-only.**
For museum APIs (Met, Cleveland, Smithsonian): download images + metadata JSON. For text archives (JKAA, costume papers): download PDFs + extract text. For Korean portals: HTML parse + save structured text. Do not download video from Gugak Archive — scrape metadata and descriptions only (video requires login).

**Decision 6: Cross-post as architectural reference, not dependency.**
The crawler does not import from cross-post. It mirrors the pattern language (structured errors, async fetch, YAML frontmatter) but is independently deployable. This avoids Node.js <> Python interop complexity.

---

## Implementation Units — Text Corpus Crawler

### Context

These units follow the existing Implementation Units structure (Units 1-6 for text + drama, Units 7-12 for video processing). The crawler units (13-18) augment the text pipeline (Scenario 1) by providing the raw corpus that feeds Units 1 (design bible) and 2 (caption templates).

**Execution order:** Units 13-18 should be executed in order (13 -> 14 -> ... -> 18), since each populates the corpus that the next unit processes. However, Units 13 and 14 can run in parallel with other planning work since they are independent of the video pipeline.

---

- [ ] **Unit 13: Set Up Crawler Framework**

**Goal:** Build the Python crawler base infrastructure — fetcher, parser, storage, error types, and directory structure. Mirrors cross-post architecture patterns without importing from it.

**Requirements:** R1 (costume differentiation), R2 (captionable visual attributes)

**Dependencies:** None

**Files:**
- Create: `scripts/text_crawler/framework/fetcher.py` — httpx async client with rate limiting, retry, and timeout. Configurable requests-per-second. Structured error on non-200 responses.
- Create: `scripts/text_crawler/framework/parser.py` — BeautifulSoup wrapper with Korean encoding detection and fallback chain (utf-8 -> euc-kr -> cp949 -> iso-8859-1)
- Create: `scripts/text_crawler/framework/storage.py` — Save crawled content to `train_data/text_corpus/{source}/` with YAML frontmatter (source_url, date_crawled, rights_status, text_type, language)
- Create: `scripts/text_crawler/framework/errors.py` — CrawlError type: code (network, parse, auth, rate_limited, robots_blocked, unknown), message, retryable, details dict
- Create: `scripts/text_crawler/framework/robots.py` — robots.txt checker; blocklist for sites that must not be crawled regardless of robots.txt
- Create: `scripts/text_crawler/run.py` — Orchestrator: load task queue, run in priority order, log progress, resume on interruption

**Patterns to follow:**
- `cross-post/src/shared/errors.ts` — error type structure (code + message + options pattern)
- `cross-post/src/core/chunker.ts` — structured output with clear error states

**Test scenarios:**
- Happy path: fetcher.py completes 10 sequential requests with correct rate limiting and no errors
- Edge case: Server returns 429 -> CrawlError with retryable=true, crawler waits and retries
- Edge case: Korean site returns EUC-KR encoded HTML -> parser correctly detects and decodes
- Error path: robots.txt disallows -> CrawlError with code=robots_blocked, log and skip
- Error path: HTTP timeout after 3 retries -> CrawlError with code=network, details include URL and timeout value

**Verification:** All framework modules import without error; `python run.py --dry-run` completes without crashing; test against one real endpoint (e.g., Met API)

---

- [ ] **Unit 14: Crawl Museum Open Access (Met, Cleveland, Smithsonian NMAA)**

**Goal:** Download all CC0 Goryeo-period images and metadata from the three best open-access museum collections.

**Requirements:** R2 (visual reference corpus)

**Dependencies:** Unit 13

**Files:**
- Create: `scripts/text_crawler/sources/museum_open_access.py` — Unified crawler for Met (API), Cleveland (API), Smithsonian NMAA (collection search)
- Create: `train_data/text_corpus/museum_open_access/` — Images + metadata YAML per object
- Create: `scripts/text_crawler/sources/met_search.py` — Met collection API: search "Goryeo", "Korean", filter for images, paginate through results
- Create: `scripts/text_crawler/sources/cleveland_search.py` — Cleveland Museum API: search Goryeo, paginate
- Create: `scripts/text_crawler/sources/smithsonian_search.py` — Smithsonian API: search Goryeo + Asian Art, paginate

**Approach:**
1. Met API: `https://collectionapi.metmuseum.org/public/collection/v1/search?q=Goryeo&hasImages=true&medium=Paintings` -> iterate object IDs -> download primaryImage + metadata JSON
2. Cleveland API: `https://api.clevelandart.org/api/v1/artworks?query=Goryeo` -> paginate -> download images
3. Smithsonian: `https://api.si.edu/api/collections/search?q=Goryeo` -> paginate -> download images where public domain
4. Save each object as: `{museum}_{object_id}.{ext}` + `{museum}_{object_id}.yaml` (all metadata fields)
5. Filter: only save objects where rightsStatus is "Public Domain" or "CC0"

**Technical design:**
```python
# Met API flow
search_url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
params = {"q": "Goryeo", "hasImages": "true", "medium": "Paintings"}
# Paginate: total / 50 per page, follow nextPage URL
# For each object ID: GET /objects/{id} -> primaryImageSmall + metadata
# Rate limit: 1 req/sec
```

**Test scenarios:**
- Happy path: >=100 Goryeo images downloaded from Met, >=50 from Cleveland, >=30 from Smithsonian
- Edge case: Object has no image (primaryImage is empty) -> skip, log count of skipped
- Error path: API key/rate limit hit -> CrawlError retryable, pause 60s, retry
- Verification: All images >=768px on one axis; all YAML files have `rightsStatus=Public Domain or CC0`

**Verification:** All downloaded images are valid JPEG/PNG, >=768px, with YAML frontmatter. Object count per museum matches API search totals.

---

- [ ] **Unit 15: Crawl JKAA + Korean Costume Papers**

**Goal:** Download open-access JKAA articles and KCI costume papers. Extract text and figure descriptions for design bible input.

**Requirements:** R1 (costume differentiation text), R2 (captionable attributes)

**Dependencies:** Unit 13

**Files:**
- Create: `scripts/text_crawler/sources/jkaa.py` — JKAA article crawler + PDF download + text extraction
- Create: `scripts/text_crawler/sources/kci_costume.py` — KCI open-access costume paper crawler
- Create: `train_data/text_corpus/jkaa_articles/` — PDFs + extracted text per article
- Create: `train_data/text_corpus/costume_papers/` — KCI paper PDFs + extracted text

**Approach:**
1. JKAA: crawl article index page -> find PDF links for costume/Goryeo articles -> download PDF -> extract text with `pdfplumber` (preserve figure captions and section headers)
2. KCI: search costume papers via `https://www.kci.go.kr/` -> follow open-access article links -> extract text
3. Extract per article: title (KO/EN), authors, abstract, body text, figure captions, references
4. Tag each extracted block with: `costume_collar`, `costume_waist`, `hairstyle`, `hat`, `ornament`, `fabric`, `color`, `period_marker`

**Technical design:**
```python
# JKAA article extraction
article_pages = ["https://www.ijkaa.org/v.14/0/73/29", ...]  # known costume articles from research report
for page_url in article_pages:
    html = fetcher.get(page_url)
    pdf_links = soup.find_all("a[href$=.pdf]")
    for link in pdf_links:
        pdf_bytes = fetcher.get_binary(link["href"])
        text = pdfplumber.extract(pdf_bytes)
        # preserve section headers, figure captions, footnotes
        storage.save(page_url, text, frontmatter_yaml)
```

**Test scenarios:**
- Happy path: >=8 JKAA costume articles downloaded and extracted; figure captions preserved
- Edge case: PDF is scan image (no extractable text) -> log warning, save PDF anyway for manual review
- Error path: KCI requires login for some articles -> CrawlError code=auth, skip those articles, log count
- Verification: All extracted texts have >=500 words; all have YAML with article title, authors, DOI

**Verification:** All outputs have >=500 words of extracted text; figure captions are preserved as a distinct block; YAML frontmatter has article title, DOI, and extracted date.

---

- [ ] **Unit 16: Crawl Korean Government Heritage Portals (NRICH, Heritage Portal, NMK)**

**Goal:** Harvest Goryeo-period excavation reports, site photos, and object records from official Korean heritage institutions.

**Requirements:** R1 (material form accuracy), R2 (spatial context)

**Dependencies:** Unit 13

**Files:**
- Create: `scripts/text_crawler/sources/nrich.py` — NRICH portal crawler (excavation reports + images)
- Create: `scripts/text_crawler/sources/heritage_portal.py` — Heritage Portal site crawler (site photos + descriptions)
- Create: `scripts/text_crawler/sources/nmk.py` — NMK collection DB API crawler (object records + images)
- Create: `train_data/text_corpus/nrich_reports/` — Excavation report text + images
- Create: `train_data/text_corpus/heritage_sites/` — Site photos + descriptions
- Create: `train_data/text_corpus/nmk_objects/` — NMK collection records + images

**Approach:**
1. **NRICH**: `https://portal.nrich.go.kr/` — search queries from research report (`고려시대 분묘유적 자료집`, `고려시대 성곽유적 자료집`) -> follow result links -> extract report text + download figures
2. **Heritage Portal**: `https://www.heritage.go.kr/` — set period filter to `시대=고려시대` -> scrape site photo pages + KOGL status per item
3. **NMK**: `https://www.museum.go.kr/ENG/contents/E0402000000.do` — search `고려`, `수월관음`, `관복` -> follow object detail pages -> collect metadata + image URLs
4. For each: separate KOGL Type 1 (CC0-equivalent) items into `train_eligible/` subdirectory; mark Type 2-4 as `reference_only/`

**Key Korean search terms for crawler:**
```
고려 청자 고려 불화 고려 목판 고려 성곽유적 고려 분묘유적
수월관음 고려 관복 고려 머리모양 고려시대 사진 고려시대 동영상
```

**Test scenarios:**
- Happy path: >=50 NRICH report pages crawled; >=100 Heritage Portal site photos with descriptions; >=50 NMK object records
- Edge case: KOGL status is mixed on a page (some images Type 1, some Type 4) -> save all but tag `rights_status` per file
- Error path: Site returns 503 -> retry 3X with backoff, then CrawlError and continue to next URL
- Verification: All outputs have YAML with KOGL status, source URL, and crawl date

**Verification:** Each crawled item has YAML with `kogol_status` field; NRICH reports are >=1000 words; site photos have Korean-language descriptions >=50 words.

---

- [ ] **Unit 17: Crawl AKS EncyKorea + Goryeodogyeong + NIKH DB**

**Goal:** Extract controlled Korean costume vocabulary (EncyKorea), primary text sections (Goryeodogyeong), and chronology entries (NIKH) for design bible foundation.

**Requirements:** R1 (terminology control), R2 (caption vocabulary)

**Dependencies:** Unit 13

**Files:**
- Create: `scripts/text_crawler/sources/aks_vocabulary.py` — AKS EncyKorea + KOSTMA terminology crawler
- Create: `scripts/text_crawler/sources/goryeodogyeong_text.py` — ITKC Goryeodogyeong text extractor
- Create: `scripts/text_crawler/sources/nikh_db.py` — NIKH DB text + educational video metadata crawler
- Create: `train_data/text_corpus/aks_vocabulary/` — Terminology YAML (KO/EN + visual notes per term)
- Create: `train_data/text_corpus/goryeodogyeong/` — Extracted text by topic (court_dress, ritual, architecture, music)
- Create: `train_data/text_corpus/nikh_db/` — Chronology entries + video descriptions

**Approach:**
1. **AKS EncyKorea**: crawl `https://encykorea.aks.ac.kr/` entries for costume terms (관복, 복식, 머리모양, 팔관회 등) -> structured YAML per term: `{ term_ko, term_en, definition, related_terms, visual_notes, period_of_validity }`
2. **Goryeodogyeong**: access `https://www.itkc.or.kr/` or use UH Press English translation text -> extract sections by topic (court dress, palace gates, ceremony) -> YAML: `{ section_title, source_text, translator_notes, period_marker }`
3. **NIKH DB**: `https://db.history.go.kr/` -> search reign-year entries for Gojong 5 (1218) -> extract office titles, ceremony descriptions, court ritual entries -> YAML: `{ year, reign, event_type, description, source }`

**Key search terms for EncyKorea crawler:**
```
백관복 제복 품대 각대 의물 팔관회 연등회 고려 복식 고려 머리모양
관모 나전 고려목판 고려 청자 고려 불화
```

**Test scenarios:**
- Happy path: >=50 AKS vocabulary entries extracted with KO/EN definitions; >=20 Goryeodogyeong sections by topic; >=50 NIKH DB chronology entries
- Edge case: Term has no English translation in KOSTMA -> mark `term_en: null`, include Korean definition only
- Error path: ITKC requires login for full text -> CrawlError code=auth; fall back to publicly available Goryeodogyeong excerpts or UH Press English text
- Verification: All vocabulary YAML has `term_ko` and `definition`; Goryeodogyeong YAML has source chapter/section reference

**Verification:** Vocabulary entries include at minimum: term_ko, term_en, definition; Goryeodogyeong sections are tagged by topic; NIKH entries include year, reign, and event description.

---

- [ ] **Unit 18: Validate Text Corpus Completeness + Integration Test**

**Goal:** Verify the complete text corpus, assess gaps, and run an integration test with the design bible generation pipeline (Units 1-2).

**Requirements:** R1 (costume differentiation), R2 (captionable attributes)

**Dependencies:** Units 13, 14, 15, 16, 17

**Files:**
- Create: `scripts/text_crawler/validate_corpus.py` — Check corpus completeness across all 10 source categories
- Create: `scripts/text_crawler/corpus_assessment_report.md` — Gap analysis: what's well-covered vs. missing per costume element
- Create: `scripts/text_crawler/integration_test.py` — Run LLM on a sample of the corpus to verify design bible generation pipeline works

**Approach:**
1. **Completeness check**: For each of 8 garment categories (collar, skirt, jacket, hat, belt, hair ornaments, jewelry, footwear), check whether corpus has >=3 relevant sources. Report gaps as `MISSING: [category] — no sources found`.
2. **Volume check**: Count total crawled items per source category; flag categories with <10 items.
3. **LLM integration test**: Take a random 10% sample of corpus -> send to LLM with prompt: "Extract all visual costume descriptions from this text and format as bullet points" -> verify output is non-empty -> if empty, flag corpus for re-crawl or manual supplement.
4. **Gap report**: Generate `corpus_assessment_report.md` with table: Category | Source Count | Quality Assessment | Gap Status | Recommended Action

**Test scenarios:**
- Happy path: All 8 garment categories have >=3 sources; LLM test produces >=50 visual description bullet points from sample
- Edge case: One category (e.g., footwear) has only 1 source -> mark as "sparse — supplement manually"
- Error path: LLM test produces empty output -> investigate whether corpus text has actual costume content or is metadata-only
- Verification: Gap report is generated with <=3 MISSING categories; manual review of LLM output shows costume-relevant descriptions

**Verification:** Gap report exists with <=3 MISSING categories; LLM integration test produces non-empty output; total corpus size >=50MB across all sources.

---

## Crawler Execution Order

```
Week 1 (parallel with other units)
├── Day 1: Unit 13 — Framework setup (~2 hours)
├── Day 1-2: Unit 14 — Museum APIs (~1-2 hours, 200+ images)
└── Day 2-3: Unit 15 — JKAA + KCI papers (~2-3 hours)

Week 2 (sequential)
├── Day 4: Unit 16 — Korean government portals (~3-4 hours)
├── Day 5: Unit 17 — AKS + Goryeodogyeong + NIKH (~3-4 hours)
└── Day 6: Unit 18 — Validation + gap report (~2 hours)

Total crawler runtime: ~12-15 hours (mostly automated, some manual monitoring)
```

**Longest pole:** Unit 16 (Korean government portals) at 3-4 hours due to site complexity and rate limiting.

---

## Deferred to Implementation

### Excluded Sources — Terms and Compliance

The following sources are explicitly excluded from automated crawling on legal/terms grounds. Do not implement crawlers for these platforms regardless of robots.txt status or technical accessibility.

| Source | URL | Exclusion Reason |
|---|---|---|
| **KBS VOD** | https://vod.kbs.co.kr | Terms explicitly prohibit AI learning and automated content extraction. robots.txt also disallows all crawlers. Use manual shot logging only (drama pipeline, Unit 4). |
| **DBpia** | https://www.dbpia.co.kr | Terms prohibit unauthorized copying, reproduction, or extraction of content. Requires institutional subscription. Automated scraping would violate terms even with credentials. |
| **KISS** | https://kiss.kstudy.com | Terms prohibit unauthorized copying. Library/archival system where content licensing requires explicit permission for anything beyond personal use. Subscription-gated. |
| **namuwiki** | https://namu.wiki | robots.txt disallows all crawlers. Requires JavaScript rendering (not static HTML) - would need Playwright for every page. Crowd-sourced content also raises reliability concerns for scholarly corpus. |

If institutional access to DBpia or KISS is obtained via university library proxy, retrieve articles manually and drop into `train_data/text_corpus/costume_papers/` as PDFs for Unit 15 processing.

### Other Deferred Items

- **Gugak Archive video download**: Full video requires login/request. Crawler extracts metadata and text descriptions only. Actual audio/video files are manual retrieval.
- **LLM pass strategy**: The LLM-assisted extraction from corpus to design bible (Units 1-2 input) is deferred to Unit 1 execution. The crawler only builds the raw corpus; the LLM layer is a separate pass.
- **Deduplication**: Large-scale text dedup (marisa-trie) is deferred - corpus is small enough (estimated <500MB) that deduplication is not critical for current scope.

## Success Metrics (Text Corpus Crawler)

- [ ] All 10 source categories have crawled content in `train_data/text_corpus/`
- [ ] Museum sources (Unit 14): >=200 images with CC0/public-domain status confirmed in YAML
- [ ] JKAA + KCI (Unit 15): >=15 articles fully extracted with figure captions preserved
- [ ] Korean government portals (Unit 16): >=150 object/site records with KOGL status tagged
- [ ] Vocabulary + primary text (Unit 17): >=50 AKS vocabulary entries + >=20 Goryeodogyeong sections + >=50 NIKH entries
- [ ] Corpus total size: >=50MB
- [ ] Gap report (Unit 18): <=3 garment categories marked as MISSING
- [ ] No KBS VOD pages, DBpia pages, or KISS pages in corpus (compliance check)

---

## Tools Summary (Text Corpus Crawler)

| Unit | Tools |
|---|---|
| Unit 13 | httpx, BeautifulSoup4, lxml, PyYAML, pathlib |
| Unit 14 | httpx (Met/Cleveland/Smithsonian APIs), PIL (image validation) |
| Unit 15 | httpx, pdfplumber (PDF text extraction), BeautifulSoup |
| Unit 16 | httpx, BeautifulSoup, Playwright (if JS-rendered), PIL |
| Unit 17 | httpx, BeautifulSoup, PyYAML, (ITKC API if accessible) |
| Unit 18 | tiktoken (LLM token counting), Python standard library |

**Total dependencies:** `pip install httpx beautifulsoup4 lxml pyyaml pdfplumber tiktoken playwright pillow`