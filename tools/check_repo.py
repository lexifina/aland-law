"""Checks the built repository against the official texts (read from the builder's cache, so it is offline).

    python -X utf8 check_repo.py [--repo DIR] [--record]

1. FINAL version (last law commit): every section file equals the file rendered from the Ålex consolidation, byte for
   byte after the declared normalisation; and, independently of the parser, the words of Ålex's law text (the HTML with
   tags removed, block boundaries as spaces) equal the words of the files, in order. 0 mismatches required.
2. FIRST version: every file equals the original act as printed in the Statute Book.
3. EACH amending act: every line the act prints for a section it names appears in that section's file at the act's
   commit; files the act does not name are byte-identical to the previous commit.
4. Author and In-force day of each commit equal the act and the day in its commencement provision (and Ålex's list).
Intermediate versions are replayed; only 1 is a check against an official consolidation. Blobs are read through
`git ls-tree` + `git cat-file --batch`.
"""
import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build as B  # noqa: E402
import parse as P  # noqa: E402


def blobs(repo, commit, folder):
    names = subprocess.run(['git', 'ls-tree', '-r', '--name-only', commit, folder + '/'], cwd=repo, capture_output=True,
                           text=True, encoding='utf-8').stdout.split('\n')
    names = [n for n in names if n]
    p = subprocess.run(['git', 'cat-file', '--batch'], cwd=repo, input=''.join(f'{commit}:{n}\n' for n in names).encode(),
                       capture_output=True)
    out, buf, i = {}, p.stdout, 0
    for n in names:
        j = buf.index(b'\n', i)
        size = int(buf[i:j].split()[2])
        out[n.split('/', 1)[1]] = buf[j + 1:j + 1 + size].decode('utf-8')
        i = j + 1 + size + 1
    return out


def words(s):
    return re.findall(r'\S+', s)


def alex_words(page: str) -> list:
    """The law text of the Ålex page as words, without the parser: chapter headings, amendment labels and editorial
    notes left out, inline tags joined without a space, every other tag a space."""
    body = page[page.index('<div class="kapitel">'):page.index('class="andringinfosektion"')]
    body = body[:body.rindex('<')]
    body = re.sub(r'<div class="anmarkning">.*?</div>', ' ', body, flags=re.S)
    body = re.sub(r'<h2[^>]*>.*?</h2>', ' ', body, flags=re.S)
    body = re.sub(r'(<h3[^>]*>\s*\d+[a-z]? §)\.', r'\1', body)  # the heading's "1 §." is "1 §" in the files
    body = P.INLINE.sub('', body)
    text = P.clean(html.unescape(re.sub(r'<[^>]+>', ' ', body)))
    text = re.sub(r'\(\d{4}/\d+\)', ' ', text)
    return words(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(HERE.parents[2] / 'aland-law'))
    ap.add_argument('--record', action='store_true')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    repo = a.repo
    cfg = B.ACTS[0]
    folder = cfg['dir']
    data = B.load_act(cfg, offline=True)
    states, changed_all = B.replay_all(data)
    log = subprocess.run(['git', 'log', '--reverse', '--format=%H%x09%an%x09%(trailers:key=In-force,valueonly,separator=)',
                          'main'], cwd=repo, capture_output=True, text=True, encoding='utf-8').stdout.splitlines()
    law = [l.split('\t') for l in log if l.split('\t')[1] != 'Lexifina']
    ams = data['ams'][:len(law) - 1]
    problems = []
    if len(law) != 1 + len(ams) or not ams:
        problems.append(f'{len(law)} law commits for {len(data["ams"])} amending acts')
    # 4. authors and dates
    if law[0][1] != f'ÅFS {cfg["year"]}/{cfg["no"]}' or law[0][2].strip() != data['base_inforce']:
        problems.append(f'first commit {law[0][1]} {law[0][2]}')
    for (h, au, day), am in zip(law[1:], ams):
        if au != f'ÅFS {am["id"]}' or day.strip() != am['in_force']:
            problems.append(f'date/author {au} {day}')
    # 2. first version
    first = blobs(repo, law[0][0], folder)
    exp = B.files_of(P.act_from_elements(data['base']['elements'], data['base']['title']), B.intro_of(data))
    first_bad = sorted(n for n in set(first) | set(exp) if first.get(n) != exp.get(n))
    problems += [f'first version {n}' for n in first_bad]
    # 1. final version against Ålex
    final = blobs(repo, law[-1][0], folder)
    want = B.files_of(data['cons'], B.intro_of(data))
    mism = sorted(n for n in set(final) | set(want) if n != 'rubrik.md' and final.get(n) != want.get(n))
    problems += [f'final text {n}' for n in mism]
    fw = []
    for n in sorted(final):
        if n == 'rubrik.md':
            continue
        for l in final[n].split('\n'):
            if l.startswith('Kapitel: '):
                continue
            fw += [w for w in words(l) if w != '#']
    aw = alex_words(data['page'])
    wc = fw == aw
    if not wc:
        k = next((i for i, (x, y) in enumerate(zip(fw, aw)) if x != y), min(len(fw), len(aw)))
        problems.append(f'word check: differs at word {k}: files {fw[k:k + 6]} / Ålex {aw[k:k + 6]}')
    # 3. each amendment
    prev = first
    for (h, au, day), am, chg in zip(law[1:], ams, changed_all):
        cur = blobs(repo, h, folder)
        named = {B.fname(k) for k in chg if re.fullmatch(r'\d+[a-z]?', k)}
        for n in sorted(set(cur) | set(prev)):
            if n not in named and cur.get(n) != prev.get(n):
                problems.append(f'{au}: {n} changed but not named')
        for kind, e in am['parsed']['elements']:
            if kind != 'section':
                continue
            f = cur.get(B.fname(e['num']), '').split('\n')
            for mom in e['seq']:
                for line in mom or []:
                    if P.clean(line) not in f:
                        problems.append(f'{au}: line of {e["num"]} § not in file: {line[:40]}')
        prev = cur
    summary = (f'final version vs Ålex (updated to ÅFS {data["updated"]}): {len(want) - 1} sections, '
               f'{len(mism)} mismatches, word check {"equal" if wc else "DIFFERENT"} ({len(aw)} words); first version vs '
               f'original act: {"equal" if not first_bad else "DIFFERENT"}; {len(ams)} amending acts checked against '
               f'their own text and in-force days; {len(problems)} problems')
    print(summary)
    for p in problems:
        print('PROBLEM', p)
    if a.record:
        vp = HERE / 'verification.json'
        rec = json.loads(vp.read_text(encoding='utf-8')) if vp.exists() else {}
        rec['check'] = {'summary': summary, 'problems': problems}
        vp.write_text(json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
