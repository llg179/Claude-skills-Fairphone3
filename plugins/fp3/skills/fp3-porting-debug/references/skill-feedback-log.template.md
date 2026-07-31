# FP3 skill-feedback log

> ⚠️ **AI-generated.** This page — and the code, device tree and tooling it
> describes — was written by Claude (Opus 5) working under the direction of
> Lajosházi, László Gergely, who reviewed every change and made or reviewed
> every measurement it rests on. Kernel commits carry `Co-authored-by: Claude`;
> anything prepared for the LKML carries `Assisted-by:` instead and never a
> `Signed-off-by` from the assistant, since only a human can certify the DCO.

**Cél:** a munka közben felismert *átvihető* módszertani tanulságok futó gyűjtője —
gotcha-k, új brick-safety osztályok, mérés-integritási csapdák, jobb receptek, vagy egy
jelenlegi skill-állítás *korrekciója*. Ez a **nyersanyag a `fp3-porting-debug` /
`fp3-kernel-test` skillek és a `references/` fájlok későbbi szerkesztéséhez.**

**Nem** a nyomozási napló: az a konkrét hiba `hipotézis→teszt→verdikt` idővonalát rögzíti
(`FP3-slim-debug-journal.md`). Ez a log azt rögzíti, hogy „ez egy átvihető mozdulat, amit
érdemes a módszerbe emelni" — vagy egy fw-cím/érték, amit egy `references/` adat-fájlban
frissíteni kell.

## Hogyan használd (a skillek erre utasítanak)
- **Fűzz be egy bejegyzést**, amikor tartós, átvihető tanulságba futsz (nem egyszeri tényt).
- **Címkézd a célt:** melyik skill + szekció, vagy melyik `references/` fájl frissüljön.
- **Jelöld a státuszt:** `NEW` (még nem beemelt) / `PROMOTED` (beemelve — egysoros hol) / `DROPPED`.
- **Skill-revízió indításakor** (te vagy a user) olvasd a `NEW` bejegyzéseket, emeld be őket a
  megfelelő skillbe/reference-be, állítsd `PROMOTED`-re (egy soros hivatkozással), és nyesd.
- A dátumozott eredmény-log-fájlok NEM kerülnek a skillekbe; azok a `data-index.md`-ben élnek.
  Ez a log a *hídja* a napló és a skill között.

## Bejegyzés-formátum
```
### <YYYY-MM-DD> — <rövid cím>   [cél: <skill/szekció vagy references/fájl>]   [státusz: NEW]
<mi a tanulság; miért átvihető; a worked example, ami felszínre hozta>
```

---
_(bejegyzések alább, legújabb elöl)_
