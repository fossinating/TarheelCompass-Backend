import datetime
import typing

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import session_factory
from models import Instructor as InstructorModel
from models import Class as ClassModel
from models import ClassSchedule as ClassScheduleModel
from models import CourseAttribute as CourseAttributeModel
from models import Course as CourseModel

import strawberry
from strawberry.extensions import Extension


@strawberry.type
class Instructor:
    instance: strawberry.Private[InstructorModel]
    id: int
    instructor_type: str
    name: str

    @classmethod
    def from_instance(cls, instance: InstructorModel):
        return cls(
            instance=instance,
            id=instance.id,
            instructor_type=instance.instructor_type,
            name=instance.name,
        )


@strawberry.type
class Class:
    instance: strawberry.Private[ClassModel]

    @strawberry.field
    def course(self) -> "Course":
        return Course.from_instance(self.instance.course)

    class_section: str
    class_number: int
    title: str
    component: str
    topics: str
    term: str
    hours: float
    meeting_dates: str
    instruction_type: str

    @strawberry.field
    def schedules(self) -> typing.List["ClassSchedule"]:
        return [ClassSchedule.from_instance(schedule) for schedule in self.instance.schedules]

    enrollment_cap: int
    enrollment_total: int
    waitlist_cap: int
    waitlist_total: int
    min_enrollment: int
    combined_section_id: str
    equivalents: str
    last_updated_at: datetime.datetime
    last_updated_from: str

    @classmethod
    def from_instance(cls, instance: ClassModel):
        return cls(
            instance=instance,
            class_section=instance.class_section,
            class_number=instance.class_number,
            title=instance.title,
            component=instance.component,
            topics=instance.topics,
            term=instance.term,
            hours=instance.hours,
            meeting_dates=instance.meeting_dates,
            instruction_type=instance.instruction_type,
            enrollment_cap=instance.enrollment_cap,
            enrollment_total=instance.enrollment_total,
            waitlist_cap=instance.waitlist_cap,
            waitlist_total=instance.waitlist_total,
            min_enrollment=instance.min_enrollment,
            combined_section_id=instance.combined_section_id,
            equivalents=instance.equivalents,
            last_updated_at=instance.last_updated_at,
            last_updated_from=instance.last_updated_from,
        )


@strawberry.type
class ClassSchedule:
    instance: strawberry.Private[ClassScheduleModel]
    location: str

    @strawberry.field
    def instructors(self) -> typing.List["Instructor"]:
        return [Instructor.from_instance(instructor) for instructor in self.instance.instructors]

    days: str
    start_time: int
    end_time: int

    @classmethod
    def from_instance(cls, instance: ClassScheduleModel):
        return cls(
            instance=instance,
            location=instance.location,
            days=instance.days,
            start_time=instance.start_time,
            end_time=instance.end_time,
        )


@strawberry.type
class CourseAttribute:
    instance: strawberry.Private[CourseAttributeModel]
    label: str
    value: str

    @classmethod
    def from_instance(cls, instance: CourseAttributeModel):
        return cls(
            instance=instance,
            label=instance.label,
            value=instance.value,
        )


@strawberry.type
class Course:
    instance: strawberry.Private[CourseModel]
    code: str
    title: str
    credits: str
    description: str

    @strawberry.field
    def attrs(self) -> typing.List["CourseAttribute"]:
        return [CourseAttribute.from_instance(attr) for attr in self.instance.attrs]

    last_updated_at: datetime.datetime
    last_updated_from: str

    @classmethod
    def from_instance(cls, instance: CourseModel):
        return cls(
            instance=instance,
            code=instance.code,
            title=instance.title,
            credits=instance.credits,
            description=instance.description,
            last_updated_at=instance.last_updated_at,
            last_updated_from=instance.last_updated_from,
        )


# hardcoding the query limit for now, if the service is performing well enough
#      then I may consider upping the limit
query_limit = 50


class SQLAlchemySession(Extension):
    def on_request_start(self):
        self.execution_context.context["db"] = session_factory()

    def on_request_end(self):
        self.execution_context.context["db"].close()


@strawberry.type
class Query:
    @strawberry.field(name="classes")
    def classes(self, info,
                term: str,
                course_id: typing.Optional[str] = None,
                title: typing.Optional[str] = None,
                class_section: typing.Optional[str] = None,
                component: typing.Optional[str] = None,
                instruction_type: typing.Optional[str] = None,
                attrs: typing.Optional[typing.List[str]] = None,
                instructor: typing.Optional[str] = None,
                days: typing.Optional[typing.List[str]] = None,
                starts_after: typing.Optional[str] = None,
                ends_before: typing.Optional[str] = None) -> typing.List["Class"]:
        db: Session = info.context["db"]
        statement = select(ClassModel).where(ClassModel.term == term).\
            limit(query_limit).order_by(ClassModel.course_id, ClassModel.class_section)
        if course_id is not None:
            statement = statement.where(ClassModel.course_id.ilike(f"%{course_id}%"))
        if title is not None:
            statement = statement.where(ClassModel.title.ilike(f"%{title}%"))
        if class_section is not None:
            statement = statement.where(ClassModel.class_section.ilike(f"%{class_section}%"))
        if component is not None:
            statement = statement.where(ClassModel.component == component)
        if instruction_type is not None:
            statement = statement.where(ClassModel.instruction_type == instruction_type)
        if attrs is not None:
            statement = statement.where(ClassModel.attributes.any(CourseAttributeModel.value.in_(attrs)))
        if instructor is not None:
            statement = statement.where(ClassModel.schedules.any(
                ClassScheduleModel.instructors.any(InstructorModel.name == instructor)
            ))
        if days is not None:
            valid_days = ["M", "Tu", "W", "Th", "F"]
            string_search = ""
            for day in valid_days:
                if day not in days:
                    string_search += f"%{day}%"

            # built a string along the like of "%M%%W%" for a filter allowing Tu, Th, F
            # filter for classes where there is not a schedule that fits the inverted filter
            statement = statement.where(~ClassModel.schedules.any(
                ClassScheduleModel.days.like(string_search)
            ))
        if starts_after is not None:
            # filter for classes where there is not a schedule that starts before the desired time
            statement = statement.where(~ClassModel.schedules.any(
                ClassScheduleModel.start_time < starts_after
            ))
        if ends_before is not None:
            # filter for classes where there is not a schedule that ends after the desired time
            statement = statement.where(~ClassModel.schedules.any(
                ClassScheduleModel.end_time > ends_before
            ))
        return [Class.from_instance(class_obj) for class_obj in db.execute(statement).scalars().all()]


schema = strawberry.Schema(Query, extensions=[SQLAlchemySession])
