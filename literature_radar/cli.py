"""
CLI 入口。把所有步骤串起来。

用法：
  literature-radar profile  --bib library.bib --api-key sk-ant-...
  literature-radar digest   --bib library.bib --api-key sk-ant-...
  literature-radar search   --query "ai alignment" --top 5
"""

import json
import os
from pathlib import Path

import typer
from rich import print as rprint
from rich.panel import Panel

from literature_radar.parser import load_or_parse
from literature_radar.profile import build_profile
from literature_radar.retrieval import retrieve_all
from literature_radar.ranker import rank_candidates
from literature_radar.enrichment import enrich_candidates
from literature_radar.renderer import render_markdown

app = typer.Typer(help="Literature Radar — arXiv digest driven by your Zotero library.")


def _get_api_key(api_key: str | None) -> str | None:
    """从参数或环境变量取 API key。"""
    return api_key or os.environ.get("ANTHROPIC_API_KEY")


@app.command()
def profile(
    bib: str = typer.Option("library.bib", help="BibTeX file path"),
    api_key: str = typer.Option(None, help="Anthropic API key (for cluster naming)"),
    output: str = typer.Option("profiles/research-interest.json", help="Output path"),
    lang: str = typer.Option("en", help="Output language: 'en' or 'zh'"),
):
    """Parse library and build interest profile."""
    rprint(Panel("📚 Parsing library...", style="blue"))

    papers = load_or_parse(bib)
    rprint(f"  Found {len(papers)} papers")

    rprint(Panel("🔬 Clustering research interests...", style="blue"))
    key = _get_api_key(api_key)
    profile_data = build_profile(papers, output_path=output, api_key=key, lang=lang)

    rprint(f"\n✅ Identified {profile_data['k']} interest clusters:")
    for i in profile_data["interests"]:
        rprint(f"  • [bold]{i['label']}[/bold]: {i['description']}")

    rprint(f"\nProfile saved to [green]{output}[/green]")


@app.command()
def digest(
    bib: str = typer.Option("library.bib", help="BibTeX file path"),
    api_key: str = typer.Option(None, help="Anthropic API key"),
    profile_path: str = typer.Option("profiles/research-interest.json", help="Interest profile path"),
    days_back: int = typer.Option(14, help="How many days back to search"),
    digest_size: int = typer.Option(5, help="Number of papers to include"),
    output: str = typer.Option("reports/digest.md", help="Output file path"),
    candidates_output: str = typer.Option("reports/candidates.json", help="Candidates output path"),
    lang: str = typer.Option("en", help="Output language: 'en' or 'zh'"),
):
    """Full pipeline: retrieve → rank → recommend → render digest."""
    key = _get_api_key(api_key)
    if not key:
        rprint("[red]❌ Anthropic API key required (--api-key or ANTHROPIC_API_KEY env var)[/red]")
        raise typer.Exit(1)

    if not Path(profile_path).exists():
        rprint(f"[yellow]Profile not found, generating...[/yellow]")
        papers = load_or_parse(bib)
        profile_data = build_profile(papers, output_path=profile_path, api_key=key, lang=lang)
    else:
        profile_data = json.loads(Path(profile_path).read_text())

    rprint(Panel(f"🔍 Searching arXiv (last {days_back} days)...", style="blue"))
    candidates = retrieve_all(profile_data, days_back=days_back)

    if not candidates:
        rprint("[yellow]No new papers found.[/yellow]")
        raise typer.Exit(0)

    rprint(Panel("📊 Ranking candidates...", style="blue"))
    ranked = rank_candidates(candidates, profile_data, top_n=20)

    rprint(Panel("🤖 Claude filtering and writing recommendations...", style="blue"))
    enriched = enrich_candidates(ranked, profile_data, api_key=key, digest_size=digest_size, lang=lang)

    Path(candidates_output).parent.mkdir(exist_ok=True)
    Path(candidates_output).write_text(json.dumps(enriched, ensure_ascii=False, indent=2))

    rprint(Panel("📝 Rendering digest...", style="blue"))
    content = render_markdown(enriched, output_path=output, lang=lang)

    kept = [p for p in enriched if p.get("review", {}).get("keep")]
    rprint(f"\n✅ Digest complete: {len(kept)} papers")
    rprint(f"   Saved to [green]{output}[/green]")
    rprint(f"\nPreview:\n")
    for line in content.split("\n")[:6]:
        rprint(f"  {line}")


@app.command()
def search(
    query: str = typer.Option(..., help="Search query"),
    top: int = typer.Option(5, help="Number of results"),
    days_back: int = typer.Option(30, help="How many days back to search"),
):
    """Quick arXiv search without a profile."""
    from literature_radar.retrieval import search_arxiv

    rprint(f"🔍 检索：{query}")
    results = search_arxiv(query, max_results=top * 2, days_back=days_back)[:top]

    for i, p in enumerate(results, 1):
        rprint(f"\n[bold]{i}. {p['title']}[/bold]")
        rprint(f"   {', '.join(p['authors'][:3])} | {p['submitted']}")
        rprint(f"   {p['url']}")
        rprint(f"   {p['abstract'][:150]}...")


if __name__ == "__main__":
    app()
