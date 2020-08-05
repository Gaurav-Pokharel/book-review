import os, json

from flask import Flask, session, render_template, request, redirect, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import requests

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/", methods=["POST", "GET"])
def index():
	if session.get("login") == True:
		return redirect(url_for('home'))
	else:
		if request.method == "POST":
			username=request.form.get("username")
			password=request.form.get("password")
			query_user=db.execute("SELECT id, password, email, username from users where username = :username",{
							   "username":username}).fetchone()
			if query_user is None :
				return render_template("message.html", message="OOPS! incorrect username, try again", mg=1)

			elif password == query_user.password :
				session['login']= True
				session['user_id']=query_user.id	
				return redirect(url_for('home'))
			else :
				return render_template("message.html", message="OOPS! incorrect password, try again", mg=1)
	return render_template("index.html")
	


@app.route("/register", methods=["POST"])
def register():
	username=request.form.get("username")
	email=request.form.get("email")
	password=request.form.get("password")

	users = db.execute("select username from users").fetchall()
	error = 0

	for user in users:
		if user.username == username:
			error=1
			break

	if error :
		return render_template("message.html", message="OOPS!, user name is already taken try another name", mg=error)
	elif email is None or username is None or password is None :
		error=1
		return render_template("message.html", message="Incomplete information, fill form again!", mg=error)
	else :
		db.execute("INSERT INTO users (email, password, username) VALUES (:email, :password, :username)",
                    {"email": email, "password": password, "username": username})
		db.commit()
		return render_template("message.html", message="Congratulation! registration completed", mg=error)


@app.route("/home/logout")
def logout():
	session['login']= False
	session['user_id']= None
	return redirect(url_for('index'))

	
@app.route("/home")
def home():
	if session.get('login') == True:
		user_id=session.get('user_id')
		user=db.execute("SELECT id, password, email, username from users where id = :user_id",{
							   "user_id":user_id}).fetchone()
		username=user.username.capitalize()
		return render_template("home.html", user=username)
	else:
		return redirect(url_for('index'))

@app.route("/home/search/", methods=["POST"])
def search():
	if session.get('login') == True:
		query=request.form.get("query")
		# Take input and add a wildcard
		query='%' + request.form.get("query") + '%'
		# Capitalize all words of input for search
		# https://docs.python.org/3.7/library/stdtypes.html?highlight=title#str.title
		query = query.title()
		books=db.execute("SELECT id, isbn, title, author FROM books WHERE isbn LIKE :query OR title LIKE :query OR author LIKE :query LIMIT 15",
			{"query":query}).fetchall()
		return render_template("search.html", books=books)
	else:
		return redirect(url_for('index'))

@app.route('/book/<book_id>')
def book(book_id):
	if session.get('login') == True:
		book=db.execute("SELECT id, isbn, title, author FROM books WHERE id = :book_id",
			{"book_id":book_id}).fetchone()
		# goodreads api
		key_goodreads="spz9iwaoXpw3WvWj5Q7hQ"
		res=requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": key_goodreads, "isbns": book.isbn})
		if res.status_code != 200:
			raise Exception("Error: API request unsuccessful.")
		book_api=res.json()
		no_rating=book_api['books'][0]['work_ratings_count']
		rating=book_api['books'][0]["average_rating"]
		# comments
		rows=db.execute("SELECT reviews.id, reviews.rating, reviews.comment, users.username, reviews.user_id FROM reviews INNER JOIN users ON reviews.user_id = users.id WHERE reviews.book_id= :book_id",
			{"book_id":book_id})
		if rows.rowcount == 0:
			comments=None
		else:
			comments=rows.fetchall()
		# user
		user_id=session.get('user_id')
		return render_template("book.html", book=book, gr_no_rating=no_rating, gr_rating=rating, comments=comments, user_id=user_id)
	else:
		return redirect(url_for('index'))

@app.route('/book/comment', methods=["POST"])
def comment():
	if session.get('login') == True:
		if request.method == "POST":
			comment=request.form.get("comment")
			rating=request.form.get("rating")
			book_id=request.form.get("book_id")
			user_id=session.get('user_id')
			row1=db.execute("SELECT comment FROM reviews WHERE user_id= :user_id",{"user_id":user_id})
			if row1.rowcount == 0:
				db.execute("INSERT INTO reviews (rating, comment, user_id, book_id) VALUES (:rating, :comment, :user_id, :book_id)",
                    {"rating": rating, "comment": comment, "user_id": user_id, "book_id": book_id})
				db.commit()	
			else:	
				error=1
				return render_template("message.html", message="You have already submitted your review", mg=error)
			return redirect(url_for('book', book_id=book_id))
	else:
		return redirect(url_for('index'))