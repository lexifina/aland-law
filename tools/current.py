"""Current consolidated texts from Ålex, one commit per act (the acts other than those replayed by build.py).

    python -X utf8 current.py --pages DIR --catalog catalog.json --repo REPO [--today YYYY-MM-DD] [--plan-only]

Each Ålex page (https://www.regeringen.ax/alandsk-lagstiftning/alex/<year><no>, or .../foraldrad-lagstiftning/... for
texts Ålex lists as obsolete) is parsed into one file per section (paragraf), a rubrik.md with the title and one file per
annex (bilaga). The parse is checked before anything is written: the words of the files, in order, must equal the words
of the page's law text with the tags removed (the same declared normalisation as build.py: amendment labels such as
"(2022/56)" and editorial notes are not law text). No AI runs here.

Dating: the commit is dated noon Europe/Mariehamn on the in-force day of the newest act the text shows (the newest
entry in Ålex's list of the act and its amending acts). That day comes from the commencement provision Ålex prints for
it, or, for an act never amended, from the act's own "träder i kraft den ..." provision in the text. An act is HELD
(not committed) when that day is not stated, is after --today, or the page holds an image the text cannot carry.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parse as P  # noqa: E402
import build as B  # noqa: E402

SITE = 'https://www.regeringen.ax'
FORMS = [  # (title prefix pattern, folder kind, Kind trailer)
    (r'Republikens presidents förordning', 'rp-forordning', 'Republikens presidents förordning'),
    (r'Ålands landskapsregerings beslut', 'beslut', 'Ålands landskapsregerings beslut'),
    (r'Landskapsförordning', 'landskapsforordning', 'Landskapsförordning'),
    (r'Förordning', 'forordning', 'Förordning'),
    (r'Lag\b', 'lag', 'Lag'),
    (r'Arbetsordning', 'arbetsordning', 'Arbetsordning'),
    (r'\w*förordning\b', 'landskapsforordning', 'Landskapsförordning'),
    (r'\w*(lag|ordning)\b', 'landskapslag', 'Landskapslag'),
]
SKIP = {'1991:71': 'Självstyrelselag: added by the constitution lane under its own folder',
        '2011:97': 'Lagtingsordning: added by the constitution lane under its own folder',
        '2015:68': 'already held, replayed by build.py (hemvardsstod/)'}


def kind_of(title):
    for pat, folder, kind in FORMS:
        if re.match(pat, title):
            return folder, kind
    head = title.split(' (')[0]
    if head.endswith('förordning'):
        return 'landskapsforordning', 'Landskapsförordning'
    if head.endswith('lag') or head.endswith('ordning'):
        return 'landskapslag', 'Landskapslag'
    raise ValueError(title)


def lines_of(fragment):
    out = []
    for item in re.finditer(r'<p>(.*?)</p>|<p [^>]*>(.*?)</p>|<tr>(.*?)</tr>|<h[4-6][^>]*>(.*?)</h[4-6]>|<li>(.*?)</li>|<caption[^>]*>(.*?)</caption>',
                            fragment, re.S):
        if item.group(3) is not None:
            t = ' | '.join(P._text(c) for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', item.group(3), re.S))
        else:
            t = P._text(next(g for g in (item.group(1), item.group(2), item.group(4), item.group(5), item.group(6)) if g is not None))
        t = t.strip()
        if t.strip(' |'):
            out.append(t)
    return out


LABEL_A = re.compile(r'\s*<a href="#an_\d+">\s*\(\d{4}/\d+\)\s*</a>')


def parse_page(page):
    page = LABEL_A.sub('', page)
    title = P._text(re.search(r'<h1[^>]*>(.*?)</h1>', page, re.S).group(1))
    i = page.index('class="content-body"')
    j = page.index('class="andringinfosektion"')
    body = page[i:j]
    body = body[:body.rindex('<')]
    body = re.sub(r'<div class="anmarkning">.*?</div>', '', body, flags=re.S)
    marks = []
    for m in re.finditer(r'<div class="avdelningsrubrik"[^>]*>(.*?)</div>', body, re.S):
        marks.append((m.start(), 'part', P._text(m.group(1))))
    for m in re.finditer(r'<h2[^>]*>(.*?)</h2>', body, re.S):
        marks.append((m.start(), 'chapter', P._text(m.group(1))))
    for m in re.finditer(r'<h3(?![^>]*\bid=)[^>]*>(.*?)</h3>', body, re.S):
        marks.append((m.start(), 'sub', P._text(m.group(1))))
    marks.sort()
    secs = []
    pars = list(re.finditer(r'<div class="paragraf">', body))
    for k, pm in enumerate(pars):
        end = pars[k + 1].start() if k + 1 < len(pars) else len(body)
        nxt = [p for p, _, _ in marks if pm.start() < p < end]
        end = min(nxt) if nxt else end
        chunk = body[pm.start():end]
        h3 = P._text(re.search(r'<h3[^>]*>(.*?)</h3>', chunk, re.S).group(1))
        hm = re.match(r'(\d+\s?[a-z]{0,2}(?:\s?[-–]\s?\d+\s?[a-z]{0,2})?) ?§§?\.?\s*(.*)', h3)
        if not hm:
            raise ValueError('section heading ' + h3)
        part = chapter = sub = ''
        prev = pars[k - 1].start() if k else -1
        pre = [txt for p, kind, txt in marks if prev < p < pm.start()]
        for p, kind, txt in marks:
            if p < pm.start():
                if kind == 'part':
                    part, chapter, sub = txt, '', ''
                elif kind == 'chapter':
                    chapter, sub = txt, ''
                else:
                    sub = txt
        moments = [lines_of(mm) for mm in re.split(r'<div class="moment">', chunk)[1:]]
        moments = [m for m in moments if m]
        nums = [re.sub(r'\s', '', x) for x in re.split(r'\s?[-–]\s?', hm.group(1))]
        secs.append({'num': '-'.join(nums), 'h3num': hm.group(1), 'heading': hm.group(2).strip(), 'part': part,
                     'chapter': chapter, 'sub': sub, 'pre': pre, 'moments': moments})
    annexes = []
    tail = page[j:page.index('</main')]
    k = tail.find('<div class="bilagesektion"')
    if k >= 0:
        for bm in re.finditer(r'<div class="bilaga">(.*?)(?=<div class="bilaga">|$)', tail[k:], re.S):
            h3 = re.search(r'<h3[^>]*>(.*?)</h3>', bm.group(1), re.S)
            annexes.append({'heading': P._text(h3.group(1)) if h3 else 'Bilaga', 'lines': lines_of(bm.group(1))})
    ams = []
    for m in re.finditer(r'<div class="andringinfo">\s*<h3 id="an_\d+">([^<]*)</h3>(.*?)(?=<div class="andringinfo">|$)',
                         page[j:k + j if k >= 0 else page.index('</main')], re.S):
        ik = re.search(r'<div class="ikrafttradelse(?:digi)?">(.*?)</div>', m.group(2), re.S)
        paras = [P._text(x) for x in re.findall(r'<p>(.*?)</p>', ik.group(1), re.S)] if ik else []
        fw = re.search(r'<div class="forarbeteshanvisningar">(.*?)</div>', m.group(2), re.S)
        works = [P._text(x) for x in re.findall(r'<li>(.*?)</li>', fw.group(1), re.S)] if fw else []
        ams.append({'id': m.group(1).strip(), 'commencement': [x for x in paras if x], 'works': works})
    has_img = '<img' in body or '<img' in tail[k:] if k >= 0 else '<img' in body
    return {'title': title, 'sections': secs, 'annexes': annexes, 'ams': ams, 'img': has_img,
            'body_words': body_words(body) + (annex_words(tail[k:]) if k >= 0 else [])}


def body_words(body):
    """Independent of the section parser: the page's law text with tags removed (part and chapter headings included)."""
    body = body[body.index('<div class="kapitelsektion">'):]
    body = re.sub(r'(<h3[^>]*>[^<]*?§§?)\.', r'\1', body)
    body = P.INLINE.sub('', body)
    text = P.clean(html.unescape(re.sub(r'<[^>]+>', ' ', body)))
    return text.split()


def annex_words(tail):
    tail = re.sub(r'<h2[^>]*>.*?</h2>', ' ', tail, count=1, flags=re.S)
    text = P.clean(html.unescape(re.sub(r'<[^>]+>', ' ', P.INLINE.sub('', tail))))
    return text.split()


def ident(a):
    m = re.fullmatch(r'(\d{4})[:/](\d+)', a)
    return (int(m.group(1)), int(m.group(2))) if m else None


def fname(sec, numbered_per_chapter):
    parts = []
    for x in sec['num'].split('-'):
        m = re.fullmatch(r'(\d+)([a-z]*)', x)
        if not m:
            raise ValueError('section number ' + x)
        parts.append(f'{int(m.group(1)):03d}{m.group(2)}')
    base = 'paragraf-' + '-'.join(parts) + '.md'
    if numbered_per_chapter:
        c = re.match(r'(\d+)\s*([a-z]?)\s*kap', sec['chapter'])
        if not c:
            raise ValueError('chapter number in ' + sec['chapter'])
        return f'kap-{int(c.group(1)):02d}{c.group(2)}-' + base
    return base


def render(sec):
    sign = '§§' if '-' in sec['num'] else '§'
    out = [f'# {sec["num"]} {sign} {sec["heading"]}'.rstrip()]
    if sec['part']:
        out.append(f'Avdelning: {sec["part"]}')
    if sec['chapter']:
        out.append(f'Kapitel: {sec["chapter"]}')
    if sec['sub']:
        out.append(f'Rubrik: {sec["sub"]}')
    for mom in sec['moments']:
        out.append('')
        out += [P.clean(x) for x in mom]
    return '\n'.join(out) + '\n'


def files_of(d):
    secs = d['sections']
    keys = [s['num'] for s in secs]
    per_ch = len(set(keys)) != len(keys)
    files = {'rubrik.md': d['title'] + '\n'}
    for s in secs:
        if len(s['moments']) == 1 and len(s['moments'][0]) == 1 and re.fullmatch(r'Upphävda?\.?', s['moments'][0][0]):
            continue
        f = fname(s, per_ch)
        if f in files:
            raise ValueError('duplicate file ' + f)
        files[f] = render(s)
    for n, a in enumerate(d['annexes'], 1):
        files[f'bilaga-{n:02d}.md'] = '\n'.join([f'# {a["heading"]}', ''] + a['lines']) + '\n'
    return files


def parsed_words(d):
    w = []
    for s in d['sections']:
        for t in s['pre']:
            w += t.split()
        w += (s['h3num'] + (' §§' if '-' in s['num'] else ' §')).split() + s['heading'].split()
        for m in s['moments']:
            for line in m:
                w += line.replace(' | ', ' ').split()
    for a in d['annexes']:
        w += a['heading'].split()
        for line in a['lines']:
            w += line.replace(' | ', ' ').split()
    return [x for x in w if x != '|']


def norm_num(words):
    """'22 a §' in a heading is '22a §' in the files."""
    out, i = [], 0
    while i < len(words):
        if i + 2 < len(words) and re.fullmatch(r'\d+', words[i]) and re.fullmatch(r'[a-z]', words[i + 1]) and words[i + 2] == '§':
            out.append(words[i] + words[i + 1]); i += 2
            continue
        if words[i] != '|':
            out.append(words[i])
        i += 1
    return out


def dating(d, today):
    """(in_force_day, newest_id, commencement_lines, basis) or raises Hold."""
    ams = [a for a in d['ams'] if ident(a['id'])]
    if not ams:
        raise Hold('Ålex lists no act number')
    newest = max(ams, key=lambda a: ident(a['id']))
    lines = [x for x in newest['commencement'] if 'träder i kraft' in x]
    days = sorted({P.iso(x) for x in lines} - {None})
    basis = f'the commencement provision Ålex prints for ÅFS {newest["id"].replace(":", "/")}'
    if not days and ':' in newest['id']:
        text = [line for s in d['sections'] for m in s['moments'] for line in m]
        lines = [x for x in text if re.search(r'träder i kraft', x)]
        days = sorted({P.iso(x) for x in lines} - {None})
        basis = 'the act\'s own commencement provision in the Ålex text (the act has no amending acts in Ålex)'
    if not days:
        raise Hold(f'no in-force day stated for ÅFS {newest["id"]} in Ålex' + (f': {lines[0][:120]}' if lines else ''))
    if days[-1] > today:
        raise Hold(f'future commencement {days[-1]} (ÅFS {newest["id"]})')
    if len(days) > 1:
        basis += f'; several days named ({", ".join(days)}), the latest used, when all of the text shown was in force'
    return days[-1], newest, lines, basis


class Hold(Exception):
    pass


def message(d, href, folder, kind, day, newest, lines, basis, nwords, obsolete):
    y, n = ident(newest['id'])
    t = d['title']
    first = f'{t}' if len(t) <= 90 else t[:87].rstrip() + '...'
    out = [first, '',
           'Gällande lydelse enligt Ålex (konsoliderad text), som den ser ut efter den senaste författning den visar.',
           'The consolidated text as Ålex shows it, after the newest act it lists; earlier versions are not replayed here.',
           '']
    if obsolete:
        out += ['Ålex lists this text under Föråldrad lagstiftning (obsolete): this is its last text; the day it ceased '
                'to apply is not stated on the page.', '']
    out += [f'Evidence: current consolidated text from Ålex; the files equal the page\'s law text word for word, in order '
            f'({nwords} words)',
            f'Kind: {kind}',
            f'In-force: {day}',
            f'In-force-basis: in-force day of ÅFS {y}/{n}, the newest act Ålex lists for this text, from {basis}']
    out += [f'Commencement: {x}' for x in lines]
    amended = [a['id'] for a in d['ams'] if '/' in a['id']]
    if amended:
        out.append('Amended-by: ' + ', '.join(f'ÅFS {a}' for a in amended))
    for a in d['ams']:
        out += [f'Preparatory-works: {w}' for w in a['works']] if a is newest else []
    out += [f'Consolidated: {SITE}{href}']
    return '\n'.join(out) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pages', required=True)
    ap.add_argument('--catalog', required=True)
    ap.add_argument('--repo', required=True)
    ap.add_argument('--today', default='2026-11-26')
    ap.add_argument('--plan-only', action='store_true')
    ap.add_argument('--verify', action='store_true', help='check the files and trailers at HEAD against the pages')
    ap.add_argument('--only-current', action='store_true', help='leave out texts Ålex lists as obsolete')
    ap.add_argument('--out', default=str(HERE / 'current-plan.json'))
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    cat = json.load(open(a.catalog, encoding='utf-8'))
    pages = Path(a.pages)
    plan, held = [], []
    seen = {}
    for href, ctitle in cat.items():
        m = re.search(r'\((\d{4}):(\d+)\)', ctitle)
        aid = f'{m.group(1)}:{m.group(2)}'
        obsolete = 'foraldrad' in href
        rec = {'href': href, 'id': aid, 'title': ctitle, 'obsolete': obsolete}
        if aid in SKIP:
            held.append({**rec, 'reason': SKIP[aid]}); continue
        if aid in seen:
            held.append({**rec, 'reason': f'the same act is also listed at {seen[aid]}'}); continue
        seen[aid] = href
        if obsolete and a.only_current:
            held.append({**rec, 'reason': 'obsolete (Föråldrad lagstiftning): left for a later pass'}); continue
        f = pages / (href.strip('/').replace('/', '__') + '.html')
        try:
            page = f.read_text(encoding='utf-8')
            d = parse_page(page)
            if d['img']:
                raise Hold('the text holds a statutory image the files cannot carry')
            if not d['sections'] and not d['annexes']:
                raise Hold('no sections found on the page')
            pw, bw = norm_num(parsed_words(d)), norm_num(d['body_words'])
            if pw != bw:
                import difflib
                sm = difflib.SequenceMatcher(None, pw, bw, autojunk=False)
                diff = [(op, ' '.join(pw[i1:i2])[:60], ' '.join(bw[j1:j2])[:60]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != 'equal']
                raise Hold(f'word check failed: {diff[:3]}')
            day, newest, lines, basis = dating(d, a.today)
            files = files_of(d)
        except Hold as e:
            held.append({**rec, 'reason': str(e)}); continue
        except Exception as e:
            held.append({**rec, 'reason': 'parse: ' + repr(e)[:200]}); continue
        folder_kind, kind = kind_of(d['title'])
        y, n = aid.split(':')
        folder = ('foraldrad/' if obsolete else '') + f'{folder_kind}-{y}-{n}'
        plan.append({**rec, 'folder': folder, 'kind': kind, 'day': day, 'newest': newest['id'], 'files': files,
                     'msg': message(d, href, folder, kind, day, newest, lines, basis, len(pw), obsolete)})
    plan.sort(key=lambda p: (p['day'], ident(p['id'])))
    folders = [p['folder'] for p in plan]
    assert len(set(folders)) == len(folders)
    summary = {'planned': len(plan), 'held': held}
    Path(a.out).write_text(json.dumps({'summary': summary, 'plan': [{k: v for k, v in p.items() if k != 'files'} for p in plan]},
                                      ensure_ascii=False, indent=1), encoding='utf-8')
    print('planned', len(plan), 'held', len(held))
    if a.plan_only:
        return
    repo = Path(a.repo)
    if a.verify:
        bad = []
        for p in plan:
            names = [x for x in B.git(repo, 'ls-tree', '-r', '--name-only', 'HEAD', p['folder'] + '/').split('\n') if x]
            if not names:
                continue
            have = {n[len(p['folder']) + 1:]: B.git(repo, 'show', f'HEAD:{n}') for n in names}
            if have != p['files']:
                bad.append(p['folder'])
            log = B.git(repo, 'log', '-1', '--format=%an%x09%(trailers:key=In-force,valueonly,separator=)', 'HEAD', '--',
                        p['folder']).strip().split('\t')
            y, n = ident(p['newest'])
            if log != [f'ÅFS {y}/{n}', p['day']]:
                bad.append(p['folder'] + ' author/in-force ' + repr(log))
        print('verified', len(plan), 'acts against their Ålex pages;', len(bad), 'problems', bad[:10])
        raise SystemExit(1 if bad else 0)
    for i, p in enumerate(plan):
        if (repo / p['folder']).exists():
            continue
        B.sync(repo, p['folder'], p['files'])
        y, n = ident(p['newest'])
        B.git(repo, 'add', '--', p['folder'])
        ts = B.stamp(p['day'], i % 50)
        env = {'GIT_AUTHOR_NAME': f'ÅFS {y}/{n}', 'GIT_AUTHOR_EMAIL': f'afs-{y}-{n}@regeringen.ax.invalid',
               'GIT_AUTHOR_DATE': ts, 'GIT_COMMITTER_NAME': 'Lexifina', 'GIT_COMMITTER_EMAIL': B.EMAIL,
               'GIT_COMMITTER_DATE': ts}
        B.git(repo, 'commit', '-q', '-F', '-', '--', p['folder'], env=env, inp=p['msg'])
    print('committed up to', B.git(repo, 'rev-parse', 'HEAD').strip())


if __name__ == '__main__':
    main()
