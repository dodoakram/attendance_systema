from app import app, db
from models import Student, Absence, Holiday

def init_database():
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

if __name__ == '__main__':
    init_database()
