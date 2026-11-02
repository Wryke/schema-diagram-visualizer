-- A small schema that covers the main cases:
-- inline FK, table-level FK, self-reference, CHECK, DEFAULT, UNIQUE, composite key.

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE employees (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id),
  manager_id INT REFERENCES employees(id),   -- self-relationship
  salary NUMERIC(10, 2) CHECK (salary > 0)
);

CREATE TABLE projects (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL
);

/* Many-to-many join table with a composite primary key */
CREATE TABLE project_members (
  project_id INT NOT NULL,
  employee_id INT NOT NULL,
  role VARCHAR(50) DEFAULT 'member',
  PRIMARY KEY (project_id, employee_id),
  CONSTRAINT fk_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY (employee_id) REFERENCES employees(id)
);

-- The parser should skip statements it doesn't understand:
CREATE INDEX idx_users_email ON users(email);
