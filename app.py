# app.py - الإصدار المحسن
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date, datetime, timedelta
import calendar
import os
from models import db, Student, Absence, Holiday
from sqlalchemy import text
import pandas as pd
from werkzeug.utils import secure_filename

# تكوين مجلد التحميلات
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# إنشاء تطبيق Flask
app = Flask(__name__)

# تكوين التطبيق
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///attendance.db').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-123')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# إنشاء مجلد التحميلات إذا لم يكن موجوداً
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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
    
    # التحقق من وجود عمود absence_type وإضافته إذا لم يكن موجوداً
    try:
        with db.engine.connect() as conn:
            conn.execute(text("SELECT absence_type FROM absences LIMIT 1"))
    except:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE absences ADD COLUMN absence_type VARCHAR(10) NOT NULL DEFAULT 'full'"))
            db.session.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_valid_excel(file):
    # Excel file signatures
    xlsx_signature = b'PK\x03\x04'  # ZIP format (used by .xlsx)
    xls_signature = b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'  # Compound File Binary Format (used by .xls)
    
    # Read the first few bytes
    file_start = file.read(8)
    file.seek(0)  # Reset file pointer
    
    # Check if it matches any Excel signature
    return file_start.startswith(xlsx_signature) or file_start.startswith(xls_signature)

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

@app.route('/manage_students')
def manage_students():
    students = Student.query.order_by(Student.name).all()
    return render_template('manage_students.html', students=students)

@app.route('/add_student', methods=['POST'])
def add_student():
    try:
        # الحصول على الاسم واللقب من النموذج
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        
        # دمج اللقب والاسم (اللقب أولاً)
        full_name = f"{last_name} {first_name}".strip()
        
        if not full_name:
            flash('يجب إدخال الاسم واللقب', 'error')
            return redirect(url_for('manage_students'))
        
        # التحقق من عدم وجود الطالب مسبقاً
        if Student.query.filter_by(name=full_name).first():
            flash('هذا الطالب موجود مسبقاً', 'error')
            return redirect(url_for('manage_students'))
        
        # إضافة الطالب الجديد
        student = Student(name=full_name)
        db.session.add(student)
        db.session.commit()
        flash('تم إضافة الطالب بنجاح', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء إضافة الطالب', 'error')
    
    return redirect(url_for('manage_students'))

@app.route('/delete_student/<int:id>')
def delete_student(id):
    try:
        student = Student.query.get_or_404(id)
        # حذف جميع الغيابات المرتبطة بالطالب
        Absence.query.filter_by(student_id=id).delete()
        # حذف الطالب
        db.session.delete(student)
        db.session.commit()
        flash('تم حذف الطالب بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash('حدث خطأ أثناء حذف الطالب', 'error')
    
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
@app.route('/statistics/<int:year>/<int:month>')
def statistics(year=None, month=None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    
    # حساب الشهر السابق والتالي
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
        
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    # تحديد بداية ونهاية الشهر
    _, last_day = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)
    
    # الحصول على قائمة العطل للشهر
    month_holidays = Holiday.query.filter(
        Holiday.date.between(month_start, month_end)
    ).all()
    
    holidays = set(h.date for h in month_holidays)
    
    # حساب أيام الدراسة في الشهر
    study_days = []
    current_date = month_start
    
    while current_date <= month_end:
        weekday = current_date.weekday()
        is_weekend = weekday in [4, 5]
        is_holiday = current_date in holidays
        
        if not is_weekend and not is_holiday:
            study_days.append(current_date)
        
        current_date += timedelta(days=1)
    
    # إحصائيات عامة
    total_students = Student.query.count()
    total_study_days = len(study_days)
    
    if total_study_days == 0 or total_students == 0:
        return render_template('statistics.html',
                            month_name=calendar.month_name[month],
                            year=year,
                            prev_month=prev_month,
                            prev_year=prev_year,
                            next_month=next_month,
                            next_year=next_year,
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
    
    # حساب الغيابات لجميع الطلاب في الشهر
    absences = Absence.query.filter(
        Absence.date.between(month_start, month_end)
    ).all()
    
    # تنظيم الغيابات في قاموس للوصول السريع
    absence_dict = {}
    for absence in absences:
        if absence.date in study_days:
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
        student_absences = sum(
            1.0 if absence_dict.get((student.id, day)) == 'full' else
            0.5 if absence_dict.get((student.id, day)) == 'half' else
            0
            for day in study_days
        )
        
        student_attendance = total_study_days - student_absences
        student_attendance_percent = (student_attendance / total_study_days) * 100 if total_study_days > 0 else 0
        
        student_stats.append({
            'name': student.name,
            'absences': student_absences,
            'attendance_percent': student_attendance_percent
        })
    
    student_stats.sort(key=lambda x: x['attendance_percent'], reverse=True)
    
    return render_template('statistics.html',
                        month_name=calendar.month_name[month],
                        year=year,
                        prev_month=prev_month,
                        prev_year=prev_year,
                        next_month=next_month,
                        next_year=next_year,
                        total_students=total_students,
                        total_study_days=total_study_days,
                        total_possible_attendance=total_possible_attendance,
                        total_absence_points=total_absence_points,
                        actual_attendance=actual_attendance,
                        attendance_percent=round(attendance_percent, 1),
                        absence_percent=round(absence_percent, 1),
                        student_stats=student_stats)

@app.route('/monthly_view')
@app.route('/monthly_view/<int:year>/<int:month>')
def monthly_view(year=None, month=None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    
    # حساب الشهر السابق والتالي
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
        
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
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
    
    # حساب إحصائيات الشهر
    total_students = len(students)
    total_study_days = len([d for d in days if d not in holiday_dates])
    total_absences = sum(1.0 if v == 'full' else 0.5 for v in absence_dict.values())
    attendance_rate = ((total_students * total_study_days) - total_absences) / (total_students * total_study_days) * 100 if total_students * total_study_days > 0 else 0
    
    return render_template('monthly_view.html',
                           students=students,
                           days=days,
                           absences=absence_dict,
                           holidays=holiday_dates,
                           weekday_names=weekday_names,
                           month_name=calendar.month_name[month],
                           year=year,
                           prev_month=prev_month,
                           prev_year=prev_year,
                           next_month=next_month,
                           next_year=next_year,
                           total_study_days=total_study_days,
                           total_absences=total_absences,
                           attendance_rate=round(attendance_rate, 1))

@app.route('/import_students', methods=['POST'])
def import_students():
    if 'excel_file' not in request.files:
        flash('لم يتم تحديد ملف', 'error')
        return redirect(url_for('manage_students'))
    
    file = request.files['excel_file']
    if file.filename == '':
        flash('لم يتم اختيار ملف', 'error')
        return redirect(url_for('manage_students'))
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('يجب أن يكون الملف بصيغة Excel (.xlsx أو .xls)', 'error')
        return redirect(url_for('manage_students'))
    
    # التحقق من صحة ملف Excel
    if not is_valid_excel(file):
        flash('الملف ليس ملف Excel صالح. تأكد من أن الملف بتنسيق .xlsx أو .xls', 'error')
        return redirect(url_for('manage_students'))
    
    try:
        # حفظ الملف مؤقتاً
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # محاولة قراءة الملف كـ Excel
            if filename.endswith('.xlsx'):
                df = pd.read_excel(filepath, engine='openpyxl')
            else:  # .xls
                df = pd.read_excel(filepath, engine='xlrd')
            
            # التحقق من وجود الأعمدة المطلوبة
            required_columns = ['الاسم', 'اللقب']
            if not all(col in df.columns for col in required_columns):
                missing_cols = [col for col in required_columns if col not in df.columns]
                flash(f'الأعمدة المطلوبة غير موجودة: {", ".join(missing_cols)}', 'error')
                return redirect(url_for('manage_students'))
            
            # دمج اللقب والاسم وإضافة الطلاب
            success_count = 0
            error_rows = []
            
            for index, row in df.iterrows():
                try:
                    # التعامل مع القيم الفارغة
                    first_name = str(row['الاسم']).strip() if pd.notna(row['الاسم']) else ''
                    last_name = str(row['اللقب']).strip() if pd.notna(row['اللقب']) else ''
                    
                    # وضع اللقب أولاً ثم الاسم
                    full_name = f"{last_name} {first_name}".strip()
                    if full_name:  # تأكد من أن الاسم ليس فارغاً
                        # التحقق من عدم وجود الطالب مسبقاً
                        if not Student.query.filter_by(name=full_name).first():
                            student = Student(name=full_name)
                            db.session.add(student)
                            success_count += 1
                except Exception as row_error:
                    error_rows.append(index + 2)  # +2 لأن Excel يبدأ من 1 والعنوان في الصف الأول
            
            if error_rows:
                flash(f'تم تخطي الصفوف التالية بسبب أخطاء: {", ".join(map(str, error_rows))}', 'warning')
            
            if success_count > 0:
                db.session.commit()
                flash(f'تم استيراد {success_count} طالب بنجاح', 'success')
            else:
                flash('لم يتم استيراد أي طالب. تأكد من تنسيق الملف وعدم تكرار الأسماء.', 'warning')
            
        except pd.errors.EmptyDataError:
            flash('الملف فارغ أو لا يحتوي على بيانات', 'error')
        except Exception as e:
            flash(f'حدث خطأ أثناء قراءة الملف: {str(e)}', 'error')
        
    except Exception as e:
        flash(f'حدث خطأ أثناء معالجة الملف: {str(e)}', 'error')
    
    finally:
        # تأكد من حذف الملف المؤقت
        if 'filepath' in locals() and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
    
    return redirect(url_for('manage_students'))

@app.route('/edit_absence/<int:student_id>/<date>/<new_type>')
def edit_absence(student_id, date, new_type):
    try:
        # تحويل التاريخ من النص إلى كائن تاريخ
        absence_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # البحث عن الغياب
        absence = Absence.query.filter_by(
            student_id=student_id,
            date=absence_date
        ).first()
        
        if absence:
            # تحديث نوع الغياب
            absence.absence_type = new_type
            db.session.commit()
            flash('تم تعديل الغياب بنجاح', 'success')
        else:
            flash('لم يتم العثور على الغياب', 'error')
            
    except Exception as e:
        flash(f'حدث خطأ: {str(e)}', 'error')
        
    # العودة إلى الصفحة الرئيسية
    return redirect(url_for('index'))

@app.route('/delete_absence/<int:student_id>/<date>')
def delete_absence(student_id, date):
    try:
        # تحويل التاريخ من النص إلى كائن تاريخ
        absence_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # البحث عن الغياب وحذفه
        absence = Absence.query.filter_by(
            student_id=student_id,
            date=absence_date
        ).first()
        
        if absence:
            db.session.delete(absence)
            db.session.commit()
            flash('تم حذف الغياب بنجاح', 'success')
        else:
            flash('لم يتم العثور على الغياب', 'error')
            
    except Exception as e:
        flash(f'حدث خطأ: {str(e)}', 'error')
        
    # العودة إلى الصفحة الرئيسية
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)