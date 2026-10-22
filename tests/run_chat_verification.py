import os
import sys
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app import create_app

app = create_app('testing')
client = app.test_client()

reliance_context = {
    'symbol': 'RELIANCE',
    'company_name': 'Reliance Industries Ltd',
    'current_price': 2950.00,
    'change': 18.50,
    'change_percent': 0.63,
    'previous_close': 2931.50,
    'day_high': 2968.00,
    'day_low': 2935.00,
    'rsi': 62.15,
    'macd': {'macd': 18.2, 'signal': 12.0, 'histogram': 6.2},
    'ma20': 2910.00,
    'ma50': 2860.00,
    'ml_prediction': {
        'predicted_price': 2985.00,
        'predicted_change': 35.00,
        'predicted_change_percentage': 1.19,
        'direction': 'UP',
        'selected_model': 'Random Forest Regressor'
    },
    'recommendation': {
        'verdict': 'BUY',
        'signal_score': 55,
        'normalized_score': 77.5,
        'explanation': 'Strong bullish technical alignment and positive ML forecast.',
        'supporting_indicators': [
            {'name': 'RSI (14)', 'score': 15, 'signal': 'BULLISH', 'interpretation': 'Constructive bullish momentum (62.15).'},
            {'name': 'MACD (12, 26, 9)', 'score': 20, 'signal': 'BULLISH', 'interpretation': 'Bullish crossover with positive histogram.'},
            {'name': 'Price vs MA20', 'score': 10, 'signal': 'BULLISH', 'interpretation': 'Price trading above MA20.'},
            {'name': 'Price vs MA50', 'score': 10, 'signal': 'BULLISH', 'interpretation': 'Price trading above MA50.'},
            {'name': 'ML Next-Day Forecast', 'score': 25, 'signal': 'BULLISH', 'interpretation': 'Moderate Bullish ML forecast (+1.19%).'}
        ]
    },
    'has_data': True
}

tcs_context = {
    'symbol': 'TCS',
    'company_name': 'Tata Consultancy Services Ltd',
    'current_price': 3850.50,
    'change': -12.40,
    'change_percent': -0.32,
    'previous_close': 3862.90,
    'day_high': 3875.00,
    'day_low': 3840.00,
    'rsi': 54.30,
    'macd': {'macd': 5.40, 'signal': 7.10, 'histogram': -1.70},
    'ma20': 3820.10,
    'ma50': 3790.00,
    'ml_prediction': {
        'predicted_price': 3865.00,
        'predicted_change': 14.50,
        'predicted_change_percentage': 0.38,
        'direction': 'UP',
        'selected_model': 'Linear Regression'
    },
    'recommendation': {
        'verdict': 'HOLD',
        'signal_score': 10,
        'normalized_score': 55.0,
        'explanation': 'Neutral momentum near 50 RSI and mild ML projection.',
        'supporting_indicators': [
            {'name': 'RSI (14)', 'score': 0, 'signal': 'NEUTRAL', 'interpretation': 'Neutral consolidation around 50 midline.'},
            {'name': 'MACD (12, 26, 9)', 'score': -10, 'signal': 'BEARISH', 'interpretation': 'MACD below signal line.'},
            {'name': 'Price vs MA20', 'score': 10, 'signal': 'BULLISH', 'interpretation': 'Price trading above MA20.'},
            {'name': 'Price vs MA50', 'score': 10, 'signal': 'BULLISH', 'interpretation': 'Price trading above MA50.'}
        ]
    },
    'has_data': True
}

test_cases = [
    {
        'title': 'Test 1: What is the current price? (RELIANCE)',
        'payload': {
            'user_message': 'What is the current price?',
            'symbol': 'RELIANCE',
            'context': reliance_context
        }
    },
    {
        'title': 'Test 2: What does the RSI value mean? (TCS)',
        'payload': {
            'user_message': 'What does the RSI value mean?',
            'symbol': 'TCS',
            'context': tcs_context
        }
    },
    {
        'title': 'Test 3: What is MACD? (RELIANCE)',
        'payload': {
            'user_message': 'What is MACD?',
            'symbol': 'RELIANCE',
            'context': reliance_context
        }
    },
    {
        'title': 'Test 4: What is the MA20 and MA50? (TCS)',
        'payload': {
            'user_message': 'What is the MA20 and MA50?',
            'symbol': 'TCS',
            'context': tcs_context
        }
    },
    {
        'title': 'Test 5: What is the ML predicted price? (RELIANCE)',
        'payload': {
            'user_message': 'What is the ML predicted price?',
            'symbol': 'RELIANCE',
            'context': reliance_context
        }
    },
    {
        'title': 'Test 6: What is the current AI recommendation? (TCS)',
        'payload': {
            'user_message': 'What is the current AI recommendation?',
            'symbol': 'TCS',
            'context': tcs_context
        }
    },
    {
        'title': 'Test 7: Why did the system generate this recommendation? (RELIANCE)',
        'payload': {
            'user_message': 'Why did the system generate this recommendation?',
            'symbol': 'RELIANCE',
            'context': reliance_context
        }
    },
    {
        'title': 'Test 8: Graceful Handling of Missing Symbol',
        'payload': {
            'user_message': 'What is the current stock price?',
            'context': {}
        }
    }
]

def run_tests():
    print("=" * 80)
    print("StockSense AI - POST /api/chat Verification Suite")
    print("=" * 80)
    all_passed = True
    
    for tc in test_cases:
        print(f"\n>>> {tc['title']}")
        resp = client.post('/api/chat', data=json.dumps(tc['payload']), content_type='application/json')
        status_code = resp.status_code
        res_data = resp.get_json()
        print(f"Status Code: {status_code}")
        
        if status_code == 200:
            data = res_data.get('data', {})
            response_text = data.get('response', '')
            print(f"Symbol: {data.get('symbol')} ({data.get('company_name')})")
            print(f"Provider: {data.get('provider')}")
            print(f"Response (Full Text):\n{response_text}")
        else:
            print(f"Error Response (Expected): {res_data}")
            if tc['title'].startswith("Test 8") and status_code == 400:
                print(">> Verification PASSED: Graceful 400 Bad Request on missing symbol.")
            else:
                all_passed = False
                
    print("\n" + "=" * 80)
    print("All Verification Tests Completed.")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
