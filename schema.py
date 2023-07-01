from models import Instructor as InstructorModel
from models import Class as ClassModel
from models import ClassSchedule as ClassScheduleModel
from models import CourseAttribute as CourseAttributeModel
from models import Course as CourseModel

import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyConnectionField, SQLAlchemyObjectType


class CourseFilter(FilterSet)


class Instructor(SQLAlchemyObjectType):
    class Meta:
        model = InstructorModel
        only_fields = ("id", "instructor_type", "name",)
        interfaces = (relay.Node, )


class Class(SQLAlchemyObjectType):
    class Meta:
        model = ClassModel
        only_fields = ("course", "class_section", "class_number", "title",
                       "component", "topics", "term", "hours", "meeting_dates",
                       "instruction_type", "schedules", "enrollment_cap", "waitlist_cap",
                       "waitlist_total", "min_enrollment", "combined_section_id", "equivalents",
                       "last_updated_at", "last_updated_from",)
        interfaces = (relay.Node, )


class ClassSchedule(SQLAlchemyObjectType):
    class Meta:
        model = ClassScheduleModel
        only_fields = ("location", "instructors", "days", "time", )
        interfaces = (relay.Node, )


class CourseAttribute(SQLAlchemyObjectType):
    class Meta:
        model = CourseAttributeModel
        only_fields = ("label", "value")
        interfaces = (relay.Node, )


class Course(SQLAlchemyObjectType):
    class Meta:
        model = CourseModel
        only_fields = ("code", "title", "credits", "description", "attrs",
                       "last_updated_at", "last_updated_from")
        interfaces = (relay.Node, )


class Query(graphene.ObjectType):
    node = relay.Node.Field()

    all_classes = SQLAlchemyConnectionField(
        Class.connection, sort=Class.sort_argument())


schema = graphene.Schema(query=Query)
