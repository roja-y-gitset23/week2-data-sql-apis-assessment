
from sqlalchemy import select
from src.database import SessionLocal
from src.models import Product, Order


class InsufficientStock(Exception):
    pass


def place_order(customer_id, product_id, qty, fail_after_update=False):
    """Reduce stock and insert order in ONE transaction.
    Any exception rolls back everything. Returns (old_stock, new_stock)."""
    with SessionLocal.begin() as session:   # commit on success, rollback on any error
        product = session.execute(
            select(Product).where(Product.id == product_id).with_for_update()
        ).scalar_one_or_none()

        if product is None:
            raise ValueError("Product not found")
        if product.stock < qty:
            raise InsufficientStock(f"Only {product.stock} in stock")

        old_stock = product.stock
        product.stock -= qty
        session.flush()                      # stock UPDATE sent to DB (not yet committed)

        if fail_after_update:
            raise RuntimeError("Forced failure after stock update")

        session.add(Order(customer_id=customer_id, product_id=product_id, qty=qty))
        return old_stock, product.stock


def get_stock(product_id):
    with SessionLocal() as session:
        return session.get(Product, product_id).stock