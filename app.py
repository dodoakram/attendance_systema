# app.py - الإصدار المحسن
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime, timedelta
import calendar
import os

# تهيئة الإضافات
db = SQLAlchemy()

def create_app():
    # إنشاء تطبيق Flask
    app = Flask(__name__)
    
    # تكوين التطبيق
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///attendance.db').replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-123')

    # تهيئة الإضافات مع التطبيق
    db.init_app(app)

    # تعريف النماذج
    class Student(db.Model):
        __tablename__ = 'students'
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(80), unique=True, nullable=False)
        absences = db.relationship('Absence', backref='student', cascade='all, delete-orphan')

        def __repr__(self):
            return f'<Student {self.name}>'

    class Absence(db.Model):
        __tablename__ = 'absences'
        id = db.Column(db.Integer, primary_key=True)
        date = db.Column(db.Date, nullable=False)
        absence_type = db.Column(db.String(10), nullable=False, default='full')
        student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

        def __repr__(self):
            return f'<Absence {self.date} {self.absence_type}>'

    class Holiday(db.Model):
        __tablename__ = 'holidays'
        id = db.Column(db.Integer, primary_key=True)
        date = db.Column(db.Date, unique=True, nullable=False)
        description = db.Column(db.String(100))

        def __repr__(self):
            return f'<Holiday {self.date}>'

    # إضافة بيانات أولية
    def add_initial_data():
        if not Student.query.first():
            default_students = [
                Student(name='أحمد'),
                Student(name='محمد'),
                Student(name='علي')
            ]
            db.session.add_all(default_students)
            db.session.commit()

    # إنشاء الجداول عند التشغيل الأول
    with app.app_context():
        db.create_all()
        add_initial_data()

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
        
        # تحديد بداية ونهاية الفصل الدراسي
        if today.month >= 9:  # الفصل الأول
            start_date = date(today.year, 9, 1)
            end_date = date(today.year + 1, 1, 31)
        else:  # الفصل الثاني
            start_date = date(today.year, 2, 1)
            end_date = date(today.year, 6, 30)
        
        # حساب أيام الدراسة
        all_days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        holidays = [h.date for h in Holiday.query.all()]
        study_days = [day for day in all_days if day.weekday() not in [4, 5] and day not in holidays]
        
        # حساب الإحصائيات
        total_students = Student.query.count()
        total_study_days = len(study_days)
        total_possible_attendance = total_students * total_study_days  # كل يوم = نقطة واحدة
        
        # حساب الغيابات في الفترة الدراسية فقط
        all_absences = Absence.query.filter(
            Absence.date.between(start_date, end_date)
        ).all()
        
        # حساب نقاط الغياب (يوم كامل = نقطة، نصف يوم = 0.5 نقطة)
        total_absence_points = sum(
            1 if ab.absence_type == 'full' else 0.5 
            for ab in all_absences 
            if ab.date in study_days
        )
        
        actual_attendance = total_possible_attendance - total_absence_points
        attendance_percent = (actual_attendance / total_possible_attendance * 100) if total_possible_attendance > 0 else 0
        absence_percent = 100 - attendance_percent
        
        # إحصائيات الطلاب
        student_stats = []
        for student in Student.query.all():
            # حساب غيابات الطالب في الفترة الدراسية فقط
            student_absences = Absence.query.filter(
                Absence.student_id == student.id,
                Absence.date.between(start_date, end_date)
            ).all()
            
            # حساب نقاط الغياب للطالب
            student_absence_points = sum(
                1 if ab.absence_type == 'full' else 0.5 
                for ab in student_absences 
                if ab.date in study_days
            )
            
            # حساب نسبة الحضور للطالب
            student_attendance_percent = (
                (total_study_days - student_absence_points) / total_study_days * 100
            ) if total_study_days > 0 else 0
            
            student_stats.append({
                'name': student.name,
                'absences': student_absence_points,
                'attendance_percent': student_attendance_percent
            })
        
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

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
