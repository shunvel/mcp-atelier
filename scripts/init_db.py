"""Create sample SQLite database for MCP learning demos."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "demo.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript(
        """
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            email TEXT NOT NULL
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        INSERT INTO customers (name, city, email) VALUES
            ('Alice Johnson', 'Bangalore', 'alice@example.com'),
            ('Bob Smith', 'Mumbai', 'bob@example.com'),
            ('Carol Davis', 'Delhi', 'carol@example.com'),
            ('David Lee', 'Chennai', 'david@example.com');

        INSERT INTO products (name, category, price) VALUES
            ('Laptop Pro', 'Electronics', 1299.99),
            ('Wireless Mouse', 'Electronics', 29.99),
            ('Standing Desk', 'Furniture', 449.00),
            ('Ergonomic Chair', 'Furniture', 399.00),
            ('USB-C Hub', 'Electronics', 49.99),
            ('Monitor 27"', 'Electronics', 329.00);

        INSERT INTO orders (customer_id, product_id, quantity, order_date) VALUES
            (1, 1, 1, '2026-01-15'),
            (1, 2, 2, '2026-01-15'),
            (2, 3, 1, '2026-02-01'),
            (3, 4, 1, '2026-02-10'),
            (3, 5, 3, '2026-02-10'),
            (4, 6, 2, '2026-03-05'),
            (2, 1, 1, '2026-03-12'),
            (1, 6, 1, '2026-03-20');
        """
    )

    conn.commit()
    conn.close()
    print(f"Created demo database at {DB_PATH}")


if __name__ == "__main__":
    init_db()
