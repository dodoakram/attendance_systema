from app import create_app, db
from flask_migrate import Migrate

app = create_app()
migrate = Migrate(app, db)

if __name__ == '__main__':
    with app.app_context():
        # إنشاء جميع الجداول إذا لم تكن موجودة
        db.create_all()
        
        # إضافة عمود absence_type إذا لم يكن موجوداً
        from sqlalchemy import text
        with db.engine.connect() as conn:
            # التحقق مما إذا كان العمود موجوداً
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
