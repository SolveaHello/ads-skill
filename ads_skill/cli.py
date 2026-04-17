"""Click CLI entry point for ads-skill."""

import sys

import click

from .display import console


@click.group()
def cli() -> None:
    """Google Ads Skill — view ad performance from your terminal."""


# ---------------------------------------------------------------------------
# auth subcommands
# ---------------------------------------------------------------------------


@cli.group()
def auth() -> None:
    """Manage Google OAuth2 credentials."""


@auth.command("login")
def auth_login() -> None:
    """Start the OAuth2 flow and store a refresh token."""
    from . import auth as _auth

    try:
        _auth.login()
    except KeyboardInterrupt:
        console.print("\n[yellow]Login cancelled.[/yellow]")
        sys.exit(1)


@auth.command("status")
def auth_status() -> None:
    """Show current authentication state (no network call)."""
    from . import auth as _auth
    from .display import show_auth_status

    show_auth_status(_auth.status())


@auth.command("refresh")
def auth_refresh() -> None:
    """Force-refresh the access token now."""
    from . import auth as _auth

    token = _auth.refresh(force=True)
    if token:
        console.print("[green]✓ Access token refreshed successfully.[/green]")
    else:
        console.print(
            "[red]Refresh failed — no stored refresh token. Run: ads-skill auth login[/red]"
        )
        sys.exit(1)


@auth.command("logout")
def auth_logout() -> None:
    """Remove all stored credentials."""
    from .config import clear_tokens

    removed = clear_tokens()
    if removed:
        for p in removed:
            console.print(f"[green]Removed:[/green] {p}")
    else:
        console.print("[yellow]No credentials found.[/yellow]")


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------


@cli.command("accounts")
@click.option("--mcc", default=None, help="MCC customer ID to use as login customer.")
def accounts(mcc: str | None) -> None:
    """List all accessible Google Ads accounts."""
    from .client import get_client, get_customer_info, list_accessible_customers
    from .display import show_accounts

    _require_auth()
    try:
        from .client import list_child_accounts

        client = get_client(mcc)
        ids = list_accessible_customers(client)
        infos = []
        skipped = []
        for cid in ids:
            try:
                info = get_customer_info(client, cid)
                if not info:
                    continue
                infos.append(info)
                # Auto-expand MCC: list child accounts and tag them
                if info.get("is_manager"):
                    children = list_child_accounts(client, cid)
                    for child in children:
                        child["mcc_id"] = cid
                        infos.append(child)
            except Exception:
                skipped.append(cid)
        show_accounts(infos)
        if skipped:
            console.print(
                f"[dim]Skipped {len(skipped)} inaccessible account(s): {', '.join(skipped)}[/dim]"
            )
    except Exception as e:
        _handle_error(e)


# ---------------------------------------------------------------------------
# campaigns
# ---------------------------------------------------------------------------


@cli.command("campaigns")
@click.option("--account", "-a", required=True, help="Customer ID (digits only).")
@click.option("--mcc", default=None, help="MCC customer ID if required by the account.")
def campaigns(account: str, mcc: str | None) -> None:
    """List campaigns with last-30-day performance."""
    from .client import get_client, get_customer_info, list_campaigns
    from .display import show_campaigns

    _require_auth()
    try:
        client = get_client(mcc)
        info = get_customer_info(client, account) or {}
        rows = list_campaigns(client, account)
        show_campaigns(rows, currency=info.get("currency", "USD"))
    except Exception as e:
        _handle_error(e)


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


@cli.command("summary")
@click.option("--account", "-a", required=True, help="Customer ID (digits only).")
@click.option(
    "--days",
    "-d",
    default="30",
    type=click.Choice(["7", "14", "30"]),
    show_default=True,
    help="Reporting period.",
)
@click.option("--mcc", default=None, help="MCC customer ID if required.")
def summary(account: str, days: str, mcc: str | None) -> None:
    """Show account-level performance summary."""
    from .client import get_account_summary, get_client, get_customer_info
    from .display import show_summary

    _require_auth()
    try:
        client = get_client(mcc)
        info = get_customer_info(client, account) or {}
        data = get_account_summary(client, account, int(days))
        show_summary(
            data,
            account_name=info.get("name") or f"Account {account}",
            days=int(days),
            currency=info.get("currency", "USD"),
        )
    except Exception as e:
        _handle_error(e)


# ---------------------------------------------------------------------------
# export  (feeds claude-ads audit)
# ---------------------------------------------------------------------------


@cli.command("export")
@click.option("--account", "-a", required=True, help="Customer ID (digits only).")
@click.option("--mcc", default=None, help="MCC customer ID if required.")
@click.option(
    "--out",
    "-o",
    default=None,
    help="Output JSON file path (default: ./ads_data/<account>_<date>.json).",
)
def export_data(account: str, mcc: str | None, out: str | None) -> None:
    """Export full account data to JSON for Claude audit."""
    import json
    from datetime import date
    from pathlib import Path

    from .client import (
        export_ad_groups,
        export_ads,
        export_conversion_actions,
        export_keywords,
        export_search_terms,
        get_account_summary,
        get_client,
        get_customer_info,
        list_campaigns,
    )

    _require_auth()
    try:
        client = get_client(mcc)

        console.print(f"[cyan]Fetching account info...[/cyan]")
        info = get_customer_info(client, account) or {}

        console.print(f"[cyan]Fetching campaigns...[/cyan]")
        campaigns = list_campaigns(client, account)

        console.print(f"[cyan]Fetching ad groups...[/cyan]")
        ad_groups = export_ad_groups(client, account)

        console.print(f"[cyan]Fetching keywords...[/cyan]")
        keywords = export_keywords(client, account)

        console.print(f"[cyan]Fetching ads (RSA)...[/cyan]")
        ads = export_ads(client, account)

        console.print(f"[cyan]Fetching search terms...[/cyan]")
        search_terms = export_search_terms(client, account)

        console.print(f"[cyan]Fetching conversion actions...[/cyan]")
        conversions = export_conversion_actions(client, account)

        console.print(f"[cyan]Fetching account summary...[/cyan]")
        summary = get_account_summary(client, account, 30)

        payload = {
            "exported_at": date.today().isoformat(),
            "period": "LAST_30_DAYS",
            "account": info,
            "summary": summary,
            "campaigns": campaigns,
            "ad_groups": ad_groups,
            "keywords": keywords,
            "ads": ads,
            "search_terms": search_terms,
            "conversion_actions": conversions,
        }

        if out:
            dest = Path(out)
        else:
            Path("ads_data").mkdir(exist_ok=True)
            dest = Path(f"ads_data/{account}_{date.today().strftime('%Y%m%d')}.json")

        dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        console.print(f"\n[green]✓ Exported to:[/green] {dest}")
        console.print(
            f"  campaigns={len(campaigns)}, ad_groups={len(ad_groups)}, "
            f"keywords={len(keywords)}, ads={len(ads)}, "
            f"search_terms={len(search_terms)}, conversions={len(conversions)}"
        )
        console.print(
            f"\n[dim]Next step: /ads google — point Claude at {dest} for audit[/dim]"
        )
    except Exception as e:
        _handle_error(e)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_auth() -> None:
    from . import auth as _auth

    s = _auth.status()
    if not s["logged_in"]:
        console.print("[red]Not authenticated.[/red] Run: ads-skill auth login")
        sys.exit(1)


def _handle_error(exc: Exception) -> None:
    try:
        from google.ads.googleads.errors import GoogleAdsException

        if isinstance(exc, GoogleAdsException):
            for err in exc.failure.errors:
                console.print(f"[red]API error:[/red] {err.message}")
            sys.exit(1)
    except ImportError:
        pass
    console.print(f"[red]Error:[/red] {exc}")
    sys.exit(1)
