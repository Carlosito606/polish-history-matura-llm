# Data licence

The datasets in `qa/`, `devsets/` and `training/` are released under the
[Creative Commons Attribution-ShareAlike 4.0 International licence (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/)
by Team Vibers (Karol Woźniak, Patryk Wójcicki, Adrian Dzido).

They are derived from:

- **Polish Wikipedia** articles, licensed CC BY-SA 4.0. Each row's `source_url` names the article it comes from.
- **ZPE** (Zintegrowana Platforma Edukacyjna) elements whose own caption states CC BY, CC BY-SA or CC0.
  Each row's `source_url` names the element.

Questions, answers and verification notes were generated with Claude (Anthropic). Our team used them only as short
canonical answer targets or as evaluation data, never to train a model on Claude-written explanations or prose.
Please follow the same rule and Anthropic's terms.

The RFT reasoning texts in `training/rft_v3_bielik_own_reasoning.jsonl.gz` were written by
Bielik-4.5B-v3.0-Instruct (Apache-2.0).

No CKE material (exam papers, answer keys or transcriptions of CKE tasks) is included.
