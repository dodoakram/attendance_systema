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
    total_students = Student.query.count()
    total_possible_attendance = total_students * total_study_days * 2
    
    # حساب إحصائيات كل طالب
    student_stats = []
    total_absence_points = 0
    
    for student in Student.query.all():
        absences = Absence.query.filter_by(student_id=student.id).all()
        absence_points = sum(2 if a.absence_type == 'full' else 1 for a in absences)
        total_absence_points += absence_points
        
        if total_study_days > 0:
            attendance_percent = ((total_study_days * 2 - absence_points) / (total_study_days * 2)) * 100
        else:
            attendance_percent = 100
            
        student_stats.append({
            'name': student.name,
            'absences': absence_points,
            'attendance_percent': attendance_percent
        })
    
    actual_attendance = total_possible_attendance - total_absence_points
    
    if total_possible_attendance > 0:
        attendance_percent = (actual_attendance / total_possible_attendance) * 100
        absence_percent = (total_absence_points / total_possible_attendance) * 100
    else:
        attendance_percent = 100
        absence_percent = 0
    
    return render_template('statistics.html',
                         total_students=total_students,
                         total_study_days=total_study_days,
                         total_possible_attendance=total_possible_attendance,
                         total_absence_points=total_absence_points,
                         actual_attendance=actual_attendance,
                         attendance_percent=attendance_percent,
                         absence_percent=absence_percent,
                         student_stats=student_stats)

@app.route('/monthly_view')
def monthly_view():
    # Get current year and month
    year = int(request.args.get('year', date.today().year))
    month = int(request.args.get('month', date.today().month))
    
    # Get all days in the month
    num_days = calendar.monthrange(year, month)[1]
    days = [date(year, month, day) for day in range(1, num_days + 1)]
    
    # Get holidays
    holidays = Holiday.query.filter(
        Holiday.date >= date(year, month, 1),
        Holiday.date <= date(year, month, num_days)
    ).all()
    holiday_dates = [h.date for h in holidays]
    
    # Get students and their absences
    students = Student.query.all()
    absences = {}
    for student in students:
        month_absences = Absence.query.filter(
            Absence.student_id == student.id,
            Absence.date >= date(year, month, 1),
            Absence.date <= date(year, month, num_days)
        ).all()
        for absence in month_absences:
            absences[(student.id, absence.date)] = absence
    
    # Arabic weekday names
    weekday_names = {
        0: 'الاثنين',
        1: 'الثلاثاء',
        2: 'الأربعاء',
        3: 'الخميس',
        4: 'الجمعة',
        5: 'السبت',
        6: 'الأحد'
    }
    
    # Arabic month names
    month_names = {
        1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
        5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
        9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
    }
    
    return render_template('monthly_view.html',
                         students=students,
                         days=days,
                         absences=absences,
                         holidays=holiday_dates,
                         weekday_names=weekday_names,
                         month_name=month_names[month],
                         year=year)

if __name__ == '__main__':
    app.run(debug=True)
