from pymongo import MongoClient


def mongo_totals():
    client = MongoClient("mongodb://localhost:27017")
    col = client["orders_db"]["order_events"]
    col.delete_many({})                      # keeps the output the same on every run

    col.insert_many([
        {"event": "order_placed", "customer_id": 1, "amount": 500},
        {"event": "order_placed", "customer_id": 1, "amount": 450},
        {"event": "order_placed", "customer_id": 1, "amount": 350},
        {"event": "order_placed", "customer_id": 2, "amount": 200},
        {"event": "order_placed", "customer_id": 2, "amount": 100},
    ])

    pipeline = [
        {"$group": {"_id": "$customer_id", "total": {"$sum": "$amount"}}},
        {"$sort": {"_id": 1}},
    ]
    for row in col.aggregate(pipeline):
        if row["_id"] == 1:                  # remove this `if` to print every customer
            print(f"Mongo totals: customer {row['_id']} -> {row['total']}")