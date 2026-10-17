#!/usr/bin/env python
"""LoRA SFT on chat JSONL with completions-only loss (only the assistant answer is trained).

Data: one JSON object per line
    {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", "content": "B"}],
     "meta": {"type": "abcd", ...}}
The last message must be the assistant answer. Every token of the rendered chat template up to and
including the assistant header gets label -100; the answer tokens and the end-of-turn token(s) are trained.

Backends: unsloth (default when importable, bf16 LoRA, no 4-bit) or plain transformers+PEFT.

Outputs in <runs-dir>/<name>/:
    config.json          all arguments + resolved base/backend/versions
    data_stats.json      token lengths, dropped examples, one decoded example with the trained span marked
    train_log.jsonl      Trainer log history (loss, lr, eval_loss, grad_norm ...)
    metrics.json         final numbers: losses, runtime, tokens/s, peak memory, generation exact match
    gen_eval.jsonl       greedy generations on the eval split (adapter on, and adapter off with --gen-eval-base)
    adapter/             PEFT adapter (adapter_model.safetensors + adapter_config.json + tokenizer)

Example (L40S):
    source /workspace/env.sh
    /workspace/venvs/train/bin/python train/train_lora.py --data data/train.jsonl --eval-frac 0.03 \\
        --base speakleash/Bielik-11B-v3.0-Instruct --name bielik11b-r16-e1 --r 16 --alpha 32 --lr 1e-4 --epochs 1
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, nargs="+", help="training JSONL file(s)")
    ap.add_argument("--eval-data", nargs="*", default=None, help="eval JSONL (default: --eval-frac of --data)")
    ap.add_argument("--eval-frac", type=float, default=0.03, help="held-out fraction when --eval-data is not given")
    ap.add_argument("--eval-max", type=int, default=400, help="cap on eval examples used for eval loss")
    ap.add_argument("--base", required=True, help="HF repo id or local dir of the base model (safetensors)")
    ap.add_argument("--name", required=True, help="run name -> <runs-dir>/<name>")
    ap.add_argument("--runs-dir", default=os.environ.get("RUNS_DIR", "/workspace/runs"))
    ap.add_argument("--backend", choices=["auto", "unsloth", "peft"], default="auto")
    ap.add_argument("--r", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=None, help="lora_alpha (default 2*r)")
    ap.add_argument("--dropout", type=float, default=0.0)
    ap.add_argument("--target-modules", default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj")
    ap.add_argument("--rslora", action="store_true")
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--max-steps", type=int, default=-1, help="overrides --epochs when > 0")
    ap.add_argument("--warmup", type=float, default=0.03, help="warmup fraction of total steps")
    ap.add_argument("--scheduler", default="cosine")
    ap.add_argument("--weight-decay", type=float, default=0.0)
    ap.add_argument("--max-seq-len", type=int, default=3072)
    ap.add_argument("--too-long", choices=["drop", "truncate-left"], default="drop",
                    help="examples longer than max-seq-len: drop them, or cut prompt tokens from the start")
    ap.add_argument("--batch", type=int, default=4, help="per-device batch size")
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--logging-steps", type=int, default=5)
    ap.add_argument("--eval-steps", type=int, default=0, help="0 = eval ~5 times per run")
    ap.add_argument("--save-steps", type=int, default=0, help="0 = only the final adapter")
    ap.add_argument("--optim", default="adamw_torch_fused")
    ap.add_argument("--no-grad-ckpt", action="store_true")
    ap.add_argument("--chat-template-kwargs", default="",
                    help='JSON passed to apply_chat_template, e.g. \'{"enable_thinking": false}\' for Qwen3 '
                         '(must match the llama-server --chat-template-kwargs used at inference)')
    ap.add_argument("--pf-numbered", action="store_true",
                    help='rewrite pf answers "P, F, P" -> "1: P\\n2: F\\n3: P" (the format the harness prompt + '
                         'GBNF ask for) when meta.type == "pf"')
    ap.add_argument("--gen-eval-n", type=int, default=128, help="greedy generations on eval split (0 = off)")
    ap.add_argument("--gen-eval-base", action="store_true", help="also generate with the adapter disabled")
    ap.add_argument("--gen-max-new", type=int, default=24)
    ap.add_argument("--dry-run", action="store_true", help="tokenize + stats + show masked example, no training")
    ap.add_argument("--limit", type=int, default=0, help="use only the first N training examples")
    return ap.parse_args(argv)


ARGS = parse_args()

HAVE_UNSLOTH = False
if ARGS.backend in ("auto", "unsloth") and not ARGS.dry_run:
    try:
        import unsloth  # noqa: F401  (must be imported before transformers/peft/trl)
        from unsloth import FastLanguageModel
        HAVE_UNSLOTH = True
    except Exception as e:  # pragma: no cover
        if ARGS.backend == "unsloth":
            raise
        print(f"[warn] unsloth not importable ({type(e).__name__}: {e}); falling back to transformers+PEFT")

import torch  # noqa: E402
from transformers import (AutoTokenizer, Trainer, TrainerCallback, TrainingArguments,  # noqa: E402
                          set_seed)


# ----------------------------------------------------------------------------- data
def read_jsonl(paths):
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                msgs = r.get("messages") or []
                if not msgs or msgs[-1].get("role") != "assistant":
                    raise ValueError(f"{p}:{i + 1}: last message must be the assistant answer")
                r.setdefault("meta", {})
                r["meta"].setdefault("_src", f"{os.path.basename(p)}:{i + 1}")
                rows.append(r)
    return rows


PF_RE = re.compile(r"^\s*[PF](\s*,\s*[PF])*\s*$")


def maybe_pf_numbered(rows):
    n = 0
    for r in rows:
        a = r["messages"][-1]
        if (r["meta"].get("type") == "pf") and PF_RE.match(a["content"]):
            vals = re.findall(r"[PF]", a["content"])
            a["content"] = "\n".join(f"{i}: {v}" for i, v in enumerate(vals, 1))
            n += 1
    return n


def _ids(x):
    """apply_chat_template(tokenize=True) returns a list in transformers 4 and a BatchEncoding in 5."""
    if isinstance(x, dict) or hasattr(x, "keys"):
        x = x["input_ids"]
    if x and isinstance(x[0], list):
        x = x[0]
    return list(x)


END_OF_TURN = ("<|im_end|>", "<end_of_turn>", "<|eot_id|>", "<turn|>", "<|end|>", "</s>")


def stop_token_ids(tok):
    ids = {tok.eos_token_id} if tok.eos_token_id is not None else set()
    vocab = tok.get_vocab()
    for t in END_OF_TURN:
        if t in vocab:
            ids.add(vocab[t])
    return ids


class Encoder:
    def __init__(self, tok, max_len, too_long, tmpl_kwargs):
        self.tok, self.max_len, self.too_long, self.kw = tok, max_len, too_long, tmpl_kwargs
        self.fallback_used = 0
        self.boundary_mismatch = 0
        self.stop_ids = stop_token_ids(tok)

    def split(self, msgs):
        """Rendered (prompt_text, completion_text). prompt ends right before the answer tokens."""
        prompt = self.tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True, **self.kw)
        full = self.tok.apply_chat_template(msgs, tokenize=False, **self.kw)
        if full.startswith(prompt):
            return prompt, full[len(prompt):]
        # template renders the last assistant turn differently from the generation prompt (e.g. reasoning
        # blocks): train only from the answer text onwards.
        ans = msgs[-1]["content"]
        k = full.rfind(ans)
        if k < 0:
            raise ValueError("assistant content not found in rendered template")
        self.fallback_used += 1
        return full[:k], full[k:]

    def __call__(self, row):
        prompt, completion = self.split(row["messages"])
        # Tokenize the FULL text once and split at the prompt boundary. Tokenizing the completion on its own
        # is wrong for SentencePiece vocabularies (Bielik/Mistral): it adds a dummy-prefix "▁" ("▁C" instead
        # of "C"), which the model never produces after "assistant\n" and which a GBNF grammar rejects.
        p_ids = self.tok(prompt, add_special_tokens=False)["input_ids"]
        f_ids = self.tok(prompt + completion, add_special_tokens=False)["input_ids"]
        b = len(p_ids)
        if f_ids[:b] != p_ids:  # boundary token merged across prompt/answer: keep the common prefix masked
            b = next((i for i, (x, y) in enumerate(zip(p_ids, f_ids)) if x != y), min(len(p_ids), len(f_ids)))
            self.boundary_mismatch += 1
        p_ids, c_ids = f_ids[:b], f_ids[b:]
        # train up to and including the first end-of-turn token; what the template puts after it ("\n", or
        # "▁" + "\n" with SentencePiece) is never generated (llama-server stops at EOG) and only adds noise
        for k, t in enumerate(c_ids):
            if t in self.stop_ids:
                c_ids = c_ids[:k + 1]
                break
        n = len(p_ids) + len(c_ids)
        truncated = False
        if n > self.max_len:
            if self.too_long == "drop":
                return None
            cut = n - self.max_len
            if cut >= len(p_ids):
                return None
            p_ids = p_ids[cut:]
            truncated = True
        return {"input_ids": p_ids + c_ids, "labels": [-100] * len(p_ids) + c_ids, "length": len(p_ids) + len(c_ids),
                "n_completion": len(c_ids), "truncated": truncated, "prompt_ids": p_ids,
                "answer": row["messages"][-1]["content"], "type": row["meta"].get("type", ""),
                "src": row["meta"].get("_src", "")}


class Collator:
    def __init__(self, pad_id):
        self.pad_id = pad_id

    def __call__(self, feats):
        m = max(len(f["input_ids"]) for f in feats)
        ids = torch.full((len(feats), m), self.pad_id, dtype=torch.long)
        lab = torch.full((len(feats), m), -100, dtype=torch.long)
        att = torch.zeros((len(feats), m), dtype=torch.long)
        for i, f in enumerate(feats):
            n = len(f["input_ids"])
            ids[i, :n] = torch.tensor(f["input_ids"])
            lab[i, :n] = torch.tensor(f["labels"])
            att[i, :n] = 1
        return {"input_ids": ids, "labels": lab, "attention_mask": att}


class ListDataset(torch.utils.data.Dataset):
    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        return {"input_ids": r["input_ids"], "labels": r["labels"], "length": r["length"]}


# ----------------------------------------------------------------------------- model
def load_model(args, tok_kwargs):
    token = os.environ.get("HF_TOKEN") or None
    alpha = args.alpha or 2 * args.r
    targets = [t.strip() for t in args.target_modules.split(",") if t.strip()]
    if HAVE_UNSLOTH:
        kw = dict(model_name=args.base, max_seq_length=args.max_seq_len, dtype=torch.bfloat16, load_in_4bit=False,
                  load_in_8bit=False, full_finetuning=False, token=token)
        try:
            model, tok = FastLanguageModel.from_pretrained(use_exact_model_name=True, **kw)
        except TypeError:
            model, tok = FastLanguageModel.from_pretrained(**kw)
        if hasattr(tok, "tokenizer") and not hasattr(tok, "get_vocab"):  # multimodal processor (e.g. Qwen3.5)
            tok = tok.tokenizer
        model = FastLanguageModel.get_peft_model(
            model, r=args.r, lora_alpha=alpha, lora_dropout=args.dropout, target_modules=targets, bias="none",
            use_gradient_checkpointing=(False if args.no_grad_ckpt else "unsloth"), random_state=args.seed,
            use_rslora=args.rslora, max_seq_length=args.max_seq_len)
        return model, tok, "unsloth"

    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM
    tok = AutoTokenizer.from_pretrained(args.base, token=token)
    model = AutoModelForCausalLM.from_pretrained(args.base, dtype=torch.bfloat16, attn_implementation="sdpa",
                                                 device_map={"": 0}, token=token)
    if not args.no_grad_ckpt:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    # regex: only language-model linears (multimodal checkpoints also have q_proj etc. in the vision tower,
    # which convert_lora_to_gguf cannot map onto the text GGUF)
    rx = r"^(?!.*(vision|visual|audio|multi_modal|mm_projector|embed_vision)).*\.(" + "|".join(targets) + r")$"
    cfg = LoraConfig(r=args.r, lora_alpha=alpha, lora_dropout=args.dropout, target_modules=rx, bias="none",
                     task_type="CAUSAL_LM", use_rslora=args.rslora)
    model = get_peft_model(model, cfg)
    return model, tok, "peft"


# ----------------------------------------------------------------------------- generation eval
def squash(s):
    return re.sub(r"[\s\.,;:\-–—\"'„”()\[\]]+", "", s or "").upper()


@torch.no_grad()
def generate(model, tok, rows, max_new, bs=16):
    model.eval()
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    eos = sorted(stop_token_ids(tok))
    outs = []
    order = sorted(range(len(rows)), key=lambda i: len(rows[i]["prompt_ids"]))
    res = [None] * len(rows)
    for s in range(0, len(order), bs):
        idx = order[s:s + bs]
        m = max(len(rows[i]["prompt_ids"]) for i in idx)
        ids = torch.full((len(idx), m), pad, dtype=torch.long)
        att = torch.zeros((len(idx), m), dtype=torch.long)
        for j, i in enumerate(idx):
            p = rows[i]["prompt_ids"]
            ids[j, m - len(p):] = torch.tensor(p)
            att[j, m - len(p):] = 1
        g = model.generate(input_ids=ids.cuda(), attention_mask=att.cuda(), max_new_tokens=max_new, do_sample=False,
                           eos_token_id=eos, pad_token_id=pad)
        for j, i in enumerate(idx):
            res[i] = tok.decode(g[j, m:], skip_special_tokens=True).strip()
    for i, r in enumerate(rows):
        outs.append({"src": r["src"], "type": r["type"], "gold": r["answer"], "pred": res[i],
                     "exact": squash(res[i]) == squash(r["answer"])})
    return outs


def summarize(gens):
    by = {}
    for g in gens:
        by.setdefault(g["type"] or "-", []).append(g["exact"])
    return {"n": len(gens), "exact": round(sum(g["exact"] for g in gens) / max(1, len(gens)), 4),
            "per_type": {t: round(sum(v) / len(v), 3) for t, v in sorted(by.items())}}


# ----------------------------------------------------------------------------- main
class JsonlLogger(TrainerCallback):
    def __init__(self, path):
        self.path = path

    def on_log(self, args, state, control, logs=None, **kw):
        if logs:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"step": state.global_step, "epoch": state.epoch, "t": round(time.time(), 1),
                                    **logs}) + "\n")


def main():
    args = ARGS
    bad = [p for p in args.data if "devset" in os.path.abspath(p).replace("\\", "/").split("/")]
    if bad:  # repo rule: dev sets are evaluation-only
        sys.exit(f"refusing to train on dev-set files: {bad}")
    t0 = time.time()
    set_seed(args.seed)
    run = os.path.join(args.runs_dir, args.name)
    os.makedirs(run, exist_ok=True)
    tmpl_kwargs = json.loads(args.chat_template_kwargs) if args.chat_template_kwargs else {}

    train_rows = read_jsonl(args.data)
    if args.limit:
        train_rows = train_rows[: args.limit]
    if args.eval_data:
        eval_rows = read_jsonl(args.eval_data)
    else:
        rnd = random.Random(args.seed)
        rnd.shuffle(train_rows)
        k = max(1, int(round(len(train_rows) * args.eval_frac))) if args.eval_frac > 0 else 0
        eval_rows, train_rows = train_rows[:k], train_rows[k:]
    if args.pf_numbered:
        print(f"pf answers rewritten to numbered lines: {maybe_pf_numbered(train_rows) + maybe_pf_numbered(eval_rows)}")

    if args.dry_run:
        tok = AutoTokenizer.from_pretrained(args.base, token=os.environ.get("HF_TOKEN") or None)
        model, backend = None, "dry-run"
    else:
        model, tok, backend = load_model(args, tmpl_kwargs)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    enc = Encoder(tok, args.max_seq_len, args.too_long, tmpl_kwargs)
    tr = [e for e in (enc(r) for r in train_rows) if e is not None]
    ev = [e for e in (enc(r) for r in eval_rows) if e is not None]
    lens = sorted(e["length"] for e in tr) or [0]
    stats = {
        "train_in": len(train_rows), "train_kept": len(tr), "eval_in": len(eval_rows), "eval_kept": len(ev),
        "dropped_or_truncated_over_max_len": len(train_rows) - len(tr) + sum(e["truncated"] for e in tr),
        "template_fallback_used": enc.fallback_used, "boundary_token_mismatch": enc.boundary_mismatch,
        "len_mean": round(sum(lens) / len(lens), 1), "len_p50": lens[len(lens) // 2],
        "len_p95": lens[int(0.95 * (len(lens) - 1))], "len_max": lens[-1],
        "train_tokens": sum(lens), "supervised_tokens": sum(e["n_completion"] for e in tr),
        "types": {t: sum(1 for e in tr if e["type"] == t) for t in sorted({e["type"] for e in tr})},
    }
    if tr:
        e = tr[0]
        p = tok.decode(e["prompt_ids"][-60:])
        c = tok.decode(e["input_ids"][len(e["prompt_ids"]):])
        stats["example_tail_of_prompt_masked"] = p
        stats["example_trained_span"] = c
        print("---- masked prompt tail:\n" + p + "\n---- trained span (repr): " + repr(c))
    with open(os.path.join(run, "data_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in stats.items() if not k.startswith("example")}, ensure_ascii=False))
    if args.dry_run:
        return
    ev_loss_rows = ev[: args.eval_max]

    eff_bs = args.batch * args.grad_accum
    steps_per_epoch = max(1, (len(tr) + eff_bs - 1) // eff_bs)
    total_steps = args.max_steps if args.max_steps > 0 else int(steps_per_epoch * args.epochs + 0.999)
    eval_steps = args.eval_steps or max(1, total_steps // 5)
    ta = dict(output_dir=os.path.join(run, "ckpt"), per_device_train_batch_size=args.batch,
              per_device_eval_batch_size=args.batch, gradient_accumulation_steps=args.grad_accum,
              learning_rate=args.lr, num_train_epochs=args.epochs, max_steps=args.max_steps,
              lr_scheduler_type=args.scheduler, warmup_steps=int(round(args.warmup * total_steps)),
              weight_decay=args.weight_decay, bf16=True, logging_steps=args.logging_steps,
              eval_strategy="steps" if ev_loss_rows else "no", eval_steps=eval_steps,
              save_strategy="steps" if args.save_steps else "no", save_steps=args.save_steps or 500,
              save_total_limit=2, report_to=[], seed=args.seed, data_seed=args.seed, optim=args.optim,
              remove_unused_columns=False, dataloader_num_workers=0, max_grad_norm=1.0)
    try:
        targs = TrainingArguments(train_sampling_strategy="group_by_length", **ta)
    except TypeError:
        targs = TrainingArguments(group_by_length=True, **ta)

    cfg = {**vars(args), "backend": backend, "alpha_resolved": args.alpha or 2 * args.r, "total_steps": total_steps,
           "effective_batch": eff_bs, "torch": torch.__version__,
           "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
    try:
        import peft, transformers, trl  # noqa: E401
        cfg.update(transformers=transformers.__version__, peft=peft.__version__, trl=trl.__version__)
        if HAVE_UNSLOTH:
            cfg["unsloth"] = unsloth.__version__
    except Exception:
        pass
    with open(os.path.join(run, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    open(os.path.join(run, "train_log.jsonl"), "w").close()

    trainer = Trainer(model=model, args=targs, train_dataset=ListDataset(tr),
                      eval_dataset=ListDataset(ev_loss_rows) if ev_loss_rows else None,
                      data_collator=Collator(tok.pad_token_id), callbacks=[JsonlLogger(os.path.join(run, "train_log.jsonl"))])
    torch.cuda.reset_peak_memory_stats()
    t_load = time.time() - t0
    print(f"backend={backend} train={len(tr)} eval={len(ev_loss_rows)} steps={total_steps} eff_bs={eff_bs} "
          f"load={t_load:.0f}s", flush=True)
    out = trainer.train()
    t_train = out.metrics.get("train_runtime", 0.0)
    epochs_done = out.metrics.get("epoch", args.epochs) or args.epochs
    metrics = {"backend": backend, "train_loss": out.training_loss, "steps": out.global_step,
               "train_runtime_s": round(t_train, 1), "load_s": round(t_load, 1),
               "train_tokens_per_s": round(stats["train_tokens"] * epochs_done / max(t_train, 1e-9), 1)
               if args.max_steps <= 0 else round(sum(e["length"] for e in tr) / len(tr) * eff_bs * out.global_step
                                                 / max(t_train, 1e-9), 1),
               "peak_mem_alloc_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
               "peak_mem_reserved_gb": round(torch.cuda.max_memory_reserved() / 1e9, 2)}
    if ev_loss_rows:
        metrics["eval_loss"] = trainer.evaluate()["eval_loss"]

    adir = os.path.join(run, "adapter")
    model.save_pretrained(adir)
    tok.save_pretrained(adir)
    acfg_p = os.path.join(adir, "adapter_config.json")
    with open(acfg_p, encoding="utf-8") as f:
        acfg = json.load(f)
    acfg["base_model_name_or_path"] = args.base  # unsloth may record its own mirror name
    with open(acfg_p, "w", encoding="utf-8") as f:
        json.dump(acfg, f, indent=2)
    print(f"adapter -> {adir}")

    if args.gen_eval_n and ev:
        rows = ev[: args.gen_eval_n]
        if HAVE_UNSLOTH:
            FastLanguageModel.for_inference(model)
        tg = time.time()
        gens = generate(model, tok, rows, args.gen_max_new)
        metrics["gen_eval"] = summarize(gens)
        metrics["gen_eval_s"] = round(time.time() - tg, 1)
        base_gens = []
        if args.gen_eval_base:
            with model.disable_adapter():
                base_gens = generate(model, tok, rows, args.gen_max_new)
            metrics["gen_eval_base"] = summarize(base_gens)
        with open(os.path.join(run, "gen_eval.jsonl"), "w", encoding="utf-8") as f:
            for i, g in enumerate(gens):
                if base_gens:
                    g = {**g, "pred_base": base_gens[i]["pred"], "exact_base": base_gens[i]["exact"]}
                f.write(json.dumps(g, ensure_ascii=False) + "\n")

    metrics["wall_s"] = round(time.time() - t0, 1)
    with open(os.path.join(run, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
    print("METRICS " + json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
