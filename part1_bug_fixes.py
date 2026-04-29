from decimal import Decimal
from sqlalchemy.exc import IntegrityError

@app.route('/api/products', methods=['POST'])
@login_required
def create_product():
    data = request.json or {}

    # 1. Validate required fields
    required = ['name', 'sku', 'price', 'warehouse_id']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return {"error": f"Missing required fields: {missing}"}, 400

    # 2. Validate and cast price (Decimal, not float — money precision)
    try:
        price = Decimal(str(data['price']))
        assert price >= 0
    except:
        return {"error": "Price must be a non-negative number"}, 400

    # 3. Handle optional initial_quantity (defaults to 0)
    try:
        quantity = int(data.get('initial_quantity', 0))
        assert quantity >= 0
    except:
        return {"error": "Quantity must be a non-negative integer"}, 400

    # 4. Warehouse ownership check (multi-tenant isolation)
    warehouse = Warehouse.query.filter_by(
        id=data['warehouse_id'],
        company_id=current_user.company_id
    ).first()
    if not warehouse:
        return {"error": "Warehouse not found"}, 404

    # 5. SKU uniqueness check
    if Product.query.filter_by(sku=data['sku']).first():
        return {"error": "SKU already in use"}, 409

    # 6. Single atomic transaction — both records commit or neither does
    try:
        product = Product(
            name=data['name'],
            sku=data['sku'],
            price=price
        )
        db.session.add(product)
        db.session.flush()  # get product.id without committing yet

        inventory = Inventory(
            product_id=product.id,
            warehouse_id=data['warehouse_id'],
            quantity=quantity
        )
        db.session.add(inventory)
        db.session.commit()

    except IntegrityError:
        # Race condition fallback — two requests hit same SKU simultaneously
        db.session.rollback()
        return {"error": "SKU already exists"}, 409

    except Exception:
        db.session.rollback()
        return {"error": "Internal server error"}, 500

    return {"message": "Product created", "product_id": product.id}, 201
