from src.database import SessionLocal
from src.models import Customer, Product, Order
from src.orders import place_order, get_stock
from mongo_events import mongo_totals



def reset_data(stock):
    with SessionLocal.begin() as s:
        s.query(Order).delete()
        s.query(Product).delete()
        s.query(Customer).delete()
        s.add(Customer(id=1, name="Asha", email="asha@example.com"))
        s.add(Product(id=1, name="Laptop", price=650, stock=stock))


# 1) Successful order
reset_data(10)
old, new = place_order(customer_id=1, product_id=1, qty=2)
print(f"Order placed: stock {old} -> {new}")

# 2) Atomicity proof: error AFTER the stock update
reset_data(10)
try:
    place_order(customer_id=1, product_id=1, qty=2, fail_after_update=True)
except RuntimeError:
    print(f"Forced failure: rolled back, stock still {get_stock(1)}")

# 3) MongoDB aggregation
mongo_totals()