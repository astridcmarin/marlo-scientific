# 0001 — The evidence index is derived from the pinned files, not stored in a database

**Date:** 11 November 2026 · **Status:** accepted

## Problem

Each pinned file is traceable on its own (quotes, locations, SHA-256), but nothing answers questions across files: which models use a given extract, which checks pinned it, which conclusions depend on an unresolved assumption, which file superseded which. An outside review (ChatGPT, 11 November 2026) proposed an evidence graph to answer them.

## Options

1. A graph database (for example Neo4j) holding drugs, sources, files, models, checks and their relationships.
2. New relational tables in the platform's SQLAlchemy database, filled by a migration.
3. A read-only index computed on demand from what the pinned files and the dataset ledger already state.

## Decision

Option 3. The pinned files already contain 303 `{file, sha256}` references and 49 `supersedes` blocks, and the ledger records every model-dataset use. An index built from them needs no new dependency, no migration and no hand-entered relationship, cannot drift from the files, and fails loudly when a reference does not resolve. Options 1 and 2 would duplicate that information and add a second place for it to go wrong.

## Revisit when

A query is needed that the computed index cannot answer quickly enough on the page; relationships are needed that no pinned file states (they would first need their own pinned, sourced file); or several users edit relationships concurrently.
