from app.models import ClassSchedule, Instructor


def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default


def generate_color(class_code):
    dept_value = sum([ord(character) for character in class_code.split()[0]])
    code_value = sum([ord(character) for character in class_code.split()[1]])

    return f"{(dept_value % 180) + (code_value / 600.0 * 360 * 20 % 180)},70%,80%,1"


def human_time(mil_time):
    if "TBA" in mil_time:
        return mil_time
    times = mil_time.split(" - ")
    human_times = []
    for time in times:
        hour = int(time[:2])
        minute = int(time[3:])
        if hour > 11:
            human_times.append(f"{(hour - 1) % 12 + 1}:{minute:02d}pm")
        else:
            human_times.append(f"{hour}:{minute:02d}am")
    return " - ".join(human_times)


def humanize_hour(hour):
    return f"{(hour - 1) % 12 + 1}{'pm' if hour >= 12 else 'am'}"


def get_or_create_instructor(name):
    from app.data_updater import db_session
    instructor = db_session.query(Instructor).filter_by(name=name).first()
    if instructor is None:
        instructor = Instructor(
            name=name,
            instructor_type="??"
        )
    return instructor


def standardize_term(term):
    data = {
        "Fall 2022": "FALL2022",
        "2022 Fall": "FALL2022",
        "2229": "FALL2022",
        "2232": "SPRI2023",
        "Spring 2023": "SPRI2023",
        "2023 Spring": "SPRI2023",
        "Fall 2023": "FALL2023",
        "2023 Fall": "FALL2023",
        "2239": "FALL2023",
        "2242": "SPRI2024",
        "Spring 2024": "SPRI2024",
        "2024 Spring": "SPRI2024"
    }
    return data[term]


# translates to 24hr
def translate_time(src_time):
    nums = src_time.strip().split(" ")[0].split(":")
    hour = int(nums[0])
    mins = int(nums[1])
    return (hour + (12 if ('PM' in src_time and hour < 12) else 0))*60 + mins


def split_and_translate_time(time):
    if time == "TBA":
        return [-1, -1]
    try:
        split_time = time.split("-")
        start_time = translate_time(split_time[0])
        end_time = translate_time(split_time[1])
        return [start_time, end_time]
    except ValueError:
        print(f"Failed to split and translate time \"{time}\"")
        return [-2, -2]  # indicating an error


def search_to_schedule(class_data, term):
    class_number = safe_cast(class_data["class number"], int, -1)

    # possible schedule values:

    # None
    # TTH 02:00 PM-03:15 PM

    if class_data["schedule"] == "None":
        days = "TBA"
        start_time = -1
        end_time = -1
        instructors = [get_or_create_instructor("TBA")]
    else:
        # convoluted code since T = Tu and TH = Th
        o_days = ["M", "T", "W", "TH", "F"]
        t_days = ["M", "Tu", "W", "Th", "F"]
        order = [3, 0, 1, 2, 4]
        schedule_arr = [""] * 5
        orig_days = class_data["schedule"][:class_data["schedule"].find(" ")]
        for i in order:
            if o_days[i] in orig_days:
                orig_days = orig_days.replace(o_days[i], "")
                schedule_arr[i] = t_days[i]
        days = "".join(schedule_arr)

        # get the time
        # splits the scheduled time to get only the hh:mm PM-hh:mm PM section
        # splits that by - to get the start and end times, then joins them after translating to 24hr
        [start_time, end_time] = split_and_translate_time(
            class_data["schedule"][class_data["schedule"].find(" ") + 1:])

        instructors = [get_or_create_instructor(class_data["primary instructor name(s)"])]

    return ClassSchedule(
        location=class_data["room"],
        class_number=class_number,
        days=days,
        start_time=start_time,
        end_time=end_time,
        instructors=instructors,
        term=term
    )
