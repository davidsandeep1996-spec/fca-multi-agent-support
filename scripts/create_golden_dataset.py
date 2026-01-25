"""
Create Golden Dataset
Generates a static JSON file with 50 'Golden' questions and expected intents
for regression testing.
"""
import json
import os

# Define 50 strictly curated questions
GOLDEN_DATA = [
    # --- ACCOUNT INQUIRY (15) ---
    {"q": "What is my current account balance?", "intent": "account_inquiry"},
    {"q": "How much money do I have?", "intent": "account_inquiry"},
    {"q": "Show me my recent transactions", "intent": "account_inquiry"},
    {"q": "List my last 5 purchases", "intent": "account_inquiry"},
    {"q": "Did I spend money at Starbucks yesterday?", "intent": "account_inquiry"},
    {"q": "What is my savings account number?", "intent": "account_inquiry"},
    {"q": "Do I have any pending transfers?", "intent": "account_inquiry"},
    {"q": "Check my checking account balance", "intent": "account_inquiry"},
    {"q": "Download my monthly statement", "intent": "account_inquiry"},
    {"q": "When was my last deposit?", "intent": "account_inquiry"},
    {"q": "What is the routing number for my account?", "intent": "account_inquiry"},
    {"q": "Can you show me my transaction history?", "intent": "account_inquiry"},
    {"q": "How much interest have I earned?", "intent": "account_inquiry"},
    {"q": "What's my available credit?", "intent": "account_inquiry"},
    {"q": "Balance check please", "intent": "account_inquiry"},

    # --- PRODUCT INQUIRY (15) ---
    {"q": "I want to apply for a personal loan", "intent": "loan_inquiry"},
    {"q": "What are your mortgage rates?", "intent": "loan_inquiry"},
    {"q": "Tell me about your credit cards", "intent": "product_inquiry"},
    {"q": "Do you offer student loans?", "intent": "loan_inquiry"},
    {"q": "I need a high interest savings account", "intent": "product_inquiry"}, # May map to savings_inquiry
    {"q": "What are the terms for a fixed rate mortgage?", "intent": "loan_inquiry"},
    {"q": "Can I get a loan for a new car?", "intent": "loan_inquiry"},
    {"q": "Compare your credit card options", "intent": "product_inquiry"},
    {"q": "I want to open a new ISA", "intent": "product_inquiry"},
    {"q": "What are the interest rates for savings?", "intent": "product_inquiry"},
    {"q": "How do I apply for a gold credit card?", "intent": "product_inquiry"},
    {"q": "Tell me about the Platinum account", "intent": "product_inquiry"},
    {"q": "I am looking for a travel insurance product", "intent": "product_inquiry"},
    {"q": "What investment products do you have?", "intent": "product_inquiry"},
    {"q": "I want to borrow 5000 pounds", "intent": "loan_inquiry"},

    # --- GENERAL INQUIRY (10) ---
    {"q": "What are your opening hours?", "intent": "general_inquiry"},
    {"q": "Where is the nearest branch?", "intent": "general_inquiry"},
    {"q": "How do I reset my password?", "intent": "account_inquiry"},
    {"q": "Is the app down?", "intent": "general_inquiry"},
    {"q": "What is your phone number?", "intent": "general_inquiry"},
    {"q": "Can I visit a branch on Sunday?", "intent": "general_inquiry"},
    {"q": "How do I change my address?", "intent": "general_inquiry"},
    {"q": "Are you open on bank holidays?", "intent": "general_inquiry"},
    {"q": "What documents do I need to join?", "intent": "general_inquiry"},
    {"q": "Is there parking at the city branch?", "intent": "general_inquiry"},

    # --- COMPLAINT / HUMAN (10) ---
    {"q": "I want to speak to a human", "intent": "complaint"},
    {"q": "This service is terrible, let me talk to a manager", "intent": "complaint"},
    {"q": "I want to make a formal complaint", "intent": "complaint"},
    {"q": "Why was I charged this fee? It's unfair.", "intent": "complaint"},
    {"q": "Escalate this conversation immediately", "intent": "complaint"},
    {"q": "I am very unhappy with your service", "intent": "complaint"},
    {"q": "Connect me to an agent", "intent": "complaint"},
    {"q": "Your bot is not helping me", "intent": "complaint"},
    {"q": "I need to speak to someone about fraud", "intent": "complaint"},
    {"q": "This information is wrong, who can I call?", "intent": "complaint"},
]

def generate_file():
    file_path = os.path.join(os.path.dirname(__file__), "golden_questions.json")

    # Ensure distinct intent mapping
    # Note: Your classifier might map 'loan_inquiry' -> 'product' in the workflow routing.
    # The evaluation script should handle this mapping or check the raw intent.

    with open(file_path, "w") as f:
        json.dump(GOLDEN_DATA, f, indent=2)

    print(f"✅ Generated {len(GOLDEN_DATA)} Golden Questions at: {file_path}")

if __name__ == "__main__":
    generate_file()
