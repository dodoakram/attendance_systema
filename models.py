from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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
