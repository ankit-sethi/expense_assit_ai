import re
from ingestion.gmail_client import GmailClient


# ------------------------
# Strong Transaction Filter
# ------------------------
def is_transaction_email(text: str):

    text = text.lower()

    strong_keywords = [
        "debited",
        "credited",
        "upi",
        "rs.",
        "inr",
        "a/c",
        "account"
    ]

    score = sum(1 for k in strong_keywords if k in text)

    return score >= 2


# ------------------------
# Improved Transaction Parser
# ------------------------
def parse_transaction(text: str):

    text_lower = text.lower()

    confidence = 0

    # amount
    amount_pattern = r"(?:INR|Rs\.?)\s?([0-9,]+(?:\.[0-9]{1,2})?)"
    amount_match = re.search(amount_pattern, text, re.IGNORECASE)

    if amount_match:
        confidence += 1
        amount = float(amount_match.group(1).replace(",", ""))
    else:
        amount = None

    # merchant
    merchant_pattern = r"(?:at|for|name|to)\s+([A-Za-z0-9 &\.-]+)"
    merchant_match = re.search(merchant_pattern, text, re.IGNORECASE)

    if merchant_match:
        confidence += 1
        merchant = merchant_match.group(1).strip()
    else:
        merchant = None

    # debit indicator
    if "debited" in text_lower or "spent" in text_lower:
        confidence += 1

    if confidence >= 2:
        return {
            "amount": amount,
            "merchant": merchant,
            "confidence": confidence
        }

    return None


# ------------------------
# Main Test Runner
# ------------------------
def run_test():

    print("\n🔍 Fetching emails...\n")

    client = GmailClient()
    messages = client.fetch_messages()

    print(f"Total messages fetched: {len(messages)}\n")

    for idx, msg in enumerate(messages, 1):

        print("=" * 80)
        print(f"EMAIL #{idx}")
        print("-" * 80)

        raw_text = msg["raw_text"]

        print("Preview:")
        print(raw_text[:300])
        print("\n")

        if not is_transaction_email(raw_text):
            print("❌ Rejected by transaction filter\n")
            continue

        print("✅ Passed filter")

        parsed = parse_transaction(raw_text)

        if not parsed:
            print("❌ Failed parsing\n")
        else:
            print("🎯 Parsed Result:")
            print(parsed)

        print("\n")


if __name__ == "__main__":
    run_test()
