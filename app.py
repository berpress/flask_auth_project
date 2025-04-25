from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import jwt
import datetime
from models import db, User
from utils import create_token, token_required

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SECRET_KEY'] = 'your-secret-key'
db.init_app(app)
app.secret_key = 'super-session-key'  # отдельно от JWT

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/init-db', methods=['GET'])
def init_db():
    with app.app_context():
        db.create_all()
    return jsonify({'status': 'DB Initialized'}), 200



# ----------- API Routes -------------

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    if not data.get('login') or not data.get('password'):
        return jsonify({'status': 'Error', 'message': 'Missing login or password'}), 400

    if User.query.filter_by(login=data['login']).first():
        return jsonify({'status': 'Error', 'message': 'User already exists'}), 400

    new_user = User(login=data['login'], password=data['password'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'status': 'Successful'}), 200


@app.route('/api/auth', methods=['POST'])
def api_auth():
    data = request.get_json()
    user = User.query.filter_by(login=data.get('login'), password=data.get('password')).first()
    if not user:
        return jsonify({'status': 'Error', 'message': 'Invalid credentials'}), 401

    token = create_token(user.id)
    return jsonify({'token': token}), 200


@app.route('/api/user', methods=['POST'])
@token_required
def api_create_user(current_user):
    data = request.get_json()
    required_fields = ['name', 'age', 'gender', 'date_registration', 'is_active']
    if not all(k in data for k in required_fields):
        return jsonify({'status': 'Error', 'message': 'Missing fields'}), 400

    new_profile = User(
        login=f"profile_{datetime.datetime.utcnow().timestamp()}",
        password='none',
        name=data['name'],
        age=data['age'],
        gender=data['gender'],
        date_registration=data['date_registration'],
        is_active=data['is_active']
    )
    db.session.add(new_profile)
    db.session.commit()
    return jsonify({'status': 'Successful'}), 200


@app.route('/api/users', methods=['GET'])
@token_required
def api_list_users(current_user):
    users = User.query.order_by(User.id.desc()).limit(20).all()
    return jsonify([u.to_dict() for u in users]), 200


@app.route('/api/user/<int:user_id>', methods=['GET'])
@token_required
def api_get_user(current_user, user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict()), 200


@app.route('/clear-db', methods=['POST'])
def clear_db():
    try:
        num_deleted = db.session.query(User).delete()
        db.session.commit()
        return jsonify({'status': 'Successful', 'deleted': num_deleted}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'Error', 'message': str(e)}), 500

# ----------- Web Routes (HTML) -------------

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if session.get('token'):
        return redirect(url_for('users_page'))  # Если токен есть, перенаправляем на страницу пользователей

    if request.method == 'POST':
        login = request.form.get('login')
        password = request.form.get('password')

        if User.query.filter_by(login=login).first():
            return render_template('register.html', error='Пользователь уже существует')

        new_user = User(login=login, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('token'):
        return redirect(url_for('users_page'))  # Если токен есть, перенаправляем на страницу пользователей

    error = None
    if request.method == 'POST':
        login = request.form.get('login')
        password = request.form.get('password')
        user = User.query.filter_by(login=login, password=password).first()
        if user:
            session['token'] = create_token(user.id)
            return redirect(url_for('users_page'))
        else:
            error = 'Неверный логин или пароль'
    return render_template('login.html', error=error)


@app.route('/users')
def users_page():
    token = session.get('token')
    if not token:
        return redirect(url_for('login'))  # Если нет токена, перенаправляем на логин

    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        users = User.query.order_by(User.id.desc()).limit(20).all()
        return render_template('users.html', users=users)
    except:
        return redirect(url_for('login'))  # Если токен недействителен, перенаправляем на логин


@app.route('/add-user', methods=['GET', 'POST'])
def add_user_page():
    token = session.get('token')
    if not token:
        return render_template('add_user.html')

    if request.method == 'POST':
        try:
            data = request.form
            new_profile = User(
                login=f"profile_{datetime.datetime.utcnow().timestamp()}",
                password='none',
                name=data['name'],
                age=int(data['age']),
                gender=data['gender'],
                date_registration=data['date_registration'],
                is_active=('is_active' in data)
            )
            db.session.add(new_profile)
            db.session.commit()
            return redirect(url_for('users_page'))
        except Exception as e:
            return f"Ошибка: {e}", 400

    return render_template('add_user.html')


@app.route('/users-page')
def users_page_html():
    return render_template('users.html')

@app.route('/logout')
def logout():
    session.pop('token', None)  # Удаляем токен из сессии
    return redirect(url_for('login'))  # Перенаправляем на страницу логина

@app.route('/flow')
def flow():
    return render_template('flow.html')

if __name__ == '__main__':
    app.run(debug=True)
