"""Report services for MOZG Analytics."""

from app.services.reports.sales import SalesReportService
from app.services.reports.menu import MenuAnalysisService

__all__ = ["SalesReportService", "MenuAnalysisService"]
