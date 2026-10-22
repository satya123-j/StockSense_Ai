import os
import re
import json
import logging
import datetime
import pytz
import requests
from typing import Dict, Any, List, Optional, Tuple

from backend.app.services.instrument_mapping_service import InstrumentMappingService
from backend.app.services.stock_service import StockService
from backend.app.services.technical_analysis_service import TechnicalAnalysisService
from backend.app.services.ml_service import MLService
from backend.app.services.recommendation_service import RecommendationService
from backend.app.utils.helpers import round_num

logger = logging.getLogger(__name__)
IST = pytz.timezone('Asia/Kolkata')


class ChatbotService:
    """
    StockSense AI Chatbot Service.
    
    Provides grounded, context-aware answers to user questions about a currently
    selected Indian stock (NSE/BSE).
    
    Supports:
    1. Real-time context normalization and validation (price, RSI, MACD, MA20/50, ML, recommendation).
    2. Automatic context enrichment using project services if client context is partial.
    3. Strict anti-hallucination guarantees (never invents stock data).
    4. External AI LLM API integration (Google Gemini, OpenAI) via environment variables.
    5. High-precision built-in Quantitative Financial Reasoning Engine (deterministic offline fallback).
    """

    DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
    DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
    REQUEST_TIMEOUT_SECONDS = 12

    # Pre-defined suggested questions for user interaction
    DEFAULT_SUGGESTIONS = [
        "What is the current price?",
        "What is RSI and what does the current value mean?",
        "What is MACD and how is it trending?",
        "What are the MA20 and MA50 moving averages?",
        "What is the ML predicted price for tomorrow?",
        "What is the current AI recommendation?",
        "Why did the system generate this recommendation?"
    ]

    # --------------------------------------------------------------------------
    # Context Normalization & Extraction
    # --------------------------------------------------------------------------

    @classmethod
    def normalize_context(cls, raw_context: Optional[Dict[str, Any]], symbol: str) -> Dict[str, Any]:
        """
        Extracts and normalizes actual available stock metrics from a raw context dict.
        Guarantees consistent keys and ensures no data is hallucinated or invented.
        """
        raw = raw_context or {}
        clean_symbol = InstrumentMappingService.normalize_symbol(symbol)
        comp_name = raw.get('name') or raw.get('company_name') or clean_symbol

        # 1. Current Price & Quote Data
        current_price = None
        for key in ['current_price', 'price', 'close', 'current_stock_price']:
            if key in raw and raw[key] is not None:
                try:
                    current_price = float(raw[key])
                    break
                except (ValueError, TypeError):
                    pass

        if current_price is None and isinstance(raw.get('latest'), dict):
            try:
                current_price = float(raw['latest'].get('close'))
            except (ValueError, TypeError):
                pass

        # Extract open price
        open_price = None
        for key in ['open', 'open_price', 'day_open', 'regularMarketOpen']:
            if key in raw and raw[key] is not None:
                try:
                    open_price = float(raw[key])
                    break
                except (ValueError, TypeError):
                    pass
        open_price = round_num(open_price, 2)

        change = round_num(raw.get('change'), 2)
        change_percent = round_num(raw.get('change_percent') or raw.get('change_percentage'), 2)
        previous_close = round_num(raw.get('previous_close'), 2)
        day_high = round_num(raw.get('day_high'), 2)
        day_low = round_num(raw.get('day_low'), 2)

        # Extract volume
        volume = None
        for key in ['volume', 'trading_volume', 'vol', 'regularMarketVolume']:
            if key in raw and raw[key] is not None:
                try:
                    volume = int(raw[key])
                    break
                except (ValueError, TypeError):
                    try:
                        volume = int(float(raw[key]))
                        break
                    except (ValueError, TypeError):
                        pass

        # Extract 52-week high & low
        w52_high = None
        for key in ['fifty_two_week_high', '52_week_high', 'fiftyTwoWeekHigh']:
            if key in raw and raw[key] is not None:
                try:
                    w52_high = float(raw[key])
                    break
                except (ValueError, TypeError):
                    pass
        w52_high = round_num(w52_high, 2)

        w52_low = None
        for key in ['fifty_two_week_low', '52_week_low', 'fiftyTwoWeekLow']:
            if key in raw and raw[key] is not None:
                try:
                    w52_low = float(raw[key])
                    break
                except (ValueError, TypeError):
                    pass
        w52_low = round_num(w52_low, 2)

        timestamp = raw.get('timestamp')
        exchange = raw.get('exchange', 'NSE')
        currency = raw.get('currency', 'INR')

        # 2. RSI (14-period)
        rsi = None
        for key in ['rsi', 'rsi_14', 'latest_rsi']:
            if key in raw and raw[key] is not None:
                try:
                    rsi = float(raw[key])
                    break
                except (ValueError, TypeError):
                    pass

        if rsi is None:
            if isinstance(raw.get('latest'), dict) and raw['latest'].get('rsi') is not None:
                try:
                    rsi = float(raw['latest']['rsi'])
                except (ValueError, TypeError):
                    pass
            elif isinstance(raw.get('raw_indicators'), dict) and raw['raw_indicators'].get('rsi') is not None:
                try:
                    rsi = float(raw['raw_indicators']['rsi'])
                except (ValueError, TypeError):
                    pass
            elif isinstance(raw.get('summary_indicators'), dict) and raw['summary_indicators'].get('rsi_14') is not None:
                try:
                    rsi = float(raw['summary_indicators']['rsi_14'])
                except (ValueError, TypeError):
                    pass

        rsi = round_num(rsi, 2)

        # 3. MACD Data
        macd_val = None
        macd_signal = None
        macd_hist = None

        raw_macd = raw.get('macd')
        if isinstance(raw_macd, dict):
            macd_val = round_num(raw_macd.get('macd') or raw_macd.get('value'), 2)
            macd_signal = round_num(raw_macd.get('signal') or raw_macd.get('macd_signal'), 2)
            macd_hist = round_num(raw_macd.get('histogram') or raw_macd.get('macd_hist') or raw_macd.get('macd_histogram'), 2)
        elif raw_macd is not None:
            try:
                macd_val = round_num(float(raw_macd), 2)
            except (ValueError, TypeError):
                pass

        if macd_val is None and isinstance(raw.get('latest'), dict):
            latest = raw['latest']
            macd_val = round_num(latest.get('macd'), 2)
            macd_signal = round_num(latest.get('macd_signal'), 2)
            macd_hist = round_num(latest.get('macd_histogram') or latest.get('macd_hist'), 2)

        if macd_val is None and isinstance(raw.get('raw_indicators'), dict):
            raw_ind = raw['raw_indicators']
            macd_val = round_num(raw_ind.get('macd'), 2)
            macd_signal = round_num(raw_ind.get('macd_signal'), 2)
            macd_hist = round_num(raw_ind.get('macd_histogram'), 2)

        if macd_val is not None and macd_signal is not None and macd_hist is None:
            macd_hist = round_num(macd_val - macd_signal, 2)

        # 4. Moving Averages (MA20 & MA50)
        ma20 = None
        ma50 = None
        for k20 in ['ma20', 'ma_20', 'sma_20', 'sma20']:
            if k20 in raw and raw[k20] is not None:
                try:
                    ma20 = float(raw[k20])
                    break
                except (ValueError, TypeError):
                    pass
        for k50 in ['ma50', 'ma_50', 'sma_50', 'sma50']:
            if k50 in raw and raw[k50] is not None:
                try:
                    ma50 = float(raw[k50])
                    break
                except (ValueError, TypeError):
                    pass

        if (ma20 is None or ma50 is None) and isinstance(raw.get('latest'), dict):
            latest = raw['latest']
            if ma20 is None:
                ma20 = latest.get('ma_20') or latest.get('sma20')
            if ma50 is None:
                ma50 = latest.get('ma_50') or latest.get('sma50')

        if (ma20 is None or ma50 is None) and isinstance(raw.get('raw_indicators'), dict):
            raw_ind = raw['raw_indicators']
            if ma20 is None:
                ma20 = raw_ind.get('ma20')
            if ma50 is None:
                ma50 = raw_ind.get('ma50')

        if (ma20 is None or ma50 is None) and isinstance(raw.get('summary_indicators'), dict):
            sum_ind = raw['summary_indicators']
            if ma20 is None:
                ma20 = sum_ind.get('sma_20')
            if ma50 is None:
                ma50 = sum_ind.get('sma_50')

        ma20 = round_num(ma20, 2)
        ma50 = round_num(ma50, 2)

        # 5. Machine Learning Prediction
        ml_pred_price = None
        ml_change = None
        ml_change_pct = None
        ml_direction = None
        ml_model_name = None
        ml_metrics = {}

        raw_ml = raw.get('ml_prediction') or raw.get('ml_prediction_information')
        if isinstance(raw_ml, dict):
            ml_pred_price = round_num(raw_ml.get('predicted_price') or raw_ml.get('predicted_close'), 2)
            ml_change = round_num(raw_ml.get('predicted_change'), 2)
            ml_change_pct = round_num(raw_ml.get('predicted_change_percentage') or raw_ml.get('predicted_change_percent'), 2)
            ml_direction = raw_ml.get('direction')
            ml_model_name = raw_ml.get('selected_model') or raw_ml.get('model_name')
            ml_metrics = raw_ml.get('metrics', {})

        if ml_pred_price is None and raw.get('predicted_price') is not None:
            try:
                ml_pred_price = round_num(float(raw['predicted_price']), 2)
                ml_change_pct = round_num(raw.get('prediction_change_percent') or raw.get('prediction_change_percentage'), 2)
            except (ValueError, TypeError):
                pass

        if ml_pred_price is None and isinstance(raw.get('predictions'), dict):
            ensemble = raw['predictions'].get('ensemble', {})
            rf = raw['predictions'].get('random_forest', {})
            lr = raw['predictions'].get('linear_regression', {})
            target = ensemble or rf or lr
            ml_pred_price = round_num(target.get('predicted_close') or target.get('predicted_price'), 2)
            ml_change = round_num(target.get('predicted_change'), 2)
            ml_change_pct = round_num(target.get('predicted_change_percent'), 2)
            ml_direction = target.get('direction')
            ml_model_name = target.get('model_name') or 'Ensemble'

        if ml_pred_price is not None and current_price is not None:
            if ml_change is None:
                ml_change = round_num(ml_pred_price - current_price, 2)
            if ml_change_pct is None and current_price > 0:
                ml_change_pct = round_num((ml_change / current_price) * 100, 2)
            if not ml_direction:
                ml_direction = 'UP' if ml_change >= 0 else 'DOWN'

        # 6. Recommendation Verdict & Scoring
        rec_verdict = None
        rec_score = None
        rec_norm_score = None
        rec_explanation = None
        rec_supporting = []

        raw_rec = raw.get('recommendation')
        if isinstance(raw_rec, dict):
            rec_verdict = raw_rec.get('recommendation') or raw_rec.get('verdict')
            rec_score = raw_rec.get('signal_score')
            rec_norm_score = raw_rec.get('normalized_score')
            rec_explanation = raw_rec.get('explanation')
            rec_supporting = raw_rec.get('supporting_indicators', [])
        elif isinstance(raw_rec, str):
            rec_verdict = raw_rec.upper()

        if rec_verdict is None and raw.get('recommendation') and isinstance(raw['recommendation'], str):
            rec_verdict = raw['recommendation'].upper()

        if rec_score is None and raw.get('signal_score') is not None:
            rec_score = raw.get('signal_score')
        if rec_norm_score is None and raw.get('normalized_score') is not None:
            rec_norm_score = raw.get('normalized_score')
        if rec_explanation is None and raw.get('explanation'):
            rec_explanation = raw.get('explanation')
        if not rec_supporting and raw.get('supporting_indicators'):
            rec_supporting = raw.get('supporting_indicators', [])

        has_data = any([
            current_price is not None,
            rsi is not None,
            macd_val is not None,
            ma20 is not None,
            ma50 is not None,
            ml_pred_price is not None,
            rec_verdict is not None
        ])

        return {
            'symbol': clean_symbol,
            'company_name': comp_name,
            'current_price': current_price,
            'currency': currency,
            'change': change,
            'change_percent': change_percent,
            'open': open_price,
            'previous_close': previous_close,
            'day_high': day_high,
            'day_low': day_low,
            'volume': volume,
            'fifty_two_week_high': w52_high,
            'fifty_two_week_low': w52_low,
            'timestamp': timestamp,
            'exchange': exchange,
            'rsi': rsi,
            'macd': {
                'macd': macd_val,
                'signal': macd_signal,
                'histogram': macd_hist
            },
            'ma20': ma20,
            'ma50': ma50,
            'ml_prediction': {
                'predicted_price': ml_pred_price,
                'predicted_change': ml_change,
                'predicted_change_percentage': ml_change_pct,
                'direction': ml_direction,
                'selected_model': ml_model_name or 'Machine Learning Regressor',
                'metrics': ml_metrics
            } if ml_pred_price is not None else None,
            'recommendation': {
                'verdict': rec_verdict,
                'signal_score': rec_score,
                'normalized_score': rec_norm_score,
                'explanation': rec_explanation,
                'supporting_indicators': rec_supporting
            } if rec_verdict is not None else None,
            'has_data': has_data
        }

    @classmethod
    def build_stock_context(cls, symbol: str) -> Dict[str, Any]:
        """
        Fetches live/actual context for a stock from existing project services.
        Ensures no invented data is returned; if a service cannot provide data,
        the corresponding fields are set to None.
        """
        clean_symbol = InstrumentMappingService.normalize_symbol(symbol)
        raw_context = {'symbol': clean_symbol}

        # 1. Quote
        try:
            quote = StockService.get_stock_quote(clean_symbol)
            if quote:
                raw_context.update({
                    'current_price': quote.get('current_price'),
                    'name': quote.get('name'),
                    'change': quote.get('change'),
                    'change_percent': quote.get('change_percent'),
                    'open': quote.get('open'),
                    'previous_close': quote.get('previous_close'),
                    'day_high': quote.get('day_high'),
                    'day_low': quote.get('day_low'),
                    'volume': quote.get('volume'),
                    'fifty_two_week_high': quote.get('fifty_two_week_high'),
                    'fifty_two_week_low': quote.get('fifty_two_week_low'),
                    'timestamp': quote.get('timestamp'),
                    'exchange': quote.get('exchange', 'NSE'),
                    'currency': quote.get('currency', 'INR')
                })
        except Exception as e:
            logger.warning(f"[Chatbot] Error fetching quote for {clean_symbol}: {e}")

        # 2. Technical Indicators
        tech_data = None
        try:
            tech_data = TechnicalAnalysisService.calculate_indicators(clean_symbol, period='1y')
            if tech_data and not tech_data.get('error'):
                latest = tech_data.get('latest', {})
                raw_context['latest'] = latest
                raw_context['rsi'] = latest.get('rsi')
                raw_context['macd'] = {
                    'macd': latest.get('macd'),
                    'signal': latest.get('macd_signal'),
                    'histogram': latest.get('macd_histogram')
                }
                raw_context['ma20'] = latest.get('ma_20')
                raw_context['ma50'] = latest.get('ma_50')
                if not raw_context.get('current_price') and latest.get('close'):
                    raw_context['current_price'] = latest.get('close')
        except Exception as e:
            logger.warning(f"[Chatbot] Error fetching technicals for {clean_symbol}: {e}")

        # 3. ML Prediction
        ml_data = None
        try:
            ml_data = MLService.predict(clean_symbol, period='1y')
            if ml_data and ml_data.get('status') == 'success':
                preds = ml_data.get('predictions', {})
                comp = ml_data.get('comparison', {})
                best_model = comp.get('best_model_by_rmse', 'Linear Regression')
                chosen = preds.get('random_forest') if 'Random Forest' in best_model else preds.get('linear_regression')
                if chosen:
                    raw_context['ml_prediction'] = {
                        'predicted_price': chosen.get('predicted_close'),
                        'predicted_change': chosen.get('predicted_change'),
                        'predicted_change_percentage': chosen.get('predicted_change_percent'),
                        'direction': chosen.get('direction'),
                        'selected_model': best_model,
                        'metrics': chosen.get('metrics', {})
                    }
        except Exception as e:
            logger.warning(f"[Chatbot] Error fetching ML prediction for {clean_symbol}: {e}")

        # 4. Recommendation
        try:
            rec = RecommendationService.get_recommendation(
                clean_symbol,
                tech_data=tech_data,
                ml_data=ml_data
            )
            if rec and rec.get('status') == 'success':
                raw_context['recommendation'] = {
                    'verdict': rec.get('recommendation'),
                    'signal_score': rec.get('signal_score'),
                    'normalized_score': rec.get('normalized_score'),
                    'explanation': rec.get('explanation'),
                    'supporting_indicators': rec.get('supporting_indicators', [])
                }
        except Exception as e:
            logger.warning(f"[Chatbot] Error fetching recommendation for {clean_symbol}: {e}")

        return cls.normalize_context(raw_context, clean_symbol)

    # --------------------------------------------------------------------------
    # Provider Selection & Config
    # --------------------------------------------------------------------------

    @classmethod
    def get_active_provider(cls) -> Tuple[str, Optional[str]]:
        """
        Determines the AI provider to use.
        Returns:
            Tuple of (provider_name, api_key_or_none)
            Provider names: 'gemini', 'openai', 'domain_engine'
        """
        forced_provider = os.getenv('CHATBOT_PROVIDER', 'auto').strip().lower()

        gemini_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY') or os.getenv('AI_API_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')

        if forced_provider == 'gemini':
            if gemini_key:
                return 'gemini', gemini_key
            logger.warning("[Chatbot] CHATBOT_PROVIDER set to 'gemini' but GEMINI_API_KEY is missing. Falling back to domain_engine.")
            return 'domain_engine', None

        if forced_provider == 'openai':
            if openai_key:
                return 'openai', openai_key
            logger.warning("[Chatbot] CHATBOT_PROVIDER set to 'openai' but OPENAI_API_KEY is missing. Falling back to domain_engine.")
            return 'domain_engine', None

        if forced_provider == 'offline' or forced_provider == 'domain_engine':
            return 'domain_engine', None

        # Auto mode: prioritize Gemini, then OpenAI, then offline domain engine
        if gemini_key:
            return 'gemini', gemini_key
        if openai_key:
            return 'openai', openai_key

        return 'domain_engine', None

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Returns the current operational status of the chatbot service."""
        provider, has_key = cls.get_active_provider()
        return {
            'is_configured': True,
            'active_provider': provider,
            'external_api_available': provider in ('gemini', 'openai'),
            'gemini_configured': bool(os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')),
            'openai_configured': bool(os.getenv('OPENAI_API_KEY')),
            'supported_queries': cls.DEFAULT_SUGGESTIONS,
            'timestamp': datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')
        }

    # --------------------------------------------------------------------------
    # Prompt Construction
    # --------------------------------------------------------------------------

    @classmethod
    def _build_system_prompt(cls, symbol: str, context: Dict[str, Any], user_portfolio: Optional[Dict[str, Any]] = None) -> str:
        """
        Builds the strict, grounded financial analyst system prompt.
        Ensures the LLM relies exclusively on the provided context without hallucinating.
        """
        ctx_dump = json.dumps(context, indent=2, default=str)
        portfolio_section = ""
        if user_portfolio and user_portfolio.get('authenticated'):
            port_dump = json.dumps(user_portfolio, indent=2, default=str)
            portfolio_section = f"\n=== AUTHENTICATED USER PORTFOLIO & WALLET ===\n{port_dump}\n============================================\n"

        return (
            "You are StockSense AI Assistant, a high-precision quantitative financial analyst specializing in Indian Equities (NSE/BSE).\n"
            f"You are currently analyzing {symbol} ({context.get('company_name', symbol)}).\n\n"
            "=== VERIFIED REAL-TIME QUANTITATIVE CONTEXT ===\n"
            f"{ctx_dump}\n"
            "================================================\n"
            f"{portfolio_section}\n"
            "MANDATORY OPERATIONAL RULES:\n"
            "1. STRICT FACTUAL GROUNDING: Rely EXCLUSIVELY on the verified context above. NEVER invent, fabricate, guess, or extrapolate stock prices, indicators, moving averages, or predictions.\n"
            "2. MISSING DATA HANDLING: If any requested metric (price, RSI, MACD, MA, ML prediction, recommendation) is null, None, or absent, state clearly and transparently that the data point is currently unavailable. Never substitute 52-week low for today's low or previous close for today's low.\n"
            "3. DAY LOW VS 52-WEEK LOW: When asked for today's lowest price, return 'day_low'. Explicitly distinguish it from 'fifty_two_week_low'.\n"
            "4. TECHNICAL ANALYSIS EXPLANATIONS: When asked about indicators (RSI, MACD, MA20/MA50):\n"
            "   - Explain the financial concept concisely and clearly.\n"
            "   - Explain what the stock's actual current reading indicates according to standard quantitative thresholds.\n"
            "5. RECOMMENDATION EXPLANATION: If asked why a recommendation was generated, refer to StockSense AI's multi-factor model:\n"
            "   - RSI momentum (20 pts)\n"
            "   - MACD crossover & histogram (20 pts)\n"
            "   - Moving averages MA20/MA50 and price alignment (25 pts)\n"
            "   - Machine Learning next-day price forecast (35 pts)\n"
            "   - Total score ranges from -100 to +100 (>= +20 is BUY, <= -20 is SELL, between is HOLD).\n"
            "6. PORTFOLIO & TRADING: Answer portfolio and wallet questions using the verified user portfolio context if available. Never execute live or paper trades directly through chat; instruct user to use the Paper Trading dashboard panel.\n"
            "7. FOLLOW-UP QUESTIONS: If the user asks a follow-up like 'What does that mean?' or 'Why?', interpret it based on the preceding message in the conversation history.\n"
            "8. EDUCATIONAL QUESTIONS: Answer educational questions (what is stock market, diversification, ML models, etc.) thoroughly even if stock data is missing.\n"
            "9. TONE & STYLE: Professional, concise, educational, objective, and structured using clean markdown bullet points.\n"
            "10. DISCLAIMER: Always remind the user that StockSense AI provides algorithmic educational analysis and not SEBI-registered financial advisory."
        )

    # --------------------------------------------------------------------------
    # External AI API Integrations (Gemini & OpenAI)
    # --------------------------------------------------------------------------

    @classmethod
    def _call_gemini_api(
        cls,
        api_key: str,
        system_prompt: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """
        Calls Google Gemini API using standard REST requests.
        """
        model = os.getenv('GEMINI_MODEL', cls.DEFAULT_GEMINI_MODEL)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        contents = []
        # Prepend system instruction into the conversation
        contents.append({
            "role": "user",
            "parts": [{"text": f"[SYSTEM INSTRUCTION]\n{system_prompt}\n\nPlease confirm you understand."}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": "Understood. I will strictly adhere to the provided StockSense AI quantitative context and instructions without hallucinating."}]
        })

        if history:
            for item in history[-6:]:  # Keep last 3 turns
                role = "user" if item.get('role') in ('user', 'human') else "model"
                content = item.get('content') or item.get('message') or ""
                if content:
                    contents.append({
                        "role": role,
                        "parts": [{"text": content}]
                    })

        contents.append({
            "role": "user",
            "parts": [{"text": user_message}]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 800
            }
        }

        try:
            resp = requests.post(url, json=payload, timeout=cls.REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts and 'text' in parts[0]:
                        return parts[0]['text'].strip()
            else:
                logger.warning(f"[Chatbot] Gemini API error ({resp.status_code}): {resp.text}")
        except Exception as e:
            logger.warning(f"[Chatbot] Gemini API request exception: {e}")

        return None

    @classmethod
    def _call_openai_api(
        cls,
        api_key: str,
        system_prompt: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[str]:
        """
        Calls OpenAI API using standard REST requests.
        """
        model = os.getenv('OPENAI_MODEL', cls.DEFAULT_OPENAI_MODEL)
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for item in history[-6:]:
                role = "user" if item.get('role') in ('user', 'human') else "assistant"
                content = item.get('content') or item.get('message') or ""
                if content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 800
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=cls.REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get('choices', [])
                if choices:
                    return choices[0].get('message', {}).get('content', '').strip()
            else:
                logger.warning(f"[Chatbot] OpenAI API error ({resp.status_code}): {resp.text}")
        except Exception as e:
            logger.warning(f"[Chatbot] OpenAI API request exception: {e}")

        return None

    # --------------------------------------------------------------------------
    # Built-In Domain Financial Reasoning Engine (Deterministic / Fallback)
    # --------------------------------------------------------------------------

    @classmethod
    def _generate_domain_response(
        cls,
        user_message: str,
        symbol: str,
        context: Dict[str, Any],
        user_portfolio: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generates grounded, comprehensive natural-language responses to user questions
        about the selected stock, technicals, recommendations, ML predictions, portfolio,
        or general financial concepts.
        """
        msg = re.sub(r'[?!.,;:\'"]+$', '', user_message.lower()).strip()
        comp_name = context.get('company_name', symbol)
        current_price = context.get('current_price')
        rsi = context.get('rsi')
        macd_data = context.get('macd', {})
        ma20 = context.get('ma20')
        ma50 = context.get('ma50')
        ml_pred = context.get('ml_prediction')
        rec = context.get('recommendation')

        price_str = f"₹{current_price:,.2f}" if current_price is not None else "N/A"

        # ----------------------------------------------------------------------
        # 1. Follow-up Questions (e.g. "What does that mean?", "Why is that?", "Explain that")
        # ----------------------------------------------------------------------
        if re.search(r'^(what does (that|this|it) mean|what do you mean|explain (that|this)|why is that|can you elaborate|tell me more|what does (that|this|it) indicate|meaning)$', msg) or \
           re.search(r'\b(what does that mean|what does this mean)\b', msg):
            return cls._build_followup_response(symbol, comp_name, context, conversation_history)

        # ----------------------------------------------------------------------
        # 2. General Educational / Conceptual Questions
        # ----------------------------------------------------------------------
        if re.search(r'\b(what is (a |the )?stock market|how does (the )?stock market work|explain (the )?stock market)\b', msg):
            return cls._build_educational_response('stock_market', symbol, comp_name)

        if re.search(r'\b(linear regression (vs|and|or) random forest|difference between linear regression and random forest)\b', msg):
            return cls._build_educational_response('models_comparison', symbol, comp_name)

        if re.search(r'\b(what is diversification|why diversify|explain diversification|portfolio diversification)\b', msg):
            return cls._build_educational_response('diversification', symbol, comp_name)

        if re.search(r'\b(investing (vs|and) paper trading|difference between investing and paper trading|what is paper trading)\b', msg):
            return cls._build_educational_response('investing_vs_paper_trading', symbol, comp_name)

        if re.search(r'\b(what is (a |the )?moving average|moving average concept|explain moving average)\b', msg) and not re.search(r'\b(ma20|ma50|20|50)\b', msg):
            return cls._build_educational_response('moving_average', symbol, comp_name)

        # ----------------------------------------------------------------------
        # 3. Portfolio & Paper Trading Questions (User-specific)
        # ----------------------------------------------------------------------
        # A. Virtual cash balance
        if re.search(r'\b(virtual cash|wallet balance|how much cash|cash available|how much money do i have|my virtual money)\b', msg):
            return cls._build_portfolio_cash_response(user_portfolio)

        # B. What stocks do I own / My portfolio
        if re.search(r'\b(what stocks do i own|which stocks do i own|my holdings|my portfolio|stocks i own|what do i own|list my stocks)\b', msg):
            return cls._build_portfolio_holdings_response(user_portfolio)

        # C. Profit or loss
        if re.search(r'\b(how much profit or loss|profit or loss|my pnl|how much profit|how much loss|portfolio return|portfolio performance)\b', msg):
            return cls._build_portfolio_pnl_response(user_portfolio)

        # D. How many shares of [SYMBOL] do I own
        holding_query = re.search(r'\bhow many shares (?:of (\w+) )?do i own\b', msg) or re.search(r'\bhow much (\w+) do i (?:hold|own)\b', msg)
        if holding_query:
            target_sym = holding_query.group(1) or symbol
            return cls._build_stock_holding_response(target_sym, user_portfolio)

        # E. Purchase cost calculation: "How much would buying two shares cost?"
        if re.search(r'\b(how much would buying|cost of buying|cost for \w+ shares|how much to buy \w+ shares|how much would \w+ shares cost)\b', msg) or \
           re.search(r'\b(cost of \w+ shares|cost to buy \w+ shares)\b', msg):
            return cls._build_trade_cost_response(symbol, comp_name, context, user_message, user_portfolio)

        # F. Why was my BUY transaction rejected?
        if re.search(r'\b(transaction|order|buy)\b.*\b(reject|rejected|fail|failed|error|declined)\b', msg) or \
           re.search(r'\bwhy was my (?:buy )?(?:transaction|order) rejected\b', msg):
            return cls._build_trade_rejection_response(symbol, comp_name, context, user_portfolio)

        # ----------------------------------------------------------------------
        # 4. Market Price Questions
        # ----------------------------------------------------------------------
        # A. Lowest Price Today (Day Low)
        if re.search(r'\b(lowest price|day low|today(\'s)? low|intraday low|low today|lowest price today|what(\'s| is) the lowest price)\b', msg):
            return cls._build_day_low_response(symbol, comp_name, context)

        # B. Highest Price Today (Day High)
        if re.search(r'\b(highest price|day high|today(\'s)? high|intraday high|high today|highest price today|what(\'s| is) the highest price)\b', msg):
            return cls._build_day_high_response(symbol, comp_name, context)

        # C. Opening Price Today (Open)
        if re.search(r'\b(opening price|today(\'s)? open|opened at|open price|at what price did it open)\b', msg):
            return cls._build_open_price_response(symbol, comp_name, context)

        # D. Yesterday's Closing Price (Previous Close)
        if re.search(r'\b(yesterday(\'s)? (closing price|close)|previous close|previous closing price|closed yesterday)\b', msg):
            return cls._build_previous_close_response(symbol, comp_name, context)

        # E. Trading Volume
        if re.search(r'\b(trading volume|volume today|shares traded|how much volume|what is the volume)\b', msg) or \
           (re.search(r'\bvolume\b', msg) and not re.search(r'\brsi|macd|prediction\b', msg)):
            return cls._build_volume_response(symbol, comp_name, context)

        # F. Price Change / Movement today
        if re.search(r'\b(how much has the stock changed|how much did it move|price change|change today|percentage change today|gain or loss today)\b', msg):
            return cls._build_price_change_response(symbol, comp_name, context)

        # G. Is current price above or below MA20 and MA50? (Technical Comparison)
        if re.search(r'\b(above or below|price vs ma|trading above ma|trading below ma|above ma|below ma)\b', msg) and re.search(r'\b(ma20|ma50|moving average)\b', msg):
            return cls._build_price_vs_ma_response(symbol, comp_name, current_price, ma20, ma50)

        # H. Current Market Price (CMP)
        if (re.search(r'\b(current price|stock price|trading price|how much is|price now|price of|cmp|quote)\b', msg) or \
           msg in ['price', 'what is price', 'price?']) and \
           not re.search(r'\b(ma20|ma50|moving average|predicted|prediction|target)\b', msg):
            return cls._build_price_response(symbol, comp_name, context)

        # ----------------------------------------------------------------------
        # 5. Technical Analysis Questions
        # ----------------------------------------------------------------------
        # A. What are MA20 and MA50?
        if re.search(r'\b(ma20|ma50|ma 20|ma 50|sma20|sma50|moving average|moving averages)\b', msg):
            return cls._build_moving_averages_response(symbol, comp_name, current_price, ma20, ma50)

        # C. Is MACD bullish or bearish according to available indicator data?
        if re.search(r'\b(is (the )?macd bullish|is (the )?macd bearish|macd bullish|macd bearish|macd signal|how is macd trending|macd trend|macd momentum)\b', msg):
            return cls._build_macd_trend_response(symbol, comp_name, macd_data)

        # D. What is MACD?
        if re.search(r'\b(what is (the )?macd|explain (the )?macd|define (the )?macd|about (the )?macd|tell me about (the )?macd|moving average convergence)\b', msg):
            return cls._build_macd_response(symbol, comp_name, macd_data)

        # E. Is RSI overbought or oversold / What does RSI indicate?
        if re.search(r'\b(overbought or oversold|is (the )?rsi overbought|is (the )?rsi oversold|what does (the )?rsi indicate|what does (the )?rsi mean|rsi interpretation|rsi status|rsi value mean)\b', msg) or \
           (re.search(r'\brsi\b', msg) and re.search(r'\b(mean|meaning|signify|indicate|interpretation|overbought|oversold)\b', msg)):
            return cls._build_rsi_meaning_response(symbol, comp_name, rsi)

        # F. What is RSI?
        if re.search(r'\b(what is (the )?rsi|explain (the )?rsi|define (the )?rsi|rsi concept|tell me about (the )?rsi|about (the )?rsi|relative strength index)\b', msg):
            return cls._build_what_is_rsi_response(symbol, comp_name, rsi)

        # ----------------------------------------------------------------------
        # 6. Machine Learning Questions
        # ----------------------------------------------------------------------
        # A. Which ML model was selected?
        if re.search(r'\b(which ml model|which model was selected|what model was used|best model|selected model)\b', msg):
            return cls._build_model_selection_response(symbol, comp_name, context)

        # B. What do MAE and RMSE mean?
        if re.search(r'\b(what do mae and rmse mean|what is mae|what is rmse|mean absolute error|root mean squared error|metrics mean)\b', msg):
            return cls._build_model_metrics_response(symbol, comp_name, context)

        # C. How reliable is the prediction?
        if re.search(r'\b(how reliable|prediction accuracy|how accurate is ml|is the prediction accurate|model confidence|r2 score|reliable)\b', msg) and \
           re.search(r'\b(predict|prediction|ml|forecast|model)\b', msg):
            return cls._build_prediction_reliability_response(symbol, comp_name, context)

        # D. Predicted percentage change
        if re.search(r'\b(predicted percentage change|predicted change|predicted pct change|how much will it change)\b', msg):
            return cls._build_ml_prediction_response(symbol, comp_name, current_price, ml_pred)

        # E. What is the predicted next-day price?
        if re.search(r'\b(predicted (?:next-day )?price|price prediction|next-day price|forecast price|predicted close|target price|forecast tomorrow|ml price)\b', msg) or \
           re.search(r'\b(ml|machine learning|predict|prediction|forecast)\b', msg):
            return cls._build_ml_prediction_response(symbol, comp_name, current_price, ml_pred)

        # ----------------------------------------------------------------------
        # 7. BUY / HOLD / SELL & Recommendation Questions
        # ----------------------------------------------------------------------
        # A. Why did the system recommend HOLD / BUY / SELL?
        if re.search(r'\b(why|reason|explain)\b.*\b(recommend|recommendation|buy|sell|hold|verdict)\b', msg) or \
           re.search(r'\b(why did the system generate|why is this (a )?(buy|sell|hold)|why (buy|sell|hold))\b', msg):
            return cls._build_why_recommendation_response(symbol, comp_name, context)

        # B. What factors support the recommendation?
        if re.search(r'\b(what factors support|supporting factors|factors for (buy|sell|hold)|supporting indicators)\b', msg):
            return cls._build_supporting_factors_response(symbol, comp_name, context)

        # C. What does the current analysis suggest about selling?
        if re.search(r'\b(suggest about selling|should i sell now|time to sell|selling pressure|exit signal|suggest selling)\b', msg):
            return cls._build_selling_analysis_response(symbol, comp_name, context)

        # D. Can I buy or hold / Should I buy / sell / hold / Recommendation?
        if re.search(r'\b(can i buy|can i sell|can i hold|should i buy|should i sell|should i hold|buy or hold|hold or sell|buy this stock|recommendation|verdict|signal)\b', msg):
            return cls._build_recommendation_response(symbol, comp_name, context)

        # ----------------------------------------------------------------------
        # 8. Full Overview / Summary
        # ----------------------------------------------------------------------
        if re.search(r'\b(overview|summary|report|analysis|tell me about|how is|performance)\b', msg):
            return cls._build_full_overview_response(symbol, comp_name, context)

        # ----------------------------------------------------------------------
        # 9. Greetings & Capabilities
        # ----------------------------------------------------------------------
        if re.search(r'\b(hello|hi|hey|greetings|help|who are you|what can you do)\b', msg):
            return cls._build_greeting_response(symbol, comp_name, price_str)

        # ----------------------------------------------------------------------
        # 10. Fallback: transparent, non-hallucinated status and clear guidance
        # ----------------------------------------------------------------------
        return cls._build_default_response(symbol, comp_name, context, user_message)

    # --------------------------------------------------------------------------
    # Dedicated Domain Response Builders
    # --------------------------------------------------------------------------

    @classmethod
    def _build_price_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        price = context.get('current_price')
        if price is None:
            return (
                f"The current market price for **{symbol}** ({name}) is currently unavailable from the active market feed.\n\n"
                f"Please verify that the symbol is listed on NSE/BSE or check back when market quotes update."
            )

        change = context.get('change')
        change_pct = context.get('change_percent')
        prev_close = context.get('previous_close')
        day_high = context.get('day_high')
        day_low = context.get('day_low')

        lines = [
            f"### Current Price for {symbol} ({name})",
            f"The latest market price is **₹{price:,.2f}** (NSE/BSE)."
        ]

        if change is not None and change_pct is not None:
            direction_word = "up" if change >= 0 else "down"
            icon = "📈" if change >= 0 else "📉"
            lines.append(f"{icon} Today's movement: **{change:+,.2f} ({change_pct:+.2f}%)** {direction_word} from the previous close.")

        if prev_close is not None:
            lines.append(f"• **Previous Close**: ₹{prev_close:,.2f}")
        if day_high is not None and day_low is not None:
            lines.append(f"• **Day Range**: ₹{day_low:,.2f} – ₹{day_high:,.2f}")

        return "\n\n".join(lines)

    @classmethod
    def _build_day_low_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        day_low = context.get('day_low')
        if day_low is None:
            return (
                f"### Today's Lowest Price for {symbol} ({name})\n\n"
                f"Today's intraday low price for **{symbol}** cannot currently be retrieved from the market data API.\n\n"
                f"Please note that StockSense AI does not substitute previous close or 52-week low values when intraday low data is unavailable."
            )

        curr_price = context.get('current_price')
        day_high = context.get('day_high')
        fifty_two_low = context.get('fifty_two_week_low')
        timestamp = context.get('timestamp') or "Current session"

        lines = [
            f"### Lowest Price Today for {symbol} ({name})",
            f"The lowest price recorded today (intraday low) for **{symbol}** is **₹{day_low:,.2f}**."
        ]

        if curr_price is not None:
            diff_from_low = curr_price - day_low
            diff_pct = (diff_from_low / day_low * 100.0) if day_low > 0 else 0.0
            lines.append(f"• **Current Price**: ₹{curr_price:,.2f} (trading +₹{diff_from_low:,.2f} / +{diff_pct:.2f}% above today's low)")

        if day_high is not None:
            lines.append(f"• **Today's Trading Range**: ₹{day_low:,.2f} (Low) – ₹{day_high:,.2f} (High)")

        if fifty_two_low is not None:
            lines.append(
                f"\n**Price Level Distinction**:\n"
                f"• **Today's Intraday Low**: **₹{day_low:,.2f}**\n"
                f"• **52-Week Low**: ₹{fifty_two_low:,.2f}\n"
                f"*(Today's low reflects session price action at {timestamp}, whereas the 52-week low represents the lowest traded price over the past year.)*"
            )
        else:
            lines.append(
                f"\n*(Note: This represents today's intraday low price action at {timestamp}, distinct from 52-week or all-time historical lows.)*"
            )

        return "\n\n".join(lines)

    @classmethod
    def _build_day_high_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        day_high = context.get('day_high')
        if day_high is None:
            return (
                f"### Today's Highest Price for {symbol} ({name})\n\n"
                f"Today's intraday high price for **{symbol}** cannot currently be retrieved from the market data API."
            )

        curr_price = context.get('current_price')
        day_low = context.get('day_low')
        fifty_two_high = context.get('fifty_two_week_high')
        timestamp = context.get('timestamp') or "Current session"

        lines = [
            f"### Highest Price Today for {symbol} ({name})",
            f"The highest price recorded today (intraday high) for **{symbol}** is **₹{day_high:,.2f}**."
        ]

        if curr_price is not None:
            diff_from_high = day_high - curr_price
            diff_pct = (diff_from_high / day_high * 100.0) if day_high > 0 else 0.0
            lines.append(f"• **Current Price**: ₹{curr_price:,.2f} (trading -₹{diff_from_high:,.2f} / -{diff_pct:.2f}% below today's high)")

        if day_low is not None:
            lines.append(f"• **Today's Trading Range**: ₹{day_low:,.2f} (Low) – ₹{day_high:,.2f} (High)")

        if fifty_two_high is not None:
            lines.append(
                f"\n**Price Level Distinction**:\n"
                f"• **Today's Intraday High**: **₹{day_high:,.2f}**\n"
                f"• **52-Week High**: ₹{fifty_two_high:,.2f}\n"
                f"*(Today's high reflects session price action at {timestamp}, distinct from the 52-week high reached over the past 12 months.)*"
            )

        return "\n\n".join(lines)

    @classmethod
    def _build_open_price_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        open_price = context.get('open')
        if open_price is None:
            return (
                f"### Opening Price for {symbol} ({name})\n\n"
                f"Today's opening price for **{symbol}** cannot currently be retrieved from the market data API."
            )

        prev_close = context.get('previous_close')
        lines = [
            f"### Today's Opening Price for {symbol} ({name})",
            f"**{symbol}** opened today's trading session at **₹{open_price:,.2f}**."
        ]

        if prev_close is not None:
            gap = open_price - prev_close
            gap_pct = (gap / prev_close * 100.0) if prev_close > 0 else 0.0
            if abs(gap) < 0.05:
                gap_desc = "flat relative to yesterday's close"
            elif gap > 0:
                gap_desc = f"with a **gap-up** of +₹{gap:,.2f} (+{gap_pct:.2f}%)"
            else:
                gap_desc = f"with a **gap-down** of -₹{abs(gap):,.2f} ({gap_pct:.2f}%)"
            lines.append(f"• **Previous Close**: ₹{prev_close:,.2f}")
            lines.append(f"• **Opening Action**: The stock opened {gap_desc}.")

        day_high = context.get('day_high')
        day_low = context.get('day_low')
        if day_high is not None and day_low is not None:
            lines.append(f"• **Session Range**: ₹{day_low:,.2f} – ₹{day_high:,.2f}")

        return "\n\n".join(lines)

    @classmethod
    def _build_previous_close_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        prev_close = context.get('previous_close')
        if prev_close is None:
            return (
                f"### Previous Close for {symbol} ({name})\n\n"
                f"Yesterday's closing price for **{symbol}** cannot currently be retrieved from the market data API."
            )

        curr_price = context.get('current_price')
        change = context.get('change')
        change_pct = context.get('change_percent')

        lines = [
            f"### Yesterday's Closing Price for {symbol} ({name})",
            f"The previous trading day's closing price for **{symbol}** was **₹{prev_close:,.2f}**."
        ]

        if curr_price is not None:
            lines.append(f"• **Current Price**: ₹{curr_price:,.2f}")
        if change is not None and change_pct is not None:
            direction = "gain" if change >= 0 else "decline"
            lines.append(f"• **Net Change Since Close**: {change:+,.2f} ({change_pct:+.2f}%) {direction}")

        return "\n\n".join(lines)

    @classmethod
    def _build_volume_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        vol = context.get('volume')
        if vol is None or vol <= 0:
            return (
                f"### Trading Volume for {symbol} ({name})\n\n"
                f"Trading volume data for **{symbol}** cannot currently be retrieved from the active market quote feed."
            )

        lines = [
            f"### Trading Volume for {symbol} ({name})",
            f"The total recorded trading volume for **{symbol}** today is **{vol:,} shares**."
        ]
        curr_price = context.get('current_price')
        if curr_price:
            approx_turnover = vol * curr_price
            if approx_turnover >= 10000000:
                turnover_str = f"₹{approx_turnover / 10000000:,.2f} Cr"
            elif approx_turnover >= 100000:
                turnover_str = f"₹{approx_turnover / 100000:,.2f} Lakhs"
            else:
                turnover_str = f"₹{approx_turnover:,.2f}"
            lines.append(f"• **Approximate Turnover**: {turnover_str}")

        return "\n\n".join(lines)

    @classmethod
    def _build_price_change_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        change = context.get('change')
        change_pct = context.get('change_percent')
        curr_price = context.get('current_price')
        prev_close = context.get('previous_close')

        if change is None or change_pct is None:
            return (
                f"### Price Movement for {symbol} ({name})\n\n"
                f"Intraday price movement for **{symbol}** cannot currently be retrieved from the market feed."
            )

        icon = "📈" if change > 0 else ("📉" if change < 0 else "⚪")
        direction = "up" if change > 0 else ("down" if change < 0 else "unchanged")

        lines = [
            f"### Today's Price Movement for {symbol} ({name})",
            f"{icon} **{symbol}** is currently trading at **₹{curr_price:,.2f}**, moving **{direction} by {change:+,.2f} ({change_pct:+.2f}%)** today."
        ]

        if prev_close is not None:
            lines.append(f"• **Previous Close**: ₹{prev_close:,.2f}")
        day_high = context.get('day_high')
        day_low = context.get('day_low')
        if day_high is not None and day_low is not None:
            lines.append(f"• **Day Range**: ₹{day_low:,.2f} (Low) – ₹{day_high:,.2f} (High)")

        return "\n\n".join(lines)

    @classmethod
    def _build_price_vs_ma_response(
        cls,
        symbol: str,
        name: str,
        current_price: Optional[float],
        ma20: Optional[float],
        ma50: Optional[float]
    ) -> str:
        if current_price is None or ma20 is None or ma50 is None:
            return (
                f"### Current Price vs Moving Averages for {symbol} ({name})\n\n"
                f"Moving average comparisons for **{symbol}** cannot currently be calculated due to missing price or historical candle data."
            )

        rel_20 = "above" if current_price >= ma20 else "below"
        rel_50 = "above" if current_price >= ma50 else "below"
        diff_20 = current_price - ma20
        diff_50 = current_price - ma50
        pct_20 = (diff_20 / ma20) * 100.0
        pct_50 = (diff_50 / ma50) * 100.0

        if rel_20 == "above" and rel_50 == "above":
            interpretation = (
                f"🟢 **Bullish Trend Alignment**:\n"
                f"Because the current price (₹{current_price:,.2f}) is trading **above both** its short-term MA20 and intermediate MA50, "
                "the stock demonstrates solid upward momentum with moving averages serving as dynamic support levels."
            )
        elif rel_20 == "below" and rel_50 == "below":
            interpretation = (
                f"🔴 **Bearish Trend Alignment**:\n"
                f"Because the current price (₹{current_price:,.2f}) is trading **below both** its MA20 and MA50, "
                "the stock is under persistent selling pressure with moving averages acting as overhead resistance."
            )
        elif rel_20 == "above" and rel_50 == "below":
            interpretation = (
                f"🟡 **Short-Term Recovery**:\n"
                f"The price has recovered above its 20-day average (+{pct_20:.2f}%), but remains below its 50-day average ({pct_50:.2f}%), "
                "suggesting a potential counter-trend rally facing intermediate resistance at the MA50."
            )
        else:
            interpretation = (
                f"🟠 **Short-Term Pullback**:\n"
                f"The price has dipped below the 20-day average ({pct_20:.2f}%), but remains above the 50-day average (+{pct_50:.2f}%), "
                "indicating a consolidation phase within a broader upward trend."
            )

        lines = [
            f"### Current Price vs MA20 and MA50 for {symbol} ({name})",
            f"• **Current Market Price**: **₹{current_price:,.2f}**\n"
            f"• **20-Day SMA (MA20)**: ₹{ma20:,.2f} → Price is trading **{rel_20}** MA20 by **{diff_20:+,.2f} ({pct_20:+.2f}%)**\n"
            f"• **50-Day SMA (MA50)**: ₹{ma50:,.2f} → Price is trading **{rel_50}** MA50 by **{diff_50:+,.2f} ({pct_50:+.2f}%)**",
            interpretation
        ]

        return "\n\n".join(lines)

    @classmethod
    def _build_macd_trend_response(cls, symbol: str, name: str, macd_data: Dict[str, Any]) -> str:
        macd_val = macd_data.get('macd')
        signal = macd_data.get('signal')
        hist = macd_data.get('histogram')

        if macd_val is None or signal is None:
            return (
                f"### MACD Trend for {symbol} ({name})\n\n"
                f"MACD trend data for **{symbol}** is currently unavailable from historical candle calculations."
            )

        is_bullish = macd_val >= signal
        icon = "🟢" if is_bullish else "🔴"
        hist_val = hist if hist is not None else (macd_val - signal)

        if is_bullish:
            trend_desc = (
                f"{icon} **MACD is Bullish** for **{symbol}**.\n\n"
                f"The fast MACD line ({macd_val:+.2f}) is positioned **above** the 9-day Signal line ({signal:+.2f}), "
                f"producing a positive histogram of **{hist_val:+.2f}**.\n\n"
                "This indicates that short-term exponential momentum is expanding faster than longer-term momentum, "
                "supporting constructive upward price action."
            )
        else:
            trend_desc = (
                f"{icon} **MACD is Bearish** for **{symbol}**.\n\n"
                f"The fast MACD line ({macd_val:+.2f}) is positioned **below** the 9-day Signal line ({signal:+.2f}), "
                f"producing a negative histogram of **{hist_val:+.2f}**.\n\n"
                "This reflects downward momentum where selling velocity outpaces historical moving averages, "
                "signaling caution or potential overhead pressure."
            )

        lines = [
            f"### Is MACD Bullish or Bearish for {symbol} ({name})?",
            trend_desc,
            f"**Exact Indicator Readings**:\n"
            f"• **MACD Line (12/26 EMA)**: {macd_val:+.2f}\n"
            f"• **Signal Line (9 EMA)**: {signal:+.2f}\n"
            f"• **MACD Histogram**: {hist_val:+.2f}"
        ]

        return "\n\n".join(lines)

    @classmethod
    def _build_model_selection_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        ml_pred = context.get('ml_prediction')
        if not ml_pred:
            return (
                f"### ML Model Selection for {symbol} ({name})\n\n"
                f"Machine Learning model data for **{symbol}** is currently unavailable.\n\n"
                "StockSense AI evaluates regression candidates (Linear Regression, Ridge, Random Forest, Gradient Boosting) "
                "and selects the one with the lowest out-of-sample RMSE."
            )

        model_name = ml_pred.get('selected_model', 'Random Forest Regressor')
        metrics = ml_pred.get('metrics', {})
        rmse = metrics.get('rmse')
        mae = metrics.get('mae')
        r2 = metrics.get('r2')

        lines = [
            f"### Selected ML Model for {symbol} ({name})",
            f"The forecasting engine selected: **{model_name}**.",
            "**How the Model Was Selected**:\n"
            "StockSense AI trains multiple candidate regression architectures on historical daily feature sets "
            "(Open, High, Low, Close, Volume, MA20, MA50) using walk-forward train/test splits. "
            "The model that achieves the **lowest out-of-sample Root Mean Squared Error (RMSE)** is automatically selected as the production forecaster."
        ]

        metric_bullets = []
        if rmse is not None:
            metric_bullets.append(f"• **Validation RMSE**: {rmse:.2f} (lower is better)")
        if mae is not None:
            metric_bullets.append(f"• **Validation MAE**: {mae:.2f}")
        if r2 is not None:
            metric_bullets.append(f"• **R² Goodness of Fit**: {r2:.2f}")

        if metric_bullets:
            lines.append("**Validation Performance Metrics**:\n" + "\n".join(metric_bullets))

        return "\n\n".join(lines)

    @classmethod
    def _build_model_metrics_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        ml_pred = context.get('ml_prediction') or {}
        metrics = ml_pred.get('metrics', {})
        mae = metrics.get('mae')
        rmse = metrics.get('rmse')

        lines = [
            "### What do MAE and RMSE Mean in StockSense AI?",
            "**MAE** and **RMSE** are the two foundational evaluation metrics used to quantify how closely our machine learning forecasts match actual historical stock price closes:\n\n"
            "1. **MAE (Mean Absolute Error)**:\n"
            "   • Measures the average magnitude of prediction errors in absolute rupees (`|Actual - Predicted|`).\n"
            "   • If MAE is ₹15.00, it means that on average, forecasts deviate from the true close by ₹15.00.\n\n"
            "2. **RMSE (Root Mean Squared Error)**:\n"
            "   • Squares each error before averaging and taking the square root (`sqrt(mean((Actual - Predicted)^2))`).\n"
            "   • Because errors are squared, RMSE **heavily penalizes large outlier errors**. An algorithm with lower RMSE is much less prone to catastrophic forecast misses."
        ]

        if mae is not None and rmse is not None:
            lines.append(
                f"**Current Metrics for {symbol} ({ml_pred.get('selected_model', 'Active Model')})**:\n"
                f"• **MAE**: **₹{mae:.2f}**\n"
                f"• **RMSE**: **₹{rmse:.2f}**"
            )
        else:
            lines.append(f"*(Historical validation metrics for {symbol} are computed during model retraining.)*")

        return "\n\n".join(lines)

    @classmethod
    def _build_prediction_reliability_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        ml_pred = context.get('ml_prediction')
        if not ml_pred:
            return (
                f"### ML Prediction Reliability for {symbol} ({name})\n\n"
                "Prediction reliability evaluation is currently unavailable because the ML forecasting model has not yet run for this security."
            )

        model_name = ml_pred.get('selected_model', 'ML Regressor')
        metrics = ml_pred.get('metrics', {})
        r2 = metrics.get('r2')
        rmse = metrics.get('rmse')
        pred_price = ml_pred.get('predicted_price')
        change_pct = ml_pred.get('predicted_change_percentage')

        lines = [
            f"### Prediction Reliability & Methodology for {symbol} ({name})",
            f"The prediction is powered by **{model_name}**.",
            "**How Reliable is the Prediction?**\n"
            "Financial markets have significant non-linear noise and exogenous events (macro announcements, earnings, regulatory shifts). "
            "No algorithm can guarantee market direction. Here is how StockSense AI manages reliability:\n\n"
            "1. **Objective Model Selection**: Candidates are strictly selected by minimizing out-of-sample RMSE.\n"
            "2. **Safety in Diversified Scoring**: StockSense AI **never** makes recommendations based solely on ML predictions. "
            "The ML forecast receives a disciplined **35% weight** in our composite score, balanced with **65% technical indicators** (RSI 20%, MACD 20%, MA20/MA50 25%).\n"
            "3. **Confidence Bounds**: Projections are best treated as statistical directional tendencies, not guaranteed price targets."
        ]

        if r2 is not None and rmse is not None:
            lines.append(
                f"**Model Statistics for {symbol}**:\n"
                f"• **R² Score**: {r2:.2f} ({'Strong variance capture' if r2 >= 0.8 else 'Moderate variance capture'})\n"
                f"• **Expected Error Margin (RMSE)**: ±₹{rmse:.2f}\n"
                f"• **Predicted Close**: ₹{pred_price:,.2f} ({change_pct:+.2f}%)"
            )

        return "\n\n".join(lines)

    @classmethod
    def _build_supporting_factors_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        rec = context.get('recommendation')
        if not rec:
            return (
                f"### Supporting Factors for {symbol} ({name})\n\n"
                f"Detailed recommendation factors for **{symbol}** are currently unavailable."
            )

        verdict = rec.get('verdict', 'HOLD')
        score = rec.get('signal_score', 0)
        supporting = rec.get('supporting_indicators', [])

        lines = [
            f"### Factors Supporting the {verdict} Recommendation for {symbol} ({name})",
            f"The overall composite score is **{score:+d} / 100**, yielding a **{verdict}** recommendation.",
            "**Pillar-by-Pillar Breakdown**:"
        ]

        if supporting:
            for item in supporting:
                name_str = item.get('name', 'Indicator')
                pts = item.get('score', 0)
                sig = item.get('signal', 'NEUTRAL')
                interp = item.get('interpretation', '')
                icon = "🟢" if pts > 0 else ("🔴" if pts < 0 else "⚪")
                lines.append(f"• {icon} **{name_str}** [{sig} | {pts:+d} pts]: {interp}")
        else:
            lines.append(f"• Recommendation explanation: {rec.get('explanation', 'N/A')}")

        lines.append(
            "\n*StockSense AI provides statistical and technical market analysis for educational and decision-support purposes. "
            "It does not guarantee financial returns.*"
        )

        return "\n\n".join(lines)

    @classmethod
    def _build_selling_analysis_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        rec = context.get('recommendation') or {}
        verdict = rec.get('verdict', 'HOLD')
        score = rec.get('signal_score', 0)
        rsi = context.get('rsi')
        curr_price = context.get('current_price')
        ma20 = context.get('ma20')
        macd_data = context.get('macd', {})
        macd_val = macd_data.get('macd')
        signal = macd_data.get('signal')

        lines = [
            f"### Selling Analysis for {symbol} ({name})"
        ]

        bearish_factors = []
        bullish_factors = []

        if rsi is not None and rsi >= 70.0:
            bearish_factors.append(f"RSI is in overbought territory ({rsi:.2f} >= 70), indicating elevated risk of profit-taking.")
        elif rsi is not None and rsi <= 30.0:
            bullish_factors.append(f"RSI is deeply oversold ({rsi:.2f} <= 30), suggesting selling may be exhausted.")

        if curr_price and ma20 and curr_price < ma20:
            bearish_factors.append(f"Price (₹{curr_price:,.2f}) is trading below the 20-day SMA (₹{ma20:,.2f}), reflecting short-term weakness.")

        if macd_val is not None and signal is not None and macd_val < signal:
            bearish_factors.append(f"MACD line ({macd_val:+.2f}) is below Signal line ({signal:+.2f}), indicating negative momentum.")

        if verdict == 'SELL':
            lines.append(
                f"🔴 **The system currently suggests SELL (Score: {score:+d} / 100)**.\n\n"
                f"Negative technical factors outweigh upside potential across momentum and trend indicators:\n" +
                "\n".join([f"• {bf}" for bf in (bearish_factors or [rec.get('explanation', '')])]) +
                "\n\nRisk management rules suggest protecting capital or reducing exposure."
            )
        elif verdict == 'BUY':
            lines.append(
                f"🟢 **The system recommends BUY (Score: {score:+d} / 100), NOT Sell**.\n\n"
                "Quantitative indicators remain predominantly constructive. "
            )
            if bearish_factors:
                lines.append("However, keep these caution points in mind:\n" + "\n".join([f"• {bf}" for bf in bearish_factors]))
            else:
                lines.append("No immediate technical sell signals are currently active on daily indicators.")
        else:
            lines.append(
                f"🟡 **The system recommends HOLD (Score: {score:+d} / 100)**.\n\n"
                "Current signals are balanced. The system does not detect an urgent trigger to liquidate positions, "
                "nor a strong enough catalyst to initiate fresh aggressive buys.\n"
            )
            if bearish_factors:
                lines.append("**Downside Watchpoints**:\n" + "\n".join([f"• {bf}" for bf in bearish_factors]))

        return "\n\n".join(lines)

    @classmethod
    def _build_portfolio_cash_response(cls, user_portfolio: Optional[Dict[str, Any]]) -> str:
        if not user_portfolio or not user_portfolio.get('authenticated'):
            return (
                "### Virtual Cash Balance\n\n"
                "🔒 **Login Required**: Please sign in to your StockSense AI account to view your live paper trading wallet balance.\n\n"
                "Every registered trader receives **₹1,00,000 in virtual trading capital** to practice risk-free paper trading."
            )

        cash = user_portfolio.get('virtual_cash', 0.0)
        username = user_portfolio.get('username', 'Trader')

        return (
            f"### Virtual Cash Balance for {username}\n\n"
            f"💰 **Available Paper Trading Cash**: **₹{cash:,.2f}**\n\n"
            "This virtual capital is ready to deploy into paper trades directly via the Paper Trading panel."
        )

    @classmethod
    def _build_portfolio_holdings_response(cls, user_portfolio: Optional[Dict[str, Any]]) -> str:
        if not user_portfolio or not user_portfolio.get('authenticated'):
            return (
                "### Your Stock Holdings\n\n"
                "🔒 **Login Required**: Please log in to view your current paper trading portfolio holdings."
            )

        holdings = user_portfolio.get('holdings', [])
        summary = user_portfolio.get('portfolio_summary', {})
        total_invested = summary.get('total_invested', 0.0)
        current_value = summary.get('current_value', 0.0)
        pnl = summary.get('total_pnl', 0.0)
        pnl_pct = summary.get('total_pnl_percent', 0.0)

        if not holdings:
            return (
                "### Your Stock Holdings\n\n"
                "You do not currently own any stock positions in your paper trading portfolio.\n\n"
                "To buy shares, use the Paper Trading execution widget on the right-hand panel."
            )

        lines = [
            f"### Your Paper Trading Portfolio ({len(holdings)} Positions)",
            f"• **Total Invested**: ₹{total_invested:,.2f}\n"
            f"• **Current Market Value**: ₹{current_value:,.2f}\n"
            f"• **Total P&L**: **{pnl:+,.2f} ({pnl_pct:+.2f}%)**\n",
            "**Holdings Breakdown**:"
        ]

        for h in holdings:
            sym = h.get('symbol', 'UNKNOWN')
            qty = h.get('quantity', 0)
            avg = h.get('average_price', 0.0)
            curr = h.get('current_price', avg)
            val = h.get('current_value', qty * curr)
            pos_pnl = h.get('unrealized_pnl', 0.0)
            pos_pct = h.get('unrealized_pnl_percent', 0.0)
            pnl_icon = "🟢" if pos_pnl >= 0 else "🔴"
            lines.append(f"• **{sym}**: {qty} shares @ avg ₹{avg:,.2f} | Value: ₹{val:,.2f} | {pnl_icon} P&L: {pos_pnl:+,.2f} ({pos_pct:+.2f}%)")

        return "\n\n".join(lines)

    @classmethod
    def _build_portfolio_pnl_response(cls, user_portfolio: Optional[Dict[str, Any]]) -> str:
        if not user_portfolio or not user_portfolio.get('authenticated'):
            return (
                "### Portfolio Profit & Loss (P&L)\n\n"
                "🔒 **Login Required**: Please sign in to view your paper trading portfolio profit and loss summary."
            )

        summary = user_portfolio.get('portfolio_summary', {})
        pnl = summary.get('total_pnl', 0.0)
        pnl_pct = summary.get('total_pnl_percent', 0.0)
        invested = summary.get('total_invested', 0.0)
        current_val = summary.get('current_value', 0.0)
        cash = user_portfolio.get('virtual_cash', 0.0)
        total_account_equity = current_val + cash

        icon = "📈 🟢" if pnl >= 0 else "📉 🔴"
        status_word = "Profit" if pnl >= 0 else "Loss"

        return (
            f"### Portfolio Profit & Loss Summary\n\n"
            f"{icon} **Total Unrealized {status_word}**: **{pnl:+,.2f} ({pnl_pct:+.2f}%)**\n\n"
            f"• **Total Capital Invested**: ₹{invested:,.2f}\n"
            f"• **Current Stock Value**: ₹{current_val:,.2f}\n"
            f"• **Available Virtual Cash**: ₹{cash:,.2f}\n"
            f"• **Total Account Equity**: **₹{total_account_equity:,.2f}**"
        )

    @classmethod
    def _build_stock_holding_response(cls, target_sym: str, user_portfolio: Optional[Dict[str, Any]]) -> str:
        clean_sym = InstrumentMappingService.normalize_symbol(target_sym or 'TCS')
        if not user_portfolio or not user_portfolio.get('authenticated'):
            return (
                f"### Holdings for {clean_sym}\n\n"
                f"🔒 **Login Required**: Please log in to check your shares of **{clean_sym}**."
            )

        holdings = user_portfolio.get('holdings', [])
        match = next((h for h in holdings if h.get('symbol', '').upper() == clean_sym.upper()), None)

        if not match or match.get('quantity', 0) == 0:
            return (
                f"### Holdings for {clean_sym}\n\n"
                f"You currently hold **0 shares** of **{clean_sym}** in your paper trading account."
            )

        qty = match.get('quantity', 0)
        avg = match.get('average_price', 0.0)
        curr = match.get('current_price', avg)
        val = match.get('current_value', qty * curr)
        pnl = match.get('unrealized_pnl', (curr - avg) * qty)
        pnl_pct = match.get('unrealized_pnl_percent', ((curr - avg) / avg * 100.0) if avg > 0 else 0.0)
        icon = "🟢" if pnl >= 0 else "🔴"

        return (
            f"### Holdings for {clean_sym}\n\n"
            f"You currently own **{qty} shares** of **{clean_sym}**.\n\n"
            f"• **Average Purchase Price**: ₹{avg:,.2f}\n"
            f"• **Current Market Price**: ₹{curr:,.2f}\n"
            f"• **Current Position Value**: ₹{val:,.2f}\n"
            f"• {icon} **Position P&L**: **{pnl:+,.2f} ({pnl_pct:+.2f}%)**"
        )

    @classmethod
    def _build_trade_cost_response(
        cls,
        symbol: str,
        name: str,
        context: Dict[str, Any],
        user_message: str,
        user_portfolio: Optional[Dict[str, Any]]
    ) -> str:
        curr_price = context.get('current_price')
        if curr_price is None:
            return (
                f"### Purchase Cost Calculation for {symbol} ({name})\n\n"
                f"The current market price for **{symbol}** is unavailable, so purchase cost cannot be calculated."
            )

        words_to_num = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
        }
        num_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+shares?\b', user_message.lower())
        qty = 1
        if num_match:
            raw_qty = num_match.group(1)
            qty = words_to_num.get(raw_qty) or (int(raw_qty) if raw_qty.isdigit() else 1)

        total_cost = qty * curr_price

        lines = [
            f"### Estimated Purchase Cost for {symbol} ({name})",
            f"Buying **{qty} share{'s' if qty != 1 else ''}** of **{symbol}** at the current market price of **₹{curr_price:,.2f}** would cost **₹{total_cost:,.2f}**."
        ]

        if user_portfolio and user_portfolio.get('authenticated'):
            cash = user_portfolio.get('virtual_cash', 0.0)
            if cash >= total_cost:
                lines.append(f"• **Wallet Status**: You have **₹{cash:,.2f}** in virtual cash — sufficient to complete this order.")
            else:
                shortfall = total_cost - cash
                lines.append(f"• **Wallet Status**: You have **₹{cash:,.2f}** in virtual cash (shortfall: ₹{shortfall:,.2f}).")

        lines.append(
            "\n⚠️ *Note: StockSense AI does not execute trading transactions through the chat window. "
            "Please use the Paper Trading execution panel to place this order securely.*"
        )

        return "\n\n".join(lines)

    @classmethod
    def _build_trade_rejection_response(
        cls,
        symbol: str,
        name: str,
        context: Dict[str, Any],
        user_portfolio: Optional[Dict[str, Any]]
    ) -> str:
        lines = [
            "### Why Was My BUY Transaction Rejected?",
            "In StockSense AI Paper Trading, a BUY order is rejected if any of the following validation rules fail:\n\n"
            "1. **Insufficient Virtual Cash Balance**:\n"
            "   • Your wallet balance must cover `Quantity × Market Price`.\n"
            "2. **Invalid Quantity**:\n"
            "   • Order quantity must be a positive whole integer greater than zero (no fractional shares).\n"
            "3. **Missing or Stale Market Quote**:\n"
            "   • Orders require a verified, active market quote from the exchange data feed.\n"
            "4. **Authentication Session Expired**:\n"
            "   • If your login session timed out, trading requests are rejected for account security."
        ]

        if user_portfolio and user_portfolio.get('authenticated'):
            cash = user_portfolio.get('virtual_cash', 0.0)
            lines.append(f"• **Your Current Wallet Balance**: **₹{cash:,.2f}**")

        lines.append(
            "\n*Check your notification toast or the Paper Trading transaction history table for the exact rejection reason.*"
        )

        return "\n\n".join(lines)

    @classmethod
    def _build_educational_response(cls, topic: str, symbol: str, name: str) -> str:
        if topic == 'stock_market':
            return (
                "### What is the Stock Market?\n\n"
                "The **stock market** is an organized financial marketplace where buyers and sellers trade shares of publicly listed companies.\n\n"
                "**Key Functions**:\n"
                "• **Capital Raising**: Enables corporations to raise long-term capital from institutional and retail investors.\n"
                "• **Price Discovery**: Prices fluctuate based on continuous supply and demand, company earnings, and macro trends.\n"
                "• **Liquidity & Ownership**: Allows investors to buy ownership stakes and easily liquidate them back into cash.\n\n"
                "In India, equities are primarily listed and traded on the **NSE (National Stock Exchange)** and **BSE (Bombay Stock Exchange)**."
            )
        elif topic == 'moving_average':
            return (
                "### What is a Moving Average (MA)?\n\n"
                "A **Moving Average** is a technical indicator that smooths out short-term price fluctuations to reveal the underlying trend direction.\n\n"
                "• **Simple Moving Average (SMA)**: Computes the arithmetic mean of closing prices over a specific period (e.g., 20 days or 50 days).\n"
                "• **Exponential Moving Average (EMA)**: Gives greater mathematical weight to more recent prices, reacting faster to price turns.\n\n"
                "**How Traders Use Them**:\n"
                "• **Trend Filter**: Prices above the moving average signal an uptrend; prices below indicate a downtrend.\n"
                "• **Support/Resistance**: MAs frequently act as dynamic price floors or ceilings."
            )
        elif topic == 'models_comparison':
            return (
                "### Difference Between Linear Regression and Random Forest\n\n"
                "StockSense AI evaluates both architectures during model selection:\n\n"
                "1. **Linear Regression**:\n"
                "   • **Mechanism**: Models the relationship between input features (MAs, volume, previous prices) and target close as a linear equation (`y = w1*x1 + w2*x2 + ... + b`).\n"
                "   • **Strengths**: Highly interpretable, computationally fast, and avoids overfitting on small datasets.\n"
                "   • **Limitation**: Cannot capture complex non-linear market interactions or sudden volatility regimes.\n\n"
                "2. **Random Forest Regressor**:\n"
                "   • **Mechanism**: An ensemble learning technique that builds hundreds of randomized decision trees and averages their predictions (`bagging`).\n"
                "   • **Strengths**: Captures non-linear dependencies, handles feature interactions effectively, and is robust to outliers.\n"
                "   • **Trade-off**: Requires more compute and can suffer from lagging on extreme outlier breakout sessions."
            )
        elif topic == 'diversification':
            return (
                "### What is Portfolio Diversification?\n\n"
                "**Diversification** is a risk-management strategy that mixes a wide variety of uncorrelated investments within a portfolio.\n\n"
                "**Core Principles**:\n"
                "• **Avoid Single-Stock Risk**: Holding 10-15 stocks across diverse sectors (e.g. IT, Energy, Banking, FMCG) ensures that a crash in one sector does not destroy total portfolio equity.\n"
                "• **Uncorrelated Asset Classes**: Blending equities, bonds, cash, and commodities helps stabilize overall returns across market cycles.\n"
                "• *'Don't put all your eggs in one basket.'*"
            )
        elif topic == 'investing_vs_paper_trading':
            return (
                "### Difference Between Investing and Paper Trading\n\n"
                "1. **Paper Trading (Virtual Simulation)**:\n"
                "   • Trades are simulated using **virtual capital** (StockSense AI provides ₹1,00,000 in virtual funds).\n"
                "   • Zero real-world financial risk.\n"
                "   • Ideal for testing indicators, ML models, and trading discipline before committing actual savings.\n\n"
                "2. **Real Investing (Capital Commitment)**:\n"
                "   • Uses real money through a registered depository participant (broker).\n"
                "   • Involves real profit, real risk of loss, trading fees, and emotional psychology."
            )
        return (
            "### Financial Education with StockSense AI\n\n"
            "StockSense AI integrates quantitative tools (RSI, MACD, MA20/50, and ML forecasting) to empower data-driven trading decisions."
        )

    @classmethod
    def _build_followup_response(
        cls,
        symbol: str,
        name: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> str:
        last_topic = None
        if conversation_history:
            for turn in reversed(conversation_history):
                content = (turn.get('content') or turn.get('text') or turn.get('response') or '').lower()
                if 'lowest price' in content or 'day low' in content or 'intraday low' in content:
                    last_topic = 'day_low'
                    break
                elif 'highest price' in content or 'day high' in content:
                    last_topic = 'day_high'
                    break
                elif 'rsi' in content or 'relative strength' in content:
                    last_topic = 'rsi'
                    break
                elif 'macd' in content or 'convergence' in content:
                    last_topic = 'macd'
                    break
                elif 'ma20' in content or 'ma50' in content or 'moving average' in content:
                    last_topic = 'moving_average'
                    break
                elif 'recommendation' in content or 'buy' in content or 'sell' in content or 'hold' in content:
                    last_topic = 'recommendation'
                    break
                elif 'prediction' in content or 'forecast' in content or 'machine learning' in content or 'ml' in content:
                    last_topic = 'ml'
                    break

        if last_topic == 'day_low':
            day_low = context.get('day_low')
            curr = context.get('current_price')
            low_str = f"₹{day_low:,.2f}" if day_low is not None else "N/A"
            curr_str = f"₹{curr:,.2f}" if curr is not None else "N/A"
            return (
                f"### What Does Today's Lowest Price ({low_str}) Mean for {symbol}?\n\n"
                f"The intraday low (**{low_str}**) marks the absolute floor of buying demand during today's session.\n\n"
                "• **Key Support**: When price approaches the day's low, buyers historically stepped in to defend that level.\n"
                "• **Breakdown Risk**: If the stock decisively trades below today's low, it signals accelerating selling pressure and potential further decline.\n"
                f"• **Current Position**: At {curr_str}, the stock is trading above that support level."
            )
        elif last_topic == 'day_high':
            day_high = context.get('day_high')
            high_str = f"₹{day_high:,.2f}" if day_high is not None else "N/A"
            return (
                f"### What Does Today's Highest Price ({high_str}) Mean for {symbol}?\n\n"
                f"The intraday high (**{high_str}**) acts as the current session's ceiling or **resistance level**.\n\n"
                "• At this level, profit-taking and selling supply exceeded buyer volume.\n"
                "• A breakout above today's high on strong volume would be a bullish continuation trigger."
            )
        elif last_topic == 'rsi':
            rsi = context.get('rsi')
            return cls._build_rsi_meaning_response(symbol, name, rsi)
        elif last_topic == 'macd':
            return cls._build_macd_trend_response(symbol, name, context.get('macd', {}))
        elif last_topic == 'moving_average':
            return cls._build_price_vs_ma_response(symbol, name, context.get('current_price'), context.get('ma20'), context.get('ma50'))
        elif last_topic == 'recommendation':
            return cls._build_why_recommendation_response(symbol, name, context)
        elif last_topic == 'ml':
            return cls._build_prediction_reliability_response(symbol, name, context)
        else:
            rec = context.get('recommendation', {})
            verdict = rec.get('verdict', 'HOLD')
            return (
                f"### Understanding the Analysis for {symbol} ({name})\n\n"
                f"StockSense AI evaluates quantitative technical indicators and ML models to guide your trading decisions:\n\n"
                f"• **Current Verdict**: **{verdict}** based on a composite score of {rec.get('signal_score', 0):+d}/100.\n"
                "• **Interpretation**: A HOLD means bullish and bearish factors are currently balancing each other out, so entering fresh positions carries lower risk-reward symmetry until a clear breakout occurs.\n\n"
                "You can ask about specific indicators like *'What does RSI mean?'*, *'Is MACD bullish or bearish?'*, or *'What is today's lowest price?'*."
            )

    @classmethod
    def _build_what_is_rsi_response(cls, symbol: str, name: str, rsi: Optional[float]) -> str:
        current_str = f"**{rsi:.2f}**" if rsi is not None else "*Unavailable*"
        lines = [
            "### What is RSI (Relative Strength Index)?",
            "The **Relative Strength Index (RSI)** is a widely respected quantitative momentum oscillator that measures the speed and magnitude of recent price changes on a scale from **0 to 100** (typically evaluated over a 14-period lookback window).",
            "**Key Benchmarks:**\n"
            "• **Overbought (>= 70)**: The asset has experienced strong, sustained buying and may be technically overextended, increasing the probability of a pullback or consolidation.\n"
            "• **Oversold (<= 30)**: The asset has endured severe selling pressure and may be undervalued in the short term, presenting a potential bullish reversal or accumulation zone.\n"
            "• **Centerline (50)**: Marks the neutral momentum boundary. Values above 50 indicate positive momentum; values below 50 reflect negative momentum.",
            f"**Current Status for {symbol}**:\n"
            f"• 14-period RSI: {current_str}"
        ]
        if rsi is not None:
            lines.append(cls._interpret_rsi_tier(symbol, rsi))
        return "\n\n".join(lines)

    @classmethod
    def _build_rsi_meaning_response(cls, symbol: str, name: str, rsi: Optional[float]) -> str:
        if rsi is None:
            return (
                f"### RSI Interpretation for {symbol}\n\n"
                f"The 14-period RSI value for **{symbol}** is currently unavailable from the historical candle calculations.\n\n"
                "Generally, an RSI above 70 indicates an overbought condition, while an RSI below 30 signals an oversold condition."
            )

        interpretation = cls._interpret_rsi_tier(symbol, rsi)
        return (
            f"### What does the RSI value mean for {symbol}?\n\n"
            f"**{symbol}** currently has a 14-period RSI of **{rsi:.2f}**.\n\n"
            f"{interpretation}\n\n"
            f"**Summary Context:**\n"
            f"RSI quantifies whether current momentum is driven by aggressive accumulation (bullish) or distribution (bearish). "
            f"At **{rsi:.2f}**, the stock is {'in positive territory (> 50)' if rsi >= 50 else 'in subdued territory (< 50)'}."
        )

    @staticmethod
    def _interpret_rsi_tier(symbol: str, rsi: float) -> str:
        if rsi >= 70.0:
            return (
                f"🚨 **Overbought Territory ({rsi:.2f} >= 70)**\n"
                f"This reading indicates that {symbol} has undergone intensive buying pressure in recent sessions. "
                "While momentum remains strong, the stock carries elevated risk of near-term price fatigue or profit taking."
            )
        elif rsi > 55.0:
            return (
                f"🟢 **Healthy Bullish Momentum ({rsi:.2f} > 55)**\n"
                f"This reading indicates constructive upward momentum for {symbol}. "
                "Buyers are in control, and the stock is advancing without entering the extreme overbought zone (>= 70)."
            )
        elif rsi >= 45.0:
            return (
                f"⚪ **Neutral Consolidation ({rsi:.2f} ≈ 50)**\n"
                f"This reading indicates that {symbol} is in a neutral equilibrium. "
                "Buying and selling forces are relatively balanced, reflecting consolidation around the 50 centerline."
            )
        elif rsi > 30.0:
            return (
                f"🟠 **Subdued / Bearish Momentum ({rsi:.2f} < 45)**\n"
                f"This reading indicates that {symbol} is experiencing persistent selling pressure below the 50 midline. "
                "Downward drift is dominant, though the stock has not yet reached extreme oversold levels."
            )
        else:
            return (
                f"🔵 **Oversold Territory ({rsi:.2f} <= 30)**\n"
                f"This reading indicates that {symbol} has suffered substantial recent selling. "
                "Historically, this signals an attractive risk-reward zone where a potential technical rebound or trend reversal may materialize."
            )

    @classmethod
    def _build_macd_response(cls, symbol: str, name: str, macd_data: Dict[str, Any]) -> str:
        macd_val = macd_data.get('macd')
        signal = macd_data.get('signal')
        hist = macd_data.get('histogram')

        lines = [
            "### What is MACD (Moving Average Convergence Divergence)?",
            "**MACD** is a trend-following momentum indicator that illustrates the dynamic relationship between two Exponential Moving Averages (EMAs):\n"
            "• **MACD Line**: Computed as the 12-day EMA minus the 26-day EMA.\n"
            "• **Signal Line**: A 9-day EMA of the MACD line itself.\n"
            "• **Histogram**: The difference between the MACD Line and Signal Line (`MACD - Signal`)."
        ]

        if macd_val is not None and signal is not None:
            status = "Bullish Crossover (MACD > Signal Line)" if macd_val >= signal else "Bearish Alignment (MACD < Signal Line)"
            hist_status = "expanding upward" if (hist or 0) > 0 else "contracting downward"

            lines.append(
                f"**Current MACD Metrics for {symbol}**:\n"
                f"• **MACD Line**: {macd_val:+.2f}\n"
                f"• **Signal Line**: {signal:+.2f}\n"
                f"• **Histogram**: {hist:+.2f}\n"
                f"• **Technical Status**: **{status}**, with momentum histogram {hist_status}."
            )
        else:
            lines.append(
                f"**Current MACD Metrics for {symbol}**:\n"
                "Detailed MACD figures are currently unavailable for this security from historical calculations."
            )

        return "\n\n".join(lines)

    @classmethod
    def _build_moving_averages_response(
        cls,
        symbol: str,
        name: str,
        current_price: Optional[float],
        ma20: Optional[float],
        ma50: Optional[float]
    ) -> str:
        lines = [
            "### What are the MA20 and MA50?",
            "Moving averages smooth historical price volatility to highlight persistent market trends:\n"
            "• **MA20 (20-day Simple Moving Average)**: Tracks average closing prices across the last 20 trading sessions (~1 calendar month), reflecting **short-term trend direction**.\n"
            "• **MA50 (50-day Simple Moving Average)**: Tracks average closing prices across the last 50 trading sessions (~2.5 calendar months), reflecting **intermediate-term trend direction**."
        ]

        if ma20 is not None and ma50 is not None:
            ma20_str = f"₹{ma20:,.2f}"
            ma50_str = f"₹{ma50:,.2f}"
            curr_str = f"₹{current_price:,.2f}" if current_price is not None else "N/A"

            # Trend alignments
            rel_20 = "Above" if (current_price and current_price >= ma20) else "Below"
            rel_50 = "Above" if (current_price and current_price >= ma50) else "Below"
            cross_status = "Bullish Trend (MA20 > MA50)" if ma20 >= ma50 else "Bearish Trend (MA20 < MA50)"

            lines.append(
                f"**Current Moving Averages for {symbol}** (Current Price: {curr_str}):\n"
                f"• **MA20**: {ma20_str} — Price is trading **{rel_20}** the 20-day average.\n"
                f"• **MA50**: {ma50_str} — Price is trading **{rel_50}** the 50-day average.\n"
                f"• **MA Alignment**: **{cross_status}**."
            )
        else:
            lines.append(
                f"**Current Moving Averages for {symbol}**:\n"
                "MA20 and MA50 values are currently unavailable due to insufficient historical candle data."
            )

        return "\n\n".join(lines)

    @classmethod
    def _build_ml_prediction_response(
        cls,
        symbol: str,
        name: str,
        current_price: Optional[float],
        ml_pred: Optional[Dict[str, Any]]
    ) -> str:
        if not ml_pred or ml_pred.get('predicted_price') is None:
            return (
                f"### Machine Learning Price Prediction for {symbol}\n\n"
                f"The ML price prediction for **{symbol}** is currently unavailable.\n\n"
                "StockSense AI requires at least 55-60 historical daily sessions to compute moving average features and train regression models."
            )

        pred_price = ml_pred.get('predicted_price')
        change_val = ml_pred.get('predicted_change')
        change_pct = ml_pred.get('predicted_change_percentage')
        direction = ml_pred.get('direction', 'UP' if (change_val or 0) >= 0 else 'DOWN')
        model_name = ml_pred.get('selected_model', 'Machine Learning Regressor')

        curr_str = f"₹{current_price:,.2f}" if current_price is not None else "N/A"
        pred_str = f"₹{pred_price:,.2f}"
        pct_str = f"{change_pct:+.2f}%" if change_pct is not None else "N/A"
        change_str = f"{change_val:+,.2f}" if change_val is not None else "N/A"

        return (
            f"### Machine Learning Price Forecast for {symbol} ({name})\n\n"
            f"StockSense AI's quantitative forecasting engine predicts:\n\n"
            f"• **Predicted Next-Day Close**: **{pred_str}**\n"
            f"• **Current Reference Price**: {curr_str}\n"
            f"• **Expected Price Movement**: **{change_str} ({pct_str})**\n"
            f"• **Forecast Direction**: **{direction}**\n"
            f"• **Selected Model**: {model_name} (chosen based on lowest out-of-sample RMSE error)\n\n"
            "**Features Evaluated in Model**:\n"
            "Open, High, Low, Close, Volume, Previous Close, MA20, and MA50."
        )

    @classmethod
    def _build_recommendation_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        rec = context.get('recommendation')
        if not rec or not rec.get('verdict'):
            return (
                f"### AI Recommendation for {symbol}\n\n"
                f"A composite recommendation for **{symbol}** is currently unavailable due to insufficient indicator inputs.\n\n"
                "Please verify active market quotes for this symbol."
            )

        verdict = rec.get('verdict')
        score = rec.get('signal_score', 0)
        norm_score = rec.get('normalized_score', 50.0)
        explanation = rec.get('explanation', '')

        icon = "🟢" if verdict == 'BUY' else ("🔴" if verdict == 'SELL' else "🟡")

        return (
            f"### Current AI Recommendation for {symbol} ({name})\n\n"
            f"{icon} **Recommendation**: **{verdict}**\n\n"
            f"• **Composite Signal Score**: **{score:+d} / 100**\n"
            f"• **Normalized Confidence**: **{norm_score:.1f}%**\n\n"
            f"**Executive Rationale**:\n"
            f"{explanation}\n\n"
            "*Ask: 'Why did the system generate this recommendation?' for a detailed indicator-by-indicator breakdown.*"
        )

    @classmethod
    def _build_why_recommendation_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        rec = context.get('recommendation')
        if not rec or not rec.get('verdict'):
            return (
                f"### Why did the system generate this recommendation?\n\n"
                f"Recommendation scoring details for **{symbol}** are currently unavailable.\n\n"
                "StockSense AI evaluates four weighted pillars: RSI (20 pts), MACD (20 pts), Moving Averages (25 pts), and ML Price Forecasts (35 pts)."
            )

        verdict = rec.get('verdict')
        total_score = rec.get('signal_score', 0)
        supporting = rec.get('supporting_indicators', [])
        explanation = rec.get('explanation', '')

        lines = [
            f"### Why StockSense AI Generated a {verdict} Recommendation for {symbol}",
            f"StockSense AI uses an objective, multi-factor quantitative scoring model (**-100 to +100**) that synthesizes four core technical and statistical pillars:",
            "**Scoring Framework Weights**:\n"
            "1. **RSI Momentum** (20 pts)\n"
            "2. **MACD Momentum & Crossovers** (20 pts)\n"
            "3. **Moving Average Alignment (MA20 & MA50)** (25 pts)\n"
            "4. **Machine Learning Price Forecast** (35 pts)"
        ]

        if supporting:
            lines.append(f"**Itemized Factor Breakdown for {symbol}**:")
            for item in supporting:
                name_str = item.get('name', 'Indicator')
                score_str = f"{item.get('score', 0):+d} pts"
                signal_str = item.get('signal', 'NEUTRAL')
                interp = item.get('interpretation', '')
                lines.append(f"• **{name_str}** [{signal_str} | {score_str}]: {interp}")

        lines.append(
            f"**Final Verdict Calculation**:\n"
            f"• **Total Composite Score**: **{total_score:+d} / 100**\n"
            f"• **Decision Rule**: Scores >= +20 trigger **BUY**; scores <= -20 trigger **SELL**; scores in between trigger **HOLD**.\n"
            f"• Result: Because the net score is **{total_score:+d}**, the system concluded **{verdict}**."
        )

        return "\n\n".join(lines)

    @classmethod
    def _build_full_overview_response(cls, symbol: str, name: str, context: Dict[str, Any]) -> str:
        curr_price = context.get('current_price')
        rsi = context.get('rsi')
        macd = context.get('macd', {})
        ma20 = context.get('ma20')
        ma50 = context.get('ma50')
        ml = context.get('ml_prediction')
        rec = context.get('recommendation')

        price_str = f"₹{curr_price:,.2f}" if curr_price is not None else "N/A"
        rsi_str = f"{rsi:.2f}" if rsi is not None else "N/A"
        macd_str = f"{macd.get('macd', 'N/A')}"
        ma20_str = f"₹{ma20:,.2f}" if ma20 is not None else "N/A"
        ma50_str = f"₹{ma50:,.2f}" if ma50 is not None else "N/A"
        pred_str = f"₹{ml.get('predicted_price'):,.2f} ({ml.get('predicted_change_percentage', 0):+.2f}%)" if ml else "N/A"
        rec_str = f"{rec.get('verdict', 'N/A')} ({rec.get('signal_score', 0):+d} pts)" if rec else "N/A"

        return (
            f"### Comprehensive Stock Analysis for {symbol} ({name})\n\n"
            f"Here is the current quantitative dashboard for **{symbol}**:\n\n"
            f"• **Current Price**: **{price_str}**\n"
            f"• **14-period RSI**: {rsi_str}\n"
            f"• **MACD (12, 26, 9)**: {macd_str}\n"
            f"• **MA20**: {ma20_str} | **MA50**: {ma50_str}\n"
            f"• **ML Predicted Price**: {pred_str}\n"
            f"• **AI Recommendation**: **{rec_str}**\n\n"
            "Feel free to ask for deeper explanations on any of these indicators or why the recommendation was generated."
        )

    @classmethod
    def _build_greeting_response(cls, symbol: str, name: str, price_str: str) -> str:
        return (
            f"### Hello! I am your StockSense AI Assistant 👋\n\n"
            f"I am actively monitoring **{symbol}** ({name}) — currently trading at **{price_str}**.\n\n"
            "Here are some questions you can ask me about this stock:\n"
            "• *What is the current price?*\n"
            "• *What is RSI?*\n"
            "• *What does the RSI value mean?*\n"
            "• *What is MACD?*\n"
            "• *What is the MA20 and MA50?*\n"
            "• *What is the ML predicted price?*\n"
            "• *What is the current AI recommendation?*\n"
            "• *Why did the system generate this recommendation?*"
        )

    @classmethod
    def _build_default_response(cls, symbol: str, name: str, context: Dict[str, Any], query: str) -> str:
        curr_price = context.get('current_price')
        price_str = f"₹{curr_price:,.2f}" if curr_price is not None else "N/A"

        return (
            f"### StockSense AI Assistant for {symbol} ({name})\n\n"
            f"I received your question: *\"{query}\"*\n\n"
            f"Currently monitoring **{symbol}** (Latest Market Price: **{price_str}**). "
            "To give you an accurate, grounded answer based on our verified exchange feed and quantitative models, "
            "you can ask questions such as:\n\n"
            "• **Market Price & Volume**: *'What is the current price?'*, *'What's the lowest price today?'*, *'What's the highest price today?'*, *'What was the opening price?'*, *'What is the trading volume?'*\n"
            "• **Technical Analysis**: *'What is RSI?'*, *'What does the current RSI indicate?'*, *'What is MACD?'*, *'Is MACD bullish or bearish?'*, *'Is price above MA20 and MA50?'*\n"
            "• **AI Recommendations & Scoring**: *'Can I buy or hold this stock?'*, *'Why did the system recommend this?'*, *'What factors support the recommendation?'*, *'What does the analysis suggest about selling?'*\n"
            "• **Machine Learning Forecast**: *'What is the predicted next-day price?'*, *'Which ML model was selected?'*, *'What do MAE and RMSE mean?'*, *'How reliable is the prediction?'*\n"
            "• **Portfolio & Paper Trading**: *'How much virtual cash do I have?'*, *'What stocks do I own?'*, *'How much profit or loss do I have?'*, *'How many shares of TCS do I own?'*\n"
            "• **Financial Concepts**: *'What is the stock market?'*, *'Difference between Linear Regression and Random Forest'*, *'What is diversification?'*\n\n"
            "Please ask your question or pick one of the topics above!"
        )

    # --------------------------------------------------------------------------
    # Main Generation Entry Point
    # --------------------------------------------------------------------------

    @classmethod
    def generate_response(
        cls,
        user_message: str,
        symbol: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_portfolio: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main Chatbot Entry Point.
        
        Args:
            user_message: The text query sent by the user
            symbol: Selected stock symbol (e.g. 'TCS', 'RELIANCE', 'INFY')
            context: Real-time stock analysis context dictionary
            conversation_history: Optional prior messages list
            user_portfolio: Optional authenticated user's portfolio and wallet data
            
        Returns:
            Structured dictionary with response text, symbol, provider used, and context.
        """
        clean_msg = (user_message or "").strip()
        if not clean_msg:
            return {
                'status': 'error',
                'message': 'User message cannot be empty.',
                'data': None
            }

        # Resolve symbol from argument or context
        target_symbol = symbol or (context.get('symbol') if context else None) or 'NIFTY'
        clean_symbol = InstrumentMappingService.normalize_symbol(target_symbol)

        # Build or normalize context
        if not context or not context.get('has_data', False):
            # Attempt to enrich context if missing
            resolved_context = cls.build_stock_context(clean_symbol)
            if context:
                # Merge client-provided overrides if any were present
                for k, v in context.items():
                    if v is not None and k in resolved_context:
                        resolved_context[k] = v
        else:
            resolved_context = cls.normalize_context(context, clean_symbol)

        now_ist_str = datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')

        # Determine AI Provider
        active_provider, api_key = cls.get_active_provider()
        response_text = None
        provider_used = 'domain_engine'

        # Attempt External AI API if configured
        if active_provider == 'gemini' and api_key:
            system_prompt = cls._build_system_prompt(clean_symbol, resolved_context, user_portfolio=user_portfolio)
            try:
                response_text = cls._call_gemini_api(
                    api_key=api_key,
                    system_prompt=system_prompt,
                    user_message=clean_msg,
                    history=conversation_history
                )
                if response_text:
                    provider_used = 'gemini'
            except Exception as e:
                logger.warning(f"[Chatbot] Gemini call failed, falling back to domain engine: {e}")

        elif active_provider == 'openai' and api_key:
            system_prompt = cls._build_system_prompt(clean_symbol, resolved_context, user_portfolio=user_portfolio)
            try:
                response_text = cls._call_openai_api(
                    api_key=api_key,
                    system_prompt=system_prompt,
                    user_message=clean_msg,
                    history=conversation_history
                )
                if response_text:
                    provider_used = 'openai'
            except Exception as e:
                logger.warning(f"[Chatbot] OpenAI call failed, falling back to domain engine: {e}")

        # Fallback to Built-in Financial Domain Engine if external API was not used or failed
        if not response_text:
            response_text = cls._generate_domain_response(
                clean_msg,
                clean_symbol,
                resolved_context,
                user_portfolio=user_portfolio,
                conversation_history=conversation_history
            )
            provider_used = 'domain_engine'

        return {
            'status': 'success',
            'message': 'Response generated successfully.',
            'data': {
                'response': response_text,
                'symbol': clean_symbol,
                'company_name': resolved_context.get('company_name', clean_symbol),
                'provider': provider_used,
                'context': resolved_context,
                'suggested_questions': cls.DEFAULT_SUGGESTIONS,
                'timestamp': now_ist_str
            }
        }
