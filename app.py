from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime, timedelta
import os
import calendar

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///attendance.db').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-123')
db = SQLAlchemy(app)

# ---- Models ----
class Student(db.Model):
    __tablename__ = 'students'  # Change table name
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    absences = db.relationship('Absence', backref='student', lazy=True, cascade='all, delete-orphan')

class Absence(db.Model):
    __tablename__ = 'absences'  # Change table name
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

class Holiday(db.Model):
    __tablename__ = 'holidays'  # Change table name
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    description = db.Column(db.String(100))

# Create database tables
def create_tables():
    with app.app_context():
        db.create_all()
        
        # Add initial data if database is empty
        if not Student.query.first():
            default_students = [
                Student(name='Ahmed'),
                Student(name='Mohammed'),
                Student(name='Ali')
            ]
            db.session.add_all(default_students)
            db.session.commit()

# Call create tables function
create_tables()

# ---- Routes ----
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
            flash('Absence recorded successfully', 'success')
        else:
            flash('Cannot record absence on a holiday', 'warning')
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
            flash('Holiday added successfully', 'success')
        else:
            flash('Date already recorded', 'danger')
    
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
            flash('Student added successfully', 'success')
        else:
            flash('Student already recorded', 'danger')
    return redirect(url_for('manage_students'))

@app.route('/delete_student/<int:id>', methods=['POST'])
def delete_student(id):
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully', 'success')
    return redirect(url_for('manage_students'))

@app.route('/monthly_view')
def monthly_view():
    # Get the current year and month
    today = date.today()
    year = today.year
    month = today.month
    
    # Get all days in the month
    num_days = calendar.monthrange(year, month)[1]
    days = [date(year, month, day) for day in range(1, num_days + 1)]
    
    # Get all students
    students = Student.query.all()
    
    # Get all absences for this month
    absences = Absence.query.filter(
        db.extract('year', Absence.date) == year,
        db.extract('month', Absence.date) == month
    ).all()
    
    # Create absence dictionary for quick lookup
    absence_dict = {}
    for absence in absences:
        key = (absence.student_id, absence.date)
        absence_dict[key] = True
    
    # Get all holidays
    holidays = Holiday.query.filter(
        db.extract('year', Holiday.date) == year,
        db.extract('month', Holiday.date) == month
    ).all()
    holiday_dates = {h.date for h in holidays}
    
    return render_template('monthly_view.html',
                         students=students,
                         days=days,
                         absences=absence_dict,
                         holidays=holiday_dates,
                         month_name=calendar.month_name[month],
                         year=year)

@app.cli.command('init')
def init_db():
    """Initialize initial data"""
    db.create_all()
    initial_students = ['Ahmed', 'Mohammed', 'Fatima', 'Ali', 'Maryam']
    for name in initial_students:
        if not Student.query.filter_by(name=name).first():
            db.session.add(Student(name=name))
    db.session.commit()
    print('Initial data initialized successfully!')

@app.cli.command('reset-db')
def reset_db():
    """Reset the database"""
    with app.app_context():
        # Drop all tables
        db.drop_all()
        # Create all tables
        db.create_all()
        print('Database has been reset successfully!')

if __name__ == '__main__':
    app.run(debug=True)
