# Table Schema Cards for RAG retrieval

SCHEMA_CARDS = {
    "customers": {
        "name": "customers",
        "description": "Stores user account details, signup information, name, email, and country of origin.",
        "ddl": """
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    signup_date DATE NOT NULL,
    country VARCHAR(50) NOT NULL
);""",
        "context": "Use this table when querying customer profiles, calculating signup numbers, filtering by country, or identifying who placed an order."
    },
    "products": {
        "name": "products",
        "description": "Stores inventory catalog, including product names, product pricing, and category classifications.",
        "ddl": """
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price DECIMAL(10, 2) NOT NULL
);""",
        "context": "Use this table to find product details, product categories (e.g. Electronics, Apparel), product prices, or when calculating product inventory metrics."
    },
    "orders": {
        "name": "orders",
        "description": "Stores transactional headers, order dates, total invoice amounts, and order status (Pending, Completed, Cancelled).",
        "ddl": """
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    order_date DATE NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('Pending', 'Completed', 'Cancelled'))
);""",
        "context": "Use this table when counting orders, filtering by order date ranges, checking transaction totals, joining customers with purchases, or checking order statuses."
    },
    "order_items": {
        "name": "order_items",
        "description": "Junction table mapping products to orders. Stores quantities purchased and unit prices for individual order items.",
        "ddl": """
CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL
);""",
        "context": "Use this table when counting specific units sold, analyzing basket content, joining orders to products, or calculating sub-total price statistics."
    },
    "payments": {
        "name": "payments",
        "description": "Stores transaction payment status (Pending, Completed, Failed, Refunded), transaction amount, and payment dates.",
        "ddl": """
CREATE TABLE payments (
    payment_id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    payment_date DATE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_status VARCHAR(20) NOT NULL CHECK (payment_status IN ('Pending', 'Completed', 'Failed', 'Refunded'))
);""",
        "context": "Use this table when verifying if orders have been paid, analyzing transaction dates, tracking revenue collection, or identifying payment failures."
    }
}
