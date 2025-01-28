# app.py - الإصدار المحسن
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date, datetime, timedelta
import calendar
import os
from models import db, Student, Absence, Holiday

# إنشاء تطبيق Flask
app = Flask(__name__)

# تكوين التطبيق
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///attendance.db').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-123')

# تهيئة الإضافات مع التطبيق
db.init_app(app)

# تهيئة قاعدة البيانات
with app.app_context():
    # إنشاء جميع الجداول
    db.create_all()
    
    # إضافة بيانات أولية إذا لم تكن موجودة
    if Student.query.count() == 0:
        # إضافة بعض الطلاب للاختبار
        default_students = [
            Student(name='أحمد'),
            Student(name='محمد'),
            Student(name='فاطمة'),
            Student(name='مريم'),
            Student(name='عبد الله')
        ]
        db.session.add_all(default_students)
        db.session.commit()
        print("تم إضافة الطلاب الافتراضيين بنجاح!")
    
    # التحقق من وجود عمود absence_type
    from sqlalchemy import text
    with db.engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='absences' AND column_name='absence_type';
        """))
        
        if not result.fetchone():
            # إضافة العمود مع قيمة افتراضية 'full'
            conn.execute(text("""
                ALTER TABLE absences 
                ADD COLUMN absence_type VARCHAR(10) NOT NULL DEFAULT 'full';
            """))
            conn.commit()
            print("تم إضافة عمود absence_type بنجاح!")
        else:
            print("عمود absence_type موجود بالفعل.")

# تعريف الروابط
@app.route('/')
def index():
    students = Student.query.order_by(Student.name).all()
    holidays = Holiday.query.all()
    today = date.today()
    return render_template('index.html', students=students, holidays=holidays, today=today)

@app.route('/add_absence', methods=['POST'])
def add_absence():
    try:
        student_id = request.form['student_id']
        absence_date = request.form.get('absence_date') or date.today().isoformat()
        absence_type = request.form.get('absence_type', 'full')

        student = Student.query.get_or_404(student_id)
        absence_date = datetime.strptime(absence_date, '%Y-%m-%d').date()

        if absence_date > date.today():
            flash('لا يمكن تسجيل غياب لتاريخ مستقبلي', 'danger')
            return redirect(url_for('index'))

        # التحقق من العطلات وعطلة نهاية الأسبوع
        holiday = Holiday.query.filter_by(date=absence_date).first()
        is_weekend = absence_date.weekday() in [4, 5]  # الجمعة والسبت

        if holiday or is_weekend:
            flash('لا يمكن التسجيل في يوم عطلة', 'warning')
            return redirect(url_for('index'))

        # التحقق من عدم تكرار التسجيل
        existing = Absence.query.filter_by(
            student_id=student.id,
            date=absence_date
        ).first()

        if existing:
            flash('الغياب مسجل مسبقاً', 'warning')
            return redirect(url_for('index'))

        absence = Absence(
            date=absence_date,
            absence_type=absence_type,
            student_id=student.id
        )
        db.session.add(absence)
        db.session.commit()
        flash('تم تسجيل الغياب بنجاح', 'success')

    except ValueError:
        flash('تاريخ غير صحيح', 'danger')
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ غير متوقع', 'danger')

    return redirect(url_for('index'))

@app.route('/students', methods=['GET'])
def manage_students():
    students = Student.query.order_by(Student.name).all()
    return render_template('students.html', students=students)

@app.route('/add_student', methods=['POST'])
def add_student():
    name = request.form.get('student_name', '').strip()
    if not name:
        flash('يرجى إدخال اسم الطالب', 'danger')
        return redirect(url_for('manage_students'))

    existing = Student.query.filter_by(name=name).first()
    if existing:
        flash('الطالب موجود مسبقاً', 'warning')
        return redirect(url_for('manage_students'))

    try:
        student = Student(name=name)
        db.session.add(student)
        db.session.commit()
        flash('تم إضافة الطالب بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء الإضافة', 'danger')

    return redirect(url_for('manage_students'))

@app.route('/delete_student/<int:id>', methods=['POST'])
def delete_student(id):
    student = Student.query.get_or_404(id)
    try:
        db.session.delete(student)
        db.session.commit()
        flash(f'تم حذف الطالب {student.name} بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء الحذف', 'danger')
    return redirect(url_for('manage_students'))

@app.route('/holidays', methods=['GET', 'POST'])
def manage_holidays():
    if request.method == 'POST':
        try:
            holiday_date = request.form['holiday_date']
            description = request.form.get('description', '').strip()
            
            holiday_date = datetime.strptime(holiday_date, '%Y-%m-%d').date()
            
            existing = Holiday.query.filter_by(date=holiday_date).first()
            if existing:
                flash('هذا التاريخ مسجل مسبقاً كعطلة', 'warning')
                return redirect(url_for('manage_holidays'))
            
            holiday = Holiday(date=holiday_date, description=description)
            db.session.add(holiday)
            db.session.commit()
            flash('تم إضافة العطلة بنجاح', 'success')
        
        except ValueError:
            flash('تاريخ غير صحيح', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('حدث خطأ أثناء إضافة العطلة', 'danger')
    
    holidays = Holiday.query.order_by(Holiday.date.desc()).all()
    return render_template('holidays.html', holidays=holidays)

@app.route('/delete_holiday/<int:id>', methods=['POST'])
def delete_holiday(id):
    holiday = Holiday.query.get_or_404(id)
    try:
        db.session.delete(holiday)
        db.session.commit()
        flash('تم حذف العطلة بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء حذف العطلة', 'danger')
    return redirect(url_for('manage_holidays'))

@app.route('/statistics')
def statistics():
    today = date.today()
    current_year = today.year
    current_month = today.month
    
    # تحديد بداية ونهاية الشهر الحالي
    _, last_day = calendar.monthrange(current_year, current_month)
    month_start = date(current_year, current_month, 1)
    month_end = date(current_year, current_month, last_day)
    
    # الحصول على قائمة العطل للشهر الحالي
    month_holidays = Holiday.query.filter(
        Holiday.date.between(month_start, month_end)
    ).all()
    
    # طباعة العطل للتحقق
    print("Holidays this month:")
    for holiday in month_holidays:
        print(f"Holiday: {holiday.date}, Description: {holiday.description}")
    
    holidays = set(h.date for h in month_holidays)
    
    # حساب أيام الدراسة في الشهر الحالي
    study_days = []
    current_date = month_start
    
    # نحسب حتى نهاية الشهر (وليس فقط حتى اليوم الحالي)
    while current_date <= month_end:
        weekday = current_date.weekday()
        # 5 = السبت، 4 = الجمعة
        is_weekend = weekday in [4, 5]
        is_holiday = current_date in holidays
        
        if not is_weekend and not is_holiday:
            study_days.append(current_date)
        
        # طباعة معلومات التصحيح
        print(f"Date: {current_date.strftime('%Y-%m-%d')}, "
              f"Day: {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][weekday]}, "
              f"Is Weekend: {is_weekend}, Is Holiday: {is_holiday}")
        
        current_date += timedelta(days=1)
    
    # طباعة مجموع الأيام
    print(f"\nTotal study days found: {len(study_days)}")
    print("Study days:", [day.strftime('%Y-%m-%d') for day in study_days])
    
    # إحصائيات عامة
    total_students = Student.query.count()
    total_study_days = len(study_days)
    
    if total_study_days == 0 or total_students == 0:
        return render_template('statistics.html',
                            month_name=calendar.month_name[current_month],
                            year=current_year,
                            total_students=0,
                            total_study_days=0,
                            total_possible_attendance=0,
                            total_absence_points=0,
                            actual_attendance=0,
                            attendance_percent=0,
                            absence_percent=0,
                            student_stats=[])
    
    # حساب إجمالي نقاط الحضور الممكنة
    total_possible_attendance = total_students * total_study_days
    
    # حساب الغيابات لجميع الطلاب في الشهر الحالي
    absences = Absence.query.filter(
        Absence.date.between(month_start, month_end)
    ).all()
    
    # تنظيم الغيابات في قاموس للوصول السريع
    absence_dict = {}
    for absence in absences:
        if absence.date in study_days:  # نتجاهل الغيابات في أيام العطل
            key = (absence.student_id, absence.date)
            absence_dict[key] = absence.absence_type
    
    # حساب إجمالي نقاط الغياب
    total_absence_points = sum(
        1.0 if absence_type == 'full' else 0.5
        for absence_type in absence_dict.values()
    )
    
    # حساب نقاط الحضور الفعلية والنسب المئوية
    actual_attendance = total_possible_attendance - total_absence_points
    attendance_percent = (actual_attendance / total_possible_attendance) * 100 if total_possible_attendance > 0 else 0
    absence_percent = (total_absence_points / total_possible_attendance) * 100 if total_possible_attendance > 0 else 0
    
    # إحصائيات الطلاب
    student_stats = []
    for student in Student.query.order_by(Student.name).all():
        # حساب نقاط الغياب للطالب
        student_absences = sum(
            1.0 if absence_dict.get((student.id, day)) == 'full' else
            0.5 if absence_dict.get((student.id, day)) == 'half' else
            0
            for day in study_days
        )
        
        # حساب نسبة الحضور للطالب
        student_attendance = total_study_days - student_absences
        student_attendance_percent = (student_attendance / total_study_days) * 100 if total_study_days > 0 else 0
        
        student_stats.append({
            'name': student.name,
            'absences': student_absences,
            'attendance_percent': student_attendance_percent
        })
    
    # ترتيب الطلاب حسب نسبة الحضور (تنازلياً)
    student_stats.sort(key=lambda x: x['attendance_percent'], reverse=True)
    
    return render_template('statistics.html',
                        month_name=calendar.month_name[current_month],
                        year=current_year,
                        total_students=total_students,
                        total_study_days=total_study_days,
                        total_possible_attendance=total_possible_attendance,
                        total_absence_points=total_absence_points,
                        actual_attendance=actual_attendance,
                        attendance_percent=round(attendance_percent, 1),
                        absence_percent=round(absence_percent, 1),
                        student_stats=student_stats)

@app.route('/monthly_view')
def monthly_view():
    today = date.today()
    year = today.year
    month = today.month
    
    num_days = calendar.monthrange(year, month)[1]
    days = [date(year, month, day) for day in range(1, num_days + 1)]
    
    students = Student.query.order_by(Student.name).all()
    absences = Absence.query.filter(
        db.extract('year', Absence.date) == year,
        db.extract('month', Absence.date) == month
    ).all()
    
    absence_dict = {(ab.student_id, ab.date): ab.absence_type for ab in absences}
    
    holidays = Holiday.query.filter(
        db.extract('year', Holiday.date) == year,
        db.extract('month', Holiday.date) == month
    ).all()
    holiday_dates = {h.date for h in holidays}
    
    # إضافة عطلات نهاية الأسبوع
    for day in days:
        if day.weekday() in [4, 5]:  # الجمعة والسبت
            holiday_dates.add(day)
    
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