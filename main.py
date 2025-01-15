from datetime import date
from hashlib import md5
from flask import Flask, abort, render_template, redirect, url_for, flash, request,current_app, session
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor, CKEditorField
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, URL, ValidationError, Email, Length
from flask_wtf import FlaskForm
from flask_sqlalchemy import SQLAlchemy, pagination
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from typing import List
import hashlib
import smtplib
import os
from dotenv import load_dotenv
from smtplib import SMTP


# Load environment variables
load_dotenv()
EMAIL = os.getenv("EMAIL")
PASSWORD= os.getenv("EMAIL_PASSWORD")
DB_URL = os.getenv("DB_URL", "sqlite:///todo.db")

#global variables 
completed_tasks=[]


# Create a new Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "secret")
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)  # Properly initializing the login manager with the app

# Create a user_loader callback
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

#creating a declarative base
class Base(DeclarativeBase):
    pass

# Connect to the database
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#create a user table in the database
# User model
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)  # Primary key
    email = db.Column(db.String(100), unique=True, nullable=False)  # Email should not be null
    password = db.Column(db.String(100), nullable=False)  # Password should not be null
    name = db.Column(db.String(1000), nullable=False)  # Name should not be null
    # Relationship with ToDoList not required in this case as i am not going to access todo list
    todo_list = db.relationship('ToDoList', back_populates='user', cascade='all, delete-orphan')

# ToDoList model
class ToDoList(db.Model):
    __tablename__ = 'todo_list'
    id = db.Column(db.Integer, primary_key=True)  # Primary key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Foreign key
    name = db.Column(db.String(250), nullable=False)  # Name of the to-do list
    due_date = db.Column(db.String(250), nullable=False)  # Due date of the to-do list  
    due_time = db.Column(db.String(250), nullable=False)  # Due time of the to-do list
    # Relationship with TasksList
    todo_task = db.relationship('TasksList', back_populates='todo_list', cascade='all, delete-orphan')
    # Relationship with User not required in this case as i am not going to access user 
    user = db.relationship('User', back_populates='todo_list') 


# Task model
class TasksList(db.Model):
    __tablename__ = 'tasks_list'
    id = db.Column(db.Integer, primary_key=True)  # Primary key
    todo_id = db.Column(db.Integer, db.ForeignKey('todo_list.id'), nullable=False)  # Foreign key
    title = db.Column(db.String(250), nullable=False)  # Task title
    due_date = db.Column(db.String(250), nullable=False)  # Due due_date
    due_time = db.Column(db.String(250), nullable=False)  # Due due_time
    is_completed = db.Column(db.Boolean, nullable=False, default=False)  # Task status
    # Relationship with ToDoList Not Required in this case as i am not going to access todo_list 
    todo_list = db.relationship('ToDoList', back_populates='todo_task')

# Initialize the database

with app.app_context():
    db.create_all()




#login form 
class LoginForm(FlaskForm):
    email = StringField(label='Email')
    password = PasswordField(label='Password')
    submit = SubmitField(label='Login')

#creating a registration form
class RegisterForm(FlaskForm):
    email = StringField(label='Email', validators=[DataRequired(), Email()])
    password = PasswordField(label='Password', validators=[DataRequired(), Length(min=6)])
    name = StringField(label='Name', validators=[DataRequired()])
    submit = SubmitField(label='Register')

#creating a ToDoList form for the task table
class CreateToDoList(FlaskForm):
    name = StringField(label='To-Do List Name', validators=[DataRequired()], render_kw={"placeholder": "To-Do List Name"})
    due_date = StringField(label='Due Date', validators=[DataRequired()], render_kw={"placeholder": "YYYY-MM-DD"})
    due_time = StringField(label='Due Time', validators=[DataRequired()], render_kw={"placeholder": "Eg: 12:00 PM"})
    submit = SubmitField(label='Add ToDoList')

# Update ToDoList form
class UpdateToDoListForm(CreateToDoList):
    submit = SubmitField(label='Update ToDoList')

#task_list form
class CreateTaskListForm(FlaskForm):
    title = StringField(label='Title', validators=[DataRequired()], render_kw={"placeholder": "ToDoList Title"})
    due_date = StringField(label='Due Date', validators=[DataRequired()], render_kw={"placeholder": "YYYY-MM-DD"})
    due_time = StringField(label='Due Time', validators=[DataRequired()], render_kw={"placeholder": "Eg: 12:00 PM"})
    submit = SubmitField(label='Add Task')

# update ToDoList form
class UpdateTaskListForm(CreateTaskListForm):
    submit = SubmitField(label='Update Task')

class FeedbackForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired()],
        render_kw={"class": "form-control", "placeholder": "Enter your name"}
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email()],
        render_kw={"class": "form-control", "placeholder": "Enter your email address"}
    )
    phone = StringField(
        "Phone",
        validators=[DataRequired()],
        render_kw={"class": "form-control", "placeholder": "Enter your phone number"}
    )
    message = CKEditorField(
        "Message",
        validators=[DataRequired()],
        render_kw={"class": "form-control", "placeholder": "Enter your message"}
    )
    submit = SubmitField(
        "Send Feedback",
        render_kw={"class": "btn btn-primary"}
    )

# url for the home page
@app.route('/', methods=['GET', 'POST'])
def home(): 
    return render_template('index.html',is_logged_in=current_user.is_authenticated)

#methods for register user page
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        name = form.name.data
        new_user = User(
            email=email,
            password=generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8),
            name=name
        )
        #check if the user already exists
        user = db.session.query(User).filter_by(email=email).first()
        if user:
            flash("User already exists! Try login", "danger")
            return redirect(url_for('login'))
        
        #add the user to the database
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f"{new_user.name} registered successfully!", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash("An error occurred while registering the user.", "danger")
            db.session.rollback()
            return redirect(url_for('register'))

    return render_template('register.html', form=form)


#method for login
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip()  # Strip extra spaces for better user input handling
        password = form.password.data

        # Query the database for the user
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("User does not exist! Please register first.", "danger")
            return redirect(url_for('register'))

        # Verify password
        if not check_password_hash(user.password, password):
            flash("Incorrect password! Please try again.", "danger")
            return redirect(url_for('login'))

        # Log the user in
        login_user(user)
     
        flash(f"Welcome back, {user.name}!", "success")
        next_page = request.args.get('next')  # Handle redirection to the originally requested page
        return redirect(next_page) if next_page else redirect(url_for('todo_lists'))

    return render_template('login.html', form=form)


# method for logout
@app.route('/logout')
def logout():
    logout_user()
    flash("You have been logged out successfully!", "success")
    return redirect(url_for('home'))


#method to display the user profile
@app.route('/profile')
def profile():
    if not current_user.is_authenticated:
        flash("You need to login first!", "danger")
        return redirect(url_for('login'))

    return render_template('profile.html', user=current_user)

# method for manage_list in nav bar
@app.route('/todo_lists', methods=['GET', 'POST'])
def todo_lists():
    print(current_user.is_authenticated)
    # Ensure the user is authenticated
    if not current_user.is_authenticated:
        flash("You need to login first!", "danger")
        return redirect(url_for('login'))

    # Querying the to-do lists for the current user
    todo_lists = db.session.query(ToDoList).filter_by(user_id=current_user.id).all()

    # Initialize the form
    form = CreateToDoList()

    # Handling form submission
    if form.validate_on_submit():
        new_todo_list = ToDoList(
            name=form.name.data,
            due_date=form.due_date.data,
            due_time=form.due_time.data,
            user_id=current_user.id  # Associate the list with the current user
        )
        try:
            db.session.add(new_todo_list)
            db.session.commit()
            flash(f"{new_todo_list.name} To-Do List added successfully!", "success")
            # Redirect to the new_task page with the newly created list's ID
            return redirect(url_for('new_task', todo_id=new_todo_list.id))
        except Exception as e:
            # Log the exception for debugging (optional)
            print(f"Error occurred: {e}")
            db.session.rollback()
            flash("An error occurred while adding the To-Do List.", "danger")
            return redirect(url_for('todo_lists'))

    # Render the template with the retrieved to-do lists and the form
    return render_template('todo_lists.html', todo_lists=todo_lists, form=form)



# method to add_new todo list
@app.route('/add_new_todo_list', methods=['GET', 'POST'])
def add_new_todo_list():
    #checking if the user is logged in
    if not current_user.is_authenticated:
        flash("You need to login first!", "danger")
        return redirect(url_for('login'))
    
    form = CreateToDoList()
    if form.validate_on_submit():
        new_todo_list = ToDoList(
            name=form.name.data,
            due_date=form.due_date.data,
            due_time=form.due_time.data,
            user_id=current_user.id
        )
        try:
            db.session.add(new_todo_list)
            db.session.commit()
            flash(f"{new_todo_list.name} To-Do List added successfully!", "success")
            #redirect to the new_task page
            new_todo_list_id = new_todo_list.id
            return redirect(url_for('new_task', todo_id=new_todo_list_id))#redirect to the new_task page
        
        except Exception as e:
            flash("An error occurred while adding the To-Do List.", "danger")
            print(f"Error occurred: {e}")
            db.session.rollback()
            return redirect(url_for('index'))

    return render_template('new_todo_list.html', form=form)

#method to edit the todo list
@app.route('/edit_todo_list/<int:todo_id>', methods=['GET', 'POST'])
def edit_todo_list(todo_id):
    todo_list = db.get_or_404(ToDoList, todo_id)
    form = UpdateToDoListForm(obj=todo_list)

    if form.validate_on_submit():
        todo_list.name = form.name.data
        todo_list.due_date = form.due_date.data
        todo_list.due_time = form.due_time.data
        try:
            db.session.commit()
            flash(f"{todo_list.name} To-Do List updated successfully!", "success")
            return redirect(url_for('todo_lists'))

        except Exception as e:
            flash("An error occurred while updating the To-Do List.", "danger")
            db.session.rollback()
            return redirect(url_for('todo_lists'))
        
    return render_template('edit_todo_list.html', form=form, todo_list=todo_list)    


#method to delete the todo list
@app.route("/delete_todo_list/<int:todo_id>", methods=['GET']) 
def delete_todo_list(todo_id):
    # Query the To-Do List
    # todo_list = db.session.query(ToDoList).filter_by(id=todo_id).first() # Get the To-Do List from the database
    todo_list = db.get_or_404(ToDoList, todo_id) # Get the To-Do List from the database
    # Check if the To-Do List exists
    if not todo_list:
        flash("To-Do List not found.", "danger")
        return redirect(url_for('todo_lists'))

    # Getting hold of task list
    tasks = db.session.query(TasksList).filter(TasksList.todo_id == todo_id).all()

    # Delete the To-Do List and its tasks
    try:
        # Check if the To-Do List has tasks
        if tasks:
            # Delete all tasks in the To-Do List
            for task in tasks:
                db.session.delete(task)
                db.session.commit()
        # Delete the To-Do List
        db.session.delete(todo_list)
        db.session.commit()
        # Flash a success message
        flash(f"{todo_list.name} To-Do List deleted successfully!", "success") # Flash a success message
        
    except Exception as e:
        flash("An error occurred  while deleting the To-Do List.", "danger")
        db.session.rollback()
    return redirect(url_for('todo_lists'))   # Redirect after deleting the To-Do List



# method to add new_task
@app.route('/new/<int:todo_id>', methods=['GET', 'POST'])
def new_task(todo_id):
    # Validate if the todo_id exists (Assume TodoList is another model representing the parent to-do list)
    todo_list = db.session.query(ToDoList).filter_by(id=todo_id).first()
    if not todo_list:
        abort(404, description="To-Do List not found.")

    # Initialize the form
    form = CreateTaskListForm()

    # Query all tasks for the To-Do List
    tasks = db.session.query(TasksList).filter(TasksList.todo_id == todo_id).all()

    # Separate completed and incomplete tasks
    completed_tasks = [task for task in tasks if task.is_completed]
    incomplete_tasks = [task for task in tasks if not task.is_completed]

    # Handle form submission
    if form.validate_on_submit():
        new_task = TasksList(
            todo_id=todo_id,
            title=form.title.data.strip(),
            due_date=form.due_date.data,
            due_time=form.due_time.data,
            is_completed=False
        )
        try:
            # Add and commit the new task
            db.session.add(new_task)
            db.session.commit()
            flash("Task added successfully!", "success")
            return redirect(url_for('new_task', todo_id=todo_id))
        except Exception as e:
            # Log error and rollback
            app.logger.error(f"Error adding task: {e}")
            db.session.rollback()
            flash("An error occurred while adding the task.", "danger")
            return redirect(url_for('new_task', todo_id=todo_id))

    # Render the template with all necessary data
    return render_template(
        'new_task.html',
        form=form,
        tasks=incomplete_tasks,
        completed_tasks=completed_tasks,
        todo_list=todo_list
    )



# url for editing the task
@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    task = db.get_or_404(TasksList, task_id) # Get the task from the database
    form = UpdateTaskListForm(obj=task) # Prefill the form with the task data

    if form.validate_on_submit():

        task.title = form.title.data
        task.due_date = form.due_date.data
        task.due_time = form.due_time.data


        try:
            db.session.commit()
            flash("Task updated successfully!", "success")
            return redirect(url_for('new_task', todo_id=task.todo_id))

        except Exception as e:
            flash("An error occurred while updating the task.", "danger")
            db.session.rollback()
            return redirect(url_for('new_task', todo_id=task.todo_id))

        
    return render_template('edit_task.html', form=form, task=task)

# url for deleting the task
@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    task = db.get_or_404(TasksList, task_id)
    try:
        db.session.delete(task)
        db.session.commit()
        flash(f"{task.title} Task deleted successfully!", "success")
        return redirect(url_for('new_task', todo_id=task.todo_id))

    
    except Exception as e:
        flash("An error occurred while deleting the task.", "danger")
        db.session.rollback()
        return redirect(url_for('new_task', todo_id=task.todo_id))

    

# url for complete task
@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    task = db.get_or_404(TasksList, task_id)
    task.is_completed = not task.is_completed

    try:
        db.session.commit()
        flash(f"Task {task.title} completed successfully!", "success")
        return redirect(url_for('new_task', todo_id=task.todo_id))

    except Exception as e:
        flash("An error occurred while updating the task status.", "danger")
        db.session.rollback()
        return redirect(url_for('new_task', todo_id=task.todo_id))

    
# url for clearing the completed tasks
@app.route('/clear_completed_tasks/<int:todo_id>', methods=['GET'])
def clear_completed_tasks(todo_id):
 
    try:
        db.session.query(TasksList).filter(TasksList.todo_id==todo_id,TasksList.is_completed == True).delete()
        db.session.commit()
        flash("Completed tasks cleared successfully!", "success")
    except Exception as e:
        flash("An error occurred while clearing completed tasks.", "danger")
        db.session.rollback()
        
    return redirect(url_for('new_task', todo_id=todo_id))  # Redirect after clearing


# Feedback route
@app.route('/send_feedback', methods=['GET', 'POST'])
def send_feedback():
    form = FeedbackForm()
    if form.validate_on_submit():
        # Get form data
        name = form.name.data
        email = form.email.data
        phone = form.phone.data
        message = form.message.data


        # Send feedback to the admin
        try:
            with SMTP("smtp.gmail.com") as connection:
                connection.starttls()
                connection.login(user=EMAIL, password=PASSWORD)
                connection.sendmail(
                    from_addr=EMAIL,
                    to_addrs=email,
                    msg=f"Subject:New Feedback\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nMessage: {message}"
                )
        except Exception as e:
            print(e)
            flash("An error occurred while sending feedback. Please try again.", "error")
            return redirect(url_for('send_feedback'))

        # Set success message
        flash("Feedback sent successfully!", "success")

        return redirect(url_for('home'))

    return render_template('feedback.html', form=form)

# initializing the app
if __name__ == "__main__":
    app.run(debug=True)