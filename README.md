# Åland: författningarnas historik i git

**Svenska** · **[Or read it in English](README.en.md)**

<picture>
<source media="(prefers-color-scheme: dark)" srcset="data/sv/effort-dark.svg">
<img alt="Ålands författningar i detta repositorium: innehåll, ändringar per år för ikraftträdande, fullständighet jämfört med officiella källor och riktighet i det som ingår" src="data/sv/effort-light.svg" width="880">
</picture>

Ålands lagstiftning som en git-historik: en fil per paragraf, en commit per version på den dag den trädde i kraft, och den lag som gjorde varje ändring som commitens författare (author). `git blame` anger lagen bakom varje rad; `git log` visar varje ändring i en paragraf; med ett valt datum får man den text som gällde den dagen.

En del av [lexifina/global-law](https://github.com/lexifina/global-law), en enda git-historik för alla länders rätt: detta är Ålands lagstiftning, som global-law läser under `aland/national/acts/`.

**Vad det innehåller nu:** en lag, Landskapslag (2015:68) om hemvårdsstöd, med sina 30 paragrafer i 8 versioner: den ursprungliga texten, i kraft från den 1 januari 2016, och texten efter var och en av dess 7 ändringslagar, den senaste ÅFS 2026/31, i kraft från den 1 maj 2026. Ålex publicerar bara den gällande texten, så varje senare version återskapas ur sin ändringslag så som författningssamlingen återger den, och den sista kontrolleras mot Ålex. [`amendments.csv`](amendments.csv) förtecknar ändringslagarna, med datum, de paragrafer som var och en ändrade och deras ikraftträdandebestämmelser; varje version har en tagg (`hemvardsstod/2022-56`).

Lagen finns i `hemvardsstod/`, med en fil per paragraf (`paragraf-013.md` är 13 §, hemvårdsstöd för syskon); `rubrik.md` innehåller dess rubrik och ingress.

Texten är på svenska, Ålands officiella språk, så som författningssamlingen och Ålex återger den. En engelsk översättning ingår inte i detta repositorium.

## Frågor som git-kommandon

| Fråga | Kommando |
| --- | --- |
| Varje ändring i 13 § landskapslagen om hemvårdsstöd | `git log -p --word-diff -- hemvardsstod/paragraf-013.md` |
| Vilken lag skrev varje rad i 13 §? | `git blame hemvardsstod/paragraf-013.md` |
| Varje version av lagen, med den dag då den trädde i kraft | `git log --format="%h %(trailers:key=In-force,valueonly,separator=) %an" -- hemvardsstod` |
| 13 § i den lydelse som gällde den 1 juni 2022 | `python tools/alex.py 2022-06-01 hemvardsstod 13` |

**Utanför git** tillhandahåller vi också detta material offentligt och gratis:

- **[Fråga Claude om åländsk lagstiftning](https://global-law.lexifina.com/v1/try_claude?country=aland)**: öppnar Claude med en första fråga färdig.
- **[Fråga ChatGPT](https://global-law.lexifina.com/v1/try_chatgpt?country=aland)**: samma fråga i ChatGPT.
- **[Sök i åländsk lagstiftning på vår webbplats](https://lexifina.com/law?country=aland&q=hemv%C3%A5rdsst%C3%B6d)**: en sökning efter ”hemvårdsstöd”, med varje bestämmelses text och dess versioner, utan konto.
- **[REST-API för utvecklare](https://global-law.lexifina.com/v1/search_law?query=hemv%C3%A5rdsst%C3%B6d&jurisdiction=aland)**: samma sökning som JSON, utan nyckel. Dokumentationen finns [här](https://lexifina.com/api/global-law).

Båda assistenterna läser materialet genom den kostnadsfria kopplingen Global law (MCP, `https://global-law.lexifina.com/mcp`); första gången ger chatten dig länken som lägger till den. Fråga på svenska eller på engelska.

**Kör det enkelt själv.** Det enda som behövs är git och Python, och verktygen körs på din egen dator:

```sh
git clone --depth 1 https://github.com/lexifina/global-law && cd global-law
python3 tools/countries.py add aland/national/acts
python3 tools/law.py show 2026-01-01 aland/national/acts/hemvardsstod/paragraf-013.md
```

Öppnad i Claude Code, Cursor, VS Code eller Codex startar klonen också en lokal MCP-server med samma verktyg ([MCP.md](https://github.com/lexifina/global-law/blob/main/MCP.md)).

## Datum

Varje commit dateras kl. 12.00 Mariehamnstid (Europe/Mariehamn) den dag versionen trädde i kraft, och dagen står i dess trailer `In-force:`:

- för varje version, den dag som lagens egen ikraftträdandebestämmelse i författningssamlingen anger (”Denna lag träder i kraft den 1 maj 2026.”), och den måste vara densamma som den dag Ålex anger; ingen lag här träder i kraft paragraf för paragraf;
- den dag lagen utfärdades står i en trailer `Enacted:`, och övergångsbestämmelser och retroaktiva bestämmelser i en ikraftträdandebestämmelse kopieras ordagrant till trailrar `Applies:` (ÅFS 2023/29 tillåter att hemvårdsstöd för syskon beviljas från den 1 augusti 2022).

Varje ändring tillskrivs den lag som gjorde den (`ÅFS 2022/56`, adress `afs-2022-56@regeringen.ax.invalid`), och den första versionen den ursprungliga lagen, `ÅFS 2015/68`; ingen version tillskrivs utgivaren.

## Hur det kontrolleras

- `tools/build.py` gör inga commits om inte det återskapade slutläget är lika med Ålex:s konsolidering (uppdaterad t.o.m. ÅFS 2026/31) i alla 30 paragrafer, efter den normalisering som [`REPRODUCE.md`](REPRODUCE.md) anger; en ändringsklausul som den inte kan läsa stoppar bygget.
- `tools/check_repo.py` läser tillbaka varje version ur git: den sista måste vara lika med Ålex, fil för fil och ord för ord (2 232 ord), den första med den ursprungliga lagen, och varje ändringslags paragrafer med dess egen text och ikraftträdandedag.
- `tools/test_repo.py` kontrollerar blame, datumverktyget före och efter en ändring, `git log --follow` och taggarna; `tools/build.py --verify-rebuild` bygger materialet på nytt och måste ge samma hash för `main`. Resultaten finns i [`REPRODUCE.md`](REPRODUCE.md).

## Vad det inte visar

- **Officiella tidigare lydelser.** De 6 versionerna mellan den ursprungliga lagen och den gällande texten är återskapade ur ändringslagarna och inte kontrollerade mot en officiell text.
- **Alla andra åländska lagar**, bland dem självstyrelselagen (Självstyrelselag (1991:71) för Åland). Landskapslag (2017:120) om landskapsandelar till kommunerna utelämnades: tre av dess ändringslagar är tidsbegränsade, och Ålex anger inget ikraftträdande för en fjärde (2018/102).
- **Landskapsförordningar, rättspraxis, lagförslag och EU-rätt.**
- **Ändringar efter den 28 oktober 2026**, den dag källorna lästes.

## Källor

| Källa | Typ | Tidigare lydelser | Anmärkningar |
| --- | --- | --- | --- |
| [Ålex](https://www.regeringen.ax/alandsk-lagstiftning) (Ålands landskapsregering) | Konsoliderad lagstiftning | nej, bara den gällande konsolideringen | Slutläget kontrolleras mot den, och varje ikraftträdandedag mot dess förteckning över ikraftträdandebestämmelser; den är informativ, bara ÅFS är auktoritativ |
| Ålands författningssamling (ÅFS), PDF-filer på samma webbplats | Författningssamling | så som de publicerats: den ursprungliga lagen och varje ändringslag | Den auktoritativa texten; varje version byggs ur den |

## Licens

Se [`LICENSE`](LICENSE). Inga licenser eller användarvillkor för texterna hittades på regeringen.ax; författningar omfattas i regel inte av upphovsrätt i Finland (9 § upphovsrättslagen 404/1961), som gäller på Åland. De återskapade versionerna är härledda ur dessa data och publiceras inte av Ålands landskapsregering. Historiken, commit-meddelandena, tabellerna och verktygen omfattas av CC0 1.0.

Ingen modell har skrivit lagtext eller körts när materialet byggs; koden skrevs med Claude, en AI-modell (se [`REPRODUCE.md`](REPRODUCE.md)).

Detta är en översättning av den engelska versionen ([README.en.md](README.en.md)); om de skiljer sig åt gäller den engelska versionen.

## Mer

Från repositoriet [lexifina/global-law](https://github.com/lexifina/global-law) (på engelska):

- [FEATURES.md](https://github.com/lexifina/global-law/blob/main/FEATURES.md): alla funktioner och vad varje korpus måste stödja (`git blame`, `law.py`, MCP-verktyg)
- [FAQ.md](https://github.com/lexifina/global-law/blob/main/FAQ.md): frågor och svar · [CONTRIBUTING.md](https://github.com/lexifina/global-law/blob/main/CONTRIBUTING.md): föreslå ändringar · [MCP.md](https://github.com/lexifina/global-law/blob/main/MCP.md): MCP-server · [REPRODUCE.md](https://github.com/lexifina/global-law/blob/main/REPRODUCE.md): hur det är byggt · [CHANGELOG.md](https://github.com/lexifina/global-law/blob/main/CHANGELOG.md)
- [FRESHNESS.md](https://github.com/lexifina/global-law/blob/main/FRESHNESS.md): hur aktuellt varje korpus är · [Övervakning](https://github.com/lexifina/global-law/tree/main/monitoring): om uppdateringarna fungerar · [WATCHING.md](https://github.com/lexifina/global-law/blob/main/WATCHING.md): hur varje officiell källa bevakas för ändringar
- [performance/](https://github.com/lexifina/global-law/tree/main/performance): hur snabba verktygen är, uppmätt
- [visualisations/](https://github.com/lexifina/global-law/tree/main/visualisations): diagram och kopplingar över hela världens rätt
- [Sårbarheter](https://github.com/lexifina/global-law/tree/main/vulnerabilities): fel i författningar så som de publicerats
