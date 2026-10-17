"""All runtime configuration, read from environment variables (one place)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return default if v is None or v == "" else v


def _int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(_env(name, str(default)))


def _bool(name: str, default: bool) -> bool:
    return _env(name, "1" if default else "0").lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # LLM backend (llama-server OpenAI API)
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", "http://127.0.0.1:18080/v1").rstrip("/"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "bielik-11b-v3"))
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY", "none"))
    # /base passthrough target. Repo rule: the base benchmark must run on a SEPARATE llama-server with the
    # untouched registered GGUF and no LoRA -> point this at it once the RAG model differs from the base.
    base_llm_base_url: str = field(default_factory=lambda: _env("BASE_LLM_BASE_URL", _env("LLM_BASE_URL", "http://127.0.0.1:18080/v1")).rstrip("/"))
    llm_timeout: float = field(default_factory=lambda: _float("LLM_TIMEOUT", 600.0))
    llm_concurrency: int = field(default_factory=lambda: _int("LLM_CONCURRENCY", 4))
    # extra body merged into every LLM request (JSON), e.g. '{"chat_template_kwargs":{"enable_thinking":false}}'
    llm_extra_body: str = field(default_factory=lambda: _env("LLM_EXTRA_BODY", ""))
    # prepend "/no_think" to the user message (Qwen3 hybrid models)
    no_think_tag: bool = field(default_factory=lambda: _bool("NO_THINK_TAG", False))

    # Server
    harness_host: str = field(default_factory=lambda: _env("HARNESS_HOST", "127.0.0.1"))
    harness_port: int = field(default_factory=lambda: _int("HARNESS_PORT", 18000))
    public_model_name: str = field(default_factory=lambda: _env("PUBLIC_MODEL_NAME", "wmt-matura-rag"))
    base_model_name: str = field(default_factory=lambda: _env("BASE_MODEL_NAME", "base"))
    request_log: str = field(default_factory=lambda: _env("REQUEST_LOG", "logs/harness-requests.jsonl"))

    # Retrieval
    kb_index_dir: str = field(default_factory=lambda: _env("KB_INDEX_DIR", ""))
    use_kb: bool = field(default_factory=lambda: _bool("USE_KB", True))
    top_k: int = field(default_factory=lambda: _int("TOP_K", 5))            # chunks kept in the prompt (max)
    per_query_k: int = field(default_factory=lambda: _int("PER_QUERY_K", 8))  # hits fetched per sub-query
    ctx_tokens: int = field(default_factory=lambda: _int("CTX_TOKENS", 1200))  # context budget (approx tokens)
    chunk_max_chars: int = field(default_factory=lambda: _int("CHUNK_MAX_CHARS", 1500))
    chars_per_token: float = field(default_factory=lambda: _float("CHARS_PER_TOKEN", 3.3))

    # Generation
    temperature: float = field(default_factory=lambda: _float("TEMPERATURE", 0.0))
    n_votes: int = field(default_factory=lambda: _int("N_VOTES", 0))        # extra sampled votes (0 = greedy only)
    vote_temperature: float = field(default_factory=lambda: _float("VOTE_TEMPERATURE", 0.6))
    use_grammar: bool = field(default_factory=lambda: _bool("USE_GRAMMAR", True))
    think: bool = field(default_factory=lambda: _bool("THINK", False))      # short reasoning before answer
    think_max_tokens: int = field(default_factory=lambda: _int("THINK_MAX_TOKENS", 600))
    open_max_tokens: int = field(default_factory=lambda: _int("OPEN_MAX_TOKENS", 48))
    generic_max_tokens: int = field(default_factory=lambda: _int("GENERIC_MAX_TOKENS", 400))
    pf_mode: str = field(default_factory=lambda: _env("PF_MODE", "joint"))          # joint | split
    chrono_mode: str = field(default_factory=lambda: _env("CHRONO_MODE", "hybrid"))  # direct | years | hybrid
    keep_caller_system: bool = field(default_factory=lambda: _bool("KEEP_CALLER_SYSTEM", True))

    # ---- harness v2 (all default OFF = original behaviour) ----
    # QTYPE_V2: command-aware type detection (two-sentence ABCD, wrapped P/F statements, letter->number
    # matching, explanation mode for wyjaśnij/uzasadnij/rozstrzygnij, detection on the command not the sources)
    qtype_v2: bool = field(default_factory=lambda: _bool("QTYPE_V2", False))
    explain_max_tokens: int = field(default_factory=lambda: _int("EXPLAIN_MAX_TOKENS", 400))
    # essay mode (QTYPE_V2=1, type 'essay', harness/essay.py): CKE 'wypracowanie', min. 300 words, 12-15 pts.
    # Needs >= ~8k tokens of context per llama-server slot (ESSAY_CTX_TOKENS + prompt + ESSAY_MAX_TOKENS).
    essay_max_tokens: int = field(default_factory=lambda: _int("ESSAY_MAX_TOKENS", 1400))
    essay_temperature: float = field(default_factory=lambda: _float("ESSAY_TEMPERATURE", 0.3))
    # token-level repeat penalty > 1 made Bielik-4.5B misspell words it must repeat ("uniia"); DRY penalises only
    # repeated sequences longer than ESSAY_DRY_ALLOWED tokens (loops) and leaves repeated names alone
    essay_repeat_penalty: float = field(default_factory=lambda: _float("ESSAY_REPEAT_PENALTY", 1.0))
    essay_dry_multiplier: float = field(default_factory=lambda: _float("ESSAY_DRY_MULTIPLIER", 0.5))
    essay_dry_allowed: int = field(default_factory=lambda: _int("ESSAY_DRY_ALLOWED", 6))
    essay_ctx_tokens: int = field(default_factory=lambda: _int("ESSAY_CTX_TOKENS", 4500))
    essay_top_k: int = field(default_factory=lambda: _int("ESSAY_TOP_K", 12))
    essay_rerank_topn: int = field(default_factory=lambda: _int("ESSAY_RERANK_TOPN", 40))
    essay_min_words: int = field(default_factory=lambda: _int("ESSAY_MIN_WORDS", 350))  # below -> ESSAY_FALLBACK
    # sections = write it again part by part (intro, one call per aspect paragraph, conclusion; guaranteed length),
    # rewrite = one 'write it longer' call, none = keep the single-pass essay. The longer result is kept.
    essay_fallback: str = field(default_factory=lambda: _env("ESSAY_FALLBACK", "sections"))
    essay_topic: int = field(default_factory=lambda: _int("ESSAY_TOPIC", 0))          # 0 = best retrieval coverage
    # LoRA adapters were trained on short answers only: send per-request scale 0 for every adapter loaded in
    # llama-server (GET /lora-adapters; nothing is sent when none is loaded)
    essay_lora_off: bool = field(default_factory=lambda: _bool("ESSAY_LORA_OFF", True))
    # RERANK: cross-encoder rerank of BM25 candidates (bge-reranker-v2-m3 GGUF on a llama-server --reranking)
    rerank: bool = field(default_factory=lambda: _bool("RERANK", False))
    rerank_backend: str = field(default_factory=lambda: _env("RERANK_BACKEND", "llama"))  # llama | st
    rerank_url: str = field(default_factory=lambda: _env("RERANK_URL", "http://127.0.0.1:18092").rstrip("/"))
    rerank_model: str = field(default_factory=lambda: _env("RERANK_MODEL", "bge-reranker-v2-m3"))
    rerank_topn: int = field(default_factory=lambda: _int("RERANK_TOPN", 24))      # candidates into the reranker
    rerank_keep: int = field(default_factory=lambda: _int("RERANK_KEEP", 0))       # chunks kept (0 = TOP_K)
    rerank_per_query_k: int = field(default_factory=lambda: _int("RERANK_PER_QUERY_K", 12))  # BM25 hits/query
    rerank_doc_chars: int = field(default_factory=lambda: _int("RERANK_DOC_CHARS", 700))
    rerank_item_slots: bool = field(default_factory=lambda: _bool("RERANK_ITEM_SLOTS", False))  # per-item best slot
    rerank_types: str = field(default_factory=lambda: _env("RERANK_TYPES", ""))  # comma list of qtypes; "" = all
    rerank_timeout: float = field(default_factory=lambda: _float("RERANK_TIMEOUT", 60.0))
    # QUERY_REWRITE: the answering LLM writes 1-2 search queries before retrieval
    #   0 = off, 1 = only for questions without named entities/years in the command, 2 = always
    query_rewrite: int = field(default_factory=lambda: _int("QUERY_REWRITE", 0))
    rewrite_max_tokens: int = field(default_factory=lambda: _int("REWRITE_MAX_TOKENS", 48))
    # DENSE: hybrid retrieval. The whole question is embedded (bge-m3 Q8_0 GGUF on a llama-server --embedding),
    # searched in the dense index (kb/dense.py) and fused with the BM25 candidates by ARTICLE-level RRF before
    # the reranker (see docs/dense_retrieval.md). 0 = BM25 only (original behaviour).
    dense: bool = field(default_factory=lambda: _bool("DENSE", False))
    dense_weight: float = field(default_factory=lambda: _float("DENSE_WEIGHT", 1.0))   # BM25 side weighs 1.0
    dense_index_dir: str = field(default_factory=lambda: _env("DENSE_INDEX_DIR", ""))  # "" -> kb_data/dense/bge-m3
    dense_url: str = field(default_factory=lambda: _env("DENSE_URL", "http://127.0.0.1:18096").rstrip("/"))
    dense_search: str = field(default_factory=lambda: _env("DENSE_SEARCH", "auto"))  # auto|faiss|torch|numpy|mmap
    dense_nprobe: int = field(default_factory=lambda: _int("DENSE_NPROBE", 64))
    dense_faiss_threads: int = field(default_factory=lambda: _int("DENSE_FAISS_THREADS", 1))  # 0 = faiss default
    dense_k: int = field(default_factory=lambda: _int("DENSE_K", 30))              # dense chunks into the fusion
    dense_depth: int = field(default_factory=lambda: _int("DENSE_DEPTH", 150))     # index rows scanned for them
    dense_per_article: int = field(default_factory=lambda: _int("DENSE_PER_ARTICLE", 3))
    dense_cand_per_article: int = field(default_factory=lambda: _int("DENSE_CAND_PER_ARTICLE", 0))  # fused head cap (0 = none)
    dense_query_chars: int = field(default_factory=lambda: _int("DENSE_QUERY_CHARS", 2000))
    dense_rrf_k: int = field(default_factory=lambda: _int("DENSE_RRF_K", 60))
    # article = article-level RRF reorders the whole pool (then RERANK_TOPN go to the reranker);
    # union = (RERANK=1 only) the BM25 top RERANK_TOPN stay as they are and the best DENSE_UNION_K dense chunks
    #         not among them are added to the reranker's candidates
    dense_mode: str = field(default_factory=lambda: _env("DENSE_MODE", "article"))
    dense_union_k: int = field(default_factory=lambda: _int("DENSE_UNION_K", 8))

    # ---- harness v3: CKE_MODE (default OFF = v2 behaviour). The final exam is graded like CKE (rubric, essay):
    # closed items reason first and end with 'Odpowiedź: ...', decisions are two-step (per-source who/what/when,
    # then decide, yes/no debiased), explanations cite each indicated source, the essay is written part by part
    # with per-element retrieval and a verification pass (harness/cke.py, cke_essay.py, cke_flow.py).
    cke_mode: bool = field(default_factory=lambda: _bool("CKE_MODE", False))
    cke_reason_max_tokens: int = field(default_factory=lambda: _int("CKE_REASON_MAX_TOKENS", 300))
    cke_explain_max_tokens: int = field(default_factory=lambda: _int("CKE_EXPLAIN_MAX_TOKENS", 380))
    cke_source_ctx_tokens: int = field(default_factory=lambda: _int("CKE_SOURCE_CTX_TOKENS", 700))
    cke_source_top_k: int = field(default_factory=lambda: _int("CKE_SOURCE_TOP_K", 3))
    # 'Tak' only when P(Tak) / (P(Tak) + P(Nie)) >= this after the per-source comparison (harness said 'Tak' 12/17,
    # key had 6/17); 0 = take the model's free answer
    cke_yes_threshold: float = field(default_factory=lambda: _float("CKE_YES_THRESHOLD", 0.7))
    # decisions: compare = per-source who/what/when -> written comparison -> constrained verdict -> justification;
    # summaries = per-source who/what/when -> one call (verdict prefilled + justification); direct = one call only
    cke_decide_mode: str = field(default_factory=lambda: _env("CKE_DECIDE_MODE", "summaries"))
    # comma list of qtypes that keep the LoRA adapter (short-answer training) in CKE mode; "" = adapter off everywhere
    cke_lora_types: str = field(default_factory=lambda: _env("CKE_LORA_TYPES", ""))
    cke_essay_part_ctx_tokens: int = field(default_factory=lambda: _int("CKE_ESSAY_PART_CTX_TOKENS", 1900))
    cke_essay_part_top_k: int = field(default_factory=lambda: _int("CKE_ESSAY_PART_TOP_K", 6))
    cke_essay_verify: bool = field(default_factory=lambda: _bool("CKE_ESSAY_VERIFY", True))
    cke_essay_max_words: int = field(default_factory=lambda: _int("CKE_ESSAY_MAX_WORDS", 650))
    # ESSAY_SAFE=1 (default OFF = essay output unchanged, tests/test_essay_safe.py): stricter date verification
    # (month/day next to its year in one passage, year near an entity of the sentence), prompts asking for at most
    # 2 plain years per paragraph, and best of two topics by unsupported claims per 100 words (>= ESSAY_SAFE_MIN_WORDS;
    # the second topic is skipped when the first took over half of ESSAY_SAFE_BUDGET seconds).
    essay_safe: bool = field(default_factory=lambda: _bool("ESSAY_SAFE", False))
    essay_safe_budget: float = field(default_factory=lambda: _float("ESSAY_SAFE_BUDGET", 90.0))
    essay_safe_min_words: int = field(default_factory=lambda: _int("ESSAY_SAFE_MIN_WORDS", 450))

    # ---- harness v4 (harness/v4.py, v4_flow.py): fixes from docs/error_map_v2.md on top of v3. All OFF by default
    # (= v3 prompts byte for byte, tests/test_v4.py). V4=1 turns on the fixes listed in harness.v4.V4_UMBRELLA; a fix
    # flag set to 0/1 wins over V4, -1 follows V4.
    v4: bool = field(default_factory=lambda: _bool("V4", False))
    v4_abcd_parts: int = field(default_factory=lambda: _int("V4_ABCD_PARTS", -1))        # one abcd call per sentence
    v4_continue: int = field(default_factory=lambda: _int("V4_CONTINUE", -1))            # finish cut reasoning
    v4_source_first: int = field(default_factory=lambda: _int("V4_SOURCE_FIRST", -1))    # identify source, then retrieve
    v4_title_rescore: int = field(default_factory=lambda: _int("V4_TITLE_RESCORE", -1))  # raw-title bonus / numeral penalty
    v4_pf_evidence: int = field(default_factory=lambda: _int("V4_PF_EVIDENCE", -1))      # F only with a quoted sentence
    v4_pf_value: int = field(default_factory=lambda: _int("V4_PF_VALUE", -1))            # P with number/quantifier re-checked
    v4_neutral_examples: int = field(default_factory=lambda: _int("V4_NEUTRAL_EXAMPLES", -1))  # '1-B, 2-A' -> '1-X, 2-X'
    v4_chrono_bc: int = field(default_factory=lambda: _int("V4_CHRONO_BC", -1))          # 1 ' p.n.e.' grammar + BC fallback, 2 + prompt
    v4_chrono_ties: int = field(default_factory=lambda: _int("V4_CHRONO_TIES", -1))      # 1 month/day then pairwise, 2 pairwise
    v4_title_bonus: float = field(default_factory=lambda: _float("V4_TITLE_BONUS", 1.5))    # reranker-logit units
    v4_title_penalty: float = field(default_factory=lambda: _float("V4_TITLE_PENALTY", 4.0))
    # self-consistency of the SAME model on closed items (abcd, pf, match, abcd_parts): greedy + SC_K-1 samples at
    # SC_TEMPERATURE, per-sub-answer majority; 0 = auto (1, or harness.v4.V4_SC_K under V4=1)
    sc_k: int = field(default_factory=lambda: _int("SC_K", 0))
    sc_temperature: float = field(default_factory=lambda: _float("SC_TEMPERATURE", 0.7))

    def public(self) -> dict:
        d = asdict(self)
        d.pop("llm_api_key", None)
        return d


SETTINGS = Settings()


def reload_settings() -> Settings:
    global SETTINGS
    SETTINGS = Settings()
    return SETTINGS
