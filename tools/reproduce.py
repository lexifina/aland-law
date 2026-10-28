"""Writes the repository's documentation: README.md, LICENSE, REPRODUCE.md, corpus.json, amendments.csv, and copies the
tools. Called by build.py; deterministic (no clock, no network). verification.json (from check_repo.py / test_repo.py)
is read when it exists."""
import json
import shutil
from pathlib import Path

NOTE_REPLAY = ('Ålex serves only the CURRENT consolidation of an act. The intermediate versions in this repository are '
               'therefore REPLAYED: the original act is taken from its Statute Book (ÅFS) PDF and each amending act is '
               'applied, in in-force order, by section, moment (subsection), point and heading replacement, moment and '
               'section insertion, as the act\'s own enacting clause states. Only the end state is checked against an '
               'official consolidation (Ålex); the earlier versions are not independently confirmed.')


def write_docs(repo: Path, datas, report, today, here: Path):
    import build as B
    d = datas[0]
    cfg = d['cfg']
    ams = [a for a in d['ams'] if a['in_force'] <= today]
    changed = d['changed'][:len(ams)]
    ver = {}
    vp = here / 'verification.json'
    if vp.exists():
        ver = json.loads(vp.read_text(encoding='utf-8'))
    first = d['base_inforce']
    last = max([first] + [a['in_force'] for a in ams])
    ident = f'{cfg["year"]}:{cfg["no"]}'
    upd = report[cfg['dir']]['consolidation_updated_to']
    corpus = {
        'corpus': 'ax/national/acts',
        'name': f'Åland law: {cfg["name"]}',
        'label': 'Åland',
        'language': 'sv',
        'acts': [ident],
        'history_from': first,
        'record_to': last,
        'record_note': (f'{ident} from its original text (in force {first}) with the {len(ams)} amending acts replayed '
                        f'to the Ålex consolidation (updated to ÅFS {upd}); data retrieved {today}.'),
        'in_force_trailer': 'In-force',
        'built': today,
        'dates': {'commit': 'in-force', 'other_trailers': ['Enacted'],
                  'time': '12:00 Europe/Mariehamn (UTC+2, UTC+3 in summer time)'},
        'scope': {
            'trailer': 'Applies',
            'when_absent': 'the amending act prints no transitional or retroactive rule in its commencement provision; '
                           'the absence is not a statement that the change reaches every case',
            'default_reach': {
                'rule': 'no genuine retroactivity (Constitution of Finland 8 §: nullum crimen; legislative practice '
                        'otherwise), which binds Åland legislation as well',
                'meaning': 'an act applies from the day it takes effect unless its own commencement provision says '
                           'otherwise (for instance ÅFS 2023/29, which lets the sibling allowance be granted from '
                           '1 August 2022); those provisions are copied verbatim into Applies: trailers',
                'authority': 'Suomen perustuslaki 731/1999, 8 §; Självstyrelselag (1991:71) för Åland; each amending '
                             'act\'s commencement provision',
                'decided_here': False}},
        'replayed': True,
        'tool': 'tools/alex.py',
    }
    (repo / 'corpus.json').write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    rows = ['act,title,enacted,in_force,sections_changed,commencement,preparatory_works']
    for a, ch in zip(ams, changed):
        rows.append(','.join('"' + str(x).replace('"', '""') + '"' for x in [
            f'ÅFS {a["id"]}', a['title'], a['enacted'] or '', a['in_force'], ' '.join(ch), ' '.join(a['commencement']),
            '; '.join(a['works'])]))
    (repo / 'amendments.csv').write_text('\n'.join(rows) + '\n', encoding='utf-8', newline='\n')

    (repo / 'LICENSE').write_text(
        'Source of the text: Ålands landskapsregering (the Government of Åland): the Statute Book, Ålands\n'
        'författningssamling (ÅFS), as PDFs, and the consolidated legislation database Ålex, both at\n'
        'https://www.regeringen.ax/alandsk-lagstiftning .\n\n'
        'No licence or terms of use for the texts were found on regeringen.ax; Ålex carries a disclaimer that its\n'
        'consolidated texts are for information and only the texts published in ÅFS are authoritative. Statutes are\n'
        'generally outside copyright in Finland (Upphovsrättslagen / Tekijänoikeuslaki 404/1961, 9 §), which applies\n'
        'on Åland, but reuse has not been separately reviewed: this repository stays PRIVATE.\n\n'
        'Attribution for the legal texts: "Text from Ålands författningssamling and Ålex, Ålands landskapsregering,\n'
        'https://www.regeringen.ax." The texts of the replayed intermediate versions are derived from that data by the\n'
        'method in REPRODUCE.md; they are not published by Ålands landskapsregering.\n\n'
        'The history (commits and commit messages), the tables and the tools are dedicated to the public domain under\n'
        'CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/legalcode\n',
        encoding='utf-8', newline='\n')

    ok_text = ''
    if ver:
        c = ver.get('check', {})
        s = ver.get('smoke', {})
        ok_text = (f'- check_repo.py: {c.get("summary", "not recorded")}\n'
                   f'- test_repo.py: {s.get("passed", "?")}/{s.get("total", "?")} passed\n')
    table = '\n'.join(f'| ÅFS {a["id"]} | {a["in_force"]} | {", ".join(ch)} |' for a, ch in zip(ams, changed))
    folder = cfg['dir']
    (repo / 'README.md').write_text(f'''# Åland law, change by change

{cfg["name"]} (the Home Care Allowance Act of the Åland Islands) as a git repository. Each amending act is one commit,
credited to that act and dated the day it took effect, at noon in Mariehamn. Text is Swedish.

**The intermediate versions are replayed. Only the end state is checked against an official consolidation.** {NOTE_REPLAY}

## The questions, as git commands

| Question | Command |
| --- | --- |
| What did 1 § say on 1 June 2021? | `python tools/alex.py 2021-06-01 {folder} 1` |
| The whole act as it stood on 1 January 2019 | `python tools/alex.py 2019-01-01 {folder}` |
| Which act wrote each line of 13 §? | `git blame {folder}/paragraf-013.md` |
| Every change to 13 §, with the act and the day | `git log --follow {folder}/paragraf-013.md` |
| Everything one act changed | `git show --stat {folder}/2022-56` |
| The amending acts with all their dates | [`amendments.csv`](amendments.csv) |
| Commits carrying the replay evidence line | `git log --grep="Evidence: replay"` |
| Acts that amended 7 § | `git log --format="%an %ad" --date=short -- {folder}/paragraf-007.md` |
| Changes with a transitional or retroactive rule | `git log --grep="^Applies:"` |
| All tags, one per act | `git tag --list "{folder}/*"` |

## The dates, and which one we use

An Åland act has a day it was signed (`Enacted:`, "Utfärdad i Mariehamn den ...") and a day it takes effect
(`In-force:`). **Commits are dated the day the change took effect**, at noon in Mariehamn (EET, or EEST in summer time).
Each in-force day is read twice and must agree: from Ålex's list of commencement provisions and from the amending act's
own text in the Statute Book. No act here is staged per section. Transitional and retroactive rules in a commencement
provision are copied verbatim into `Applies:` trailers; the preparatory works Ålex lists go into `Preparatory-works:`.

## What "author" means

The author of a commit is the act that made the change (`ÅFS 2022/56`, address `afs-2022-56@regeringen.ax.invalid`), so
`git blame` names the act. The committer is always `Lexifina`.

## Amending acts

| Act | In force | Sections |
| --- | --- | --- |
{table}

## How it is checked

`tools/build.py` stops unless the replayed end state equals the Ålex consolidation (updated to ÅFS {upd}) for all
{report[folder]["sections"]} sections, after this normalisation: {B.NORMALISATION}
`tools/check_repo.py` then reads every version back from git and compares the final one with Ålex (file by file and
word for word), the first with the original act, and each amendment's sections with the amending act's own text.
`tools/test_repo.py` checks that the commands above work. See [`REPRODUCE.md`](REPRODUCE.md).
{ok_text}
## Files

`{folder}/paragraf-NNN.md` is one section (paragraf); the `#` line is its number and heading, `Kapitel:` its chapter, and
each moment (subsection) is a block separated by a blank line, each line one paragraph or numbered point. `rubrik.md` is
the title and the enacting words. A repealed section is removed.

## What it does not show

- Versions Ålex does not publish: only the current consolidation exists; the rest is replayed.
- Landskapslag (2017:120) om landskapsandelar till kommunerna was not built: three of its amending acts are temporary
  (2020/50, 2021/136, 2022/67, with sunset days) and Ålex gives no commencement for 2018/102.
- The Autonomy Act (Självstyrelselag 1991:71 för Åland) is a Finnish act, published by Finlex, not in ÅFS.

## Licence

See [`LICENSE`](LICENSE): no terms of use were found; the repository stays private. Tools, history and tables: CC0.

## Source

Ålands landskapsregering, https://www.regeringen.ax/alandsk-lagstiftning : Ålex (consolidated texts, HTML) and Ålands
författningssamling (PDF).
''', encoding='utf-8', newline='\n')

    urls = '\n'.join(f'   - `{a["url"]}`' for a in d['ams'])
    (repo / 'REPRODUCE.md').write_text(f'''# Reproduce

Data retrieved {today}. Everything below is deterministic: the same data gives the same hashes.

## Steps

1. `python -X utf8 tools/build.py --repo <dir>` (needs network once and PyMuPDF; fills `tools/cache`, then `--offline`
   reproduces). Sources, each fetched once with a User-Agent and gzip, one request at a time with a pause, cached
   including 404s (older PDFs use `nr`, newer `Nr` in the file name):
   - `{d["alex_url"]}` (the consolidation, its list of amending acts, their commencement provisions and preparatory works)
   - `{d["base_url"]}` (the original act)
{urls}
   regeringen.ax's robots.txt sets no crawl delay; lagtinget.ax (preparatory works, not fetched) asks for 10 s.
2. The builder replays the acts (`parse.py`), compares the result with Ålex (the gate), then commits.
3. `python -X utf8 tools/check_repo.py`, `python -X utf8 tools/test_repo.py`, and `python -X utf8 tools/build.py --offline --verify-rebuild --repo <dir>` (a second build in a temporary folder must give the same `main` hash).

## Method

{NOTE_REPLAY}

PDF text is read with PyMuPDF in reading order (two columns per page, merged by baseline); a moment starts at an indented
line; "- - -" lines are omission marks for the units an amending act leaves alone. The enacting clause ("ändras ...,
fogas ... som följer:") lists every unit the act changes; provenance notes ("sådant det lyder i landskapslagen 2020/54")
are dropped. If the grammar does not recognise a clause, or the body does not match what the clause names, the build
stops. The declared normalisation (applied to both sides): {B.NORMALISATION}

## Dates and causes

Commit date: noon Mariehamn on the in-force day (EET +0200; EEST +0300 from the last Sunday of March to the last Sunday of
October, `start <= day < end`). Several commits carry seconds 00 to 07 only to keep their order. In-force days come from
the commencement provision of each amending act in the Statute Book and must equal the one Ålex lists. Nothing is
attributed by date alone and no commit is by the publisher.

## Decisions by hand and AI

No model wrote legal text or ran at build time. The code was written with Claude (Claude Agent SDK; models claude-sonnet
and claude-opus-5-5) and is plain Python. Hand decisions: the declared normalisation; the choice of act; leaving out the
act on landskapsandelar (temporary amendments).

## Verification record

{ok_text or '(not yet recorded)'}''', encoding='utf-8', newline='\n')

    tools = repo / 'tools'
    tools.mkdir(exist_ok=True)
    for n in ('build.py', 'parse.py', 'reproduce.py', 'check_repo.py', 'test_repo.py', 'alex.py'):
        src = here / ('repo/tools/' + n if n == 'alex.py' else n)
        shutil.copyfile(src, tools / n)
