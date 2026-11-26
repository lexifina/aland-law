"""Appends Åland's constitutional law to the aland-law repository (append-only: new commits on top of main).

    python -X utf8 append.py --repo DIR [--offline] [--dry-run]

1. lagtingsordning/: Lagtingsordning (2011:97) för Åland, from its ÅFS PDF, with the 5 amending acts (2012/71,
   2013/24, 2015/66, 2023/92, 2023/135) replayed from their ÅFS PDFs by build.py/parse.py's engine. The operations of
   each amending act are written out below from its enacting clause (OPS): the clause grammar in parse.py does not
   read these clauses (renumbering "varvid", repealed moments, points within a moment), so they are stated by hand,
   one entry per unit the clause names, and checked: every body section must be used, and the replayed end state must
   equal the Ålex consolidation (the gate). 8 kap. (Finanserna) came into force on 2013-01-01, the rest on 2011-11-01.
2. sjalvstyrelselag/: Självstyrelselag (1991:71) för Åland (FFS 1144/1991), Ålex's Swedish consolidation, current
   text only, one commit dated the in-force day of its newest amendment (ÅFS 2020/33 = FFS 98/2020, 2021-01-01).

Commits are dated noon Europe/Mariehamn on the in-force day and carry In-force trailers; the committer is Lexifina.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
import lo_try as L  # noqa: E402  (patches build/parse: ÅFS node URLs, 2011:97 commencement, editorial lines)

B, P = L.B, L.P
R = 'replace_sec'


def sub(k, *n):
    return ('replace_sub', k, list(n), False)


def ins(k, n):
    return ('insert_sub', k, n, False)


def sec(*ks):
    return [(R, k, None, False) for k in ks]


def head(k):
    return ('heading', k, None, False)


def rsub(k, n):
    return ('repeal_sub', k, n, False)


def point(k, mom, label, how):
    return ('point', k, (mom, label, how), False)


OPS = {
    # ändras 54 § 4 mom. och 57 §
    '2012/71': [sub('54', 4), *sec('57')],
    # ändras 31 § 1 mom. och 56 § samt fogas till 28 § ett nytt 6 mom., varvid nuvarande 6-7 mom. blir 7-8 mom.
    '2013/24': [sub('31', 1), *sec('56'), ins('28', 6)],
    # ändras 5 § 3 mom., 7 §, 13-14 §§, 18 §, 20 §, 21 §, 25 § 1-2 mom., 26 § 2 mom., 28 § 1 mom., 31 § 2 mom.,
    # 33 § 1 mom., 34 §, 36 §, 38 § 1 mom., 41 §, 46 § 2 mom., 48 §, 52 §, 58 § 1 mom., 59 § 3 mom., 61 § och 64 §
    # samt rubriken till 11 kap. samt fogas till 19 § ett nytt 4 mom., en ny 21a §, till 28 § ett nytt 2 mom. [...]
    # samt ett nytt 5 mom. [...] till 44 § ett nytt 2 mom. samt till 53 § ett nytt 4 mom.
    '2015/66': [sub('5', 3), *sec('7', '13', '14', '18', '20', '21'), sub('25', 1, 2), sub('26', 2), sub('28', 1),
                sub('31', 2), sub('33', 1), *sec('34', '36'), sub('38', 1), *sec('41'), sub('46', 2), *sec('48', '52'),
                sub('58', 1), sub('59', 3), *sec('61', '64'), ('chapter_heading', '11 kap.', None, False),
                ins('19', 4), ('insert_sec', '21a', None, False), ins('28', 2), ins('28', 5), ins('44', 2),
                ins('53', 4)],
    # upphävs 5 § 3 mom., ändras rubriken till 5 § och 5 § 2 mom., 6 § 1 mom., rubriken till 8 § och 8 § 3 mom., 9 §,
    # rubriken till 16 § och 16 § 1 och 3 mom., 17 §, 18 § 1 mom., 20 § 1 och 2 mom., 21 § 1 och 3 mom., 21a §,
    # 23 § 1 mom., 28 § 3 mom., 32 §, 42 §, rubriken till 45 §, 52 §, 53 § 1 mom. och 59 §, samt fogas till lagen en
    # ny 12a §, till 28 § ett nytt 7 mom. varvid gällande 7–10 mom. blir 8–11 mom.
    '2023/92': [rsub('5', 3), head('5'), sub('5', 2), sub('6', 1), head('8'), sub('8', 3), *sec('9'), head('16'),
                sub('16', 1, 3), *sec('17'), sub('18', 1), sub('20', 1, 2), sub('21', 1, 3), *sec('21a'), sub('23', 1),
                sub('28', 3), *sec('32', '42'), head('45'), *sec('52'), sub('53', 1), *sec('59'),
                ('insert_sec', '12a', None, False), ins('28', 7)],
    # upphävs 53 § 2 mom., ändras 28 § 3 mom. 2 punkten och 8 mom. 3 punkten, 31 § 1 mom., 52 § och 54 § 1–3 mom.,
    # samt fogas till 28 § 3 mom. en ny 2a punkten och till lagen en ny 51a §
    '2023/135': [rsub('53', 2), point('28', 3, '2', 'replace'), point('28', 3, '2a', 'insert'),
                 point('28', 8, '3', 'replace'), sub('31', 1), *sec('52'), sub('54', 1, 2, 3),
                 ('insert_sec', '51a', None, False)],
}

_orig_apply = P.apply_act


def apply_act(act, parsed, ops):
    """parse.apply_act plus two operations it does not have: a repealed moment, and a point replaced or inserted
    within a named moment. A section changed only by these is taken out of the body before the engine runs."""
    extra = [o for o in ops if o[0] in ('repeal_sub', 'point')]
    rest = [o for o in ops if o[0] not in ('repeal_sub', 'point')]
    body = {e['num']: e for kind, e in parsed['elements'] if kind == 'section'}
    changed = []
    pts = [o for o in extra if o[0] == 'point']
    for k in {o[1] for o in pts}:
        lines = [x for m in body[k]['seq'] if m for x in m]
        _, s = P.find_sec(act, k)
        old = {P.clean(x) for m in s['moments'] for x in m}
        new_pts = [x for x in lines if P.POINT.match(x) or re.match(r'^\d+[a-z]\)\s', x)]
        context = [x for x in lines if x not in new_pts]
        if any(P.clean(x) not in old for x in context):
            raise P.ReplayError(f'{k} §: context line differs from the text in force')
        mine = [o for o in pts if o[1] == k]
        if len(new_pts) != len(mine):
            raise P.ReplayError(f'{k} §: body gives {len(new_pts)} points, clause names {len(mine)}')
        for (_, _, (mom, label, how), _), line in zip(mine, new_pts):
            if not line.startswith(label + ') '):
                raise P.ReplayError(f'{k} § {mom} mom. {label} punkten: body line {line[:30]}')
            m = s['moments'][mom - 1]
            if how == 'replace':
                hit = [i for i, x in enumerate(m) if x.startswith(label + ') ')]
                if len(hit) != 1:
                    raise P.ReplayError(f'{k} § {mom} mom. {label} punkten: {len(hit)} matches')
                m[hit[0]] = line
            else:
                prev = re.match(r'\d+', label).group()
                hit = [i for i, x in enumerate(m) if x.startswith(prev + ') ')]
                if len(hit) != 1 or any(x.startswith(label + ') ') for x in m):
                    raise P.ReplayError(f'{k} § {mom} mom.: cannot insert {label} punkten')
                m.insert(hit[0] + 1, line)
        changed.append(k)
    for _, k, n, _ in sorted((o for o in extra if o[0] == 'repeal_sub'), key=lambda o: -o[2]):
        _, s = P.find_sec(act, k)
        if s is None or n > len(s['moments']):
            raise P.ReplayError(f'repeal {k} § {n} mom.: no such moment')
        # Ålex keeps the number of a repealed moment with the note "N mom. upphävt." (the later moments keep theirs)
        s['moments'][n - 1] = [f'{n} mom. upphävt.']
        changed.append(k)
    handled = {o[1] for o in pts}
    if any(o[1] in handled for o in rest):
        raise P.ReplayError('a section with points also has other changes')
    parsed2 = dict(parsed, elements=[(kind, e) for kind, e in parsed['elements']
                                     if not (kind == 'section' and e['num'] in handled)])
    r = _orig_apply(act, parsed2, rest) if rest else {'changed': [], 'pre': {}}
    r['changed'] = sorted(set(r['changed']) | set(changed),
                          key=lambda x: (0, P.sort_key(x)) if re.match(r'\d+[a-z]?$', x) else (1, (int(x.split()[0]), '')))
    return r


P.apply_act = apply_act

# Reading of the older ÅFS PDFs (2013/24, 2015/66, 2023/92), declared: the ligatures ﬁ/ﬂ are fi/fl; a line starting
# with one plain space starts a paragraph (as an indent or an em space does); a word broken at a line end with a hard
# hyphen ("revisions-" / "myndighet") is joined when the next line starts with a lower-case letter and is not a
# conjunction (then the hyphen is part of a compound, "revisions- och"). One misprint inside a line, ÅFS 2015/66 34 §
# "nå-got" (a reflowed break), is read as "något".
CONJ = {'och', 'eller', 'samt', 'respektive', 'till', 'som'}
_orig_pdf_lines = P.pdf_lines


def pdf_lines(data):
    out = _orig_pdf_lines(data)
    for l in out:
        t = l['text'].replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace(' nå-got ', ' något ')
        if re.match(r'^ \S', t):
            t = P.EMSP + t[1:]
        l['text'] = t
    real = [l for l in out if not l['blank']]
    for a, b in zip(real, real[1:]):
        m = re.search(r'[a-zåäöé]-\s*$', a['text'])
        w = re.match(r'\s*([a-zåäöé]+)', b['text'].replace(P.EMSP, ' '))
        if m and w and w.group(1) not in CONJ and not b['text'].startswith(P.EMSP):
            a['text'] = a['text'].rstrip()[:-1] + P.SOFT
    return out


P.pdf_lines = pdf_lines

# Where Ålex's consolidation differs from the Statute Book, the repository follows the Statute Book. Each such place is
# listed: (section, Statute Book text, Ålex text); the gate compares after reading Ålex's text as the Statute Book's.
DEVIATIONS = [('28', '6) en årsredovisning i enlighet med 25 § i landskapslagen (1971:42)',
               '6) en årsredovisning i enlighet med 25 § landskapslagen (1971:42)')]


def cons_as_statute_book(cons):
    c = json.loads(json.dumps(cons))
    for k, afs, alex in DEVIATIONS:
        _, s = P.find_sec(c, k)
        hits = [(m, i) for m in s['moments'] for i, x in enumerate(m) if alex in x]
        if len(hits) != 1:
            raise SystemExit(f'deviation {k} §: {len(hits)} hits in Ålex')
        m, i = hits[0]
        m[i] = m[i].replace(alex, afs)
    return c


def load_lo(offline):
    """build.load_act for 2011:97, with the ops from OPS and the in-force day from the ÅFS PDF where Ålex gives none
    (2013/24, 2015/66)."""
    cfg = L.LO
    y, n = cfg['year'], cfg['no']
    alex_url = f'{B.ALEX}{y}{n}'
    page = B.fetch(alex_url, offline).decode('utf-8')
    cons = P.parse_alex(page)
    meta = B.alex_meta(page)
    base_url, base_b = B.pdf_url(y, n, offline)
    base = P.parse_pdf(base_b)
    assert base['original']
    ams = []
    for ident, m in meta.items():
        if ident == f'{y}:{n}':
            continue
        ay, an = (int(x) for x in ident.split('/'))
        url, b = B.pdf_url(ay, an, offline)
        parsed = P.parse_pdf(b)
        assert not parsed['original'], ident
        pdf_day = P.iso(parsed['commencement'])
        days = {P.iso(x) for x in m['commencement'] if 'träder i kraft' in x} - {None}
        if days and days != {pdf_day}:
            raise SystemExit(f'{ident}: commencement Ålex {days} vs ÅFS {pdf_day}')
        commencement = m['commencement'] or [parsed['commencement']]
        notes = [w for w in m['works'] if 'förordnades att förfalla' in w]
        ams.append({'year': ay, 'no': an, 'id': ident, 'url': url, 'parsed': parsed, 'title': P.clean(parsed['title']),
                    'enacted': parsed['issued'], 'in_force': pdf_day, 'commencement': commencement, 'notes': notes,
                    'works': [w for w in m['works'] if w not in notes], 'ops': OPS[ident]})
    ams.sort(key=lambda a: (a['in_force'], a['year'], a['no']))
    return {'cfg': cfg, 'alex_url': alex_url, 'page': page, 'cons': cons, 'base': base, 'base_url': base_url,
            'base_inforce': P.iso(base['commencement']), 'base_works': meta[f'{y}:{n}']['works'],
            'base_commencement': meta[f'{y}:{n}']['commencement'], 'ams': ams, 'updated': ams[-1]['id']}


# ---- Självstyrelselag: Ålex consolidation ---------------------------------------------------------------------------
def parse_alex_ss(page):
    """parse.parse_alex with two Ålex quirks of 1991:71 read: a chapter heading printed without its number (3 kap.,
    numbered from its place) and lettered chapters (9a kap.)."""
    page2, k = page, 0
    out = []
    prev = 0
    for m in re.finditer(r'(<h2[^>]*>)(.*?)(</h2>)', page2, re.S):
        t = P._text(m.group(2))
        nm = re.match(r'(\d+)([a-z]?) kap\.', t)
        if nm:
            prev = int(nm.group(1))
            out.append(page2[k:m.end()])
        else:
            prev += 1
            out.append(page2[k:m.start()] + m.group(1) + f'{prev} kap.\t' + m.group(2) + m.group(3))
        k = m.end()
    out.append(page2[k:])
    fixed = ''.join(out)
    real = P.re.match

    def match(pat, s, *a, **kw):
        if pat == r'(\d+ kap\.)\s*(.*)':
            pat = r'(\d+[a-z]? kap\.)\s*(.*)'
        return real(pat, s, *a, **kw)
    shim = type(sys)('re_shim')
    shim.__dict__.update(re.__dict__)
    shim.match = match
    P.re = shim
    try:
        return P.parse_alex(fixed)
    finally:
        P.re = re


SS = {'dir': 'grundlag/sjalvstyrelselag', 'year': 1991, 'no': 71, 'short': 'Självstyrelselag',
      'name': 'Självstyrelselag (1991:71) för Åland'}


def load_ss(offline):
    url = f'{B.ALEX}199171'
    page = B.fetch(url, offline).decode('utf-8')
    cons = parse_alex_ss(page)
    meta = B.alex_meta(page)
    newest = list(meta)[-1]
    day = next(P.iso(x) for x in meta[newest]['commencement'] if 'träder i kraft' in x)
    return {'cfg': SS, 'url': url, 'page': page, 'cons': cons, 'meta': meta, 'newest': newest, 'in_force': day}


# ---- rendering and messages -----------------------------------------------------------------------------------------
def lo_files(state, day, intro):
    act = json.loads(json.dumps(state))
    if day < '2013-01-01':
        act['chapters'] = [c for c in act['chapters'] if c['num'] != '8 kap.']
    return B.files_of(act, intro)


def fix_commencement(msg):
    """A transitional provision that mentions 'träder i kraft' is an Applies trailer, not a Commencement."""
    return re.sub(r'^Commencement: (?!Denna )', 'Applies: ', msg, flags=re.M)


def fix_kind(msg, kind):
    msg = fix_commencement(msg.replace('Kind: Landskapslag', 'Kind: ' + kind))
    return re.sub(r'^Landskapslag \((\d{4}):(\d+)\) ', r'ÅFS \1/\2 ', msg, flags=re.M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    lo = load_lo(args.offline)
    states, changed = B.replay_all(lo)
    bad = B.gate(states[-1], cons_as_statute_book(lo['cons']))
    print('lagtingsordning: amendments', len(lo['ams']), 'sections', len(P.canon(states[-1])), 'gate', bad or 'EQUAL')
    if bad:
        raise SystemExit('GATE FAILED: ' + str(bad))
    ss = load_ss(args.offline)
    nsec = len(P.canon(ss['cons']))
    print('sjalvstyrelselag: sections', nsec, 'newest', ss['newest'], ss['in_force'])
    # the first version equals the original act as printed (it is the base of the replay, so this checks rendering)
    lo_intro = f'{lo["cons"]["title"]}\n{P.clean(lo["base"]["clause"])}\n'
    ss_intro = f'{ss["cons"]["title"]}\nFFS 1144/1991\n'
    for d in (lo, ss):
        for s in (c2 for c in d['cons']['chapters'] for c2 in c['sections']):
            assert s['moments'], (d['cfg']['dir'], s['num'])
    if args.dry_run:
        for n, t in sorted(lo_files(states[-1], '2099-01-01', lo_intro).items())[:3]:
            print('---', n, '\n' + t)
        for n, t in sorted(B.files_of(ss['cons'], ss_intro).items())[:3]:
            print('---', n, '\n' + t)
        return
    repo = Path(args.repo)
    events = []  # (day, order, kind, payload)
    events.append((lo['base_inforce'], 0, 'lo-base', None))
    events.append(('2013-01-01', 0, 'lo-8kap', None))
    for j, a in enumerate(lo['ams']):
        events.append((a['in_force'], 1, 'lo-am', j))
    events.append((ss['in_force'], 2, 'ss', None))
    events.sort(key=lambda e: (e[0], e[1]))
    for n, (day, _, kind, j) in enumerate(events):
        if kind == 'lo-base':
            files = lo_files(states[0], day, lo_intro)
            msg = B.base_message(lo)
            msg = msg.replace(f'{L.LO["short"]}: {L.LO["name"]} (ÅFS 2011:97)\n',
                              f'{L.LO["short"]}: {L.LO["name"]} (ÅFS 2011/97)\n')
            msg = msg.replace('Lagen sådan den antogs', 'Lagtingsordningen sådan den antogs')
            msg = msg.replace('Commencement: ', 'Commencement: ', 1)
            msg = msg.replace(f'In-force: {day}\n', f'In-force: {day}\n' + ''.join(
                f'Applies: {x}\n' for x in lo['base_commencement'][1:2]))
            msg = msg.replace('\n\nEvidence:', '\n\n8 kap. (Finanserna) träder i kraft den 1 januari 2013 and is added '
                              'by its own commit on that day. The President ordered 1 § 3 mom. to lapse (Lagens 1 § '
                              '3 mom. förordnades att förfalla); it was not printed and is not here.\n\nEvidence:')
            author = 'ÅFS 2011/97'
            tag = 'lagtingsordning/2011-97'
        elif kind == 'lo-8kap':
            # the state on 2013-01-01 before 2012/71 (same day, next commit)
            files = lo_files(states[0], day, lo_intro)
            keys = [s['num'] for c in states[0]['chapters'] if c['num'] == '8 kap.' for s in c['sections']]
            msg = (f'Lagtingsordning: 8 kap. Finanserna träder i kraft (ÅFS 2011/97)\n\n'
                   f'{L.LO["name"]}, 64 §: "{lo["base"]["commencement"]}"\n\n'
                   f'Nya: {", ".join(k + " §" for k in keys)}\n\n'
                   'Evidence: original text from the Statute Book (the base of the replay)\nKind: Lagtingsordning\n'
                   f'Enacted: {lo["base"]["issued"]}\nIn-force: {day}\nCommencement: {lo["base"]["commencement"]}\n'
                   f'Affecting: {", ".join("2011:97 " + k + " §" for k in keys)}\n'
                   f'Source: {lo["base_url"]}\nConsolidated: {lo["alex_url"]}\n')
            author = 'ÅFS 2011/97'
            tag = 'lagtingsordning/2011-97-8kap'
        elif kind == 'lo-am':
            a = lo['ams'][j]
            files = lo_files(states[j + 1], day, lo_intro)
            msg = B.amend_message(lo, a, set(P.canon(states[j])), set(P.canon(states[j + 1])), changed[j])
            msg = msg.replace(f'Landskapslag ({a["year"]}:{a["no"]}) {a["title"]}',
                              f'ÅFS {a["year"]}/{a["no"]} Lag {a["title"]}')
            if a['notes']:
                msg = msg.replace('\nSource:', ''.join(f'\nNote: {x}' for x in a['notes']) + '\nSource:')
            author = f'ÅFS {a["year"]}/{a["no"]}'
            tag = f'lagtingsordning/{a["year"]}-{a["no"]}'
        else:
            files = B.files_of(ss['cons'], ss_intro)
            m = ss['meta']
            msg = [f'Självstyrelselag: {SS["name"]}, gällande lydelse (Ålex, uppdaterad till ÅFS {ss["newest"]})', '',
                   'Självstyrelselagen i Ålex svenska konsolidering, sådan den gäller sedan den senaste ändringen '
                   f'(ÅFS {ss["newest"]}) trädde i kraft.',
                   'Current text only: Ålex serves only the current consolidation, and the amending acts (Finnish acts '
                   'reprinted in ÅFS) are not replayed, so this one commit is dated the in-force day of the newest '
                   f'amendment, ÅFS {ss["newest"]}. The {len(m) - 1} amending acts are listed below.', '',
                   'Evidence: the Ålex consolidation (current text)', 'Kind: Självstyrelselag (rikslag, FFS 1144/1991)',
                   f'In-force: {day}']
            msg += [f'Commencement: {x}' for x in m[ss['newest']]['commencement'] if 'träder i kraft' in x]
            msg += [f'Amended-by: ÅFS {k} ({", ".join(w for w in v["works"] if w.startswith("FFS"))})'
                    for k, v in m.items() if '/' in k]
            msg += [f'Preparatory-works: {w}' for w in m['1991:71']['works']]
            msg += [f'Source: {ss["url"]}']
            msg = fix_commencement('\n'.join(msg) + '\n')
            author = B.PUBLISHER
            tag = 'sjalvstyrelselag/2020-33'
            B.sync(repo, SS['dir'], files)
            B.commit(repo, author, 'alex@regeringen.ax.invalid', day, msg, extra=n % 50)
            B.git(repo, 'tag', tag)
            print(day, author, tag)
            continue
        B.sync(repo, L.LO['dir'], files)
        y, no = author.split()[1].split('/')
        B.commit(repo, author, f'afs-{y}-{no}@regeringen.ax.invalid', day, fix_kind(msg, 'Lagtingsordning'), extra=n % 50)
        B.git(repo, 'tag', tag)
        print(day, author, tag)


if __name__ == '__main__':
    main()
