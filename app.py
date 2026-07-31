"""
A.I.D.A. website integration demonstration

This Flask application serves a demonstration homepage showing
how A.I.D.A. could appear on the Anguilla Inland Revenue website.
"""

from flask import Flask, render_template


# Flask automatically looks for HTML files inside templates
# and CSS, JavaScript and images inside static
app = Flask(__name__)


@app.route("/")
def home():
    """Display the demonstration IRD homepage."""

    return render_template("index.html")


if __name__ == "__main__":
    # Debug mode automatically reloads the website when files change
    app.run(debug=True)