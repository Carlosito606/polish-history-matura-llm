#!/usr/bin/env python3
"""Fetch open-licensed HISTORY e-materials (liceum/technikum) from zpe.gov.pl.

Legal gate (see CLAUDE.md + docs/zpe_sources.md):
  * robots.txt on zpe.gov.pl is `Allow: /`.
  * Only the public, anonymous endpoints the site's own catalogue/reader calls are used
    (`/api/v1/search`, `/api/v1/project/<id>/content|toc`, server-rendered `/a/<slug>/<id>`
    document pages). No login areas, no `/kursy`, no uploads.
  * Sequential requests, >= 1.5 s apart, identifying User-Agent.
  * Finding (2026-09-26, checked in Chromium via Playwright + raw HTML + the platform's own
    PDF/EPUB downloads): ZPE history e-materials show NO licence for the lesson prose
    ("Wprowadzenie", "Przeczytaj", "Dla nauczyciela", exercises), and the regulamin grants
    the public no licence. Licences are printed only per ELEMENT, in the element's caption
    ("Źródło: Contentplus.pl sp. z o.o., licencja: CC BY-SA 3.0.").
  * Therefore the gate is applied per element: text is kept ONLY from elements (interactive
    maps, schematy, timelines, animations, galleries ...) whose own rendered caption states
    CC BY / CC BY-SA / CC0. Lesson prose is never kept. Public-domain captions cover the
    reproduced image only, not ZPE's description, so they are logged, not kept. Third-party
    quotations inside a kept element (<q> + "Źródło: <book>" lines) are stripped. A material
    is "kept" when >= --min-words words survive; everything else is logged in manifest.csv.
  * The document pages are server-rendered (identical to the Chromium DOM), so plain HTTP
    GETs of the page the browser loads are used for throughput.

Output (git-ignored): sources/raw/zpe/<id>.txt|.json, manifest.csv, catalog.jsonl,
zpe_chunks.parquet.

Subcommands:
  catalog   list all history e-materials for stage E4 via the public search endpoint
  fetch     extract each material (non-prose documents from its TOC), apply the licence gate
  batches   write question-generation batch files from kept materials
  chunks    write the KB-compatible parquet of section-aware chunks
  docs      write docs/zpe_sources.md (attribution list, no content)
"""
import argparse
import csv
import html as htmlmod
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = 'WMT-hackathon-research/1.0 (contact: see repository README)'
BASE = 'https://zpe.gov.pl'
DELAY = 1.6
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'sources', 'raw', 'zpe')
HIST_SUBJECTS = {56: 'Historia', 79364: 'Historia PP 2022'}

_last = [0.0]


def get(url, want_json=False, retries=3):
    for attempt in range(retries):
        wait = DELAY - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'pl-PL'})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read().decode('utf-8', 'replace')
            return json.loads(data) if want_json else data
        except Exception as e:  # noqa: BLE001
            print(f'  ! {url} -> {e}', file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    return None


# ---------------------------------------------------------------- catalog
def cmd_catalog(args):
    os.makedirs(OUT, exist_ok=True)
    items = {}
    for sid in HIST_SUBJECTS:
        off = 0
        while True:
            q = urllib.parse.urlencode([
                ('searcher', 'main'), ('query', ''), ('filter[isStudentContent]', 'true'),
                ('filter[language][]', 'pl'), ('filter[stage][]', 'E4'),
                ('filter[subject][]', str(sid)), ('fields', ''), ('offset', str(off)),
                ('limit', '100'), ('sort', 'default_DESC'), ('format', 'json'), ('withCount', '1')])
            d = get(f'{BASE}/api/v1/search?{q}', want_json=True)
            if not d or not d.get('data'):
                break
            for x in d['data']:
                it = items.setdefault(x['id'], {'id': x['id'], 'title': re.sub(r'<[^>]+>', '', htmlmod.unescape(x['title'])).strip(),
                                                'subject': x.get('subject', []), 'stage': x.get('stage', [])})
            off += len(d['data'])
            print(f'subject {sid}: {off}/{d.get("count")}', file=sys.stderr)
            if off >= (d.get('count') or 0):
                break
    with open(os.path.join(OUT, 'catalog.jsonl'), 'w', encoding='utf-8', newline='\n') as f:
        for it in items.values():
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    print(len(items), 'catalogue items')


# ---------------------------------------------------------------- licence gate + extraction
# Licence strings as printed in ZPE element captions ("Źródło: X, licencja: CC BY-SA 3.0.").
LIC_RE = re.compile(r'licencj[ai]:?\s*(CC\s*0|CC0|CC\s*BY(?:[\s-]*(?:SA|NC|ND))*\s*\d\.\d(?:\s*PL)?|CC\s*BY(?:[\s-]*(?:SA|NC|ND))*)', re.I)
PD_RE = re.compile(r'domen[aąieę]\s+publiczn', re.I)
OPEN_CC = re.compile(r'^CC\s*0$|^CC0$|^CC\s*BY(?:[\s-]*SA)?(?:\s*\d\.\d)?(?:\s*PL)?$', re.I)
UI_LINES = {'Kliknij, aby uruchomić podgląd', 'Powiększ', 'Pełny ekran', 'Odtwórz', 'Zatrzymaj',
            'Pokaż odpowiedź', 'Sprawdź', 'Wyczyść', 'Zamknij', 'Treść filmu', 'Napisy',
            'Alternatywna ścieżka', 'Pobierz załącznik', 'Polecenie', 'Pokaż ilustrację',
            'Przejdź do tekstu alternatywnego', 'Przejdź do treści', 'Pokaż mapę'}
# TOC tabs that hold the lesson prose / exercises / lesson plan: their prose carries no
# licence of its own, so only their captioned elements could qualify (pass 2, optional).
PROSE_TABS = re.compile(r'^(wprowadzenie|przeczytaj|sprawdź się|dla nauczyciela|słownik|bibliografia|'
                        r'podsumowanie|ćwiczenia|zadania)$', re.I)


def caption_licence(fig):
    """Return (licence_label, source_line, title) from the figure's OWN caption, or (None,..)."""
    cap = None
    for ch in fig.find_all('figcaption', recursive=False):
        cap = ch
    if cap is None:
        # some templates wrap the caption one level down
        for ch in fig.find_all('figcaption'):
            if ch.find_parent('figure') is fig:
                cap = ch
    if cap is None:
        return None, '', ''
    bib = cap.find(class_='figure_caption_bibliography')
    hy = str.maketrans({c: '-' for c in '‐‑‒–—―'})
    src = re.sub(r'\s+', ' ', bib.get_text(' ')).strip().translate(hy) if bib else ''
    full = re.sub(r'\s+', ' ', cap.get_text(' ')).strip().translate(hy)
    title = full.replace(src, '').strip() if src else ''
    m = LIC_RE.search(src or full)
    if m:
        lab = re.sub(r'\s+', ' ', m.group(1).upper().replace('-', '-')).strip()
        lab = re.sub(r'CC\s*BY\s*-?\s*SA', 'CC BY-SA', lab)
        lab = re.sub(r'CC\s*0', 'CC0', lab)
        return lab, src, title
    if PD_RE.search(src or full):
        return 'domena publiczna', src, title
    return ('other' if src else None), src, title


def clean_text(node):
    for t in node.find_all(['script', 'style', 'button', 'svg', 'noscript', 'figcaption', 'audio', 'video', 'source', 'track']):
        t.decompose()
    drop = {'sr-only', 'print-only', 'mdi', 'video-static-alt'}
    for t in node.find_all(class_=lambda c: c and bool(drop & set(c.split()))):
        t.decompose()
    # Third-party quotations embedded in an element (<q> source excerpts from books/translations,
    # cited with a <sub>Źródło: ...</sub> line) are not covered by the element's own licence.
    for q in node.find_all('q'):
        if len(q.get_text(' ').split()) > 12:
            q.decompose()
    for sb in node.find_all('sub'):
        st = sb.get_text(' ')
        if 'Źródło' in st and not (LIC_RE.search(st) or PD_RE.search(st)):
            sb.decompose()
    for br in node.find_all('br'):
        br.replace_with('\n')
    for t in node.find_all(['p', 'li', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr', 'section', 'blockquote', 'dd', 'dt']):
        t.insert_after('\n')
    txt = node.get_text(' ')
    out = []
    for line in txt.split('\n'):
        line = re.sub(r'\s+', ' ', line).strip()
        if not line or line in UI_LINES or re.fullmatch(r'[\W\d_]{0,3}', line):
            continue
        if out and out[-1] == line:
            continue
        out.append(line)
    return '\n'.join(out)


def extract_doc(html, tab):
    """Split one server-rendered /a/ document into licensed element sections + a skip log."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')
    body = soup.find(class_='document-body') or soup
    for t in body.find_all(class_=re.compile(r'page-nav-footer|document-navigation|wrapper_comments')):
        t.decompose()
    kept, skipped = [], []

    def visit(fig):
        lic, src, title = caption_licence(fig)
        if lic and lic != 'other' and (lic == 'domena publiczna' or OPEN_CC.match(lic)):
            if lic == 'domena publiczna':
                # PD covers the reproduced work (painting, photo, document), not the ZPE author's
                # caption/description of it -> log only, keep no text.
                skipped.append({'tab': tab, 'title': title[:150], 'source': src[:300], 'why': 'PD image; caption text not covered'})
                return
            else:
                txt = clean_text(fig)
                if title and title not in txt:
                    txt = title + '\n' + txt
            if len(txt.split()) >= 5:
                kept.append({'tab': tab, 'title': title[:150], 'licence': lic, 'source': src[:300], 'text': txt})
            return
        if lic == 'other':
            skipped.append({'tab': tab, 'title': title[:150], 'source': src[:300]})
            return
        subs = [f for f in fig.find_all('figure') if f.find_parent('figure') is fig]
        for f in subs:
            visit(f)

    for fig in body.find_all('figure'):
        if fig.find_parent('figure') is None:
            visit(fig)
    return kept, skipped


# ---------------------------------------------------------------- fetch
MAN_FIELDS = ['id', 'title', 'url', 'subjects', 'tabs', 'docs_fetched', 'n_kept_elements', 'n_words',
              'licences', 'attribution', 'status', 'reason']


def load_manifest():
    p = os.path.join(OUT, 'manifest.csv')
    if not os.path.exists(p):
        return {}
    with open(p, encoding='utf-8', newline='') as f:
        return {r['id']: r for r in csv.DictReader(f)}


def save_manifest(rows):
    p = os.path.join(OUT, 'manifest.csv')
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=MAN_FIELDS, lineterminator='\n')
        w.writeheader()
        for r in rows.values():
            w.writerow({k: r.get(k, '') for k in MAN_FIELDS})
    os.replace(tmp, p)


def cmd_fetch(args):
    import random
    items = [json.loads(l) for l in open(os.path.join(OUT, 'catalog.jsonl'), encoding='utf-8')]
    random.Random(args.seed).shuffle(items)          # uniform era coverage if stopped early
    man = load_manifest()
    deadline = time.time() + args.minutes * 60
    n = 0
    for it in items:
        if time.time() > deadline:
            print('deadline reached', file=sys.stderr)
            break
        if it['id'] in man and man[it['id']].get('status') in ('kept', 'skipped') and not args.prose:
            continue
        if args.prose and man.get(it['id'], {}).get('prose_done'):
            continue
        toc = get(f'{BASE}/api/v1/project/{it["id"]}/toc', want_json=True)
        if not isinstance(toc, list):
            man[it['id']] = {'id': it['id'], 'title': it['title'], 'url': f'{BASE}/b/{it["id"]}',
                             'status': 'error', 'reason': 'no toc'}
            continue
        docs = [d for d in toc if d.get('type') == 'document']
        want = [d for d in docs if not PROSE_TABS.match(d['name'].strip())]
        if args.prose:
            want = [d for d in docs if d['name'].strip().lower() == 'przeczytaj']
        kept, skipped = [], []
        for d in want:
            h = get(f'{BASE}/a/x/{d["id"]}')
            if not h:
                continue
            k, s = extract_doc(h, d['name'].strip())
            for e in k:
                e['doc_url'] = f'{BASE}/a/{d["id"]}'
            kept += k
            skipped += s
        # merge with an existing txt from a previous pass
        jpath = os.path.join(OUT, f'{it["id"]}.json')
        if os.path.exists(jpath):
            prev = json.load(open(jpath, encoding='utf-8'))
            seen = {e['text'] for e in prev['kept']}
            kept = prev['kept'] + [e for e in kept if e['text'] not in seen]
            skipped = prev['skipped'] + skipped
        rec = {'id': it['id'], 'title': it['title'], 'url': f'{BASE}/b/{it["id"]}', 'subjects': it['subject'],
               'tabs': [d['name'] for d in docs], 'kept': kept, 'skipped': skipped}
        json.dump(rec, open(jpath, 'w', encoding='utf-8'), ensure_ascii=False)
        words = sum(len(e['text'].split()) for e in kept)
        lics = sorted({e['licence'] for e in kept})
        attrib = sorted({re.sub(r'^Źródło:\s*', '', re.sub(r',?\s*licencj.*$', '', e['source'])).strip()
                         for e in kept if e['licence'] != 'domena publiczna'} - {''})
        status = 'kept' if words >= args.min_words else 'skipped'
        reason = ('' if status == 'kept' else
                  'no element with an open licence caption' if not kept else f'only {words} words of openly licensed element text')
        reason += ('; ' if reason else '') + 'lesson prose: no licence shown on page -> not kept'
        if skipped:
            reason += f'; {len(skipped)} element(s) with non-open licence skipped'
        man[it['id']] = {'id': it['id'], 'title': it['title'], 'url': f'{BASE}/b/{it["id"]}',
                         'subjects': ' '.join(map(str, it['subject'])), 'tabs': ' | '.join(d['name'] for d in docs),
                         'docs_fetched': str(int(man.get(it['id'], {}).get('docs_fetched') or 0) + len(want)),
                         'n_kept_elements': str(len(kept)), 'n_words': str(words), 'licences': '; '.join(lics),
                         'attribution': '; '.join(attrib)[:400], 'status': status, 'reason': reason}
        if status == 'kept':
            write_txt(rec)
        n += 1
        if n % 10 == 0:
            save_manifest(man)
            nk = sum(1 for r in man.values() if r.get('status') == 'kept')
            print(f'{n} done this run; manifest {len(man)} ({nk} kept)', file=sys.stderr)
    save_manifest(man)
    print('fetched', n)


def write_txt(rec):
    parts = [f'# {rec["title"]}', f'URL: {rec["url"]}', '']
    for e in rec['kept']:
        sec = e['tab'] + (f' — {e["title"]}' if e['title'] else '')
        parts += [f'## {sec}', f'[licencja: {e["licence"]}; {e["source"]}]', e['text'], '']
    with open(os.path.join(OUT, f'{rec["id"]}.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(parts))


# ---------------------------------------------------------------- batches + chunks
def kept_records():
    man = load_manifest()
    order = [json.loads(l)['id'] for l in open(os.path.join(OUT, 'catalog.jsonl'), encoding='utf-8')]
    for idx, mid in enumerate(order):
        if man.get(mid, {}).get('status') != 'kept':
            continue
        rec = json.load(open(os.path.join(OUT, f'{mid}.json'), encoding='utf-8'))
        rec['idx'] = idx
        yield rec


def element_label(e):
    lab = e['tab']
    if e['title']:
        t = e['title'] if len(e['title']) <= 110 else e['title'][:107].rsplit(' ', 1)[0] + '…'
        lab += f': {t}'
    return lab


def split_words(text, max_w=2500):
    paras, parts, buf, bw = text.split('\n'), [], [], 0
    for p in paras:
        w = len(p.split())
        if buf and bw + w > max_w:
            parts.append('\n'.join(buf))
            buf, bw = [], 0
        buf.append(p)
        bw += w
    if buf:
        parts.append('\n'.join(buf))
    return parts


def cmd_batches(args):
    os.makedirs(args.out, exist_ok=True)
    for f in os.listdir(args.out):
        if re.fullmatch(r'batch_\d{3}\.md', f):
            os.remove(os.path.join(args.out, f))
    files, cur, cw = [], [], 0

    def flush():
        nonlocal cur, cw
        if cur:
            files.append('\n\n'.join(cur) + '\n')
        cur, cw = [], 0

    for rec in kept_records():
        for e in rec['kept']:
            parts = split_words(e['text'])
            for pi, part in enumerate(parts):
                sec = element_label(e) + (f' (część {pi + 1}/{len(parts)})' if len(parts) > 1 else '')
                block = f'### ARTYKUŁ: {rec["title"]} — {sec}\nURL: {e.get("doc_url") or rec["url"]}\n\n{part}'
                w = len(block.split())
                if cw and cw + w > args.max_words:
                    flush()
                cur.append(block)
                cw += w
                if cw >= args.target_words:
                    flush()
    flush()
    tot = 0
    for i, body in enumerate(files):
        with open(os.path.join(args.out, f'batch_{i:03d}.md'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(body)
        tot += len(body.split())
    print(f'{len(files)} batches, {tot} words -> {args.out}')


SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9„\"(\[])")


def pack(text, target=170, max_w=250, min_w=60):
    """Same packing as kb/build_chunks.py: ~120-250-word chunks on sentence boundaries."""
    sents = SENT_SPLIT.split(re.sub(r'\s*\n\s*', ' ', text.strip()))
    chunks, buf, bw = [], [], 0
    for s in sents:
        w = s.split()
        if len(w) > max_w:
            if buf:
                chunks.append(' '.join(buf))
                buf, bw = [], 0
            for i in range(0, len(w), target):
                chunks.append(' '.join(w[i:i + target]))
            continue
        if bw + len(w) > max_w and bw >= min_w:
            chunks.append(' '.join(buf))
            buf, bw = [], 0
        buf.append(s)
        bw += len(w)
        if bw >= target:
            chunks.append(' '.join(buf))
            buf, bw = [], 0
    if buf:
        if chunks and bw < min_w and len(chunks[-1].split()) + bw <= max_w + 40:
            chunks[-1] = chunks[-1] + ' ' + ' '.join(buf)
        else:
            chunks.append(' '.join(buf))
    return chunks


def cmd_chunks(args):
    import pyarrow as pa
    import pyarrow.parquet as pq
    schema = pa.schema([
        ('page_id', pa.int64()), ('title', pa.string()), ('section', pa.string()), ('chunk_idx', pa.int32()),
        ('text', pa.string()), ('n_words', pa.int32()), ('url', pa.string()), ('popularity_score', pa.float32()),
        ('incoming_links', pa.int32()), ('categories', pa.string()), ('aliases', pa.string()),
        ('hist_score', pa.int32()), ('opening_text', pa.string()), ('headings', pa.string())])
    rows = []
    for rec in kept_records():
        title = rec['title']
        heads = [element_label(e) for e in rec['kept']]
        opening = ' '.join(rec['kept'][0]['text'].split()[:60]) if rec['kept'] else ''
        ci = 0
        for e, lab in zip(rec['kept'], heads):
            for ch in pack(e['text']):
                nw = len(ch.split())
                if nw < 8:
                    continue
                rows.append({'page_id': args.offset + rec['idx'], 'title': title, 'section': lab, 'chunk_idx': ci,
                             'text': f'{title} — {lab}\n{ch}', 'n_words': nw, 'url': e.get('doc_url') or rec['url'],
                             'popularity_score': 0.0, 'incoming_links': 0, 'categories': 'ZPE', 'aliases': '',
                             'hist_score': 10, 'opening_text': opening if ci == 0 else '',
                             'headings': '|'.join(heads) if ci == 0 else ''})
                ci += 1
    out = os.path.join(OUT, 'zpe_chunks.parquet')
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), out)
    print(f'{len(rows)} chunks, {len({r["page_id"] for r in rows})} pages, '
          f'{sum(r["n_words"] for r in rows)} words -> {out}')


def cmd_docs(args):
    import collections
    man = load_manifest()
    rows = list(man.values())
    kept = [r for r in rows if r.get('status') == 'kept']
    st = collections.Counter(r.get('status') for r in rows)
    lic = collections.Counter(l for r in kept for l in r['licences'].split('; ') if l)
    words = sum(int(r['n_words'] or 0) for r in kept)
    ncat = sum(1 for _ in open(os.path.join(OUT, 'catalog.jsonl'), encoding='utf-8'))
    L = ['# ZPE (zpe.gov.pl) — history e-materials used as sources', '',
         'Attribution list only — no content is committed. Text lives in the git-ignored',
         '`sources/raw/zpe/` and is rebuilt with `scripts/fetch_zpe.py` (catalog → fetch → batches/chunks → docs).', '',
         '## Licence gate (read this first)', '',
         '- Source: Zintegrowana Platforma Edukacyjna, operated by the Ministerstwo Edukacji Narodowej;',
         '  `robots.txt` = `Allow: /`. Only public, anonymous endpoints the site itself calls; sequential',
         '  requests >= 1.5 s apart; UA `WMT-hackathon-research/1.0 (contact: see repository README)`; no login areas.',
         '- Checked in Chromium (Playwright), in the server HTML and in the platform\'s own PDF/EPUB',
         '  downloads: **the lesson prose of ZPE history e-materials carries no licence statement**, and',
         '  the regulamin grants the public none. Licences appear only per element, in captions such as',
         '  `Źródło: Contentplus.pl sp. z o.o., licencja: CC BY-SA 3.0.`',
         '- So only the text of elements whose own caption shows CC BY / CC BY-SA / CC0 is kept',
         '  (interactive maps, schematy, animations, galleries, timelines with such a caption).',
         '  Lesson prose ("Wprowadzenie", "Przeczytaj", exercises, "Dla nauczyciela") is never kept.',
         '  Public-domain captions cover the reproduced image, not ZPE\'s description: logged, not kept.',
         '  Quotations from third-party books inside a kept element are stripped.',
         '- CC BY-SA obliges attribution + share-alike for derived text; attribution is listed below',
         '  (material title, URL, licence, author/licensor shown in the caption).', '',
         '## Coverage', '',
         f'- Catalogue (stage E4 = liceum/technikum, subjects Historia + Historia PP 2022): {ncat} e-materials.',
         f'- Processed (random order, so coverage is uniform across eras): {len(rows)}; '
         f'kept {st.get("kept", 0)}, skipped {st.get("skipped", 0)}, errors {st.get("error", 0)}.',
         f'- Kept text: {words} words. Licences in kept elements: ' + ', '.join(f'{k} ({v})' for k, v in lic.most_common()) + '.',
         '- Per-material status and skip reasons: `sources/raw/zpe/manifest.csv` (git-ignored, rebuilt by the script).', '',
         '## Kept materials', '', '| # | Title | URL | Licence(s) | Author / licensor (from captions) | Words |',
         '|---|---|---|---|---|---|']
    for i, r in enumerate(sorted(kept, key=lambda r: r['title']), 1):
        t = r['title'].replace('|', '/')
        a = (r['attribution'] or '—').replace('|', '/')
        L.append(f'| {i} | {t} | {r["url"]} | {r["licences"]} | {a} | {r["n_words"]} |')
    L.append('')
    with open(os.path.join(ROOT, 'docs', 'zpe_sources.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L))
    print('docs/zpe_sources.md:', len(kept), 'kept rows')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('catalog')
    sub.add_parser('docs')
    bt = sub.add_parser('batches')
    bt.add_argument('--out', required=True)
    bt.add_argument('--target-words', type=int, default=15000)
    bt.add_argument('--max-words', type=int, default=20000)
    ck = sub.add_parser('chunks')
    ck.add_argument('--offset', type=int, default=900000000)
    f = sub.add_parser('fetch')
    f.add_argument('--minutes', type=float, default=45)
    f.add_argument('--seed', type=int, default=20260926)
    f.add_argument('--min-words', type=int, default=60)
    f.add_argument('--prose', action='store_true', help='second pass: captioned elements on the Przeczytaj tab')
    a = ap.parse_args()
    {'catalog': cmd_catalog, 'fetch': cmd_fetch, 'batches': cmd_batches, 'chunks': cmd_chunks, 'docs': cmd_docs}[a.cmd](a)
