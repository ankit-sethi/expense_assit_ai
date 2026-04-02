CATEGORY_MAP = {
    "Amazon": ("Shopping", "Online Shopping"),
    "Flipkart": ("Shopping", "Online Shopping"),
    "Meesho": ("Shopping", "Online Shopping"),
    "Myntra": ("Shopping", "Fashion"),
    "Ajio": ("Shopping", "Fashion"),
    "Nykaa": ("Shopping", "Beauty"),
    "Swiggy": ("Food", "Food Delivery"),
    "Zomato": ("Food", "Food Delivery"),
    "Blinkit": ("Food", "Grocery Delivery"),
    "BigBasket": ("Food", "Grocery Delivery"),
    "Dunzo": ("Food", "Grocery Delivery"),
    "Uber Eats": ("Food", "Food Delivery"),
    "Uber": ("Transport", "Ride Hailing"),
    "Ola": ("Transport", "Ride Hailing"),
    "Rapido": ("Transport", "Ride Hailing"),
    "RedBus": ("Transport", "Bus"),
    "IRCTC": ("Transport", "Train"),
    "IndiGo": ("Transport", "Flight"),
    "Air India": ("Transport", "Flight"),
    "Netflix": ("Entertainment", "Streaming"),
    "Hotstar": ("Entertainment", "Streaming"),
    "Spotify": ("Entertainment", "Streaming"),
    "Apple Music": ("Entertainment", "Streaming"),
    "YouTube": ("Entertainment", "Streaming"),
    "BookMyShow": ("Entertainment", "Events"),
    "HDFC": ("Bills", "Bank"),
    "SBI": ("Bills", "Bank"),
    "Axis": ("Bills", "Bank"),
    "ICICI": ("Bills", "Bank"),
    "Kotak": ("Bills", "Bank"),
    "Airtel": ("Bills", "Telecom"),
    "Jio": ("Bills", "Telecom"),
    "Vi": ("Bills", "Telecom"),
    "BESCOM": ("Bills", "Electricity"),
    "Tata Power": ("Bills", "Electricity"),
    "PhonePe": ("Finance", "UPI"),
    "GPay": ("Finance", "UPI"),
    "Paytm": ("Finance", "Wallet"),
    "Apollo": ("Health", "Pharmacy"),
    "Practo": ("Health", "Consultation"),
    "1mg": ("Health", "Pharmacy"),
    "MakeMyTrip": ("Travel", "Booking"),
    "Goibibo": ("Travel", "Booking"),
}

# Precompute lowercased keys so normalize() doesn't do it on every call
_CATEGORY_MAP_LOWER = {k.lower(): v for k, v in CATEGORY_MAP.items()}


class Categorizer:

    def normalize(self, txn: dict) -> dict:
        merchant_lower = txn.get("merchant", "").lower()
        category, sub_category = "Other", ""

        for key, (cat, sub) in _CATEGORY_MAP_LOWER.items():
            if key in merchant_lower:
                category, sub_category = cat, sub
                break

        txn["category"] = category
        txn["sub_category"] = sub_category
        return txn
