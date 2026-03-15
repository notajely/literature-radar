# Literature Radar

arXiv paper discovery driven by your Zotero library. Automatically identifies your research interests, retrieves relevant papers, and uses Claude to write personalized recommendations.

## Why Literature Radar?

Keeping up with research is hard. Every week, thousands of papers hit arXiv. How do you find the ones that matter to *your* work?

Literature Radar solves this by learning from your existing library. It analyzes papers you've already collected, identifies your research interests through **TF-IDF vectorization and K-means clustering**, then automatically searches arXiv for relevant new papers. Claude reviews the top candidates and writes personalized recommendations explaining why each paper matters to your work.

Inspired by [research-assist](https://github.com/zhanglg12/research-assist), but built for researchers who want a lightweight, reproducible workflow.

## How it works

```
library.bib (Zotero export)
    ↓
[1] Profile  — TF-IDF + K-means clustering → research-interest.json
    ↓
[2] Retrieve — arXiv API queries per cluster
    ↓
[3] Rank     — TF-IDF similarity + recency decay
    ↓
[4] Enrich   — Claude reviews top 20, picks best N
    ↓
[5] Render   — Markdown digest
```

## Setup

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and install

```bash
git clone https://github.com/notajely/literature-radar.git
cd literature-radar
uv sync
```

### 3. Export your Zotero library

Zotero → File → Export Library → format: **BibTeX** → save as `library.bib` in the project root.

Having abstracts in your entries improves clustering quality significantly.

### 4. Set your API key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Optional — if using a proxy:
```bash
export ANTHROPIC_BASE_URL="https://your-proxy.example.com"
export API_TIMEOUT_MS=300000
```

Or pass it per command: `--api-key sk-ant-...`

## Usage

```bash
# First run: build interest profile
uv run literature-radar profile --bib library.bib

# Weekly: generate digest
uv run literature-radar digest --bib library.bib

# Quick search (no profile needed)
uv run literature-radar search --query "ai safety" --top 5
```

### Language

All commands accept `--lang en` (default) or `--lang zh`:

```bash
uv run literature-radar digest --bib library.bib --lang zh
```

This controls the language of Claude's recommendations and the digest labels.

## Options

```bash
# digest
--days-back 7        # search last N days (default: 14)
--digest-size 8      # papers to recommend (default: 5)
--lang zh            # output language: en or zh

# profile
--lang zh            # cluster labels language
```

## Output

```
literature-radar/
├── library.bib                    ← your Zotero export
├── profiles/
│   └── research-interest.json    ← auto-generated profile
└── reports/
    ├── digest.md                  ← weekly output
    └── candidates.json            ← all candidates (debug)
```

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Anthropic API key ([get one here](https://console.anthropic.com/))

## License

MIT
