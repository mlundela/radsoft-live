# Radsoft live

Sorterer rekkene dine fra Radsoft etter antall rette på tippekupongen, med live-resultater fra Norsk Tipping.

**Side:** https://mlundela.github.io/radsoft-live/

## Bruk

Siden viser den nyeste `.fak`-fila i repoet (nyeste tidsstempel i filnavnet, f.eks. `LFulltid_202610311328.fak`).
Ny kupong: eksporter fra Radsoft, legg fila i repoet og push.

Du kan også laste opp en annen fil i nettleseren («Last opp ny .fak-fil» eller dra den inn). Den brukes i den
nettleseren til repoet får en ny `.fak`-fil, eller til du trykker «bruk … fra repoet».

Live-resultater hentes hvert minutt. Du kan også sette resultater selv med H/U/B-knappene.

## Datakilde

`GET https://api.norsk-tipping.no/PoolGamesSportInfo/v1/api/tipping/game/resulted-and-closest-before-date?date=<ISO>`
gir kupongen med siste salgsstopp før `date`, med `matches[].results.current` (live), `results.fullTime` og
`status.value` (`ENDED` når kampen er ferdig). API-et svarer med CORS `*`, så siden kan hente direkte.

## .fak-formatet (det vi bruker)

- `#oppsett`: kampnr 1–12, 12 hjemmelag, 12 bortelag, folkerekka (12 H, 12 U, 12 B), egne prosenter
  (12 H, 12 U, 12 B), 12 ukjente verdier, 12 avsparkstider, … , antall rekker, kupongfrist.
- `#rader`: én rekke per linje, 12 tegn der 1 = H, 2 = U, 3 = B.
- Tegnsett: Windows-1252, men noen lagnavn ligger som UTF-8.

## Lokalt uten nett-hosting

`python3 tipping_live.py [fil.fak]` bygger siden fra `rekker_mal.html` med rekkene innebygd og serverer den på
http://localhost:8765, med `/api/live` som proxy mot Norsk Tipping.
