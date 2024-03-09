import datetime
import filecmp
import os
import urllib.request
from os.path import exists

import requests as requests
from bs4 import BeautifulSoup, NavigableString
from sqlalchemy.orm import scoped_session
from tqdm import tqdm

from database import session_factory
from models import Course, Class, CourseAttribute
from utilities import search_to_schedule, get_or_create_instructor, safe_cast, standardize_term

db_session = scoped_session(session_factory)


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


# gets data about courses from the catalog
def process_course_catalog():
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
                if generated_schedule.days == schedule.days and \
                        generated_schedule.start_time == schedule.start_time and \
                        generated_schedule.end_time == schedule.end_time:
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


# Read through the directory of class listings
def process_pdfs():
    print("Getting most up to date pdf")

    response = requests.get("https://registrar.unc.edu/courses/schedule-of-classes/directory-of-classes-2/")

    soup = BeautifulSoup(response.content, "html.parser")

    for link in soup.select(".main div > ul > li > a"):
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