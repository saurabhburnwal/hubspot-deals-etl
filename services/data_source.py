"""
DLT data source for HubSpot Deals.

Produces one resource, `hubspot_deals`, loaded with write_disposition="merge"
on the compound primary key (_tenant_id, id). Merge (rather than the template's
"replace") is what makes checkpoint resumes and re-runs idempotent: re-reading a
page never duplicates rows and never wipes rows loaded before a pause.

Pagination uses HubSpot's cursor (`paging.next.after`). A checkpoint is written
every N pages (HUBSPOT_CHECKPOINT_INTERVAL), on pause, on cancel, on error and on
completion. See ExtractionService.create_source_with_checkpoints for the rules
about which checkpoints are safe to resume from.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Iterator, List, Optional

import dlt

from config import get_config
from loki_logger import get_logger, log_business_event
from .hubspot_api_service import (
    DEFAULT_DEAL_PROPERTIES,
    HubSpotAPIError,
    HubSpotAPIService,
    HubSpotPermissionError,
)

SERVICE_NAME = "hubspot_deals"
RESOURCE_NAME = "hubspot_deals"

# Fallback HubSpot property types used when the Properties API is unavailable.
# Values are HubSpot "type" values: string | number | date | datetime | bool | enumeration
STATIC_PROPERTY_TYPES: Dict[str, str] = {
    "dealname": "string",
    "amount": "number",
    "dealstage": "enumeration",
    "pipeline": "enumeration",
    "closedate": "datetime",
    "createdate": "datetime",
    "hs_lastmodifieddate": "datetime",
    "dealtype": "enumeration",
    "description": "string",
    "hubspot_owner_id": "enumeration",
    "hs_priority": "enumeration",
    "deal_currency_code": "enumeration",
    "amount_in_home_currency": "number",
    "hs_deal_stage_probability": "number",
    "hs_forecast_amount": "number",
    "hs_forecast_probability": "number",
    "hs_projected_amount": "number",
    "hs_closed_amount": "number",
    "hs_is_closed": "bool",
    "hs_is_closed_won": "bool",
    "days_to_close": "number",
    "hs_next_step": "string",
    "closed_lost_reason": "string",
    "closed_won_reason": "string",
    "hs_analytics_source": "enumeration",
    "num_associated_contacts": "number",
    "num_contacted_notes": "number",
    "num_notes": "number",
    "notes_last_updated": "datetime",
    "hs_object_id": "number",
}

# HubSpot "number" properties that are integral counts/ids -> BIGINT, not NUMERIC
INTEGER_PROPERTIES = {
    "hs_object_id",
    "days_to_close",
    "num_associated_contacts",
    "num_contacted_notes",
    "num_notes",
    "hs_num_associated_deal_splits",
    "hs_num_target_accounts",
}

# Explicit dlt column hints so the table has a stable, typed schema even when a
# column is NULL for every record in the first load.
COLUMN_HINTS: Dict[str, Dict[str, Any]] = {
    "id": {"data_type": "text", "nullable": False},
    "_tenant_id": {"data_type": "text", "nullable": False},
    "dealname": {"data_type": "text"},
    "amount": {"data_type": "decimal", "precision": 18, "scale": 2},
    "dealstage": {"data_type": "text"},
    "pipeline": {"data_type": "text"},
    "closedate": {"data_type": "timestamp"},
    "createdate": {"data_type": "timestamp"},
    "hs_lastmodifieddate": {"data_type": "timestamp"},
    "dealtype": {"data_type": "text"},
    "description": {"data_type": "text"},
    "hubspot_owner_id": {"data_type": "text"},
    "hs_priority": {"data_type": "text"},
    "deal_currency_code": {"data_type": "text"},
    "amount_in_home_currency": {"data_type": "decimal", "precision": 18, "scale": 2},
    "hs_deal_stage_probability": {"data_type": "decimal", "precision": 5, "scale": 4},
    "hs_forecast_amount": {"data_type": "decimal", "precision": 18, "scale": 2},
    "hs_forecast_probability": {"data_type": "decimal", "precision": 5, "scale": 4},
    "hs_projected_amount": {"data_type": "decimal", "precision": 18, "scale": 2},
    "hs_closed_amount": {"data_type": "decimal", "precision": 18, "scale": 2},
    "hs_is_closed": {"data_type": "bool"},
    "hs_is_closed_won": {"data_type": "bool"},
    "days_to_close": {"data_type": "bigint"},
    "hs_next_step": {"data_type": "text"},
    "closed_lost_reason": {"data_type": "text"},
    "closed_won_reason": {"data_type": "text"},
    "hs_analytics_source": {"data_type": "text"},
    "num_associated_contacts": {"data_type": "bigint"},
    "num_contacted_notes": {"data_type": "bigint"},
    "num_notes": {"data_type": "bigint"},
    "notes_last_updated": {"data_type": "timestamp"},
    "hs_object_id": {"data_type": "bigint"},
    "created_at": {"data_type": "timestamp"},
    "updated_at": {"data_type": "timestamp"},
    "archived": {"data_type": "bool"},
    "archived_at": {"data_type": "timestamp"},
    "_scan_id": {"data_type": "text", "nullable": False},
    "_extracted_at": {"data_type": "timestamp", "nullable": False},
    "_page_number": {"data_type": "bigint"},
    "_source_service": {"data_type": "text"},
}


# --------------------------------------------------------------------------- #
# Type conversion helpers
# --------------------------------------------------------------------------- #
def parse_hubspot_datetime(value: Any) -> Optional[datetime]:
    """HubSpot returns ISO-8601 ('2026-12-31T17:00:00Z' / '...123Z') or, for
    some legacy properties, epoch milliseconds. Returns aware UTC datetime."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if s.isdigit():
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_hubspot_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    dt = parse_hubspot_datetime(value)
    if dt:
        return dt.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def parse_decimal(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def parse_int(value: Any) -> Optional[int]:
    d = parse_decimal(value)
    return int(d) if d is not None else None


def parse_bool(value: Any) -> Optional[bool]:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def convert_property(name: str, value: Any, hubspot_type: Optional[str]) -> Any:
    """Convert a raw HubSpot property string into a Python value of the right type."""
    if value is None or value == "":
        return None
    if name in INTEGER_PROPERTIES:
        return parse_int(value)
    if hubspot_type == "number":
        return parse_decimal(value)
    if hubspot_type == "datetime":
        return parse_hubspot_datetime(value)
    if hubspot_type == "date":
        return parse_hubspot_date(value)
    if hubspot_type in ("bool", "boolean"):
        return parse_bool(value)
    return str(value)


def transform_deal(
    record: Dict[str, Any],
    property_types: Dict[str, str],
    tenant_id: str,
    scan_id: str,
    page_number: int,
    extracted_at: datetime,
) -> Dict[str, Any]:
    """
    Flatten a HubSpot deal object into a typed row:
        {id, properties:{...}, createdAt, updatedAt, archived, archivedAt}
      -> {id, <each property as a typed column>, created_at, updated_at,
          archived, archived_at, _tenant_id, _scan_id, _extracted_at, ...}
    """
    props = record.get("properties") or {}
    row: Dict[str, Any] = {"id": str(record.get("id"))}
    for name, raw in props.items():
        # Column names are the HubSpot internal property names (already
        # lowercase snake_case), which keeps rows 1:1 traceable to HubSpot.
        row[name] = convert_property(name, raw, property_types.get(name))

    row["created_at"] = parse_hubspot_datetime(record.get("createdAt"))
    row["updated_at"] = parse_hubspot_datetime(record.get("updatedAt"))
    row["archived"] = bool(record.get("archived", False))
    row["archived_at"] = parse_hubspot_datetime(record.get("archivedAt"))

    # ETL metadata
    row["_tenant_id"] = tenant_id
    row["_scan_id"] = scan_id
    row["_extracted_at"] = extracted_at
    row["_page_number"] = page_number
    row["_source_service"] = SERVICE_NAME
    return row


def _in_date_range(row: Dict[str, Any], date_range: Optional[Dict[str, Any]]) -> bool:
    """Optional client-side filter on deal create date (inclusive, YYYY-MM-DD)."""
    if not date_range:
        return True
    created = row.get("createdate") or row.get("created_at")
    if not created:
        return True
    d = created.date() if isinstance(created, datetime) else created
    start, end = date_range.get("startDate"), date_range.get("endDate")
    if start and d < date.fromisoformat(start):
        return False
    if end and d > date.fromisoformat(end):
        return False
    return True


# --------------------------------------------------------------------------- #
# Source factory
# --------------------------------------------------------------------------- #
def create_data_source(
    job_config: Dict[str, Any],
    auth_config: Dict[str, Any],
    filters: Dict[str, Any],
    checkpoint_callback: Optional[Callable] = None,
    check_cancel_callback: Optional[Callable] = None,
    check_pause_callback: Optional[Callable] = None,
    resume_from: Optional[Dict[str, Any]] = None,
):
    """
    Build the DLT resources for a HubSpot Deals scan.

    Args:
        job_config: must contain organizationId (used as the tenant id)
        auth_config: {"accessToken": "pat-..."} (decrypted)
        filters: {"properties": [...] | ["*"], "includeArchived": bool,
                  "batchSize": 1-100, "dateRange": {...}, "scan_id": ...}
        checkpoint_callback(job_id, checkpoint_dict): persists progress
        check_cancel_callback(job_id) / check_pause_callback(job_id) -> bool
        resume_from: {"cursor", "page_number", "records_processed"} or None
    """
    logger = get_logger(__name__)
    config = get_config()

    access_token = (auth_config or {}).get("accessToken")
    if not access_token:
        raise ValueError("No access token found in auth configuration")

    tenant_id = job_config.get("organizationId")
    if not tenant_id:
        raise ValueError("No organization ID found in job configuration")

    job_id = filters.get("scan_id", job_config.get("scanId", "unknown"))
    page_size = int(filters.get("batchSize") or config.HUBSPOT_PAGE_SIZE)
    page_size = max(1, min(page_size, HubSpotAPIService.MAX_PAGE_SIZE))
    archived = bool(filters.get("includeArchived", False))
    date_range = filters.get("dateRange") or None
    checkpoint_interval = max(1, int(config.HUBSPOT_CHECKPOINT_INTERVAL))
    max_pages = max(1, int(config.HUBSPOT_MAX_PAGES))

    api = HubSpotAPIService(
        base_url=config.HUBSPOT_API_BASE_URL,
        timeout=config.HUBSPOT_API_TIMEOUT,
        rate_limit_requests=config.HUBSPOT_RATE_LIMIT_REQUESTS,
        rate_limit_window_seconds=config.HUBSPOT_RATE_LIMIT_WINDOW_SECONDS,
        max_retries=config.HUBSPOT_MAX_RETRIES,
        retry_backoff_seconds=config.HUBSPOT_RETRY_BACKOFF_SECONDS,
        test_delay_seconds=config.HUBSPOT_TEST_DELAY_SECONDS,
    )

    # Fail fast with a clear message on a bad token / missing scope so the job
    # is marked failed with an actionable error instead of a stack trace.
    creds = api.validate_credentials(access_token)
    if not creds["valid"]:
        raise HubSpotAPIError(f"HubSpot authentication failed: {creds['error']}", status_code=401)
    if not creds["has_deals_scope"]:
        raise HubSpotPermissionError(
            "HubSpot token is missing the crm.objects.deals.read scope", status_code=403
        )

    # Discover property metadata (types) - best effort.
    property_types: Dict[str, str] = dict(STATIC_PROPERTY_TYPES)
    portal_properties: List[str] = []
    try:
        for p in api.get_deal_properties(access_token):
            property_types[p["name"]] = p.get("type", "string")
            portal_properties.append(p["name"])
    except HubSpotAPIError as exc:
        logger.warning(
            "Deal property metadata unavailable; using static type map",
            extra={"operation": "data_source_init", "job_id": job_id, "error": str(exc)},
        )

    requested = filters.get("properties") or []
    if requested == ["*"]:
        properties = portal_properties or list(DEFAULT_DEAL_PROPERTIES)
    else:
        # Defaults first, then any extra requested properties (deduplicated)
        properties = list(dict.fromkeys(list(DEFAULT_DEAL_PROPERTIES) + list(requested)))

    logger.info(
        "Starting HubSpot deals extraction",
        extra={
            "operation": "data_source_init",
            "job_id": job_id,
            "tenant_id": tenant_id,
            "page_size": page_size,
            "property_count": len(properties),
            "include_archived": archived,
            "checkpoint_interval": checkpoint_interval,
            "resuming": bool(resume_from),
        },
    )

    def _checkpoint(phase: str, records: int, cursor: Optional[str], page: int, extra: Dict[str, Any]):
        if not checkpoint_callback:
            return
        try:
            checkpoint_callback(
                job_id,
                {
                    "phase": phase,
                    "records_processed": records,
                    "cursor": cursor,
                    "page_number": page,
                    "batch_size": page_size,
                    "checkpoint_data": {"service": SERVICE_NAME, "tenant_id": tenant_id, **extra},
                },
            )
        except Exception as exc:  # checkpoint failure must not kill extraction
            logger.warning(
                "Failed to save checkpoint",
                extra={"operation": "checkpoint", "job_id": job_id, "phase": phase, "error": str(exc)},
            )

    @dlt.resource(
        name=RESOURCE_NAME,
        write_disposition="merge",
        primary_key=("_tenant_id", "id"),
        columns=COLUMN_HINTS,
    )
    def hubspot_deals() -> Iterator[List[Dict[str, Any]]]:
        """Yield one list of transformed deal rows per HubSpot page."""
        if resume_from:
            after = resume_from.get("cursor")
            page_count = int(resume_from.get("page_number") or 0)
            total_records = int(resume_from.get("records_processed") or 0)
            logger.info(
                "Resuming deals extraction from checkpoint",
                extra={"operation": "data_extraction", "job_id": job_id, "page_number": page_count + 1,
                       "records_processed": total_records},
            )
        else:
            after, page_count, total_records = None, 0, 0

        while page_count < max_pages:
            # ---- cooperative cancel / pause (checked between pages) ----
            if check_cancel_callback and check_cancel_callback(job_id):
                logger.info("Extraction cancelled", extra={"operation": "data_extraction", "job_id": job_id,
                                                           "page_number": page_count})
                _checkpoint("main_data_cancelled", total_records, after, page_count,
                            {"cancellation_reason": "user_requested"})
                return
            if check_pause_callback and check_pause_callback(job_id):
                logger.info("Extraction paused", extra={"operation": "data_extraction", "job_id": job_id,
                                                        "page_number": page_count})
                # `after` is the cursor of the NEXT page to fetch; everything
                # before it has been yielded and will be loaded when this
                # generator returns, so resuming from here is lossless.
                _checkpoint("main_data_paused", total_records, after, page_count,
                            {"pause_reason": "user_requested",
                             "paused_at": datetime.now(timezone.utc).isoformat()})
                return

            try:
                page = api.get_deals(access_token, limit=page_size, after=after,
                                     properties=properties, archived=archived)
            except Exception as exc:
                logger.error(
                    "Error fetching deals page",
                    extra={"operation": "data_extraction", "job_id": job_id,
                           "page_number": page_count + 1, "error": str(exc)},
                    exc_info=True,
                )
                _checkpoint("main_data_error", total_records, after, page_count,
                            {"error": str(exc), "error_page": page_count + 1})
                raise

            extracted_at = datetime.now(timezone.utc)
            rows = [
                transform_deal(rec, property_types, tenant_id, job_id, page_count + 1, extracted_at)
                for rec in page.get("results", [])
            ]
            rows = [r for r in rows if _in_date_range(r, date_range)]
            if rows:
                yield rows

            page_count += 1
            total_records += len(rows)
            next_after = api.next_cursor(page)

            logger.debug(
                "Deals page processed",
                extra={"operation": "data_extraction", "job_id": job_id, "page_number": page_count,
                       "page_records": len(rows), "total_records": total_records},
            )

            if not next_after:
                _checkpoint("main_data_completed", total_records, None, page_count,
                            {"completion_status": "success", "total_pages": page_count,
                             "api_usage": api.get_api_usage()})
                logger.info(
                    "Deals extraction completed",
                    extra={"operation": "data_extraction", "job_id": job_id,
                           "total_records": total_records, "total_pages": page_count},
                )
                log_business_event(logger, "deals_extraction_completed", job_id=job_id,
                                   tenant_id=tenant_id, total_records=total_records)
                return

            if page_count % checkpoint_interval == 0:
                _checkpoint("main_data", total_records, next_after, page_count,
                            {"pages_processed": page_count, "last_page_records": len(rows)})
            after = next_after

        logger.warning(
            "Max page safety limit reached; stopping extraction",
            extra={"operation": "data_extraction", "job_id": job_id, "max_pages": max_pages},
        )
        _checkpoint("main_data_completed", total_records, None, page_count,
                    {"completion_status": "max_pages_reached", "total_pages": page_count})

    return [hubspot_deals]
