from typing import List, Optional

from sqlalchemy import Table, Float, DateTime, Column, Integer, \
    String, ForeignKey, Text, ForeignKeyConstraint, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column

from common.database import Base

schedule_instructor_join_table = Table("schedule_instructor_join_table",
                                       Base.metadata,
                                       Column("join_id", Integer, primary_key=True),
                                       Column("instructor_id", ForeignKey("instructor.id")),
                                       Column("schedule_id", ForeignKey("class_schedule.id")),
                                       UniqueConstraint("instructor_id", "schedule_id"), )


class Instructor(Base):
    __tablename__ = "instructor"
    id: Mapped[int] = mapped_column(primary_key=True)
    instructor_type: Mapped[Optional[str]] = mapped_column(String(6))
    name: Mapped[Optional[str]] = mapped_column(Text)


class Class(Base):
    __tablename__ = "class"
    course_id: Mapped[str] = mapped_column(String(10), ForeignKey("course.code"))
    # AAAD 51
    course: Mapped["Course"] = relationship("Course")
    class_section: Mapped[str] = mapped_column(String(4))
    # 001
    class_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 13904 (Registration number)
    title: Mapped[str] = mapped_column(Text)
    # FYS MASQS OF BLACKNESS
    component: Mapped[Optional[str]] = mapped_column(Text)
    # Lecture
    topics: Mapped[Optional[str]] = mapped_column(Text)
    # A (I really don't know what this is for tbh)
    term: Mapped[str] = mapped_column(String(20), primary_key=True)
    # SPRING 2024
    units: Mapped[str] = mapped_column(String(40))
    # 3
    meeting_dates: Mapped[Optional[str]] = mapped_column(String(30))
    # Not provided in pdf and thus must be optional
    instruction_type: Mapped[str] = mapped_column(String)
    schedules: Mapped[List["ClassSchedule"]] = relationship("ClassSchedule", cascade="all, delete", passive_deletes=True)
    enrollment_cap: Mapped[Optional[int]] = mapped_column(Integer)
    enrollment_total: Mapped[int] = mapped_column(Integer)
    waitlist_cap: Mapped[Optional[int]] = mapped_column(Integer)
    waitlist_total: Mapped[Optional[int]] = mapped_column(Integer)
    min_enrollment: Mapped[Optional[int]] = mapped_column(Integer)
    combined_section_id: Mapped[Optional[str]] = mapped_column(Text)
    equivalents: Mapped[Optional[str]] = mapped_column(Text)
    reserve_capacities: Mapped[Optional[List["ClassReserveCapacity"]]] = relationship("ClassReserveCapacity", cascade="all, delete", passive_deletes=True)
    last_updated_at: Mapped[DateTime] = mapped_column(DateTime)
    last_updated_from: Mapped[str] = mapped_column(String(7))

    def to_json(self):
        attributes = {}
        for attribute in self.course.attrs:
            attributes[attribute.label] = attribute.value

        return {
            "course_code": self.course_id,
            "section_code": self.class_section,
            "title": self.title,
            "description": self.course.description,
            "schedules": [schedule.to_json() for schedule in self.schedules],
            "class_number": self.class_number,
            "component": self.component,
            "term": self.term,
            "credits": self.course.credits,
            "instruction_type": self.instruction_type,
            "enrollment_cap": self.enrollment_cap,
            "enrollment_total": self.enrollment_total,
            "waitlist_cap": self.waitlist_cap,
            "waitlist_total": self.waitlist_total,
            "min_enrollment": self.min_enrollment,
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
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    building: Mapped[Optional[str]] = mapped_column(String(32))
    room: Mapped[Optional[str]] = mapped_column(String(16))
    instructors: Mapped[List["Instructor"]] = relationship("Instructor", secondary=schedule_instructor_join_table)
    days: Mapped[str] = mapped_column(String(10))
    # start time and end time are in minutes since midnight
    start_time: Mapped[Optional[int]] = mapped_column(Integer)
    end_time: Mapped[Optional[int]] = mapped_column(Integer)
    class_number: Mapped[int] = mapped_column(Integer)
    term: Mapped[str] = mapped_column(String(20))
    __table_args__ = (ForeignKeyConstraint((class_number, term), (Class.class_number, Class.term)), {})
    class_reference: Mapped["Class"] = relationship("Class",
                                                    back_populates="schedules")

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
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    parent_course_code: Mapped[str] = mapped_column(String(10), ForeignKey("course.code"))


class Course(Base):
    __tablename__ = "course"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    credits: Mapped[str] = mapped_column(String(20))
    description: Mapped[Optional[str]] = mapped_column(Text)
    attrs: Mapped[Optional[List["CourseAttribute"]]] = relationship("CourseAttribute")
    last_updated_at: Mapped[DateTime] = mapped_column(DateTime)
    last_updated_from: Mapped[str] = mapped_column(String(7))


class TermDataSource(Base):
    __tablename__ = "term_source"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(10))
    raw_term_name: Mapped[str] = mapped_column(String(20))
    term_name: Mapped[str] = mapped_column(String(20))
    last_updated: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    last_seen: Mapped[DateTime] = mapped_column(DateTime)


class TermData(Base):
    __tablename__ = "term"
    name: Mapped[str] = mapped_column(String(20), unique=True)
    confirmed: Mapped[Boolean] = mapped_column(Boolean, default=False)
    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True)
    default: Mapped[Boolean] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, autoincrement=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class ClassEnrollmentStamp(Base):
    __tablename__ = "class_enrollment_stamp"
    class_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str] = mapped_column(String(32), primary_key=True)
    enrollment_cap: Mapped[Optional[int]] = mapped_column(Integer)
    enrollment_total: Mapped[Optional[int]] = mapped_column(Integer)
    waitlist_cap: Mapped[Optional[int]] = mapped_column(Integer)
    waitlist_total: Mapped[Optional[int]] = mapped_column(Integer)
    min_enrollment: Mapped[Optional[int]] = mapped_column(Integer)
    timestamp: Mapped[DateTime] = mapped_column(DateTime, primary_key=True)
    source: Mapped[str] = mapped_column(String(7), primary_key=True)

class ClassReserveCapacity(Base):
    __tablename__ = "class_reserve_capacity"
    class_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str] = mapped_column(String(32), primary_key=True)
    expire_date: Mapped[DateTime] = mapped_column(DateTime)
    description: Mapped[str] = mapped_column(String(60))
    enroll_cap: Mapped[int] = mapped_column(Integer)
    enroll_total: Mapped[int] = mapped_column(Integer)
    __table_args__ = (ForeignKeyConstraint((class_number, term), (Class.class_number, Class.term), ondelete="CASCADE"), {})
    class_reference: Mapped["Class"] = relationship("Class",
                                                    back_populates="reserve_capacities")
