from typing import List

from sqlalchemy import Table, Float, DateTime, Column, Integer, \
    String, ForeignKey, Text, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

from database import Base

schedule_instructor_join_table = Table("schedule_instructor_join_table",
                                       Base.metadata,
                                       Column("join_id", Integer, primary_key=True),
                                       Column("instructor_id", ForeignKey("instructor.id")),
                                       Column("schedule_id", ForeignKey("class_schedule.id")),
                                       UniqueConstraint("instructor_id", "schedule_id"), )


class Instructor(Base):
    __tablename__ = "instructor"
    id: Mapped[int] = mapped_column(primary_key=True)
    instructor_type: Mapped[str] = mapped_column(String(6))
    name: Mapped[str] = mapped_column(Text)


class Class(Base):
    __tablename__ = "class"
    course_id: Mapped[str] = mapped_column(String(10), ForeignKey("course.code"))
    course: Mapped["Course"] = relationship("Course")
    class_section: Mapped[str] = mapped_column(String(4))
    class_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    component: Mapped[str] = mapped_column(Text)
    topics: Mapped[str] = mapped_column(Text)
    term: Mapped[str] = mapped_column(String(8), primary_key=True)
    hours: Mapped[float] = mapped_column(Float)
    meeting_dates: Mapped[str] = mapped_column(String(30))
    instruction_type: Mapped[str] = mapped_column(String)
    schedules: Mapped[List["ClassSchedule"]] = relationship("ClassSchedule")
    enrollment_cap: Mapped[int] = mapped_column(Integer)
    enrollment_total: Mapped[int] = mapped_column(Integer)
    waitlist_cap: Mapped[int] = mapped_column(Integer)
    waitlist_total: Mapped[int] = mapped_column(Integer)
    min_enrollment: Mapped[int] = mapped_column(Integer)
    attributes: Mapped[str] = mapped_column(Text)
    combined_section_id: Mapped[str] = mapped_column(Text)
    equivalents: Mapped[str] = mapped_column(Text)
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
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location: Mapped[str] = mapped_column(Text)
    instructors: Mapped[List["Instructor"]] = relationship("Instructor", secondary=schedule_instructor_join_table)
    days: Mapped[str] = mapped_column(String(10))
    # start time and end time are in minutes since midnight
    start_time: Mapped[int] = mapped_column(Integer)
    end_time: Mapped[int] = mapped_column(Integer)
    time: Mapped[str] = mapped_column(String(15))
    class_number: Mapped[int] = mapped_column(Integer)
    term: Mapped[str] = mapped_column(String(8))
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
    description: Mapped[str] = mapped_column(Text)
    attrs: Mapped[List["CourseAttribute"]] = relationship("CourseAttribute")
    last_updated_at: Mapped[DateTime] = mapped_column(DateTime)
    last_updated_from: Mapped[str] = mapped_column(String(7))


'''

class RolesUsers(Base):
    __tablename__ = 'roles_users'
    id = Column(Integer(), primary_key=True)
    user_id = Column('user_id', UUID(as_uuid=True), ForeignKey('user.id'))
    role_id = Column('role_id', Integer(), ForeignKey('role.id'))


class Role(Base, RoleMixin):
    __tablename__ = 'role'
    id = Column(Integer(), primary_key=True)
    name = Column(String(80), unique=True)
    description = Column(String(255))


class User(Base, UserMixin):
    __tablename__ = 'user'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True)
    username = Column(String(255), unique=True, nullable=True)
    password = Column(String(255), nullable=False)
    last_login_at = Column(DateTime())
    current_login_at = Column(DateTime())
    last_login_ip = Column(String(100))
    current_login_ip = Column(String(100))
    login_count = Column(Integer)
    active = Column(Boolean())
    fs_uniquifier = Column(String(255), unique=True, nullable=False)
    confirmed_at = Column(DateTime())
    roles = relationship('Role', secondary='roles_users',
                         backref=backref('users', lazy='dynamic'))
    schedules = relationship('UserSchedule', foreign_keys='[UserSchedule.user_id]')
    active_schedule_id = Column(ForeignKey("user_schedule.id"))

    def to_json(self):
        return {
            "active_schedule_id": self.active_schedule_id,
            "schedules": {str(schedule.id): schedule.to_json() for schedule in self.schedules}
        }


# join table
class ClassUserSchedule(Base):
    __tablename__ = "class_user_schedule"
    entry_id = Column(Integer, primary_key=True)
    user_schedule_id = Column(ForeignKey("user_schedule.id"))
    class_number = Column(Integer)
    term = Column(String(8))
    __table_args__ = (ForeignKeyConstraint((class_number, term), (Class.class_number, Class.term)), {})


class UserSchedule(Base):
    __tablename__ = "user_schedule"
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"))
    display_name = Column(String(30))
    term = Column(String(8))
    classes = relationship("Class", secondary="class_user_schedule")

    def to_json(self):
        return {
            "id": self.id,
            "displayName": self.display_name,
            "term": self.term,
            "classNumbers": [class_obj.class_number for class_obj in self.classes]
        }
'''