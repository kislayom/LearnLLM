# GPT Tutorial — Train an LLM from Scratch

A learn-by-building course with **interactive** lessons and a runnable tiny GPT.

## Lessons (open in a browser)
- **`index.html`** — course home: links the lessons, shows your saved progress
  across days, quick-start, and the notes panel. **Start here.**
- **`day1.html`** — Foundations & self-attention: theory, maths, 9 SVG diagrams,
  glossary with linked references, and **interactive widgets** (softmax playground,
  gradient-descent simulator, attention weights).
- **`day2.html`** — The transformer block & training: positional embeddings,
  residuals, LayerNorm, multi-head attention, the Adam optimizer, learning-rate
  schedule, and sampling — with diagrams and widgets (LR schedule, temperature/top-k).

Both pages share:
- **My Questions & Notes** panel — saved in your browser (localStorage), with
  `.md`/`.json` export. Carries over between days.
- **Progress checkboxes** per section, with a progress bar.

## Code
- **`train.py`** — ~150-line commented character-level GPT (runs on CPU).
- **`get_data.py`** — fetch a dataset into `input.txt`.
- **`DATA.md`** — guide to good datasets (and bigger ones for later).
- **`questions.md`** — running log of questions & answers.

## Run
```bash
pip install torch                 # CPU build is fine
python get_data.py                # tiny shakespeare (or: tinystories, sherlock)
python get_data.py --list         # see all dataset options
python train.py                   # trains, prints loss, generates a sample
```

**What to watch:** initial loss ≈ `log(|V|)` (~4.17 for ~65 chars), falling
steadily, with generated text drifting from gibberish toward real English.

## Assets
- `assets/app.css`, `assets/app.js` — shared styles + interactivity for the pages.

## Credit
Architecture & code adapted from Andrej Karpathy's
[nanoGPT](https://github.com/karpathy/nanoGPT) (MIT) and the
["Let's build GPT" lecture](https://www.youtube.com/watch?v=kCc8FmEb1nY).
Production reference for later stages:
[FareedKhan-dev/train-llm-from-scratch](https://github.com/FareedKhan-dev/train-llm-from-scratch).
