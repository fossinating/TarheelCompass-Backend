import dataclasses
import datetime
import os
import urllib.request

import requests as requests
from tqdm import tqdm
from bs4 import BeautifulSoup, NavigableString
from urllib3.exceptions import NewConnectionError, MaxRetryError
from tika import parser
from os.path import exists
import filecmp

from models import Course, Class, ClassSchedule, Instructor, CourseAttribute
from utilities import search_to_schedule, get_or_create_instructor, safe_cast, standardize_term
from database import db_session


def get_root_text(html_element):
    if isinstance(html_element, NavigableString):
        return html_element
    elif len(html_element.contents) == 0:
        return ""
    else:
        return get_root_text(html_element.contents[0])


subjects = (
    "AERO", "AAAD", "AMST", "ANTH", "APPL", "ARAB", "ARCH", "ARMY", "ARTH", "ASIA", "ASTR", "BIOC", "BCB", "BBSP",
    "BIOL",
    "BMME", "BIOS", "BCS", "BUSI", "CHIP", "CBIO", "CBPH", "CBMC", "CHEM", "CHER", "CHIN", "PLAN", "CLAR", "CLAS",
    "CLSC",
    "CRMH", "COMM", "CMPL", "COMP", "EURO", "CZCH", "DENG", "DHYG", "DHED", "DRAM", "DTCH", "ECON", "EDUC", "ENDO",
    "ENGL",
    "ENEC", "ENVR", "EPID", "EXSS", "EDMX", "DPET", "FOLK", "FREN", "GNET", "GEOL", "GEOG", "GERM", "GSLL", "GLBL",
    "GOVT",
    "GRAD", "GREK", "HBEH", "HPM", "HEBR", "HNUR", "HIST", "INLS", "IDST", "ITAL", "JAPN", "JWST", "SWAH", "KOR",
    "LTAM",
    "LATN", "LFIT", "LGLA", "LING", "MASC", "MTSC", "MHCH", "MATH", "MEJO", "MCRO", "MUSC", "NAVS", "NBIO", "NSCI",
    "NURS",
    "NUTR", "OCSC", "OCCT", "OPER", "ORPA", "ORAD", "ORTH", "PATH", "PWAD", "PEDO", "PERI", "PRSN", "PHRS", "DPMP",
    "PHCO",
    "PHCY", "DPOP", "PHIL", "PHYA", "PHYS", "PHYI", "PLSH", "POLI", "PORT", "PACE", "PROS", "PSYC", "PUBA", "PUBH",
    "PLCY",
    "RADI", "RECR", "RELI", "ROML", "RUSS", "SPHG", "SLAV", "SOWO", "SOCI", "SPAN", "SPHS", "STOR", "ARTS", "TOXC",
    "TURK",
    "WOLO", "WGST", "VIET")


def process_course_search_for_terms(terms):
    process_course_search_for_term(", ".join(terms))


# gets information about classes from the class search
# (will not get information about any class without credit hours)
def process_course_search_for_term(term):
    response = requests.get("https://reports.unc.edu/class-search/advanced_search/", params={
        "term": term,
        "advanced": ", ".join(subjects)
    })

    missing_courses = []
    missing_classes = []

    print("got a response")
    soup = BeautifulSoup(str(response.content).replace("\\n", ""), "html.parser")
    timestamp = datetime.datetime.utcnow()

    rows = soup.select("#results-table > tbody > tr")
    static_class_data = {}
    for row in tqdm(rows, position=0):
        class_data = {}
        i = 0
        while i < len(row.contents):
            key = row.contents[i].split(";")[0].strip()
            value = get_root_text(row.contents[i + 1])
            class_data[key] = value
            static_class_data[key] = value
            i += 2

        # check to see if the course exists, if not leave a warning
        course_id = static_class_data["subject"] + " " + static_class_data["catalog number"]
        if db_session.query(Course.code).filter_by(code=course_id).first() is None and course_id not in missing_courses:
            missing_courses.append(course_id)
            db_session.add(Course(
                code=course_id,
                title=class_data["course description"],
                description="Generated from section data",
                credits=class_data["credit hours"],
                last_updated_at=timestamp,
                last_updated_from="search"
            ))

        class_number = safe_cast(class_data["class number"], int, -1)

        class_obj = db_session.query(Class).filter_by(
            class_number=class_number, term=standardize_term(class_data["term"])).first()
        if class_obj is None:
            if str(class_number) in missing_classes:
                continue
            missing_classes.append(str(class_number))

            schedule = search_to_schedule(class_data, standardize_term(class_data["term"]))
            db_session.add(schedule)

            db_session.add(Class(
                course_id=course_id,
                class_section=class_data["section number"],
                class_number=class_number,
                title=class_data["course description"],
                term=standardize_term(class_data["term"]),
                hours=safe_cast(class_data["credit hours"], float, -1.0),
                meeting_dates=class_data["meeting dates"],
                instruction_type=class_data["instruction mode"],
                schedules=[schedule],
                enrollment_total=-1 * safe_cast(class_data["available seats"], int, -1),
                last_updated_at=timestamp,
                last_updated_from="search"
            ))
        else:
            # add/update the meeting dates since this isnt available in the pdf
            class_obj.meeting_dates = class_data["meeting dates"]
            # add/update the instruction type since this isn't scraped from the pdf
            class_obj.instruction_type = class_data["instruction mode"]
            generated_schedule = search_to_schedule(class_data, standardize_term(class_data["term"]))
            found_match = False
            # search through all of the schedules to find a matching one
            for schedule in class_obj.schedules:
                if generated_schedule.days == schedule.days and generated_schedule.time == schedule.time:
                    found_match = True
                    # if a match is found, check if the instructor is included
                    if class_data["primary instructor name(s)"] not in [instructor.name for instructor in schedule.instructors]:
                        # if instructor not included, add it
                        schedule.instructors.append(get_or_create_instructor(class_data["primary instructor name(s)"]))
                    break

            # if a matching schedule not found, add the generated one
            if not found_match:
                class_obj.schedules.append(generated_schedule)

            # update enrollment total
            class_obj.enrollment_total = \
                (0 if class_obj.enrollment_cap is None else class_obj.enrollment_cap) \
                - safe_cast(class_data["available seats"], int, -1)

            # update last updated info
            class_obj.last_updated_at = timestamp
            class_obj.last_updated_from = "search"

    print(f"Created entries for {len(missing_courses)} missing courses: " + ",".join(missing_courses))
    print(f"Created entries for {len(missing_classes)} missing classes: " + ",".join(missing_classes))


def process_pdf_for_terms(terms):
    print("Getting most up to date pdf")

    response = requests.get("https://registrar.unc.edu/courses/schedule-of-classes/directory-of-classes-2/")

    soup = BeautifulSoup(response.content, "html.parser")

    for link in soup.select("div > ul > li > a"):
        if link.text in terms:
            source = link["href"]
            term = source.split("/")[-1].split("-")[0]
            filename = "ssb-collection/" + standardize_term(term) + ".pdf"
            temp_filename = "temp/" + standardize_term(term) + ".pdf"
            if not exists("temp/"):
                os.mkdir("temp")
            if not exists("ssb-collection/"):
                os.mkdir("ssb-collection")
            if exists(temp_filename):
                os.remove(temp_filename)
            print(f"Downloading {filename} from {source}")
            urllib.request.urlretrieve(source, temp_filename)

            if True or not exists(filename) or not filecmp.cmp(filename, temp_filename):
                print("File changed, analysing new PDF")
                if exists(filename):
                    os.remove(filename)
                os.rename(temp_filename, filename)
                process_pdf(filename)
            else:
                print(f"File unchanged")
                os.remove(temp_filename)


# TODO: Rewrite to cache everything and then input at the very end
def process_pdf(file_name):
    print(f"Processing {file_name}")

    missing_courses = []

    timestamp = datetime.datetime.utcnow()
    term = file_name.split("/")[1].split(".")[0]
    raw = parser.from_file(file_name)
    class_data = {}
    for line in tqdm(raw["content"].strip().split("\n"), position=0):
        if line.strip() == "":
            continue
        if "_________________________________________________________________________________________________________" in line:
            if len(class_data) > 0:
                course_id = class_data["dept"] + " " + class_data["catalog_number"]
                # check to see if the course exists, if not leave a warning

                if db_session.query(Course.code).filter_by(
                        code=course_id).first() is None and course_id not in missing_courses:
                    missing_courses.append(course_id)
                    db_session.add(Course(
                        code=course_id,
                        title=class_data["title"],
                        credits=class_data["units"],
                        last_updated_at=timestamp,
                        last_updated_from="pdf"
                    ))

                class_obj = db_session.query(Class).filter_by(class_number=class_data["class_number"],
                                                              term=term).first()

                if class_obj is None:
                    # if the class doesn't exist yet, create it and any necessary information
                    schedules = []
                    for schedule_data in class_data["schedules"]:
                        #print(schedule_data)
                        instructors = []

                        for instructor_data in schedule_data["instructors"]:
                            instructor = db_session.query(Instructor).filter_by(name=instructor_data["name"]).first()
                            if instructor is None:
                                instructor = Instructor(
                                    name=instructor_data["name"],
                                    instructor_type=instructor_data["type"]
                                )
                            if instructor not in instructors:
                                instructors.append(instructor)
                        db_session.add_all(instructors)
                        schedule = ClassSchedule(
                            location=schedule_data["building"] + " " + schedule_data["room"],
                            instructors=instructors,
                            days=schedule_data["days"],
                            time=schedule_data["time"],
                            term=term
                        )
                        schedules.append(schedule)
                    db_session.add_all(schedules)

                    db_session.add(Class(
                        course_id=course_id,
                        class_section=class_data["section"],
                        class_number=class_data["class_number"],
                        title=class_data["title"],
                        component=class_data["component"],
                        topics=class_data["topics"],
                        term=term,
                        hours=class_data["units"],
                        # meeting dates, instruction type not provided
                        schedules=schedules,
                        enrollment_cap=class_data["enrollment_cap"],
                        enrollment_total=class_data["enrollment_total"],
                        waitlist_cap=class_data["waitlist_cap"],
                        waitlist_total=class_data["waitlist_total"],
                        min_enrollment=class_data["min_enrollment"],
                        attributes=class_data["attributes"] if "attributes" in class_data else "",
                        combined_section_id=class_data[
                            "combined_section_id"] if "combined_section_id" in class_data else "",
                        equivalents=class_data["equivalents"] if "equivalents" in class_data else "",
                        last_updated_at=timestamp,
                        last_updated_from="pdf"
                    ))
                else:
                    # if the class does already exist, update it with new information
                    print(class_data["class_number"])
                    for schedule in class_obj.schedules:
                        db_session.delete(schedule)

                    schedules = []
                    for schedule_data in class_data["schedules"]:
                        instructors = []
                        # print(schedule_data["instructors"])

                        for instructor_data in schedule_data["instructors"]:
                            instructor = db_session.query(Instructor).filter_by(
                                name=instructor_data["name"]).first()
                            if instructor is None:
                                if len(instructor_data["type"]) > 5:
                                    print(instructor_data["type"])
                                instructor = Instructor(
                                    name=instructor_data["name"],
                                    instructor_type=instructor_data["type"]
                                )
                            if instructor not in instructors:
                                instructors.append(instructor)
                        db_session.add_all(instructors)
                        schedule = ClassSchedule(
                            class_reference=class_obj,
                            location=schedule_data["building"] + " " + schedule_data["room"],
                            instructors=instructors,
                            days=schedule_data["days"],
                            time=schedule_data["time"],
                            term=term
                        )
                        schedules.append(schedule)
                    db_session.add_all(schedules)
                    class_obj.course_id = course_id
                    class_obj.class_section = class_data["section"]
                    class_obj.title = class_data["title"]
                    class_obj.component = class_data["component"]
                    class_obj.topics = class_data["topics"]
                    class_obj.hours = class_data["units"]
                    # meeting dates, instruction type not provided
                    class_obj.schedules = schedules
                    class_obj.enrollment_cap = class_data["enrollment_cap"]
                    class_obj.enrollment_total = class_data["enrollment_total"]
                    class_obj.waitlist_cap = class_data["waitlist_cap"]
                    class_obj.waitlist_total = class_data["waitlist_total"]
                    class_obj.min_enrollment = class_data["min_enrollment"]
                    class_obj.attributes = class_data["attributes"] if "attributes" in class_data else ""
                    class_obj.combined_section_id = class_data[
                        "combined_section_id"] if "combined_section_id" in class_data else ""
                    class_obj.equivalents = class_data["equivalents"] if "equivalents" in class_data else ""
                    class_obj.last_updated_at = timestamp
                    class_obj.last_updated_from = "pdf"
            class_data = None
            continue
        # first line
        elif class_data is None:
            if line.startswith("Report"):
                class_data = {}
                continue
            line_data = [x for x in line.split(" ") if x.strip()]
            class_data = {}

            data_stage = ["dept", "catalog_number", "section", "class_number", "title", "component", "units", "topics"]
            altered_line = line.strip()
            while len(altered_line) > 0 and len(data_stage) > 0:
                if data_stage[0] == "title":
                    for component in ["Lecture", "Lab", "Recitation", "Independent Study", "Practicum",
                                      "Thesis Research", "Clinical", "Correspondence", "Field Work",
                                      "Inter_Institutional"]:
                        if component in altered_line:
                            class_data["title"] = altered_line[:altered_line.index(component)].strip()
                            data_stage.pop(0)
                            class_data["component"] = component
                            altered_line = altered_line[altered_line.index(component) + len(component):].strip()
                            break
                elif data_stage[0] == "units":
                    j = 0
                    while j < len(altered_line):
                        if not altered_line[j].isnumeric() and altered_line[j] not in [" ", "_"]:
                            break
                        j += 1
                    class_data["units"] = altered_line[:j].strip()
                    altered_line = altered_line[j:].strip()
                else:
                    if " " in altered_line:
                        class_data[data_stage[0]] = altered_line[:altered_line.index(" ")]
                        altered_line = altered_line[altered_line.index(" "):].strip()
                    else:
                        class_data[data_stage[0]] = altered_line
                        altered_line = ""
                data_stage.pop(0)
            continue
        elif line.startswith("Bldg:"):
            def find_nth(haystack, needle, n):
                start = haystack.find(needle)
                while start >= 0 and n > 1:
                    start = haystack.find(needle, start + len(needle))
                    n -= 1
                return start

            schedule = {"building": line[len("Bldg: "):line.index("Room: ")],
                        "room": line[line.index("Room:") + len("Room:"):line.index("Days:")].strip(),
                        "days": line[line.index("Days:") + len("Days:"):line.index("Time:")].strip(),
                        "time": line[line.index("Time:") + len("Time:"):
                                     find_nth(line[line.index("Time:") + len("Time:"):].strip(), ":", 2)
                                     + line.index("Time:") + len("Time: ") + 4].strip()}
            if "TBA" in schedule["time"]:
                schedule["time"] = "TBA"
            if "schedules" not in class_data:
                class_data["schedules"] = []
            class_data["schedules"].append(schedule)
        elif "Instructor:" in line and not line.startswith("Instructor:") and "enrollment_cap" not in class_data:
            if "schedules" not in class_data:
                print("Major error occurred!!!")
            if "instructors" not in class_data["schedules"][len(class_data["schedules"]) - 1]:
                class_data["schedules"][len(class_data["schedules"]) - 1]["instructors"] = []
            class_data["schedules"][len(class_data["schedules"]) - 1]["instructors"].append({
                "type": line[:line.index(" ")],
                "name": line[line.index("Instructor:") + len("Instructor:"):].strip()
            })
        elif line.startswith("Class Enrl Cap:"):
            class_data["enrollment_cap"] = line[len("Class Enrl Cap:"):line.index("Class Enrl Tot:")].strip()
            class_data["enrollment_total"] = line[line.index("Class Enrl Tot:") + len("Class Enrl Tot:"):line.index(
                "Class Wait Cap:")].strip()
            class_data["waitlist_cap"] = line[line.index("Class Wait Cap:") + len("Class Wait Cap:"):line.index(
                "Class Wait Tot:")].strip()
            class_data["waitlist_total"] = line[line.index("Class Wait Tot:") + len("Class Wait Tot:"):line.index(
                "Class Min Enrl:")].strip()
            class_data["min_enrollment"] = \
            line[line.index("Class Min Enrl:") + len("Class Min Enrl:"):].strip().split()[0]
        elif line.startswith("Attributes"):
            class_data["attributes"] = line[len("Attributes: "):]
        elif line.startswith("Combined Section ID"):
            class_data["combined_section_id"] = line[len("Combined Section ID:"):].strip()
        elif line.startswith("Class Equivalents"):
            class_data["equivalents"] = line[len("Class Equivalents:"):].strip()
    print(f"Created entries for {len(missing_courses)} missing courses: " + ",".join(missing_courses))


# gets data about courses from the catalog
def process_course_catalog():
    max_length = 0
    add_queue = []
    timestamp = datetime.datetime.utcnow()
    for subject in tqdm(subjects, position=0, leave=False, desc="Subjects"):
        response = requests.get(f"https://catalog.unc.edu/courses/{subject.lower()}/")

        soup = BeautifulSoup(str(response.content).replace("\\n", "")
                             .replace("\\xc2\\xa0", " ").encode('utf-8').decode("unicode_escape"), "html.parser")

        for course in tqdm(soup.select(".courseblock"), position=1, leave=False, desc=subject):
            attributes = []
            attribute_codes = ["grading_status", "making_connections", "requisites", "repeat_rules", "idea_action",
                               "same_as", "global_language"]

            for attribute_code in attribute_codes:
                attribute_block = course.select_one(".detail-" + attribute_code)
                if attribute_block is not None:
                    strong_text = attribute_block.select_one("strong").text
                    other_text = attribute_block.text.replace(strong_text, "")
                    attributes.append(CourseAttribute(
                        label=strong_text.strip().strip(".:"),
                        value=other_text.strip().strip(".")))

            course_obj = db_session.query(Course).filter_by(
                code=course.select_one(".detail-code strong").text.strip(".")).first()
            add_queue.extend(attributes)

            if course_obj is None:
                add_queue.append(Course(
                    code=course.select_one(".detail-code strong").text.strip("."),
                    title=course.select_one(".detail-title strong").text.strip("."),
                    credits=course.select_one(".detail-hours strong").text.strip(".").replace(" Credits", ""),
                    description=("" if course.select_one(".courseblockextra") is None else
                                 course.select_one(".courseblockextra").text.strip(".")),
                    attrs=attributes,
                    last_updated_at=timestamp,
                    last_updated_from="catalog"
                ))
            else:
                for attribute in course_obj.attrs:
                    db_session.delete(attribute)
                course_obj.title = course.select_one(".detail-title strong").text.strip(".")
                course_obj.credits = course.select_one(".detail-hours strong").text.strip(".").replace(" Credits", "")
                course_obj.description = ("" if course.select_one(".courseblockextra") is None else
                                          course.select_one(".courseblockextra").text.strip("."))
                course_obj.attrs = attributes
                course_obj.last_updated_at = timestamp
                course_obj.last_updated_from = "catalog"
    db_session.add_all(add_queue)


def update_unc_data():
    from database import init_db
    init_db()

    process_course_catalog()
    db_session.commit()

    process_pdf_for_terms(["Spring 2023", "Fall 2023"])
    db_session.commit()

    process_course_search_for_terms(["2023 Spring", "2023 Fall"])
    db_session.commit()


if __name__ == "__main__":
    update_unc_data()
