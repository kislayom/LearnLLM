# Datasets for training your tiny LLM

Fetch any of these with `python get_data.py <name>` (writes `input.txt`).
Pick based on what you want to *see* the model do.

| Name | Command | Size | Why use it |
|---|---|---|---|
| **Tiny Shakespeare** | `python get_data.py shakespeare` | ~1 MB | The classic. Char-level model produces recognizable Shakespeare-ish text fast. Best first run. |
| **TinyStories** | `python get_data.py tinystories` | ~20 MB | Short, simple children's stories with a tiny vocabulary. **Even a small model writes coherent, grammatical English** — the most satisfying result for a from-scratch model. |
| **Sherlock Holmes** | `python get_data.py sherlock` | ~600 KB | Public-domain prose (Project Gutenberg). Richer vocabulary than Shakespeare; fun for narrative text. |

## Which should I pick?
- **Day 1, first run:** `shakespeare` — small and quick, you'll see loss fall and text improve in minutes.
- **Want the model to actually "make sense":** `tinystories` — designed so small models learn real grammar and simple reasoning. Train a bit longer.
- **Your own text:** drop any UTF-8 `.txt` file in this folder as `input.txt` and run `train.py`. Your notes, a book, code — anything works.

## Bigger / more serious corpora (for later, when you move to BPE)
These are larger and usually loaded via the HuggingFace `datasets` library rather than a single file:

- **WikiText-103** — clean Wikipedia articles (~500 MB). Good standard LM benchmark.
- **OpenWebText** — open reproduction of GPT-2's training data (~38 GB).
- **The Pile** — the 800 GB dataset used by the production
  [reference repo](https://github.com/FareedKhan-dev/train-llm-from-scratch).
- **FineWeb / FineWeb-Edu** — large, high-quality filtered web text for modern pretraining.

> Rule of thumb: character-level + a single `.txt` is perfect for *learning*.
> Switch to subword (BPE) tokenization and a HuggingFace dataset only when you
> outgrow these — your model code barely changes, just the tokenizer and the
> data loader.

## Licensing note
Tiny Shakespeare and Project Gutenberg texts are public domain. TinyStories is
released under a permissive license for research/learning. Always check a
dataset's license before using it beyond personal experimentation.
