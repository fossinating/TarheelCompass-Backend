import json
import random
import uuid

from flask import render_template, Response, request
#from flask_login import current_user
from sqlalchemy import text, select

from __init__ import app
from database import db_session
from models import Class#, UserSchedule
from utilities import humanize_hour


@app.context_processor
def utility_processor():
    from utilities import generate_color, human_time
    return dict(generate_color=generate_color, human_time=human_time)


current_term = 2229


class Schedule:
    id = ""
    classes = []
    name = "Unnamed Schedule"

    def __init__(self, json_schedule):
        self.id = json_schedule["id"]
        self.name = json_schedule["name"]
        for class_number in json_schedule["class_numbers"]:
            self.classes.append(db_session.query(Class).filter_by(class_number=class_number).first())

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "class_numbers": [class_obj.class_number for class_obj in self.classes]
        }

    @classmethod
    def new(cls):
        return Schedule({
            "id": str(uuid.uuid4()),
            "name": "New Schedule",
            "class_numbers": []
        })


def get_active_schedule(request, response):
    if "schedules" in request.cookies:
        if "active_schedule" in request.cookies:
            return Schedule(json.loads(request.cookies.get("schedules")).get(request.cookies.get("active_schedule")))
        else:
            active_schedule = random.choice(request.cookies.get("schedules").keys())
            response.set_cookie("active_schedule", active_schedule)
            return Schedule(json.loads(request.cookies.get("schedules")).get(active_schedule))
    else:
        schedule = Schedule.new()
        schedules = {schedule.id: schedule.to_json()}
        response.set_cookie("schedules", value=json.dumps(schedules), secure=True)
        response.set_cookie("active_schedule", value=schedule.id, secure=True)
        return schedule


@app.route('/search', methods=["POST"])
# TODO: Search by name, professor, geneds
# TODO: Fade if class already in schedule
# TODO: Fade if class conflicts with schedule
def class_search():
    q = db_session.query(Class)
    print(request.json.get("component"))
    if request.json.get("class_code") != "":
        print(request.json.get("class_code"))
        q = q.filter(Class.course_id.ilike(f"%{request.json.get('class_code')}%", escape="\\"))
    if request.json.get("component") != "any":
        q = q.filter(Class.component.ilike(f"%{request.json.get('component')}%", escape="\\"))
    if request.json.get("term") != "":
        q = q.filter(Class.term == request.json.get('term'))

    print(q.order_by(Class.course_id, Class.class_section).limit(50).all())
    return [result.to_json() for result in q.order_by(Class.course_id, Class.class_section).limit(50).all()]


@app.route("/class_data", methods=["POST"])
def class_data():
    q = db_session.query(Class)

    classes = {}

    for _class_id in request.json["classes"]:
        print(int(_class_id), request.json["term"])
        classes[_class_id] = db_session.scalar(select(Class).where(
            Class.class_number == int(_class_id) and Class.term == request.json["term"])).to_json()

    return classes


'''
@app.route('/api/schedule', methods=["POST", "OPTIONS"])
def schedule_maker():
    response_data = []
    for class_number in request.json["classNumbers"]:
        class_obj = db_session.query(Class).filter_by(class_number=class_number).first()
        if class_obj is None:
            print(f"Someone had an invalid class {class_number}")
            continue
        response_data.append({
            "parent": "#class-descriptions",
            "html": render_template("class_description.html", class_obj=class_obj)
        })
        for timeslot in class_obj.get_timeslots():
            response_data.append({
                "parent": f"#{timeslot['day']}",
                "html": render_template("class_slot.html", class_obj=class_obj, timeslot=timeslot)})
    return json.dumps(response_data)


# put migrate {schedules, active_schedule_id}
# put update_active_schedule {schedule_id}
# put create_schedule
@app.route('/api/user', methods=["POST", "GET", "OPTIONS"])
def user_endpoint():
    if request.method == "GET":
        return current_user.to_json()
    elif request.method == "POST":
        if request.json["action"] == "migrate":
            schedules = []
            schedules_json = json.loads(request.json["schedules"])
            for schedule_data in schedules_json.values():
                term = schedule_data["term"] if "term" in schedule_data else current_term
                schedules.append(UserSchedule(
                    id=uuid.UUID(schedule_data["id"]) if "id" in schedule_data else uuid.UUID(),
                    display_name=schedule_data["displayName"],
                    term=term,
                    classes=[
                        db_session.query(Class).filter(
                            Class.class_number == int(class_number), Class.term == term
                        ).first()
                        for class_number
                        in schedule_data["classNumbers"]
                    ]
                ))
            current_user.schedules = schedules
            db_session.add_all(schedules)
            db_session.flush()
            current_user.active_schedule_id = request.json["active_schedule_id"]
            db_session.commit()
            return current_user.to_json()
        elif request.json["action"] == "update_active_schedule":
            current_user.active_schedule_id = request.json["active_schedule_id"]
            db_session.commit()
            return current_user.to_json()
        elif request.json["action"] == "create_schedule":
            schedule = UserSchedule(
                term=current_term,
                display_name="New Schedule"
            )
            db_session.add(schedule)
            current_user.schedules.append(schedule)
            db_session.commit()
            return current_user.to_json()


# put add_class {schedule_id, class_number}
# put remove_class {schedule_id, class_number}
# put set_display_name {schedule_id, displayName}
@app.route('/api/user/schedule', methods=["POST"])
def user_schedule_endpoint():
    schedule = db_session.query(UserSchedule).filter(
        UserSchedule.user_id == current_user.id, UserSchedule.id == uuid.UUID(request.json["schedule_id"])).first()
    if request.json["action"] == "add_class":
        class_obj = db_session.query(Class).filter(
            Class.class_number == int(request.json["class_number"]), Class.term == schedule.term
        ).first()
        schedule.classes.append(class_obj)
    elif request.json["action"] == "remove_class":
        for class_obj in schedule.classes:
            print(class_obj.class_number, int(request.json["class_number"]))
            if class_obj.class_number == int(request.json["class_number"]):
                print("removing")
                schedule.classes.remove(class_obj)
    elif request.json["action"] == "set_display_name":
        schedule.display_name = request.json["displayName"]
    db_session.commit()
    return current_user.to_json()
'''

app.jinja_env.globals.update(humanize_hour=humanize_hour)


if __name__ == '__main__':
    app.run()
