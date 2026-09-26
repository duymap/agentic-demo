import uuid

from app.auth import hash_password, new_salt
from app.db import get_conn, init_db

USERS = [("alice", "demo123"), ("bob", "demo123")]

CUSTOMERS = [
    ("C-1024", "Công ty An Phát", "Business"),
    ("C-2048", "Nguyễn Minh", "Pro"),
    ("C-4096", "Studio Hạ Long", "Starter"),
]
INVOICES = [
    ("INV-9001", "C-1024", 120.0, "overdue", "2026-09-10"),
    ("INV-9002", "C-2048", 45.0, "paid", "2026-09-15"),
    ("INV-9003", "C-4096", 19.0, "open", "2026-10-05"),
]
ACCOUNTS = [
    ("C-1024", 1, "too_many_failed_logins", 6),
    ("C-2048", 0, None, 0),
    ("C-4096", 1, "payment_overdue", 0),
]


def main() -> None:
    init_db()
    with get_conn() as conn:
        for username, password in USERS:
            salt = new_salt()
            conn.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash, salt) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), username, hash_password(password, salt), salt),
            )
        conn.executemany("INSERT OR IGNORE INTO customers VALUES (?, ?, ?)", CUSTOMERS)
        conn.executemany("INSERT OR IGNORE INTO invoices VALUES (?, ?, ?, ?, ?)", INVOICES)
        conn.executemany("INSERT OR IGNORE INTO accounts VALUES (?, ?, ?, ?)", ACCOUNTS)
    print("Seed done")


if __name__ == "__main__":
    main()
