# Comics Meta Organizer - nested ComicInfo merge (option d), dry run

Date: 2026-11-18 22:50:36. Tool: `tools/nested_comicinfo_merge.py` (dry run). Library: `Y:\Comix`. Took 247 s.

Read-only: each archive opened with a read-only handle that lets the app rename, replace or delete it meanwhile; the app's backup (`.comic-metadata-backups`), conversion-staging (`.comic-metadata-convert-*`) and `.yacreaderlibrary` folders skipped; any archive with a `.metadata-tmp` beside it (a write under way) skipped; no catalog opened. Nothing written to any comic, the catalog or the config.

Beside this file: `ComicsMetaOrganizer_NestedMergeDryRun_2026-11-18.csv` (one row per field filled or nested value dropped, with the value, and the nested entry removed) and `ComicsMetaOrganizer_NestedMergeDryRun_2026-11-18.json` (the plan the apply mode takes).

Rule: fill-empty from the nested copy into the root copy, element by element (the app's `merge_comicinfo`); where both copies hold a value the root wins; a nested "None" is blank; then the nested entry is removed, so one ComicInfo remains. Sergei's rulings (2026-11-18): copies naming a different Series or Number are merged (the root's stay); after Futaba's sample the merge never copies a nested Year, Month or Day, PageCount, a tag that is another tag's letter-case twin (`writer` beside `Writer`) or a Volume that is a four-digit year; the merged values are recorded as an automatic write from source `nested-comicinfo-merge`, not as Sergei's; each backup is deleted once its archive is re-read and verified, after the dropped nested values and the whole nested copy are saved in the apply's `--out` folder.

## Library

| Layout | Archives |
|---|---:|
| No ComicInfo | 11212 |
| Root copy only | 28929 |
| One nested copy, no root (Part 1: read, moved to the root at the next write) | 150 |
| Root + one nested (this merge) | 357 |
| Root + several nested (not planned) | 1 |
| RAR/7-Zip named .cbz | 1 |
| **CBZ files** | **40650** |

One nested copy, no root: 150, of which 150 readable and 0 unreadable (ignored and kept, as before).

## Merge set (root + one nested copy)

| Outcome | Archives |
|---|---:|
| Merge, then remove the nested entry | 356 |
| - of which fill at least one field | 298 |
| - of which fill nothing (the root holds it all; only the nested entry goes) | 58 |
| - of which the copies name a different Series or Number (the root's stay) | 65 |
| Held (see below) | 1 |

### Nested values the merge never copies (values / archives)

| Rule | Values | Archives |
|---|---:|---:|
| PageCount never copied | 250 | 250 |
| nested date never copied | 224 | 140 |
| Volume is a year | 83 | 83 |
| same tag in another letter case | 40 | 40 |

Fields filled in all: 787. Nested values dropped: 1749, in 355 archives (each saved to the apply's `dropped-nested-values.csv`, and every removed nested copy whole to `removed-nested-copies.jsonl`, before its backup is deleted). Backups: one at a time, deleted after verification; the largest archive is 4.70 GB.

Nested "None" values (blank): {'Number': 13} in the merge set; {'Number': 4} in nested-only copies (Part 1 reads those as blank too).

### Fields filled, per type (archives)

| Field | Archives |
|---|---:|
| Summary | 154 |
| Genre | 130 |
| ScanInformation | 100 |
| LanguageISO | 80 |
| Pages | 76 |
| Title | 48 |
| Writer | 32 |
| Publisher | 29 |
| writer | 29 |
| Penciller | 26 |
| Issue | 22 |
| Web | 14 |
| Artist | 12 |
| CoverArtist | 11 |
| Colorist | 6 |
| AgeRating | 4 |
| Number | 4 |
| Notes | 3 |
| Inker | 3 |
| Volume | 1 |
| Letterer | 1 |
| Format | 1 |
| Imprint | 1 |

### Nested values dropped, per type

| Field | Why | Archives |
|---|---|---:|
| Notes | root wins | 326 |
| PageCount | PageCount never copied | 250 |
| Web | root wins | 209 |
| Publisher | root wins | 172 |
| Series | root wins | 125 |
| Summary | root wins | 117 |
| Month | nested date never copied | 109 |
| Volume | Volume is a year | 83 |
| Day | nested date never copied | 68 |
| Year | nested date never copied | 47 |
| Genre | root wins | 42 |
| writer | same tag in another letter case | 40 |
| LanguageISO | root wins | 36 |
| Penciller | root wins | 33 |
| Writer | root wins | 30 |
| ScanInformation | root wins | 22 |
| Title | root wins | 20 |
| CoverArtist | root wins | 13 |
| AgeRating | root wins | 3 |
| Number | root wins | 2 |
| Colorist | root wins | 1 |
| Pages | root wins | 1 |

## ZIP order (YACReader reads the first ComicInfo.xml in ZIP order, at any depth)

| Layout | First copy in ZIP order | Archives |
|---|---|---:|
| Root + one nested (this merge) | nested | 356 |
| Root + one nested (this merge) | root | 1 |
| Root + several nested (not planned) | root | 1 |

Merge set: the root copy is the last entry of the archive in 356 of 357 (the app always writes its copy last).
Central-directory order and local-header order disagree on the first copy in 0 archive(s).

## Merged although the copies name a different Series or Number (the root's stay)

- `!!GraphicNovels_oneshots\Cheer Up! Love and Pompoms (2021) (Digital) (Relic-Empire).cbz`: Series named differently; root: Cheer Up! Love and Pompoms #1, 2021-8-16; nested: Cheer Up #-.
- `!!GraphicNovels_oneshots\Macbeth - A Tale of Horror (2023) (Digital) (XRA-Empire).cbz`: Series named differently; root: Macbeth: A Tale of Horror #1, 2023-10-1; nested: Macbeth #-.
- `!!GraphicNovels_oneshots\Mawrth Valliis OGN (2021) (Digital) (XRA-Empire).cbz`: Series named differently; root: Mawrth Valliis #1, 2021-7-25; nested: Mawrth Valliis OGN #-.
- `!!GraphicNovels_oneshots\Parachute Kids (2023) (Digital) (XRA-Empire).cbz`: Series named differently; root: Parachute Kids #-, no date; nested: Parachute Kids: A Graphic Novel #-.
- `!!GraphicNovels_oneshots\Saints - The Book of Blaise (2016) (Digital) (XRA-Empire).cbz`: Series named differently; root: Saints: The Book of Blaise #1, 2016-9-30; nested: Saints #-.
- `!!GraphicNovels_oneshots\Straight On Till Morning - A Twisted Tale Graphic Novel (2024) (GreenGiant-DCP).cbz`: Series named differently; root: Straight on Till Morning: A Twisted Tale Graphic Novel #-, 2024-6; nested: Straight On Till Morning #-.
- `!!GraphicNovels_oneshots\The Cartoonists Club (2025) (Digital) (XRA-Empire).cbz`: Series named differently; root: The Cartoonists Club #-, 2025-4; nested: The Cartoonists Club: A Graphic Novel #-.
- `!!GraphicNovels_oneshots\The Fall of the House of Usher (2023) (Ablaze) (Digital-Empire).cbz`: Series named differently; root: The Fall of the House of Usher #-, no date; nested: The Fall Of The House Of Usher: A Graphic Novel #-.
- `!DC\Harley Quinn\Harley Quinn - Uncovered\Harley Quinn - Uncovered 001 (2023) (Digital) (Walkabout-DCP).cbz`: Series named differently; root: Harley Quinn - Uncovered #1, 2023-2-01; nested: Harley Quinn #1.
- `!Marvel Universe\Betsy Braddock - Captain Britain (2024) (Digital) (Shan-Empire).cbz`: Series named differently; root: Betsy Braddock: Captain Britain #1, 2024-01-31; nested: Captain Britain: Betsy Braddock #None.
- `!Marvel Universe\Lockjaw\Lockjaw - Who's A Good Boy 001 (2018) (digital) (Marika-Empire).cbz`: Series named differently; root: Lockjaw - Who's A Good Boy #1, no date; nested: Lockjaw: Who's A Good Boy?: 1 #-.
- `!Titan Comics\Tank Girl\21st Century Tank Girl (2015) (Digital) (XRA-Empire).cbz`: Series named differently; root: 21st Century Tank Girl #-, 2015-12; nested: Tank Girl #-.
- `!Titan Comics\Tank Girl\Dirty Old Tank Girl (2019) (Digital) (XRA-Empire).cbz`: Series named differently; root: Dirty Old Tank Girl #-, 2019-3; nested: Tank Girl #-.
- `!Zenescope\Grimm Tales of Terror\Grimm Tales of Terror Quarterly\Grimm Tales of Terror Quarterly - 2023 Halloween Special (2023) (digital) ( Li'l-Empire) (HD-Upscaled).cbz`: Series named differently; root: Grimm Tales of Terror Quarterly: 2023 Halloween Special #-, 2023; nested: Tales of Terror Quarterly: 2023 Halloween Special #None.
- `Alexandro Jodorowsky\The Incal\The Incal - Kill Wolfhead (Humanoids 2023) (webrip) (MagicMan-DCP).cbz`: Series named differently; root: The Incal: Kill Wolfhead #-, 2023-10; nested: The Incal: Kill Wolfhead (2023) v01 #-.
- `Alien\Alien 2021 Marvel\Alien 003 (2021) (Digital) (F) (Bean-Empire).cbz`: Series named differently; root: Alien #3, 2021-07-01; nested: Alien (2021-) #3.
- `Alien\Alien 2021 Marvel\Alien 006 (2021) (Digital) (Relic-Empire).cbz`: Series named differently; root: Alien #6, 2021-10-01; nested: Alien (2021-) #6.
- `Alien\Alien 2021 Marvel\Alien 007 (2021) (Digital) (Relic-Empire).cbz`: Series named differently; root: Alien #7, 2021-11-01; nested: Alien (2021-) #7.
- `Alien\Alien 2021 Marvel\Alien 008 (2022) (Digital) (Relic-Empire).cbz`: Series named differently; root: Alien #8, 2022-01-01; nested: Alien (2021-) #8.
- `Alien\Alien 2021 Marvel\Alien 009 (2022) (Digital) (Relic-Empire).cbz`: Series named differently; root: Alien #9, 2022-04-01; nested: Alien (2021-) #9.
- `Amazonia\Amazonia 01 (Cinebook 2024) (webrip) (MagicMan-DCP).cbz`: Series named differently; root: Amazonia #1, 2024-8; nested: Amazonia (2017), Episode 1 #-.
- `Archie Comics\Chilling Aventures Presents\Chilling Adventures\Chilling Adventures Presents... Truth or Dare (OS) (2024) (Forsythe-DCP).cbz`: Series named differently; root: Chilling Adventures Presents... Truth or Dare #1, 2024-09-01; nested: Chilling Adventures Presents... Truth or Dare (One Shot) #-.
- `Archie Comics\Kardak the Mystic\Kardak the Mystic (OS) (2024) (Forsythe-DCP).cbz`: Series named differently; root: Kardak the Mystic #-, no date; nested: Kardak the Mystic (One Shot) #-.
- `Archie Comics\Sabrina the Teenage Witch\The Wicked Trinity (One Shot) (2024) (Forsythe-DCP).cbz`: Series named differently; root: The Wicked Trinity #1, 2024-08-01; nested: The Wicked Trinity (One Shot) #-.
- `Black Magick\Black Magick - The First Book of Shadows (2019) (Digital-Empire).cbz`: Series named differently; root: Black Magick: The First Book of Shadows #-, 2019-5; nested: Black Magick #-.
- `CONAN\MARVEL (New)\[2019 - 2019] Age Of Conan\Belit - Queen Of The Black Coast [2019]\Age Of Conan - Belit - Queen Of The Black Coast 01.cbz`: Number named differently; root: Age Of Conan - Belit - Queen Of The Black Coast #1, no date; nested: Age Of Conan: Belit, Queen Of The Black Coast #01 (of 05).
- `CONAN\MARVEL (New)\[2019 - 2019] Age Of Conan\Belit - Queen Of The Black Coast [2019]\Age Of Conan - Belit - Queen Of The Black Coast 02.cbz`: Number named differently; root: Age Of Conan - Belit - Queen Of The Black Coast #2, no date; nested: Age Of Conan: Belit, Queen Of The Black Coast #02 (of 05).
- `Canto\Canto - The Hollow Men (2024) (Digital-Empire).cbz`: Series named differently; root: Canto - The Hollow Men #-, no date; nested: Canto Volume 2: The Hollow Men #-.
- `Canto\Canto v03 - Tales of the Unnamed World (2024) (Digital-Empire).cbz`: Series named differently; root: Canto #3, 2024-7; nested: Canto Volume 3: Tales of the Unnamed World #-.
- `Daphne Byrne\Daphne Byrne (2020) (digital) (Dr.Vink).cbz`: Series named differently; root: Daphne Byrne #-, no date; nested: Daphne Byrne (2020-) #1.
- `Dark Souls\Willow King\Dark Souls - The Willow King 002 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: Dark Souls - The Willow King #2, 2024-3; nested: Dark Souls: The Willow King (2024) #2.
- `Dark Souls\Willow King\Dark Souls - The Willow King 003 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: Dark Souls - The Willow King #3, 2024-5; nested: Dark Souls: The Willow King (2024) #3.
- `Dollhouse Family\The Dollhouse Family (2020) (digital) (Dr.Vink).cbz`: Series named differently; root: The Dollhouse Family #-, 2020-12; nested: The Dollhouse Family (2019-) #1.
- `Dune\House Corrino\Dune - House Corrino 002 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: Dune: House Corrino #2, 2024-4-24; nested: Dune: House Corrino (2024) #2.
- `Dune\House Corrino\Dune - House Corrino 003 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: Dune: House Corrino #3, 2024-5-29; nested: Dune: House Corrino (2024) #3.
- `Eros - Psyche\Eros - Psyche (2021) (Digital) (XRA-Empire).cbz`: Series named differently; root: Eros - Psyche #-, no date; nested: Maria Llovet’s Eros/Psyche #-.
- `Expanse\Dragon Tooth\The Expanse - Dragon Tooth 005 (2023) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: The Expanse: Dragon Tooth #5, 2023-09-01; nested: The Expanse: Dragon Tooth (2023) #5.
- `Expanse\Dragon Tooth\The Expanse - Dragon Tooth 006 (2023) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: The Expanse - Dragon Tooth #6, 2023-10-01; nested: The Expanse: Dragon Tooth (2023) #6.
- `Firefly\Firefly Blue Sun\Firefly - Blue Sun Rising v01 (2021) (Digital-Empire).cbz`: Series named differently; root: Firefly: Blue Sun Rising #1, 2021-3; nested: Firefly #-.
- `Firefly\Firefly Blue Sun\Firefly - Blue Sun Rising v02 (2021) (Digital-Empire).cbz`: Series named differently; root: Firefly: Blue Sun Rising #2, 2021-5; nested: Firefly #-.
- `Godzilla\Godzilla - Kingdom of Monsters\Godzilla - Kingdom of Monsters v01 (2011) (digital) (Dr.Vink).cbz`: Series named differently; root: Godzilla: Kingdom of Monsters #1, 2011-9; nested: Godzilla: Kingdom of Monsters (2011-2012) #1.
- `Godzilla\Godzilla - Kingdom of Monsters\Godzilla - Kingdom of Monsters v02 (2012) (digital) (Dr.Vink).cbz`: Series named differently; root: Godzilla: Kingdom of Monsters #2, 2012-1; nested: Godzilla: Kingdom of Monsters (2011-2012) #2.
- `Godzilla\Godzilla - Kingdom of Monsters\Godzilla - Kingdom of Monsters v03 (2012) (digital) (Dr.Vink).cbz`: Series named differently; root: Godzilla: Kingdom of Monsters #3, 2012-5; nested: Godzilla: Kingdom of Monsters (2011-2012) #3.
- `Gun Honey\Gun Honey Collision Course\Gun Honey - Collision Course 001 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: Gun Honey - Collision Course #1, 2024-06-01; nested: Gun Honey: Collision Course (2024) #1.
- `Gun Honey\Gun Honey Collision Course\Gun Honey - Collision Course 002 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: Gun Honey - Collision Course #2, 2024-07-01; nested: Gun Honey: Collision Course (2024) #2.
- `Gun Honey\Gun Honey Collision Course\Gun Honey - Collision Course 003 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: Gun Honey - Collision Course #3, 2024-08-01; nested: Gun Honey: Collision Course (2024) #3.
- `Gun Honey\Gun Honey Collision Course\Gun Honey - Collision Course 004 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: Gun Honey - Collision Course #4, 2024-09-01; nested: Gun Honey: Collision Course (2024) #4.
- `Gun Honey\Gun Honey Heat Seeker\Gun Honey - Heat Seeker 003 (2023) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: Gun Honey - Heat Seeker #3, no date; nested: Gun Honey: Heat Seeker (2023) #3.
- `Gun Honey\Heat Seeker - A Gun Honey Series\Heat Seeker - A Gun Honey Series v01 (2024) (Digital) (XRA-Empire).cbz`: Series named differently; root: Heat Seeker: A Gun Honey Series #1, 2024-2; nested: Heat Seeker #-.
- `Gun Honey\Heat Seeker - A Gun Honey Series\Heat Seeker Combustion\Heat Seeker - Combustion - A Gun Honey Series 002 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: Heat Seeker: Combustion: A Gun Honey Series #2, 2024-12; nested: Heat Seeker: Combustion (2024) #2.
- `Love And Rockets\Love and Rockets 014 (2023) (digital) ( Li'l-Empire) (HD-Upscaled).cbz`: Series named differently; root: Love and Rockets #14, 2023-10-01; nested: Love and Rockets VOL. IV #14.
- `Magic Order\The Magic Order v01 (2024) (Digital) (XRA-Empire).cbz`: Series named differently; root: The Magic Order #1, 2024-7; nested: The Magic Order Volume 1 #-.
- `Magic Order\The Magic Order v02 (2024) (Digital) (XRA-Empire).cbz`: Series named differently; root: The Magic Order #2, 2024-8; nested: The Magic Order Volume 2 #-.
- `Masters of the Universe\He-Man and the Masters of the Universe\He-Man and the Masters of the Universe v02 - Origins of Eternia (2014) (Digital) (Bean-Empire).cbz`: Series named differently; root: He-Man and the Masters of the Universe #2, 2014-5; nested: Masters of the Universe #-.
- `Night Eaters v01-03 (2022-2025)\The Night Eaters v01 - She Eats the Night (2022) (Digital) (XRA-Empire).cbz`: Series named differently; root: The Night Eaters #1, 2022-10; nested: The Night Eaters: She Eats the Night #-.
- `Plunge\Plunge (2020) (digital) (Son of Ultron-Empire) (Fan Made TPB).cbz`: Series named differently; root: Plunge #-, no date; nested: Plunge (2020) #1.
- `Power Fantasy\Power Fantasy v02 (2025) (Digital) (EricJGriffin-Empire).cbz`: Series named differently; root: The Power Fantasy #2, 2025-9-01; nested: Power Fantasy #-.
- `Renaissance\The Resistance v01 (2020) (digital) (Dr.Vink).cbz`: Series named differently; root: The Resistance #1, 2020-10; nested: The Resistance (2020) #1.
- `Robert Silverberg's Belzagor\Robert Silverberg's Belzagor (Humanoids 2024) (webrip) (MagicMan-DCP).cbz`: Series named differently; root: Robert Silverberg's Belzagor #1, 2024-05-01; nested: Robert Silverberg's Belzagor Digital Omnibus #-.
- `S.I.R\S.I.R. 002 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: S.I.R. #2, 2024-09-01; nested: S.I.R. (2024) #2.
- `S.I.R\S.I.R. 003 (2024) (Digital Rip) (Hourman-DCP).cbz`: Series named differently; root: S.I.R. #3, 2024-10-01; nested: S.I.R. (2024) #3.
- `Sparks\Sparks v01 - Portals (2024) (Digital-Empire).cbz`: Series named differently; root: Sparks #1, 2024-7; nested: Sparks Volume 1: Portals #-.
- `Star Wars\High Republic\The High Republic Adventures\Pathfinders\Star Wars - The High Republic Adventures - Pathfinders 004 (2026) (Digital) (Kileko-Empire).cbz`: Series named differently; root: Star Wars - The High Republic Adventures - Pathfinders #4, 2026-08-01; nested: Star Wars: The High Republic Adventures #4.
- `Star Wars\Star Wars Epic Collection\Star Wars Modern Era Epic Collection v01 - Skywalker Strikes (2024) (Digital) (Kileko-Empire).cbz`: Series named differently; root: Star Wars Modern Era Epic Collection #1, 2024-7; nested: Star Wars Modern Era Epic Collection: Skywalker Strikes #-.
- `Step by Bloody Step\Step by Bloody Step - A Wordless Fantasy (2022) (Digital) (XRA-Empire).cbz`: Series named differently; root: Step by Bloody Step: A Wordless Fantasy #-, 2022-8; nested: Step by Bloody Step #-.

## Held archives

- `!Titan Comics\Ms. Tree (2019-)\Ms. Tree v04 - Deadline (2022) (Digital) (XRA-Empire).cbz`: nested copy unreadable: mismatched tag: line 21, column 2; root: Ms. Tree #4, 2022-10; nested: (unreadable) #(unreadable).

## Other oddities

- `!DC\DC Finest\DC Finest - The Doom Patrol - The Death of the Doom Patrol! (2026) (hybrid) (Marika-Empire).cbz`: Root + several nested (not planned)

## Per archive (merge set)

Fields filled, nested values dropped, the nested entry removed, and which copy YACReader reads today.

| Archive | Outcome | Fields filled | Nested values dropped | Nested entry removed | YACReader reads today |
|---|---|---|---|---|---|
| !!GraphicNovels_oneshots\A Land Called Tarot (2017) (Digital) (XRA-Empire).cbz | merge | Genre, LanguageISO | Web, Notes, PageCount | A Land Called Tarot (2017) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Barda (2024) (Digital Rip) (Hourman-DCP).cbz | merge | - | Summary | Barda (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Beyond the Sea (Europe Comics 2024) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO, Summary | Notes | Beyond the Sea (Europe Comics 2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Black Fire (2011) (Digital) (XRA-Empire).cbz | merge | Genre, LanguageISO | Title, Web, Notes, ScanInformation, Writer, Penciller | Black Fire (2011) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Blankets (2003) (Digital) (XRA-Empire).cbz | merge | Notes, LanguageISO | Web, Summary, Publisher, Year | Blankets (2003) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Breathers (2023) (Digital) (XRA-Empire).cbz | merge | LanguageISO | Web, Summary, Notes, Publisher, ScanInformation | Breathers (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Brownstone (2024) (Digital) (XRA-Empire).cbz | merge | LanguageISO | Summary, Notes, writer | Brownstone (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Cheer Up! Love and Pompoms (2021) (Digital) (Relic-Empire).cbz | merge | Genre, LanguageISO, Pages | Title, Series, Web, Notes, Day | Cheer Up! Love and Pompoms (2021) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Dandelion (Image 2024) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO | Summary, Publisher, Notes | Dandelion (Image 2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Dying is Easy (2020) (Digital) (Relic-Empire).cbz | merge | Genre, LanguageISO, Pages | Series, Web, Notes, Publisher, Month, Day | Dying is Easy (2020) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Eden (Humanoids 2024) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO | Summary, Notes | Eden (Humanoids 2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Eerie Tales from the School of Screams (2023) (Digital) (XRA-Empire).cbz | merge | Title, Summary, Genre, LanguageISO, Penciller | Web, Notes, Publisher, PageCount, ScanInformation, Day | Eerie Tales from the School of Screams (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Fairest of All - A Villains Graphic Novel (2023) (GreenGiant-DCP).cbz | merge | - | Summary, Publisher | Fairest of All - A Villains Graphic Novel (023) (GreenGiant-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Gamerville (2024) (Digital-Empire).cbz | merge | LanguageISO | Notes, writer | Gamerville (2024) (Digital-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Garlic and the Vampire (2021) (digital) (Dr.Vink).cbz | merge | Genre, LanguageISO, Artist | Title, Web, Summary, Notes, Publisher, PageCount, ScanInformation | Garlic and the Vampire (2021) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Graveneye (2021) (Digital) (XRA-Empire).cbz | merge | Web, Summary, Publisher, Genre, LanguageISO | Notes, PageCount | Graveneye (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Gurvan - A Dream of Earth (Humanoids 2023) (webrip) (MagicMan-DCP).cbz | merge | Summary | - | Gurvan - A Dream of Earth (Humanoids 2023) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Holler (2024) (Digital) (XRA-Empire).cbz | merge | writer | PageCount, Notes | Holler (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Indiana (Europe Comics 2023) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO, Summary, Publisher | Notes | Indiana (Europe Comics 2023) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Kalevala - The Graphic Novel (2024) (Digital) (XRA-Empire).cbz | merge | writer | Publisher, PageCount, Notes | Kalevala - The Graphic Novel (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Loud - Stories to Make Your Voice Heard (2024) (Digital-Empire).cbz | merge | LanguageISO | Notes, writer | Loud - Stories to Make Your Voice Heard (2024) (Digital-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Luna (2021) (Digital) (XRA-Empire).cbz | merge | Title, Genre, Writer, Penciller | Web, Notes, ScanInformation | Luna (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Macbeth - A Tale of Horror (2023) (Digital) (XRA-Empire).cbz | merge | - | Series, Web, Summary, Notes, Publisher, LanguageISO, ScanInformation, Month | Macbeth - A Tale of Horror (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Man and Superwoman (Europe Comics 2024) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO | Summary, Notes | Man and Superwoman (Europe Comics 2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Match Point! (2023) (Digital) (XRA-Empire).cbz | merge | Publisher, LanguageISO, writer | PageCount, Notes, Month, Year | Match Point! (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Mawrth Valliis OGN (2021) (Digital) (XRA-Empire).cbz | merge | - | Series, Web, Summary, Notes, Genre, ScanInformation, Day | Mawrth Valliis OGN (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Mooncakes - Collector's Edition (2021) (Digital) (XRA-Empire).cbz | merge | LanguageISO | Summary, Notes, writer | Mooncakes - Collector's Edition (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Mountainhead (2021) (Digital) (Relic-Empire).cbz | merge | Genre, LanguageISO, Pages | Web, Summary, Notes, Publisher, Year, Month, Day | Mountainhead (2021) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\New Masters (2022) (Digital) (XRA-Empire).cbz | merge | Genre, LanguageISO | Title, Web, Summary, Notes, Publisher, ScanInformation, Penciller, CoverArtist | New Masters (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\On the Way (2023) (Digital) (XRA-Empire).cbz | merge | - | Series, Publisher, Summary, Notes, writer | On the Way (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\One Hundred Tales (2023) (Digital) (XRA-Empire).cbz | merge | Title, Genre, ScanInformation, Writer, Penciller | Web, Notes, Publisher | One Hundred Tales (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Parachute Kids (2023) (Digital) (XRA-Empire).cbz | merge | Publisher, LanguageISO, Summary, writer | Series, PageCount, Notes, Month, Year | Parachute Kids (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Princess Princess Ever After (2016) (Digital) (Relic-Empire).cbz | merge | Genre, LanguageISO, Pages | Web, Summary, Notes, Day, Writer, Penciller, Colorist | Princess Princess Ever After (2016) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Roaming (2023) (sd Digital Rip) (Hourman-DCP).cbz | merge | LanguageISO | Summary, Notes | Roaming  (2023) (sd Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Saints - The Book of Blaise (2016) (Digital) (XRA-Empire).cbz | merge | Genre, LanguageISO | Title, Series, Web, Summary, Notes, PageCount | Saints - The Book of Blaise (2016) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Second Chances (2022) (Digital) (XRA-Empire).cbz | merge | Title, Genre, LanguageISO | Web, Notes, ScanInformation | Second Chances (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Seoul Before Sunrise (Humanoids 2024) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO, Summary | Publisher, Notes | Seoul Before Sunrise (Humanoids 2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Sheets - Collector's Edition (2021) (Digital-Empire).cbz | merge | LanguageISO | Summary, Notes, writer | Sheets - Collector's Edition (2021) (Digital-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Spectro (2022) (Digital) (XRA-Empire).cbz | merge | Genre, LanguageISO | Web, Summary, Notes, Publisher, ScanInformation, Day, CoverArtist | Spectro (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Squire (2022) (Digital) (XRA-Empire).cbz | merge | Title, Genre, LanguageISO, Writer, Penciller | Web, Summary, Notes, ScanInformation, Day | Squire (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Station (2008) (Digital) (XRA-Empire).cbz | merge | Title, Genre, Writer, Penciller | Web, Notes, ScanInformation | Station (2008) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Straight On Till Morning - A Twisted Tale Graphic Novel (2024) (GreenGiant-DCP).cbz | merge | - | Series, Summary, Publisher, Notes | Straight On Till Morning - A Twisted Tale Graphic Novel (2024) (GreenGiant-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Supper Club (2022) (Digital) (XRA-Empire).cbz | merge | Genre, LanguageISO | Title, Summary, Web, Notes, ScanInformation | Supper Club (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\The Cartoonists Club (2025) (Digital) (XRA-Empire).cbz | merge | - | Series, Publisher, PageCount, Notes, writer | The Cartoonists Club (2025) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\The Dyatlov Pass Mystery (Europe Comics 2023) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO | Notes | The Dyatlov Pass Mystery (Europe Comics 2023) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\The Fall of the House of Usher (2023) (Ablaze) (Digital-Empire).cbz | merge | Publisher, LanguageISO, Summary, writer | Series, PageCount, Notes, Month, Year | The Fall of the House of Usher (2023) (Ablaze) (Digital-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\The Forest (2022) (Digital) (XRA-Empire).cbz | merge | Genre, LanguageISO | Web, Summary, Notes, ScanInformation, Day | The Forest (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\The Hobbit - A Graphic Novel (2024) (Digital Rip) (Hourman-DCP).cbz | merge | LanguageISO | Series, Summary, Publisher, Notes | The Hobbit - A Graphic Novel (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\The Man That Corrupted Hadleyburg (Humanoids 2023) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO, Summary | Publisher, Notes | The Man That Corrupted Hadleyburg (Humanoids 2023) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\The Marble Queen (2024) (Digital) (XRA-Empire).cbz | merge | - | Web, Summary, Notes, Publisher, LanguageISO, ScanInformation | The Marble Queen (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\The Missing Play (Europe Comics 2024) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO | Summary, Notes | The Missing Play (Europe Comics 2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\The Site (Europe Comics 2024) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO, Summary, Publisher | Notes | The Site (Europe Comics 2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\The War.cbz | merge | Title, Volume, Summary, Writer, Inker, Colorist, Letterer, CoverArtist, Format, Pages | Notes, Year, Publisher, PageCount | The War (Fan Edit)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\They Called Us Enemy - Expanded Edition (2020) (Digital) (XRA-Empire).cbz | merge | LanguageISO | Series, Publisher, Summary, Notes, writer | They Called Us Enemy - Expanded Edition (2020) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Through Clouds of Smoke - Freud's Final Days (Humanoids 2023) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO, Summary, Publisher | Notes | Through Clouds of Smoke - Freud's Final Days (Humanoids 2023) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Weeaboo (2021) (Digital) (XRA-Empire).cbz | merge | Web, Summary, Publisher, Genre, LanguageISO, ScanInformation, Writer, Penciller, Colorist, CoverArtist | Notes, PageCount, Year, Month, Day | Weeaboo (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Whistleblowers - Four Who Fought to Expose the Holocaust to America (2024) (Digital Rip) (Hourman-DCP).cbz | merge | LanguageISO | Series, Summary, Publisher, Notes | Whistleblowers - Four Who Fought to Expose the Holocaust to America (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| !!GraphicNovels_oneshots\Youth Group (2024) (Digital) (XRA-Empire).cbz | merge | LanguageISO, Summary, writer | Publisher, PageCount, Notes | Youth Group (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !DC\Birds of Prey\Birds of Prey 2023\Birds of Prey 005 (2024) (Digital) (Shan-Empire).cbz | merge | - | Web, Notes, Publisher, LanguageISO, Volume | Birds of Prey 005 (2024) (Digital) (Shan-Empire)/ComicInfo.xml | nested |
| !DC\Birds of Prey\Birds of Prey 2023\Birds of Prey 006 (2024) (Digital) (Shan-Empire).cbz | merge | - | Web, Summary, Notes, Publisher, LanguageISO, Volume | Birds of Prey 006 (2024) (Digital) (Shan-Empire)/ComicInfo.xml | nested |
| !DC\DC Horror\Sgt. Rock vs. The Army of the Dead\DC Horror Presents - Sgt. Rock vs. The Army of the Dead 03 (of 06) (2023) (Digital) (Walkabout-DCP).cbz | merge | ScanInformation | Series, Web, Summary, Notes, Publisher, Genre, PageCount | DC Horror Presents - Sgt. Rock vs. The Army of the Dead 003 (2023) (Digital) (Walkabout-DCP)/ComicInfo.xml | nested |
| !DC\Great Ten 001-009 (2010)\The Great Ten 001 (2010) (Digital) (Shadowcat-Empire).cbz | merge | - | Web, Volume, Summary, Notes, Publisher, Genre, PageCount | The Great Ten 001 (2010)/ComicInfo.xml | nested |
| !DC\Harley Quinn\Harley Quinn - Uncovered\Harley Quinn - Uncovered 001 (2023) (Digital) (Walkabout-DCP).cbz | merge | Title, ScanInformation | Series, Web, Notes, Publisher, Genre, PageCount | Harley Quinn - Uncovered 001 (2023) (Digital) (Walkabout-DCP)/ComicInfo.xml | nested |
| !DC\Harley Quinn\Harley Quinn 2022\Harley Quinn 024 (2023) (Digital) (Walkabout-DCP).cbz | merge | ScanInformation | Web, Summary, Notes, Publisher, Genre, PageCount | Harley Quinn 024 (2023) (Digital) (Walkabout-DCP)/ComicInfo.xml | nested |
| !DC\Lobo\Lobo-Deadman - The Brave and the Bald 001 (1995) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, LanguageISO | Series, Web, Volume, Notes, Publisher, PageCount | Lobo-Deadman - The Brave and the Bald 001 (1995)/ComicInfo.xml | nested |
| !DC\Lobo\Lobo-Demon - Hellowe'en 001 (1996) (Digital) (Shadowcat-Empire).cbz | merge | Summary | Series, Web, Volume, Notes, Publisher, Genre, PageCount | Lobo-Demon - Hellowe'en 001 (1996)/ComicInfo.xml | nested |
| !DC\Lobo\A Contract on Gawd\Lobo - A Contract on Gawd 001 (1994) (Digital) (Shadowcat-Empire).cbz | merge | - | Web, Volume, Summary, Notes, Publisher, Genre, PageCount | Lobo - A Contract on Gawd 001 (1994)/ComicInfo.xml | nested |
| !DC\Lobo\Lobo 061-064 + 1000000 + Annuals (1998-1999)\Lobo Annual 001 (1993) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | Lobo Annual 001 (1993)/ComicInfo.xml | nested |
| !DC\Lobo\Lobo Unbound\Lobo Unbound 001 (2003) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre | Web, Volume, Notes, Publisher, PageCount | Lobo Unbound 001 (2003)/ComicInfo.xml | nested |
| !DC\Lobo\Lobo's Back\Lobo's Back 001 (1992) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre | Web, Volume, Notes, Publisher, PageCount | Lobo's Back 001 (1992)/ComicInfo.xml | nested |
| !DC\Poison Ivy\Poison Ivy (2022 - 2025)\Poison Ivy 007 (2023) (Digital) (Walkabout-DCP).cbz | merge | Genre, ScanInformation | Web, Summary, Notes, Publisher, PageCount | Poison Ivy 007 (2023) (Digital) (Walkabout-DCP)/ComicInfo.xml | nested |
| !DC\Titans\Titans 2023-2025\Titans 006 (2024) (Digital) (Shan-Empire).cbz | merge | - | Web, Summary, Notes, Publisher, PageCount, LanguageISO, Volume, Month | Titans 006 (2024) (Digital) (Shan-Empire)/ComicInfo.xml | nested |
| !DC\Titans\Titans 2023-2025\Titans 007 (2024) (Digital) (Shan-Empire).cbz | merge | - | Web, Summary, Notes, Publisher, PageCount, LanguageISO, Volume, Month | Titans 007 (2024) (Digital) (Shan-Empire)/ComicInfo.xml | nested |
| !DC\Wonder Woman\Wonder Woman - The Adventures of Young Diana (2024) (webrip) (MagicMan-DCP).cbz | merge | - | Series, Summary | Wonder Woman - The Adventures of Young Diana (2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| !Disney\Anna and the Mystery of the Mountains (2023) (GreenGiant-DCP).cbz | merge | Summary | Publisher, Notes | Anna and the Mystery of the Mountains (2023) (GreenGiant-DCP)/ComicInfo.xml | nested |
| !Disney\Ariel and the Curse of the Sea Witches (2023) (GreenGiant-DCP).cbz | merge | Summary | Publisher | Ariel and the Curse of the Sea Witches (2023) (GreenGiant-DCP)/ComicInfo.xml | nested |
| !Disney\Mulan and the Palace of Secrets (2024) (GreenGiant-DCP).cbz | merge | Summary | Publisher, Notes | Mulan and the Palace of Secrets (2024) (GreenGiant-DCP)/ComicInfo.xml | nested |
| !Marvel Universe\Betsy Braddock - Captain Britain (2024) (Digital) (Shan-Empire).cbz | merge | Summary, LanguageISO | Series, Web, Notes, PageCount, Month | Betsy Braddock - Captain Britain (2024) (Digital) (Shan-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\G.O.D.S. (2024) (Digital) (EricJGriffin-Empire).cbz | merge | LanguageISO, Summary | Publisher, PageCount, Notes, writer, Month | G.O.D.S. (2024) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Imperial (2026) (Digital) (EricJGriffin-Empire).cbz | merge | writer | PageCount, Notes | Imperial (2026) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Mythos (2009) (Digital) (EricJGriffin-Empire).cbz | merge | Publisher, LanguageISO, Summary, writer | PageCount, Notes, Month, Year | Mythos (2009) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Aliens vs. Avengers\Aliens vs. Avengers (2025) (Digital) (EricJGriffin-Empire).cbz | merge | writer | PageCount, Notes | Aliens vs. Avengers (2025) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Bishop\Bishop 003 (2026) (Digital) (Kileko-Empire).cbz | merge | Summary, AgeRating | Volume, Month, Day, Penciller, Publisher, PageCount | Bishop 003(2026) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Captain Marvel\Captain Marvel - Starforce (2019) (Digital) (Relic-Empire).cbz | merge | Summary, Genre, Pages | Series, Web, Notes, PageCount | Captain Marvel - Starforce (2019) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Captain Marvel\Captain Marvel by Margaret Stohl (2024) (Digital) (Kileko-Empire).cbz | merge | Summary, writer | Publisher, PageCount, Notes | Captain Marvel by Margaret Stohl (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Doom\One World Under Doom (2026) (Digital) (EricJGriffin-Empire).cbz | merge | - | PageCount, Notes, writer, Month | One World Under Doom (2026) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Excalibur\Excalibur 004 (2004) (Digital) (Shadowcat-Empire).cbz | merge | - | Web, Volume, Summary, Notes, Genre, PageCount | Excalibur 004 (2004)/ComicInfo.xml | nested |
| !Marvel Universe\Excalibur\Excalibur 005 (2004) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, PageCount | Excalibur 005 (2004)/ComicInfo.xml | nested |
| !Marvel Universe\Excalibur\Excalibur 010 (2005) (Digital) (Shadowcat-Empire).cbz | merge | - | Web, Volume, Summary, Notes, Genre, PageCount | Excalibur 010 (2005)/ComicInfo.xml | nested |
| !Marvel Universe\Hellcat\Hellcat (2023) (Digital) (Shan-Empire).cbz | merge | Web, Summary, Publisher, LanguageISO | Notes, PageCount, Year, Month | Hellcat (2023) (Digital) (Shan-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Hellhunters\Hellhunters (2025) (Digital) (EricJGriffin-Empire).cbz | merge | writer | PageCount, Notes, Month | Hellhunters (2025) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Iron Man\Ultimate Comics Iron Man - Ultimate Collection (2010) (Digital) (EricJGriffin-Empire).cbz | merge | Summary, writer | Series, PageCount, Notes, Month | Ultimate Comics Iron Man - Ultimate Collection (2010) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Lockjaw\Lockjaw - Who's A Good Boy 001 (2018) (digital) (Marika-Empire).cbz | merge | Publisher, LanguageISO, Summary, writer | Series, PageCount, Notes, Month, Year | Lockjaw - Who's A Good Boy - 1 (2018)/ComicInfo.xml | nested |
| !Marvel Universe\Loki\Loki - The Liar (2023) (Digital) (Shan-Empire).cbz | merge | Summary | Series, Web, Notes, PageCount, LanguageISO, Year, Month | Loki - The Liar (2023) (Digital) (Shan-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\S.H.I.E.L.D\S.H.I.E.L.D. By Hickman & Weaver Omnibus (2025) (Digital) (EricJGriffin-Empire).cbz | merge | Summary, writer | Series, PageCount, Notes | S.H.I.E.L.D. By Hickman & Weaver Omnibus (2025) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Scarlet Witch\Vision & The Scarlet Witch\Vision & The Scarlet Witch - The Saga of Wanda and Vision (2021) (Digital) (XRA-Empire).cbz | merge | LanguageISO, Summary | Series, PageCount, Notes, writer, Month | Vision & The Scarlet Witch - The Saga of Wanda and Vision (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Secret Wars\Secret Wars By Jonathan Hickman Omnibus (2025) (Digital) (EricJGriffin-Empire).cbz | merge | LanguageISO | Series, PageCount, Notes, writer, Month | Secret Wars By Jonathan Hickman Omnibus (2025) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Spider-Verse\Edge of Spider-Verse\Edge of Spider-Verse (2023) (Digital) (Shan-Empire).cbz | merge | Summary | Series, Web, Notes, Publisher, PageCount, LanguageISO, Month | Edge of Spider-Verse (2023) (Digital) (Shan-Empire)/ComicInfo.xml | nested |
| !Marvel Universe\Wolverine\Wolverine (2026)\Wolverine 026 (2026) (Digital) (Kileko-Empire).cbz | merge | Summary, AgeRating | Volume, Month, Day, Publisher, PageCount | Wolverine 026 (2026) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| !Other Indie Publishers\Pixels of You (2022)\Pixels of You (2022) (Digital) (XRA-Empire).cbz | merge | Summary, Genre, ScanInformation, Writer, Penciller, Colorist | Web, Notes, Publisher, PageCount, Month, Day | Pixels of You (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Titan Comics\Afro Samurai (2022-)\Afro Samurai v01 (2022) (Digital) (XRA-Empire).cbz | merge | Title, Genre, ScanInformation | Web, Notes, Publisher, Writer | Afro Samurai v01 (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Titan Comics\Atom - The Beginning (2022-)\Atom - The Beginning v01 (2022) (Digital) (XRA-Empire).cbz | merge | Title, Genre, ScanInformation, Writer, Penciller | Series, Web, Notes | Atom - The Beginning v01 (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Titan Comics\Cutting Edge (2021)\Cutting Edge (2021) (Digital) (XRA-Empire).cbz | merge | Title, Web, Publisher, Genre, LanguageISO, ScanInformation, Writer, Penciller | Notes, Year | Cutting Edge (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Titan Comics\Ms. Tree (2019-)\Ms. Tree v01 (2019) (Digital) (XRA-Empire).cbz | merge | Genre, ScanInformation | Title, Web, Summary, Notes, Publisher, PageCount, Month, Day | Ms. Tree v01 (2019) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Titan Comics\Ms. Tree (2019-)\Ms. Tree v02 - Skeleton In The Closet (2020) (Digital) (XRA-Empire).cbz | merge | Summary, Genre, ScanInformation | Title, Web, Notes, Publisher, PageCount, Month, Day, Penciller | Ms. Tree v02 - Skeleton In The Closet (2020) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Titan Comics\Ms. Tree (2019-)\Ms. Tree v03 - The Cold Dish (2021) (Digital) (XRA-Empire).cbz | merge | Summary, Genre, ScanInformation | Title, Web, Notes, Publisher, PageCount, Month, Day, Writer, Penciller | Ms. Tree v03 - The Cold Dish (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Titan Comics\Ms. Tree (2019-)\Ms. Tree v04 - Deadline (2022) (Digital) (XRA-Empire).cbz | hold | - | - | - (held) | nested |
| !Titan Comics\Tank Girl\21st Century Tank Girl (2015) (Digital) (XRA-Empire).cbz | merge | Title, Genre, ScanInformation, Writer, Penciller | Series, Web, Notes | 21st Century Tank Girl (2015) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Titan Comics\Tank Girl\Dirty Old Tank Girl (2019) (Digital) (XRA-Empire).cbz | merge | Title, Summary, Genre | Series, Web, Notes, Publisher, PageCount | Dirty Old Tank Girl (2019) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Titan Comics\Tank Girl\Tank Girl - All Stars (2019) (Digital) (XRA-Empire).cbz | merge | Title, Summary, Genre | Series, Web, Notes, Publisher, PageCount | Tank Girl - All Stars (2019) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Titan Comics\The Junction (2022)\The Junction (2022) (Digital) (XRA-Empire).cbz | merge | Title, Genre, ScanInformation, Writer, Penciller | Web, Notes | The Junction (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| !Zenescope\Grimm Fairy Tales\Wonderland\Wonderland Annual\Wonderland Annual - Out of Time (2023) (digital) (Li'l-Empire) (HD-Upscaled).cbz | merge | - | Web, Notes, Publisher, PageCount, LanguageISO, Month | Wonderland Annual - Out of Time (2023) (digital) (Li'l-Empire)/ComicInfo.xml | nested |
| !Zenescope\Grimm Tales of Terror\Grimm Tales of Terror Quarterly\Grimm Tales of Terror Quarterly - 2023 Halloween Special (2023) (digital) ( Li'l-Empire) (HD-Upscaled).cbz | merge | Summary | Series, Web, Notes, Publisher, PageCount, LanguageISO, Month | Grimm Tales of Terror Quarterly - 2023 Halloween Special (2023) (digital) ( Li'l-Empire)/ComicInfo.xml | nested |
| Adventure Time\Adventure Time - The Bubbline College Special 001 (2025) (digital) (Bean-Empire).cbz | merge | Issue | Series, PageCount, Notes, writer | Adventure Time - The Bubbline College Special 001 (2025) (digital) (Bean-Empire)/ComicInfo.xml | nested |
| Adventure Time\Adventure Time (2025)\Adventure Time 001 (2025) (digital) (Bean-Empire).cbz | merge | Issue | PageCount, Notes, writer, Month | Adventure Time 001 (2025) (digital) (Bean-Empire)/ComicInfo.xml | nested |
| Adventure Time\Adventure Time (2025)\Adventure Time 006 (2025) (digital) (Bean-Empire).cbz | merge | Issue | PageCount, Notes, writer | Adventure Time 006 (2025) (digital) (Bean-Empire)/ComicInfo.xml | nested |
| Adventure Time\Adventure Time (2025)\Adventure Time 007 (2026) (digital) (Bean-Empire).cbz | merge | Issue, Publisher, LanguageISO, writer | PageCount, Notes, Month, Year | Adventure Time 007 (2026) (digital) (Bean-Empire)/ComicInfo.xml | nested |
| Adventure Time\Adventure Time (2025)\Adventure Time 008 (2026) (digital) (Bean-Empire).cbz | merge | Issue, Publisher, LanguageISO, writer | PageCount, Notes, Month, Year | Adventure Time 008 (2026) (digital) (Bean-Empire)/ComicInfo.xml | nested |
| Adventureman\Adventureman v01 - The End and Everything After (2020) (Digital) (XRA-Empire).cbz | merge | Summary, Genre | Title, Web, Notes, Publisher, PageCount | Adventureman v01 - The End and Everything After (2020) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Adventureman\Adventureman v02 - A Fairy Tale of New York (2022) (Digital) (XRA-Empire).cbz | merge | Genre, ScanInformation | Web, Notes, Publisher, Penciller | Adventureman v02 - A Fairy Tale of New York (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Alexandro Jodorowsky\The Incal\The Incal - Kill Wolfhead (Humanoids 2023) (webrip) (MagicMan-DCP).cbz | merge | Summary | Series, Notes | The Incal - Kill Wolfhead (Humanoids 2023) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| Alien\Alien by Shalvey & Broccardo v02 - Descendant (2024) (Digital) (Kileko-Empire).cbz | merge | Summary | Publisher, PageCount, Notes, writer | Alien by Shalvey & Broccardo v02 - Descendant (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Alien\Alien v03 - Icarus (2023) (Digital) (Kileko-Empire).cbz | merge | Summary, writer | Publisher, PageCount, Notes | Alien v03 - Icarus (2023) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Alien\Alien 2021 Marvel\Alien 003 (2021) (Digital) (F) (Bean-Empire).cbz | merge | ScanInformation, Pages | Series, Web, Summary, Notes, Genre, PageCount, Month, Writer | Alien 003 (2021) (Digital) (F) (Bean-Empire)/ComicInfo.xml | nested |
| Alien\Alien 2021 Marvel\Alien 005 (2021) (Digital) (Bean-Empire).cbz | merge | ScanInformation, Pages | Web, Summary, Notes, Genre, PageCount, Month, Writer | Alien 005 (2021) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| Alien\Alien 2021 Marvel\Alien 006 (2021) (Digital) (Relic-Empire).cbz | merge | Summary, CoverArtist, Pages | Series, Web, Notes, Genre, PageCount, Writer | Alien 006 (2021) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| Alien\Alien 2021 Marvel\Alien 007 (2021) (Digital) (Relic-Empire).cbz | merge | Pages | Series, Web, Summary, Notes, Genre, PageCount, Writer | Alien 007 (2021) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| Alien\Alien 2021 Marvel\Alien 008 (2022) (Digital) (Relic-Empire).cbz | merge | Summary, Pages | Series, Web, Notes, Genre, PageCount, Month, Writer | Alien 008 (2022) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| Alien\Alien 2021 Marvel\Alien 009 (2022) (Digital) (Relic-Empire).cbz | merge | Summary, CoverArtist, Pages | Series, Web, Notes, Genre, PageCount, Month, Writer | Alien 009 (2022) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| Alien\Aliens Epic Collection\Aliens Epic Collection - The Original Years v01 (2023) (Digital) (Kileko-Empire).cbz | merge | Summary, writer | Publisher, PageCount, Notes | Aliens Epic Collection - The Original Years v01 (2023) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Alien\King Killer\Alien - King Killer 005 (2026) (Digital) (Kileko-Empire).cbz | merge | Summary, Writer, Penciller, AgeRating | Series, Volume, Month, Day, Publisher, PageCount | Alien - King Killer 005(2026) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Amazonia\Amazonia 01 (Cinebook 2024) (webrip) (MagicMan-DCP).cbz | merge | Summary | Series, Notes | Amazonia 01 (Cinebook 2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| Amazonia\Amazonia 02 (Cinebook 2024) (webrip) (MagicMan-DCP).cbz | merge | Summary | Notes | Amazonia 02 (Cinebook 2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| Archie Comics\Chilling Aventures Presents\Chilling Adventures\Chilling Adventures Presents... Truth or Dare (OS) (2024) (Forsythe-DCP).cbz | merge | - | Series, Summary, Publisher, Notes | Chilling Adventures Presents... Truth or Dare (OS) (2024) (Forsythe-DCP)/ComicInfo.xml | nested |
| Archie Comics\Chilling Aventures Presents\Chilling Adventures\Chilling Adventures Presents\Chilling Adventures Presents - Pop's Chock'lit Shoppe of Horrors - Fresh Meat (2024) (Forsythe-DCP).cbz | merge | Summary | Series, Publisher, Notes | Chilling Adventures Presents - Pop's Chock'lit Shoppe of Horrors - Fresh Meat (2024) (Forsythe-DCP)/ComicInfo.xml | nested |
| Archie Comics\Kardak the Mystic\Kardak the Mystic (OS) (2024) (Forsythe-DCP).cbz | merge | LanguageISO, Summary, Publisher | Series, Notes | Kardak the Mystic (OS) (2024) (Forsythe-DCP)/ComicInfo.xml | nested |
| Archie Comics\Sabrina the Teenage Witch\The Wicked Trinity (One Shot) (2024) (Forsythe-DCP).cbz | merge | Summary | Series, Publisher, Notes | The Wicked Trinity (One Shot) (2024) (Forsythe-DCP)/ComicInfo.xml | nested |
| Babs\Babs v01 (2025) (Digital) (EricJGriffin-Empire).cbz | merge | - | PageCount, Notes, writer | Babs v01 (2025) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| Beware\Beware the Eye of Odin\Beware the Eye of Odin (2022) (Digital) (XRA-Empire).cbz | merge | Title, Summary, Genre, ScanInformation, Writer, Penciller | Web, Notes, Publisher, PageCount, Day | Beware the Eye of Odin (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Black Magick\Black Magick - The First Book of Shadows (2019) (Digital-Empire).cbz | merge | Title, Summary, Genre | Series, Web, Notes, Publisher, PageCount | Black Magick - The First Book of Shadows (2019) (Digital-Empire)/ComicInfo.xml | nested |
| Black Star\Black Star (2021) (Digital) (XRA-Empire).cbz | merge | Summary, writer | Publisher, PageCount, Notes, Month | Black Star (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Blood Stain\Blood Stain v04 (2023) (Digital) (XRA-Empire).cbz | merge | - | Summary, PageCount, Notes, writer | Blood Stain v04 (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Bolero\Bolero (2022) (Digital) (XRA-Empire).cbz | merge | Title, Genre, ScanInformation, Writer, Penciller | Web, Notes, Publisher | Bolero (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 001 (1980) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day, CoverArtist | King Conan 001 (1980) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 002 (1980) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Day, CoverArtist | King Conan 002 (1980) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 003 (1980) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day, Penciller | King Conan 003 (1980) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 004 (1980) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day | King Conan 004 (1980) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 005 (1981) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day, Penciller | King Conan 005 (1981) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 006 (1981) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Day, Penciller | King Conan 006 (1981) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 007 (1981) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day, Penciller | King Conan 007 (1981) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 008 (1981) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day, Penciller | King Conan 008 (1981) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 009 (1982) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day | King Conan 009 (1982) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 010 (1982) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day | King Conan 010 (1982) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 011 (1982) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day, Penciller | King Conan 011 (1982) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 012 (1982) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day, CoverArtist | King Conan 012 (1982) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 013 (1982) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day, CoverArtist | King Conan 013 (1982) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 014 (1983) (Digital) (Shadowcat-Empire).cbz | merge | Summary, ScanInformation, Pages | Web, Volume, Notes, Genre, PageCount, Year, Month, Day | King Conan 014 (1983) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 015 (1983) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day | King Conan 015 (1983) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 016 (1983) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day, CoverArtist | King Conan 016 (1983) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 017 (1983) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, PageCount, Year, Month, Day | King Conan 017 (1983) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 018 (1983) (Digital) (Shadowcat-Empire).cbz | merge | ScanInformation, Pages | Web, Volume, Notes, Genre, PageCount, Year, Month, Day, Penciller, CoverArtist | King Conan 018 (1983) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL\King Conan [1980-1989]\King Conan 019 (1983) (Digital) (Shadowcat-Empire).cbz | merge | ScanInformation, Pages | Web, Volume, Notes, Genre, PageCount, Year, Month, Day, CoverArtist | King Conan 019 (1983) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2019] Age Of Conan\Belit - Queen Of The Black Coast [2019]\Age Of Conan - Belit - Queen Of The Black Coast 01.cbz | merge | Web, Summary, Publisher, Genre, LanguageISO, ScanInformation, Writer, Penciller, CoverArtist, Pages | Series, Number, Volume, Notes, PageCount, Year, Month | Age Of Conan - Belit, Queen Of The Black Coast 01 (of 05) (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2019] Age Of Conan\Belit - Queen Of The Black Coast [2019]\Age Of Conan - Belit - Queen Of The Black Coast 02.cbz | merge | Web, Summary, Publisher, Genre, LanguageISO, ScanInformation, Writer, Penciller, CoverArtist, Pages | Series, Number, Volume, Notes, PageCount, Year, Month | Age Of Conan - Belit, Queen Of The Black Coast 02 (of 05) (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2019] The Savage Sword of Conan\Savage Sword Of Conan 05.cbz | merge | Genre, ScanInformation, Pages | Web, Volume, Summary, Notes, PageCount | Savage Sword of Conan 005 (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2019] The Savage Sword of Conan\Savage Sword of Conan 01.cbz | merge | Genre, ScanInformation | Series, Web, Volume, Summary, Notes, PageCount | Savage Sword Of Conan 001 (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2019] The Savage Sword of Conan\Savage Sword of Conan 02.cbz | merge | Genre, ScanInformation | Series, Web, Volume, Notes, PageCount | Savage Sword Of Conan 002 (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2019] The Savage Sword of Conan\Savage Sword of Conan 03.cbz | merge | Genre, ScanInformation, Pages | Series, Web, Volume, Summary, Notes, PageCount, Writer | Savage Sword of Conan 003 (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2019] The Savage Sword of Conan\Savage Sword of Conan 04.cbz | merge | Genre, ScanInformation, Pages | Series, Web, Volume, Summary, Notes, PageCount | Savage Sword Of Conan 004 (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2021] Conan The Barbarian\Conan the Barbarian 01.cbz | merge | ScanInformation, Pages | Series, Web, Volume, Summary, Notes, Penciller, CoverArtist, PageCount | Conan The Barbarian 001 (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2021] Conan The Barbarian\Conan the Barbarian 03.cbz | merge | ScanInformation | Series, Web, Volume, Summary, Notes, PageCount | Conan The Barbarian 003 (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2021] Conan The Barbarian\Conan the Barbarian 04.cbz | merge | Summary, ScanInformation | Series, Web, Volume, Notes, PageCount | Conan The Barbarian 004 (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2021] Conan The Barbarian\Conan the Barbarian 05.cbz | merge | ScanInformation, Pages | Series, Web, Volume, Summary, Notes, PageCount, Penciller, CoverArtist | Conan The Barbarian 005 (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| CONAN\MARVEL (New)\[2019 - 2021] Conan The Barbarian\Conan the Barbarian 06.cbz | merge | ScanInformation, Pages | Series, Web, Volume, Summary, Notes, PageCount, Penciller, CoverArtist | Conan the Barbarian 006 (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| Canto\Canto - The Hollow Men (2024) (Digital-Empire).cbz | merge | Publisher, LanguageISO, writer | Series, PageCount, Notes, Month, Year | Canto - The Hollow Men (2024) (Digital-Empire)/ComicInfo.xml | nested |
| Canto\Canto v03 - Tales of the Unnamed World (2024) (Digital-Empire).cbz | merge | writer | Series, PageCount, Notes | Canto v03 - Tales of the Unnamed World (2024) (Digital-Empire)/ComicInfo.xml | nested |
| Cowboy Wally Show (2003)(c)\The Cowboy Wally Show (2016) (Digital) (FatNerd).cbz | merge | Web, Summary, Publisher, Genre, LanguageISO, ScanInformation, Writer, Penciller, Pages | Notes, PageCount, Year, Month, Day | The Cowboy Wally Show (2016) (Digital) (FatNerd)/ComicInfo.xml | nested |
| Cull\The Cull 03 (of 05) (2023) (digital) (Li'l-Empire) (HD-Upscaled).cbz | merge | Summary | Web, Notes, Publisher, PageCount, LanguageISO, Month | The Cull 03 (of 05) (2023) (digital) (Li'l-Empire)/ComicInfo.xml | nested |
| Cyn\Cyn (Humanoids 2024) (webrip) (MagicMan-DCP).cbz | merge | - | Summary, Notes | Cyn (Humanoids 2024) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| Danger Street\Danger Street 001 (2023) (Digital) (Walkabout-DCP).cbz | merge | ScanInformation | Web, Summary, Notes, Publisher, Genre, PageCount | Danger Street 001 (2023) (Digital) (Walkabout-DCP)/ComicInfo.xml | nested |
| Daphne Byrne\Daphne Byrne (2020) (digital) (Dr.Vink).cbz | merge | Title, Number, Web, Summary, Publisher, Genre, LanguageISO, ScanInformation, Writer, Artist | Series, Notes, PageCount, Year | Daphne Byrne (2020) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| Dark Souls\Willow King\Dark Souls - The Willow King 002 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | Summary | Series, Notes | Dark Souls - The Willow King 002 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Dark Souls\Willow King\Dark Souls - The Willow King 003 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | Summary | Series, Notes | Dark Souls - The Willow King 003 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Darkling\Darkling 001 (2024) (OS) (Forsythe-DCP) (HD-Upscaled).cbz | merge | - | Summary, Publisher, Notes | Darkling 001 (2024) (OS) (Forsythe-DCP)/ComicInfo.xml | nested |
| Deadliest Bouquet\The Deadliest Bouquet (2023) (Digital) (XRA-Empire).cbz | merge | Title, ScanInformation | Web, Summary, Notes, Publisher, PageCount, Month, Day | The Deadliest Bouquet (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Department of Truth\The Department of Truth v01 - The End of the World (2021) (digital-Empire).cbz | merge | Summary, Genre | Web, Notes, Publisher, PageCount | The Department of Truth v01 - The End of the World (2021) (digital-Empire)/ComicInfo.xml | nested |
| Disciples\The Disciples (2016) (digital) (Dr.Vink).cbz | merge | Title, Number, Web, Summary, Publisher, Genre, LanguageISO, ScanInformation, Writer, Artist | Notes, PageCount, Year | The Disciples (2016) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| Dollhouse Family\The Dollhouse Family (2020) (digital) (Dr.Vink).cbz | merge | Title, Number, Summary, Genre, ScanInformation, Artist | Series, Web, Notes, Publisher, PageCount, Writer | The Dollhouse Family (2020) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| Druuna\Druuna 00 Anima (of 9) (2016)(2 covers)(GN)(digital)(cbf-dcp).cbz | merge | - | Pages | Druuna Vol.0 - Anima (2016)/ComicInfo.xml | root |
| Dune\House Corrino\Dune - House Corrino 002 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | - | Series, Summary, Publisher, Notes | Dune - House Corrino 002 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Dune\House Corrino\Dune - House Corrino 003 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | - | Series, Summary, Publisher, Notes | Dune - House Corrino 003 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Eat, and Love Yourself\Eat, and Love Yourself (2020) (Digital) (XRA-Empire).cbz | merge | Summary, Genre | Web, Notes, Publisher, PageCount | Eat, and Love Yourself (2020) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Elvira\Elvira's House of Mystery 01-11 + Annual (1986-1987)\Elvira's House of Mystery 001 (1986) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre | Web, Volume, Notes, Publisher, PageCount | Elvira's House of Mystery 001 (1986)/ComicInfo.xml | nested |
| Elvira\Elvira's House of Mystery 01-11 + Annual (1986-1987)\Elvira's House of Mystery 002 (1986) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre | Web, Volume, Notes, Publisher, PageCount | Elvira's House of Mystery 002 (1986)/ComicInfo.xml | nested |
| Enfield Gang Massacre\The Enfield Gang Massacre\The Enfield Gang Massacre 003 (2023) (Digital) (Li'l-Empire) (HD-Upscaled).cbz | merge | - | Web, Notes, Publisher, PageCount, LanguageISO, Month | The Enfield Gang Massacre 003 (2023) (Digital) (Li'l-Empire)/ComicInfo.xml | nested |
| Eros - Psyche\Eros - Psyche (2021) (Digital) (XRA-Empire).cbz | merge | Web, Summary, Publisher, LanguageISO, ScanInformation | Series, Notes, PageCount, Year, Month | Eros - Psyche (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Expanse\Dragon Tooth\The Expanse - Dragon Tooth 005 (2023) (Digital Rip) (Hourman-DCP).cbz | merge | - | Series, Summary, Publisher, Notes | The Expanse - Dragon Tooth 005 (2023) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Expanse\Dragon Tooth\The Expanse - Dragon Tooth 006 (2023) (Digital Rip) (Hourman-DCP).cbz | merge | - | Series, Summary, Notes | The Expanse - Dragon Tooth 006 (2023) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Firefly\Firefly - Keep Flying 001 (2022) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Series, Web, Summary, Notes, Genre, PageCount, Day, Penciller | Firefly - Keep Flying 001 (2022) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\Firefly Holiday Special 001 (2021) (Digital) (Pirate-Empire).cbz | merge | Web, Summary, Publisher, Genre, LanguageISO, ScanInformation, Writer, Penciller, Pages | Notes, PageCount, Year, Month, Day | Firefly Holiday Special 001 (2021) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\All New Firefly\All-New Firefly - Big Damn Finale 001 (2022) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Series, Web, Summary, Notes, Genre, PageCount, Day, Writer, Penciller | All-New Firefly - Big Damn Finale 001 (2022) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\All New Firefly\All-New Firefly 005 (2022) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Web, Summary, Notes, Genre, PageCount, Month, Day, Writer, Penciller | All-New Firefly 005 (2022) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\All New Firefly\All-New Firefly 006 (2022) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Web, Summary, Notes, Genre, PageCount, Month, Day, Writer | All-New Firefly 006 (2022) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\All New Firefly\All-New Firefly 007 (2022) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Web, Notes, Genre, PageCount, Month, Day, Writer | All-New Firefly 007 (2022) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\All New Firefly\All-New Firefly 008 (2022) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Web, Summary, Notes, Genre, PageCount, Month, Day, Writer | All-New Firefly 008 (2022) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\All New Firefly\All-New Firefly 009 (2022) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Web, Summary, Notes, Genre, PageCount, Day, Writer, Penciller | All-New Firefly 009 (2022) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\All New Firefly\All-New Firefly 010 (2022) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Web, Summary, Notes, Genre, PageCount, Day, Writer, Penciller | All-New Firefly 010 (2022) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\Firefly 20th Anniversary\Firefly - 20th Anniversary Special 001 (2022) (Digital) (Pirate-Empire).cbz | merge | Summary, ScanInformation, Pages | Series, Web, Notes, Genre, PageCount, Day, Writer, Penciller | Firefly - 20th Anniversary Special 001 (2022) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\Firefly Blue Sun\Firefly - Blue Sun Rising v01 (2021) (Digital-Empire).cbz | merge | Title, Summary, Genre | Series, Web, Notes, PageCount | Firefly - Blue Sun Rising v01 (2021) (Digital-Empire)/ComicInfo.xml | nested |
| Firefly\Firefly Blue Sun\Firefly - Blue Sun Rising v02 (2021) (Digital-Empire).cbz | merge | Title, Summary, Genre | Series, Web, Notes, PageCount | Firefly - Blue Sun Rising v02 (2021) (Digital-Empire)/ComicInfo.xml | nested |
| Firefly\Firefly – Brand New ‘Verse\Firefly - Brand New 'Verse 001 (2021) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Series, Web, Summary, Notes, Genre, PageCount, Day | Firefly - Brand New 'Verse 001 (2021) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\Firefly – Brand New ‘Verse\Firefly - Brand New 'Verse 002 (2021) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Series, Web, Summary, Notes, Genre, PageCount, Day | Firefly - Brand New 'Verse 002 (2021) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\Firefly – Brand New ‘Verse\Firefly - Brand New 'Verse 003 (2021) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Series, Web, Summary, Notes, Genre, PageCount, Day | Firefly - Brand New 'Verse 003 (2021) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\Firefly – Brand New ‘Verse\Firefly - Brand New 'Verse 004 (2021) (Digital) (Pirate-Empire).cbz | merge | Summary, ScanInformation, Pages | Series, Web, Notes, Genre, PageCount, Day | Firefly - Brand New 'Verse 004 (2021) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Firefly\Firefly – Brand New ‘Verse\Firefly - Brand New 'Verse 006 (2021) (Digital) (Pirate-Empire).cbz | merge | ScanInformation, Pages | Series, Web, Summary, Notes, Genre, PageCount, Day | Firefly - Brand New 'Verse 006 (2021) (Digital) (Pirate-Empire)/ComicInfo.xml | nested |
| Forged\The Forged 005 (2023) (Digital) (Li'l-Empire) (HD-Upscaled).cbz | merge | - | Web, Summary, Notes, Publisher, PageCount, LanguageISO, Month | The Forged 005 (2023) (Digital) (Li'l-Empire)/ComicInfo.xml | nested |
| Freeze\The Freeze v01 (2019) (digital) (Dr.Vink).cbz | merge | Notes, Genre, LanguageISO, Artist | Title, Web, Summary, Publisher, PageCount, ScanInformation | The Freeze v01 (2019) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| Gannibal\Gannibal v01 (2024) (Digital) (XRA-Empire).cbz | merge | LanguageISO | Web, Summary, PageCount, ScanInformation, Month | Gannibal v01 (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Gannibal\Gannibal v02 (2024) (Digital) (XRA-Empire).cbz | merge | LanguageISO | Web, Summary, PageCount, ScanInformation | Gannibal v02 (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Gannibal\Gannibal v03 (2024) (Digital) (XRA-Empire).cbz | merge | LanguageISO | Web, PageCount, ScanInformation | Gannibal v03 (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Godzilla\Godzilla - Kingdom of Monsters\Godzilla - Kingdom of Monsters v01 (2011) (digital) (Dr.Vink).cbz | merge | Title, Summary, Genre, ScanInformation, Writer, Artist | Series, Web, Notes, Publisher, PageCount | Godzilla - Kingdom of Monsters v01 (2011) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| Godzilla\Godzilla - Kingdom of Monsters\Godzilla - Kingdom of Monsters v02 (2012) (digital) (Dr.Vink).cbz | merge | Title, Summary, Genre, ScanInformation, Writer, Artist | Series, Web, Notes, Publisher, PageCount | Godzilla - Kingdom of Monsters v02 (2012) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| Godzilla\Godzilla - Kingdom of Monsters\Godzilla - Kingdom of Monsters v03 (2012) (digital) (Dr.Vink).cbz | merge | Title, Summary, Genre, ScanInformation, Writer, Artist | Series, Web, Notes, Publisher, PageCount | Godzilla - Kingdom of Monsters v03 (2012) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| Gun Honey\Gun Honey Collision Course\Gun Honey - Collision Course 001 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | Summary | Series, Publisher, Notes | Gun Honey - Collision Course 001 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Gun Honey\Gun Honey Collision Course\Gun Honey - Collision Course 002 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | Summary | Series, Publisher, Notes | Gun Honey - Collision Course 002 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Gun Honey\Gun Honey Collision Course\Gun Honey - Collision Course 003 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | Summary | Series, Publisher, Notes | Gun Honey - Collision Course 003 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Gun Honey\Gun Honey Collision Course\Gun Honey - Collision Course 004 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | Summary | Series, Publisher, Notes | Gun Honey - Collision Course 004 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Gun Honey\Gun Honey Heat Seeker\Gun Honey - Heat Seeker 003 (2023) (Digital Rip) (Hourman-DCP).cbz | merge | LanguageISO, Summary, Publisher | Series, Notes | Gun Honey - Heat Seeker 003 (2023) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Gun Honey\Heat Seeker - A Gun Honey Series\Heat Seeker - A Gun Honey Series v01 (2024) (Digital) (XRA-Empire).cbz | merge | Summary, ScanInformation | Series, Web, Notes, Publisher, PageCount, LanguageISO, Month | Heat Seeker - A Gun Honey Series v01 (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Gun Honey\Heat Seeker - A Gun Honey Series\Heat Seeker Combustion\Heat Seeker - Combustion - A Gun Honey Series 002 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | Summary | Series, Notes | Heat Seeker - Combustion - A Gun Honey Series 002 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 005 (2003) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 005 (2003) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 006 (2003) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 006 (2003) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 007 (2003) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 007 (2003) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 008 (2003) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 008 (2003) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 009 (2003) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 009 (2003) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 010 (2004) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 010 (2004) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 011 (2004) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 011 (2004) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 012 (2004) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 012 (2004) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 013 (2004) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 013 (2004) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 014 (2004) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 014 (2004) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 015 (2004) (Digital) (Shadowcat-Empire).cbz | merge | Genre | Web, Volume, Summary, Notes, Publisher, PageCount | H-E-R-O 015 (2004) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| H-E-R-O\H-E-R-O 016 (2004) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Genre | Web, Volume, Notes, Publisher, PageCount | H-E-R-O 016 (2004) (Digital) (Shadowcat-Empire)/ComicInfo.xml | nested |
| Halo\Blood Line\Halo_Blood Line #1.cbz | merge | Pages | PageCount | Halo Blood Line #1/ComicInfo.xml | nested |
| Halo\Blood Line\Halo_Blood Line #2.cbz | merge | Pages | PageCount | Halo Blood Line #2/ComicInfo.xml | nested |
| Halo\Blood Line\Halo_Blood Line #3.cbz | merge | Pages | PageCount | Halo Blood Line #3/ComicInfo.xml | nested |
| Halo\Blood Line\Halo_Blood Line #4.cbz | merge | Pages | PageCount | Halo Blood Line #4/ComicInfo.xml | nested |
| Hard Case Crime\Normandy Gold (2018) (Digital) (XRA-Empire).cbz | merge | Title, Summary, Genre, ScanInformation, Writer, Penciller, Colorist, CoverArtist | Web, Notes, Publisher, PageCount, Month, Day | Harmony Gold (2018) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Hard Case Crime\Peepland (2017) (Digital) (XRA-Empire).cbz | merge | Title, Summary, Genre | Web, Notes, Publisher, PageCount | Peepland (2017) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Ice Cream Man\Ice Cream Man 037 (2023) (Digital) ( Li'l-Empire) (HD-Upscaled).cbz | merge | - | Web, Summary, Notes, Publisher, PageCount, LanguageISO, Month | Ice Cream Man 037 (2023) (Digital) ( Li'l-Empire)/ComicInfo.xml | nested |
| Ice Cream Man\Ice Cream Man v10 - Imperious Wrecks (2024) (Digital) (XRA-Empire).cbz | merge | writer | PageCount, Notes | Ice Cream Man v10 - Imperious Wrecks (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Jim Henson's\Jim Henson's Labyrinth 2024\Jim Henson's Labyrinth 007.cbz | merge | Pages | PageCount | Jim Henson's Labyrinth #7/ComicInfo.xml | nested |
| Jim Henson's\Jim Henson's Labyrinth 2024\Jim Henson's Labyrinth 008.cbz | merge | Pages | PageCount | Jim Henson's Labyrinth #8/ComicInfo.xml | nested |
| KISS\KISS - Zombies (2021) (Digital) (XRA-Empire).cbz | merge | Title, Web, Publisher, Genre, LanguageISO, ScanInformation, Writer, Penciller | Series, Notes, Year | KISS - Zombies (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Kaptara\Kaptara Universal Truths\Kaptara - Universal Truths 002 (2023) (Digital) (Li'l-Empire) (HD-Upscaled).cbz | merge | Summary | Series, Web, Notes, Publisher, PageCount, LanguageISO, Month | Kaptara - Universal Truths 002 (2023) (Digital) (Li'l-Empire)/ComicInfo.xml | nested |
| Kaptara\Kaptara Universal Truths\Kaptara - Universal Truths 003 (2023) (Digital) ( Li'l-Empire) (HD-Upscaled).cbz | merge | - | Web, Summary, Notes, Publisher, PageCount, LanguageISO, Month | Kaptara - Universal Truths 003 (2023) (Digital) ( Li'l-Empire)/ComicInfo.xml | nested |
| Kill More\Kill More 002 (2023) (digital) ( Li'l-Empire) (HD-Upscaled).cbz | merge | - | Web, Summary, Notes, Publisher, PageCount, LanguageISO, Month | Kill More 002 (2023) (digital) ( Li'l-Empire)/ComicInfo.xml | nested |
| Kill Your\Kill Your Boyfriend\Kill Your Boyfriend 001 (1995) (Digital) (Shadowcat-Empire).cbz | merge | Summary, Imprint, Genre | Web, Volume, Notes, Publisher, PageCount | Kill Your Boyfriend 001 (1995)/ComicInfo.xml | nested |
| Killadelphia\Killadelphia v05 - There's No Place Like Home (2023) (Digital) (XRA-Empire).cbz | merge | Summary, ScanInformation | Web, Publisher, PageCount, LanguageISO | Killadelphia v05 - There's No Place Like Home (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| LIFE\Life is Strange\Life is Strange v05 - Coming Home (2021) (Digital-Empire).cbz | merge | Summary | Series, Web, Publisher, PageCount, LanguageISO, Year, Month | Life is Strange v05 - Coming Home (2021) (Digital-Empire)/ComicInfo.xml | nested |
| LIFE\Life is Strange\Settling Dust\Life is Strange v06 - Settling Dust (2022) (Digital-Empire).cbz | merge | Summary | Series, Web, Publisher, PageCount, LanguageISO, Month | Life is Strange v06 - Settling Dust (2022) (Digital-Empire)/ComicInfo.xml | nested |
| Laura and Other Stories\Laura and Other Stories (2022) (Digital) (XRA-Empire).cbz | merge | Title, Summary, ScanInformation, Writer | Web, Notes, Publisher, Genre, PageCount, Month, Day | Laura and Other Stories (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Lazarus\Lazarus Fallen\Lazarus - Fallen 001 (2025) (Digital) (Forever-Empire).cbz | merge | Issue | Series, PageCount, Notes, writer, Month | Lazarus - Fallen 001 (2025) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| Lazarus\Lazarus Fallen\Lazarus - Fallen 003 (2025) (Digital) (Forever-Empire).cbz | merge | Issue | Series, PageCount, Notes, writer, Month | Lazarus - Fallen 003 (2025) (Digital) (Forever-Empire)/ComicInfo.xml | nested |
| Lazarus\Lazarus Fallen\Lazarus - Fallen 004 (2025) (Digital) (Forever-Empire).cbz | merge | Issue | Series, PageCount, Notes, writer, Month | Lazarus - Fallen 004 (2025) (Digital) (Forever-Empire)/ComicInfo.xml | nested |
| Lazarus\Lazarus Fallen\Lazarus - Fallen 005 (2025) (Digital) (Forever-Empire).cbz | merge | Issue | Series, PageCount, Notes, writer | Lazarus - Fallen 005 (2025) (Digital) (Forever-Empire)/ComicInfo.xml | nested |
| Lazarus\Lazarus Fallen\Lazarus - Fallen 006 (2026) (Digital) (Forever-Empire).cbz | merge | Issue, LanguageISO, writer | Series, PageCount, Notes, Month, Year | Lazarus - Fallen 006 (2026) (Digital) (Forever-Empire)/ComicInfo.xml | nested |
| Local Man\Local Man 006 (2023) (Digital) (Li'l-Empire) (HD-Upscaled).cbz | merge | Summary | Web, Notes, Publisher, PageCount, LanguageISO, Month | Local Man 006 (2023) (Digital) (Li'l-Empire)/ComicInfo.xml | nested |
| Loneliness of the Abyss\The Loneliness of the Abyss (Europe Comics 2023) (webrip) (MagicMan-DCP).cbz | merge | LanguageISO, Summary, Publisher | Notes | The Loneliness of the Abyss (Europe Comics 2023) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| Lord of\Lord of Gore\Lord of Gore 004 (2018) (digital) (Minutemen-Excelsior).cbz | merge | Summary, Genre, Pages | Web, Notes, Publisher, PageCount | Lord of Gore 004 (2018) (digital) (Minutemen-Excelsior)/ComicInfo.xml | nested |
| Lord of\Lord of Gore\Lord of Gore 005 (2018) (digital) (Minutemen-Excelsior).cbz | merge | Summary, Genre, Pages | Web, Notes, Publisher, PageCount | Lord of Gore 005 (2018) (digital) (Minutemen-Excelsior)/ComicInfo.xml | nested |
| Love And Rockets\Love and Rockets 014 (2023) (digital) ( Li'l-Empire) (HD-Upscaled).cbz | merge | - | Series, Web, Summary, Notes, PageCount, LanguageISO, Month | Love and Rockets 014 (2023) (digital) ( Li'l-Empire)/ComicInfo.xml | nested |
| Magic Order\The Magic Order v01 (2024) (Digital) (XRA-Empire).cbz | merge | Summary, writer | Series, PageCount, Notes | The Magic Order v01 (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Magic Order\The Magic Order v02 (2024) (Digital) (XRA-Empire).cbz | merge | writer | Series, PageCount, Notes | The Magic Order v02 (2024) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Man-Eaters\Man-Eaters v01 (2019) (Digital) (DrDoom-Empire).cbz | merge | Title, Genre | Web, Summary, Notes, Publisher, PageCount | Man-Eaters v01 (2019) (Digital) (DrDoom-Empire)/ComicInfo.xml | nested |
| Man-Eaters\Man-Eaters v02 (2019) (Digital) (DrDoom-Empire).cbz | merge | Title, Summary, Genre | Web, Notes, Publisher, PageCount | Man-Eaters v02 (2019) (Digital) (DrDoom-Empire)/ComicInfo.xml | nested |
| Man-Eaters\Man-Eaters v03 (2019) (Digital) (DrDoom-Empire).cbz | merge | Title, Summary, Genre | Web, Notes, Publisher, PageCount | Man-Eaters v03 (2019) (Digital) (DrDoom-Empire)/ComicInfo.xml | nested |
| Masters of the Universe\DC Universe Vs. Masters of the Universe (2014) (Digital) (Bean-Empire).cbz | merge | Summary, Penciller, Genre, LanguageISO, ScanInformation, Pages | Web, Volume, Notes, Month, Writer, Publisher, PageCount | DC Universe Vs. Masters of the Universe (2014) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| Masters of the Universe\He-Man and the Masters of the Universe\He-Man - The Eternity War v01 (2015) (Digital) (Bean-Empire).cbz | merge | Title, Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, Writer, Penciller, Publisher, PageCount | He-Man - The Eternity War v01 (2015) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| Masters of the Universe\He-Man and the Masters of the Universe\He-Man - The Eternity War v02 (2016) (Digital) (Bean-Empire).cbz | merge | Title, Summary, Genre, ScanInformation, Pages | Web, Volume, Notes, Writer, Penciller, Publisher, PageCount | He-Man - The Eternity War v02 (2016) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| Masters of the Universe\He-Man and the Masters of the Universe\He-Man and the Masters of the Universe v02 - Origins of Eternia (2014) (Digital) (Bean-Empire).cbz | merge | Genre, ScanInformation, Pages | Title, Series, Web, Summary, Notes, Writer, Penciller, Publisher, PageCount | He-Man and the Masters of the Universe v02 - Origins of Eternia (2014) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| Masters of the Universe\He-Man and the Masters of the Universe\He-Man and the Masters of the Universe v03 (2014) (Digital) (Bean-Empire).cbz | merge | Title, Genre, ScanInformation, Pages | Web, Volume, Summary, Notes, Writer, Penciller, Publisher, PageCount | He-Man and the Masters of the Universe v03 (2014) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| Masters of the Universe\He-Man and the Masters of the Universe\He-Man and the Masters of the Universe v04 - What Lies Within (2015) (Digital) (Bean-Empire).cbz | merge | Genre, ScanInformation, Pages | Title, Web, Volume, Summary, Notes, Month, Writer, Penciller, Publisher, PageCount | He-Man and the Masters of the Universe v04 - What Lies Within (2015) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| Memorial\Memorial (2014) (Digital) (XRA-Empire).cbz | merge | Web, Summary, Publisher, Genre, LanguageISO, ScanInformation, Writer, Penciller | Notes, PageCount, Year, Month, Day | Memorial (2014) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Moonshine\Moonshine v01 (2017) (Digital-Empire).cbz | merge | Title, Genre | Web, Summary, Notes, Publisher, PageCount | Moonshine v01 (2017) (Digital-Empire)/ComicInfo.xml | nested |
| Namor\Namor - Last King Of Atlantis (2025) (Digital) (EricJGriffin-Empire).cbz | merge | - | Series, PageCount, Notes, writer, Month | Namor - Last King Of Atlantis (2025) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| Neil Gaiman Comics\Sandman Universe\John Constantine, Hellblazer\The Hellblazer 2021\John Constantine - Hellblazer v02 - The Best Version of You (2021) (Digital-Empire) (Dr.Vink) (FMTPB).cbz | merge | Summary, Genre, ScanInformation, Artist | Title, Volume, Web, Notes, Publisher, PageCount | John Constantine - Hellblazer 007-012 (2020-2021) (Digital-Empire) (Dr.Vink)/ComicInfo.xml | nested |
| Newburn\Newburn 012 (2023) (Digital) ( Li'l-Empire) (HD-Upscaled).cbz | merge | Summary | Web, Notes, Publisher, PageCount, LanguageISO, Month | Newburn 012 (2023) (Digital) ( Li'l-Empire)/ComicInfo.xml | nested |
| Night Eaters v01-03 (2022-2025)\The Night Eaters v01 - She Eats the Night (2022) (Digital) (XRA-Empire).cbz | merge | Summary, ScanInformation | Series, Web, Notes, Publisher, PageCount, LanguageISO | The Night Eaters v01 - She Eats the Night (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Night Eaters v01-03 (2022-2025)\The Night Eaters v02 - Her Little Reapers (2023) (Digital) (XRA-Empire).cbz | merge | Summary, ScanInformation | Web, Notes, Publisher, PageCount, LanguageISO | The Night Eaters v02 - Her Little Reapers (2023) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| November\November v02 - The Gun in the Puddle (2020) (Digital) (DrDoom-Empire).cbz | merge | Summary, Genre | Title, Web, Notes, Publisher, PageCount | November v02 - The Gun in the Puddle (2020) (Digital) (DrDoom-Empire)/ComicInfo.xml | nested |
| Paradiso\Paradiso v01 - Essential Singularity (2018) (digital) (Dr.Vink).cbz | merge | Summary, Genre, ScanInformation, Writer, Artist | Title, Web, Notes, Publisher, PageCount | Paradiso v01 - Essential Singularity (2018) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| Paradiso\Paradiso v02 - Dark Dwellers (2018) (digital) (Dr.Vink).cbz | merge | Summary, Genre, ScanInformation, Writer, Artist | Title, Web, Notes, Publisher, PageCount | Paradiso v02 - Dark Dwellers (2018) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| Planet of the\Planet of the Apes\Planet of the Apes Artist Tribute (2019) (Digital) (Bean-Empire).cbz | merge | Summary, Genre, ScanInformation, Penciller, Pages | Web, Notes, PageCount, Day | Planet of the Apes Artist Tribute (2019) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| Plunge\Plunge (2020) (digital) (Son of Ultron-Empire) (Fan Made TPB).cbz | merge | Title, Number, Web, Summary, Publisher, Genre, LanguageISO, ScanInformation | Series, Notes, PageCount | Plunge 001-006 (2020) (digital) (Son of Ultron-Empire) (Dr.Vink) (Fan Made TPB)/ComicInfo.xml | nested |
| Power Fantasy\Power Fantasy v02 (2025) (Digital) (EricJGriffin-Empire).cbz | merge | - | Series, PageCount, Notes, writer | Power Fantasy v02 (2025) (Digital) (EricJGriffin-Empire)/ComicInfo.xml | nested |
| Predator\Predator - The Original Years Omnibus v02 (2024) (Digital) (Kileko-Empire).cbz | merge | Summary | Publisher, PageCount, Notes, writer | Predator - The Original Years Omnibus v02 (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Prism\The Prism 003 (2023) (digital) (faethon).cbz | merge | Inker, CoverArtist, Pages | Volume, Summary, Notes, Day, Writer, Penciller, Publisher, Web, PageCount | The Prism Vol.2023 #3 (December, 2023)/ComicInfo.xml | nested |
| Project Cryptid\Project Cryptid 002 (2023) (digital) (Li'l-Empire) (HD-Upscaled).cbz | merge | - | Series, Web, Summary, Notes, Publisher, PageCount, LanguageISO, Month | Project Cryptid 002 (2023) (digital) (Li'l-Empire)/ComicInfo.xml | nested |
| Proxima Centauri\Proxima Centauri (2019) (Digital) (XRA-Empire).cbz | merge | Summary, ScanInformation | Web, Publisher, PageCount, LanguageISO, Month | Proxima Centauri (2019) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Redneck\Redneck v04 - Lone Star (2019) (Digital) (DrDoom-Empire).cbz | merge | Summary, Genre | Title, Web, Notes, Publisher, PageCount | Redneck v04 - Lone Star (2019) (Digital) (DrDoom-Empire)/ComicInfo.xml | nested |
| Renaissance\The Resistance v01 (2020) (digital) (Dr.Vink).cbz | merge | Title, Summary, Genre, ScanInformation, Artist | Series, Web, Notes, Publisher, PageCount | The Resistance v01 (2020) (digital) (Dr.Vink)/ComicInfo.xml | nested |
| Robert Silverberg's Belzagor\Robert Silverberg's Belzagor (Humanoids 2024) (webrip) (MagicMan-DCP).cbz | merge | - | Series, Summary, Notes | Robert Silverberg's Belzagor (Humanoids 2023) (webrip) (MagicMan-DCP)/ComicInfo.xml | nested |
| S.I.R\S.I.R. 002 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | - | Series, Publisher, Notes | S.I.R. 002 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| S.I.R\S.I.R. 003 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | - | Series, Publisher, Notes | S.I.R. 003 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| S.I.R\S.I.R. 004 (2024) (Digital Rip) (Hourman-DCP).cbz | merge | - | Publisher, Notes | S.I.R. 004 (2024) (Digital Rip) (Hourman-DCP)/ComicInfo.xml | nested |
| Sea Serpent's Heir\Sea Serpent's Heir Book 1 - Pirate's Daughter (2022) (Digital) (XRA-Empire).cbz | merge | Genre, ScanInformation | Web, Notes, Publisher | Sea Serpent's Heir Book 1 - Pirate's Daughter (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Skyward\Skyward (2021) (Digital) (XRA-Empire).cbz | merge | Genre, LanguageISO | Title, Web, Summary, Notes, ScanInformation, Day | Skyward (2021) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Snotgirl\Snotgirl v03 - Is This Real Life (2020) (Digital) (XRA-Empire).cbz | merge | Notes, Genre, LanguageISO | Title, Web, Summary, ScanInformation, Year, Month, Day, CoverArtist | Snotgirl v03 - Is This Real Life (2020) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Sparks\Sparks v01 - Portals (2024) (Digital-Empire).cbz | merge | writer | Series, PageCount, Notes | Sparks v01 - Portals (2024) (Digital-Empire)/ComicInfo.xml | nested |
| Spectacle\Spectacle, Book 01 (2018) (Digital) (Relic-Empire).cbz | merge | Title, Summary, Genre, Writer, Penciller, Inker, Colorist, CoverArtist, Pages | Web, Notes, PageCount, Month, Day | Spectacle, Book 01 (2018) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| Spectacle\Spectacle, Book 02 (2019) (Digital) (Relic-Empire).cbz | merge | Title, Summary, Genre, Writer, Penciller, Colorist, CoverArtist, Pages | Web, Notes, PageCount, Day | Spectacle, Book 02 (2019) (Digital) (Relic-Empire)/ComicInfo.xml | nested |
| Star Trek\Defiant\Star Trek - Defiant 017 (2024) (Digital) (Kileko-Empire).cbz | merge | Issue | Notes, writer | Star Trek - Defiant 017 (2024)/ComicInfo.xml | nested |
| Star Trek\Defiant\Star Trek - Defiant 023 (2025) (Digital) (Kileko-Empire).cbz | merge | Issue | Notes, writer | Star Trek - Defiant 023 (2025) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Trek\Star Trek 2022\Star Trek 012 (2023) (digital) (Li'l-Empire) (HD-Upscaled).cbz | merge | - | Web, Summary, Notes, Publisher, LanguageISO, Volume, Month | Star Trek 012 (2023) (digital) (Li'l-Empire)/ComicInfo.xml | nested |
| Star Trek\Star Trek 2022\Star Trek 023 (2024) (Digital) (Kileko-Empire).cbz | merge | Issue | Notes, writer | Star Trek 023 (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\Dark Droids\Star Wars - Dark Droids (2026) (Digital) (Kileko-Empire).cbz | merge | Summary, Writer, Penciller, CoverArtist, Publisher, AgeRating | Series, Year, Month, Day, PageCount | Star Wars - Dark Droids (2026) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\Darth Vader\Darth Vader (2020)\Star Wars - Darth Vader 043 (2024) (Digital) (F) (Kileko-Empire).cbz | merge | - | Web, Notes, LanguageISO, Volume | Star Wars - Darth Vader 043 (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\Darth Vader\Darth Vader (2020)\Star Wars - Darth Vader 044 (2024) (Digital) (Kileko-Empire).cbz | merge | - | Web, Notes, LanguageISO, Volume | Star Wars - Darth Vader 044 (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\Darth Vader\Darth Vader (2020)\Star Wars - Darth Vader 048 (2024) (Digital) (Kileko-Empire).cbz | merge | Issue | Publisher, Summary, Notes, writer, Month | Star Wars - Darth Vader 048 (2024)/ComicInfo.xml | nested |
| Star Wars\Darth Vader\Darth Vader (2020)\Star Wars - Darth Vader 049 (2024) (Digital) (Kileko-Empire).cbz | merge | Issue | Publisher, Notes, writer, Month | Star Wars - Darth Vader 049 (2024)/ComicInfo.xml | nested |
| Star Wars\Galaxy's Edge\Galaxy's Edge (2026)\Star Wars - Galaxy's Edge - Echoes of The Empire 005 (2026) (Digital) (Kileko-Empire).cbz | merge | - | Series, Volume, Summary, Month, Day, Penciller, Publisher, PageCount, AgeRating | Star Wars - Galaxy's Edge - Echoes Of The Empire 005(2026) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\High Republic\The High Republic - Phase III\Star Wars - The High Republic - Phase III 009 (2024) (Digital) (Kileko-Empire).cbz | merge | Issue, Summary | Publisher, PageCount, Notes, writer, Month | Star Wars - The High Republic - Phase III 009 (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\High Republic\The High Republic - Phase III\Star Wars - The High Republic - Phase III 010 (2024) (Digital) (Kileko-Empire).cbz | merge | Issue, Summary | Series, Publisher, PageCount, Notes, writer, Month | Star Wars - The High Republic - Phase III 010 (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\High Republic\The High Republic - Phase III\Star Wars - The High Republic - Phase III v01 - Children Of The Storm (2024) (Digital) (Kileko-Empire).cbz | merge | LanguageISO | Publisher, Summary, Notes, writer | Star Wars - The High Republic Phase III v01 - Children Of The Storm (2024)/ComicInfo.xml | nested |
| Star Wars\High Republic\The High Republic Adventures\Star Wars - The High Republic Adventures Phase III 007 (2024) (Digital) (Kileko-Empire).cbz | merge | Issue | Series, Publisher, Summary, Notes, writer | Star Wars - The High Republic Adventures Phase III 007 (2024)/ComicInfo.xml | nested |
| Star Wars\High Republic\The High Republic Adventures\Star Wars - The High Republic Adventures Phase III 008 (2024) (Digital) (Kileko-Empire).cbz | merge | Issue | Series, Notes, writer | Star Wars - The High Republic Adventures - Phase III 008 (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\High Republic\The High Republic Adventures\Star Wars - The High Republic Adventures Phase III 014 (2025) (Digital) (Kileko-Empire).cbz | merge | Issue | Series, Notes, writer | Star Wars - The High Republic Adventures Phase III 014 (2025) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\High Republic\The High Republic Adventures\Star Wars- The High Republic Adventures - Galactic Bake-Off Spectacular (2022) (Digital) (Kileko-Empire).cbz | merge | Pages | Web, Notes, Publisher, Genre, ScanInformation, Day, Writer, Penciller | Star Wars- The High Republic Adventures - Galactic Bake-Off Spectacular (2022) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\High Republic\The High Republic Adventures\Dispatches from the Occlusion Zone\Star Wars - The High Republic Adventures Phase III - Dispatches from the Occlusion Zone 004 (2025) (Digital) (Kileko-Empire).cbz | merge | Issue, LanguageISO | Series, Notes, writer | Star Wars - The High Republic Adventures Phase III--Dispatches from the Occlusion Zone 004 (2025) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\High Republic\The High Republic Adventures\Pathfinders\Star Wars - The High Republic Adventures - Pathfinders 004 (2026) (Digital) (Kileko-Empire).cbz | merge | - | Series, Summary, Month, Day, Penciller, PageCount, AgeRating | Star Wars - The High Republic Adventures - Pathfinders 004 (2026) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\Jango Fett\Star Wars - Jango Fett - Trail Of Lost Hope (2025) (Digital) (Kileko-Empire).cbz | merge | LanguageISO | Series, Notes, writer | Star Wars - Jango Fett - Trail Of Lost Hope (2025) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\Mace Windu\Mace Windu (2024)\The Twilight Run\Star Wars - Mace Windu - The Twilight Run (2024) (Digital) (Kileko-Empire).cbz | merge | Summary, writer | Publisher, PageCount, Notes | Star Wars - Mace Windu - The Twilight Run (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\Obi Wan\Obi-Wan Kenobi\Star Wars - Obi-Wan Kenobi (2024) (Digital) (Kileko-Empire).cbz | merge | Summary, writer | Publisher, PageCount, Notes | Star Wars - Obi-Wan Kenobi (2024)/ComicInfo.xml | nested |
| Star Wars\Star Wars (2020)\Star Wars 049 (2024) (Digital) (Kileko-Empire).cbz | merge | Issue | Publisher, Notes, writer, Month | Star Wars 049 (2024) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Star Wars\Star Wars Epic Collection\Star Wars Modern Era Epic Collection v01 - Skywalker Strikes (2024) (Digital) (Kileko-Empire).cbz | merge | Summary, writer | Series, Publisher, PageCount, Notes | Star Wars Modern Era Epic Collection - Skywalker Strikes (2024)/ComicInfo.xml | nested |
| Star Wars\Star Wars Legends\Star Wars Legends - The New Republic Omnibus v02 (2024) (Digital) (Kileko-Empire).cbz | merge | LanguageISO | Publisher, Summary, Notes, writer | Star Wars Legends - The New Republic Omnibus v02 (2024)/ComicInfo.xml | nested |
| Step by Bloody Step\Step by Bloody Step - A Wordless Fantasy (2022) (Digital) (XRA-Empire).cbz | merge | Title, Genre, ScanInformation | Series, Web, Notes, Publisher, Writer, Penciller | Step by Bloody Step - A Wordless Fantasy (2022) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Stranger Things\Teenage Mutant Ninja Turtles x Stranger Things\Teenage Mutant Ninja Turtles x Stranger Things 004 (2023) (digital) ( Li'l-Empire) (HD-Upscaled).cbz | merge | - | Web, Summary, Notes, Publisher, PageCount, LanguageISO, Month | Teenage Mutant Ninja Turtles x Stranger Things 004 (2023) (digital) ( Li'l-Empire)/ComicInfo.xml | nested |
| Supernatural\Supernatural 010 (2026) (Digital) (Kileko-Empire).cbz | merge | - | Summary, Month, Day, PageCount, AgeRating | Supernatural 010 (2026) (Digital) (Kileko-Empire)/ComicInfo.xml | nested |
| Swan Songs\Swan Songs 004 (2023) (Digital) (Li'l-Empire) (HD-Upscaled).cbz | merge | Summary | Web, Notes, Publisher, PageCount, LanguageISO, Month | Swan Songs 004 (2023) (Digital) (Li'l-Empire)/ComicInfo.xml | nested |
| Swing\Swing v01 (2018) (Digital) (DrDoom-Empire).cbz | merge | Title, Summary, Genre | Web, Notes, Publisher, PageCount | Swing v01 (2018) (Digital) (DrDoom-Empire)/ComicInfo.xml | nested |
| Swing\Swing v02 (2019) (Digital) (DrDoom-Empire).cbz | merge | Title, Summary, Genre | Web, Notes, Publisher, PageCount | Swing v02 (2019) (Digital) (DrDoom-Empire)/ComicInfo.xml | nested |
| Symmetry\Symmetry v01 (2016) (Digital) (XRA-Empire).cbz | merge | Title, Summary, Genre | Web, Notes, Publisher, PageCount | Symmetry v01 (2016) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Symmetry\Symmetry v02 (2016) (Digital) (XRA-Empire).cbz | merge | Title, Summary, Genre | Web, Notes, Publisher, PageCount | Symmetry v02 (2016) (Digital) (XRA-Empire)/ComicInfo.xml | nested |
| Thundercats\He-Man-Thundercats (2017) (Digital) (Bean-Empire).cbz | merge | Summary, Genre, ScanInformation, Pages | Series, Web, Volume, Notes, Writer, Publisher, PageCount | He-Man-Thundercats (2017) (Digital) (Bean-Empire)/ComicInfo.xml | nested |
| Tower\Tower of Shadows Creatures on the loose\Creatures on the Loose 010-037 (1970-1975)\Creatures on the Loose 031 (1974) (Digital) (Shadowcat-Empire).cbz | merge | - | Web, Volume, Notes, Genre, PageCount | Creatures on the Loose 031 (1974)/ComicInfo.xml | nested |
| Tower\Tower of Shadows Creatures on the loose\Creatures on the Loose 010-037 (1970-1975)\Creatures on the Loose 032 (1974) (Digital) (Shadowcat-Empire).cbz | merge | - | Web, Volume, Notes, Genre, PageCount | Creatures on the Loose 032 (1974)/ComicInfo.xml | nested |
| Tower\Tower of Shadows Creatures on the loose\Creatures on the Loose 010-037 (1970-1975)\Creatures on the Loose 033 (1975) (Digital) (Shadowcat-Empire).cbz | merge | - | Web, Volume, Notes, Genre, PageCount | Creatures on the Loose 033 (1975)/ComicInfo.xml | nested |
| Tower\Tower of Shadows Creatures on the loose\Creatures on the Loose 010-037 (1970-1975)\Creatures on the Loose 034 (1975) (Digital) (Shadowcat-Empire).cbz | merge | - | Web, Volume, Summary, Notes, Genre, PageCount | Creatures on the Loose 034 (1975)/ComicInfo.xml | nested |
| Tower\Tower of Shadows Creatures on the loose\Creatures on the Loose 010-037 (1970-1975)\Creatures on the Loose 035 (1975) (Digital) (Shadowcat-Empire).cbz | merge | - | Web, Volume, Notes, Genre, PageCount | Creatures on the Loose 035 (1975)/ComicInfo.xml | nested |
| Tower\Tower of Shadows Creatures on the loose\Creatures on the Loose 010-037 (1970-1975)\Creatures on the Loose 036 (1975) (Digital) (Shadowcat-Empire).cbz | merge | - | Web, Volume, Notes, Genre, PageCount | Creatures on the Loose 036 (1975)/ComicInfo.xml | nested |
| Tower\Tower of Shadows Creatures on the loose\Creatures on the Loose 010-037 (1970-1975)\Creatures on the Loose 037 (1975) (Digital) (Shadowcat-Empire).cbz | merge | Summary | Web, Volume, Notes, Genre, PageCount | Creatures on the Loose 037 (1975)/ComicInfo.xml | nested |
| Void Rivals\Void Rivals 005 (2023) (Digital) ( Li'l-Empire) (HD-Upscaled).cbz | merge | - | Web, Summary, Notes, Publisher, PageCount, LanguageISO, Month | Void Rivals 005 (2023) (Digital) ( Li'l-Empire)/ComicInfo.xml | nested |
| Walking Dead\The Walking Dead Deluxe\The Walking Dead Deluxe 139 (2026).cbz | merge | Pages | PageCount, Publisher, Volume | The Walking Dead Deluxe 139 (2026)/ComicInfo.xml | nested |
| What's the Furtherst Place From Here\What's the Furthest Place from Here 014 (2023) (Digital) (Li'l-Empire) (HD-Upscaled).cbz | merge | - | Series, Web, Summary, Notes, Publisher, PageCount, LanguageISO, Month | What's the Furthest Place from Here 014 (2023) (Digital) (Li'l-Empire)/ComicInfo.xml | nested |
| What's the Furtherst Place From Here\What's the Furthest Place from Here 015 (2023) (Digital) ( Li'l-Empire) (HD-Upscaled).cbz | merge | - | Series, Web, Summary, Notes, Publisher, PageCount, LanguageISO, Month | What's the Furthest Place from Here 015 (2023) (Digital) ( Li'l-Empire)/ComicInfo.xml | nested |
| Winnebago Graveyard\Winnebago Graveyard (2017) (Digital) (DrDoom-Empire).cbz | merge | Title, Summary, Genre | Web, Notes, Publisher, PageCount | Winnebago Graveyard (2017) (Digital) (DrDoom-Empire)/ComicInfo.xml | nested |

## Apply (only after Futaba's sample and Sergei's final OK)

Needs the installed app to be a version with the nested merge (the tool refuses an older engine). The `--out` folder keeps the record of every dropped nested value and removed nested copy: keep it.

```
"%LOCALAPPDATA%\Programs\comic-metadata\resources\runtime\python\python.exe" -B tools\nested_comicinfo_merge.py --apply "Docs\ComicsMetaOrganizer_NestedMergeDryRun_2026-11-18.json" --out "<new empty folder>"
```
