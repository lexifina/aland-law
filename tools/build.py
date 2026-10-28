"""Builds the Åland git-for-law repository from Ålex (the current consolidation) and the ÅFS PDFs (the Statute Book).

    python -X utf8 build.py [--repo DIR] [--offline] [--today YYYY-MM-DD] [--gate-only]

For each act: the current consolidation is fetched from Ålex, https://www.regeringen.ax/alandsk-lagstiftning/alex/<year><no>,
with its list of amending ÅFS acts and their commencement provisions; the original act and every amending act are fetched
as PDFs from the Statute Book (Ålands författningssamling), .../sites/default/files/attachments/law/afs<year>_Nr<no>.pdf.
Ålex serves only the CURRENT text, so the intermediate versions are REPLAYED (parse.py: whole-section, moment, point and
heading replacement, moment and section insertion, repeal; no AI, no fuzzy edits). The gate: the replayed end state must
equal the Ålex consolidation after one declared normalisation (NORMALISATION below). Only then are commits made.

One commit per amending act per in-force day, authored by the act. Needs PyMuPDF (pymupdf); otherwise standard library.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parse as P  # noqa: E402

CACHE = HERE / 'cache'
UA = 'LexifinaLawHistory/1.0 (law@lexifina.com)'
SITE = 'https://www.regeringen.ax'
ALEX = SITE + '/alandsk-lagstiftning/alex/'
PDF = SITE + '/sites/default/files/attachments/law/afs{y}_{nr}{n}.pdf'
PUBLISHER = 'Ålands landskapsregering (Ålex)'
EMAIL = 'aland-law@lexifina.com'

ACTS = [
    {'dir': 'hemvardsstod', 'year': 2015, 'no': 68, 'short': 'Hemvårdsstöd',
     'name': 'Landskapslag (2015:68) om hemvårdsstöd'},
]

NORMALISATION = (
    '(1) whitespace: no-break and em spaces and tabs are read as spaces, runs of whitespace as one space, soft hyphens '
    '(U+00AD) are dropped and a word broken at a line end is joined; (2) Ålex: inline markup (links, emphasis) joins '
    'without a space, the amendment labels such as "(2022/56)" are dropped, and the editorial notes (div '
    '"anmarkning", e.g. under 21 §) are not law text; (3) ÅFS PDF: an unmapped glyph (U+FFFD) before a line-end hyphen '
    'is the consonant doubled at a Swedish triple-consonant break ("til-lämpning"), so the word is joined as written '
    'unbroken ("tillämpning"); the publisher\'s headers, footers, signatures and footnotes are dropped by content.')


# ---- fetching --------------------------------------------------------------------------------------------------------
def fetch(url: str, offline: bool = False):
    """Body bytes, or None for a cached/real 404. Cached on disk, negative answers too."""
    CACHE.mkdir(exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n', encoding='utf-8', newline='\n')
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest() + '.bin')
    if f.exists():
        d = f.read_bytes()
        return None if d == b'\x00404' else d
    if offline:
        raise SystemExit(f'--offline: {url} is not in the cache')
    d = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'gzip'})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    d = gzip.decompress(d)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                f.write_bytes(b'\x00404')
                return None
            if e.code in (429, 503):
                time.sleep(10 * (attempt + 1))
                continue
            raise
        except Exception:
            out = subprocess.run(['curl', '-sS', '-f', '--compressed', '-A', UA, url], capture_output=True)
            if out.returncode == 0:
                d = out.stdout
                break
            time.sleep(2)
    if d is None:
        raise SystemExit('cannot fetch ' + url)
    f.write_bytes(d)
    stamp_f = CACHE / 'retrieved.txt'
    if not stamp_f.exists():
        stamp_f.write_text(dt.date.today().isoformat() + '\n', encoding='utf-8', newline='\n')
    time.sleep(1)
    return d


def retrieved() -> str:
    p = CACHE / 'retrieved.txt'
    return p.read_text(encoding='utf-8').strip() if p.exists() else dt.date.today().isoformat()


def pdf_url(y: int, n: int, offline: bool):
    """The ÅFS PDF; recent years use 'Nr', older ones 'nr' (both tried, the 404 cached)."""
    for nr in ('Nr', 'nr'):
        u = PDF.format(y=y, nr=nr, n=n)
        b = fetch(u, offline)
        if b is not None and b.startswith(b'%PDF'):
            return u, b
    raise SystemExit(f'ÅFS {y}/{n}: no PDF')


def alex_meta(page: str) -> dict:
    """{id: {'commencement': [paragraphs], 'works': [preparatory works]}} from Ålex's 'andringinfo' blocks."""
    out = {}
    j = page.index('class="andringinfosektion"')
    for m in re.finditer(r'<div class="andringinfo">\s*<h3 id="an_\d+">([^<]*)</h3>(.*?)(?=<div class="andringinfo">|$)',
                         page[j:], re.S):
        ik = re.search(r'<div class="ikrafttradelsedigi">(.*?)</div>', m.group(2), re.S)
        paras = [P._text(x) for x in re.findall(r'<p>(.*?)</p>', ik.group(1), re.S)] if ik else []
        fw = re.search(r'<div class="forarbeteshanvisningar">(.*?)</div>', m.group(2), re.S)
        works = [P._text(x) for x in re.findall(r'<li>(.*?)</li>', fw.group(1), re.S)] if fw else []
        out[m.group(1).strip()] = {'commencement': [p for p in paras if p], 'works': works}
    return out


def load_act(cfg: dict, offline: bool) -> dict:
    y, n = cfg['year'], cfg['no']
    alex_url = f'{ALEX}{y}{n}'
    page = fetch(alex_url, offline).decode('utf-8')
    cons = P.parse_alex(page)
    meta = alex_meta(page)
    base_url, base_b = pdf_url(y, n, offline)
    base = P.parse_pdf(base_b)
    if not base['original']:
        raise SystemExit(f'{y}/{n}: the PDF is not an original act')
    ams = []
    for k, (ident, m) in enumerate(meta.items()):
        if ident == f'{y}:{n}':
            continue
        ay, an = (int(x) for x in ident.split('/'))
        url, b = pdf_url(ay, an, offline)
        parsed = P.parse_pdf(b)
        if parsed['original']:
            raise SystemExit(f'{ident}: not an amending act')
        days = {P.iso(x) for x in m['commencement'] if 'träder i kraft' in x} - {None}
        pdf_day = P.iso(parsed['commencement'])
        if len(days) != 1 or pdf_day not in days:
            raise SystemExit(f'{ident}: commencement Ålex {days} vs ÅFS {pdf_day}: needs per-section dates')
        ams.append({'year': ay, 'no': an, 'id': ident, 'url': url, 'parsed': parsed, 'title': P.clean(parsed['title']),
                    'enacted': parsed['issued'], 'in_force': pdf_day, 'commencement': m['commencement'],
                    'works': m['works'], 'ops': P.parse_clause(parsed['clause'], base['title'])})
    ams.sort(key=lambda a: (a['in_force'], a['year'], a['no']))
    base_day = P.iso(base['commencement'])
    updated = cons['updated'] or (ams[-1]['id'] if ams else f'{y}:{n}')  # Ålex lists the acts up to its update
    return {'cfg': cfg, 'alex_url': alex_url, 'page': page, 'cons': cons, 'base': base, 'base_url': base_url,
            'base_inforce': base_day, 'base_works': meta.get(f'{y}:{n}', {}).get('works', []), 'ams': ams, 'updated': updated}


def replay_all(data: dict):
    """Replay; returns (states, changed). Raises ReplayError."""
    act = P.act_from_elements(data['base']['elements'], data['base']['title'])
    states = [json.loads(json.dumps(act))]
    changed = []
    for a in data['ams']:
        if any(op[3] for op in a['ops']):
            raise P.ReplayError(f'{a["id"]}: a temporary change needs an end date')
        changed.append(P.apply_act(act, a['parsed'], a['ops'])['changed'])
        states.append(json.loads(json.dumps(act)))
    return states, changed


def gate(final: dict, cons: dict) -> list:
    A, B = P.canon(final), P.canon(cons)
    bad = sorted(set(A) ^ set(B), key=P.sort_key)
    bad += [k for k in sorted(A, key=P.sort_key) if k in B and A[k] != B[k]]
    return bad


# ---- rendering -------------------------------------------------------------------------------------------------------
def fname(k: str) -> str:
    m = re.fullmatch(r'(\d+)([a-z]*)', k)
    return f'paragraf-{int(m.group(1)):03d}{m.group(2)}.md'


def render(chapter: dict, sec: dict) -> str:
    out = [f'# {sec["num"]} § {sec["heading"]}'.rstrip()]
    if chapter['num'].strip():
        out.append(f'Kapitel: {chapter["num"]} {chapter["heading"]}'.rstrip())
    for mom in sec['moments']:
        out.append('')
        out += [P.clean(x) for x in mom]
    return '\n'.join(out) + '\n'


def files_of(act: dict, intro: str) -> dict:
    d = {'rubrik.md': intro}
    for ch in act['chapters']:
        for s in ch['sections']:
            if not s.get('repealed'):
                d[fname(s['num'])] = render(ch, s)
    return d


def intro_of(data: dict) -> str:
    cfg = data['cfg']
    return f'Landskapslag ({cfg["year"]}:{cfg["no"]}) {P.clean(data["base"]["title"])}\n{P.clean(data["base"]["clause"])}\n'


# ---- dates -----------------------------------------------------------------------------------------------------------
def last_sunday(y, m):
    d = dt.date(y, m, 31)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def utc_offset(day: dt.date) -> str:
    """Mariehamn (Finnish time): EET +0200, EEST +0300 from the last Sunday of March to the last Sunday of October,
    start <= day < end (at noon the clock change of that Sunday has already happened)."""
    summer = last_sunday(day.year, 3) <= day < last_sunday(day.year, 10)
    return '+0300' if summer else '+0200'


def stamp(day: str, extra_seconds: int = 0) -> str:
    d = dt.date.fromisoformat(day)
    if d.year < 1970:
        return f'1970-01-01T12:00:{extra_seconds:02d}+0000'
    return f'{d.isoformat()}T12:00:{extra_seconds:02d}{utc_offset(d)}'


# ---- git -------------------------------------------------------------------------------------------------------------
def git(repo, *args, env=None, inp=None):
    e = dict(os.environ)
    e.update(env or {})
    r = subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.safecrlf=false', *args], cwd=repo, env=e,
                       input=inp, capture_output=True, text=True, encoding='utf-8')
    if r.returncode:
        raise SystemExit(f'git {" ".join(args)}: {r.stderr}')
    return r.stdout


def commit(repo, author, email, day, msg, extra=0):
    ts = stamp(day, extra)
    env = {'GIT_AUTHOR_NAME': author, 'GIT_AUTHOR_EMAIL': email, 'GIT_AUTHOR_DATE': ts,
           'GIT_COMMITTER_NAME': 'Lexifina', 'GIT_COMMITTER_EMAIL': EMAIL, 'GIT_COMMITTER_DATE': ts}
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '--allow-empty', '-F', '-', env=env, inp=msg)


def rmtree(p):
    def fix(func, path, exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(p, onexc=fix)


def sync(repo: Path, folder: str, files: dict):
    d = repo / folder
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for name in sorted(files):
        (d / name).write_text(files[name], encoding='utf-8', newline='\n')


def amend_message(data, a, prev_keys, new_keys, changed):
    cfg = data['cfg']
    secs = [k for k in changed if re.fullmatch(r'\d+[a-z]?', k)]
    added = [k for k in secs if k not in prev_keys]
    removed = [k for k in prev_keys if k not in new_keys]
    mod = [k for k in secs if k in prev_keys and k in new_keys]
    first = ', '.join(f'{k} §' for k in changed[:6]) + (f' (+{len(changed) - 6})' if len(changed) > 6 else '')
    lines = [f'{cfg["short"]}: {first} (ÅFS {a["id"]})', '', f'Landskapslag ({a["year"]}:{a["no"]}) {a["title"]}', '',
             'The replayed intermediate version: Ålex serves only the current consolidation, so this version is replayed '
             'from the amending act as printed in the Statute Book; only the end state is checked against Ålex.', '']
    if mod:
        lines.append('Ändrade: ' + ', '.join(f'{k} §' for k in mod))
    if added:
        lines.append('Nya: ' + ', '.join(f'{k} §' for k in added))
    if removed:
        lines.append('Upphävda: ' + ', '.join(f'{k} §' for k in removed))
    lines.append('')
    lines += [f'Evidence: replay of ÅFS {a["id"]} verified against the Ålex consolidation (updated to ÅFS '
              f'{data["updated"]})',
              'Kind: Landskapslag', f'Enacted: {a["enacted"]}' if a['enacted'] else None,
              f'In-force: {a["in_force"]}']
    lines += [f'Commencement: {x}' for x in a['commencement'] if 'träder i kraft' in x]
    lines += [f'Applies: {x}' for x in a['commencement'] if 'träder i kraft' not in x]
    lines += [f'Preparatory-works: {w}' for w in a['works']]
    lines += ['Affecting: ' + ', '.join(f'{cfg["year"]}:{cfg["no"]} {k}' + (' §' if re.fullmatch(r'\d+[a-z]?', k) else '')
                                        for k in changed),
              f'Source: {a["url"]}', f'Consolidated: {data["alex_url"]}']
    return '\n'.join(x for x in lines if x is not None) + '\n'


def base_message(data):
    cfg = data['cfg']
    b = data['base']
    lines = [f'{cfg["short"]}: {cfg["name"]} (ÅFS {cfg["year"]}:{cfg["no"]})', '',
             'Lagen sådan den antogs och publicerades i Ålands författningssamling.',
             'The act as enacted: the original text from the Statute Book, before any amendment.', '',
             'Evidence: original text from the Statute Book (the base of the replay)', 'Kind: Landskapslag',
             f'Enacted: {b["issued"]}' if b['issued'] else None, f'In-force: {data["base_inforce"]}',
             f'Commencement: {b["commencement"]}']
    lines += [f'Preparatory-works: {w}' for w in data['base_works']]
    lines += [f'Source: {data["base_url"]}', f'Consolidated: {data["alex_url"]}']
    return '\n'.join(x for x in lines if x is not None) + '\n'


def tag_of(cfg, y, n):
    return f'{cfg["dir"]}/{y}-{n}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(HERE.parents[2] / 'aland-law'))
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--today', default=None)
    ap.add_argument('--gate-only', action='store_true')
    ap.add_argument('--verify-rebuild', action='store_true',
                    help='rebuild offline into a temporary folder and require the same main hash as --repo')
    args = ap.parse_args()
    if args.verify_rebuild:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cmd = [sys.executable, '-X', 'utf8', __file__, '--offline', '--repo', str(Path(tmp) / 'r')]
            if args.today:
                cmd += ['--today', args.today]
            subprocess.run(cmd, check=True, capture_output=True)
            a, b = git(Path(tmp) / 'r', 'rev-parse', 'main').strip(), git(args.repo, 'rev-parse', 'main').strip()
            rmtree(Path(tmp) / 'r')
        print('rebuild', a, 'repo', b, 'IDENTICAL' if a == b else 'DIFFERENT')
        raise SystemExit(0 if a == b else 1)
    sys.stdout.reconfigure(encoding='utf-8')
    datas, events, report = [], [], {}
    for cfg in ACTS:
        data = load_act(cfg, args.offline)
        states, changed = replay_all(data)
        bad = gate(states[-1], data['cons'])
        report[cfg['dir']] = {'act': f'{cfg["year"]}:{cfg["no"]}', 'amendments': len(data['ams']),
                              'sections': len(P.canon(states[-1])), 'mismatches': bad,
                              'consolidation_updated_to': data['updated']}
        print(cfg['dir'], report[cfg['dir']])
        if bad:
            raise SystemExit(f'GATE FAILED for {cfg["dir"]}: sections {bad}')
        data['states'], data['changed'] = states, changed
        datas.append(data)
    if args.gate_only:
        return
    today = args.today or retrieved()
    repo = Path(args.repo)
    if repo.exists():
        for p in repo.iterdir():
            if p.name != '.git':
                rmtree(p) if p.is_dir() else p.unlink()
    else:
        repo.mkdir(parents=True)
    if (repo / '.git').exists():
        rmtree(repo / '.git')
    git(repo, 'init', '-q', '-b', 'main')
    for i, d in enumerate(datas):
        events.append((d['base_inforce'], 0, i, -1))
        for j, a in enumerate(d['ams']):
            if a['in_force'] <= today:
                events.append((a['in_force'], 1, i, j))
    events.sort()
    (repo / '.gitattributes').write_text('* text eol=lf\n', encoding='utf-8', newline='\n')
    for n, (day, _, i, j) in enumerate(events):
        d = datas[i]
        cfg = d['cfg']
        files = files_of(d['states'][j + 1], intro_of(d))
        sync(repo, cfg['dir'], files)
        if j < 0:
            msg = base_message(d)
            y, no = cfg['year'], cfg['no']
        else:
            a = d['ams'][j]
            msg = amend_message(d, a, set(P.canon(d['states'][j])), set(P.canon(d['states'][j + 1])), d['changed'][j])
            y, no = a['year'], a['no']
        commit(repo, f'ÅFS {y}/{no}', f'afs-{y}-{no}@regeringen.ax.invalid', day, msg, extra=n % 50)
        git(repo, 'tag', tag_of(cfg, y, no))
    (HERE / 'gate.json').write_text(json.dumps({'normalisation': NORMALISATION, 'acts': report}, indent=1,
                                               ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print('law commits:', len(events))
    import reproduce
    reproduce.write_docs(repo, datas, report, today, HERE)
    git(repo, 'add', '-A')
    env = {'GIT_AUTHOR_NAME': 'Lexifina', 'GIT_AUTHOR_EMAIL': EMAIL, 'GIT_AUTHOR_DATE': stamp(today),
           'GIT_COMMITTER_NAME': 'Lexifina', 'GIT_COMMITTER_EMAIL': EMAIL, 'GIT_COMMITTER_DATE': stamp(today)}
    msg = ('Documentation, tools and REPRODUCE.md\n\nNo law text changes. The tools, README, LICENSE, corpus.json, the '
           'table of amending acts and REPRODUCE.md.\n\nKind: documentation\nIn-force: ' + today + '\n')
    git(repo, 'commit', '-q', '--allow-empty', '-F', '-', env=env, inp=msg)
    print('main', git(repo, 'rev-parse', 'HEAD').strip())


if __name__ == '__main__':
    main()
