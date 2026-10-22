import time
import datetime
import pytz
from typing import Dict, Any, List, Optional

from backend.app.services.stock_service import StockService
from backend.app.services.technical_analysis_service import TechnicalAnalysisService
from backend.app.services.ml_service import MLService
from backend.app.services.instrument_mapping_service import InstrumentMappingService
from backend.app.utils.helpers import round_num

IST = pytz.timezone('Asia/Kolkata')

# In-memory recommendation cache (TTL: 3 minutes)
_RECOMMENDATION_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 180


class RecommendationService:
    """
    AI Stock Recommendation Engine for StockSense AI.

    Combines quantitative technical indicators (RSI, MACD, MA20, MA50)
    with Machine Learning price forecasts (Linear Regression & Random Forest)
    into a transparent, explainable scoring system that generates:
      - Recommendation: BUY, HOLD, or SELL
      - Signal Score: -100 (Strongest Sell) to +100 (Strongest Buy)
      - Normalized Score: 0 to 100
      - Supporting Indicators Breakdown
      - ML Prediction Details
      - Natural Language Rationale / Explanation
    """

    # Scoring Weights
    WEIGHT_RSI = 20
    WEIGHT_MACD = 20
    WEIGHT_MA20 = 10
    WEIGHT_MA50 = 10
    WEIGHT_MA_ALIGNMENT = 5
    WEIGHT_ML = 35

    @classmethod
    def evaluate_rsi(cls, rsi: Optional[float]) -> Dict[str, Any]:
        """
        Evaluates 14-period RSI (Weight: 20 pts).
        - RSI <= 30: Oversold reversal opportunity (+20)
        - 30 < RSI < 45: Bearish momentum (-5)
        - 45 <= RSI <= 55: Neutral consolidation (0)
        - 55 < RSI < 70: Bullish momentum (+15)
        - RSI >= 70: Overbought risk (-15)
        """
        if rsi is None:
            return {
                'name': 'RSI (14)',
                'value': 'N/A',
                'signal': 'NEUTRAL',
                'score': 0,
                'max_score': cls.WEIGHT_RSI,
                'interpretation': 'RSI data is unavailable.'
            }

        rsi_val = float(rsi)
        if rsi_val <= 30.0:
            score = 20
            signal = 'BULLISH'
            desc = f"Oversold ({rsi_val:.2f} <= 30) - Potential bullish reversal and attractive accumulation zone."
        elif rsi_val < 45.0:
            score = -5
            signal = 'BEARISH'
            desc = f"Subdued momentum ({rsi_val:.2f}) below 50 midline, indicating mild selling pressure."
        elif rsi_val <= 55.0:
            score = 0
            signal = 'NEUTRAL'
            desc = f"Neutral consolidation ({rsi_val:.2f}) around the 50 midline."
        elif rsi_val < 70.0:
            score = 15
            signal = 'BULLISH'
            desc = f"Positive upward momentum ({rsi_val:.2f}) in healthy bullish territory without overextension."
        else:
            score = -15
            signal = 'BEARISH'
            desc = f"Overbought ({rsi_val:.2f} >= 70) - High valuation elevation with increased pullback risk."

        return {
            'name': 'RSI (14)',
            'value': round_num(rsi_val, 2),
            'signal': signal,
            'score': score,
            'max_score': cls.WEIGHT_RSI,
            'interpretation': desc
        }

    @classmethod
    def evaluate_macd(
        cls,
        macd: Optional[float],
        signal_line: Optional[float],
        histogram: Optional[float]
    ) -> Dict[str, Any]:
        """
        Evaluates MACD (12, 26, 9) (Weight: 20 pts).
        - MACD > Signal Line & Hist > 0: Bullish expanding (+20)
        - MACD > Signal Line & Hist <= 0: Bullish slowing (+10)
        - MACD < Signal Line & Hist < 0: Bearish expanding (-20)
        - MACD < Signal Line & Hist >= 0: Bearish slowing (-10)
        """
        if macd is None or signal_line is None:
            return {
                'name': 'MACD (12, 26, 9)',
                'value': 'N/A',
                'signal': 'NEUTRAL',
                'score': 0,
                'max_score': cls.WEIGHT_MACD,
                'interpretation': 'MACD data is unavailable.'
            }

        m_val = float(macd)
        s_val = float(signal_line)
        h_val = float(histogram) if histogram is not None else (m_val - s_val)

        if m_val >= s_val:
            if h_val > 0:
                score = 20
                signal = 'BULLISH'
                desc = f"Bullish momentum (MACD {m_val:.2f} > Signal {s_val:.2f}) with positive expanding histogram (+{h_val:.2f})."
            else:
                score = 10
                signal = 'BULLISH'
                desc = f"Bullish crossover (MACD {m_val:.2f} > Signal {s_val:.2f}), though momentum histogram is narrowing."
        else:
            if h_val < 0:
                score = -20
                signal = 'BEARISH'
                desc = f"Bearish momentum (MACD {m_val:.2f} < Signal {s_val:.2f}) with negative expanding histogram ({h_val:.2f})."
            else:
                score = -10
                signal = 'BEARISH'
                desc = f"Bearish alignment (MACD {m_val:.2f} < Signal {s_val:.2f}), though histogram is narrowing."

        return {
            'name': 'MACD (12, 26, 9)',
            'value': f"MACD: {round_num(m_val, 2)} | Signal: {round_num(s_val, 2)}",
            'signal': signal,
            'score': score,
            'max_score': cls.WEIGHT_MACD,
            'interpretation': desc
        }

    @classmethod
    def evaluate_moving_averages(
        cls,
        price: Optional[float],
        ma20: Optional[float],
        ma50: Optional[float]
    ) -> List[Dict[str, Any]]:
        """
        Evaluates Price vs MA20 (10 pts), Price vs MA50 (10 pts), and MA20 vs MA50 alignment (5 pts).
        Total Weight: 25 pts.
        """
        results = []

        # 1. Price vs MA20
        if price is not None and ma20 is not None:
            p_val = float(price)
            m20_val = float(ma20)
            diff = p_val - m20_val
            pct = (diff / m20_val) * 100 if m20_val else 0.0

            if p_val >= m20_val:
                score_20 = 10
                sig_20 = 'BULLISH'
                desc_20 = f"Price (₹{p_val:.2f}) is trading {pct:+.2f}% above the 20-day MA (₹{m20_val:.2f}), indicating short-term strength."
            else:
                score_20 = -10
                sig_20 = 'BEARISH'
                desc_20 = f"Price (₹{p_val:.2f}) is trading {pct:.2f}% below the 20-day MA (₹{m20_val:.2f}), indicating short-term weakness."

            results.append({
                'name': 'Price vs MA20',
                'value': f"₹{round_num(p_val, 2)} vs ₹{round_num(m20_val, 2)}",
                'signal': sig_20,
                'score': score_20,
                'max_score': cls.WEIGHT_MA20,
                'interpretation': desc_20
            })
        else:
            results.append({
                'name': 'Price vs MA20',
                'value': 'N/A',
                'signal': 'NEUTRAL',
                'score': 0,
                'max_score': cls.WEIGHT_MA20,
                'interpretation': 'MA20 data is unavailable.'
            })

        # 2. Price vs MA50
        if price is not None and ma50 is not None:
            p_val = float(price)
            m50_val = float(ma50)
            diff = p_val - m50_val
            pct = (diff / m50_val) * 100 if m50_val else 0.0

            if p_val >= m50_val:
                score_50 = 10
                sig_50 = 'BULLISH'
                desc_50 = f"Price (₹{p_val:.2f}) is trading {pct:+.2f}% above the 50-day MA (₹{m50_val:.2f}), confirming medium-term trend support."
            else:
                score_50 = -10
                sig_50 = 'BEARISH'
                desc_50 = f"Price (₹{p_val:.2f}) is trading {pct:.2f}% below the 50-day MA (₹{m50_val:.2f}), indicating medium-term resistance."

            results.append({
                'name': 'Price vs MA50',
                'value': f"₹{round_num(p_val, 2)} vs ₹{round_num(m50_val, 2)}",
                'signal': sig_50,
                'score': score_50,
                'max_score': cls.WEIGHT_MA50,
                'interpretation': desc_50
            })
        else:
            results.append({
                'name': 'Price vs MA50',
                'value': 'N/A',
                'signal': 'NEUTRAL',
                'score': 0,
                'max_score': cls.WEIGHT_MA50,
                'interpretation': 'MA50 data is unavailable.'
            })

        # 3. MA20 vs MA50 Alignment
        if ma20 is not None and ma50 is not None:
            m20_val = float(ma20)
            m50_val = float(ma50)

            if m20_val >= m50_val:
                score_align = 5
                sig_align = 'BULLISH'
                desc_align = f"Golden trend alignment: 20-day MA (₹{m20_val:.2f}) is above 50-day MA (₹{m50_val:.2f})."
            else:
                score_align = -5
                sig_align = 'BEARISH'
                desc_align = f"Death trend alignment: 20-day MA (₹{m20_val:.2f}) is below 50-day MA (₹{m50_val:.2f})."

            results.append({
                'name': 'MA Trend Alignment (MA20 vs MA50)',
                'value': f"MA20: ₹{round_num(m20_val, 2)} | MA50: ₹{round_num(m50_val, 2)}",
                'signal': sig_align,
                'score': score_align,
                'max_score': cls.WEIGHT_MA_ALIGNMENT,
                'interpretation': desc_align
            })
        else:
            results.append({
                'name': 'MA Trend Alignment (MA20 vs MA50)',
                'value': 'N/A',
                'signal': 'NEUTRAL',
                'score': 0,
                'max_score': cls.WEIGHT_MA_ALIGNMENT,
                'interpretation': 'Moving average alignment could not be computed.'
            })

        return results

    @classmethod
    def evaluate_ml_prediction(
        cls,
        predicted_price: Optional[float],
        current_price: Optional[float],
        predicted_change_pct: Optional[float],
        best_model: str = "Linear Regression",
        r2_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluates Machine Learning next-day price forecast (Weight: 35 pts).
        - change_pct >= +2.0%: +35 pts (Strong Bullish)
        - +0.75% <= change_pct < +2.0%: +25 pts (Moderate Bullish)
        - +0.20% <= change_pct < +0.75%: +15 pts (Mild Bullish)
        - -0.20% < change_pct < +0.20%: 0 pts (Flat / Neutral)
        - -0.75% < change_pct <= -0.20%: -15 pts (Mild Bearish)
        - -2.0% < change_pct <= -0.75%: -25 pts (Moderate Bearish)
        - change_pct <= -2.0%: -35 pts (Strong Bearish)
        """
        if predicted_price is None or current_price is None or predicted_change_pct is None:
            return {
                'name': 'ML Next-Day Forecast',
                'value': 'N/A',
                'signal': 'NEUTRAL',
                'score': 0,
                'max_score': cls.WEIGHT_ML,
                'interpretation': 'Machine Learning price prediction is unavailable.'
            }

        pct = float(predicted_change_pct)
        pred_p = float(predicted_price)
        cur_p = float(current_price)

        if pct >= 2.0:
            score = 35
            signal = 'BULLISH'
            desc = f"Strong Bullish ML forecast: {best_model} predicts next close of ₹{pred_p:.2f} ({pct:+.2f}% expected gain)."
        elif pct >= 0.75:
            score = 25
            signal = 'BULLISH'
            desc = f"Moderate Bullish ML forecast: {best_model} predicts next close of ₹{pred_p:.2f} ({pct:+.2f}% expected gain)."
        elif pct >= 0.20:
            score = 15
            signal = 'BULLISH'
            desc = f"Mild Bullish ML forecast: {best_model} predicts next close of ₹{pred_p:.2f} ({pct:+.2f}% expected gain)."
        elif pct > -0.20:
            score = 0
            signal = 'NEUTRAL'
            desc = f"Flat / Neutral ML forecast: {best_model} predicts next close of ₹{pred_p:.2f} ({pct:+.2f}% minimal deviation)."
        elif pct > -0.75:
            score = -15
            signal = 'BEARISH'
            desc = f"Mild Bearish ML forecast: {best_model} predicts next close of ₹{pred_p:.2f} ({pct:.2f}% expected decline)."
        elif pct > -2.0:
            score = -25
            signal = 'BEARISH'
            desc = f"Moderate Bearish ML forecast: {best_model} predicts next close of ₹{pred_p:.2f} ({pct:.2f}% expected decline)."
        else:
            score = -35
            signal = 'BEARISH'
            desc = f"Strong Bearish ML forecast: {best_model} predicts next close of ₹{pred_p:.2f} ({pct:.2f}% expected decline)."

        # Dampen score slightly if model test R2 was negative
        if r2_score is not None and r2_score < 0:
            score = int(score * 0.7)
            desc += f" (Note: Test R² {r2_score:.2f} suggests high variance; score adjusted)."

        return {
            'name': 'ML Next-Day Forecast',
            'value': f"₹{round_num(pred_p, 2)} ({pct:+.2f}%)",
            'signal': signal,
            'score': score,
            'max_score': cls.WEIGHT_ML,
            'interpretation': desc
        }

    @classmethod
    def generate_explanation(
        cls,
        symbol: str,
        recommendation: str,
        total_score: int,
        supporting_indicators: List[Dict[str, Any]],
        current_price: Optional[float],
        predicted_price: Optional[float],
        predicted_change_pct: Optional[float],
        best_model: str
    ) -> str:
        """
        Synthesizes a cohesive, factual narrative explaining the recommendation verdict.
        """
        sentiment = "Bullish" if total_score >= 20 else ("Bearish" if total_score <= -20 else "Neutral / Consolidation")
        confidence = "High Conviction" if abs(total_score) >= 50 else ("Moderate Conviction" if abs(total_score) >= 25 else "Neutral Bias")

        bullish_reasons = [i['interpretation'] for i in supporting_indicators if i['signal'] == 'BULLISH']
        bearish_reasons = [i['interpretation'] for i in supporting_indicators if i['signal'] == 'BEARISH']

        price_str = f"₹{current_price:.2f}" if current_price is not None else "market price"

        parts = [
            f"StockSense AI issues a {recommendation} recommendation for {symbol} with a composite signal score of {total_score:+d}/100 ({sentiment}, {confidence})."
        ]

        if recommendation == 'BUY':
            parts.append(f"At the current price of {price_str}, positive technical indicators and ML forward projections outweigh downside risks.")
            if bullish_reasons:
                parts.append("Key bullish drivers: " + " ".join(bullish_reasons[:2]))
            if bearish_reasons:
                parts.append("Risk considerations: " + bearish_reasons[0])
        elif recommendation == 'SELL':
            parts.append(f"At the current price of {price_str}, prevailing technical resistance and negative momentum outweigh short-term recovery signals.")
            if bearish_reasons:
                parts.append("Key bearish factors: " + " ".join(bearish_reasons[:2]))
            if bullish_reasons:
                parts.append("Potential counter-trend factors: " + bullish_reasons[0])
        else:  # HOLD
            parts.append(f"The stock at {price_str} is exhibiting mixed signals or trading within a consolidation range.")
            if bullish_reasons and bearish_reasons:
                parts.append(f"Bullish factor: {bullish_reasons[0]} However, offset by: {bearish_reasons[0]}")
            parts.append("Investors are advised to maintain current positions until a definitive breakout or trend confirmation emerges.")

        if predicted_price is not None and predicted_change_pct is not None:
            parts.append(f"The quantitative {best_model} projects next-day closing price at ₹{predicted_price:.2f} ({predicted_change_pct:+.2f}%).")

        return " ".join(parts)

    @classmethod
    def get_recommendation(
        cls,
        symbol: str,
        tech_data: Optional[Dict[str, Any]] = None,
        ml_data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generates comprehensive AI recommendation for an Indian stock symbol.
        Fetches live technical indicators and ML predictions from existing project services.
        
        Args:
            symbol: NSE/BSE stock ticker (e.g. 'RELIANCE', 'TCS', 'HDFCBANK')
            tech_data: Optional pre-fetched output from TechnicalAnalysisService
            ml_data: Optional pre-fetched output from MLService
            use_cache: Whether to utilize in-memory cache
            
        Returns:
            JSON-serializable recommendation dictionary containing:
            - recommendation: 'BUY' | 'HOLD' | 'SELL'
            - signal_score: int (-100 to +100)
            - normalized_score: float (0.0 to 100.0)
            - explanation: str
            - supporting_indicators: list
            - ml_prediction_information: dict
            - current_stock_price: float
        """
        clean_symbol = InstrumentMappingService.normalize_symbol(symbol)
        cache_key = f"REC_{clean_symbol}"
        now = time.time()

        if use_cache and cache_key in _RECOMMENDATION_CACHE:
            cached = _RECOMMENDATION_CACHE[cache_key]
            if (now - cached['timestamp']) < CACHE_TTL:
                return cached['data']

        now_ist_str = datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')

        # 1. Fetch Technical Analysis data if not provided
        if not tech_data:
            tech_data = TechnicalAnalysisService.calculate_indicators(clean_symbol, period='1y')

        # 2. Fetch ML Prediction data if not provided
        if not ml_data:
            ml_data = MLService.predict(clean_symbol, period='1y')

        # Extract technical indicator values
        latest_tech = tech_data.get('latest', {}) if tech_data else {}
        rsi = latest_tech.get('rsi')
        macd = latest_tech.get('macd')
        macd_signal = latest_tech.get('macd_signal')
        macd_hist = latest_tech.get('macd_histogram')
        ma20 = latest_tech.get('ma_20')
        ma50 = latest_tech.get('ma_50')
        tech_close = latest_tech.get('close')

        # Extract ML prediction values
        ml_status = ml_data.get('status') == 'success' if ml_data else False
        ml_summary = ml_data.get('data_summary', {}) if ml_status else {}
        ml_preds = ml_data.get('predictions', {}) if ml_status else {}
        ml_comp = ml_data.get('comparison', {}) if ml_status else {}

        current_price = ml_summary.get('current_close') or tech_close
        if current_price is None:
            # Fallback to StockService quote
            quote = StockService.get_stock_quote(clean_symbol)
            if quote and quote.get('current_price'):
                current_price = float(quote['current_price'])

        best_model_name = ml_comp.get('best_model_by_rmse', 'Linear Regression')
        selected_model_data = (
            ml_preds.get('random_forest', {})
            if 'Random Forest' in best_model_name
            else ml_preds.get('linear_regression', {})
        )

        ml_pred_price = selected_model_data.get('predicted_close')
        ml_pred_change = selected_model_data.get('predicted_change')
        ml_pred_change_pct = selected_model_data.get('predicted_change_percent')
        ml_direction = selected_model_data.get('direction', 'NEUTRAL')
        ml_metrics = selected_model_data.get('metrics', {})
        ml_r2 = ml_metrics.get('r2_score')

        # 3. Transparent Scoring Calculation
        rsi_eval = cls.evaluate_rsi(rsi)
        macd_eval = cls.evaluate_macd(macd, macd_signal, macd_hist)
        ma_evals = cls.evaluate_moving_averages(current_price, ma20, ma50)
        ml_eval = cls.evaluate_ml_prediction(
            predicted_price=ml_pred_price,
            current_price=current_price,
            predicted_change_pct=ml_pred_change_pct,
            best_model=best_model_name,
            r2_score=ml_r2
        )

        supporting_indicators = [
            rsi_eval,
            macd_eval,
            ma_evals[0],  # Price vs MA20
            ma_evals[1],  # Price vs MA50
            ma_evals[2],  # MA20 vs MA50
            ml_eval       # ML Prediction
        ]

        total_score = sum(item['score'] for item in supporting_indicators)
        # Clamp to [-100, 100]
        total_score = max(-100, min(100, total_score))

        # Normalized score: 0 to 100 (50 is neutral)
        normalized_score = round((total_score + 100) / 2.0, 1)

        # Recommendation decision
        if total_score >= 20:
            recommendation = 'BUY'
        elif total_score <= -20:
            recommendation = 'SELL'
        else:
            recommendation = 'HOLD'

        # Natural Language Explanation
        explanation = cls.generate_explanation(
            symbol=clean_symbol,
            recommendation=recommendation,
            total_score=total_score,
            supporting_indicators=supporting_indicators,
            current_price=current_price,
            predicted_price=ml_pred_price,
            predicted_change_pct=ml_pred_change_pct,
            best_model=best_model_name
        )

        # ML Prediction Information structure
        ml_info = {
            'predicted_price': round_num(ml_pred_price, 2) if ml_pred_price is not None else None,
            'current_price': round_num(current_price, 2) if current_price is not None else None,
            'predicted_change': round_num(ml_pred_change, 2) if ml_pred_change is not None else None,
            'predicted_change_percentage': round_num(ml_pred_change_pct, 2) if ml_pred_change_pct is not None else None,
            'direction': ml_direction,
            'selected_model': best_model_name,
            'metrics': {
                'mae': ml_metrics.get('mae'),
                'rmse': ml_metrics.get('rmse'),
                'r2': ml_metrics.get('r2_score')
            }
        }

        result = {
            'status': 'success',
            'symbol': clean_symbol,
            'recommendation': recommendation,
            'signal_score': total_score,
            'normalized_score': normalized_score,
            'score_range': '[-100, +100]',
            'current_stock_price': round_num(current_price, 2) if current_price is not None else None,
            'explanation': explanation,
            'supporting_indicators': supporting_indicators,
            'ml_prediction_information': ml_info,
            'raw_indicators': {
                'rsi': round_num(rsi, 2) if rsi is not None else None,
                'macd': round_num(macd, 2) if macd is not None else None,
                'macd_signal': round_num(macd_signal, 2) if macd_signal is not None else None,
                'macd_histogram': round_num(macd_hist, 2) if macd_hist is not None else None,
                'ma20': round_num(ma20, 2) if ma20 is not None else None,
                'ma50': round_num(ma50, 2) if ma50 is not None else None
            },
            'timestamp': now_ist_str
        }

        if use_cache:
            _RECOMMENDATION_CACHE[cache_key] = {'data': result, 'timestamp': now}

        return result
