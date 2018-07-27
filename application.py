import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

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
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    portfolios = db.execute("SELECT * FROM portfolio WHERE user_id = :user", user=session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :user", user=session["user_id"])
    total = float(cash[0]["cash"])
    data = []
    for portfolio in portfolios:
        curent_price = lookup(portfolio["stock"])
        portfolio["curent_price"] = curent_price["price"]
        total += (float(portfolio["curent_price"]) * int(portfolio["number"]))
        data.append(portfolio)
    return render_template("index.html", cash=cash[0]["cash"], data=data, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "GET":
        return render_template("buy.html")
    else:
        if not request.form.get("symbol"):
            return apology("Не введен символ!", 400)
        elif not request.form.get("shares"):
            return apology("Не введено количество акций!", 400)
        else:
            try:
                number = int(request.form.get("shares"))
                result = lookup(request.form.get("symbol"))
                if number <= 0:
                    return apology("Введите положительное значение запрашиваемого Вами количества акций!", 400)
                elif not result:
                    return apology("Не корректно введен символ! Попробуйте еще раз.", 400)
            except:
                return apology("Число, КАРЛ, Ч-И-С-Л-О!!!", 400)

            cash = db.execute("SELECT cash FROM users WHERE id = :user", user=session["user_id"])
            curentCash = float(cash[0]["cash"])
            result = lookup(request.form.get("symbol"))
            query = float(result["price"]) * number
            if query > curentCash:
                return apology("У Вас не достаточно средств, освободитесь от 'баласта'!", 400)
            else:
                newCash = db.execute("UPDATE users SET cash = :balance WHERE id = :user",
                                     balance=curentCash - query,
                                     user=session["user_id"])

                addHistory = db.execute("INSERT INTO history (user_id, stock, number, type, price) VALUES (:user, :stock, :shares, :operation, :price)",
                                        user=session["user_id"],
                                        stock=result["symbol"],
                                        shares=number,
                                        operation="BUY",
                                        price=float(result["price"]))
                duplication = db.execute("SELECT * FROM portfolio WHERE stock = :request_quote",
                                         request_quote=result["symbol"])
                if not duplication:
                    new_number = db.execute("INSERT INTO portfolio (user_id, stock, number, price) VALUES (:user, :stock, :number, :price)",
                                            user=session["user_id"],
                                            stock=result["symbol"],
                                            number=request.form.get("shares"),
                                            price=float(result["price"]))
                    return redirect("/")
                else:
                    new_number = db.execute("UPDATE portfolio SET number = :new WHERE (user_id = :user) AND (stock = :request_quote)",
                                            new=int(duplication[0]["number"]) + number,
                                            user=session["user_id"],
                                            request_quote=result["symbol"])
                    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    operations = db.execute("SELECT * FROM history WHERE user_id = :user", user=session["user_id"])
    if not operations:
        return render_template("history.html", bad="Вы еще не осуществили ни одной операции, решайтесь уже, миллион на дороге не валяется)))")
    else:
        return render_template("history.html", operations=operations)


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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html", bad="")

    else:
        if not request.form.get("symbol"):
            return apology("Введите символ", 400)
        else:
            result = lookup(request.form.get("symbol"))
            if not result:
                return apology("Не корректно введен символ! Попробуйте еще раз.", 400)
            else:
                return render_template("quote_result.html", result=result)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # если гет - возвращаем форму

    if request.method == "GET":
        return render_template("register.html")
    # если пост - проверяем и записываем в базу

    else:
        if not request.form.get("username"):
            return apology("Аноним не принимается", 400)
        if not request.form.get("password"):
            return apology("Забыли пароль", 400)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Пароли не совпадают", 400)

        user = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                          username=request.form.get("username"),
                          hash=generate_password_hash(request.form.get("password")))

        if not user:
            return apology("Имя пользователя занято")

        session["user_id"] = user
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        portfolio = db.execute("SELECT * FROM portfolio WHERE (user_id = :user)",
                               user=session["user_id"])
        return render_template("sell.html", portfolio=portfolio)
    else:
        if not request.form.get("symbol"):
            return apology("Не введен символ!", 400)
        elif not request.form.get("shares"):
            return apology("Не введено количество акций!", 400)
        else:
            portfolio = db.execute("SELECT * FROM portfolio WHERE (user_id = :user) AND (stock = :quote)",
                                   user=session["user_id"],
                                   quote=request.form.get("symbol"))
            if int(portfolio[0]["number"]) < int(request.form.get("shares")):
                return apology("У Вас не достаточно акций для продажи!", 400)
            else:
                request_price = lookup(request.form.get("symbol"))
                result = request_price["price"] * int(request.form.get("shares"))
                row = db.execute("SELECT cash FROM users WHERE id = :user", user=session["user_id"])
                curentCash = float(row[0]["cash"])
                newCash = db.execute("UPDATE users SET cash = :balance WHERE id = :user",
                                     balance=float(curentCash + result),
                                     user=session["user_id"])

                addHistory = db.execute("INSERT INTO history (user_id, stock, number, type, price) VALUES (:user, :stock, :number, :operation, :price)",
                                        user=session["user_id"],
                                        stock=request.form.get("symbol"),
                                        number=request.form.get("shares"),
                                        operation="SELL",
                                        price=float(request_price["price"]))
                # print(int(portfolio[0]["number"]))
                # print(float(portfolio[0]["price"]))
                # print(int(request.form.get("number")))
                # print(float(request_price["price"]))
                shares = int(portfolio[0]["number"]) - int(request.form.get("shares"))
                if shares == 0:
                    updatePortfolio = db.execute("DELETE FROM portfolio WHERE stock = :request_quote",
                                                 request_quote=request.form.get("symbol"))
                else:
                    updatePortfolio = db.execute("UPDATE portfolio SET number = :new, price = :newPrice WHERE (user_id = :user) AND (stock = :request_quote)",
                                                 new=shares,
                                                 user=session["user_id"],
                                                 request_quote=request.form.get("symbol"),
                                                 newPrice=(int(portfolio[0]["number"]) * float(portfolio[0]["price"]) + int(request.form.get("shares")) * float(request_price["price"])) / (int(portfolio[0]["number"]) + int(request.form.get("shares"))))
                return redirect("/")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
