# dev-b: evaluation set for early modern history (ok. 1490–1815)

`../dev-b.jsonl` has 72 matura-style questions (104 points). Each question comes from one Polish Wikipedia article (56 articles; see `sources.tsv` for the page IDs and the revision IDs at fetch time, 2026-09-25). **Use this set for evaluation only. Never use it for training or put it in the RAG knowledge base as Q/A pairs.**

| type | n | points each |
|---|---|---|
| abcd (single choice A–D) | 26 | 1 |
| pf (3–4 true/false statements, answer `P, F, P, P`) | 14 | 2 |
| chrono (4 events, answer `C, A, D, B`) | 11 | 2 |
| match (3–4 pairs, answer `1-B, 2-A, 3-C`) | 7 | 2 |
| open (a name, year or term; alternatives are in `accept`) | 14 | 1 |

Topics covered: the discoveries, the Reformation and the Council of Trent, the Union of Lublin and the free elections, the Vasa kings and the 17th-century wars (Kłuszyn, Chocim 1621, Chmielnicki, the Deluge, Vienna), liberum veto and the Saxon era, the Thirty Years' War and the Peace of Westphalia, Louis XIV, the Enlightenment under Stanisław August (KEN, the Four-Year Sejm, the Constitution of 3 May), the partitions, the Kościuszko Uprising, the French and American revolutions, and the Napoleonic era (the Legions, Tilsit, the Duchy of Warsaw, the Napoleonic Code, 1812).

## Rebuilding
```bash
python fetch_wiki.py titles.txt /tmp/devb_wiki      # sequential fetch of plain-text extracts from the pl.wikipedia API
python build_devb.py /tmp/devb_wiki ../dev-b.jsonl  # assembles questions.py, validates, writes the JSONL
```
`build_devb.py` checks the schema, the answer formats, the points rules and that labels are unique. It also checks that every open answer appears in the article text, allowing for declension.

The questions were written by hand (by Claude) from the fetched text, and every gold answer was checked against the article. The live articles may change after the revisions listed in `sources.tsv`.
