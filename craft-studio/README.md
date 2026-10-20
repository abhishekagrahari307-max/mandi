# Craft Studio — Excel, Photo, PDF & Complete 14-App WebAssembly Suite

**Live Website:** [https://abhishekagrahari307-max.github.io/craft-studio/](https://abhishekagrahari307-max.github.io/craft-studio/)

All **14 open-source pure-Rust + WebAssembly applications** from the [storytold](https://github.com/storytold) suite hosted together on one fast, zero-backend website with **Multi-Tab Studio OS**, **Side-by-Side Split View**, **Hindi / English UI**, **WebGPU / WebGL2 / CPU renderer switching**, and **direct native desktop downloads** (Windows, macOS, Linux & FreeBSD).

---

## Included Applications (Live in Browser via WebAssembly)

| Category | App | Direct Browser Route | Upstream Rust Repo | Key Formats |
|---|---|---|---|---|
| **Excel** | **GridCraft** | [`/apps/gridcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/gridcraft/) · [`/excel/`](https://abhishekagrahari307-max.github.io/craft-studio/excel/) | [`storytold/gridcraft`](https://github.com/storytold/gridcraft) | `.xlsx`, `.csv`, `.tsv`, Formulas, Pivot Tables, Charts |
| **Photo** | **PhotoCraft** | [`/apps/photocraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/photocraft/) · [`/photo/`](https://abhishekagrahari307-max.github.io/craft-studio/photo/) | [`storytold/photocraft`](https://github.com/storytold/photocraft) | `.psd`, `.psb`, `.png`, `.jpg`, `.webp`, `.heic`, `.svg`, `.kra`, `.ora` |
| **PDF** | **PdfCraft** | [`/apps/pdfcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/pdfcraft/) · [`/pdf/`](https://abhishekagrahari307-max.github.io/craft-studio/pdf/) | [`storytold/pdfcraft`](https://github.com/storytold/pdfcraft) | `.pdf` Read, Merge, Split, Reorder, Rotate, Forms, AES-256 |
| **Word** | **WordCraft** | [`/apps/wordcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/wordcraft/) · [`/word/`](https://abhishekagrahari307-max.github.io/craft-studio/word/) | [`storytold/wordcraft`](https://github.com/storytold/wordcraft) | `.docx`, `.doc`, `.odt`, `.rtf`, `.md`, `.pdf` |
| **Slides** | **DeckCraft** | [`/apps/deckcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/deckcraft/) · [`/slides/`](https://abhishekagrahari307-max.github.io/craft-studio/slides/) | [`storytold/deckcraft`](https://github.com/storytold/deckcraft) | `.pptx`, `.pdf`, `.png`, Morph Transitions |
| **RAW Photo** | **LightCraft** | [`/apps/lightcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/lightcraft/) · [`/raw/`](https://abhishekagrahari307-max.github.io/craft-studio/raw/) | [`storytold/lightcraft`](https://github.com/storytold/lightcraft) | `.dng`, `.cr2`, `.nef`, `.arw`, `.raf`, 32-bit RAW |
| **Vector** | **VectorCraft** | [`/apps/vectorcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/vectorcraft/) · [`/vector/`](https://abhishekagrahari307-max.github.io/craft-studio/vector/) | [`storytold/vectorcraft`](https://github.com/storytold/vectorcraft) | `.svg`, `.pdf`, `.png`, `.webp`, Image Trace |
| **UI / UX** | **FigCraft** | [`/apps/figcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/figcraft/) · [`/ui/`](https://abhishekagrahari307-max.github.io/craft-studio/ui/) | [`storytold/figcraft`](https://github.com/storytold/figcraft) | `.figcraft`, `.fig`, `.svg`, CSS / React / SwiftUI |
| **Publishing** | **DesignCraft** | [`/apps/designcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/designcraft/) · [`/layout/`](https://abhishekagrahari307-max.github.io/craft-studio/layout/) | [`storytold/designcraft`](https://github.com/storytold/designcraft) | Spreads, CMYK & Bleed `PDF/A` |
| **Video** | **FilmCraft** | [`/apps/filmcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/filmcraft/) · [`/video/`](https://abhishekagrahari307-max.github.io/craft-studio/video/) | [`storytold/filmcraft`](https://github.com/storytold/filmcraft) | H.264, HEVC, ProRes, VP9, Scopes, EBU R128 |
| **Motion VFX** | **EffectCraft** | [`/apps/effectcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/effectcraft/) · [`/vfx/`](https://abhishekagrahari307-max.github.io/craft-studio/vfx/) | [`storytold/effectcraft`](https://github.com/storytold/effectcraft) | Lottie `.json`, 3D Cameras, Particles, Alpha Video |
| **Audio DAW** | **SoundCraft** | [`/apps/soundcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/soundcraft/) · [`/audio/`](https://abhishekagrahari307-max.github.io/craft-studio/audio/) | [`storytold/soundcraft`](https://github.com/storytold/soundcraft) | `.wav`, `.flac`, `.mp3`, MIDI, Mixer & Synths |
| **2D/3D CAD** | **CADCraft** | [`/apps/cadcraft/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/cadcraft/) · [`/cad/`](https://abhishekagrahari307-max.github.io/craft-studio/cad/) | [`storytold/cadcraft`](https://github.com/storytold/cadcraft) | `.dwg` (R13–2018), `.dxf` (R12–2018), Scale PDF |
| **Suite Hub** | **Craft Launcher** | [`/apps/launcher/`](https://abhishekagrahari307-max.github.io/craft-studio/apps/launcher/) | [`storytold/craft-launcher`](https://github.com/storytold/craft-launcher) | Native Windows, macOS, Linux & Web Manager |

---

## Local Build & Preview

```bash
python3 scripts/build_site.py
python3 server.py --port 8080
```

## License & Attribution

- Upstream Crafting Apps, app icons, and public-domain demo artworks are developed by the contributors at [`github.com/storytold`](https://github.com/storytold) and dual-licensed under **MIT OR Apache-2.0**.
- Bundled UI variable fonts (`Archivo`, `Inter`, `Geist Mono`) are licensed under the **SIL Open Font License 1.1** (`public/assets/fonts/OFL-*.txt`).
