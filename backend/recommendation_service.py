"""
StockSense AI - Backend AI Recommendation Service Module

This module exposes the RecommendationService for generating AI recommendations
(BUY, HOLD, SELL) with transparent multi-indicator scoring and natural language explanations.
"""

from backend.app.services.recommendation_service import RecommendationService

__all__ = ['RecommendationService']
