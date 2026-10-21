
from flask import Flask, render_template, request
import sqlite3

app = Flask(__name__)

DATABASE = "tickets.db"


def initialize_database():
    connection = sqlite3.connect(DATABASE)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open'
        )
    """)

    connection.commit()
    connection.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ticket", methods=["GET", "POST"])
def ticket():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()

        if not all([title, category, priority, description, location]):
            return "Error: All fields are required.", 400

        connection = sqlite3.connect(DATABASE)

        connection.execute("""
            INSERT INTO tickets
            (title, category, priority, description, location)
            VALUES (?, ?, ?, ?, ?)
        """, (title, category, priority, description, location))

        connection.commit()
        connection.close()

        return "Ticket submitted and saved successfully!"

    return render_template("ticket.html")


initialize_database()
@app.route("/tickets")
def view_tickets():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    tickets = connection.execute(
        "SELECT * FROM tickets ORDER BY id DESC"
    ).fetchall()

    connection.close()

    return render_template("tickets.html", tickets=tickets)

@app.route("/ticket/<int:ticket_id>/status", methods=["POST"])
def update_ticket_status(ticket_id):
    status = request.form.get("status", "")

    allowed_statuses = ["Open", "In Progress", "Resolved"]

    if status not in allowed_statuses:
        return "Invalid ticket status.", 400

    connection = sqlite3.connect(DATABASE)

    cursor = connection.execute(
        "UPDATE tickets SET status = ? WHERE id = ?",
        (status, ticket_id)
    )

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return "Ticket not found.", 404

    return "Ticket status updated successfully. <a href='/tickets'>Back to tickets</a>"


@app.route("/dashboard")
def dashboard():
    connection = sqlite3.connect(DATABASE)

    total = connection.execute(
        "SELECT COUNT(*) FROM tickets"
    ).fetchone()[0]

    open_tickets = connection.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'Open'"
    ).fetchone()[0]

    in_progress = connection.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'In Progress'"
    ).fetchone()[0]

    resolved = connection.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'Resolved'"
    ).fetchone()[0]

    connection.close()

    return render_template(
        "dashboard.html",
        total=total,
        open_tickets=open_tickets,
        in_progress=in_progress,
        resolved=resolved
    )

if __name__ == "__main__":
    app.run(debug=True)
