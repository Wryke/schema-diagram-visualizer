-- A larger schema for checking the diagram: 14 tables with one-to-one links,
-- self-references, optional relationships, join tables, and a composite foreign key.

CREATE TABLE customers (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  referred_by INT REFERENCES customers(id),   -- self-reference, optional
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- One-to-one: UNIQUE means each customer has at most one profile.
CREATE TABLE customer_profiles (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL UNIQUE REFERENCES customers(id) ON DELETE CASCADE,
  bio TEXT,
  newsletter BOOLEAN DEFAULT FALSE
);

CREATE TABLE addresses (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  street VARCHAR(200) NOT NULL,
  city VARCHAR(100) NOT NULL,
  country CHAR(2) DEFAULT 'US'
);

CREATE TABLE categories (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  parent_id INT REFERENCES categories(id)     -- self-reference, optional
);

CREATE TABLE suppliers (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL
);

CREATE TABLE products (
  id SERIAL PRIMARY KEY,
  sku VARCHAR(40) NOT NULL UNIQUE,
  name VARCHAR(200) NOT NULL,
  price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
  supplier_id INT REFERENCES suppliers(id) ON DELETE SET NULL
);

-- Many-to-many join table.
CREATE TABLE product_categories (
  product_id INT NOT NULL REFERENCES products(id),
  category_id INT NOT NULL REFERENCES categories(id),
  PRIMARY KEY (product_id, category_id)
);

CREATE TABLE warehouses (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  manager_id INT REFERENCES employees(id)     -- points forward to a later table
);

CREATE TABLE employees (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  manager_id INT REFERENCES employees(id),    -- self-reference, optional
  warehouse_id INT REFERENCES warehouses(id)
);

CREATE TABLE inventory (
  product_id INT NOT NULL REFERENCES products(id),
  warehouse_id INT NOT NULL REFERENCES warehouses(id),
  quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  PRIMARY KEY (product_id, warehouse_id)
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  shipping_address_id INT REFERENCES addresses(id),
  status VARCHAR(20) NOT NULL DEFAULT 'new',
  placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CHECK (status IN ('new', 'paid', 'shipped', 'cancelled'))
);

CREATE TABLE order_lines (
  order_id INT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  line_no INT NOT NULL,
  product_id INT NOT NULL REFERENCES products(id),
  quantity INT NOT NULL CHECK (quantity > 0),
  PRIMARY KEY (order_id, line_no)
);

-- A composite foreign key: both columns together pick one order line.
CREATE TABLE shipments (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL,
  line_no INT NOT NULL,
  warehouse_id INT NOT NULL REFERENCES warehouses(id),
  shipped_at TIMESTAMP,
  CONSTRAINT fk_shipment_line FOREIGN KEY (order_id, line_no) REFERENCES order_lines(order_id, line_no)
);

CREATE TABLE payments (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  amount NUMERIC(10, 2) NOT NULL,
  paid_at TIMESTAMP,
  CHECK (amount > 0 AND paid_at IS NOT NULL)
);
