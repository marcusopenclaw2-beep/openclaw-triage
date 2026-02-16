"""CLI interface for OpenClaw Triage."""

import asyncio
import json
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from openclaw_triage.config import Settings, get_settings
from openclaw_triage.github_client import GitHubClient
from openclaw_triage.llm_client import LLMClient
from openclaw_triage.orchestrator import TriageOrchestrator

app = typer.Typer(
    name="openclaw-triage",
    help="AI-powered PR/Issue triage for OpenClaw",
    rich_markup_mode="rich",
)
console = Console()


def get_repo(repo: str | None) -> str:
    """Get repository from arg or env."""
    if repo:
        return repo
    env_repo = os.getenv("TRIAGE_REPO")
    if env_repo:
        return env_repo
    console.print("[red]Error: Repository required. Use --repo or set TRIAGE_REPO[/red]")
    raise typer.Exit(1)


@app.command()
def analyze_pr(
    pr_number: int = typer.Argument(..., help="PR number to analyze"),
    repo: str | None = typer.Option(None, "--repo", "-r", help="Repository (owner/repo)"),
    no_dedup: bool = typer.Option(False, "--no-dedup", help="Skip deduplication"),
    no_base: bool = typer.Option(False, "--no-base", help="Skip base detection"),
    no_review: bool = typer.Option(False, "--no-review", help="Skip deep review"),
    no_vision: bool = typer.Option(False, "--no-vision", help="Skip vision check"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Analyze a single PR."""
    repo = get_repo(repo)
    
    async def run():
        # Check for API keys
        if not os.getenv("GITHUB_TOKEN"):
            console.print("[red]Error: GITHUB_TOKEN environment variable required[/red]")
            raise typer.Exit(1)
        
        llm = None
        if not (no_review and no_vision):
            if os.getenv("ANTHROPIC_API_KEY"):
                llm = LLMClient(provider="anthropic")
            elif os.getenv("OPENAI_API_KEY"):
                llm = LLMClient(provider="openai")
            else:
                console.print("[yellow]Warning: No LLM API key found. Running without AI features.[/yellow]")
        
        orchestrator = TriageOrchestrator(llm_client=llm)
        
        with console.status(f"[bold green]Analyzing PR #{pr_number}..."):
            result = await orchestrator.triage_pr(
                repo=repo,
                pr_number=pr_number,
                enable_dedup=not no_dedup,
                enable_base_detection=not no_base,
                enable_review=not no_review,
                enable_vision=not no_vision,
            )
        
        await orchestrator.close()
        
        if json_output:
            console.print(json.dumps(result.model_dump(), indent=2, default=str))
            return
        
        # Display results
        console.print(Panel.fit(
            f"[bold]PR #{pr_number} Analysis[/bold]\n"
            f"Repository: {repo}\n"
            f"Status: {result.status.value}\n"
            f"Processing time: {result.processing_time_ms}ms",
            title="OpenClaw Triage",
            border_style="blue"
        ))
        
        if result.error_message:
            console.print(f"[red]Error: {result.error_message}[/red]")
            return
        
        # Executive summary
        console.print(Panel(
            result.executive_summary,
            title="[bold]Executive Summary[/bold]",
            border_style="green"
        ))
        
        # Deduplication
        if result.deduplication:
            dedup = result.deduplication
            if dedup.is_duplicate:
                console.print(Panel(
                    f"[yellow]⚠️ Likely duplicate of #{dedup.canonical_item.item_number}[/yellow]\n"
                    f"Confidence: {dedup.confidence:.1%}\n"
                    f"Reason: {dedup.canonical_item.reason}",
                    title="Deduplication",
                    border_style="yellow"
                ))
            elif dedup.similar_items:
                table = Table(title="Similar PRs")
                table.add_column("PR", style="cyan")
                table.add_column("Title")
                table.add_column("Similarity", justify="right")
                table.add_column("Reason")
                
                for item in dedup.similar_items:
                    table.add_row(
                        f"#{item.item_number}",
                        item.title[:50] + "..." if len(item.title) > 50 else item.title,
                        f"{item.similarity_score:.1%}",
                        item.reason[:40]
                    )
                console.print(table)
            else:
                console.print("[green]✅ No duplicates detected[/green]")
        
        # Base detection
        if result.base_detection:
            base = result.base_detection
            if base.is_base_candidate:
                console.print(Panel(
                    "[bold green]⭐ This PR is a BASE candidate[/bold green]\n"
                    f"Score: {base.score.total_score:.2f}\n"
                    f"Competing PRs: {', '.join(f'#{n}' for n in base.competing_prs)}",
                    title="Base Detection",
                    border_style="green"
                ))
            console.print(f"[dim]{base.reasoning}[/dim]")
        
        # Deep review
        if result.deep_review:
            review = result.deep_review
            quality_color = "green" if review.overall_quality >= 0.8 else "yellow" if review.overall_quality >= 0.6 else "red"
            
            console.print(Panel(
                f"[bold]Quality: [{quality_color}]{review.overall_quality:.0%}[/{quality_color}][/bold]\n"
                f"Security Risk: {review.security_risk}\n"
                f"Findings: {len(review.findings)}\n"
                f"Breaking Changes: {len(review.breaking_changes)}",
                title="Deep Review",
                border_style="blue"
            ))
            
            if review.findings:
                findings_table = Table(title="Top Findings")
                findings_table.add_column("Severity", style="bold")
                findings_table.add_column("Category")
                findings_table.add_column("Message")
                
                severity_colors = {
                    "critical": "red",
                    "high": "red",
                    "medium": "yellow",
                    "low": "blue",
                    "info": "dim",
                }
                
                for finding in review.findings[:5]:
                    color = severity_colors.get(finding.severity, "white")
                    findings_table.add_row(
                        f"[{color}]{finding.severity.upper()}[/{color}]",
                        finding.category,
                        finding.message[:60]
                    )
                console.print(findings_table)
        
        # Vision alignment
        if result.vision_alignment:
            vision = result.vision_alignment
            status_colors = {
                "aligned": "green",
                "needs_discussion": "yellow",
                "misaligned": "red",
            }
            color = status_colors.get(vision.status, "white")
            
            console.print(Panel(
                f"[bold {color}]Status: {vision.status.upper()}[/{color}][/bold]\n"
                f"Alignment Score: {vision.alignment_score:.0%}\n"
                f"Recommendation: {vision.recommendation}",
                title="Vision Alignment",
                border_style=color
            ))
        
        # Recommended action
        console.print(Panel(
            f"[bold]Priority: {result.priority.upper()}[/bold]\n"
            f"Action: {result.recommended_action}",
            title="Recommendation",
            border_style="magenta"
        ))
    
    asyncio.run(run())


@app.command()
def analyze_issue(
    issue_number: int = typer.Argument(..., help="Issue number to analyze"),
    repo: str | None = typer.Option(None, "--repo", "-r", help="Repository (owner/repo)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Analyze a single Issue."""
    repo = get_repo(repo)
    
    async def run():
        if not os.getenv("GITHUB_TOKEN"):
            console.print("[red]Error: GITHUB_TOKEN environment variable required[/red]")
            raise typer.Exit(1)
        
        orchestrator = TriageOrchestrator()
        
        with console.status(f"[bold green]Analyzing Issue #{issue_number}..."):
            result = await orchestrator.triage_issue(repo, issue_number)
        
        await orchestrator.close()
        
        if json_output:
            console.print(json.dumps(result.model_dump(), indent=2, default=str))
            return
        
        console.print(Panel.fit(
            f"[bold]Issue #{issue_number} Analysis[/bold]\n"
            f"Repository: {repo}\n"
            f"Status: {result.status.value}",
            title="OpenClaw Triage",
            border_style="blue"
        ))
        
        if result.deduplication:
            if result.deduplication.is_duplicate:
                console.print(f"[yellow]🔁 Duplicate of #{result.deduplication.canonical_item.item_number}[/yellow]")
            else:
                console.print(f"[green]✅ {result.executive_summary}[/green]")
        
        console.print(f"[bold]Recommended Action:[/bold] {result.recommended_action}")
    
    asyncio.run(run())


@app.command()
def batch(
    repo: str | None = typer.Option(None, "--repo", "-r", help="Repository (owner/repo)"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of PRs to analyze"),
    since: str | None = typer.Option(None, "--since", "-s", help="Only PRs updated since (e.g., '24h', '7d')"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file for results"),
):
    """Batch analyze open PRs."""
    repo = get_repo(repo)
    
    async def run():
        if not os.getenv("GITHUB_TOKEN"):
            console.print("[red]Error: GITHUB_TOKEN environment variable required[/red]")
            raise typer.Exit(1)
        
        llm = None
        if os.getenv("ANTHROPIC_API_KEY"):
            llm = LLMClient(provider="anthropic")
        elif os.getenv("OPENAI_API_KEY"):
            llm = LLMClient(provider="openai")
        
        github = GitHubClient()
        orchestrator = TriageOrchestrator(github_client=github, llm_client=llm)
        
        with console.status("[bold green]Fetching open PRs..."):
            prs = await github.list_pull_requests(repo, state="open", per_page=limit)
        
        console.print(f"Found {len(prs)} open PRs. Analyzing...")
        
        results = []
        for i, pr in enumerate(prs, 1):
            with console.status(f"[bold green]Analyzing PR #{pr.number} ({i}/{len(prs)})..."):
                result = await orchestrator.triage_pr(
                    repo=repo,
                    pr_number=pr.number,
                    enable_dedup=True,
                    enable_base_detection=True,
                    enable_review=llm is not None,
                    enable_vision=llm is not None,
                )
                results.append(result)
        
        await orchestrator.close()
        
        # Summary table
        table = Table(title=f"Batch Analysis Results ({len(results)} PRs)")
        table.add_column("PR", style="cyan")
        table.add_column("Title")
        table.add_column("Priority", justify="center")
        table.add_column("Duplicate?")
        table.add_column("Base?")
        table.add_column("Quality")
        
        for r in results:
            pr_data = prs[[p.number for p in prs].index(r.item_number)]
            
            dup = "🔁" if (r.deduplication and r.deduplication.is_duplicate) else ""
            base = "⭐" if (r.base_detection and r.base_detection.is_base_candidate) else ""
            quality = f"{r.deep_review.overall_quality:.0%}" if r.deep_review else "-"
            
            priority_color = {
                "urgent": "red",
                "high": "yellow",
                "normal": "white",
                "low": "dim",
            }.get(r.priority, "white")
            
            table.add_row(
                f"#{r.item_number}",
                pr_data.title[:40] + "..." if len(pr_data.title) > 40 else pr_data.title,
                f"[{priority_color}]{r.priority.upper()}[/{priority_color}]",
                dup,
                base,
                quality,
            )
        
        console.print(table)
        
        # Save results
        if output:
            output_data = [r.model_dump() for r in results]
            output.write_text(json.dumps(output_data, indent=2, default=str))
            console.print(f"[green]Results saved to {output}[/green]")
    
    asyncio.run(run())


@app.command()
def init_config(
    path: Path = typer.Option("config.yaml", "--path", "-p", help="Config file path"),
):
    """Initialize a new configuration file."""
    settings = Settings()
    settings.to_yaml(path)
    console.print(f"[green]Configuration written to {path}[/green]")


@app.command()
def server(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the API server."""
    import uvicorn
    
    # This would require the api module to be implemented
    console.print("[yellow]API server not yet implemented[/yellow]")
    console.print("Use 'analyze-pr' or 'batch' commands for now")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
