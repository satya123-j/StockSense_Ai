import logging
import re
from flask import Blueprint, request
from backend.app.services.chatbot_service import ChatbotService
from backend.app.services.instrument_mapping_service import InstrumentMappingService, NSE_INSTRUMENTS_MASTER
from backend.app.utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)

chatbot_bp = Blueprint('chatbot_api', __name__, url_prefix='/api')


def _extract_symbol_from_message(message: str) -> str:
    """
    Attempts to detect a known Indian stock ticker mentioned in the user message.
    """
    if not message:
        return ""
    upper_msg = message.upper()
    for item in NSE_INSTRUMENTS_MASTER:
        sym = item['symbol'].upper()
        # Word boundary match for exact symbol
        if re.search(rf'\b{re.escape(sym)}\b', upper_msg):
            return sym
    return ""


@chatbot_bp.route('/chat', methods=['POST'])
def chat():
    """
    AI Stock Chatbot API Endpoint:
    POST /api/chat

    Request JSON:
    {
        "user_message": "What is the current price?", // Required
        "symbol": "RELIANCE",                         // Required (or in context / message)
        "context": { ... }                            // Optional real-time stock context
    }

    The API:
    1. Validates the incoming request and ensures user_message is provided.
    2. Resolves and validates the stock symbol.
    3. Retrieves or normalizes the stock analysis context (price, RSI, MACD, MA, ML, recommendation).
    4. Invokes ChatbotService to generate a grounded, factual response.
    5. Handles missing symbols, invalid JSON, and errors gracefully.
    6. Never exposes API keys or secrets.
    7. Never invents or hallucinates stock values.
    8. Keeps responses focused on StockSense AI and stock analysis.
    """
    try:
        payload = request.get_json(silent=True)
        if payload is None:
            return error_response(
                "Invalid request. Request body must be valid JSON with 'user_message' and 'symbol'.",
                status_code=400
            )

        # 1. Validate user_message
        user_message = payload.get('user_message') or payload.get('message')
        if not user_message or not isinstance(user_message, str) or not user_message.strip():
            return error_response(
                "Field 'user_message' is required and must not be empty.",
                status_code=400
            )

        user_message = user_message.strip()

        # 2. Validate and resolve symbol
        raw_symbol = payload.get('symbol')
        raw_context = payload.get('context')

        # Fallback to symbol inside context if present
        if not raw_symbol and isinstance(raw_context, dict):
            raw_symbol = raw_context.get('symbol')

        # Fallback to extracting known ticker from the message text
        if not raw_symbol:
            raw_symbol = _extract_symbol_from_message(user_message)

        if not raw_symbol or not isinstance(raw_symbol, str) or not raw_symbol.strip():
            return error_response(
                "Stock symbol is required. Please specify a valid symbol (e.g. 'RELIANCE' or 'TCS').",
                status_code=400
            )

        clean_symbol = InstrumentMappingService.normalize_symbol(raw_symbol.strip())

        # 3. Get the selected stock context
        # If client passed context with actual data, normalize it.
        # If context is missing, partial, or empty, automatically build/fetch verified data.
        resolved_context = None
        if isinstance(raw_context, dict) and raw_context:
            normalized = ChatbotService.normalize_context(raw_context, clean_symbol)
            if normalized.get('has_data', False):
                resolved_context = normalized

        if resolved_context is None:
            # Fetch live verified context from backend services
            resolved_context = ChatbotService.build_stock_context(clean_symbol)
            if isinstance(raw_context, dict):
                # Merge any client-supplied non-null overrides
                for k, v in raw_context.items():
                    if v is not None and k in resolved_context:
                        resolved_context[k] = v

        # 4. Optional user portfolio context if authenticated
        user_portfolio = None
        try:
            from backend.app.utils.decorators import get_authenticated_user
            auth_user = get_authenticated_user()
            if auth_user:
                from backend.app.services.wallet_service import WalletService
                from backend.app.services.paper_trading_service import PaperTradingService
                wallet_bal = WalletService.get_balance(auth_user.id)
                summary = PaperTradingService.get_portfolio_summary(auth_user.id)
                holdings = PaperTradingService.get_user_holdings(auth_user.id)
                txs = PaperTradingService.get_user_transactions(auth_user.id, limit=5)
                user_portfolio = {
                    'authenticated': True,
                    'user_id': auth_user.id,
                    'username': auth_user.username,
                    'virtual_cash': wallet_bal,
                    'portfolio_summary': summary,
                    'holdings': holdings,
                    'recent_transactions': txs
                }
            else:
                user_portfolio = {'authenticated': False}
        except Exception as e:
            logger.warning(f"[Chatbot] Error assembling user portfolio context: {e}")
            user_portfolio = {'authenticated': False}

        # 5. Generate response from ChatbotService
        history = payload.get('history') or payload.get('conversation_history')
        result = ChatbotService.generate_response(
            user_message=user_message,
            symbol=clean_symbol,
            context=resolved_context,
            conversation_history=history,
            user_portfolio=user_portfolio
        )

        if result.get('status') == 'error':
            return error_response(
                result.get('message', 'Failed to generate chatbot response.'),
                status_code=400
            )

        data = result.get('data', {})
        # Ensure 'answer' field is also available alongside 'response'
        if 'response' in data and 'answer' not in data:
            data['answer'] = data['response']

        # Sanitize data to guarantee no API keys or secrets could ever leak
        data.pop('api_key', None)
        data.pop('key', None)

        return success_response(data=data, message="Chatbot response generated successfully.")

    except Exception as e:
        logger.error(f"[Chatbot API Error]: {e}", exc_info=True)
        return error_response(
            "An error occurred while processing the chatbot request. Please try again.",
            status_code=500
        )


@chatbot_bp.route('/chat/status', methods=['GET'])
def chat_status():
    """
    Chatbot Status Endpoint:
    GET /api/chat/status

    Returns the active provider, configuration status, and supported queries.
    Never exposes API keys.
    """
    status_info = ChatbotService.get_status()
    # Ensure no keys are present
    status_info.pop('api_key', None)
    status_info.pop('key', None)
    return success_response(data=status_info)


@chatbot_bp.route('/chat/context/<symbol>', methods=['GET'])
def get_chat_context(symbol):
    """
    Fetches the complete real-time quantitative context for a stock:
    GET /api/chat/context/<symbol>

    Returns actual available market price, RSI, MACD, MA20/50, ML prediction, and recommendation.
    Never invents stock values.
    """
    if not symbol:
        return error_response("Symbol parameter is required.", status_code=400)

    clean_symbol = InstrumentMappingService.normalize_symbol(symbol)
    context = ChatbotService.build_stock_context(clean_symbol)

    return success_response(data=context)
