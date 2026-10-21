
from flask import Flask, render_template, request

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ticket", methods=["GET", "POST"])
def ticket():
    if request.method == "POST":
        return "Ticket form submitted."

    return render_template("ticket.html")


if __name__ == "__main__":
    app.run(debug=True)
