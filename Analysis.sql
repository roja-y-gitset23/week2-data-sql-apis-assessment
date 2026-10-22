-- =====================================================
-- Task 1: SQL Analysis
-- File: analysis.sql
-- Database: PostgreSQL (JSONB required)
-- =====================================================

-- =====================================================
-- SETUP: Create tables and insert data
-- =====================================================
DROP TABLE IF EXISTS orders, products, customers CASCADE;

CREATE TABLE customers (
  id   INT PRIMARY KEY,
  name TEXT,
  city TEXT
);

CREATE TABLE orders (
  id          INT PRIMARY KEY,
  customer_id INT REFERENCES customers(id),
  amount      NUMERIC,
  ordered_at  DATE
);

CREATE TABLE products (
  id    INT PRIMARY KEY,
  name  TEXT,
  attrs JSONB
);

INSERT INTO customers VALUES
  (1, 'Arun',  'Chennai'),
  (2, 'Priya', 'Mumbai'),
  (3, 'Rahul', 'Chennai'),
  (4, 'Divya', 'Bangalore');

INSERT INTO orders VALUES
  (101, 1, 700, '2026-01-05'),
  (102, 1, 600, '2026-02-10'),
  (103, 2, 300, '2026-01-20'),
  -- 6 additional orders
  (104, 2, 500, '2026-02-15'),
  (105, 2, 450, '2026-03-01'),
  (106, 3, 900, '2026-02-25'),
  (107, 3,  50, '2026-03-10'),
  (108, 1, 800, '2026-03-15'),
  (109, 2, 200, '2026-03-20');

INSERT INTO products VALUES
  (1, 'Laptop A', '{"brand":"Dell","ram":16}'),
  (2, 'Laptop B', '{"brand":"HP","ram":8}');


-- =====================================================
-- Q1: Total sales per customer (JOIN + GROUP BY),
--     only customers with total above 1000 (HAVING)
-- Expected: Arun 2100, Priya 1450
-- =====================================================
SELECT c.name,
       SUM(o.amount) AS total_sales
FROM customers c
JOIN orders o ON o.customer_id = c.id
GROUP BY c.name
HAVING SUM(o.amount) > 1000
ORDER BY total_sales DESC;


-- =====================================================
-- Q2: Customers who have never ordered (LEFT JOIN)
-- Expected: Divya (id 4, Bangalore)
-- =====================================================
SELECT c.id, c.name, c.city
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
WHERE o.id IS NULL;


-- =====================================================
-- Q3: Top customer per city (CTE)
-- Expected: Chennai -> Arun 2100, Mumbai -> Priya 1450
-- =====================================================
WITH city_sales AS (
  SELECT c.name, c.city, SUM(o.amount) AS total_sales
  FROM customers c
  JOIN orders o ON o.customer_id = c.id
  GROUP BY c.name, c.city
),
ranked AS (
  SELECT city, name, total_sales,
         ROW_NUMBER() OVER (PARTITION BY city ORDER BY total_sales DESC) AS rn
  FROM city_sales
)
SELECT city, name, total_sales
FROM ranked
WHERE rn = 1
ORDER BY city;


-- =====================================================
-- Q4: ROW_NUMBER() ranks orders per customer by amount,
--     LAG() shows the previous order amount (by date)
-- Note: prev_amount is NULL for each customer's first order
-- =====================================================
SELECT customer_id,
       id AS order_id,
       ordered_at,
       amount,
       ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount DESC) AS amount_rank,
       LAG(amount)  OVER (PARTITION BY customer_id ORDER BY ordered_at)  AS prev_amount
FROM orders
ORDER BY customer_id, ordered_at;


-- =====================================================
-- Q5: JSONB - products where attrs @> '{"brand": "Dell"}'
--     and extract attrs ->> 'ram'
-- Expected: Laptop A, ram 16
-- =====================================================
SELECT name,
       attrs ->> 'ram' AS ram
FROM products
WHERE attrs @> '{"brand": "Dell"}';