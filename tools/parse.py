"""Parsing of the two Åland sources and the deterministic replay of amending acts.

Ålex (regeringen.ax) serves only the CURRENT consolidation of an act, as HTML; the Statute Book (Ålands
författningssamling, ÅFS) serves each act as a PDF. The original act is parsed from its ÅFS PDF, every amending act
from its ÅFS PDF, and the amending acts are replayed onto the original: whole-section replacement, heading
replacement, subsection (moment) replacement and insertion, point replacement, section insertion, repeal, and the
end of a temporary change. The enacting clause of each act ("ändras ... fogas ... upphävs ... som följer:") names
every unit it changes; the body gives the new text with "- - -" omission marks for the units it leaves alone.
Anything the grammar does not recognise raises ReplayError; nothing is guessed. No AI runs here.

Requires PyMuPDF (pymupdf) for the PDFs; otherwise standard library.
"""
import html
import re

WS = re.compile(r'\s+')
LABEL = re.compile(r'\s*\(\d{4}/\d+\)')
SOFT = '­'
NBSP = ' '
EMSP = ' '
UNMAPPED = '�'
MONTHS = ['januari', 'februari', 'mars', 'april', 'maj', 'juni', 'juli', 'augusti', 'september', 'oktober',
          'november', 'december']
DAY = re.compile(r'(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\s+(\d{4})')


class ReplayError(Exception):
    pass


def iso(s: str):
    m = DAY.search(s)
    return f'{m.group(3)}-{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}' if m else None


def clean(s: str) -> str:
    """Whitespace normalisation applied to BOTH sources: NBSP and tabs to spaces, soft hyphens dropped, runs of
    whitespace collapsed."""
    return WS.sub(' ', s.replace(NBSP, ' ').replace(SOFT, '').replace(EMSP, ' ')).strip()


def skey(num: str) -> str:
    """'22a §' / '22 a §' / '22a' -> '22a'."""
    m = re.fullmatch(r'(\d+)\s*([a-z]?)\s*§?\.?', clean(num))
    if not m:
        raise ReplayError(f'bad section number {num!r}')
    return m.group(1) + m.group(2)


def sort_key(k: str):
    m = re.fullmatch(r'(\d+)([a-z]*)', k)
    return (int(m.group(1)), m.group(2))


# ---- Ålex HTML -----------------------------------------------------------------------------------------------------
INLINE = re.compile(r'</?(?:a|span|em|strong|i|b|u|abbr|sup|sub)\b[^>]*>')


def _text(fragment: str) -> str:
    return clean(html.unescape(re.sub(r'<[^>]+>', ' ', INLINE.sub('', fragment))))


def parse_alex(page: str) -> dict:
    """{'title', 'chapters': [{'num','heading','sections':[{'num','heading','moments':[[lines]], 'repealed'}]}],
    'amendments': [{'id': '2017/126', 'commencement': str}], 'updated': str}"""
    title = _text(re.search(r'<h1[^>]*>(.*?)</h1>', page, re.S).group(1))
    i = page.index('class="content-body"')
    j = page.index('class="andringinfosektion"')
    body = page[i:j]
    chapters = []
    for cm in re.finditer(r'<div class="kapitel">(.*?)(?=<div class="kapitel">|<div class="andringinfosektion"|$)', body, re.S):
        chunk = cm.group(1)
        h2 = _text(re.search(r'<h2[^>]*>(.*?)</h2>', chunk, re.S).group(1))
        m = re.match(r'(\d+ kap\.)\s*(.*)', h2)
        ch = {'num': m.group(1), 'heading': LABEL.sub('', m.group(2)).strip(), 'sections': []}
        for pm in re.finditer(r'<div class="paragraf">(.*?)(?=<div class="paragraf">|$)', chunk, re.S):
            p = pm.group(1)
            h3 = _text(re.search(r'<h3[^>]*>(.*?)</h3>', p, re.S).group(1))
            hm = re.match(r'(\d+[a-z]?) §\.?\s*(.*)', h3)
            sec = {'num': skey(hm.group(1)), 'heading': LABEL.sub('', hm.group(2)).strip(), 'moments': [], 'repealed': False}
            p = re.sub(r'<div class="anmarkning">.*?</div>', '', p, flags=re.S)
            for mm in re.split(r'<div class="moment">', p)[1:]:
                lines = []
                for item in re.finditer(r'<p>(.*?)</p>|<tr>(.*?)</tr>', mm, re.S):
                    if item.group(1) is not None:
                        t = LABEL.sub('', _text(item.group(1))).strip()
                    else:
                        t = ' | '.join(_text(c) for c in re.findall(r'<t[hd]>(.*?)</t[hd]>', item.group(2), re.S))
                    if t:
                        lines.append(t)
                if lines:
                    sec['moments'].append(lines)
            if len(sec['moments']) == 1 and len(sec['moments'][0]) == 1 and re.fullmatch(r'Upphävd\.?', sec['moments'][0][0]):
                sec['repealed'] = True
            ch['sections'].append(sec)
        chapters.append(ch)
    ams = []
    for am in re.finditer(r'<h3 id="an_\d+">([^<]*)</h3>(.*?)(?=<div class="andringinfo">|</div>\s*</div>\s*</div>\s*</div>)', page[j:], re.S):
        ik = re.search(r'<div class="ikrafttradelsedigi">(.*?)</div>', am.group(2), re.S)
        ams.append({'id': am.group(1).strip(), 'commencement': _text(ik.group(1)) if ik else ''})
    upd = re.search(r'Uppdaterad till och med ÅFS (\d{4}/\d+)', html.unescape(page))
    return {'title': title, 'chapters': chapters, 'amendments': ams, 'updated': upd.group(1) if upd else ''}


# ---- ÅFS PDF -------------------------------------------------------------------------------------------------------
JUNK = [r'^ÅLANDS FÖRFATTNINGSSAMLING', r'^\d{4}$', r'^Nr \d+$', r'^LANDSKAPSLAG$', r'^Föredragen för',
        r'^(\d\)?\s*)?(LF|TMK|FNU|SMU|LKU|Lu|Lr|Ls)\b.*\d{4}[-–]\d{2,4}', r'^Mariehamn den \d+ \w+ \d{4}$',
        r'^[A-ZÅÄÖ]{2,}(\s[A-ZÅÄÖ-]{2,})+$', r'^(vice)?lantråd$', r'^(föredragande )?minister$', r'^([A-Za-zÅÄÖåäöé]{1,2} ){3,}[A-Za-zÅÄÖåäöé]{1,2}$',
        r'^[A-ZÅÄÖ][a-zåäöé]+(-[A-ZÅÄÖ][a-zåäöé]+)? [A-ZÅÄÖ][a-zåäöé]+(-[A-ZÅÄÖ][a-zåäöé]+)?$',
        r'^Nr \d+, utgiven', r'Mariehamns Tryckeri', r'^\d+$', r'^År \d{4}\.? ?Nr', r'^[A-Z]{2,4} bet\.? ?(nr)?']
JUNK = [re.compile(p) for p in JUNK]


def pdf_lines(data: bytes) -> list:
    """Reading-order lines: [{'x': indent from column edge, 'text', 'fonts': {'B','I','R'}}]. Two columns per page,
    merged by baseline; spans under 7pt (footnote marks) dropped; publisher's header, footer, footnote and signature
    lines dropped by their content."""
    import pymupdf
    doc = pymupdf.open(stream=data, filetype='pdf')
    out = []
    for page in doc:
        mid = page.rect.width / 2
        raw = []
        for b in page.get_text('dict')['blocks']:
            if b['type'] != 0:
                continue
            for l in b['lines']:
                spans = [s for s in l['spans'] if s['size'] >= 7]
                text = ''.join(s['text'] for s in spans)
                if not text:
                    continue
                fonts = set()
                for s in spans:
                    if s['text'].strip():
                        f = s['font']
                        fonts.add('B' if 'Bold' in f else 'I' if 'Italic' in f else 'R')
                x0, y0, x1, _ = l['bbox']
                col = 0 if (x0 + x1) / 2 < mid else 1
                raw.append([col, round(y0), x0, text, fonts])
        raw.sort(key=lambda r: (r[0], r[1], r[2]))
        merged = []
        for r in raw:
            if merged and merged[-1][0] == r[0] and abs(merged[-1][1] - r[1]) <= 1 and r[3].strip():
                if not merged[-1][3].strip():
                    merged[-1][2] = r[2]
                merged[-1][3] = merged[-1][3].rstrip() + ' ' + r[3].lstrip()
                merged[-1][4] |= r[4]
            else:
                merged.append(r)
        left = {}
        merged = [r for r in merged if not any(p.search(clean(r[3])) for p in JUNK)]
        for col, y, x, text, fonts in merged:
            if len(text.strip()) >= 30 and fonts == {'R'}:
                left[col] = min(left.get(col, 9e9), x)
        for col, y, x, text, fonts in merged:
            out.append({'x': x - left.get(col, x), 'text': text.replace(NBSP, ' '), 'fonts': fonts, 'blank': not text.strip()})
    return out


def join_lines(parts: list) -> str:
    s = ''
    for p in parts:
        p = p.strip(' \t')
        if s.endswith(UNMAPPED + SOFT):
            # an unmapped glyph before the hyphen is the consonant doubled at a Swedish triple-consonant break
            # ("til[l]-lämpning" for "tillämpning"); the word is joined as it is written unbroken
            s = s[:-2] + p
        elif s.endswith(SOFT):
            s = s[:-1] + p
        else:
            s = (s + ' ' + p) if s else p
    return clean(s)


SEC = re.compile(r'^(\d+[a-z]?)\s*§$')
CHAP = re.compile(r'^(\d+)\s*kap\.$')
OMIT = re.compile(r'^[-–\s]{8,}$')
POINT = re.compile(r'^(\d+|[a-z])\)\s')


def parse_body(lines: list) -> list:
    """Body lines -> elements: ('chapter', {'num','heading'}) and ('section', {'num','heading','seq'}) where seq is
    the list of moments (each a list of lines: the paragraph, then its points) with None for an omission mark.
    A paragraph starts at an indented line (or one starting with an em space); a line "1) ..." at a paragraph start
    is a point of the open moment. Blank lines are ignored (a paragraph may run across a page)."""
    elems, cur, head_mode, buf = [], None, None, []

    def flush():
        nonlocal buf
        if buf and cur is not None:
            line = join_lines(buf)
            if cur['open'] and POINT.match(line):
                cur['seq'][-1].append(line)
            else:
                cur['seq'].append([line])
                cur['open'] = True
        buf = []

    for l in lines:
        if l['blank']:
            continue
        t = clean(l['text'])
        if head_mode and l['fonts'] <= {head_mode}:
            cur['heading'].append(l['text'])
            continue
        head_mode = None
        m = SEC.match(t)
        if m and l['fonts'] == {'R'}:
            flush()
            cur = {'num': skey(m.group(1)), 'heading': [], 'seq': [], 'open': False}
            elems.append(('section', cur))
            head_mode = 'I'
            continue
        m = CHAP.match(t)
        if m and l['fonts'] == {'B'}:
            flush()
            cur = {'num': m.group(1) + ' kap.', 'heading': [], 'seq': [], 'open': False}
            elems.append(('chapter', cur))
            head_mode = 'B'
            continue
        if OMIT.match(t):
            flush()
            cur['seq'].append(None)
            cur['open'] = False
            continue
        if cur is None:
            raise ReplayError('text before the first section: ' + t[:60])
        if l['text'].startswith(EMSP) or l['x'] >= 7:
            flush()
        buf.append(l['text'])
    flush()
    out = []
    for kind, e in elems:
        e['heading'] = join_lines(e['heading'])
        e.pop('open', None)
        out.append((kind, e))
    return out


def parse_pdf(data: bytes) -> dict:
    """{'title', 'clause', 'elements', 'commencement', 'tail', 'issued'}"""
    lines = pdf_lines(data)
    texts = [clean(l['text']) for l in lines]
    start = next(i for i, t in enumerate(texts) if t.startswith('I enlighet med lagtingets beslut'))
    title = join_lines([l['text'] for l in lines[:start] if l['fonts'] == {'B'} and clean(l['text']).startswith('om ')])
    issued = next((iso(t) for t in texts[:start] if t.startswith('Utfärdad')), None)
    clause, k = [], start
    while k < len(texts):
        clause.append(lines[k]['text'])
        if re.search(r'(föreskrivs|som följer)\s*:\s*\d?$', texts[k]):
            break
        k += 1
    clause = re.sub(r'\d?$', '', join_lines(clause))
    original = 'föreskrivs' in clause
    body, tail = [], []
    for l in lines[k + 1:]:
        t = clean(l['text'])
        if not original and (re.match(r'^_{3,}$', t) or t.startswith(('Denna lag träder i kraft', 'Lagtinget bemyndigar'))):
            tail = lines[lines.index(l):]
            break
        if re.match(r'^_{3,}$', t):
            continue
        body.append(l)
    elems = parse_body(body)
    tail_text = join_lines([l['text'] for l in tail if not l['blank']]) if tail else ''
    if original:
        tail_text = ' '.join(x for kind, e in elems for mom in e.get('seq', []) if mom for x in mom if 'träder i kraft' in x)
    return {'title': title, 'clause': clause, 'elements': elems, 'original': original, 'tail': tail_text, 'issued': issued,
            'commencement': re.search(r'Denna lag träder i kraft[^.]*\.', tail_text).group(0) if 'träder i kraft' in tail_text else ''}


def act_from_elements(elems: list, title: str) -> dict:
    act = {'title': title, 'chapters': []}
    cur = None
    for kind, e in elems:
        if kind == 'chapter':
            cur = {'num': e['num'], 'heading': e['heading'], 'sections': []}
            act['chapters'].append(cur)
        else:
            if cur is None:
                cur = {'num': '', 'heading': '', 'sections': []}
                act['chapters'].append(cur)
            if None in e['seq']:
                raise ReplayError(f'{e["num"]} §: omission mark in an original act')
            cur['sections'].append({'num': e['num'], 'heading': e['heading'], 'moments': [list(m) for m in e['seq']],
                                    'repealed': False})
    return act


# ---- enacting-clause grammar --------------------------------------------------------------------------------------
K = r'\d+[a-z]?'
LIST = rf'{K}(?:\s*[–-]\s*{K})?(?:(?:\s*,\s*|\s+och\s+|\s+samt\s+){K}(?:\s*[–-]\s*{K})?)*'


def expand(lst: str) -> list:
    out = []
    for a, b in re.findall(rf'({K})(?:\s*[–-]\s*({K}))?', lst):
        if not b:
            out.append(a)
        else:
            n = re.match(r'\d+', a).group()
            assert n == re.match(r'\d+', b).group(), lst
            for c in range(ord(a[len(n)]), ord(b[len(n)]) + 1):
                out.append(n + chr(c))
    return out


def parse_clause(clause: str, title: str = '') -> list:
    """Ops: (kind, key, extra, temp). kinds: replace_sec, heading, chapter_heading, replace_sub(k,[n..]),
    replace_point(k, n), insert_sub(k, n), insert_sec(k, chapter or None), repeal_sec."""
    t = clause.split('lagtingets beslut', 1)[1]
    t = re.sub(r'(föreskrivs|som följer)\s*:.*$', '', t)
    t = re.sub(r'landskapslagen \(\d{4}:\d+\) ' + re.escape(clean(title)), '', clean(t))
    # provenance notes ("av dessa lagrum 1 § 2 mom. sådant det lyder i landskapslagen 2020/54", "sådan 1 § lyder i
    # ...", "sådana de lyder i ...") say which version is amended; they name no change and are dropped
    t = re.sub(r',?\s*av dessa(?: lagrum)? [^,]*?sådan\w* \w+ lyder i landskapslagen \d{4}/\d+', '', t)
    t = re.sub(r',?\s*sådan\w* (?:\S+ ){0,2}?lyder i landskapslagen \d{4}/\d+', '', t)
    ops = []
    for seg in re.split(r'(?=\b(?:ändras|fogas|upphävs)\b)', t):
        seg = seg.strip(' ,')
        if not seg:
            continue
        verb = seg.split()[0]
        if verb not in ('ändras', 'fogas', 'upphävs'):
            raise ReplayError('clause not understood: ' + seg[:80])
        temp = bool(re.match(r'\w+\s+temporärt', seg))
        s = re.sub(r'^\w+(\s+temporärt)?\s*', '', seg)
        s = s.replace(' samt ', ' , ').replace(' och ', ' & ')
        if verb == 'fogas':
            s2 = s
            for m in re.finditer(rf'till (?:lagens )?({K})\s*§ ett nytt (\d+)\s*mom\.', s2):
                ops.append(('insert_sub', skey(m.group(1)), int(m.group(2)), temp))
            s2 = re.sub(rf'till (?:lagens )?{K}\s*§ ett nytt \d+\s*mom\.', '', s2)
            got = 0
            for m in re.finditer(rf'(?:till lagens (\d+) kap\.\s*)?(?:en ny|nya) ({LIST.replace("och", "&")})\s*§§?', s2):
                for key in expand(m.group(2).replace('&', 'och')):
                    ops.append(('insert_sec', skey(key), (m.group(1) + ' kap.') if m.group(1) else None, temp))
                got += 1
            s2 = re.sub(rf'(?:till lagens \d+ kap\.\s*)?(?:en ny|nya) {LIST.replace("och", "&")}\s*§§?', '', s2)
            if re.search(r'\d', re.sub(r'till lagen', '', s2)):
                raise ReplayError('insertion not understood: ' + seg)
            continue
        s = re.sub(r'^(till lagen(s)?\s*)', '', s)
        items = re.compile(rf'rubriken (?:till|för) (\d+) kap\.|rubriken (?:till|för|samt) ({K})\s*§|({K})\s*§\s*rubriken(?:\s*[&,]\s*(\d+(?:\s*[&,]\s*\d+)*)\s*mom\.)?'
                           rf'|({K})\s*§\s*(\d+(?:\s*[&,]\s*\d+)*)\s*mom\.|({K})\s*§\s*(\d+) punkten|({LIST.replace("och", "&")})\s*§§|({K})\s*§')
        pos = 0
        for m in items.finditer(s):
            gap = s[pos:m.start()].strip(' ,&')
            if re.search(r'\d', gap):
                raise ReplayError(f'clause fragment not understood: {gap!r} in {seg}')
            pos = m.end()
            g = m.groups()
            if verb == 'upphävs':
                keys = expand(g[8].replace('&', 'och')) if g[8] else [skey(g[9] or g[2] or g[4])]
                ops += [('repeal_sec', k, None, temp) for k in keys]
            elif g[0]:
                ops.append(('chapter_heading', g[0] + ' kap.', None, temp))
            elif g[1]:
                ops.append(('heading', skey(g[1]), None, temp))
            elif g[2]:
                ops.append(('heading', skey(g[2]), None, temp))
                if g[3]:
                    ops.append(('replace_sub', skey(g[2]), [int(x) for x in re.findall(r'\d+', g[3])], temp))
            elif g[4]:
                ops.append(('replace_sub', skey(g[4]), [int(x) for x in re.findall(r'\d+', g[5])], temp))
            elif g[6]:
                ops.append(('replace_point', skey(g[6]), int(g[7]), temp))
            elif g[8]:
                ops += [('replace_sec', k, None, temp) for k in expand(g[8].replace('&', 'och'))]
            else:
                ops.append(('replace_sec', skey(g[9]), None, temp))
        if re.search(r'\d', s[pos:]):
            raise ReplayError(f'clause tail not understood: {s[pos:]!r}')
    if not ops:
        raise ReplayError('no operations in clause: ' + clause[:100])
    return ops


# ---- replay --------------------------------------------------------------------------------------------------------
def find_sec(act: dict, k: str):
    for ch in act['chapters']:
        for s in ch['sections']:
            if s['num'] == k:
                return ch, s
    return None, None


def snapshot(sec: dict) -> dict:
    return {'num': sec['num'], 'heading': sec['heading'], 'moments': [list(m) for m in sec['moments']], 'repealed': sec['repealed']}


def apply_act(act: dict, parsed: dict, ops: list) -> dict:
    """Replay one parsed amending act (in place). Returns {'changed': [keys], 'pre': {key: snapshot or None},
    'chapters_changed': [...]}; 'pre' holds the text before the change for the temporary units."""
    body = {}
    chap_body = {}
    for kind, e in parsed['elements']:
        if kind == 'section':
            body[e['num']] = e
        else:
            chap_body[e['num']] = e
    changed, used, pre = [], set(), {}
    per_sub = {}

    def remember(k):
        if k not in pre:
            _, s = find_sec(act, k)
            pre[k] = snapshot(s) if s else None

    for kind, k, extra, temp in ops:
        if kind in ('replace_sub', 'insert_sub'):
            per_sub.setdefault(k, {'replace': [], 'insert': [], 'temp': temp})
            per_sub[k]['replace' if kind == 'replace_sub' else 'insert'] += extra if kind == 'replace_sub' else [extra]
            continue
        if kind == 'replace_sec':
            _, old = find_sec(act, k)
            if old is None:
                raise ReplayError(f'{k} § not in act')
            b = body.get(k)
            if b is None or None in b['seq']:
                raise ReplayError(f'{k} § named whole but body {"missing" if b is None else "has omission marks"}')
            if temp:
                remember(k)
            old['heading'], old['moments'] = b['heading'], [list(m) for m in b['seq']]
            used.add(k)
        elif kind == 'heading':
            _, old = find_sec(act, k)
            if old is None or k not in body:
                raise ReplayError(f'heading of {k} §: section or body missing')
            if temp:
                remember(k)
            old['heading'] = body[k]['heading']
            used.add(k)
        elif kind == 'chapter_heading':
            ch = next((c for c in act['chapters'] if c['num'] == k), None)
            if ch is None or k not in chap_body:
                raise ReplayError(f'chapter {k}: not in act or body')
            ch['heading'] = chap_body[k]['heading']
            changed.append(k)
            continue
        elif kind == 'repeal_sec':
            _, old = find_sec(act, k)
            if old is None:
                raise ReplayError(f'repeal: {k} § not in act')
            for ch in act['chapters']:
                ch['sections'] = [s for s in ch['sections'] if s['num'] != k]
        elif kind == 'replace_point':
            _, old = find_sec(act, k)
            b = body.get(k)
            if old is None or b is None:
                raise ReplayError(f'point of {k} §: missing')
            all_lines = [x for m in b['seq'] if m for x in m]
            new_lines = [x for x in all_lines if x.startswith(f'{extra})')]
            # the body may repeat the moment's lead-in for context; it must be the text already in force
            old_lines = {clean(x) for m in old['moments'] for x in m} if old else set()
            context = [x for x in all_lines if not x.startswith(f'{extra})')]
            if any(clean(x) not in old_lines for x in context):
                raise ReplayError(f'{k} § {extra} punkten: context line differs from the text in force: {context}')
            if len(new_lines) != 1 or not new_lines[0].startswith(f'{extra})'):
                raise ReplayError(f'{k} § {extra} punkten: body gives {new_lines}')
            hit = [(i, j) for i, m in enumerate(old['moments']) for j, x in enumerate(m) if x.startswith(f'{extra}) ')]
            if len(hit) != 1:
                raise ReplayError(f'{k} § {extra} punkten: {len(hit)} matches in act')
            if temp:
                remember(k)
            old['moments'][hit[0][0]][hit[0][1]] = new_lines[0]
            used.add(k)
        elif kind == 'insert_sec':
            if find_sec(act, k)[1] is not None:
                raise ReplayError(f'insert: {k} § already in act')
            b = body.get(k)
            if b is None or None in b['seq']:
                raise ReplayError(f'insert: {k} § body missing or has omission marks')
            new = {'num': k, 'heading': b['heading'], 'moments': [list(m) for m in b['seq']], 'repealed': False}
            if temp:
                pre[k] = None
            if extra:
                ch = next((c for c in act['chapters'] if c['num'] == extra), None)
                if ch is None:
                    raise ReplayError(f'insert into {extra}: no such chapter')
                idx = next((i for i, s in enumerate(ch['sections']) if sort_key(s['num']) > sort_key(k)), len(ch['sections']))
                ch['sections'].insert(idx, new)
            else:
                prev = max((s['num'] for c in act['chapters'] for s in c['sections'] if sort_key(s['num']) < sort_key(k)), key=sort_key)
                ch, _ = find_sec(act, prev)
                idx = next(i for i, s in enumerate(ch['sections']) if s['num'] == prev) + 1
                ch['sections'].insert(idx, new)
            used.add(k)
        changed.append(k)
    for k, d in per_sub.items():
        _, old = find_sec(act, k)
        b = body.get(k)
        if old is None or b is None:
            raise ReplayError(f'{k} §: not in act or body')
        listed = sorted(set(d['replace']) | set(d['insert']))
        new = [m for m in b['seq'] if m is not None]
        if len(new) != len(listed):
            raise ReplayError(f'{k} §: body has {len(new)} moments, clause names {listed}')
        if d['temp']:
            remember(k)
        text = dict(zip(listed, new))
        for n in sorted(d['replace']):
            if n > len(old['moments']):
                raise ReplayError(f'{k} § has no {n} mom.')
            old['moments'][n - 1] = list(text[n])
        for n in sorted(d['insert']):
            if n > len(old['moments']) + 1:
                raise ReplayError(f'{k} §: cannot insert {n} mom.')
            old['moments'].insert(n - 1, list(text[n]))
        used.add(k)
        changed.append(k)
    unused = set(body) - used
    if unused:
        raise ReplayError(f'body sections not covered by the clause: {sorted(unused)}')
    changed = sorted(set(changed), key=lambda x: (0, sort_key(x)) if re.match(r'\d+[a-z]?$', x) else (1, (int(x.split()[0]), '')))
    return {'changed': changed, 'pre': pre}


def restore(act: dict, pre: dict) -> list:
    """End of a temporary change: put the remembered text back (None = the unit did not exist: remove it)."""
    changed = []
    for k, snap in pre.items():
        ch, old = find_sec(act, k)
        if snap is None:
            if old is not None:
                ch['sections'] = [s for s in ch['sections'] if s['num'] != k]
        elif old is None:
            raise ReplayError(f'restore {k} §: section gone')
        else:
            old['heading'], old['moments'] = snap['heading'], [list(m) for m in snap['moments']]
        changed.append(k)
    return sorted(changed, key=sort_key)


def canon(act: dict) -> dict:
    """{section key: (chapter line, heading, moments)} with repealed sections left out."""
    out = {}
    for ch in act['chapters']:
        for s in ch['sections']:
            if s.get('repealed'):
                continue
            out[s['num']] = ((ch['num'] + ' ' + ch['heading']).strip(), s['heading'], [[clean(x) for x in m] for m in s['moments']])
    return out
