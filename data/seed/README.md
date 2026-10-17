# Seed corpus

`manifest.json` lists the curated real cases (one entry per case: cite, name, `match` fragment used to verify the
fetched case name, CAP reporter slug/volume/page, court id, group, status). `raw/` caches the fetched, slimmed
JSON (`{reporter}-{volume}-{page:04d}.json`: name, date, cites, court, `cites_to` with CAP case ids, opinion text),
so a fresh clone builds offline: `stare ingest seed --offline`. `treatments.json` holds curated negative treatment
(legislative supersession, abrogation, vacatur).

Sources: CAP static (static.case.law) for everything up to 2019 (`us` through 2014, `s-ct` 2013-2020, `f2d`, `f3d`,
`f-supp*`, `f-appx`); law.cornell.edu supremecourt text for Groff v. DeJoy and Muldrow v. City of St. Louis
(source `lii`; CAP has no U.S. Reports volumes after 2014). Post-2014 S. Ct. cases carry their U.S. Reports cite in
`extra_cites`.

Status: 53 Supreme Court, 82 courts of appeals (ca5 40, ca9 29; includes 13 unpublished F. App'x), 15 district
(N.D. Tex. 8, N.D. Cal. 7), 1 Mata-location case = 151 opinions. `needs_token`: Mata v. Avianca, 678 F. Supp. 3d 443
(S.D.N.Y. 2023): not in CAP (coverage ends 2019) and CourtListener's cluster/opinion endpoints answer 401 without a
token; no text was fabricated.

## Mata v. Avianca reporter locations (CAP, checked against volume metadata)

| Fake citation in the brief | What CAP has there |
|---|---|
| 905 F. Supp. 2d 121 ("Petersen v. Iran Air", D.D.C. 2012) | A real, different case begins there: United States v. ISS Marine Services, Inc., 905 F. Supp. 2d 121 (D.D.C. 2012). Added to the seed (group `mata_real_cite`). |
| 925 F.3d 1339 ("Varghese v. China Southern Airlines", 11th Cir. 2019) | No case begins on page 1339. The page falls inside J.D. v. Azar, 925 F.3d 1291 (D.C. Cir. 2019) (pages 1291-1349); the next case is Philipp v. Federal Republic of Germany, 925 F.3d 1349. Nothing added. |
| 174 F.3d 366 ("Miller v. United Airlines", 2d Cir. 1999) | No case begins on page 366. The page falls inside Greenleaf v. Garlock, Inc., 174 F.3d 352 (3d Cir. 1999); Miller v. City of Philadelphia, 174 F.3d 368 (3d Cir. 1999) starts two pages later. Nothing added. |

The other three fabrications use WL or Illinois neutral cites and are not in any reporter volume. Gate 2 should
therefore compare the case name for 905 F. Supp. 2d 121 (a real cite, wrong name), and treat the other two as
"not found at that first page".

## Curated treatments (`treatments.json`)

Toyota v. Williams, Sutton, Murphy: superseded by the ADA Amendments Act of 2008 (Pub. L. 110-325). Ledbetter:
superseded by the Lilly Ledbetter Fair Pay Act of 2009 (Pub. L. 111-2). Wards Cove, Price Waterhouse: superseded in
part by the Civil Rights Act of 1991 (Pub. L. 102-166), severity `warning`. Mattern v. Eastman Kodak: abrogated by
Burlington Northern v. White (2006). Barnett v. U.S. Air (9th Cir. en banc): vacated by US Airways v. Barnett (2002).

## Adding cases

Add an entry to `manifest.json` with `status: "pending"` and run `stare ingest seed` (online): it fetches missing
cases, rejects any whose name does not contain `match`, and rewrites the statuses.
