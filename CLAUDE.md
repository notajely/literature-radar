# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Literature Radar** is an arXiv paper discovery tool driven by your Zotero library. It analyzes your research interests through clustering, then retrieves and ranks recent papers from arXiv, with Claude providing final recommendations.

### Core Pipeline

1. **Profile** (`profile.py`): Parse BibTeX → TF-IDF vectorization → K-means clustering → Claude names clusters → generates `research-interest.json`
2. **Retrieval** (`retrieval.py`): Query arXiv API using cluster keywords → deduplicate → returns candidate papers
3. **Ranking** (`ranker.py`): Score candidates using TF-IDF similarity + recency decay → top 20 papers
4. **Enrichment** (`enrichment.py`): Claude reviews top 20, selects best 5, writes recommendations
5. **Rendering** (`renderer.py`): Format results as Markdown digest

## Development Commands

```bash
# Install dependencies
uv sync

# Generate research interest profile (one-time setup)
uv run literature-radar profile --bib library.bib --api-key sk-ant-...

# Generate weekly digest
uv run literature-radar digest --bib library.bib --api-key sk-ant-...

# Quick search without profile
uv run literature-radar search --query "ai safety" --top 5
```

### Common Options

```bash
# Customize digest parameters
uv run literature-radar digest --days-back 7 --digest-size 8

# Regenerate profile after library updates
uv run literature-radar profile --bib library.bib --api-key sk-ant-...
```

## Architecture Notes

### Data Flow

- **Input**: `library.bib` (Zotero export) → parsed into `papers` list
- **Intermediate**: `profiles/research-interest.json` (cluster definitions with keywords)
- **Output**: `reports/digest.md` (final recommendations), `reports/candidates.json` (debug)

### Key Design Decisions

- **Clustering**: K-means on TF-IDF vectors with automatic k selection via silhouette score (range 4–9)
- **Scoring**: Two-factor ranking: topic fit (70%) via cosine similarity + recency (30%) via exponential decay
- **LLM Usage**: Only for cluster naming and final paper selection/review; all retrieval and ranking is deterministic
- **arXiv API**: Uses free Atom XML API with 3-second rate limiting between requests

### Module Responsibilities

- `parser.py`: BibTeX parsing, caching parsed results
- `profile.py`: Clustering logic, cluster naming via Claude
- `retrieval.py`: arXiv API queries, deduplication
- `ranker.py`: TF-IDF similarity scoring, recency weighting
- `enrichment.py`: Claude review of top candidates
- `renderer.py`: Markdown output formatting
- `cli.py`: Typer CLI orchestration

## Dependencies

- `bibtexparser`: BibTeX parsing
- `scikit-learn`: TF-IDF, K-means, cosine similarity
- `numpy`: Numerical operations
- `anthropic`: Claude API
- `httpx`: HTTP client (via arXiv queries)
- `rich`: Terminal UI
- `typer`: CLI framework

## Important Implementation Details

### Profile Generation

- Requires minimum 4 papers to cluster
- TF-IDF uses bigrams, filters common/rare terms (min_df=2, max_df=0.85)
- Each cluster generates 2 retrieval queries from top 4–8 TF-IDF terms
- Cluster naming requires API key; falls back to top term if unavailable

### Ranking Weights

- `w_topic=0.70`: Cosine similarity between candidate abstract+title and combined interest profile
- `w_recency=0.30`: Exponential decay with 7-day half-life
- Top 20 candidates passed to enrichment

### Enrichment Prompt

Claude receives:
- Researcher's interest areas (cluster labels + descriptions)
- Top 20 ranked candidates with scores
- Task: select best N papers (default 5), write review fields (recommendation, why_it_matters, caveats, anchor_connection)

### Error Handling

- arXiv API failures are caught and logged; retrieval continues with other queries
- Missing API key in digest command exits with error message
- Profile auto-generation if missing during digest run
