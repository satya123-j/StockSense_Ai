import urllib.request
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def test_live_server():
    print("=" * 70)
    print("1. Verifying HTML Page and Chatbot Assets on Live Server")
    print("=" * 70)

    url_page = 'http://127.0.0.1:5000/analysis/RELIANCE'
    req_page = urllib.request.Request(url_page)
    with urllib.request.urlopen(req_page) as resp:
        html = resp.read().decode('utf-8')
        has_launcher = 'id="chatbot-launcher"' in html
        has_panel = 'id="chatbot-panel"' in html
        has_css = 'chatbot.css' in html
        has_js = 'chatbot.js' in html
        print(f"Page Load Status: {resp.status} OK")
        print(f"Chatbot Launcher Button in HTML: {has_launcher}")
        print(f"Chatbot Panel in HTML: {has_panel}")
        print(f"Chatbot CSS Included: {has_css}")
        print(f"Chatbot JS Included: {has_js}")

    # Check static assets serve 200 OK
    for asset in ['/static/css/chatbot.css', '/static/js/chatbot.js']:
        req_asset = urllib.request.Request(f'http://127.0.0.1:5000{asset}')
        with urllib.request.urlopen(req_asset) as resp_asset:
            print(f"Asset Check [{asset}]: HTTP {resp_asset.status} OK")

    print("\n" + "=" * 70)
    print("2. Testing 5 Required Questions Against POST /api/chat")
    print("=" * 70)

    test_questions = [
        ("What is the current price?", "RELIANCE"),
        ("What does the RSI indicate?", "RELIANCE"),
        ("Explain the MACD.", "RELIANCE"),
        ("Why is the recommendation HOLD?", "TCS"),
        ("What is the predicted price?", "RELIANCE")
    ]

    for idx, (q, sym) in enumerate(test_questions, start=1):
        payload = json.dumps({'user_message': q, 'symbol': sym}).encode('utf-8')
        req = urllib.request.Request(
            'http://127.0.0.1:5000/api/chat',
            data=payload,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            print(f"\n--- Question {idx}: ({sym}) \"{q}\" ---")
            print(f"HTTP Status: {resp.status} | API Status: {res.get('status')}")
            print(f"Provider: {res['data'].get('provider')}")
            print(f"Symbol: {res['data'].get('symbol')} ({res['data'].get('company_name')})")
            answer = res['data']['response']
            print(f"Chatbot Answer:\n{answer}")

    print("\n" + "=" * 70)
    print("All 5 Question Tests Completed Successfully.")
    print("=" * 70)

if __name__ == '__main__':
    test_live_server()
