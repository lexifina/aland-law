# Reproduce

Data retrieved 2026-10-28. Everything below is deterministic: the same data gives the same hashes.

## Steps

1. `python -X utf8 tools/build.py --repo <dir>` (needs network once and PyMuPDF; fills `tools/cache`, then `--offline`
   reproduces). Sources, each fetched once with a User-Agent and gzip, one request at a time with a pause, cached
   including 404s (older PDFs use `nr`, newer `Nr` in the file name):
   - `https://www.regeringen.ax/alandsk-lagstiftning/alex/201568` (the consolidation, its list of amending acts, their commencement provisions and preparatory works)
   - `https://www.regeringen.ax/sites/default/files/attachments/law/afs2015_nr68.pdf` (the original act)
   - `https://www.regeringen.ax/sites/default/files/attachments/law/afs2017_nr126.pdf`
   - `https://www.regeringen.ax/sites/default/files/attachments/law/afs2020_nr63.pdf`
   - `https://www.regeringen.ax/sites/default/files/attachments/law/afs2020_nr54.pdf`
   - `https://www.regeringen.ax/sites/default/files/attachments/law/afs2021_nr104.pdf`
   - `https://www.regeringen.ax/sites/default/files/attachments/law/afs2022_nr56.pdf`
   - `https://www.regeringen.ax/sites/default/files/attachments/law/afs2023_Nr29.pdf`
   - `https://www.regeringen.ax/sites/default/files/attachments/law/afs2026_Nr31.pdf`
   regeringen.ax's robots.txt sets no crawl delay; lagtinget.ax (preparatory works, not fetched) asks for 10 s.
2. The builder replays the acts (`parse.py`), compares the result with Ålex (the gate), then commits.
3. `python -X utf8 tools/check_repo.py`, `python -X utf8 tools/test_repo.py`, and `python -X utf8 tools/build.py --offline --verify-rebuild --repo <dir>` (a second build in a temporary folder must give the same `main` hash).

## Method

Ålex serves only the CURRENT consolidation of an act. The intermediate versions in this repository are therefore REPLAYED: the original act is taken from its Statute Book (ÅFS) PDF and each amending act is applied, in in-force order, by section, moment (subsection), point and heading replacement, moment and section insertion, as the act's own enacting clause states. Only the end state is checked against an official consolidation (Ålex); the earlier versions are not independently confirmed.

PDF text is read with PyMuPDF in reading order (two columns per page, merged by baseline); a moment starts at an indented
line; "- - -" lines are omission marks for the units an amending act leaves alone. The enacting clause ("ändras ...,
fogas ... som följer:") lists every unit the act changes; provenance notes ("sådant det lyder i landskapslagen 2020/54")
are dropped. If the grammar does not recognise a clause, or the body does not match what the clause names, the build
stops. The declared normalisation (applied to both sides): (1) whitespace: no-break and em spaces and tabs are read as spaces, runs of whitespace as one space, soft hyphens (U+00AD) are dropped and a word broken at a line end is joined; (2) Ålex: inline markup (links, emphasis) joins without a space, the amendment labels such as "(2022/56)" are dropped, and the editorial notes (div "anmarkning", e.g. under 21 §) are not law text; (3) ÅFS PDF: an unmapped glyph (U+FFFD) before a line-end hyphen is the consonant doubled at a Swedish triple-consonant break ("til-lämpning"), so the word is joined as written unbroken ("tillämpning"); the publisher's headers, footers, signatures and footnotes are dropped by content.

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

- check_repo.py: final version vs Ålex (updated to ÅFS 2026/31): 30 sections, 0 mismatches, word check equal (2232 words); first version vs original act: equal; 7 amending acts checked against their own text and in-force days; 0 problems
- test_repo.py: 6/6 passed
