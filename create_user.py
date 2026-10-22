
import sqlite3
from getpass import getpass
from pathlib import Path
from werkzeug.security import generate_password_hash

DATABASE = Path(__file__).resolve().parent / "tickets.db"

ALLOWED_ROLES = {"technician", "worker"}


def create_user():
    username = input("Enter username: ").strip()
    role = input("Enter role (technician/worker): ").strip().lower()

    if not username:
        print("Error: Username cannot be empty.")
        return

    if role not in ALLOWED_ROLES:
        print("Error: Role must be technician or worker.")
        return

    password = getpass("Enter password: ")
    confirm_password = getpass("Confirm password: ")

    if len(password) < 12:
        print("Error: Password must be at least 12 characters.")
        return

    if password != confirm_password:
        print("Error: Passwords do not match.")
        return

    password_hash = generate_password_hash(password)

    with sqlite3.connect(DATABASE) as connection:
        existing_user = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing_user:
            print("Error: This username already exists.")
            return

        connection.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (username, password_hash, role)
        )

    print(f"Successfully created {role} account: {username}")


if __name__ == "__main__":
    create_user()
