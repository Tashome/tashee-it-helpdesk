
import sqlite3
from pathlib import Path

DATABASE = Path(__file__).resolve().parent / "tickets.db"


def migrate_database():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        # Confirm that the expected tables exist.
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

        if "tickets" not in tables or "users" not in tables:
            raise RuntimeError(
                "Expected tickets and users tables were not found."
            )

        # Read existing ticket columns.
        conn.row_factory = sqlite3.Row
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(tickets)").fetchall()
        }

        # Add ownership fields only when they are missing.
        if "created_by" not in columns:
            conn.execute(
                "ALTER TABLE tickets ADD COLUMN created_by "
                "INTEGER REFERENCES users(id)"
            )
            print("Added created_by column.")

        if "assigned_to" not in columns:
            conn.execute(
                "ALTER TABLE tickets ADD COLUMN assigned_to "
                "INTEGER REFERENCES users(id)"
            )
            print("Added assigned_to column.")

        # Indexes improve searches by creator and assignee.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_created_by "
            "ON tickets(created_by)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to "
            "ON tickets(assigned_to)"
        )

        conn.commit()
        print("Database migration completed successfully.")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
