import logging
import os

import pymysql
from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException

import db
from config import Config
from models import user as users
from routes import admin, auth, orders, pages, products


def wants_json():
    return request.path.startswith("/api/")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.teardown_appcontext(db.close_db)

    for module in (pages, auth, products, orders, admin):
        app.register_blueprint(module.bp)

    @app.before_request
    def load_user():
        """Look the logged-in user up on every request so role changes apply immediately."""
        g.user = None
        if request.endpoint == "static":
            return
        user_id = session.get("user_id")
        if user_id:
            g.user = users.get_by_id(user_id)
            if g.user is None:  # account was deleted
                session.clear()

    @app.context_processor
    def inject_globals():
        return {"current_user": users.public(g.get("user")), "currency": app.config["CURRENCY_SYMBOL"]}

    def fail(message, code):
        if wants_json():
            return jsonify(error=message), code
        return render_template("error.html", code=code, message=message), code

    @app.errorhandler(HTTPException)
    def handle_http(e):
        return fail(e.description, e.code)

    @app.errorhandler(pymysql.MySQLError)
    def handle_db(e):
        app.logger.exception("Database error")
        return fail("The database is unavailable right now. Please try again shortly.", 503)

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        app.logger.exception("Unexpected error")
        return fail("Something went wrong on our side. Please try again.", 500)

    return app


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
