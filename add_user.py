from app import app, db, User

def add_user(username, password, role):
    with app.app_context():
        existing_user = User.query.filter_by(username=username).first()
        if not existing_user:
            new_user = User(username=username, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            print(f'Yeni {role} başarıyla eklendi: {username}')
        else:
            print("Kullanıcı zaten mevcut.")

if __name__ == '__main__':
    # Kullanıcı ve yönetici eklemek için örnek kullanımlar:
    add_user('user1', 'password1', 'user')
    add_user('admin1', 'password1', 'admin')
    add_user('admin2', 'password1', 'admin')
    add_user('user2', 'password1', 'user')
