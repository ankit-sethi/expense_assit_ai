CATEGORY_MAP = {
    "Amazon": "Shopping",
    "Swiggy": "Food",
    "SBI": "Bills",
    "Zomato": "Food",
    "HDFC": "Bills",
    "Flipkart": "Shopping",
    "Rapido": "Transport",
    "Uber": "Transport",
    "Netflix": "Entertainment",
    "Apple Music": "Entertainment",
    "Axis": "Bills"
}

class Categorizer:

    def normalize(self, txn):

        txn["category"] = CATEGORY_MAP.get(txn["merchant"], "Other")

        return txn
