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

import hashlib
import json
from typing import List, Tuple, Dict, Any

def build_custom_schema_card(
    dataset_id: str,
    table_name: str,
    filename: str,
    columns_metadata: List[Tuple[str, str, str]]
) -> Dict[str, Any]:
    """
    Generates a structured schema card and deterministic schema hash for an uploaded dataset.
    columns_metadata: List of (original_col, sanitized_col, postgres_type)
    """
    # 1. Deterministic schema hash for change detection & caching
    meta_repr = json.dumps([(c[0], c[1], c[2]) for c in columns_metadata], sort_keys=True)
    schema_hash = hashlib.sha256(f"{table_name}:{meta_repr}".encode("utf-8")).hexdigest()[:16]
    
    # 2. Build annotated DDL
    ddl_lines = [f"-- Table: {table_name} (Source: {filename})", f"CREATE TABLE {table_name} ("]
    col_summaries = []
    for orig, sanitized, db_type in columns_metadata:
        ddl_lines.append(f'    "{sanitized}" {db_type}, -- Original Column Name: "{orig}"')
        col_summaries.append(f'"{sanitized}" ({db_type}, source: "{orig}")')
        
    if len(ddl_lines) > 2:
        ddl_lines[-1] = ddl_lines[-1].rstrip(',')
    ddl_lines.append(");")
    ddl_str = "\n".join(ddl_lines)
    
    # 3. Context & Embedding text (schema/metadata only, never raw row values)
    description = f"Uploaded dataset table from file '{filename}' with {len(columns_metadata)} columns."
    context = f"Columns: {', '.join(col_summaries)}."
    text_to_embed = (
        f"Dataset: {filename}. Table: {table_name}. "
        f"Description: {description} "
        f"Columns: {', '.join(col_summaries)}. "
        f"Context: Use this table when querying records from uploaded file '{filename}'."
    )
    
    return {
        "dataset_id": dataset_id,
        "table_name": table_name,
        "filename": filename,
        "schema_hash": schema_hash,
        "description": description,
        "context": context,
        "ddl": ddl_str,
        "columns": columns_metadata,
        "text_to_embed": text_to_embed
    }
