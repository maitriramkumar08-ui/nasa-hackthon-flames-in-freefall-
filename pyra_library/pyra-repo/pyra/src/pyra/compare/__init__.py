"""Observation operators and status-aware comparison metrics."""

from pyra.compare.evaluation import ModelEvaluation, evaluate_model
from pyra.compare.metrics import bias, relative_difference, z_score
from pyra.compare.operators import first_order_lag

__all__ = [
    "ModelEvaluation", "bias", "evaluate_model", "first_order_lag",
    "relative_difference", "z_score",
]
