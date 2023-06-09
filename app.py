import flask
import requests

from dotenv import load_dotenv, find_dotenv
from flask import Flask, request, render_template, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from os import getenv
from werkzeug.security import generate_password_hash, check_password_hash


# create the app
app = Flask(__name__)

# load environment variables and set app config settings
load_dotenv(find_dotenv())
app.config["SQLALCHEMY_DATABASE_URI"] = getenv("DATABASE_URL")
app.config['SECRET_KEY'] = getenv("SECRET_KEY")
app.secret_key = 'super secret key'

# create database
db = SQLAlchemy(app)


# These classes form the relations in the database 
class Comment(db.Model): #a model for a row, defines a table
    id = db.Column(db.Integer, primary_key=True)
    recipe = db.Column(db.Integer, unique=False, nullable=False)
    user = db.Column(db.String(80), unique=False, nullable=False)
    rating = db.Column(db.Integer, unique=False, nullable=False)
    comment = db.Column(db.String(420), unique=False, nullable=False)
    
class Saved_Recipes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(80), unique=False, nullable=False)
    recipe_name = db.Column(db.String(420), unique=False, nullable=False)
    recipe_id = db.Column(db.Integer, unique=False, nullable=False)
    
class Person(db.Model,UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(420), nullable=False)


# make sure database tables are created
with app.app_context():
    db.create_all()

# setup user authentification
login_manager = LoginManager()
login_manager.init_app(app)

# this is how the login manager will be able to
# set who is logged in.
@login_manager.user_loader
def load_user(user_id):
    return Person.query.get(user_id)


# Landing Page: If the user is logged in, go directly to the
# Dashboard, and if not go to the Login Page
@app.route('/')
def start():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    else:
        return redirect(url_for('login'))


# Login Page: from here they can login and be redirected to the Dashboard,
# or they can go to the create_account page.
@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    # if they submitted the login form, check the username and password
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # get a user from the database
        user = Person.query.filter_by(username=username).first()

        # if the user exists and the password matches, log them in
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('start'))
        # otherwise log an error message
        else:
            error = 'Invalid credentials. Please try again.'
        
    return render_template('login.html', error=error)


# Logout: this logs out the user and sends them back to the start route
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('start'))


# Create Account: you can arrive here from the login page
# on this page you create a new acocunt to be stored in the database
@app.route('/create_account',methods=['GET','POST'])
def create_account():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # get user from the database
        user = Person.query.filter_by(username=username).first()

        # if you were able to find a user, then log error
        if user:
            error = 'Account already exists. Try again.'
        # otherwise go back to the login page
        else:
            # hash the users password
            hashed_password = generate_password_hash(password)
            # save user credentials to the database
            new_user = Person(username=username,password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            return render_template('login.html')

    return render_template('create_account.html',error=error)

    
#this displays the dashboard, should always be accessible from every page
@app.route('/dashboard')
@login_required
def index():
    saved_list = db.session.query(Saved_Recipes).filter_by(user=current_user.username).all()
    #the saved_list will likely require some API calls right here in order to properly display
    #might be API intensive to display too many in one list
    comments = db.session.query(Comment).filter_by(user=current_user.username).all()
    #stretch feature for displaying most popular recipes
    #query the comments per recipe for most popular recipes and display information of the one with the best overall rating
    #should give higher weight to recipes with more comments?
    return render_template('dash.html', saved_list = saved_list, comments=comments)

#search bar function, should always be accessible from every page
@app.route('/search',methods=['GET','POST'])
@login_required
def search():
    results = None
    # if the user performed a query, parse the results and display
    if request.method == 'POST':
        query = request.form['query']
        # Use the Whoosh library to search for the query
        # Return the search results in an HTML template
        load_dotenv(find_dotenv())
        SPOON_API_SEARCH_URL = "https://api.spoonacular.com/recipes/complexSearch?"
        spoon_api_response = requests.get(
            SPOON_API_SEARCH_URL,
            params={
                "apiKey": getenv("RECIPE_API"),
                "query": query
            },
        )
        results = spoon_api_response.json()
    return render_template('search.html', results=results)


#when link from search/saved-list clicked, redirects to this. Uses ID of recipe
#ID can be accessed via recipe["id"]
#this also handles both adding comments/ratings & adding to saved recipes
@app.route('/recipe/<recipe_id>', methods=["GET", "POST"])
@login_required
def recipe(recipe_id):
    form_data = request.form
    if request.method == 'POST':
        #for comment submission
        if(form_data["type"] == 'comment'): 
            c = Comment(recipe = recipe_id, 
                            user = current_user.username,
                            rating = form_data["rating"],
                            comment = form_data["comment"])  
            db.session.add(c)
            db.session.commit()
        else: #for adding to saved list
            s = Saved_Recipes(recipe_id = recipe_id, 
                              recipe_name = form_data['name'],
                            user = current_user.username)  
            db.session.add(s)
            db.session.commit()
    #end POST method, begin page info gathering
    SPOON_API_GET_RECIPE_URL = "https://api.spoonacular.com/recipes/" + recipe_id
    spoon_api_response_1 = requests.get(
            SPOON_API_GET_RECIPE_URL + '/information',
            params={
                "apiKey": getenv("RECIPE_API"),
            },
        )
    recipe = spoon_api_response_1.json()
    spoon_api_response_2 = requests.get(
            SPOON_API_GET_RECIPE_URL + '/analyzedInstructions',
            params={
                "apiKey": getenv("RECIPE_API"),
            },
        )
    instructions = spoon_api_response_2.json()
    spoon_api_response_3 = requests.get(
            SPOON_API_GET_RECIPE_URL + '/ingredientWidget.json',
            params={
                "apiKey": getenv("RECIPE_API"),
            },
        )
    ingredients = spoon_api_response_3.json()
    query = db.session.query(Comment).filter_by(recipe=recipe_id).all()
    return render_template('recipe.html', recipe=recipe, instruct=instructions, ingred=ingredients, query=query)


#this will generate the printable shopping list from entries in the saved list
#currently this will use every recipe in the saved list
#for stretch features shopping list should be a separate DB that has:
# >desired servings adjustments, which can be tuned before the final product is produced
# >ingredient aggrigation, happens once the list is generated
@app.route('/shopping-list')
@login_required
def list_generator():
    pass
    #saved_list = db.session.query(Saved_Recipes).filter_by(user=current_user.username).all()
    #for recipe in saved_list:
        #use API to collect ingredient information from each saved recipe
        #create an dictionary with keys for each ingredient
        # >if key does not exist, set initial value to 0 and add ingredients
        # >else incriment ingredients by whats required for the recipe 
    
#comment this out when using "fly deploy", uncomment when testing locally
#app.run()