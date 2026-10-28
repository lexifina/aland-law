# Åland law, change by change

Landskapslag (2015:68) om hemvårdsstöd (the Home Care Allowance Act of the Åland Islands) as a git repository. Each amending act is one commit,
credited to that act and dated the day it took effect, at noon in Mariehamn. Text is Swedish.

**The intermediate versions are replayed. Only the end state is checked against an official consolidation.** Ålex serves only the CURRENT consolidation of an act. The intermediate versions in this repository are therefore REPLAYED: the original act is taken from its Statute Book (ÅFS) PDF and each amending act is applied, in in-force order, by section, moment (subsection), point and heading replacement, moment and section insertion, as the act's own enacting clause states. Only the end state is checked against an official consolidation (Ålex); the earlier versions are not independently confirmed.

## The questions, as git commands

| Question | Command |
| --- | --- |
| What did 1 § say on 1 June 2021? | `python tools/alex.py 2021-06-01 hemvardsstod 1` |
| The whole act as it stood on 1 January 2019 | `python tools/alex.py 2019-01-01 hemvardsstod` |
| Which act wrote each line of 13 §? | `git blame hemvardsstod/paragraf-013.md` |
| Every change to 13 §, with the act and the day | `git log --follow hemvardsstod/paragraf-013.md` |
| Everything one act changed | `git show --stat hemvardsstod/2022-56` |
| The amending acts with all their dates | [`amendments.csv`](amendments.csv) |
| Commits carrying the replay evidence line | `git log --grep="Evidence: replay"` |
| Acts that amended 7 § | `git log --format="%an %ad" --date=short -- hemvardsstod/paragraf-007.md` |
| Changes with a transitional or retroactive rule | `git log --grep="^Applies:"` |
| All tags, one per act | `git tag --list "hemvardsstod/*"` |

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
| ÅFS 2017/126 | 2018-01-01 | 25 |
| ÅFS 2020/63 | 2020-09-01 | 22a |
| ÅFS 2020/54 | 2021-01-01 | 1 |
| ÅFS 2021/104 | 2022-01-01 | 27 |
| ÅFS 2022/56 | 2022-08-01 | 1, 7, 8, 9, 11, 13, 14, 15, 28 |
| ÅFS 2023/29 | 2023-05-01 | 7, 13 |
| ÅFS 2026/31 | 2026-05-01 | 21 |

## How it is checked

`tools/build.py` stops unless the replayed end state equals the Ålex consolidation (updated to ÅFS 2026/31) for all
30 sections, after this normalisation: (1) whitespace: no-break and em spaces and tabs are read as spaces, runs of whitespace as one space, soft hyphens (U+00AD) are dropped and a word broken at a line end is joined; (2) Ålex: inline markup (links, emphasis) joins without a space, the amendment labels such as "(2022/56)" are dropped, and the editorial notes (div "anmarkning", e.g. under 21 §) are not law text; (3) ÅFS PDF: an unmapped glyph (U+FFFD) before a line-end hyphen is the consonant doubled at a Swedish triple-consonant break ("til-lämpning"), so the word is joined as written unbroken ("tillämpning"); the publisher's headers, footers, signatures and footnotes are dropped by content.
`tools/check_repo.py` then reads every version back from git and compares the final one with Ålex (file by file and
word for word), the first with the original act, and each amendment's sections with the amending act's own text.
`tools/test_repo.py` checks that the commands above work. See [`REPRODUCE.md`](REPRODUCE.md).
- check_repo.py: final version vs Ålex (updated to ÅFS 2026/31): 30 sections, 0 mismatches, word check equal (2232 words); first version vs original act: equal; 7 amending acts checked against their own text and in-force days; 0 problems
- test_repo.py: 6/6 passed

## Files

`hemvardsstod/paragraf-NNN.md` is one section (paragraf); the `#` line is its number and heading, `Kapitel:` its chapter, and
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
