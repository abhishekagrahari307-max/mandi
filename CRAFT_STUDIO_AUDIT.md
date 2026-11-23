# Craft Studio audit

**Scope:** `craft-studio/` in repository at `33a81ac` ancestry / current branch base `0b4c579cf0d328d6de7c51ddaf176d5d0a388e51`; review performed 2026-11-21 (UTC). Live site: https://abhishekagrahari307-max.github.io/mandi/craft-studio/.

**Overall assessment: not production-ready for untrusted files or important work.** The hub loads publicly and contains working client-side editor implementations, but high-risk script execution paths and silent export/data-loss paths need attention. The homepage materially overstates browser implementations and compatibility.

## Method and limitations

- Inspected hub, catalog, service workers, routing, static server, all 14 app entry files, file-import/export handlers and existing tests. Fetched the live landing page and checked three upstream releases' asset names against `assets/releases.json` via GitHub API.
- Ran `python -m unittest discover -s tests -p test_craft_studio.py -v`: **4 passed**. These tests check presence of files, not functional behavior.
- Reproduced GridCraft formula execution in a Node VM using the actual evaluation functions; the harmless formula `=(globalThis.auditMarker=17)` set the marker and returned 17. No external requests or real credentials were used.
- No browser engine was available in the sandbox. This is a source-based audit, not a complete real-browser, cross-browser, accessibility, performance, penetration or round-trip interoperability certification. Individual editor features, vendor dependency vulnerabilities, all download URLs, mobile interactions, and deployed response headers were not exhaustively tested. Observed behavior on a deployed site may vary with its current revision and browser.
- No application code was changed by this audit. Risks marked potential follow from code inspection and require controlled browser confirmation.

## Critical / high priority

### P0 — Spreadsheet formulas execute JavaScript

`craft-studio/apps/gridcraft/index.html:228-233,268-272,592-613` imports workbook formulas and passes their expressions into JavaScript `Function`. The Node reproduction confirmed execution of a harmless global assignment. A malicious formula opened by a user can run arbitrary code in the site's origin, potentially accessing same-origin session data and making network requests. This is not a spreadsheet formula sandbox.

**Recommendation:** immediately avoid opening untrusted spreadsheets; disable formula evaluation or replace it with a restrictive parser/interpreter that cannot execute JS. Add malicious-formula regression tests, resource limits, a strict CSP, and round-trip tests. Treat existing sessions on the same origin as potentially exposed if a hostile document was opened.

### P0 — Unsanitized document and SVG HTML insertion

`craft-studio/apps/wordcraft/index.html:114-125` inserts DOCX-derived HTML, raw `.html`, and even text file contents via `innerHTML`; `:97-99` also re-inserts heading text as markup. `craft-studio/apps/vectorcraft/index.html:162-167` inserts imported SVG markup into the live DOM without sanitization. `craft-studio/apps/deckcraft/index.html:94-108,122-125` interpolates edited text into HTML. Event handlers and active content in untrusted files/input can potentially execute in the application origin. Browser exploit tests were not run.

**Recommendation:** use text nodes for plain text and labels; sanitize rich HTML/SVG with a maintained, configured allowlist sanitizer; strip event handlers, scripts, dangerous URLs, embedded resources and foreign content. Avoid same-origin privileged iframe assumptions and test with adversarial inputs. Do not open untrusted files before mitigation.

### P1 — Import/export can silently discard important content

- **GridCraft:** `apps/gridcraft/index.html:135-141,595-607` caps imports to 14 columns (A–N). Export rebuilds a workbook from evaluated cell values and formula strings (`:616-639`), not original workbook structure; styles and other workbook features are not preserved. Multi-letter references are parsed using only the first character (`:137-141`). Opening and re-saving an existing workbook can lose columns and formatting.
- **WordCraft:** `apps/wordcraft/index.html:128-139` creates paragraphs from `innerText`; formatting, tables, embedded images and other document structures are not faithfully preserved by this export path.
- **DesignCraft:** `apps/designcraft/index.html:85-96` exports title and first 900 story characters into a new PDF. The uploaded hero image, layout and remaining content are not included by this path; it is not an evidenced full-fidelity PDF/A/CMYK export.
- **CADCraft:** `apps/cadcraft/index.html:193-224` exports lines/circles but imports only LINE records and assigns them to WALLS; unsupported entities and layers are dropped. Existing DWG compatibility is not demonstrated by this browser editor.
- **FilmCraft:** `apps/filmcraft/index.html:179-201` assigns imported clips a fixed 3.5 s and stops WebM recording after at most six seconds; the export captures the canvas stream, not an audio track. Longer timelines are truncated and audio is absent from that stream.
- **SoundCraft:** `apps/soundcraft/index.html:168-185` plays imported audio but WAV bounce renders a 32-step sequencer rather than including `customBuffer`; imported stems are not part of the bounce.

**Recommendation:** warn before loss, reject unsupported files/features rather than silently discard, maintain an untouched original, and test import→edit→export round trips against real applications. Restrict marketing and file-type claims to verified functionality until tested.

### P1 — Unsupported Rust/WASM and pro-feature claims

The live landing page and `craft-studio/README.md` describe 14 pure Rust + WebAssembly apps with capabilities such as DWG, RAW, AES-256 and WebGPU. The repository's actual browser entry points inspected are HTML/JS; no `.wasm` files were found under `craft-studio/`, and the editors import JavaScript vendor bundles. This does not establish that the cited upstream Rust projects lack those features; it means the bundled site does not establish that those upstream WASM binaries/features are running. Renderer switch changes iframe query strings (`assets/app.js:211-233,590-595`), but no corresponding application-side renderer handling was identified.

**Recommendation:** clearly distinguish the lightweight browser implementations from upstream native/WASM projects. Remove unverified feature/security/performance claims or ship and verify the actual upstream builds and licenses.

## Medium priority

### P2 — Service worker can interfere with the main Mandi dashboard

`craft-studio/sw.js:25-29` deletes *all* Cache Storage names on the origin except its own, including Mandi's `up-mandi-*` caches. The parent worker similarly deletes cache names other than its own (`sw.js` activate handler). Visiting either app can therefore remove the other's offline cache. The Craft worker also stores every successful GET with no allowlist, size bound or `event.waitUntil` for writes (`craft-studio/sw.js:33-45`); an offline cache miss can resolve to undefined rather than a response. External GET responses may be cached when CORS permits.

**Recommendation:** scope cache cleanup to each application's own prefix, cache only an explicit set of safe assets, bound sizes, use `event.waitUntil`, and return a defined offline fallback. Add tests involving both service workers, offline reload, failed installation and storage quota.

### P2 — Documentation and test coverage do not match deployment

`craft-studio/README.md` references `python3 scripts/build_site.py`, but `craft-studio/scripts/` is absent, and the documented public links use `/craft-studio/` rather than this repository's `/mandi/craft-studio/` route. The four existing tests mostly check file existence; none executes the editors or checks imported files, malicious inputs, export fidelity, responsive behavior or offline behavior.

**Recommendation:** correct deployment URLs/build instructions and add browser-based CI for all 14 routes plus import/export fixtures, security regression tests, PWA behavior, mobile screens and supported browsers. Audit and document bundled library versions, source and licenses.

### P2 — Privacy guarantee is too broad

The landing page claims “Files never leave your device”. The app files largely process input locally, but unsanitized rich HTML/SVG can reference remote resources or execute scripts, and there is no demonstrated restrictive application CSP. Therefore the absolute privacy claim is not established for hostile inputs.

**Recommendation:** constrain imported content and network destinations; document what local processing means and any network requests; verify with browser network tests using malicious and benign fixture files.

## Per-app review inventory

Source inspection, not an end-to-end certification:

| App | What was observed | Main follow-up |
|---|---|---|
| GridCraft | JS spreadsheet import, formula evaluator and XLSX/CSV export | P0 formula execution; 14-column truncation; fidelity |
| PhotoCraft | JS canvas/PSD import and exports | Security-review layer/file-name rendering, PSD fidelity and file-size limits |
| PdfCraft | PDF.js/PDF-lib viewer and page operations | Test forms, annotations, encryption, signatures and round-trip; no AES-256 guarantee established |
| WordCraft | DOCX/text/HTML import and DOCX/HTML export | P0 unsafe HTML; formatting loss |
| DeckCraft | Editable slides and PPTX export | P0 unsafe interpolation; fidelity and notes round-trip |
| LightCraft | Browser image loading, pixel adjustments and JPG export | Actual RAW format support and preservation need verification |
| VectorCraft | SVG editing, SVG/PNG export | P0 unsafe SVG import; sanitization and fidelity |
| FigCraft | DOM component editor and HTML export | Inspect interpolation and test export; advertised .fig support not established |
| DesignCraft | Browser layout and simplified PDF export | Partial content export; PDF/A/CMYK claim |
| FilmCraft | Canvas preview and WebM recording | 6-second cap, fixed clip duration and no audio stream |
| EffectCraft | Canvas animation, generated Lottie JSON and WebM | Validate exported Lottie and actual content fidelity |
| SoundCraft | Sequencer and audio playback, WAV bounce | Imported audio not included in bounce |
| CADCraft | Basic canvas entities, DXF/PNG export | Partial DXF parser; loss of circles/layers on re-import |
| Launcher | Displays release metadata and links | Validate all links periodically; the 21 asset filenames sampled for GridCraft, PhotoCraft and PdfCraft matched upstream release assets at audit time |

## Suggested remediation order

1. Disable unsafe GridCraft formula execution and sanitize WordCraft/VectorCraft/DeckCraft input; add security tests and isolation.
2. Prevent silent data loss: warnings, unsupported-feature detection and representative round-trip tests for GridCraft, WordCraft, DesignCraft, FilmCraft, SoundCraft and CADCraft.
3. Correct homepage, catalog and documentation claims; preserve attribution and verify licenses of bundled dependencies.
4. Isolate both service-worker caches and test offline behavior.
5. Add a real-browser CI suite, mobile/accessibility checks, dependency inventory, file-size/error handling and release-link verification.
