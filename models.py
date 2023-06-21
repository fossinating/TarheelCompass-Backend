# from flask_security import UserMixin, RoleMixin
from sqlalchemy import Table, Float, DateTime, Column, Integer, \
    String, Text, UniqueConstraint, and_
from sqlalchemy.orm import relationship, mapped_column, foreign, remote

from database import Base

schedule_instructor_join_table = Table("schedule_instructor_join_table",
                                       Base.metadata,
                                       Column("instructor_id", Integer, primary_key=True),
                                       Column("schedule_id", Integer, primary_key=True),
                                       UniqueConstraint("instructor_id", "schedule_id"), )


class Instructor(Base):
    __tablename__ = "instructor"
    id = mapped_column(Integer, primary_key=True)
    instructor_type = mapped_column(String(6))
    name = mapped_column(Text)


class Class(Base):
    __tablename__ = "class"
    course_code = mapped_column(String(10))
    course = relationship("Course", primaryjoin="foreign(Course.code) == Class.course_code")
    section = mapped_column(String(4))
    number = mapped_column(Integer, primary_key=True)
    title = mapped_column(Text)
    component = mapped_column(Text)
    topics = mapped_column(Text)
    term = mapped_column(String(8), primary_key=True)
    hours = mapped_column(Float)
    meeting_dates = mapped_column(String(30))
    instruction_type = mapped_column(String(35))
    schedules = relationship(
        "ClassSchedule",
        primaryjoin="and_(Class.number == foreign(ClassSchedule.class_number), Class.term == foreign(ClassSchedule.term))")
    enrollment_cap = mapped_column(Integer)
    enrollment_total = mapped_column(Integer)
    waitlist_cap = mapped_column(Integer)
    waitlist_total = mapped_column(Integer)
    min_enrollment = mapped_column(Integer)
    attributes = mapped_column(Text)
    combined_section_id = mapped_column(Text)
    equivalents = mapped_column(Text)
    last_updated_at = mapped_column(DateTime)
    last_updated_from = mapped_column(String(7))

    def to_json(self):
        attributes = {}
        for attribute in self.course.attrs:
            attributes[attribute.label] = attribute.value

        return {
            "course_code": self.course_code,
            "section": self.section,
            "title": self.title,
            "description": self.course.description,
            "schedules": [schedule.to_json() for schedule in self.schedules],
            "number": self.number,
            "component": self.component,
            "term": self.term,
            "credits": self.course.credits,
            "instruction_type": self.instruction_type,
            "enrollment_cap": self.enrollment_cap,
            "enrollment_total": self.enrollment_total,
            "waitlist_cap": self.waitlist_cap,
            "waitlist_total": self.waitlist_total,
            "min_enrollment": self.min_enrollment,
            "attributes": attributes,
            "last_updated_at": self.last_updated_at,
            "last_updated_from": self.last_updated_from
        }

    def get_timeslots(self):
        timeslots = []

        def convert_time(time_string):
            time_parts = time_string.strip().split(":")
            hours = int(time_parts[0])
            minutes = int(time_parts[1].split(" ")[0])
            return (hours - 8) * int(60 / 5) + int(minutes / 5) + 2

        for schedule in self.schedules:
            scheduled_days = []
            readable_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
            days = ["M", "Tu", "W", "Th", "F"]
            for i in range(len(days)):
                if days[i] in schedule.days:
                    scheduled_days.append(readable_days[i])
            times = schedule.time.split("-")
            start_time = 140
            end_time = 146
            if len(times) == 2:
                start_time = convert_time(times[0])
                end_time = convert_time(times[1])

            for day in scheduled_days:
                timeslots.append({
                    "day": day,
                    "start_time": start_time,
                    "end_time": end_time,
                    "schedule": schedule
                })

        return timeslots


class ClassSchedule(Base):
    __tablename__ = "class_schedule"
    id = mapped_column(Integer, primary_key=True)
    location = mapped_column(Text)
    instructors = relationship(
        "Instructor",
        secondary=schedule_instructor_join_table,
        primaryjoin="ClassSchedule.id == foreign(schedule_instructor_join_table.c.schedule_id)",
        secondaryjoin="foreign(schedule_instructor_join_table.c.instructor_id) == foreign(Instructor.id)")
    days = mapped_column(String(10))
    time = mapped_column(String(15))
    class_number = mapped_column(Integer, primary_key=True)
    term = mapped_column(String(8), primary_key=True)
    #__table_args__ = (ForeignKeyConstraint((class_number, term), (Class.class_number, Class.term)), {})

    def instructors_string(self):
        return "; ".join([instructor.name for instructor in self.instructors])

    def to_json(self):
        return {
            "location": self.location,
            "instructors": [instructor.name for instructor in self.instructors],
            "days": self.days,
            "time": self.time
        }


class CourseAttribute(Base):
    __tablename__ = "course_attributes"
    id = mapped_column(Integer, primary_key=True)
    label = mapped_column(Text)
    value = mapped_column(Text)
    parent_course_code = mapped_column(String(10))


class Course(Base):
    __tablename__ = "course"
    code = mapped_column(String(10), primary_key=True)
    title = mapped_column(Text)
    credits = mapped_column(String(20))
    description = mapped_column(Text)
    attrs = relationship("CourseAttribute", primaryjoin="foreign(CourseAttribute.parent_course_code) == Course.code")
    last_updated_at = mapped_column(DateTime)
    last_updated_from = mapped_column(String(7))
