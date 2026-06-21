"""
Minimal character-level GPT — Day 1 of the "Train an LLM from scratch" tutorial.

This is a single-file, ~150-line GPT you can read top to bottom. It uses the
SAME architecture as large models (token + position embeddings -> transformer
blocks with self-attention -> output head), just tiny enough to train on a CPU
in a few minutes.

Architecture credit: this follows Andrej Karpathy's "Let's build GPT" / nanoGPT
(https://github.com/karpathy/nanoGPT, MIT licensed), adapted with extra comments
for learning.

Run:
    python get_data.py      # creates input.txt (tiny Shakespeare)
    python train.py
"""

import os
import torch
import torch.nn as nn
from torch.nn import functional as F

# ----------------------------------------------------------------------------
# Hyperparameters — the "knobs" you'll experiment with. Start small.
# ----------------------------------------------------------------------------
batch_size = 32          # how many independent sequences we process in parallel
block_size = 64          # context length: max tokens of history the model sees (T)
max_iters = 3000         # number of training steps
eval_interval = 300      # how often to print train/val loss
learning_rate = 3e-4     # step size for the optimizer (eta)
eval_iters = 100         # how many batches to average when estimating loss
n_embd = 128             # embedding dimension (model width, d)
n_head = 4               # number of attention heads (n_embd must divide by this)
n_layer = 4              # number of stacked transformer blocks
dropout = 0.1            # regularization: randomly zero some activations
device = "cuda" if torch.cuda.is_available() else "cpu"
torch.manual_seed(1337)  # reproducibility

# ----------------------------------------------------------------------------
# 1. DATA: read text, build a character-level tokenizer
# ----------------------------------------------------------------------------
if not os.path.exists("input.txt"):
    raise SystemExit("input.txt not found — run `python get_data.py` first.")

with open("input.txt", "r", encoding="utf-8") as f:
    text = f.read()

chars = sorted(set(text))          # the vocabulary: every unique character
vocab_size = len(chars)            # |V|
stoi = {c: i for i, c in enumerate(chars)}   # string -> int
itos = {i: c for i, c in enumerate(chars)}   # int -> string
encode = lambda s: [stoi[c] for c in s]               # text -> list[int]
decode = lambda l: "".join(itos[i] for i in l)        # list[int] -> text

data = torch.tensor(encode(text), dtype=torch.long)
n = int(0.9 * len(data))           # 90% train, 10% validation
train_data, val_data = data[:n], data[n:]


def get_batch(split):
    """Grab a random batch. x = context, y = x shifted left by one (the targets)."""
    d = train_data if split == "train" else val_data
    ix = torch.randint(len(d) - block_size, (batch_size,))
    x = torch.stack([d[i:i + block_size] for i in ix])
    y = torch.stack([d[i + 1:i + 1 + block_size] for i in ix])
    return x.to(device), y.to(device)


@torch.no_grad()
def estimate_loss():
    out = {}
    model.eval()
    for split in ["train", "val"]:
        losses = torch.zeros(eval_iters)
        for k in range(eval_iters):
            X, Y = get_batch(split)
            _, loss = model(X, Y)
            losses[k] = loss.item()
        out[split] = losses.mean().item()
    model.train()
    return out


# ----------------------------------------------------------------------------
# 2. MODEL: self-attention building blocks
# ----------------------------------------------------------------------------
class Head(nn.Module):
    """One head of causal self-attention: softmax(Q·Kᵀ / √d) · V with a causal mask."""

    def __init__(self, head_size):
        super().__init__()
        self.key = nn.Linear(n_embd, head_size, bias=False)     # W_K
        self.query = nn.Linear(n_embd, head_size, bias=False)   # W_Q
        self.value = nn.Linear(n_embd, head_size, bias=False)   # W_V
        # Lower-triangular matrix used to mask out the future (causal mask).
        self.register_buffer("tril", torch.tril(torch.ones(block_size, block_size)))
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        B, T, C = x.shape
        k = self.key(x)     # (B, T, head_size)
        q = self.query(x)   # (B, T, head_size)
        # Raw similarity scores Q·Kᵀ, scaled by 1/√(head_size).
        wei = q @ k.transpose(-2, -1) * k.shape[-1] ** -0.5   # (B, T, T)
        # Causal mask: a token cannot attend to future positions.
        wei = wei.masked_fill(self.tril[:T, :T] == 0, float("-inf"))
        wei = F.softmax(wei, dim=-1)        # attention weights (each row sums to 1)
        wei = self.dropout(wei)
        v = self.value(x)                   # (B, T, head_size)
        return wei @ v                      # weighted average of values -> (B, T, head_size)


class MultiHeadAttention(nn.Module):
    """Several attention heads in parallel, then project back to n_embd."""

    def __init__(self, num_heads, head_size):
        super().__init__()
        self.heads = nn.ModuleList([Head(head_size) for _ in range(num_heads)])
        self.proj = nn.Linear(n_embd, n_embd)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        out = torch.cat([h(x) for h in self.heads], dim=-1)
        return self.dropout(self.proj(out))


class FeedForward(nn.Module):
    """Position-wise MLP: lets each token 'think' on the info it gathered."""

    def __init__(self, n_embd):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_embd, 4 * n_embd),
            nn.ReLU(),
            nn.Linear(4 * n_embd, n_embd),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        return self.net(x)


class Block(nn.Module):
    """One transformer block: attention + feed-forward, each with a residual + LayerNorm."""

    def __init__(self, n_embd, n_head):
        super().__init__()
        head_size = n_embd // n_head
        self.sa = MultiHeadAttention(n_head, head_size)
        self.ffwd = FeedForward(n_embd)
        self.ln1 = nn.LayerNorm(n_embd)
        self.ln2 = nn.LayerNorm(n_embd)

    def forward(self, x):
        x = x + self.sa(self.ln1(x))    # residual around attention
        x = x + self.ffwd(self.ln2(x))  # residual around feed-forward
        return x


class GPT(nn.Module):
    def __init__(self):
        super().__init__()
        self.token_embedding_table = nn.Embedding(vocab_size, n_embd)
        self.position_embedding_table = nn.Embedding(block_size, n_embd)
        self.blocks = nn.Sequential(*[Block(n_embd, n_head) for _ in range(n_layer)])
        self.ln_f = nn.LayerNorm(n_embd)
        self.lm_head = nn.Linear(n_embd, vocab_size)

    def forward(self, idx, targets=None):
        B, T = idx.shape
        tok_emb = self.token_embedding_table(idx)                       # (B, T, n_embd)
        pos_emb = self.position_embedding_table(torch.arange(T, device=device))  # (T, n_embd)
        x = tok_emb + pos_emb
        x = self.blocks(x)
        x = self.ln_f(x)
        logits = self.lm_head(x)                                        # (B, T, vocab_size)

        if targets is None:
            loss = None
        else:
            B, T, C = logits.shape
            loss = F.cross_entropy(logits.view(B * T, C), targets.view(B * T))
        return logits, loss

    @torch.no_grad()
    def generate(self, idx, max_new_tokens):
        for _ in range(max_new_tokens):
            idx_cond = idx[:, -block_size:]     # crop to context length
            logits, _ = self(idx_cond)
            logits = logits[:, -1, :]           # focus on the last time step
            probs = F.softmax(logits, dim=-1)   # convert to probabilities
            idx_next = torch.multinomial(probs, num_samples=1)  # sample
            idx = torch.cat((idx, idx_next), dim=1)
        return idx


# ----------------------------------------------------------------------------
# 3. TRAIN
# ----------------------------------------------------------------------------
model = GPT().to(device)
print(f"{sum(p.numel() for p in model.parameters()) / 1e6:.2f}M parameters | device={device}")
print(f"vocab_size={vocab_size} | expected initial loss ≈ {torch.log(torch.tensor(float(vocab_size))):.3f}")

optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

for it in range(max_iters):
    if it % eval_interval == 0 or it == max_iters - 1:
        losses = estimate_loss()
        print(f"step {it:5d}: train loss {losses['train']:.4f}, val loss {losses['val']:.4f}")

    xb, yb = get_batch("train")
    logits, loss = model(xb, yb)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()

# ----------------------------------------------------------------------------
# 4. GENERATE a sample
# ----------------------------------------------------------------------------
print("\n----- sample -----")
context = torch.zeros((1, 1), dtype=torch.long, device=device)
print(decode(model.generate(context, max_new_tokens=500)[0].tolist()))
