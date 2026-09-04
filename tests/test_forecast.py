from datetime import datetime, timezone
from decimal import Decimal

import pytest

from eig import Forecast, ForecastStatus, calibration_metrics


def make_forecast():
    return Forecast("f1", "NBIS", "BUY", Decimal("38"), Decimal("45"), Decimal("36"), "one week", datetime.now(timezone.utc), Decimal("0.7"))


def test_forecast_resolution_and_censoring():
    forecast = make_forecast()
    assert forecast.resolve(True, False).status is ForecastStatus.SUCCESS
    assert forecast.resolve(False, False, True).status is ForecastStatus.CENSORED
    with pytest.raises(ValueError):
        forecast.resolve(True, True)


def test_calibration_excludes_censored_forecasts():
    forecasts = (make_forecast().resolve(True, False), make_forecast().resolve(False, True), make_forecast().resolve(False, False, True))
    metrics = calibration_metrics(forecasts)
    assert metrics.count == 2
    assert metrics.brier_score == Decimal("0.29")