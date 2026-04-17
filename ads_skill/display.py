"""Rich-powered terminal output helpers."""

import time

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def show_auth_status(s: dict) -> None:
    if not s["logged_in"]:
        console.print(
            Panel(
                "[red]Not logged in.[/red]\nRun: [bold]ads-skill auth login[/bold]",
                title="Auth Status",
                border_style="red",
            )
        )
        return

    lines = ["[green]✓ Logged in[/green]"]

    if s["has_refresh_token"]:
        lines.append("[green]✓ Refresh token present[/green]")
    else:
        lines.append("[red]✗ No refresh token — run: ads-skill auth login[/red]")

    if s["expired"]:
        lines.append(
            "[yellow]⚡ Access token expired — will auto-refresh on next API call[/yellow]"
        )
    else:
        lines.append(
            f"[green]✓ Access token valid ({s['remaining']}s remaining)[/green]"
        )

    console.print(
        Panel("\n".join(lines), title="Auth Status", border_style="green")
    )


def show_accounts(accounts: list[dict]) -> None:
    if not accounts:
        console.print("[yellow]No accessible accounts found.[/yellow]")
        return

    table = Table(title="Accessible Accounts", box=box.ROUNDED, show_lines=True)
    table.add_column("Customer ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Type", justify="center", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Currency", justify="center")
    table.add_column("MCC", style="dim", no_wrap=True)

    for a in accounts:
        sc = "green" if a.get("status") == "ENABLED" else "red"
        kind = "[bold]MCC[/bold]" if a.get("is_manager") else "Client"
        indent = "  └ " if a.get("mcc_id") else ""
        table.add_row(
            a["id"],
            f"{indent}{a.get('name') or '—'}",
            kind,
            f"[{sc}]{a.get('status', '?')}[/{sc}]",
            a.get("currency", ""),
            a.get("mcc_id", ""),
        )
    console.print(table)


def show_campaigns(campaigns: list[dict], currency: str = "USD") -> None:
    if not campaigns:
        console.print("[yellow]No campaigns found.[/yellow]")
        return

    table = Table(
        title=f"Campaigns — Last 30 Days",
        box=box.ROUNDED,
        show_lines=False,
    )
    table.add_column("Name", max_width=36, style="white")
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Channel", style="dim", no_wrap=True)
    table.add_column("Impressions", justify="right", style="cyan")
    table.add_column("Clicks", justify="right", style="cyan")
    table.add_column("CTR%", justify="right")
    table.add_column(f"Cost ({currency})", justify="right", style="yellow")
    table.add_column("Conv.", justify="right", style="green")
    table.add_column("Avg CPC", justify="right")

    status_color = {"ENABLED": "green", "PAUSED": "yellow", "REMOVED": "red"}

    for c in campaigns:
        sc = status_color.get(c["status"], "white")
        ctr_c = "green" if c["ctr"] >= 3 else ("yellow" if c["ctr"] >= 1 else "red")
        table.add_row(
            c["name"],
            f"[{sc}]{c['status']}[/{sc}]",
            c["channel"].replace("_", " ").title(),
            f"{c['impressions']:,}",
            f"{c['clicks']:,}",
            f"[{ctr_c}]{c['ctr']:.2f}%[/{ctr_c}]",
            f"{c['cost']:,.2f}",
            f"{c['conversions']:.1f}",
            f"{c['avg_cpc']:.2f}",
        )
    console.print(table)


def show_summary(
    summary: dict,
    account_name: str,
    days: int,
    currency: str = "USD",
) -> None:
    if not summary:
        console.print("[yellow]No data available for this period.[/yellow]")
        return

    cost = summary.get("cost", 0)
    conv = summary.get("conversions", 0)
    conv_val = summary.get("conversion_value", 0)
    roas = conv_val / cost if cost > 0 else 0
    cpa = cost / conv if conv > 0 else 0

    content = (
        f"[bold]{account_name}[/bold] — Last {days} days\n\n"
        f"Impressions       [cyan]{summary.get('impressions', 0):>14,}[/cyan]\n"
        f"Clicks            [cyan]{summary.get('clicks', 0):>14,}[/cyan]\n"
        f"CTR               [cyan]{summary.get('ctr', 0):>13.2f}%[/cyan]\n"
        f"Avg CPC           [yellow]{currency} {summary.get('avg_cpc', 0):>11.2f}[/yellow]\n"
        f"Cost              [yellow]{currency} {cost:>11.2f}[/yellow]\n"
        f"Conversions       [green]{conv:>14.1f}[/green]\n"
        f"Conv. Value       [green]{currency} {conv_val:>11.2f}[/green]\n"
        f"ROAS              [green]{roas:>14.2f}x[/green]\n"
        f"CPA               [green]{currency} {cpa:>11.2f}[/green]\n"
        f"Impression Share  [blue]{summary.get('impression_share', 0):>13.1f}%[/blue]"
    )
    console.print(Panel(content, title="Account Summary", border_style="blue"))
