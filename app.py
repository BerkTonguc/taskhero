from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

project_users = db.Table('project_users',
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    steps = db.relationship('Step', backref='project', lazy=True)
    users = db.relationship('User', secondary=project_users, lazy='subquery',
        backref=db.backref('projects', lazy=True))
    notes = db.relationship('ProjectNote', backref='project', lazy=True)

    @property
    def completed_steps(self):
        return len([step for step in self.steps if step.completed])

    @property
    def total_steps(self):
        return len(self.steps)

class Step(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    note = db.Column(db.Text, nullable=True)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

class ProjectNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('notes', lazy=True))  # İlişki tanımı
    comments = db.relationship('Comment', backref='note', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    note_id = db.Column(db.Integer, db.ForeignKey('project_note.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check your username and password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    projects = Project.query.all()
    current_date = datetime.now().date()
    return render_template('dashboard.html', projects=projects, current_date=current_date)

@app.route('/add_project', methods=['GET', 'POST'])
@login_required
def add_project():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name')
        start_date = datetime.strptime(request.form.get('start'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end'), '%Y-%m-%d').date()
        user_ids = request.form.getlist('users')
        users = User.query.filter(User.id.in_(user_ids)).all()
        new_project = Project(name=name, start_date=start_date, end_date=end_date, users=users)
        db.session.add(new_project)
        db.session.commit()
        return redirect(url_for('dashboard'))
    users = User.query.all()
    return render_template('add_project.html', users=users)

@app.route('/project_details/<int:project_id>', methods=['GET', 'POST'])
@login_required
def project_details(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == 'POST' and current_user.role == 'admin':
        content = request.form.get('note')
        if len(content) > 200:  # Backend karakter sınırı kontrolü
            flash('Note content exceeds the maximum allowed length of 200 characters.')
            return redirect(url_for('project_details', project_id=project_id))
        
        if content:  # content kontrolü ekleyin
            new_note = ProjectNote(content=content, project_id=project.id, user_id=current_user.id)
            db.session.add(new_note)
            db.session.commit()
            return redirect(url_for('project_details', project_id=project_id))
    return render_template('project_details.html', project=project)

@app.route('/delete_note/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    note = ProjectNote.query.get_or_404(note_id)
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    project_id = note.project_id

    # Önce note ile ilişkili tüm yorumları sil
    for comment in note.comments:
        db.session.delete(comment)

    db.session.delete(note)
    db.session.commit()
    return redirect(url_for('project_details', project_id=project_id))

@app.route('/add_comment/<int:note_id>', methods=['POST'])
@login_required
def add_comment(note_id):
    note = ProjectNote.query.get_or_404(note_id)
    content = request.form.get('comment')
    if len(content) > 200:  # Backend karakter sınırı kontrolü
        flash('Comment content exceeds the maximum allowed length of 200 characters.')
        return redirect(url_for('project_details', project_id=note.project_id))
    new_comment = Comment(content=content, note_id=note.id, user_id=current_user.id)
    db.session.add(new_comment)
    db.session.commit()
    return redirect(url_for('project_details', project_id=note.project_id))

@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        return redirect(url_for('dashboard'))
    note = comment.note
    project_id = note.project_id
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('project_details', project_id=project_id))

@app.route('/add_step/<int:project_id>', methods=['GET', 'POST'])
@login_required
def add_step(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == 'POST':
        name = request.form.get('name')
        note = request.form.get('note')
        if len(note) > 200:  # Backend karakter sınırı kontrolü
            flash('Step note content exceeds the maximum allowed length of 200 characters.')
            return redirect(url_for('add_step', project_id=project.id))
        new_step = Step(name=name, note=note, project_id=project.id)
        db.session.add(new_step)
        db.session.commit()
        return redirect(url_for('project_details', project_id=project.id))
    return render_template('add_step.html', project=project)

@app.route('/toggle_step_completion/<int:project_id>/<int:step_id>', methods=['POST'])
@login_required
def toggle_step_completion(project_id, step_id):
    step = Step.query.get_or_404(step_id)
    step.completed = not step.completed
    db.session.commit()
    project = Project.query.get_or_404(project_id)
    return jsonify({'completed_steps': project.completed_steps, 'total_steps': project.total_steps})

@app.route('/delete_step/<int:project_id>/<int:step_id>', methods=['POST'])
@login_required
def delete_step(project_id, step_id):
    step = Step.query.get_or_404(step_id)
    db.session.delete(step)
    db.session.commit()
    return redirect(url_for('project_details', project_id=project_id))

@app.route('/delete_project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user.role != 'admin':
        flash("You do not have permission to delete this project.")
        return redirect(url_for('project_details', project_id=project_id))
    for step in project.steps:
        db.session.delete(step)
    db.session.delete(project)
    db.session.commit()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
