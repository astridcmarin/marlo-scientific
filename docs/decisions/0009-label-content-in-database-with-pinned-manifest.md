# 0009 — Label content is stored in database tables, rebuilt from DailyMed files listed in a pinned manifest

**Date:** 20 November 2026 · **Status:** accepted by the owner, 20 November 2026 (choice 4 of decision 0007), with one change: "if the repository is too large, then we will look for a different way to store them"

## Problem

Decision 0007 puts every US prescription label into the platform as verbatim text, one page per active ingredient. Everything the platform holds so far is versioned JSON in `intelligence_store/data/`, each file pinned by SHA-256. That does not scale to this content. On 20 November DailyMed's download page listed the full human prescription release as six parts, 54,916 label files and about 16.7 GB zipped (last modified 21 September 2026). Labels are revised, and DailyMed publishes daily, weekly and monthly updates. The repository is public, and the GitHub account was flagged on 3 November for too many commits.

Whatever is chosen must keep three properties the platform already has: every value can be traced to a pinned source; nothing changes in place; and a page can say what was and was not reviewed.

## Options

1. **Versioned JSON files in the repository**, as now. Rejected for this content: tens of thousands of label versions, a pin per file, and a commit for every refresh.
2. **Database tables, rebuilt by script from DailyMed files listed in a pinned manifest.** The raw files stay outside the repository; the manifest that names them (set ID, version, checksum) is a pinned data file; the extracted text lives in tables that are only ever added to.
3. **Extracted files on disk outside the repository** (`instance/` or the supplemental folder) with a manifest. Traceable, but drug pages need to find labels by ingredient, section and date, which means building an index — a database by another name.
4. **Hosted storage now** (object storage or a hosted database). Premature: there are no invited users yet (Phase 7), and it adds cost and accounts before the pilot shows the shape works.

## Decision

Option 2:

- **Raw files.** The DailyMed zip files are kept on the ingestion machine (the owner's iMac, decision 0007 choice 3), under `supplemental-information/dailymed/`, never committed. Each label's XML is identified by its SHA-256.
- **Manifest.** Each ingestion run writes a release manifest to `intelligence_store/data/`, pinned like any other data file. Per label it lists the set ID, version, effective date, marketing category and application number, the ingredients (UNII and name), the zip file it came from, the XML's SHA-256 and the extraction method version. The pilot's manifest is a plain JSON file. If the full set's manifest is too large for the repository, another way to store it is chosen then, by the owner (20 November); the repository is not made to carry it.
- **Tables.** One Alembic migration adds three tables: a document table (one row per label version: set ID, version, manifest, marketing category, application number, effective date, title, XML checksum); a section table (document, LOINC section code, heading as printed, order, verbatim text, text checksum, extraction method version); and an ingredient table (document, UNII, name). Rows are insert-only, like the platform's immutable run tables: a new label version or a new extraction method adds rows and never updates old ones.
- **Rebuildable.** A deterministic script rebuilds the tables from the manifest and the raw files. Tests run it on small synthetic SPL files in the repository (made up, not taken from DailyMed). Anyone with the same DailyMed files can rebuild the same tables, so the public repository carries the method and the manifest, not the content.
- **Review state.** Every section row shows as "taken from the label by script, not reviewed" (decision 0007), until a sampled review under a locked plan says otherwise. Review records are pinned JSON files, as now.
- **Database.** SQLite for the pilot and for the owner's computer, as the platform uses now; the existing `DATABASE_URL` setting allows another database when the platform goes online.
- **What does not change.** The ten hand-built catalogue drugs, their reviewed summaries and every pinned model input stay in versioned JSON files. Label text in the tables never feeds a calculation or a model check without first being reviewed by hand and pinned, as the NINLARO values were.

## Revisit when

- The pilot shows the tables or the manifest do not fit (size, rebuild time, or a label structure the parser cannot handle).
- A full prescription ingest is more than SQLite handles comfortably on the owner's computer.
- The platform goes online (Phase 7) and the content must be hosted.
- DailyMed changes its release format.
