
import sqlite3
from getpass import getpass
from pathlib import Path
from werkzeug.security import generate_password_hash

# Use the database located beside app.py
DATABASE = Path(__file__).resolve().parent / "tickets.db"


def create_admin():
    username = input("Enter administrator username: ").strip()

    if not username:
        print("Username cannot be empty.")
        return

    password = getpass("Enter administrator password: ")
    confirm_password = getpass("Confirm administrator password: ")

    if len(password) < 12:
        print("Password must be at least 12 characters long.")
        return

    if password != confirm_password:
        print("Passwords do not match.")
        return

    connection = sqlite3.connect(DATABASE)

    try:
        existing_admin = connection.execute(
            "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()

        if existing_admin:
            print("An administrator already exists. No account was created.")
            return

        connection.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (username, generate_password_hash(password), "admin")
        )

        connection.commit()
        print("Administrator account created successfully.")

    except sqlite3.IntegrityError:
        print("That username already exists. Choose another username.")

    finally:
        connection.close()


if __name__ == "__main__":
    create_admin()
