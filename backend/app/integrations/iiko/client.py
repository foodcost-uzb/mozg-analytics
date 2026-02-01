import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class IikoAPIError(Exception):
    """Custom exception for iiko API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class IikoClient:
    """
    Client for iiko Cloud API.

    Documentation: https://api-ru.iiko.services/
    """

    def __init__(self, api_login: str):
        self.api_login = api_login
        self.base_url = settings.IIKO_API_URL
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()

    @property
    def http_client(self) -> httpx.AsyncClient:
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized. Use async context manager.")
        return self._http_client

    async def _ensure_token(self) -> str:
        """Get valid access token, refreshing if needed."""
        if self._token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return self._token

        await self._get_access_token()
        return self._token

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _get_access_token(self) -> None:
        """Get access token from iiko API."""
        response = await self.http_client.post(
            "/api/1/access_token",
            json={"apiLogin": self.api_login},
        )

        if response.status_code != 200:
            raise IikoAPIError(
                f"Failed to get access token: {response.text}",
                status_code=response.status_code,
            )

        data = response.json()
        self._token = data.get("token")
        # iiko tokens are valid for 60 minutes
        self._token_expires_at = datetime.utcnow() + timedelta(minutes=55)

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
    ) -> Any:
        """Make authenticated request to iiko API."""
        token = await self._ensure_token()

        headers = {"Authorization": f"Bearer {token}"}

        response = await self.http_client.request(
            method=method,
            url=endpoint,
            headers=headers,
            json=json_data,
        )

        if response.status_code == 401:
            # Token expired, retry with new token
            self._token = None
            token = await self._ensure_token()
            headers = {"Authorization": f"Bearer {token}"}
            response = await self.http_client.request(
                method=method,
                url=endpoint,
                headers=headers,
                json=json_data,
            )

        if response.status_code >= 400:
            raise IikoAPIError(
                f"API request failed: {response.text}",
                status_code=response.status_code,
            )

        return response.json()

    # ==================== Organizations ====================

    async def get_organizations(self) -> List[Dict]:
        """Get list of organizations available for this API login."""
        data = await self._request(
            "POST",
            "/api/1/organizations",
            json_data={"returnAdditionalInfo": True},
        )
        return data.get("organizations", [])

    # ==================== Menu ====================

    async def get_nomenclature(
        self,
        organization_id: str,
        start_revision: Optional[int] = None,
    ) -> Dict:
        """
        Get menu nomenclature (products, categories, modifiers).

        Args:
            organization_id: iiko organization ID
            start_revision: For incremental sync, get changes since this revision
        """
        request_data = {"organizationId": organization_id}
        if start_revision is not None:
            request_data["startRevision"] = start_revision

        return await self._request(
            "POST",
            "/api/1/nomenclature",
            json_data=request_data,
        )

    # ==================== Employees ====================

    async def get_employees(self, organization_ids: List[str]) -> Dict:
        """Get list of employees."""
        return await self._request(
            "POST",
            "/api/1/employees",
            json_data={"organizationIds": organization_ids},
        )

    # ==================== Orders/Receipts ====================

    async def get_orders_by_period(
        self,
        organization_ids: List[str],
        date_from: datetime,
        date_to: datetime,
    ) -> Dict:
        """
        Get closed orders for a period.

        Note: Maximum period is 31 days.
        """
        return await self._request(
            "POST",
            "/api/1/order/by_table",
            json_data={
                "organizationIds": organization_ids,
                "dateFrom": date_from.strftime("%Y-%m-%d %H:%M:%S"),
                "dateTo": date_to.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    async def get_deliveries_by_period(
        self,
        organization_ids: List[str],
        date_from: datetime,
        date_to: datetime,
    ) -> Dict:
        """
        Get delivery orders for a period.

        Note: Maximum period is 30 days.
        """
        return await self._request(
            "POST",
            "/api/1/deliveries/by_delivery_date_and_status",
            json_data={
                "organizationIds": organization_ids,
                "deliveryDateFrom": date_from.strftime("%Y-%m-%d"),
                "deliveryDateTo": date_to.strftime("%Y-%m-%d"),
                "statuses": ["Closed"],
            },
        )

    # ==================== OLAP Reports ====================

    async def get_olap_columns(self, organization_id: str) -> Dict:
        """Get available OLAP report columns."""
        return await self._request(
            "POST",
            "/api/1/olap/columns",
            json_data={"organizationId": organization_id},
        )

    async def get_olap_report(
        self,
        organization_id: str,
        date_from: datetime,
        date_to: datetime,
        report_type: str = "SALES",
        group_by: Optional[List[str]] = None,
        aggregate_fields: Optional[List[str]] = None,
    ) -> Dict:
        """
        Get OLAP report data.

        Args:
            organization_id: iiko organization ID
            date_from: Start date
            date_to: End date
            report_type: SALES, TRANSACTIONS, etc.
            group_by: Fields to group by
            aggregate_fields: Fields to aggregate
        """
        if group_by is None:
            group_by = ["Department", "DishName"]

        if aggregate_fields is None:
            aggregate_fields = [
                "DishDiscountSum",
                "DishReturnSum",
                "ProductCostBase.ProductCost",
                "DishSum",
                "DishAmount",
            ]

        return await self._request(
            "POST",
            "/api/1/olap",
            json_data={
                "organizationId": organization_id,
                "reportType": report_type,
                "dateFrom": date_from.strftime("%Y-%m-%d"),
                "dateTo": date_to.strftime("%Y-%m-%d"),
                "groupByRowFields": group_by,
                "aggregateFields": aggregate_fields,
            },
        )

    # ==================== Stop Lists ====================

    async def get_stop_list(self, organization_ids: List[str]) -> Dict:
        """Get current stop list (out of stock items)."""
        return await self._request(
            "POST",
            "/api/1/stop_lists",
            json_data={"organizationIds": organization_ids},
        )

    # ==================== Terminals ====================

    async def get_terminal_groups(self, organization_ids: List[str]) -> Dict:
        """Get terminal groups."""
        return await self._request(
            "POST",
            "/api/1/terminal_groups",
            json_data={"organizationIds": organization_ids},
        )
