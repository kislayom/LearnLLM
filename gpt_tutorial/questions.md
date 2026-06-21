# My Questions Log

A running record of questions asked while learning, with short answers and where
to read more. (Maintained as we go — you can also capture questions yourself in
the in-page "My Questions & Notes" panel and export them here.)

## Day 1 — Foundations & attention

### Q1. Why don't we tokenize letter-by-letter?
We *can* (and do for learning — tiny vocab, fully transparent). But at scale,
characters make sequences ~5× longer, and attention cost is **quadratic** in
length, so ~25× more compute for the same text; they also waste model capacity
on spelling and fit less real text per context window. **BPE** (subword) is the
standard compromise: common words → one token, no out-of-vocabulary.
→ `day1.html` §2, glossary: tokenization, BPE.

### Q2. Why is attention "quadratic"?
Every token compares with every token → a `T × T` grid of comparisons, so cost
grows like `T²`. Double the length → 4× work; 10× → 100×.
→ `day1.html` §8 (with the O(T) vs O(T²) graph).

### Q3. Can we optimise it / skip some checks?
Yes. Causal masking already drops ~half. Beyond that: **sparse/local attention**
(`O(T·w)`), **linear attention** (`O(T)`, loses softmax sharpness),
**FlashAttention** (same maths, far less memory), and the **KV cache** (don't
redo past work during generation). Trade-off: exact-but-quadratic vs
approximate-but-cheap.
→ `day1.html` §8 note, glossary: sparse / linear / flash / kvcache.

### Q4. What is `softmax(Q·Kᵀ)`?
The dot products `Q·Kᵀ` form a `T × T` grid of query–key similarity scores;
softmax on each row turns them into attention weights (≥0, sum to 1) saying how
much each token attends to every other. Divide by `√d` to keep it trainable,
then multiply by `V` to blend the information.
→ `day1.html` §6 (attention dataflow) + §7 (causal grid).

### Q5. How can I save my questions & make the content dynamic?
Two ways to save: this `questions.md` log in the repo, and an in-page
**localStorage** notebook (with `.md`/`.json` export). "Dynamic" = added
JavaScript widgets so the maths becomes interactive (softmax playground,
gradient-descent simulator, attention weights, LR schedule, sampling).
→ all `dayN.html` pages now include these.

---

## Day 2 — Inside the block & training
_(add your questions here)_
