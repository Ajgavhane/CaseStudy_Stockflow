-- Companies
CREATE TABLE companies (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Warehouses
CREATE TABLE warehouses (
    id         SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(id),
    name       VARCHAR(255) NOT NULL,
    location   TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_warehouses_company ON warehouses(company_id);

-- Suppliers
CREATE TABLE suppliers (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    contact_email VARCHAR(255),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Users (referenced in inventory_logs for audit trail)
CREATE TABLE users (
    id         SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(id),
    email      VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Products
CREATE TABLE products (
    id                  SERIAL PRIMARY KEY,
    company_id          INT NOT NULL REFERENCES companies(id),
    name                VARCHAR(255) NOT NULL,
    sku                 VARCHAR(100) NOT NULL,
    price               NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    product_type        VARCHAR(50) NOT NULL DEFAULT 'standard',
    low_stock_threshold INT NOT NULL DEFAULT 10,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- SKU unique per company, not globally
    UNIQUE (company_id, sku)
);

CREATE INDEX idx_products_company ON products(company_id);

-- Product-Supplier mapping (many-to-many)
CREATE TABLE product_suppliers (
    product_id  INT NOT NULL REFERENCES products(id),
    supplier_id INT NOT NULL REFERENCES suppliers(id),
    is_primary  BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (product_id, supplier_id)
);

-- Inventory (one row per product per warehouse)
CREATE TABLE inventory (
    id           SERIAL PRIMARY KEY,
    product_id   INT NOT NULL REFERENCES products(id),
    warehouse_id INT NOT NULL REFERENCES warehouses(id),
    quantity     INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (product_id, warehouse_id)
);

CREATE INDEX idx_inventory_product   ON inventory(product_id);
CREATE INDEX idx_inventory_warehouse ON inventory(warehouse_id);

-- Inventory logs (audit trail for every stock change)
CREATE TABLE inventory_logs (
    id             SERIAL PRIMARY KEY,
    inventory_id   INT NOT NULL REFERENCES inventory(id),
    changed_by     INT REFERENCES users(id),
    change_type    VARCHAR(50) NOT NULL, -- 'sale', 'restock', 'adjustment', 'transfer'
    quantity_delta INT NOT NULL,
    quantity_after INT NOT NULL,         -- stored directly, makes point-in-time audits easy
    note           TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- DESC index because most queries will be "what changed recently"
CREATE INDEX idx_inventory_logs_recent ON inventory_logs(inventory_id, created_at DESC);

-- Product bundles (self-referential)
CREATE TABLE product_bundles (
    bundle_product_id    INT NOT NULL REFERENCES products(id),
    component_product_id INT NOT NULL REFERENCES products(id),
    quantity             INT NOT NULL DEFAULT 1,
    PRIMARY KEY (bundle_product_id, component_product_id)
);
