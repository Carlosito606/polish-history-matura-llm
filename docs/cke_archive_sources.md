# CKE historia matura archive — source pages (arkusze.pl)

Source of truth for `scripts/fetch_arkusze.py`. Each row is one page on
[arkusze.pl](https://arkusze.pl/); the script re-crawls the page and downloads whatever
PDF links (exam sheet + answer key / zasady oceniania, plus any extra attachment) are
on it that day. No PDF content or extracted text is committed — only this URL list and
the fetch script. Checked 2026-09-25; site's `robots.txt` allows crawling (`Disallow:` empty).

Columns: year / session / level are read off the URL slug itself (not verified per-PDF
here — the fetch script re-derives and records them per download in `manifest.json`).

| # | year | session | level | slug (page URL) |
|---|------|---------|-------|------------------|
| 1 | 2003 | maj | podstawowy | https://arkusze.pl/matura-historia-2003-maj-poziom-podstawowy/ |
| 2 | 2003 | maj | rozszerzony | https://arkusze.pl/matura-historia-2003-maj-poziom-rozszerzony/ |
| 3 | 2005 | maj | podstawowy | https://arkusze.pl/matura-historia-2005-maj-poziom-podstawowy/ |
| 4 | 2005 | maj | rozszerzony | https://arkusze.pl/matura-historia-2005-maj-poziom-rozszerzony/ |
| 5 | 2006 | maj | podstawowy | https://arkusze.pl/matura-historia-2006-maj-poziom-podstawowy/ |
| 6 | 2006 | maj | rozszerzony | https://arkusze.pl/matura-historia-2006-maj-poziom-rozszerzony/ |
| 7 | 2007 | maj | podstawowy | https://arkusze.pl/matura-historia-2007-maj-poziom-podstawowy/ |
| 8 | 2007 | maj | rozszerzony | https://arkusze.pl/matura-historia-2007-maj-poziom-rozszerzony/ |
| 9 | 2008 | maj | podstawowy | https://arkusze.pl/matura-historia-2008-maj-poziom-podstawowy/ |
| 10 | 2008 | maj | rozszerzony | https://arkusze.pl/matura-historia-2008-maj-poziom-rozszerzony/ |
| 11 | 2009 | maj | podstawowy | https://arkusze.pl/matura-historia-2009-maj-poziom-podstawowy/ |
| 12 | 2009 | maj | rozszerzony | https://arkusze.pl/matura-historia-2009-maj-poziom-rozszerzony/ |
| 13 | 2010 | maj | podstawowy | https://arkusze.pl/matura-historia-2010-maj-poziom-podstawowy/ |
| 14 | 2010 | maj | rozszerzony | https://arkusze.pl/matura-historia-2010-maj-poziom-rozszerzony/ |
| 15 | 2011 | czerwiec | podstawowy | https://arkusze.pl/matura-historia-2011-czerwiec-poziom-podstawowy/ |
| 16 | 2011 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2011-czerwiec-poziom-rozszerzony/ |
| 17 | 2011 | maj | podstawowy | https://arkusze.pl/matura-historia-2011-maj-poziom-podstawowy/ |
| 18 | 2011 | maj | rozszerzony | https://arkusze.pl/matura-historia-2011-maj-poziom-rozszerzony/ |
| 19 | 2012 | czerwiec | podstawowy | https://arkusze.pl/matura-historia-2012-czerwiec-poziom-podstawowy/ |
| 20 | 2012 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2012-czerwiec-poziom-rozszerzony/ |
| 21 | 2012 | maj | podstawowy | https://arkusze.pl/matura-historia-2012-maj-poziom-podstawowy/ |
| 22 | 2012 | maj | rozszerzony | https://arkusze.pl/matura-historia-2012-maj-poziom-rozszerzony/ |
| 23 | 2013 | maj | podstawowy | https://arkusze.pl/matura-historia-2013-maj-poziom-podstawowy/ |
| 24 | 2013 | maj | rozszerzony | https://arkusze.pl/matura-historia-2013-maj-poziom-rozszerzony/ |
| 25 | 2014 | maj | podstawowy | https://arkusze.pl/matura-historia-2014-maj-poziom-podstawowy/ |
| 26 | 2014 | maj | rozszerzony | https://arkusze.pl/matura-historia-2014-maj-poziom-rozszerzony/ |
| 27 | 2015 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2015-czerwiec-poziom-rozszerzony/ |
| 28 | 2015 | maj | rozszerzony | https://arkusze.pl/matura-historia-2015-maj-poziom-rozszerzony/ |
| 29 | 2015 | przykladowy | rozszerzony | https://arkusze.pl/matura-historia-2015-przykladowy-arkusz-cke-poziom-rozszerzony/ |
| 30 | 2016 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2016-czerwiec-poziom-rozszerzony/ |
| 31 | 2016 | maj | rozszerzony | https://arkusze.pl/matura-historia-2016-maj-poziom-rozszerzony/ |
| 32 | 2017 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2017-czerwiec-poziom-rozszerzony/ |
| 33 | 2017 | maj | rozszerzony | https://arkusze.pl/matura-historia-2017-maj-poziom-rozszerzony/ |
| 34 | 2018 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2018-czerwiec-poziom-rozszerzony/ |
| 35 | 2018 | maj | rozszerzony | https://arkusze.pl/matura-historia-2018-maj-poziom-rozszerzony/ |
| 36 | 2019 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2019-czerwiec-poziom-rozszerzony/ |
| 37 | 2019 | maj | rozszerzony | https://arkusze.pl/matura-historia-2019-maj-poziom-rozszerzony/ |
| 38 | 2020 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2020-czerwiec-poziom-rozszerzony/ |
| 39 | 2020 | lipiec | rozszerzony | https://arkusze.pl/matura-historia-2020-lipiec-poziom-rozszerzony/ |
| 40 | 2021 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2021-czerwiec-poziom-rozszerzony/ |
| 41 | 2021 | maj | rozszerzony | https://arkusze.pl/matura-historia-2021-maj-poziom-rozszerzony/ |
| 42 | 2022 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2022-czerwiec-poziom-rozszerzony/ |
| 43 | 2022 | maj | rozszerzony | https://arkusze.pl/matura-historia-2022-maj-poziom-rozszerzony/ |
| 44 | 2023 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2023-czerwiec-poziom-rozszerzony/ |
| 45 | 2023 | maj | rozszerzony | https://arkusze.pl/matura-historia-2023-maj-poziom-rozszerzony/ |
| 46 | 2023 | przykladowy | rozszerzony | https://arkusze.pl/matura-historia-2023-przykladowy-arkusz-cke-poziom-rozszerzony/ |
| 47 | 2024 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2024-czerwiec-poziom-rozszerzony/ |
| 48 | 2024 | maj | rozszerzony | https://arkusze.pl/matura-historia-2024-maj-poziom-rozszerzony/ |
| 49 | 2025 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2025-czerwiec-poziom-rozszerzony/ |
| 50 | 2025 | maj | rozszerzony | https://arkusze.pl/matura-historia-2025-maj-poziom-rozszerzony/ |
| 51 | 2026 | czerwiec | rozszerzony | https://arkusze.pl/matura-historia-2026-czerwiec-poziom-rozszerzony/ |
| 52 | 2026 | maj | rozszerzony | https://arkusze.pl/matura-historia-2026-maj-poziom-rozszerzony/ |
| 53 | 2010 | sierpien (poprawkowa) | podstawowy | https://arkusze.pl/matura-poprawkowa-historia-2010-sierpien-poziom-podstawowy/ |
| 54 | 2010 | sierpien (poprawkowa) | rozszerzony | https://arkusze.pl/matura-poprawkowa-historia-2010-sierpien-poziom-rozszerzony/ |
| 55 | 2011 | sierpien (poprawkowa) | podstawowy | https://arkusze.pl/matura-poprawkowa-historia-2011-sierpien-poziom-podstawowy/ |
| 56 | 2003 | styczen (probna) | podstawowy | https://arkusze.pl/matura-probna-historia-2003-styczen-poziom-podstawowy/ |
| 57 | 2003 | styczen (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2003-styczen-poziom-rozszerzony/ |
| 58 | 2004 | grudzien (probna) | podstawowy | https://arkusze.pl/matura-probna-historia-2004-grudzien-poziom-podstawowy/ |
| 59 | 2004 | grudzien (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2004-grudzien-poziom-rozszerzony/ |
| 60 | 2004 | styczen (probna) | podstawowy | https://arkusze.pl/matura-probna-historia-2004-styczen-poziom-podstawowy/ |
| 61 | 2004 | styczen (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2004-styczen-poziom-rozszerzony/ |
| 62 | 2005 | grudzien (probna) | podstawowy | https://arkusze.pl/matura-probna-historia-2005-grudzien-poziom-podstawowy/ |
| 63 | 2005 | grudzien (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2005-grudzien-poziom-rozszerzony/ |
| 64 | 2005 | styczen (probna) | podstawowy | https://arkusze.pl/matura-probna-historia-2005-styczen-poziom-podstawowy/ |
| 65 | 2005 | styczen (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2005-styczen-poziom-rozszerzony/ |
| 66 | 2006 | listopad (probna) | podstawowy | https://arkusze.pl/matura-probna-historia-2006-listopad-poziom-podstawowy/ |
| 67 | 2006 | listopad (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2006-listopad-poziom-rozszerzony/ |
| 68 | 2006 | styczen (probna) | podstawowy | https://arkusze.pl/matura-probna-historia-2006-styczen-poziom-podstawowy/ |
| 69 | 2006 | styczen (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2006-styczen-poziom-rozszerzony/ |
| 70 | 2008 | marzec (probna) | podstawowy | https://arkusze.pl/matura-probna-historia-2008-marzec-poziom-podstawowy/ |
| 71 | 2008 | marzec (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2008-marzec-poziom-rozszerzony/ |
| 72 | 2009 | styczen (probna) | podstawowy | https://arkusze.pl/matura-probna-historia-2009-styczen-poziom-podstawowy/ |
| 73 | 2009 | styczen (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2009-styczen-poziom-rozszerzony/ |
| 74 | 2014 | grudzien (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2014-grudzien-poziom-rozszerzony/ |
| 75 | 2020 | kwiecien (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2020-kwiecien-poziom-rozszerzony/ |
| 76 | 2021 | marzec (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2021-marzec-poziom-rozszerzony/ |
| 77 | 2022 | grudzien (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2022-grudzien-poziom-rozszerzony/ |
| 78 | 2024 | grudzien (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2024-grudzien-poziom-rozszerzony/ |
| 79 | 2026 | styczen (probna) | rozszerzony | https://arkusze.pl/matura-probna-historia-2026-styczen-poziom-rozszerzony/ |
| 80 | 2015 | maj (stara matura) | podstawowy | https://arkusze.pl/matura-stara-historia-2015-maj-poziom-podstawowy/ |
| 81 | 2015 | maj (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2015-maj-poziom-rozszerzony/ |
| 82 | 2016 | maj (stara matura) | podstawowy | https://arkusze.pl/matura-stara-historia-2016-maj-poziom-podstawowy/ |
| 83 | 2016 | maj (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2016-maj-poziom-rozszerzony/ |
| 84 | 2017 | maj (stara matura) | podstawowy | https://arkusze.pl/matura-stara-historia-2017-maj-poziom-podstawowy/ |
| 85 | 2017 | maj (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2017-maj-poziom-rozszerzony/ |
| 86 | 2018 | maj (stara matura) | podstawowy | https://arkusze.pl/matura-stara-historia-2018-maj-poziom-podstawowy/ |
| 87 | 2018 | maj (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2018-maj-poziom-rozszerzony/ |
| 88 | 2019 | maj (stara matura) | podstawowy | https://arkusze.pl/matura-stara-historia-2019-maj-poziom-podstawowy/ |
| 89 | 2019 | maj (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2019-maj-poziom-rozszerzony/ |
| 90 | 2020 | czerwiec (stara matura) | podstawowy | https://arkusze.pl/matura-stara-historia-2020-czerwiec-poziom-podstawowy/ |
| 91 | 2020 | czerwiec (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2020-czerwiec-poziom-rozszerzony/ |
| 92 | 2023 | czerwiec (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2023-czerwiec-poziom-rozszerzony/ |
| 93 | 2023 | maj (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2023-maj-poziom-rozszerzony/ |
| 94 | 2024 | czerwiec (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2024-czerwiec-poziom-rozszerzony/ |
| 95 | 2024 | maj (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2024-maj-poziom-rozszerzony/ |
| 96 | 2025 | czerwiec (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2025-czerwiec-poziom-rozszerzony/ |
| 97 | 2025 | maj (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2025-maj-poziom-rozszerzony/ |
| 98 | 2026 | czerwiec (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2026-czerwiec-poziom-rozszerzony/ |
| 99 | 2026 | maj (stara matura) | rozszerzony | https://arkusze.pl/matura-stara-historia-2026-maj-poziom-rozszerzony/ |

Fetch with: `python scripts/fetch_arkusze.py` (downloads into `data_cke/arkusze/<slug>/`,
manifest at `data_cke/arkusze/manifest.json`, both git-ignored).
