# Comic Metadata icon rendered review — 2026-10-13

Owner: Judy. Scope: DesktopShell §10 and icon-state glyphs/rings in §2 only. **Verdict: FIX REQUIRED before icon QA handoff.** This is not a complete desktop UX or release verdict.

## Required fix

**I1 — Verification glyph loses its exclamation mark at 16 px.** In desktop/assets/tray-verification-16.png, sampled glyph pixels are x12,y11–13: one continuous 1×3 white bar. There is no separate dot. At actual size on both taskbars it reads as a bar, while the committed state symbol is !. Ender: preserve the reserved zone, palette and ring; separate the stem and dot on the 16 px grid, regenerate affected crops and submit that exact source for recheck. The 32 px verification glyph is visibly an exclamation mark.

## Passing checks and measured methods

Viewed all 22 supplied 64×64 crops individually using view_image at their actual scale1 size, with the 16/20/24/32/48 px mark centred on #202020 and #f3f3f3; three badge states at16 and32 on both backgrounds. Independently decoded actual PNGs with Pillow. Every source SHA256 matches manifest.json; recompositing every source at its native size reproduces all22 crop RGB bytes exactly. ICO has exactly16,20,24,32,40,48,64,256 frames; every decoded frame equals its matching PNG RGBA bytes. Processing tray16 and32 equal basePNG16 and32. SVG geometry/flat fills match the committed32px master.

Base16 sampled grid exactly equals §10, opaque teal/white only: top white panel x4–11,y1–6; horizontal teal gutter y7,x3–12; lower panels x4–6 and x8–11,y8–14, divided by teal x7. Panels/gutters remain distinct at actual16px. Base20/24 use only transparent, teal and white pixels; no antialiased gutters. Larger rounded corners have coverage pixels as expected.

Contrast uses sampled solid interior/edge colours and the sRGB relative luminance formula, not antialiased corner fringe pixels. Teal #1f8a80:3.8835:1 on dark,3.7810:1 on light; panels4.1955:1 on teal. Pause #707070:3.2901 dark,4.4629 light,4.9521 white ring/glyph. Verification #b87300:4.2598 dark,3.4470 light,3.8249 white. Error #d13438:3.3047 dark,4.4432 light,4.9303 white. All meaningful solid boundaries exceed3:1. White rings remain visible and keep badge fills apart from teal; pause has two distinct bars, error has the crossed shape at16/32; consistent shapes/palette on both backgrounds. No native GUI launch, focus or audio.

Limits: these are asset crops, not native Windows tray/taskbar captures or runtime state/tooltips. Accent taskbar not assessed: none specified by Sergei. §2 mentions24px badges but §10 review gate and delivered manifest require16/32; native DPI representations remain Futaba's job. Existing Yandex references in older shell spec do not authorize implementation; current v014 supports Lens.

## Evidence

Crop manifest: C:/Users/AnGeLZzZ/AppData/Local/Temp/illuminati-codex-cmo-installer-resume-20261013/ender/icon-review-01/manifest.json

Independent measurements: C:/Users/AnGeLZzZ/AppData/Local/Temp/illuminati-codex-cmo-installer-resume-20261013/judy/icon-measurements.json

Pinned reviewed sources:
- icon.svg SHA256 2792c2fbb44cba34eaa0639229c158341b8fc64f56c449b9f84078ba694f19fc
- icon.ico SHA256 9aa838eca9eec3469c1e04f5959ab1e3c02ffc46022b37afb80c871d9bd5bbb0
- tray-verification-16.png SHA256 0c25c7a0a430e42fbaf3482a9d01452330ff5a049b9ead3b3add892aa5b7718f
- tray-verification.png SHA256 13342e149e19c54b8e6eaa575d846096caa6d0ca5e7e6b83f9c68948a65ca593

Report kept in owned Temp while Ender's M1 graph is frozen. No code/assets/git/live/service/trust/hook config changed. Retain unique crops/measurements until I1 resolved; removed owned disposable diagnostic script after measurements.

## Recheck — 2026-10-14

I1 FIXED; **Icon asset review: PASS** for icon-review-02 graph. Native shell/state UX acceptance remains separate. Viewed corrected16px verification crops on both backgrounds at actualscale: stem/dot distinct. Independently sampled x12,y10–13 = white,white,amber,white: onepixelgap is real. All22 regeneratedcrop/source hashes and exact native-size composites pass. Source tray-verification-16 SHA256 ac645a0c07f528278d2d75d826cc1b518174b9fe84f2f0f9710d62892289e097; newmanifest SHA2566bdd2604677df1bb9bc3dce4780b9c81ebad0af142ab36909ca85d5fc1fc84de. Otherassets unchanged permanifest comparedto01; originalgeometry/contrast/ICOchecks apply. Recheck measurements retained in owned Temp; script removed.
