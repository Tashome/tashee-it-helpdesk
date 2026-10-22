
from flask_wtf.csrf import CSRFProtect
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    url_for,
    flash,
    abort
)
import os

from werkzeug.security import generate_password_hash, check_password_hash

import sqlite3
from pathlib import Path


app = Flask(__name__)

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError("SECRET_KEY is missing. Check your .env file.")

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False  # Local development only

csrf = CSRFProtect(app)

DATABASE = str(Path(__file__).resolve().parent / "tickets.db")

def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))

        return view_function(*args, **kwargs)

    return wrapped_view


def roles_required(*allowed_roles):
    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            # The login_required decorator should also protect the route.
            if "user_id" not in session:
                flash("Please log in to access this page.", "error")
                return redirect(url_for("login"))

            # Verify the user's role.
            if session.get("role") not in allowed_roles:
                abort(403)

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator



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
            status TEXT NOT NULL DEFAULT 'Open')  
            """)    
    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
                CHECK (role IN ('admin', 'technician', 'worker'))
        )
    """)

    connection.commit()
    connection.close()

@app.route("/")
def home():
    return render_template("index.html")



@app.route("/ticket", methods=["GET", "POST"])
@login_required
def ticket():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()

        if not all([title, category, priority, description, location]):
            return "Error: All fields are required.", 400

        # Get the ID of the currently logged-in user.
        created_by = session["user_id"]

        connection = sqlite3.connect(DATABASE)

        try:
            connection.execute("""
                INSERT INTO tickets
                (
                    title,
                    category,
                    priority,
                    description,
                    location,
                    created_by
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                title,
                category,
                priority,
                description,
                location,
                created_by
            ))

            connection.commit()

        except sqlite3.Error:
            connection.rollback()
            raise

        finally:
            connection.close()

        return "Ticket submitted and saved successfully!"

    return render_template("ticket.html")

initialize_database()

@app.route("/tickets")
@login_required
def view_tickets():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()
    category = request.args.get("category", "").strip()

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    query = "SELECT * FROM tickets WHERE 1=1"
    parameters = []

    # Restrict ticket visibility according to the logged-in user's role.
    role = session.get("role")
    user_id = session.get("user_id")

    if role == "admin":
        # Administrators can see all tickets.
        pass

    elif role == "technician":
        # Technicians can see only tickets assigned to them.
        query += " AND assigned_to = ?"
        parameters.append(user_id)

    elif role == "worker":
        # Workers can see only tickets they created.
        query += " AND created_by = ?"
        parameters.append(user_id)

    else:
        # Unknown roles must not see any tickets.
        connection.close()
        abort(403)

    # Search by title, description, or location.
    if search:
        query += """
            AND (
                title LIKE ?
                OR description LIKE ?
                OR location LIKE ?
            )
        """
        search_term = f"%{search}%"
        parameters.extend([search_term, search_term, search_term])

    # Apply the selected filters.
    if status in ["Open", "In Progress", "Resolved"]:
        query += " AND status = ?"
        parameters.append(status)

    if priority:
        query += " AND priority = ?"
        parameters.append(priority)

    if category:
        query += " AND category = ?"
        parameters.append(category)

    query += " ORDER BY id DESC"

    tickets = connection.execute(
        query, parameters
    ).fetchall()

    priorities = [
        row["priority"]
        for row in connection.execute(
            "SELECT DISTINCT priority FROM tickets ORDER BY priority"
        ).fetchall()
    ]

    categories = [
        row["category"]
        for row in connection.execute(
            "SELECT DISTINCT category FROM tickets ORDER BY category"
        ).fetchall()
    ]

    connection.close()

    return render_template(
        "tickets.html",
        tickets=tickets,
        search=search,
        selected_status=status,
        selected_priority=priority,
        selected_category=category,
        priorities=priorities,
        categories=categories
    )


@app.route("/ticket/<int:ticket_id>/status", methods=["POST"])
@login_required
def update_ticket_status(ticket_id):
    status = request.form.get("status", "").strip()

    allowed_statuses = ["Open", "In Progress", "Resolved"]

    if status not in allowed_statuses:
        return "Invalid ticket status.", 400

    role = session.get("role")
    user_id = session.get("user_id")

    connection = sqlite3.connect(DATABASE)

    cursor = None

    try:
        # Admins can update any ticket.
        if role == "admin":
            cursor = connection.execute(
                "UPDATE tickets SET status = ? WHERE id = ?",
                (status, ticket_id)
            )

        # Technicians can update only their assigned tickets.
        elif role == "technician":
            cursor = connection.execute(
                """
                UPDATE tickets
                SET status = ?
                WHERE id = ? AND assigned_to = ?
                """,
                (status, ticket_id, user_id)
            )

        else:
            abort(403)

        connection.commit()

        if cursor is not None and cursor.rowcount == 0:
            exists = connection.execute(
                "SELECT 1 FROM tickets WHERE id = ?",
                (ticket_id,)
            ).fetchone()

            if exists is None:
                return "Ticket not found.", 404

            abort(403)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
    return (
        "Ticket status updated successfully. "
        "<a href='/tickets'>Back to tickets</a>"
    )

@app.route("/ticket/<int:ticket_id>/assign", methods=["POST"])
@login_required
def assign_ticket(ticket_id):
    # Only administrators can assign tickets.
    if session.get("role") != "admin":
        abort(403)

    assigned_to_raw = request.form.get("assigned_to", "").strip()

    # Validate the submitted technician ID.
    if not assigned_to_raw.isdigit():
        return "Invalid technician ID.", 400

    assigned_to = int(assigned_to_raw)

    connection = sqlite3.connect(DATABASE)

    try:
        # Confirm that the ticket exists.
        ticket = connection.execute(
            "SELECT id FROM tickets WHERE id = ?",
            (ticket_id,)
        ).fetchone()

        if ticket is None:
            return "Ticket not found.", 404

        # Only accounts with the technician role may be assigned.
        technician = connection.execute(
            "SELECT id FROM users WHERE id = ? AND role = ?",
            (assigned_to, "technician")
        ).fetchone()

        if technician is None:
            return "Selected account is not a valid technician.", 400

        connection.execute(
            "UPDATE tickets SET assigned_to = ? WHERE id = ?",
            (assigned_to, ticket_id)
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return (
        "Ticket assigned successfully. "
        "<a href='/tickets'>Back to tickets</a>"
    )


@app.route("/dashboard")
@login_required
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

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter your username and password.", "error")
            return render_template("login.html")

        conn = None

        try:
            conn = sqlite3.connect(DATABASE)
            conn.row_factory = sqlite3.Row

            user = conn.execute(
                """
                SELECT id, username, password_hash, role
                FROM users
                WHERE username = ?
                """,
                (username,)
            ).fetchone()

        except sqlite3.Error:
            app.logger.exception("Database error during login.")
            flash("Unable to log in right now. Please try again.", "error")
            return render_template("login.html")

        finally:
            if conn is not None:
                conn.close()

        if user is None or not check_password_hash(
            user["password_hash"], password
        ):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        # Clear any previous session data before creating a new session.
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]

        flash("Login successful.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")

if __name__ == "__main__":
    app.run(debug=True)