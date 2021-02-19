import requests
import urllib.parse
import datetime
import os
from flask import redirect, render_template, request, session
from functools import wraps
from cs50 import SQL
import pandas as pd
import plotly.offline as po
import plotly.graph_objs as go
import pandas_datareader.data as web
import datetime
# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        response = requests.get(f"https://cloud-sse.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}")
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

def getStocks():
    user_id = session['user_id']
    stocks = db.execute("SELECT * FROM users_stocks WHERE user_id = :user_id GROUP BY stock", user_id = user_id)
    data = {
        'balance': db.execute("SELECT cash FROM users where id = :user_id", user_id = user_id)[0]['cash'],
        'owned': stocksCurPrice(stocks),
    }
    data['stockBalance'] = TotalBalance(data['owned'])
    stocks = db.execute("SELECT * FROM transactions where user_id = :user_id ORDER BY date DESC", user_id = user_id)
    data['stocks'] = stocksCurPrice(stocks)
    return data

def TotalBalance(stocks):
    total = 0.0
    for stock in stocks:
        total = total + (stock['curPrice'] * stock['shares'])
    return total

def modStock(symbol, shares):
    user_id = session['user_id']
    # check if stock exists and update users stock shares
    if ownStock(symbol):
        db.execute("UPDATE users_stocks set shares = shares + :shares WHERE stock = :symbol AND user_id = :user_id",
        user_id = user_id, symbol = symbol, shares = shares)
    # else save new stock with shares
    else:
        db.execute("INSERT INTO users_stocks (user_id, stock, shares) VALUES(:user_id, :stock, :shares)",
        user_id = user_id, stock = symbol, shares = shares)

def ownStock(symbol):
    user_id = session['user_id']
    return db.execute("SELECT * FROM users_stocks WHERE user_id = :user_id AND stock = :symbol AND shares > 0",
    user_id = user_id, symbol = symbol)

def storeTxn(amount, type, symbol = None, shares = None):
    user_id = session['user_id']
    date = datetime.datetime.now()
    db.execute("INSERT INTO transactions (user_id, stock, price, shares, type, date) VALUES (:user_id, :symbol, :amount, :shares, :type, :date)"
    , amount = amount, symbol = symbol, date = date, user_id = user_id, shares = shares, type = type)

def updateCash(amount):
    user_id = session['user_id']
    db.execute("UPDATE users SET cash = cash + :newBalance where id = :user_id", user_id = user_id, newBalance = amount)

def stocksCurPrice(stocks):
    for stock in stocks:
        if stock['stock']:
            stock['curPrice'] = lookup(stock['stock'])['price']
        else:
            stock['curPrice'] = 0
    return stocks

def validate(symbol, shares):
    return (shares and symbol) or shares < 1
