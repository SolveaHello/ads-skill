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
# Export queries (for audit / claude-ads integration)
# ---------------------------------------------------------------------------

def export_ad_groups(client: GoogleAdsClient, customer_id: str) -> list[dict]:
    svc = client.get_service("GoogleAdsService")
    query = """
        SELECT
            ad_group.id,
            ad_group.name,
            ad_group.status,
            ad_group.type,
            ad_group.cpc_bid_micros,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM ad_group
        WHERE segments.date DURING LAST_30_DAYS
          AND ad_group.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
        LIMIT 500
    """
    resp = svc.search(customer_id=customer_id, query=query)
    result = []
    for row in resp:
        ag, m = row.ad_group, row.metrics
        result.append({
            "id": str(ag.id),
            "name": ag.name,
            "status": ag.status.name,
            "type": ag.type_.name,
            "cpc_bid": ag.cpc_bid_micros / 1_000_000,
            "campaign_id": str(row.campaign.id),
            "campaign_name": row.campaign.name,
            "impressions": m.impressions,
            "clicks": m.clicks,
            "cost": m.cost_micros / 1_000_000,
            "conversions": m.conversions,
            "ctr": m.ctr * 100,
            "avg_cpc": m.average_cpc / 1_000_000,
        })
    return result


def export_keywords(client: GoogleAdsClient, customer_id: str) -> list[dict]:
    svc = client.get_service("GoogleAdsService")
    query = """
        SELECT
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.status,
            ad_group_criterion.quality_info.quality_score,
            ad_group_criterion.quality_info.creative_quality_score,
            ad_group_criterion.quality_info.post_click_quality_score,
            ad_group_criterion.quality_info.search_predicted_ctr,
            ad_group_criterion.cpc_bid_micros,
            ad_group.id,
            ad_group.name,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc,
            metrics.search_impression_share
        FROM keyword_view
        WHERE segments.date DURING LAST_30_DAYS
          AND ad_group_criterion.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
        LIMIT 1000
    """
    resp = svc.search(customer_id=customer_id, query=query)
    result = []
    for row in resp:
        kw = row.ad_group_criterion
        qi = kw.quality_info
        m = row.metrics
        result.append({
            "text": kw.keyword.text,
            "match_type": kw.keyword.match_type.name,
            "status": kw.status.name,
            "quality_score": qi.quality_score,
            "creative_quality": qi.creative_quality_score.name,
            "landing_page_quality": qi.post_click_quality_score.name,
            "expected_ctr": qi.search_predicted_ctr.name,
            "cpc_bid": kw.cpc_bid_micros / 1_000_000,
            "ad_group_id": str(row.ad_group.id),
            "ad_group_name": row.ad_group.name,
            "campaign_id": str(row.campaign.id),
            "campaign_name": row.campaign.name,
            "impressions": m.impressions,
            "clicks": m.clicks,
            "cost": m.cost_micros / 1_000_000,
            "conversions": m.conversions,
            "ctr": m.ctr * 100,
            "avg_cpc": m.average_cpc / 1_000_000,
            "impression_share": m.search_impression_share * 100,
        })
    return result


def export_ads(client: GoogleAdsClient, customer_id: str) -> list[dict]:
    svc = client.get_service("GoogleAdsService")
    query = """
        SELECT
            ad_group_ad.ad.id,
            ad_group_ad.ad.type,
            ad_group_ad.ad.final_urls,
            ad_group_ad.ad.responsive_search_ad.headlines,
            ad_group_ad.ad.responsive_search_ad.descriptions,
            ad_group_ad.status,
            ad_group_ad.ad.name,
            ad_group.id,
            ad_group.name,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM ad_group_ad
        WHERE segments.date DURING LAST_30_DAYS
          AND ad_group_ad.status != 'REMOVED'
        ORDER BY metrics.impressions DESC
        LIMIT 500
    """
    resp = svc.search(customer_id=customer_id, query=query)
    result = []
    for row in resp:
        ad = row.ad_group_ad.ad
        m = row.metrics
        rsa = ad.responsive_search_ad
        headlines = [h.text for h in rsa.headlines] if rsa else []
        descriptions = [d.text for d in rsa.descriptions] if rsa else []
        result.append({
            "id": str(ad.id),
            "type": ad.type_.name,
            "status": row.ad_group_ad.status.name,
            "final_urls": list(ad.final_urls),
            "headlines": headlines,
            "descriptions": descriptions,
            "ad_group_id": str(row.ad_group.id),
            "ad_group_name": row.ad_group.name,
            "campaign_id": str(row.campaign.id),
            "campaign_name": row.campaign.name,
            "impressions": m.impressions,
            "clicks": m.clicks,
            "cost": m.cost_micros / 1_000_000,
            "conversions": m.conversions,
            "ctr": m.ctr * 100,
            "avg_cpc": m.average_cpc / 1_000_000,
        })
    return result


def export_search_terms(client: GoogleAdsClient, customer_id: str) -> list[dict]:
    svc = client.get_service("GoogleAdsService")
    query = """
        SELECT
            search_term_view.search_term,
            search_term_view.status,
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM search_term_view
        WHERE segments.date DURING LAST_30_DAYS
        ORDER BY metrics.cost_micros DESC
        LIMIT 1000
    """
    resp = svc.search(customer_id=customer_id, query=query)
    result = []
    for row in resp:
        st = row.search_term_view
        m = row.metrics
        result.append({
            "search_term": st.search_term,
            "status": st.status.name,
            "campaign_id": str(row.campaign.id),
            "campaign_name": row.campaign.name,
            "ad_group_id": str(row.ad_group.id),
            "ad_group_name": row.ad_group.name,
            "impressions": m.impressions,
            "clicks": m.clicks,
            "cost": m.cost_micros / 1_000_000,
            "conversions": m.conversions,
            "ctr": m.ctr * 100,
            "avg_cpc": m.average_cpc / 1_000_000,
        })
    return result


def export_conversion_actions(client: GoogleAdsClient, customer_id: str) -> list[dict]:
    svc = client.get_service("GoogleAdsService")
    query = """
        SELECT
            conversion_action.id,
            conversion_action.name,
            conversion_action.status,
            conversion_action.type,
            conversion_action.category,
            conversion_action.counting_type,
            conversion_action.tag_snippets
        FROM conversion_action
        WHERE conversion_action.status != 'REMOVED'
    """
    resp = svc.search(customer_id=customer_id, query=query)
    result = []
    for row in resp:
        ca = row.conversion_action
        result.append({
            "id": str(ca.id),
            "name": ca.name,
            "status": ca.status.name,
            "type": ca.type_.name,
            "category": ca.category.name,
            "counting_type": ca.counting_type.name,
            "has_tag": len(ca.tag_snippets) > 0,
        })
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


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def _field_mask(*paths: str):
    from google.protobuf.field_mask_pb2 import FieldMask
    return FieldMask(paths=list(paths))


def _set_campaign_status(
    client: GoogleAdsClient, customer_id: str, campaign_id: str, status_name: str
) -> str:
    svc = client.get_service("CampaignService")
    op = client.get_type("CampaignOperation")
    op.update.resource_name = svc.campaign_path(customer_id, campaign_id)
    # proto-plus enum: CampaignStatusEnum.PAUSED / ENABLED (no nested class)
    op.update.status = getattr(client.enums.CampaignStatusEnum, status_name)
    op.update_mask.CopyFrom(_field_mask("status"))
    resp = svc.mutate_campaigns(customer_id=customer_id, operations=[op])
    return resp.results[0].resource_name


def pause_campaign(client: GoogleAdsClient, customer_id: str, campaign_id: str) -> str:
    return _set_campaign_status(client, customer_id, campaign_id, "PAUSED")


def enable_campaign(client: GoogleAdsClient, customer_id: str, campaign_id: str) -> str:
    return _set_campaign_status(client, customer_id, campaign_id, "ENABLED")


def set_maximize_conversions(
    client: GoogleAdsClient, customer_id: str, campaign_id: str
) -> str:
    svc = client.get_service("CampaignService")
    op = client.get_type("CampaignOperation")
    op.update.resource_name = svc.campaign_path(customer_id, campaign_id)
    # target_cpa_micros = 0 → no CPA target (unconstrained maximize conversions)
    # Using a sub-field leaf path avoids the FIELD_HAS_SUBFIELDS API error.
    op.update.maximize_conversions.target_cpa_micros = 0
    op.update_mask.CopyFrom(
        _field_mask("maximize_conversions.target_cpa_micros")
    )
    resp = svc.mutate_campaigns(customer_id=customer_id, operations=[op])
    return resp.results[0].resource_name


def add_campaign_negative_keywords(
    client: GoogleAdsClient,
    customer_id: str,
    campaign_id: str,
    keywords: list[str],
) -> int:
    """Add exact-match negative keywords to a campaign. Returns count added."""
    svc = client.get_service("CampaignCriterionService")
    campaign_rn = client.get_service("CampaignService").campaign_path(
        customer_id, campaign_id
    )
    # proto-plus enum: KeywordMatchTypeEnum.EXACT (no nested class)
    exact = client.enums.KeywordMatchTypeEnum.EXACT
    ops = []
    for kw in keywords:
        op = client.get_type("CampaignCriterionOperation")
        op.create.campaign = campaign_rn
        op.create.negative = True
        op.create.keyword.text = kw
        op.create.keyword.match_type = exact
        ops.append(op)
    if not ops:
        return 0
    resp = svc.mutate_campaign_criteria(customer_id=customer_id, operations=ops)
    return len(resp.results)
