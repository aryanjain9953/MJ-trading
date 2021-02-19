import os
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
import yfinance as yf
from flask import Flask, request, render_template,jsonify 
from helpers import * #apology, login_required, lookup, usd
from wtforms import Form, BooleanField, StringField, PasswordField, validators
import re
# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.globals.update(usd=usd)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    data = getStocks()

    return render_template("index.html", data = data)


@app.route("/addcash", methods=["POST"])
@login_required
def addcash():
    amount = int(request.form.get('amount'))
    if not amount or amount < 1:
        return jsonify({'status': False, 'reason': 'Valid amount required'})

    updateCash(amount)
    storeTxn(amount = amount, type = 'funded')
    return jsonify({'status': True, 'reason': 'Amount added to cash'})


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == 'POST':
        result = { 'status' : False }
        symbol = request.form.get('symbol')
        shares = int(request.form.get('shares'))

        # validate input
        if not validate(symbol, shares):
            return apology("You must provide Shares & Symbol or Shares must be positive")

        quote = lookup(symbol)
        user_id = session["user_id"]
        if quote:
            # get user balance
            balance = db.execute("SELECT cash FROM users where id = :user_id", user_id = user_id)[0]['cash']
            amount = quote['price'] * int(shares)
            if amount > balance:
                return apology("Insufficient funds to buy stock(s)")
            else:
                # add to users portfolio
                modStock(symbol, shares)
                # add to transactions
                storeTxn(amount, 'bought', symbol, shares)
                updateCash(-amount)
                # result = { 'status' : True, 'reason' : "Stock bought successfully" }
                return redirect("/")
        else:
            apology("Stock not found")
        return apology(result)

    """Buy shares of stock"""
    return render_template("buy.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    data = getStocks()
    if request.method == 'POST':
        user_id = session['user_id']
        result = { 'status' : False }
        symbol = request.form.get('symbol')
        shares = int(request.form.get('shares'))
        # validate input
        if not validate(symbol, shares):
            result['reason'] = "You must provide Shares & Symbol or Shares must be potive"
            return render_template("sell.html", result = result, data = data)
        # check if user can sell
        ownedShares = db.execute("SELECT SUM(shares) as shares FROM users_stocks WHERE shares > 0 AND user_id = :user_id AND stock = :symbol GROUP BY stock", user_id = user_id, symbol = symbol)
        if not ownedShares:
            result['reason'] = "You do not own the selected stock"
            return apology("You do not own the selected stock", code=400)
        elif not ownedShares[0]['shares'] >= shares:
            result['reason'] = "You do not have enough shares of the selected stock"
            return render_template("sell.html", result = result, data = data)
        else:
            # remove stocks from users portfolio
            quote = lookup(symbol)
            amount = quote['price'] * shares
            modStock(symbol, -shares)
            # update user cash
            storeTxn(amount, 'sold', symbol, shares)
            updateCash(amount)
    data = getStocks()
    return render_template("sell.html", data = data)


@app.route("/hist")
@login_required
def history():
    """Show history of transactions"""
    data = getStocks()
    return render_template("history.html", data = data)

@app.route("/pay")
@login_required
def pay():
    return render_template("pay.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/q", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == 'POST':
        symbol = request.form.get('symbol')
        quote = lookup(symbol)

        if not quote:
            return apology("Stock not found")

        return render_template('quoted.html', quote = quote)

    """Get stock quote."""
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == 'POST':
        """Register user"""
        uname = request.form.get('username')
        password = generate_password_hash(request.form.get('password'))
        status = True
        # check password confirmation
        if len(request.form.get('password')) < 8:
            status = False
            text = "Password should be atleast 8 characters"
        if re.search("![_@$]", password):
            status = False
            text = "Password should have either of these symbols [_@$]"
        if not any(char.isdigit() for char in request.form.get('password')):
            status = False
            text = "Password should have either one numeral"
        if not any(char.isupper() for char in request.form.get('password')):
            status = False
            text = "Password should have either one uppercase character"
        if not any(char.islower() for char in request.form.get('password')):
            status = False
            text = "Password should have either one lowercase character"
        if not request.form.get('password') == request.form.get('c-password'):
            status = False
            text = "Password confirmation not match"
        # check unique username
        exists_username= db.execute("SELECT username FROM users where username = :username", username = uname)
        if exists_username:
            status = False
            text = "Username already taken by another user"
        if status:
            # register
            register = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
            username = uname, hash = password)
            text = "Registration Was Successful"
            # Remember which user has logged in
            session["user_id"] = register

            # Redirect user to home page
            return redirect("/")
        return apology(text)
        # return render_template('register.html', status = status, text = text)
    else:
        return render_template('register.html')

@app.route("/quote")
def display_quote():
	# get a stock ticker symbol from the query string
	# default to AAPL
	symbol = request.args.get('symbol', default="AAPL")

	# pull the stock quote
	quote = yf.Ticker(symbol)

	#return the object via the HTTP Response
	return quote.info

# API route for pulling the stock history
@app.route("/history")
def display_history():
	#get the query string parameters
	symbol = request.args.get('symbol', default="AAPL")
	period = request.args.get('period', default="1y")
	interval = request.args.get('interval', default="1d")

	#pull the quote
	quote = yf.Ticker(symbol)	
	#use the quote to pull the historical data from Yahoo finance
	hist = quote.history(period=period, interval=interval)
	#convert the historical data to JSON
	data = hist.to_json()
	#return the JSON in the HTTP response
	return data

# This is the / route, or the main landing page route.
@app.route("/charts")
@login_required
def home():
	# we will use Flask's render_template method to render a website template.
    return render_template("homepage.html")

@app.route("/c")
@login_required
def c():
	# we will use Flask's render_template method to render a website template.
    return render_template("com.html")
def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
# for code in default_exceptions:
#     app.errorhandler(code)(errorhandler)
