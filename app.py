from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import date
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///attendance.db').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-123')
db = SQLAlchemy(app)

# ---- النماذج ----
class Student(db.Model):
    __tablename__ = 'students'  # تغيير اسم الجدول
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    absences = db.relationship('Absence', backref='student', lazy=True)

class Absence(db.Model):
    __tablename__ = 'absences'  # تغيير اسم الجدول
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

class Holiday(db.Model):
    __tablename__ = 'holidays'  # تغيير اسم الجدول
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    description = db.Column(db.String(100))

# إنشاء جداول قاعدة البيانات
def create_tables():
    with app.app_context():
        db.create_all()
        
        # إضافة بيانات أولية إذا كانت قاعدة البيانات فارغة
        if not Student.query.first():
            default_students = [
                Student(name='أحمد'),
                Student(name='محمد'),
                Student(name='علي')
            ]
            db.session.add_all(default_students)
            db.session.commit()

# استدعاء إنشاء الجداول
create_tables()

# ---- الروابط ----
@app.route('/')
def index():
    students = Student.query.all()
    holidays = Holiday.query.all()
    return render_template('index.html', students=students, holidays=holidays)

@app.route('/add_absence', methods=['POST'])
def add_absence():
    student_id = request.form.get('student_id')
    student = Student.query.get(student_id)
    
    if student:
        today = date.today()
        if not Holiday.query.filter_by(date=today).first():
            absence = Absence(student_id=student.id, date=today)
            db.session.add(absence)
            db.session.commit()
            flash('تم تسجيل الغياب بنجاح', 'success')
        else:
            flash('لا يمكن التسجيل في يوم عطلة', 'warning')
    return redirect(url_for('index'))

@app.route('/holidays', methods=['GET', 'POST'])
def manage_holidays():
    if request.method == 'POST':
        holiday_date = date.fromisoformat(request.form['date'])
        description = request.form['description']
        
        if not Holiday.query.filter_by(date=holiday_date).first():
            holiday = Holiday(date=holiday_date, description=description)
            db.session.add(holiday)
            db.session.commit()
            flash('تمت إضافة العطلة', 'success')
        else:
            flash('هذا التاريخ مسجل مسبقاً', 'danger')
    
    holidays = Holiday.query.order_by(Holiday.date.desc()).all()
    return render_template('holidays.html', holidays=holidays)

@app.route('/students', methods=['GET', 'POST'])
def manage_students():
    students = Student.query.all()
    return render_template('students.html', students=students)

@app.route('/add_student', methods=['POST'])
def add_student():
    name = request.form.get('student_name')
    if name:
        if not Student.query.filter_by(name=name).first():
            new_student = Student(name=name)
            db.session.add(new_student)
            db.session.commit()
            flash('تمت إضافة الطالب بنجاح', 'success')
        else:
            flash('الطالب مسجل مسبقاً', 'danger')
    return redirect(url_for('manage_students'))

@app.route('/delete_student/<int:id>', methods=['POST'])
def delete_student(id):
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    flash('تم حذف الطالب بنجاح', 'success')
    return redirect(url_for('manage_students'))

@app.cli.command('init')
def init_db():
    """تهيئة البيانات الأولية"""
    db.create_all()
    initial_students = ['أحمد', 'محمد', 'فاطمة', 'علي', 'مريم']
    for name in initial_students:
        if not Student.query.filter_by(name=name).first():
            db.session.add(Student(name=name))
    db.session.commit()
    print('تم تهيئة البيانات بنجاح!')

if __name__ == '__main__':
    app.run()
