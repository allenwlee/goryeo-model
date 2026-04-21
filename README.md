# goryeo-model

A local LLM finetuned on historically accurate data from the Goryeo era (918–1392 CE).

## Overview

This project produces a model capable of generating or evaluating Goryeo-period accurate content — dialogue, documents, customs, and historical context.

## Project Structure

```
goryeo-model/
├── data/               # Raw historical data and curated corpora
├── scripts/            # Data processing, training, evaluation scripts
├── model/              # Model weights, config, tokenizer (not committed to git)
├── results/            # Training outputs, logs, eval results
├── README.md
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
```

## Dataset

The training corpus draws from primary and secondary sources on Goryeo history, including:
- Samguk Sagi (삼국유사)
- Goryeo-sa (고려사)
- Contemporary academic datasets on medieval Korean history

## Training

```bash
python scripts/train.py --config configs/finetune.yaml
```

## Model

- **Base model**: TBD
- **Task**: Instruction-tuning / RAG-style historical Q&A
- **Expected output**: Period-accurate dialogue, document drafts, historical analysis

## License

TBD
