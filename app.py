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
    absence_type = db.Column(db.String(10), nullable=False, default='full')  # 'full' أو 'half'
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
    today = date.today()
    return render_template('index.html', students=students, holidays=holidays, today=today)

@app.route('/add_absence', methods=['POST'])
def add_absence():
    student_id = request.form.get('student_id')
    absence_date = request.form.get('absence_date')
    absence_type = request.form.get('absence_type', 'full')

    if absence_type not in ['full', 'half']:
        flash('نوع الغياب غير صحيح', 'danger')
        return redirect(url_for('index'))

    student = Student.query.get(student_id)
    
    if student:
        try:
            if absence_date:
                absence_date = date.fromisoformat(absence_date)
            else:
                absence_date = date.today()
            
            holiday = Holiday.query.filter_by(date=absence_date).first()
            is_weekend = absence_date.weekday() in [4, 5]
            
            if not holiday and not is_weekend:
                existing_absence = Absence.query.filter_by(
                    student_id=student.id,
                    date=absence_date
                ).first()
                
                if not existing_absence:
                    absence = Absence(
                        student_id=student.id,
                        date=absence_date,
                        absence_type=absence_type
                    )
                    db.session.add(absence)
                    db.session.commit()
                    flash('تم تسجيل الغياب بنجاح', 'success')
                else:
                    flash('الغياب مسجل مسبقاً لهذا اليوم', 'warning')
            else:
                flash('لا يمكن تسجيل الغياب في يوم عطلة', 'warning')
        except ValueError:
            flash('تاريخ غير صحيح', 'danger')
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
            flash('تم إضافة العطلة بنجاح', 'success')
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
            flash('Student added successfully', 'success')
        else:
            flash('Student already recorded', 'danger')
    return redirect(url_for('manage_students'))

@app.route('/delete_student/<int:id>', methods=['POST'])
def delete_student(id):
    try:
        student = Student.query.get_or_404(id)
        name = student.name
        db.session.delete(student)
        db.session.commit()
        flash(f'تم حذف الطالب {name} بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء حذف الطالب', 'danger')
    return redirect(url_for('manage_students'))

@app.route('/delete_holiday/<int:id>', methods=['POST'])
def delete_holiday(id):
    try:
        holiday = Holiday.query.get_or_404(id)
        date = holiday.date
        db.session.delete(holiday)
        db.session.commit()
        flash(f'تم حذف العطلة بتاريخ {date.strftime("%Y-%m-%d")} بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء حذف العطلة', 'danger')
    return redirect(url_for('manage_holidays'))

@app.route('/statistics')
def statistics():
    # تواريخ بداية ونهاية الفصل الدراسي (ديناميكية)
    today = date.today()
    if today.month >= 9:  # إذا كنا في الفصل الأول
        start_date = date(today.year, 9, 1)
        end_date = date(today.year + 1, 1, 31)
    else:  # إذا كنا في الفصل الثاني
        start_date = date(today.year, 2, 1)
        end_date = date(today.year, 6, 30)
    
    # حساب أيام الدراسة (بدون عطلات نهاية الأسبوع والعطل الرسمية)
    all_days = []
    current_day = start_date
    while current_day <= end_date:
        all_days.append(current_day)
        current_day += timedelta(days=1)
    
    # استبعاد العطلات الرسمية
    holidays = [h.date for h in Holiday.query.all()]
    
    # استبعاد الجمعة (4) والسبت (5)
    study_days = [day for day in all_days 
                  if day.weekday() not in [4, 5] # الجمعة والسبت
                  and day not in holidays]
    
    total_study_days = len(study_days)
    
    # عدد التلاميذ
    total_students = Student.query.count()
    
    # الحضور الكلي (يوم كامل = 2 نقطة، نصف يوم = 1 نقطة)
    total_possible_attendance = total_students * total_study_days * 2
    
    # حساب الغيابات (يوم كامل = 2 نقطة، نصف يوم = 1 نقطة)
    all_absences = Absence.query.all()
    total_absence_points = sum(
        2 if ab.absence_type == 'full' else 1 
        for ab in all_absences
        if ab.date in study_days # تأكد أن الغياب في أيام الدراسة
    )
    
    # الحضور الفعلي
    actual_attendance = total_possible_attendance - total_absence_points
    
    # النسب المئوية
    if total_possible_attendance > 0:
        attendance_percent = (actual_attendance / total_possible_attendance) * 100
        absence_percent = (total_absence_points / total_possible_attendance) * 100
    else:
        attendance_percent = 0
        absence_percent = 0
    
    # إحصائيات إضافية
    students = Student.query.all()
    student_stats = []
    for student in students:
        student_absences = Absence.query.filter_by(student_id=student.id).all()
        student_absence_points = sum(
            2 if ab.absence_type == 'full' else 1 
            for ab in student_absences
            if ab.date in study_days
        )
        student_possible = total_study_days * 2
        student_actual = student_possible - student_absence_points
        student_stats.append({
            'name': student.name,
            'absences': student_absence_points,
            'attendance_percent': (student_actual / student_possible * 100) if student_possible > 0 else 0
        })
    
    return render_template(
        'statistics.html',
        total_students=total_students,
        total_study_days=total_study_days,
        total_possible_attendance=total_possible_attendance,
        total_absence_points=total_absence_points,
        actual_attendance=actual_attendance,
        attendance_percent=attendance_percent,
        absence_percent=absence_percent,
        student_stats=student_stats
    )
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
    
    # Add weekends (Friday and Saturday) to holidays
    for day in days:
        # In Python, weekday() returns 0-6 where 0 is Monday and 6 is Sunday
        # 4 is Friday, 5 is Saturday
        if day.weekday() in [4, 5]:  # Friday or Saturday
            holiday_dates.add(day)
    
    # Get weekday names in Arabic
    weekday_names = {
        0: 'الإثنين',
        1: 'الثلاثاء',
        2: 'الأربعاء',
        3: 'الخميس',
        4: 'الجمعة',
        5: 'السبت',
        6: 'الأحد'
    }
    
    return render_template('monthly_view.html',
                         students=students,
                         days=days,
                         absences=absence_dict,
                         holidays=holiday_dates,
                         weekday_names=weekday_names,
                         month_name=calendar.month_name[month],
                         year=year)

if __name__ == '__main__':
    app.run(debug=True)
