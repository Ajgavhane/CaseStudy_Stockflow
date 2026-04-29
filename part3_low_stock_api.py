from flask import jsonify, g
from sqlalchemy import func
from datetime import datetime, timedelta
from models import (db, Company, Product, Inventory,
                    Warehouse, Supplier, ProductSupplier, InventoryLog)

RECENT_SALES_DAYS = 30  # would move to company-level config in production

@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
@login_required
def low_stock_alerts(company_id):

    # Auth: user must belong to this company
    if g.current_user.company_id != company_id:
        return jsonify({"error": "Forbidden"}), 403

    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404

    recent_date = datetime.utcnow() - timedelta(days=RECENT_SALES_DAYS)

    # Step 1: Get all (product, warehouse) pairs below threshold for this company
    low_stock_rows = (
        db.session.query(Product, Inventory, Warehouse)
        .join(Inventory, Inventory.product_id == Product.id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .filter(
            Warehouse.company_id == company_id,
            Product.is_active == True,
            Inventory.quantity < Product.low_stock_threshold
        )
        .all()
    )

    # Step 2: Filter by recent sales activity + calculate days until stockout
    # N+1 here — acceptable for now, worth batching if this becomes slow
    alerts = []

    for product, inventory, warehouse in low_stock_rows:

        # Sum units sold in last 30 days for this specific (product, warehouse)
        total_sold = (
            db.session.query(func.sum(func.abs(InventoryLog.quantity_delta)))
            .filter(
                InventoryLog.inventory_id == inventory.id,
                InventoryLog.change_type == 'sale',
                InventoryLog.created_at >= recent_date
            )
            .scalar() or 0
        )

        # Skip if no recent sales — per business rule
        if total_sold == 0:
            continue

        avg_daily_sales = total_sold / RECENT_SALES_DAYS

        # Return null if velocity rounds to zero — null is more honest than 0
        days_until_stockout = (
            round(inventory.quantity / avg_daily_sales)
            if avg_daily_sales > 0 else None
        )

        # Step 3: Get primary supplier, fall back to first if none marked primary
        supplier = (
            db.session.query(Supplier)
            .join(ProductSupplier, ProductSupplier.supplier_id == Supplier.id)
            .filter(ProductSupplier.product_id == product.id)
            .order_by(ProductSupplier.is_primary.desc())
            .first()
        )

        alerts.append({
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "current_stock": inventory.quantity,
            "threshold": product.low_stock_threshold,
            "days_until_stockout": days_until_stockout,
            "supplier": {
                "id": supplier.id,
                "name": supplier.name,
                "contact_email": supplier.contact_email
            } if supplier else None
        })

    # Sort by urgency: soonest stockout first, nulls at the bottom
    alerts.sort(key=lambda a: (
        a["days_until_stockout"] is None,
        a["days_until_stockout"]
    ))

    # TODO: add pagination before production — large companies could have hundreds of alerts

    return jsonify({
        "alerts": alerts,
        "total_alerts": len(alerts)
    }), 200
