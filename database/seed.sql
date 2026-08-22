-- Seed Data for the QueryPilot Text-to-SQL Relational Database

-- Clean tables before seeding (just in case they are populated)
TRUNCATE payments, order_items, orders, products, customers RESTART IDENTITY CASCADE;

-- 1. Populate Customers
INSERT INTO customers (name, email, signup_date, country) VALUES
('Satyam Singh', 'satyam@example.com', '2026-01-15', 'India'),
('Jane Doe', 'jane.doe@example.com', '2026-02-20', 'USA'),
('John Smith', 'john.smith@example.com', '2026-03-05', 'USA'),
('Alice Cooper', 'alice.c@example.com', '2026-05-12', 'UK'),
('Bob Martin', 'bob.martin@example.com', '2026-06-01', 'Canada'),
('Charlie Brown', 'charlie.b@example.com', '2026-06-15', 'USA'),
('Diana Prince', 'diana@example.com', '2026-07-02', 'UK'),
('Evan Wright', 'evan.w@example.com', '2026-07-10', 'Canada'),
('Fiona Gallagher', 'fiona@example.com', '2026-07-20', 'Ireland'),
('George Costanza', 'george@example.com', '2026-08-01', 'USA'),
('Harsh Patel', 'harsh@example.com', '2026-08-03', 'India');

-- 2. Populate Products
INSERT INTO products (name, category, price) VALUES
('Wireless Mouse', 'Electronics', 1500.00),
('Mechanical Keyboard', 'Electronics', 4500.00),
('USB-C Hub', 'Electronics', 2500.00),
('Leather Journal', 'Stationery', 800.00),
('Fountain Pen', 'Stationery', 1200.00),
('Running Shoes', 'Apparel', 6000.00),
('Cotton T-Shirt', 'Apparel', 1200.00),
('Ceramic Coffee Mug', 'Home & Kitchen', 600.00),
('Double-Walled Thermos', 'Home & Kitchen', 1800.00),
('Introduction to Algorithms Book', 'Books', 3200.00);

-- 3. Populate Orders
-- Let's construct a variety of orders with different dates and statuses
-- Order amounts will be updated after inserting items, or we set them initially to match item totals.
INSERT INTO orders (customer_id, order_date, total_amount, status) VALUES
-- Satyam Singh (ID 1)
(1, '2026-01-20', 4000.00, 'Completed'),
(1, '2026-05-15', 4500.00, 'Completed'),
(1, '2026-08-05', 8500.00, 'Completed'), -- Best customer last month (August) / current month

-- Jane Doe (ID 2)
(2, '2026-02-25', 1500.00, 'Completed'),
(2, '2026-07-10', 3200.00, 'Completed'),

-- John Smith (ID 3)
(3, '2026-03-10', 2500.00, 'Completed'),
(3, '2026-07-15', 7300.00, 'Completed'), -- Ordered keyboard + USB hub + mug

-- Alice Cooper (ID 4)
(4, '2026-05-20', 800.00, 'Completed'),
(4, '2026-06-10', 6000.00, 'Completed'), -- Running shoes

-- Bob Martin (ID 5)
(5, '2026-06-05', 1800.00, 'Completed'),

-- Charlie Brown (ID 6)
(6, '2026-06-18', 2000.00, 'Cancelled'),

-- Diana Prince (ID 7)
(7, '2026-07-05', 5700.00, 'Completed'), -- Keyboard + mug + pen

-- Evan Wright (ID 8)
(8, '2026-07-12', 1200.00, 'Pending'),

-- Fiona Gallagher (ID 9)
(9, '2026-07-22', 1500.00, 'Completed'),

-- George Costanza (ID 10)
(10, '2026-08-02', 800.00, 'Completed'),

-- Harsh Patel (ID 11)
(11, '2026-08-04', 5000.00, 'Pending');

-- 4. Populate Order Items
-- Link items to the orders created above
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
-- Order 1: Satyam - Hub (2500) + Mouse (1500) = 4000
(1, 3, 1, 2500.00),
(1, 1, 1, 1500.00),

-- Order 2: Satyam - Keyboard (4500) = 4500
(2, 2, 1, 4500.00),

-- Order 3: Satyam - Keyboard (4500) + USB-C Hub (2500) + Thermos (1800) = 8800 (adjusted total_amount to 8800 later, let's keep it close)
(3, 2, 1, 4500.00),
(3, 3, 1, 2500.00),
(3, 9, 1, 1800.00), -- Total matches total_amount adjustment (let's update order 3 total_amount to 8800 in update command below)

-- Order 4: Jane - Mouse (1500) = 1500
(4, 1, 1, 1500.00),

-- Order 5: Jane - Book (3200) = 3200
(5, 10, 1, 3200.00),

-- Order 6: John - Hub (2500) = 2500
(6, 3, 1, 2500.00),

-- Order 7: John - Keyboard (4500) + Mug (600) + Pen (1200) + Hub (1000 discount) = 7300 (let's say 1 keyboard @4500, 2 journals @800, 1 mug @600 = 6700)
-- Let's match product prices: Keyboard (4500), Pen (1200), Thermos (1800) minus 200 discount.
(7, 2, 1, 4500.00),
(7, 5, 1, 1200.00),
(7, 9, 1, 1600.00), -- unit price can differ due to discounts

-- Order 8: Alice - Journal (800) = 800
(8, 4, 1, 800.00),

-- Order 9: Alice - Running Shoes (6000) = 6000
(9, 6, 1, 6000.00),

-- Order 10: Bob - Thermos (1800) = 1800
(10, 9, 1, 1800.00),

-- Order 11: Charlie - Mouse (1500) + Mug (500) = 2000
(11, 1, 1, 1500.00),
(11, 8, 1, 500.00),

-- Order 12: Diana - Keyboard (4500) + Pen (1200) = 5700
(12, 2, 1, 4500.00),
(12, 5, 1, 1200.00),

-- Order 13: Evan - T-Shirt (1200) = 1200
(13, 7, 1, 1200.00),

-- Order 14: Fiona - Mouse (1500) = 1500
(14, 1, 1, 1500.00),

-- Order 15: George - Journal (800) = 800
(15, 4, 1, 800.00),

-- Order 16: Harsh - Keyboard (4500) + Mug (500) = 5000
(16, 2, 1, 4500.00),
(16, 8, 1, 500.00);

-- Update order total_amounts to match exactly the sum of items
UPDATE orders SET total_amount = (SELECT COALESCE(SUM(quantity * unit_price), 0) FROM order_items WHERE order_items.order_id = orders.order_id);

-- 5. Populate Payments
-- Insert payment records matching the orders
INSERT INTO payments (order_id, payment_date, amount, payment_status) VALUES
(1, '2026-01-20', 4000.00, 'Completed'),
(2, '2026-05-15', 4500.00, 'Completed'),
(3, '2026-08-05', 8800.00, 'Completed'),
(4, '2026-02-25', 1500.00, 'Completed'),
(5, '2026-07-10', 3200.00, 'Completed'),
(6, '2026-03-10', 2500.00, 'Completed'),
(7, '2026-07-16', 7300.00, 'Completed'),
(8, '2026-05-20', 800.00, 'Completed'),
(9, '2026-06-10', 6000.00, 'Completed'),
(10, '2026-06-05', 1800.00, 'Completed'),
(11, '2026-06-18', 2000.00, 'Failed'), -- Cancelled order has failed/refunded/no payment
(12, '2026-07-05', 5700.00, 'Completed'),
(13, '2026-07-12', 1200.00, 'Pending'),
(14, '2026-07-22', 1500.00, 'Completed'),
(15, '2026-08-02', 800.00, 'Completed'),
(16, '2026-08-04', 5000.00, 'Pending');
