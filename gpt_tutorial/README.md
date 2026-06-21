# GPT Tutorial — Train an LLM from Scratch

A learn-by-building course. **Day 1** covers the theory and maths of language
models and self-attention, plus a runnable tiny GPT.

## Files
- **`day1.html`** — open in a browser. Day-1 concept tables, a glossary where
  every term (softmax, cross-entropy, attention, …) is defined and linked to
  authoritative references, and the embedded code.
- **`train.py`** — a ~150-line, fully commented character-level GPT (same
  architecture as large models, tiny enough to train on a CPU).
- **`get_data.py`** — creates `input.txt` (downloads tiny Shakespeare, with an
  offline fallback).

## Run
```bash
pip install torch        # CPU build is fine
python get_data.py       # creates input.txt
python train.py          # trains, prints loss, generates a sample
```

**What to watch:** the initial loss should be ≈ `log(|V|)` (~4.17 for ~65
chars). It should fall steadily, and generated text should drift from gibberish
toward Shakespeare-ish English.

## Credit
Architecture and code adapted from Andrej Karpathy's
[nanoGPT](https://github.com/karpathy/nanoGPT) (MIT) and the
["Let's build GPT" lecture](https://www.youtube.com/watch?v=kCc8FmEb1nY).
Production reference for later stages:
[FareedKhan-dev/train-llm-from-scratch](https://github.com/FareedKhan-dev/train-llm-from-scratch).
