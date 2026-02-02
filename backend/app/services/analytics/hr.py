"""HR Analytics service for MOZG Analytics."""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, extract, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Employee,
    Receipt,
    ReceiptItem,
    Venue,
)


class PerformanceLevel(str, Enum):
    """Employee performance level."""

    TOP = "top"           # Top 20%
    ABOVE_AVG = "above_average"  # 60-80%
    AVERAGE = "average"   # 40-60%
    BELOW_AVG = "below_average"  # 20-40%
    LOW = "low"           # Bottom 20%


class Shift(str, Enum):
    """Work shift."""

    MORNING = "morning"   # 6:00-14:00
    AFTERNOON = "afternoon"  # 14:00-22:00
    EVENING = "evening"   # 22:00-6:00


@dataclass
class EmployeeMetrics:
    """Performance metrics for a single employee."""

    employee_id: uuid.UUID
    employee_name: str
    role: Optional[str]

    # Volume metrics
    total_revenue: Decimal
    total_receipts: int
    total_items: int

    # Efficiency metrics
    avg_check: Decimal
    items_per_receipt: Decimal
    revenue_per_hour: Decimal  # if work hours known

    # Quality metrics
    avg_discount_percent: Decimal  # Lower is better
    return_rate: Decimal  # Percentage of voided items

    # Performance ranking
    performance_level: PerformanceLevel
    rank: int
    percentile: Decimal


@dataclass
class EmployeeComparison:
    """Comparison of employee metrics with average."""

    employee_id: uuid.UUID
    employee_name: str

    revenue_vs_avg: Decimal  # % above/below average
    avg_check_vs_avg: Decimal
    items_per_receipt_vs_avg: Decimal

    strengths: List[str]
    improvements: List[str]


@dataclass
class ShiftAnalysis:
    """Analysis by work shift."""

    shift: Shift
    shift_name: str
    hours: str  # "6:00-14:00"

    total_revenue: Decimal
    total_receipts: int
    avg_check: Decimal
    revenue_percent: Decimal  # % of total

    top_employees: List[str]  # Names of top performers in this shift


@dataclass
class HourlyProductivity:
    """Hourly productivity metrics."""

    hour: int  # 0-23
    avg_revenue: Decimal
    avg_receipts: int
    avg_items: int
    efficiency_index: Decimal  # 100 = average


@dataclass
class TeamMetrics:
    """Team-wide metrics and benchmarks."""

    total_employees: int
    active_employees: int

    # Averages
    avg_revenue_per_employee: Decimal
    avg_receipts_per_employee: Decimal
    avg_check: Decimal
    avg_items_per_receipt: Decimal

    # Distribution
    top_performers_count: int
    avg_performers_count: int
    low_performers_count: int

    # Efficiency
    revenue_per_labor_hour: Decimal
    receipts_per_labor_hour: Decimal


@dataclass
class HRReport:
    """Complete HR Analytics report."""

    period_start: date
    period_end: date
    venue_ids: List[uuid.UUID]

    # Team overview
    team_metrics: TeamMetrics

    # Individual rankings
    employee_rankings: List[EmployeeMetrics]

    # Comparisons
    employee_comparisons: List[EmployeeComparison]

    # Shift analysis
    shift_analysis: List[ShiftAnalysis]

    # Hourly productivity
    hourly_productivity: List[HourlyProductivity]

    # Recommendations
    recommendations: List[str] = field(default_factory=list)


class HRAnalyticsService:
    """
    HR Analytics service.

    Analyzes employee performance including:
    - Sales per employee
    - Average check by employee
    - Productivity metrics
    - Shift performance
    - Employee rankings
    """

    SHIFT_HOURS = {
        Shift.MORNING: (6, 14, "06:00-14:00"),
        Shift.AFTERNOON: (14, 22, "14:00-22:00"),
        Shift.EVENING: (22, 6, "22:00-06:00"),  # Crosses midnight
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_employee_metrics(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[EmployeeMetrics]:
        """Calculate performance metrics for each employee."""

        # Query employee performance
        query = (
            select(
                Employee.id.label("employee_id"),
                Employee.name.label("employee_name"),
                Employee.role.label("role"),
                func.sum(Receipt.total).label("total_revenue"),
                func.count(Receipt.id).label("total_receipts"),
                func.sum(
                    select(func.count(ReceiptItem.id))
                    .where(ReceiptItem.receipt_id == Receipt.id)
                    .correlate(Receipt)
                    .scalar_subquery()
                ).label("total_items"),
                func.avg(Receipt.total).label("avg_check"),
                func.avg(
                    case(
                        (Receipt.subtotal > 0, Receipt.discount_amount / Receipt.subtotal * 100),
                        else_=Decimal("0")
                    )
                ).label("avg_discount_percent"),
            )
            .select_from(Receipt)
            .join(Employee, Receipt.employee_id == Employee.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                    Receipt.is_paid == True,
                )
            )
            .group_by(Employee.id, Employee.name, Employee.role)
            .order_by(func.sum(Receipt.total).desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return []

        # Calculate items per receipt separately
        items_query = (
            select(
                Receipt.employee_id,
                func.count(ReceiptItem.id).label("total_items"),
            )
            .select_from(ReceiptItem)
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                    Receipt.employee_id.isnot(None),
                )
            )
            .group_by(Receipt.employee_id)
        )

        items_result = await self.db.execute(items_query)
        items_by_employee = {row.employee_id: row.total_items for row in items_result.all()}

        # Calculate metrics
        total_count = len(rows)
        metrics_list = []

        for idx, row in enumerate(rows):
            total_revenue = Decimal(str(row.total_revenue or 0))
            total_receipts = int(row.total_receipts or 0)
            total_items = items_by_employee.get(row.employee_id, 0)
            avg_check = Decimal(str(row.avg_check or 0))

            items_per_receipt = (Decimal(str(total_items)) / total_receipts) if total_receipts > 0 else Decimal("0")

            # Calculate percentile (rank-based)
            percentile = Decimal(str((total_count - idx) / total_count * 100))

            # Determine performance level
            if percentile >= 80:
                level = PerformanceLevel.TOP
            elif percentile >= 60:
                level = PerformanceLevel.ABOVE_AVG
            elif percentile >= 40:
                level = PerformanceLevel.AVERAGE
            elif percentile >= 20:
                level = PerformanceLevel.BELOW_AVG
            else:
                level = PerformanceLevel.LOW

            # Estimate work hours (assume 8 hours/day working days)
            work_days = (date_to - date_from).days + 1
            estimated_hours = work_days * 8 * Decimal("0.7")  # 70% utilization
            revenue_per_hour = (total_revenue / estimated_hours) if estimated_hours > 0 else Decimal("0")

            metrics_list.append(EmployeeMetrics(
                employee_id=row.employee_id,
                employee_name=row.employee_name,
                role=row.role,
                total_revenue=total_revenue.quantize(Decimal("0.01")),
                total_receipts=total_receipts,
                total_items=total_items,
                avg_check=avg_check.quantize(Decimal("0.01")),
                items_per_receipt=items_per_receipt.quantize(Decimal("0.01")),
                revenue_per_hour=revenue_per_hour.quantize(Decimal("0.01")),
                avg_discount_percent=Decimal(str(row.avg_discount_percent or 0)).quantize(Decimal("0.1")),
                return_rate=Decimal("0"),  # Would need void data
                performance_level=level,
                rank=idx + 1,
                percentile=percentile.quantize(Decimal("0.1")),
            ))

        return metrics_list

    async def get_employee_comparisons(
        self,
        employee_metrics: List[EmployeeMetrics],
    ) -> List[EmployeeComparison]:
        """Compare each employee to team average."""

        if not employee_metrics:
            return []

        # Calculate averages
        avg_revenue = sum(e.total_revenue for e in employee_metrics) / len(employee_metrics)
        avg_check = sum(e.avg_check for e in employee_metrics) / len(employee_metrics)
        avg_items = sum(e.items_per_receipt for e in employee_metrics) / len(employee_metrics)

        comparisons = []
        for emp in employee_metrics:
            revenue_vs = ((emp.total_revenue - avg_revenue) / avg_revenue * 100) if avg_revenue > 0 else Decimal("0")
            check_vs = ((emp.avg_check - avg_check) / avg_check * 100) if avg_check > 0 else Decimal("0")
            items_vs = ((emp.items_per_receipt - avg_items) / avg_items * 100) if avg_items > 0 else Decimal("0")

            strengths = []
            improvements = []

            if revenue_vs > 10:
                strengths.append("Высокий объём продаж")
            elif revenue_vs < -10:
                improvements.append("Увеличить объём продаж")

            if check_vs > 10:
                strengths.append("Высокий средний чек")
            elif check_vs < -10:
                improvements.append("Работать над увеличением среднего чека")

            if items_vs > 10:
                strengths.append("Хороший допродаж")
            elif items_vs < -10:
                improvements.append("Улучшить допродажи")

            if emp.avg_discount_percent < 5:
                strengths.append("Низкий уровень скидок")
            elif emp.avg_discount_percent > 15:
                improvements.append("Снизить уровень скидок")

            comparisons.append(EmployeeComparison(
                employee_id=emp.employee_id,
                employee_name=emp.employee_name,
                revenue_vs_avg=revenue_vs.quantize(Decimal("0.1")),
                avg_check_vs_avg=check_vs.quantize(Decimal("0.1")),
                items_per_receipt_vs_avg=items_vs.quantize(Decimal("0.1")),
                strengths=strengths or ["Стабильная работа"],
                improvements=improvements or ["Продолжать в том же духе"],
            ))

        return comparisons

    async def analyze_shifts(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[ShiftAnalysis]:
        """Analyze performance by shift."""

        analyses = []

        for shift, (start_hour, end_hour, hours_str) in self.SHIFT_HOURS.items():
            # Build hour condition
            if shift == Shift.EVENING:
                # Evening shift crosses midnight
                hour_condition = (
                    (extract("hour", Receipt.opened_at) >= start_hour) |
                    (extract("hour", Receipt.opened_at) < end_hour)
                )
            else:
                hour_condition = and_(
                    extract("hour", Receipt.opened_at) >= start_hour,
                    extract("hour", Receipt.opened_at) < end_hour,
                )

            query = (
                select(
                    func.sum(Receipt.total).label("revenue"),
                    func.count(Receipt.id).label("receipts"),
                    func.avg(Receipt.total).label("avg_check"),
                )
                .where(
                    and_(
                        Receipt.venue_id.in_(venue_ids),
                        Receipt.opened_at >= date_from,
                        Receipt.opened_at <= date_to,
                        Receipt.is_deleted == False,
                        hour_condition,
                    )
                )
            )

            result = await self.db.execute(query)
            row = result.first()

            revenue = Decimal(str(row.revenue or 0))
            receipts = int(row.receipts or 0)
            avg_check = Decimal(str(row.avg_check or 0))

            # Get top employees for this shift
            top_query = (
                select(
                    Employee.name,
                    func.sum(Receipt.total).label("emp_revenue"),
                )
                .select_from(Receipt)
                .join(Employee, Receipt.employee_id == Employee.id)
                .where(
                    and_(
                        Receipt.venue_id.in_(venue_ids),
                        Receipt.opened_at >= date_from,
                        Receipt.opened_at <= date_to,
                        Receipt.is_deleted == False,
                        hour_condition,
                    )
                )
                .group_by(Employee.name)
                .order_by(func.sum(Receipt.total).desc())
                .limit(3)
            )

            top_result = await self.db.execute(top_query)
            top_employees = [r.name for r in top_result.all()]

            shift_names = {
                Shift.MORNING: "Утренняя смена",
                Shift.AFTERNOON: "Дневная смена",
                Shift.EVENING: "Вечерняя смена",
            }

            analyses.append(ShiftAnalysis(
                shift=shift,
                shift_name=shift_names[shift],
                hours=hours_str,
                total_revenue=revenue.quantize(Decimal("0.01")),
                total_receipts=receipts,
                avg_check=avg_check.quantize(Decimal("0.01")),
                revenue_percent=Decimal("0"),  # Will calculate after
                top_employees=top_employees,
            ))

        # Calculate revenue percentages
        total_revenue = sum(s.total_revenue for s in analyses)
        for analysis in analyses:
            analysis.revenue_percent = (
                (analysis.total_revenue / total_revenue * 100) if total_revenue > 0 else Decimal("0")
            ).quantize(Decimal("0.1"))

        return analyses

    async def get_hourly_productivity(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[HourlyProductivity]:
        """Get productivity by hour of day."""

        query = (
            select(
                extract("hour", Receipt.opened_at).label("hour"),
                func.avg(Receipt.total).label("avg_revenue_per_receipt"),
                func.count(Receipt.id).label("total_receipts"),
            )
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                )
            )
            .group_by(extract("hour", Receipt.opened_at))
            .order_by(extract("hour", Receipt.opened_at))
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return []

        # Count days in period
        days = (date_to - date_from).days + 1

        # Calculate overall average for efficiency index
        total_receipts = sum(r.total_receipts for r in rows)
        avg_receipts_per_hour = total_receipts / len(rows) if rows else 1

        productivity = []
        for row in rows:
            hour = int(row.hour)
            receipts = int(row.total_receipts)
            avg_revenue = Decimal(str(row.avg_revenue_per_receipt or 0))

            # Average per day
            daily_receipts = receipts / days if days > 0 else receipts

            efficiency = (Decimal(str(receipts)) / Decimal(str(avg_receipts_per_hour)) * 100) if avg_receipts_per_hour > 0 else Decimal("100")

            productivity.append(HourlyProductivity(
                hour=hour,
                avg_revenue=avg_revenue.quantize(Decimal("0.01")),
                avg_receipts=int(daily_receipts),
                avg_items=0,  # Would need items query
                efficiency_index=efficiency.quantize(Decimal("0.1")),
            ))

        return productivity

    def calculate_team_metrics(
        self,
        employee_metrics: List[EmployeeMetrics],
    ) -> TeamMetrics:
        """Calculate team-wide metrics."""

        if not employee_metrics:
            return TeamMetrics(
                total_employees=0,
                active_employees=0,
                avg_revenue_per_employee=Decimal("0"),
                avg_receipts_per_employee=Decimal("0"),
                avg_check=Decimal("0"),
                avg_items_per_receipt=Decimal("0"),
                top_performers_count=0,
                avg_performers_count=0,
                low_performers_count=0,
                revenue_per_labor_hour=Decimal("0"),
                receipts_per_labor_hour=Decimal("0"),
            )

        total = len(employee_metrics)
        active = len([e for e in employee_metrics if e.total_receipts > 0])

        avg_revenue = sum(e.total_revenue for e in employee_metrics) / total
        avg_receipts = sum(e.total_receipts for e in employee_metrics) / total
        avg_check = sum(e.avg_check for e in employee_metrics) / total
        avg_items = sum(e.items_per_receipt for e in employee_metrics) / total

        top_count = len([e for e in employee_metrics if e.performance_level in [PerformanceLevel.TOP, PerformanceLevel.ABOVE_AVG]])
        avg_count = len([e for e in employee_metrics if e.performance_level == PerformanceLevel.AVERAGE])
        low_count = len([e for e in employee_metrics if e.performance_level in [PerformanceLevel.BELOW_AVG, PerformanceLevel.LOW]])

        # Revenue per labor hour (estimate)
        total_revenue = sum(e.total_revenue for e in employee_metrics)
        total_receipts = sum(e.total_receipts for e in employee_metrics)
        estimated_hours = active * 160  # ~160 hours/month estimate

        return TeamMetrics(
            total_employees=total,
            active_employees=active,
            avg_revenue_per_employee=avg_revenue.quantize(Decimal("0.01")),
            avg_receipts_per_employee=Decimal(str(avg_receipts)).quantize(Decimal("0.1")),
            avg_check=avg_check.quantize(Decimal("0.01")),
            avg_items_per_receipt=avg_items.quantize(Decimal("0.01")),
            top_performers_count=top_count,
            avg_performers_count=avg_count,
            low_performers_count=low_count,
            revenue_per_labor_hour=(total_revenue / estimated_hours if estimated_hours > 0 else Decimal("0")).quantize(Decimal("0.01")),
            receipts_per_labor_hour=(Decimal(str(total_receipts)) / estimated_hours if estimated_hours > 0 else Decimal("0")).quantize(Decimal("0.01")),
        )

    def generate_recommendations(
        self,
        team_metrics: TeamMetrics,
        employee_metrics: List[EmployeeMetrics],
        shift_analysis: List[ShiftAnalysis],
    ) -> List[str]:
        """Generate HR recommendations."""

        recommendations = []

        # Performance distribution
        if team_metrics.low_performers_count > team_metrics.total_employees * 0.3:
            recommendations.append(
                "⚠️ Высокая доля слабых сотрудников (>30%) — рассмотреть программу обучения"
            )

        if team_metrics.top_performers_count < team_metrics.total_employees * 0.2:
            recommendations.append(
                "📊 Мало топ-исполнителей — внедрить систему мотивации и бонусов"
            )

        # Individual recommendations
        if employee_metrics:
            # Find employees with high receipts but low check
            high_volume_low_check = [
                e for e in employee_metrics
                if e.total_receipts > team_metrics.avg_receipts_per_employee
                and e.avg_check < team_metrics.avg_check * Decimal("0.9")
            ]
            if high_volume_low_check:
                names = ", ".join(e.employee_name for e in high_volume_low_check[:3])
                recommendations.append(
                    f"💡 {names} — обучить техникам апселла для увеличения среднего чека"
                )

            # Find employees with low items per receipt
            low_items = [
                e for e in employee_metrics
                if e.items_per_receipt < team_metrics.avg_items_per_receipt * Decimal("0.8")
            ]
            if low_items:
                names = ", ".join(e.employee_name for e in low_items[:3])
                recommendations.append(
                    f"🛒 {names} — улучшить допродажи, провести тренинг"
                )

        # Shift recommendations
        if shift_analysis:
            weakest_shift = min(shift_analysis, key=lambda s: s.total_revenue)
            strongest_shift = max(shift_analysis, key=lambda s: s.total_revenue)

            if weakest_shift.total_revenue < strongest_shift.total_revenue * Decimal("0.5"):
                recommendations.append(
                    f"📅 {weakest_shift.shift_name} значительно слабее — перераспределить лучших сотрудников"
                )

        return recommendations[:5]

    async def generate_report(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> HRReport:
        """Generate complete HR analytics report."""

        # Get employee metrics
        employee_metrics = await self.get_employee_metrics(venue_ids, date_from, date_to)

        # Get comparisons
        comparisons = await self.get_employee_comparisons(employee_metrics)

        # Team metrics
        team_metrics = self.calculate_team_metrics(employee_metrics)

        # Shift analysis
        shift_analysis = await self.analyze_shifts(venue_ids, date_from, date_to)

        # Hourly productivity
        hourly_productivity = await self.get_hourly_productivity(venue_ids, date_from, date_to)

        # Recommendations
        recommendations = self.generate_recommendations(
            team_metrics, employee_metrics, shift_analysis
        )

        return HRReport(
            period_start=date_from,
            period_end=date_to,
            venue_ids=venue_ids,
            team_metrics=team_metrics,
            employee_rankings=employee_metrics,
            employee_comparisons=comparisons,
            shift_analysis=shift_analysis,
            hourly_productivity=hourly_productivity,
            recommendations=recommendations,
        )
