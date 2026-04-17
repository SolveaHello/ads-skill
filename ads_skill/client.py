"""Google Ads API wrapper — builds the client and executes GAQL queries."""

from __future__ import annotations

from google.ads.googleads.client import GoogleAdsClient

from .config import CLIENT_ID, CLIENT_SECRET, DEVELOPER_TOKEN, load_tokens


def get_client(login_customer_id: str | None = None) -> GoogleAdsClient:
    """Build a GoogleAdsClient from stored tokens.

    The google-ads library internally handles access-token refresh via the
    stored refresh_token whenever a call is made, so no manual refresh is
    needed before each request.
    """
    tokens = load_tokens()
    if not tokens or not tokens.get("refresh_token"):
        raise RuntimeError("Not authenticated. Run: ads-skill auth login")

    cfg: dict = {
        "developer_token": DEVELOPER_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": tokens["refresh_token"],
        "use_proto_plus": True,
    }
    if login_customer_id:
        cfg["login_customer_id"] = login_customer_id.replace("-", "")

    return GoogleAdsClient.load_from_dict(cfg)


# ---------------------------------------------------------------------------
# Account discovery
# ---------------------------------------------------------------------------

def list_accessible_customers(client: GoogleAdsClient) -> list[str]:
    """Return customer IDs the authenticated user can access."""
    svc = client.get_service("CustomerService")
    resp = svc.list_accessible_customers()
    return [r.split("/")[-1] for r in resp.resource_names]


def get_customer_info(client: GoogleAdsClient, customer_id: str) -> dict | None:
    svc = client.get_service("GoogleAdsService")
    query = """
        SELECT
            customer.id,
            customer.descriptive_name,
            customer.currency_code,
            customer.time_zone,
            customer.status,
            customer.manager
        FROM customer
        LIMIT 1
    """
    resp = svc.search(customer_id=customer_id, query=query)
    for row in resp:
        c = row.customer
        return {
            "id": str(c.id),
            "name": c.descriptive_name,
            "currency": c.currency_code,
            "timezone": c.time_zone,
            "status": c.status.name,
            "is_manager": c.manager,
        }
    return None


def list_child_accounts(client: GoogleAdsClient, mcc_id: str) -> list[dict]:
    """Return all non-manager client accounts under an MCC."""
    svc = client.get_service("GoogleAdsService")
    query = """
        SELECT
            customer_client.id,
            customer_client.descriptive_name,
            customer_client.currency_code,
            customer_client.time_zone,
            customer_client.status,
            customer_client.manager,
            customer_client.level
        FROM customer_client
        WHERE customer_client.manager = FALSE
          AND customer_client.status = 'ENABLED'
    """
    resp = svc.search(customer_id=mcc_id, query=query)
    results = []
    for row in resp:
        cc = row.customer_client
        results.append(
            {
                "id": str(cc.id),
                "name": cc.descriptive_name,
                "currency": cc.currency_code,
                "timezone": cc.time_zone,
                "status": cc.status.name,
                "is_manager": False,
                "level": cc.level,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Campaign reporting
# ---------------------------------------------------------------------------

def list_campaigns(client: GoogleAdsClient, customer_id: str) -> list[dict]:
    """Campaigns + last-30-day metrics, sorted by spend descending."""
    svc = client.get_service("GoogleAdsService")
    query = """
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign.bidding_strategy_type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM campaign
        WHERE segments.date DURING LAST_30_DAYS
          AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
        LIMIT 100
    """
    resp = svc.search(customer_id=customer_id, query=query)
    result = []
    for row in resp:
        c, m = row.campaign, row.metrics
        result.append(
            {
                "id": str(c.id),
                "name": c.name,
                "status": c.status.name,
                "channel": c.advertising_channel_type.name,
                "bidding": c.bidding_strategy_type.name,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "cost": m.cost_micros / 1_000_000,
                "conversions": m.conversions,
                "ctr": m.ctr * 100,
                "avg_cpc": m.average_cpc / 1_000_000,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Account-level summary
# ---------------------------------------------------------------------------

_PERIOD_MAP = {7: "LAST_7_DAYS", 14: "LAST_14_DAYS", 30: "LAST_30_DAYS"}


def get_account_summary(
    client: GoogleAdsClient, customer_id: str, days: int = 30
) -> dict:
    period = _PERIOD_MAP.get(days, "LAST_30_DAYS")
    svc = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.ctr,
            metrics.average_cpc,
            metrics.search_impression_share
        FROM customer
        WHERE segments.date DURING {period}
    """
    resp = svc.search(customer_id=customer_id, query=query)
    for row in resp:
        m = row.metrics
        return {
            "impressions": m.impressions,
            "clicks": m.clicks,
            "cost": m.cost_micros / 1_000_000,
            "conversions": m.conversions,
            "conversion_value": m.conversions_value,
            "ctr": m.ctr * 100,
            "avg_cpc": m.average_cpc / 1_000_000,
            "impression_share": m.search_impression_share * 100,
        }
    return {}
