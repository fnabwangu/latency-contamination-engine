from decimal import Decimal

from eig import Analog, BaseRate, ConvictionFeatures, Fragility, Uncertainty, assess_conviction, bayesian_probability, regularized_logistic, survival_probability


def test_conviction_models_use_base_rates_analogs_and_time():
    base = BaseRate("momentum", 40, 20)
    analogs = (Analog(True, Decimal("0.8"), Decimal("2")), Analog(False, Decimal("0.2"), Decimal("3")))
    assert bayesian_probability(base, analogs) > base.probability
    assert 0 < regularized_logistic(ConvictionFeatures()) < 1
    assert survival_probability(Decimal("2"), Decimal("0.1")) < 1


def test_assessment_separates_uncertainty_and_marks_fragile_ev():
    assessment = assess_conviction(BaseRate("small", 1, 1), (), ConvictionFeatures(time_to_event=Decimal("2")), Decimal("100"), Decimal("100"), uncertainty=Uncertainty(Decimal("0.4"), Decimal("0.4"), Decimal("0.1")))
    assert assessment.probability_range is not None
    assert assessment.uncertainty.model == Decimal("0.4")
    assert assessment.fragility is Fragility.FRAGILE