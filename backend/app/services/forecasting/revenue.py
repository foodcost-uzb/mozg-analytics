"""Revenue Forecasting service using Prophet for MOZG Analytics."""

import uuid
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from prophet import Prophet
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailySales, Venue

logger = logging.getLogger(__name__)


@dataclass
class ForecastPoint:
    """Single forecast data point."""

    date: date
    forecast: Decimal
    lower_bound: Decimal  # 95% confidence interval
    upper_bound: Decimal
    is_actual: bool = False  # True if this is historical data


@dataclass
class ForecastAccuracy:
    """Forecast accuracy metrics."""

    mape: Decimal  # Mean Absolute Percentage Error
    rmse: Decimal  # Root Mean Square Error
    mae: Decimal   # Mean Absolute Error
    r_squared: Decimal  # R² score


@dataclass
class SeasonalComponent:
    """Seasonal decomposition component."""

    name: str  # "weekly", "yearly", "holiday"
    strength: Decimal  # Relative strength 0-1
    pattern: Dict[str, Decimal]  # e.g., {"Monday": 0.85, "Saturday": 1.25}


@dataclass
class TrendComponent:
    """Trend analysis."""

    direction: str  # "up", "down", "stable"
    slope: Decimal  # Daily change
    change_points: List[date]  # Dates where trend changed


@dataclass
class RevenueForecast:
    """Complete revenue forecast result."""

    venue_ids: List[uuid.UUID]
    forecast_start: date
    forecast_end: date
    horizon_days: int

    # Forecast data
    historical: List[ForecastPoint]
    forecast: List[ForecastPoint]

    # Analysis
    accuracy: Optional[ForecastAccuracy]
    seasonality: List[SeasonalComponent]
    trend: TrendComponent

    # Summary
    total_forecast: Decimal
    avg_daily_forecast: Decimal
    growth_percent: Decimal  # vs same period historically

    # Recommendations
    insights: List[str] = field(default_factory=list)


class RevenueForecastService:
    """
    Revenue forecasting service using Facebook Prophet.

    Features:
    - Time series forecasting with seasonality
    - Holiday effects (Russian holidays)
    - Trend detection and changepoints
    - Confidence intervals
    - Accuracy metrics (backtesting)
    """

    # Russian holidays for Prophet
    RUSSIAN_HOLIDAYS = pd.DataFrame({
        'holiday': [
            'new_year', 'new_year', 'new_year', 'new_year', 'new_year',
            'christmas', 'defender_day', 'womens_day',
            'labor_day', 'victory_day', 'russia_day', 'unity_day',
        ],
        'ds': pd.to_datetime([
            '2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04', '2025-01-05',
            '2025-01-07', '2025-02-23', '2025-03-08',
            '2025-05-01', '2025-05-09', '2025-06-12', '2025-11-04',
        ]),
        'lower_window': 0,
        'upper_window': 1,
    })

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_historical_data(
        self,
        venue_ids: List[uuid.UUID],
        days: int = 365,
    ) -> pd.DataFrame:
        """Get historical daily revenue data."""

        date_from = date.today() - timedelta(days=days)

        query = (
            select(
                DailySales.date,
                func.sum(DailySales.total_revenue).label("revenue"),
            )
            .where(
                and_(
                    DailySales.venue_id.in_(venue_ids),
                    DailySales.date >= date_from,
                )
            )
            .group_by(DailySales.date)
            .order_by(DailySales.date)
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return pd.DataFrame(columns=['ds', 'y'])

        data = pd.DataFrame([
            {'ds': row.date, 'y': float(row.revenue)}
            for row in rows
        ])

        return data

    def _prepare_holidays(self, years: List[int]) -> pd.DataFrame:
        """Prepare holiday dataframe for multiple years."""

        holidays_list = []

        base_holidays = [
            ('new_year', 1, 1, 0, 5),
            ('christmas', 1, 7, 0, 1),
            ('defender_day', 2, 23, 0, 1),
            ('womens_day', 3, 8, 0, 1),
            ('labor_day', 5, 1, 0, 1),
            ('victory_day', 5, 9, 0, 1),
            ('russia_day', 6, 12, 0, 1),
            ('unity_day', 11, 4, 0, 1),
        ]

        for year in years:
            for name, month, day, lower, upper in base_holidays:
                try:
                    holidays_list.append({
                        'holiday': name,
                        'ds': pd.Timestamp(year=year, month=month, day=day),
                        'lower_window': lower,
                        'upper_window': upper,
                    })
                except ValueError:
                    continue

        return pd.DataFrame(holidays_list)

    def _create_prophet_model(
        self,
        yearly_seasonality: bool = True,
        weekly_seasonality: bool = True,
        daily_seasonality: bool = False,
        holidays: Optional[pd.DataFrame] = None,
    ) -> Prophet:
        """Create and configure Prophet model."""

        model = Prophet(
            yearly_seasonality=yearly_seasonality,
            weekly_seasonality=weekly_seasonality,
            daily_seasonality=daily_seasonality,
            holidays=holidays,
            changepoint_prior_scale=0.05,  # Flexibility of trend
            seasonality_prior_scale=10.0,
            interval_width=0.95,  # 95% confidence interval
        )

        return model

    def _train_and_forecast(
        self,
        data: pd.DataFrame,
        horizon_days: int,
        holidays: Optional[pd.DataFrame] = None,
    ) -> Tuple[Prophet, pd.DataFrame]:
        """Train Prophet model and generate forecast."""

        model = self._create_prophet_model(holidays=holidays)

        # Suppress Prophet logging
        import logging
        logging.getLogger('prophet').setLevel(logging.WARNING)
        logging.getLogger('cmdstanpy').setLevel(logging.WARNING)

        # Fit model
        model.fit(data)

        # Create future dataframe
        future = model.make_future_dataframe(periods=horizon_days)

        # Generate forecast
        forecast = model.predict(future)

        return model, forecast

    def _calculate_accuracy(
        self,
        actual: pd.Series,
        predicted: pd.Series,
    ) -> ForecastAccuracy:
        """Calculate forecast accuracy metrics using backtesting."""

        # Remove any NaN values
        mask = ~(actual.isna() | predicted.isna())
        actual = actual[mask]
        predicted = predicted[mask]

        if len(actual) == 0:
            return ForecastAccuracy(
                mape=Decimal("0"),
                rmse=Decimal("0"),
                mae=Decimal("0"),
                r_squared=Decimal("0"),
            )

        # MAPE (avoid division by zero)
        mape_values = np.abs((actual - predicted) / actual.replace(0, np.nan)) * 100
        mape = np.nanmean(mape_values)

        # RMSE
        rmse = np.sqrt(np.mean((actual - predicted) ** 2))

        # MAE
        mae = np.mean(np.abs(actual - predicted))

        # R²
        ss_res = np.sum((actual - predicted) ** 2)
        ss_tot = np.sum((actual - actual.mean()) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        return ForecastAccuracy(
            mape=Decimal(str(mape)).quantize(Decimal("0.01")),
            rmse=Decimal(str(rmse)).quantize(Decimal("0.01")),
            mae=Decimal(str(mae)).quantize(Decimal("0.01")),
            r_squared=Decimal(str(max(0, r_squared))).quantize(Decimal("0.001")),
        )

    def _extract_seasonality(
        self,
        model: Prophet,
        forecast: pd.DataFrame,
    ) -> List[SeasonalComponent]:
        """Extract seasonality components from trained model."""

        components = []

        # Weekly seasonality
        if 'weekly' in model.seasonalities:
            weekly_effect = {}
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

            # Get weekly component values
            weekly_df = forecast[['ds', 'weekly']].copy()
            weekly_df['dayofweek'] = weekly_df['ds'].dt.dayofweek

            for i, day in enumerate(days):
                day_values = weekly_df[weekly_df['dayofweek'] == i]['weekly']
                if len(day_values) > 0:
                    weekly_effect[day] = Decimal(str(1 + day_values.mean())).quantize(Decimal("0.01"))

            # Calculate strength (variance of weekly effect)
            if weekly_effect:
                values = list(weekly_effect.values())
                strength = Decimal(str(max(values) - min(values))).quantize(Decimal("0.01"))

                components.append(SeasonalComponent(
                    name="weekly",
                    strength=strength,
                    pattern=weekly_effect,
                ))

        # Yearly seasonality
        if 'yearly' in model.seasonalities:
            yearly_effect = {}
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

            yearly_df = forecast[['ds', 'yearly']].copy()
            yearly_df['month'] = yearly_df['ds'].dt.month

            for i, month in enumerate(months, 1):
                month_values = yearly_df[yearly_df['month'] == i]['yearly']
                if len(month_values) > 0:
                    yearly_effect[month] = Decimal(str(1 + month_values.mean())).quantize(Decimal("0.01"))

            if yearly_effect:
                values = list(yearly_effect.values())
                strength = Decimal(str(max(values) - min(values))).quantize(Decimal("0.01"))

                components.append(SeasonalComponent(
                    name="yearly",
                    strength=strength,
                    pattern=yearly_effect,
                ))

        return components

    def _extract_trend(
        self,
        model: Prophet,
        forecast: pd.DataFrame,
        data: pd.DataFrame,
    ) -> TrendComponent:
        """Extract trend component from trained model."""

        # Get trend values
        trend = forecast['trend'].values

        # Calculate overall slope (daily change)
        if len(trend) > 1:
            slope = (trend[-1] - trend[0]) / len(trend)
        else:
            slope = 0

        # Determine direction
        if slope > 100:  # More than 100 currency units per day
            direction = "up"
        elif slope < -100:
            direction = "down"
        else:
            direction = "stable"

        # Get changepoints
        changepoints = []
        if hasattr(model, 'changepoints') and model.changepoints is not None:
            for cp in model.changepoints:
                changepoints.append(cp.date())

        return TrendComponent(
            direction=direction,
            slope=Decimal(str(slope)).quantize(Decimal("0.01")),
            change_points=changepoints[:5],  # Top 5 changepoints
        )

    def _generate_insights(
        self,
        forecast_result: 'RevenueForecast',
        data: pd.DataFrame,
    ) -> List[str]:
        """Generate actionable insights from forecast."""

        insights = []

        # Growth insight
        if forecast_result.growth_percent > 10:
            insights.append(
                f"📈 Прогнозируется рост выручки на {forecast_result.growth_percent}% — "
                "подготовить запасы и персонал"
            )
        elif forecast_result.growth_percent < -10:
            insights.append(
                f"📉 Прогнозируется снижение на {abs(forecast_result.growth_percent)}% — "
                "рассмотреть маркетинговые акции"
            )

        # Trend insight
        if forecast_result.trend.direction == "up":
            insights.append(
                f"📊 Позитивный тренд: +{forecast_result.trend.slope}/день — "
                "бизнес растёт"
            )
        elif forecast_result.trend.direction == "down":
            insights.append(
                f"⚠️ Негативный тренд: {forecast_result.trend.slope}/день — "
                "требуется анализ причин"
            )

        # Weekly seasonality insight
        for component in forecast_result.seasonality:
            if component.name == "weekly" and component.pattern:
                best_day = max(component.pattern.items(), key=lambda x: x[1])
                worst_day = min(component.pattern.items(), key=lambda x: x[1])

                insights.append(
                    f"📅 Лучший день: {best_day[0]} (индекс {best_day[1]}), "
                    f"худший: {worst_day[0]} (индекс {worst_day[1]})"
                )

        # Accuracy insight
        if forecast_result.accuracy:
            if forecast_result.accuracy.mape < 10:
                insights.append(
                    f"✅ Высокая точность прогноза (MAPE {forecast_result.accuracy.mape}%)"
                )
            elif forecast_result.accuracy.mape > 25:
                insights.append(
                    f"⚠️ Низкая точность прогноза (MAPE {forecast_result.accuracy.mape}%) — "
                    "нужно больше данных"
                )

        return insights[:5]

    async def forecast_revenue(
        self,
        venue_ids: List[uuid.UUID],
        horizon_days: int = 30,
        history_days: int = 365,
    ) -> RevenueForecast:
        """
        Generate revenue forecast using Prophet.

        Args:
            venue_ids: List of venue UUIDs to forecast
            horizon_days: Number of days to forecast (default 30)
            history_days: Days of historical data to use (default 365)

        Returns:
            RevenueForecast with predictions and analysis
        """

        # Get historical data
        data = await self.get_historical_data(venue_ids, history_days)

        if len(data) < 30:
            raise ValueError("Insufficient data for forecasting. Need at least 30 days.")

        # Prepare holidays
        years = list(range(data['ds'].min().year, date.today().year + 2))
        holidays = self._prepare_holidays(years)

        # Train and forecast
        model, forecast_df = self._train_and_forecast(data, horizon_days, holidays)

        # Split into historical and forecast
        historical_points = []
        forecast_points = []

        last_actual_date = data['ds'].max()

        for _, row in forecast_df.iterrows():
            point = ForecastPoint(
                date=row['ds'].date(),
                forecast=Decimal(str(max(0, row['yhat']))).quantize(Decimal("0.01")),
                lower_bound=Decimal(str(max(0, row['yhat_lower']))).quantize(Decimal("0.01")),
                upper_bound=Decimal(str(max(0, row['yhat_upper']))).quantize(Decimal("0.01")),
                is_actual=row['ds'] <= last_actual_date,
            )

            if row['ds'] <= last_actual_date:
                historical_points.append(point)
            else:
                forecast_points.append(point)

        # Calculate accuracy (on last 30 days of historical data)
        backtest_data = data.tail(30)
        backtest_forecast = forecast_df[forecast_df['ds'].isin(backtest_data['ds'])]

        accuracy = self._calculate_accuracy(
            backtest_data.set_index('ds')['y'],
            backtest_forecast.set_index('ds')['yhat'],
        )

        # Extract components
        seasonality = self._extract_seasonality(model, forecast_df)
        trend = self._extract_trend(model, forecast_df, data)

        # Calculate summary
        total_forecast = sum(p.forecast for p in forecast_points)
        avg_daily = total_forecast / len(forecast_points) if forecast_points else Decimal("0")

        # Compare with same period historically
        historical_avg = Decimal(str(data['y'].mean()))
        growth_percent = (
            ((avg_daily - historical_avg) / historical_avg * 100)
            if historical_avg > 0 else Decimal("0")
        ).quantize(Decimal("0.1"))

        result = RevenueForecast(
            venue_ids=venue_ids,
            forecast_start=forecast_points[0].date if forecast_points else date.today(),
            forecast_end=forecast_points[-1].date if forecast_points else date.today(),
            horizon_days=horizon_days,
            historical=historical_points[-90:],  # Last 90 days of history
            forecast=forecast_points,
            accuracy=accuracy,
            seasonality=seasonality,
            trend=trend,
            total_forecast=total_forecast.quantize(Decimal("0.01")),
            avg_daily_forecast=avg_daily.quantize(Decimal("0.01")),
            growth_percent=growth_percent,
        )

        # Generate insights
        result.insights = self._generate_insights(result, data)

        return result

    async def quick_forecast(
        self,
        venue_ids: List[uuid.UUID],
        days: int = 7,
    ) -> List[ForecastPoint]:
        """
        Quick forecast for next N days without full analysis.

        Useful for dashboard widgets.
        """

        data = await self.get_historical_data(venue_ids, 90)

        if len(data) < 14:
            # Not enough data - return simple average
            avg = Decimal(str(data['y'].mean())) if len(data) > 0 else Decimal("0")
            return [
                ForecastPoint(
                    date=date.today() + timedelta(days=i),
                    forecast=avg,
                    lower_bound=avg * Decimal("0.8"),
                    upper_bound=avg * Decimal("1.2"),
                )
                for i in range(1, days + 1)
            ]

        # Simple Prophet forecast
        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
        )

        import logging
        logging.getLogger('prophet').setLevel(logging.WARNING)

        model.fit(data)
        future = model.make_future_dataframe(periods=days)
        forecast = model.predict(future)

        # Get only future dates
        future_forecast = forecast[forecast['ds'] > data['ds'].max()]

        return [
            ForecastPoint(
                date=row['ds'].date(),
                forecast=Decimal(str(max(0, row['yhat']))).quantize(Decimal("0.01")),
                lower_bound=Decimal(str(max(0, row['yhat_lower']))).quantize(Decimal("0.01")),
                upper_bound=Decimal(str(max(0, row['yhat_upper']))).quantize(Decimal("0.01")),
            )
            for _, row in future_forecast.iterrows()
        ]
