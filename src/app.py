# app.py — Complete working DineLine POC
# Dependencies: pip install flask twilio spacy
# python -m spacy download en_core_web_sm

from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import spacy
import json
import sqlite3
from datetime import datetime

app = Flask(__name__)
nlp = spacy.load("en_core_web_sm")

# Simple menu
MENU = {
    "butter chicken": 320, "garlic naan": 60, "biryani": 280,
    "paneer tikka": 260, "dal makhani": 220, "rice": 80,
    "chicken tikka": 300, "lassi": 90, "gulab jamun": 120
}

# Init SQLite (no Docker needed)
def init_db():
    conn = sqlite3.connect("orders.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT, items TEXT, total REAL,
        created_at TEXT
    )""")
    conn.commit()
    conn.close()

def parse_order(text):
    """Extract items and quantities from speech text."""
    text = text.lower()
    order_items = []
    
    # Number words mapping
    numbers = {"one":1,"two":2,"three":3,"four":4,"five":5,
               "a ":1,"an ":1}
    
    for item, price in MENU.items():
        if item in text:
            qty = 1
            # Check for quantity before item
            for word, num in numbers.items():
                if word + item in text:
                    qty = num
                    break
            order_items.append({
                "item": item, "qty": qty, "price": price
            })
    
    return order_items

def save_order(phone, items, total):
    conn = sqlite3.connect("orders.db")
    conn.execute(
        "INSERT INTO orders (phone, items, total, created_at) VALUES (?,?,?,?)",
        (phone, json.dumps(items), total, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

@app.route("/answer", methods=['POST'])
def answer_call():
    response = VoiceResponse()
    gather = Gather(
        input='speech',
        action='/process_order',
        timeout=5,
        speech_timeout='auto',
        language='en-IN'
    )
    gather.say(
        "Welcome to DineLine! Please tell me your order. "
        "We have butter chicken, biryani, paneer tikka, garlic naan and more.",
        voice='Polly.Aditi'
    )
    response.append(gather)
    response.say("I didn't catch that. Please call again.")
    return str(response)

@app.route("/process_order", methods=['POST'])
def process_order():
    speech = request.form.get('SpeechResult', '')
    phone = request.form.get('From', 'unknown')
    
    print(f"\n{'='*50}")
    print(f"CALL FROM: {phone}")
    print(f"CUSTOMER SAID: {speech}")
    
    response = VoiceResponse()
    items = parse_order(speech)
    
    if not items:
        # Nothing recognised — ask again
        gather = Gather(
            input='speech',
            action='/process_order',
            timeout=5,
            speech_timeout='auto'
        )
        gather.say(
            "Sorry, I didn't catch your order. "
            "Could you please repeat? For example, say: "
            "two butter chickens and one garlic naan.",
            voice='Polly.Aditi'
        )
        response.append(gather)
        return str(response)
    
    # Build confirmation
    total = sum(i['qty'] * i['price'] for i in items)
    order_summary = ", ".join(
        [f"{i['qty']} {i['item']}" for i in items]
    )
    
    print(f"PARSED ORDER: {items}")
    print(f"TOTAL: ₹{total}")
    print(f"{'='*50}\n")
    
    # Save to DB
    save_order(phone, items, total)
    
    # Confirm to caller
    gather = Gather(
        input='speech',
        action='/confirm_order',
        timeout=5
    )
    gather.say(
        f"I have {order_summary}, totalling rupees {int(total)}. "
        f"Shall I confirm this order? Say yes or no.",
        voice='Polly.Aditi'
    )
    response.append(gather)
    return str(response)

@app.route("/confirm_order", methods=['POST'])
def confirm_order():
    speech = request.form.get('SpeechResult', '').lower()
    response = VoiceResponse()
    
    if 'yes' in speech or 'confirm' in speech or 'correct' in speech:
        response.say(
            "Your order is confirmed! It will be ready in 30 minutes. "
            "Thank you for ordering with DineLine. Goodbye!",
            voice='Polly.Aditi'
        )
    else:
        response.say(
            "No problem. Please call again when you're ready to order. "
            "Thank you. Goodbye!",
            voice='Polly.Aditi'
        )
    
    response.hangup()
    return str(response)

@app.route("/orders", methods=['GET'])
def view_orders():
    """View all orders — open in browser."""
    conn = sqlite3.connect("orders.db")
    orders = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    
    result = []
    for o in orders:
        result.append({
            "id": o[0], "phone": o[1],
            "items": json.loads(o[2]),
            "total": o[3], "created_at": o[4]
        })
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    init_db()
    print("DineLine POC starting...")
    print("Endpoints: /answer, /process_order, /confirm_order, /orders")
    app.run(debug=True, port=8080)