from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_gravatar import Gravatar
from smtplib import SMTP
from forms import RegisterForm, CreatePostForm, LoginForm, CommentForm
from functools import wraps


class Base(DeclarativeBase):
    pass


# initial settings...
app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6d2onzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECTING TO DB...
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# login functionalities...
login_manager = LoginManager()
login_manager.init_app(app)

# initializing gravatar...
# # after "app", everything's default value. I'm keeping them here just to remember the values...
gravatar = Gravatar(app, size=50, rating='g', default='retro', force_default=False,
                    force_lower=False, use_ssl=False, base_url=None)  # modified size has a default value of '100'...

# website functionality requirements...
current_year = date.today().year
MY_EMAIL = 'mahim.testmail@gmail.com'
MY_APP_PASSWORD = 'eyssbaxyslxzaogc'


# CONFIGURE TABLES...
class User(UserMixin, db.Model):
    # noinspection SpellCheckingInspection
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    password: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    # below line will act like a list of BlogPost objects attached to each user...
    # where the "author" refers to the author property in the BlogPost class...
    posts = relationship('BlogPost', back_populates='author')

    # here, "comment_author" refers to the comment_author property in the Comment class...
    comments = relationship('Comment', back_populates='comment_author')


class BlogPost(db.Model):
    # noinspection SpellCheckingInspection
    __tablename__ = 'blog_posts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # creating a foreign_key to refer to users table named "users.id"...
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))

    # creating reference to the User object, the "posts" refers to the posts property in the User class...
    author = relationship('User', back_populates='posts')

    title: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String, nullable=False)

    # creating parent relationship with parent_post obj from Comment class...
    comments = relationship('Comment', back_populates='parent_post')


class Comment(db.Model):
    # noinspection SpellCheckingInspection
    __tablename__ = 'comments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # creating a foreign_key to refer to users table named "users.id"...

    # "comments" refers to the comments property of the User class...
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))
    comment_author = relationship('User', back_populates='comments')

    # creating child relation with the comments obj from BlogPost class associating with blogpost_id...
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey('blog_posts.id'))
    parent_post = relationship('BlogPost', back_populates='comments')


# building the skeleton...
# with app.app_context():  # use only one time, comment out these two lines after that...
#     db.create_all()


@app.route('/', methods=['GET'])
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template('index.html', all_posts=posts,
                           year=current_year, this_user=current_user)


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    register_form = RegisterForm()
    password = register_form.password.data

    if register_form.validate_on_submit():

        if User.query.filter_by(email=register_form.email.data).first():
            flash(message='You\'ve already signed up with this email, consider logging in...')

            return redirect(url_for('login_page'))

        hashed_and_salted_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        # noinspection PyArgumentList
        new_user = User(
            email=register_form.email.data,
            name=register_form.name.data.title(),
            password=hashed_and_salted_password
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)  # making sure the new user logs in as soon as he/she registers...
        return redirect(url_for('get_all_posts'))

    return render_template('register.html', form=register_form,
                           year=current_year, this_user=current_user)


@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(id=user_id).first()


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    login_form = LoginForm()

    if login_form.validate_on_submit():
        email = login_form.email.data
        password = login_form.password.data
        this_user = User.query.filter_by(email=email).first()

        if not this_user:  # if email id isn't found...
            flash(message=f'This email({email}) does not exist. Please check and try again!')

        elif not check_password_hash(this_user.password, password):  # if passwords don't match...
            flash(message='Oh no, You might have mistaken the password cause it does not match.')

        else:
            login_user(this_user)
            return redirect(url_for('get_all_posts'))

    return render_template('login.html', form=login_form,
                           year=current_year, this_user=current_user)


@app.route('/logout', methods=['GET'])
def logout_page():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = BlogPost.query.filter_by(id=post_id).first()

    if comment_form.validate_on_submit():

        if not current_user.is_authenticated:
            flash(message='You need to Login or Register in order to comment.')
            return redirect(url_for('login_page'))

        new_comment = Comment(
            text=comment_form.comment_field.data,
            comment_author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))

    return render_template('post.html', post=requested_post, form=comment_form,
                           year=current_year, this_user=current_user)


def admin_only(func):  # creating admin only decorator...
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.id == 1:  # if user is not admin(id=1), return abort with 403 error...
            return abort(403)
        # else, continue with the route function...
        return func(*args, **kwargs)

    return decorated_function


@app.route('/new-post', methods=['GET', 'POST'])
@admin_only  # notice the "Mark with @admin-only decorator"
def create_post():
    new_post_form = CreatePostForm()

    if new_post_form.validate_on_submit():
        new_post = BlogPost(
            author=current_user,
            title=new_post_form.title.data,
            subtitle=new_post_form.subtitle.data,
            img_url=new_post_form.img_url.data,
            body=new_post_form.body.data,
            date=date.today().strftime('%B %d, %y')
        )

        db.session.add(new_post)
        db.session.commit()

        return redirect(url_for('get_all_posts'))

    return render_template('make-post.html', form=new_post_form,
                           year=current_year, this_user=current_user)


@app.route('/edit-post/<int:post_id>', methods=['GET', 'POST'])
@admin_only  # notice the "Mark with @admin-only decorator"
@login_required
def edit_post(post_id):
    selected_post = BlogPost.query.filter_by(id=post_id).first()
    edit_post_form = CreatePostForm(obj=selected_post)

    if edit_post_form.validate_on_submit():
        # short method...
        edit_post_form.populate_obj(selected_post)
        db.session.commit()

        # edit_form = CreatePostForm(
        #     title=post.title,
        #     subtitle=post.subtitle,
        #     img_url=post.img_url,
        #     author=post.author,
        #     body=post.body
        # )
        # if edit_form.validate_on_submit():
        #     post.title = edit_form.title.data
        #     post.subtitle = edit_form.subtitle.data
        #     post.img_url = edit_form.img_url.data
        #     post.author = edit_form.author.data
        #     post.body = edit_form.body.data
        #     db.session.commit()

        return redirect(url_for('show_post', post_id=selected_post.id))

    return render_template('make-post.html', form=edit_post_form, is_edit=True,
                           year=current_year, this_user=current_user)


@app.route('/delete/<int:post_id>', methods=['GET'])
@admin_only  # notice the "Mark with @admin-only decorator"
def delete_post(post_id):
    selected_post = BlogPost.query.filter_by(id=post_id).first()
    db.session.delete(selected_post)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route('/about', methods=['GET'])
def about_page():
    return render_template('about.html', year=current_year,
                           this_user=current_user)


@app.route('/contact', methods=['GET', 'POST'])
def contact_page():
    if request.method == 'POST':
        data = request.form
        name = data['sender_name']
        email = data['sender_email']
        phone = data['sender_phone']
        message = data['sender_message']

        # sending mail with the given data...
        with SMTP(host='smtp.gmail.com', port=587) as connection:
            connection.starttls()
            connection.login(user=MY_EMAIL, password=MY_APP_PASSWORD)

            subject = 'New User CONTACTED!'
            body = f'Name: {name}\nEmail: {email}\nPhone: {phone}\nMessage: {message}'
            message = f'Subject: {subject}\n\n{body}'

            connection.sendmail(
                from_addr=MY_EMAIL,
                to_addrs='mahimnxt23@gmail.com',
                msg=message
            )

        return render_template('contact.html', msg_sent=True,
                               year=current_year, this_user=current_user)

    return render_template('contact.html', msg_sent=False,
                           year=current_year, this_user=current_user)


if __name__ == '__main__':
    app.run(debug=True)
