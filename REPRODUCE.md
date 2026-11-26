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

## The current texts (tools/current.py)

Every Ålex text other than hemvardsstod/, lagtingsordning/ and sjalvstyrelselag/ is its current consolidation, retrieved 2026-11-26. The catalogue is regeringen.ax "Sök i lagstiftningen" filtered to Ålex (`/alandsk-lagstiftning/sok?f[0]=law_type:law_updated`, 690 entries: 522 under `/alex/`, 168 under `/foraldrad-lagstiftning/`), each page fetched once, two requests in flight, no 429 or 5xx seen.

`python -X utf8 tools/current.py --pages <dir> --catalog catalog.json --repo <dir>` parses each page into one file per section, one per annex and `rubrik.md`, and checks that the files hold the page's law text word for word, in order (amendment labels such as "(2022/56)", marked up as links to the list of amending acts, and editorial notes are not law text; a repealed section ("Upphävd.") is not written). `--verify` reads the files and trailers back from HEAD.

Folders: `<kind>-<year>-<number>/`, kind `landskapslag`, `landskapsforordning`, `rp-forordning` (Republikens presidents förordning), `forordning`, `lag`, `beslut`, `arbetsordning`; texts Ålex lists as obsolete go under `foraldrad/`. Files: `paragraf-NNN.md`; where sections restart in each chapter, `kap-NN-paragraf-NNN.md`; a combined heading such as "9 - 10 §§" gives `paragraf-009-010.md`; annexes `bilaga-NN.md`. Each file has the heading line and `Avdelning:`, `Kapitel:` and `Rubrik:` (the intermediate heading) lines for its context.

Dating: one commit per act, noon Europe/Mariehamn on the in-force day of the newest act in Ålex's list for the text, from the commencement provision Ålex prints for it or, for an act never amended, the act's own "träder i kraft den ..." provision; several days named: the latest. Author `ÅFS <year>/<number>` of that act; trailers `In-force`, `In-force-basis`, `Commencement`, `Amended-by`, `Preparatory-works`, `Consolidated`. Held, not committed: no in-force day stated in Ålex, a day after 2026-11-26, a statutory image, or a word-check failure.

Result: 625 acts committed (467 in force, 158 obsolete); 65 catalogue entries held:

- 2026:24 (in force): the text holds a statutory image the files cannot carry
- 2026:22 (in force): future commencement 2027-01-01 (ÅFS 2026:22)
- 2025:66 (in force): no in-force day stated for ÅFS 2025:66 in Ålex: Åtgärder som denna förordning förutsätter får vidtas innan den träder i kraft.
- 2025:10 (in force): the text holds a statutory image the files cannot carry
- 2024:32 (in force): the text holds a statutory image the files cannot carry
- 2023:108 (in force): the text holds a statutory image the files cannot carry
- 2021:166 (in force): future commencement 2049-07-17 (ÅFS 2021:166)
- 2020:32 (in force): parse: ValueError('duplicate file kap-01-paragraf-001.md')
- 2018:91 (in force): no in-force day stated for ÅFS 2018:91 in Ålex: Ändringar i den rikslagstiftning som anges i 1 mom. ska tillämpas i landskapet från det att de träder i kraft i 
- 2018:81 (in force): the same act is also listed at /alandsk-lagstiftning/foraldrad-lagstiftning/201881
- 2017:76 (obsolete): the same act is also listed at /alandsk-lagstiftning/alex/201776
- 2016:10 (obsolete): no in-force day stated for ÅFS 2017/100 in Ålex
- 2015:68 (in force): already held, replayed by build.py (hemvardsstod/)
- 2011:97 (in force): Lagtingsordning: added by the constitution lane under its own folder
- 2010:93 (in force): the text holds a statutory image the files cannot carry
- 2008:144 (in force): no in-force day stated for ÅFS 2008:144 in Ålex: Åtgärder som verkställigheten av lagen förutsätter får vidtas innan lagen träder i kraft.
- 2008:130 (in force): the text holds a statutory image the files cannot carry
- 2007:57 (in force): the text holds a statutory image the files cannot carry
- 2006:11 (in force): no in-force day stated for ÅFS 2006:11 in Ålex
- 2005:51 (obsolete): no in-force day stated for ÅFS 2005:51 in Ålex: Ändringar i riksförordningen skall tillämpas i landskapet från det att de träder i kraft i riket.
- 2005:35 (obsolete): the text holds a statutory image the files cannot carry
- 2004:15 (in force): no in-force day stated for ÅFS 2004:15 in Ålex
- 2003:60 (in force): no in-force day stated for ÅFS 2003:60 in Ålex: Ändringar i ovannämnda riksförfattningar skall tillämpas i landskapet från den dag de träder i kraft i riket.
- 2003:58 (obsolete): no in-force day stated for ÅFS 2007/119 in Ålex
- 2001:38 (in force): word check failed: [('insert', '', '1. Statsrådets beslut om riktvärden för luftkvalitet och mål'), ('insert', '', '4. Statsrådets beslut om begränsning av utsl
- 1998:113 (obsolete): word check failed: [('insert', '', 'utter, Lutra lutra vikare, Phoca hispida botnica'), ('insert', '', 'backsvala, Riparia riparia bergand, Aythya marila berguv
- 1998:101 (obsolete): no in-force day stated for ÅFS 1998:101 in Ålex
- 1998:86 (in force): word check failed: [('insert', '', '- Stränder. - Bäckar och källor. - Alkärr samt ormbunks- och'), ('insert', '', '- Barrskogsbevuxna öar omfattande mindre än 
- 1998:83 (in force): no in-force day stated for ÅFS 2003/59 in Ålex
- 1997:60 (in force): word check failed: [('replace', '§§', '§')]
- 1997:42 (in force): no in-force day stated for ÅFS 2002/38 in Ålex
- 1995:36 (obsolete): the text holds a statutory image the files cannot carry
- 1995:7 (in force): Ålex lists no act number
- 1994:72 (in force): Ålex lists no act number
- 1993:112 (in force): Ålex lists no act number
- 1993:19 (in force): word check failed: [('replace', '31a §', '31a§')]
- 1992:41 (in force): the text holds a statutory image the files cannot carry
- 1991:71 (in force): Självstyrelselag: added by the constitution lane under its own folder
- 1989:31 (in force): no in-force day stated for ÅFS 2002/24 in Ålex
- 1987:44 (in force): no in-force day stated for ÅFS 2002/48 in Ålex
- 1984:45 (in force): no in-force day stated for ÅFS 1984:45 in Ålex
- 1984:25 (in force): no in-force day stated for ÅFS 2010/53 in Ålex
- 1980:44 (in force): no in-force day stated for ÅFS 1981/10 in Ålex
- 1979:72 (in force): no in-force day stated for ÅFS 1983/16 in Ålex
- 1979:6 (in force): the text holds a statutory image the files cannot carry
- 1977:77 (in force): no in-force day stated for ÅFS 1979/54 in Ålex
- 1977:68 (obsolete): no in-force day stated for ÅFS 2021:80 in Ålex
- 1977:10 (in force): no in-force day stated for ÅFS 1987/18 in Ålex
- 1976:67 (in force): no in-force day stated for ÅFS 1976:43 in Ålex
- 1976:43 (in force): parse: AttributeError("'NoneType' object has no attribute 'group'")
- 1976:22 (in force): parse: AttributeError("'NoneType' object has no attribute 'group'")
- 1975:64 (in force): no in-force day stated for ÅFS 1975:64 in Ålex
- 1974:83 (in force): no in-force day stated for ÅFS 2002/45 in Ålex
- 1973:47 (in force): no in-force day stated for ÅFS 1973:47 in Ålex
- 1972:50 (in force): no in-force day stated for ÅFS 1972:50 in Ålex
- 1971:51 (in force): no in-force day stated for ÅFS 1997/6 in Ålex
- 1969:18 (in force): no in-force day stated for ÅFS 1975/39 in Ålex
- 1966:13 (in force): no in-force day stated for ÅFS 1966:13 in Ålex
- 1953:16 (in force): no in-force day stated for ÅFS 1955/17 in Ålex
- 1952:11 (in force): no in-force day stated for ÅFS 1952:11 in Ålex
- 1951:19 (in force): no in-force day stated for ÅFS 1951:19 in Ålex
- 1950:25 (in force): no in-force day stated for ÅFS 1950:25 in Ålex
- 1947:6 (in force): no in-force day stated for ÅFS 2021:80 in Ålex
- 1942:10 (obsolete): no in-force day stated for ÅFS 1942:10 in Ålex
- 1936:1 (in force): no in-force day stated for ÅFS 1936:1 in Ålex
