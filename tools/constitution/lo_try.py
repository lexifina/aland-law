"""Lagtingsordning (2011:97): replay probe and shared helpers for the constitution append (see append.py)."""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build as B  # noqa: E402
import parse as P  # noqa: E402

# ÅFS PDFs before 2015 are not at the afs<year>_Nr<no>.pdf path; the site's ÅFS node (from its law search) redirects
# to the PDF.
NODES = {'2011/97': 26738, '2012/71': 27026, '2013/24': 27152, '2015/66': 2615, '2023/92': 207389, '2023/135': 208787}
_orig_pdf_url = B.pdf_url


def pdf_url(y, n, offline):
    key = f'{y}/{n}'
    if key in NODES:
        u = f'{B.SITE}/node/{NODES[key]}'
        b = B.fetch(u, offline)
        if not b.startswith(b'%PDF'):
            raise SystemExit(f'{u}: not a PDF')
        return u, b
    return _orig_pdf_url(y, n, offline)


B.pdf_url = pdf_url

# Editorial lines printed in the 2011:97 PDF that are not law text: the note that the President ordered 1 § 3 mom.
# to lapse (it is not printed), and the committee report reference.
P.JUNK += [re.compile(r'^Lagens [\d, §moch.]+ förordnades att förfalla\.?$'), re.compile(r'^LM nr \d+/\d{4}-\d{4}$')]

_orig_parse_pdf = P.parse_pdf


def parse_pdf(data):
    """parse.parse_pdf, with the original act's commencement sentence read as 'Denna <lag|lagtingsordning> träder i
    kraft ... <year>.' (it may run past a 'kap.' abbreviation)."""
    lines = P.pdf_lines(data)
    joined = ' '.join(P.clean(l['text']) for l in lines)
    if 'Denna lagtingsordning träder i kraft' in joined:
        real = P.re.search

        def search(pat, s, *a, **k):
            if pat == r'Denna lag träder i kraft[^.]*\.':
                pat = r'Denna lagtingsordning träder i kraft.*?\d{4}\.'
            return real(pat, s, *a, **k)
        P.re = type(sys)('re_shim')
        P.re.__dict__.update(re.__dict__)
        P.re.search = search
        try:
            return _orig_parse_pdf(data)
        finally:
            P.re = re
    return _orig_parse_pdf(data)


P.parse_pdf = parse_pdf

LO = {'dir': 'grundlag/lagtingsordning', 'year': 2011, 'no': 97, 'short': 'Lagtingsordning',
      'name': 'Lagtingsordning (2011:97) för Åland'}

if __name__ == '__main__':
    d = B.load_act(LO, '--offline' in sys.argv)
    print(d['base']['title'], d['base_inforce'], d['base']['issued'], d['base']['commencement'])
    for a in d['ams']:
        print(a['id'], a['in_force'], a['title'], a['ops'])
    st, ch = B.replay_all(d)
    print('gate', B.gate(st[-1], d['cons']))
