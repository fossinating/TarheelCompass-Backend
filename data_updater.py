import datetime
import filecmp
import math
import os
import re
import urllib.request
import dotenv
from discord_logger import DiscordLogger
from os.path import exists

import requests as requests
from bs4 import BeautifulSoup, NavigableString
from sqlalchemy.orm import scoped_session
from sqlalchemy import delete, select
from tqdm import tqdm

from database import session_factory
from models import ClassReserveCapacity, Course, Class, CourseAttribute, TermDataSource, TermData, ClassSchedule
from utilities import search_to_schedule, get_or_create_instructor, safe_cast, standardize_term

from pypdf import PdfReader
import pathlib

import logging

formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

from logging.handlers import TimedRotatingFileHandler
debug_handler = TimedRotatingFileHandler((pathlib.Path(__file__).parent / "logs" / "debug.log").resolve(), when="midnight", backupCount=14)
debug_handler.suffix = "%Y%m%d"
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(formatter)

dotenv.load_dotenv()
logger = DiscordLogger(os.getenv("DISCORD_WEBHOOK_URL"), "Tarheel Compass Data", 'tarheel-compass-data')

logger.logger.addHandler(debug_handler)
logging.getLogger("sqlalchemy.engine").addHandler(debug_handler)
logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)

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
    db_session = scoped_session(session_factory)
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

            course_obj = db_session.scalar(select(Course).filter_by(
                code=course.select_one(".detail-code strong").text.strip(".")))
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
    db_session = scoped_session(session_factory)
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


pdf_split_line = "____________________________________________________________________________________________________________________________________________________________"


class PDFParser:
    # TODO: complete this list
    """
    Valid states:

    `waiting` - waiting for the starting line
    `first_line` - parsing first line for basic information
    
    
    """

    # TODO: comprehensive documentation/comments

    def __init__(self, term: str, source: str):
        self.term = term
        self.source = source
        self.reset_state()
        self.db_session = scoped_session(session_factory)
        self.missing_courses = []
        self.errors = 0
        self.state_logger = logging.getLogger("state_logger")
        self.state_logger.setLevel(logging.DEBUG) # Set it to DEBUG for it to actually output anything at all
        state_log_handler = TimedRotatingFileHandler((pathlib.Path(__file__).parent / "logs" / "state.log").resolve(), when="midnight", backupCount=14)
        state_log_handler.suffix = "%Y%m%d"
        state_log_handler.setLevel(logging.DEBUG)
        state_log_handler.setFormatter(formatter)
        self.state_logger.handlers.clear()
        self.state_logger.addHandler(state_log_handler)
        self.state_logger.info("Starting parsing of new.")
    
    def reset_state(self):
        self.state = "waiting"
        self.class_data = None
        self.extras = []
        self.schedule = None
        self.class_notes = []
        self.course = None

    
    def parse(self, force=False):
        filename = "ssb-collection/" + self.term + ".pdf"
        temp_filename = "temp/" + self.term + ".pdf"

        # Create temporary directory if it doesn't already exist
        if not exists("temp/"):
            os.mkdir("temp")
        # Delete pre-existing temp file if it already exists so there is room to download
        if exists(temp_filename):
            os.remove(temp_filename)

        # Download the file
        logger.info(f"Downloading {filename} from {self.source}")
        urllib.request.urlretrieve(self.source, temp_filename)

        # source_reader is exclusively for reading the run time and determine if we should continue
        source_reader = PdfReader(temp_filename)
        page_one = source_reader.pages[0].extract_text(extraction_mode="layout")

        logger.debug(
            page_one[page_one.index("Run Date: ")+11:page_one.index("Run Date: ")+21] + 
            " " + 
            page_one[page_one.index("Run Time: ")+11:page_one.index("Run Time: ")+19])

        self.source_datetime = datetime.datetime.strptime(
            page_one[page_one.index("Run Date: ")+11:page_one.index("Run Date: ")+21] + 
            " " + 
            page_one[page_one.index("Run Time: ")+11:page_one.index("Run Time: ")+19],
            "%m/%d/%Y %H:%M:%S")
        
        # Check if there is already a TermDataSource record indicating that a ssb of source time or later has already been parsed
        term_data_source = self.db_session.scalar(select(TermDataSource).filter_by(term_name=self.term, source="pdf"))
        if term_data_source is None:
            logger.error(f"Could not find pdf term for `{self.term}`, but this should have been created before parsing.")
            os.remove(temp_filename)
            return
        else:
            # Only parse if source_time is newer than last_updated, or if being forced(which should only happen in dev)
            if term_data_source.last_updated is None or self.source_datetime > term_data_source.last_updated or force:
                logger.info("Source run time later than saved updated time, parsing.")

                # Create ssb-collection directory if it doesn't already exist
                if not exists("ssb-collection/"):
                    os.mkdir("ssb-collection")

                # Delete existing ssb if it exists so there's room to move
                if exists(filename):
                    os.remove(filename)

                # Move the file by renaming
                os.rename(temp_filename, filename)
                
                # Start new reader instance for the new location
                reader = PdfReader(filename)

                for page in tqdm(reader.pages, position=1, leave=False, desc="Pages"):
                    for line in tqdm(page.extract_text(extraction_mode="layout").split("\n"), position=2, leave=False, desc="Lines"):
                        if self.errors >= 5:
                            logger.error("Reached 5 errors, something serious must be wrong, killing parse attempt.")
                            return
                        try:
                            self.state_logger.debug(f"{self.state}>|{line}")
                            self.parse_line(line)
                        except (Exception) as e:
                            logger.error(f"Failed to parse line with reason {e}\nLine:`{line}`")
                            self.errors += 1
                            self.reset_state()
                            raise e

                # Update the last_updated value
                # This is done at the very end intentionally so that it won't get updated if we run into any issues
                term_data_source.last_updated = self.source_datetime
                self.db_session.commit()
                self.db_session.close()
        
    def parse_line(self, line: str):
        if self.state == "waiting":
            if line.startswith(pdf_split_line):
                self.state = "first_line"
                return
        if self.state == "first_line":
            # Since sometimes between pages there will be another header bit, detect this and don't throw an error,
            # just reset to the waiting state
            if line.strip().startswith("Report ID") or len(line.strip()) == 0:
                self.reset_state()
                return
            if line[:2] != "  ":
                logger.error(f"Looking for first_line but got `{line}`")
                self.errors += 1
                self.reset_state()
                return
            # Notes on the extra characters:
            # So far I've found:
            # A(standard, on almost everything)
            # X(only on LAW classes)
            # SSB2(Summer Session 2)

            # I'm not doing regex here because I can't figure out how to include optional spaces in the character counter.
            course_id = line[2:12].strip() + " " + line[12:23].strip()
            if self.db_session.scalar(select(Course.code).filter_by(code=course_id)) is None and course_id not in self.missing_courses:
                self.missing_courses.append(course_id)
                self.course = Course(
                    code=course_id,
                    title=line[44:73].strip(),
                    credits=line[102:114].strip(),
                    last_updated_at=self.source_datetime,
                    last_updated_from="pdf"
                )
            self.class_obj = Class(
                term = self.term,
                course_id = course_id,
                class_section = line[23:32].strip(),
                class_number = int(line[32:44]),
                title = line[44:73].strip(),
                component = line[74:102].strip(),
                units = line[102:114].strip(),
                topics = line[114:143].strip(),
                last_updated_at=self.source_datetime,
                last_updated_from="pdf",
            )
            self.state = "instruction_type"
            return
        if self.state == "instruction_type":
            if len(line[:89].strip()) > 0:
                logger.error(f"Looking for instruction_type but got `{line}`")
                self.errors += 1
                self.reset_state()
                return
            self.class_obj.instruction_type = line.strip()
            self.state = "notes|schedule"
            return
        if self.state == "notes|schedule":
            if line.strip().startswith("Bldg:"):
                self.state = "schedule"
            else:
                if len(line.strip()) > 0:
                    self.class_notes.append(line.strip())
        if self.state == "schedule" or self.state == "schedule|enrollment":
            if line.strip().startswith("Bldg:"):
                match = re.match(r"""^ # Read from the very start to the very end(indicated by the $ at the end) of the string
                                   \ *Bldg:\ (?P<building>[\S]([\S]|\ [\S])*) # Look for zero or more space, then `Bldg: `, then get the building string(allowing non-whitespace and single spaces within)
                                   \ *Room:\ (?P<room>(\S.*\S)|\S) # Look for zero or more space, then `Room: `, then get room string(allowing non-zero spaces and single spaces within)
                                   \ *Days:\ (?P<days>[A-z]+) # Look for zero or more space, then `Days: `, then get days string(allowing A-z)
                                   \ *Time:\ ((?P<time>TBA)|(?P<start_time_hour>[0-9]{2}):(?P<start_time_min>[0-9]{2})\ -\ (?P<end_time_hour>[0-9]{2}):(?P<end_time_min>[0-9]{2}))
                                    # Either find TBA and put that in `time` or find the hour&min of start&end time
                                 \ *.*$""", line, re.VERBOSE) # Accept an unknown number of characters tagged on since some people(AAAD 89) like to put random shit there
                start_time = None
                end_time = None
                try:
                    start_time=(int(match.group("start_time_hour"))*60+int(match.group("start_time_min")))
                    end_time=(int(match.group("end_time_hour"))*60+int(match.group("end_time_min")))
                except (TypeError, IndexError):
                    start_time = None
                    end_time = None
                self.schedule = ClassSchedule(building=match.group("building").strip(), 
                                              room=match.group("room").strip(),
                                              days=match.group("days").strip(),
                                              start_time=start_time,
                                              end_time=end_time,
                                              class_number=self.class_obj.class_number,
                                              term=self.term)
                self.state = "instructor"
                return
            if self.state == "schedule|enrollment" and line.strip().startswith("Class"):
                self.state = "enrollment"
        if self.state == "instructor":
            if len(line.strip()) == 0 or line.strip().startswith("Class Enrl"):
                self.class_obj.schedules.append(self.schedule)
                self.extras.append(self.schedule)
                self.schedule = None
                if len(line.strip()) == 0:
                    self.state = "schedule|enrollment"
                    return
                else:
                    self.state = "enrollment"
            else:
                match = re.match(r"""^ # Read from the very start to the very end(indicated by the $ at the end) of the string
                                \ +(?P<type>[A-Z]+) # Look for one or more space and then get type as capitalized letter string
                                \ +([0-9]|\.)+ # Look for one or more space and then a number(we ignore this for now bc i have no clue what the purpose of it is), or a period because apparently this can be a float
                                \ +Instructor:(?P<name>.+) # Look for one or more space and then `Instructor:` and then take the rest as the instructor name
                                $""", line, re.VERBOSE)
                self.schedule.instructors.append(get_or_create_instructor(match.group("name"), match.group("type"), self.db_session))
                return
        if self.state == "enrollment":
            if not line.strip().startswith("Class"):
                logger.error(f"Looking for enrollment but got `{line}`")
                self.errors += 1
                self.reset_state()
                return
            # TODO: Enrollment stamp
            # The indices change depending on how long the numbers are, as there are 15 character of spacing between entries
            # Enrollment_cap always starts at 21 
            match = re.match(r"""^ # Read from the very start to the very end(indicated by the $ at the end) of the string
                             \ +Class\ Enrl\ Cap:(?P<class_enrollment_cap>[0-9]+) # Look for one or more space then `Class Enrl Cap:` then find class_enrollment_cap which is one or more digits
                             \ +Class\ Enrl\ Tot:(?P<class_enrollment_tot>[0-9]+) # Look for one or more space then `Class Enrl Tot:` then find class_enrollment_tot which is one or more digits
                             \ +Class\ Wait\ Cap:(?P<class_waitlist_cap>[0-9]+) # Look for one or more space then `Class Wait Cap:` then find class_waitlist_cap which is one or more digits
                             \ +Class\ Wait\ Tot:(?P<class_waitlist_tot>[0-9]+) # Look for one or more space then `Class Wait Tot:` then find class_waitlist_tot which is one or more digits
                             \ +Class\ Min\ Enrl:(?P<class_min_enrollment>[0-9]+) # Look for one or more space then `Class Min Enrl:` then find class_min_enrollment which is one or more digits
                             \ *.*$""", line, re.VERBOSE) # Allow an unknown number of characters after a space since some people(AERO 202 Spring 2024) like to put random shit there
            # re.VERBOSE is to allow whitespace in the regex that is exclusively for readability, as well as comments!
            
            self.class_obj.enrollment_cap = int(match.group("class_enrollment_cap"))
            self.class_obj.enrollment_total = int(match.group("class_enrollment_tot"))
            self.class_obj.waitlist_cap = int(match.group("class_waitlist_cap"))
            self.class_obj.waitlist_total = int(match.group("class_waitlist_tot"))
            self.class_obj.min_enrollment = int(match.group("class_min_enrollment"))
            self.state = "waiting_for_properties"
            return
        if self.state == "waiting_for_properties":
            if line.strip() in ["GR1", "GR3", "GRZ", "CPF"]:
                self.state = "properties"
                return
            elif len(line.strip()) > 0:
                self.state = "properties"
        if self.state == "properties":
            if len(line.strip()) == 0:
                self.state = "notes"
            if line.strip().startswith("Combined Section ID:"):
                self.class_obj.combined_section_id = line[line.index(":")+1:].strip()
            if line.strip().startswith("Class Equivalents:"):
                self.class_obj.equivalents = line[line.index(":")+1:].strip()
            # Here is where we could theoretically populate the attributes(GenEds) into new course listings, but it instead should be moved into a gened credit system rather than the properties system I currently have in place.
            # TODO: Populate GenEd credits into their own table, allowing for easy and more efficient searching
            if line.strip().startswith("Reserve Capacity:"):
                self.state = "reserve_capacity"
        if self.state == "reserve_capacity":
            if len(line.strip()) == 0:
                self.state = "notes"
                return
            if line[:35].strip() not in ["", "Reserve Capacity:"]:
                self.state = "properties"
                return

            match = re.match(r"""^
                             (\ +Reserve\ Capacity:|) # Optionally include label since it only occurs on the first line
                             \ +(?P<expiration_date>[0-3][0-9]-[A-Z]{3}-[0-9]{4}) # Look for one or more space and then find expiration_date of DD-MON-YYYY
                             \ +(?P<description>\S(\S|\ \S)+) # Look for one or more space and then find description string with only one space in a row allowed
                             \ +(?P<cap>[0-9]{1,3}) # Look for one or more more space and then find cap of 1-3 digit number
                             \ +(?P<tot>[0-9]{1,3}) # Look for one or more more space and then find tot of 1-3 digit number
                             ((Reserve\ Enrl\ Cap:Reserve\ Enrl\ Tot:)|) # Optionally include the labels since those only occur on the first line
                             $""", line, re.VERBOSE)
            
            reserve_cap = ClassReserveCapacity(
                class_number=self.class_obj.class_number,
                term=self.term,
                expire_date=datetime.datetime.strptime(match.group("expiration_date"), "%d-%b-%Y"),
                description=match.group("description"),
                enroll_cap=int(match.group("cap")),
                enroll_total=int(match.group("tot")))
            self.extras.append(reserve_cap)
            if self.class_obj.reserve_capacities is None:
                self.class_obj.reserve_capacities = []
            self.class_obj.reserve_capacities.append(reserve_cap)
        if self.state == "notes":
            if line.startswith(pdf_split_line):
                self.state = "first_line"

                self.db_session.add_all(self.extras)
                if self.course is not None:
                    self.db_session.add(self.course)
                self.db_session.add(self.class_obj)
                logger.debug(f"Adding class {self.class_obj.course_id} - {self.class_obj.class_section} ({self.class_obj.class_number})")
                return
            if len(line.strip()) > 0:
                self.class_notes.append(line.strip)


# Read through the directory of class listings
def process_pdfs():
    logger.debug("Getting directory of pdfs")

    response = requests.get("https://registrar.unc.edu/courses/schedule-of-classes/directory-of-classes-2/")

    soup = BeautifulSoup(response.content, "html.parser")

    for ssb_link in tqdm(soup.select(".main div > ul > li > a"), position=0, leave=False, desc="PDFs"):
        source = ssb_link["href"]
        term = ssb_link.text.upper().replace(" ", "_")
        parser = PDFParser(term, source)

        logger.info(f"Found ssb with term {term}")

        db_session = scoped_session(session_factory)

        term_data = db_session.scalar(select(TermData).filter_by(name=term))
        if term_data is None:
            logger.warning(f"Found a new term `{term}`, creating placeholder entry in term_data.")
            db_session.add(TermData(name=term))

        term_data_source = db_session.scalar(select(TermDataSource).filter_by(term_name=term, source="pdf"))
        if term_data_source is None:
            logger.warning(f"Found a new pdf term `{term}`, creating a new entry in term_data_source")
            db_session.add(TermDataSource(source="pdf", term_name=term, raw_term_name=ssb_link.text, last_seen=datetime.datetime.now()))
        else:
            term_data_source.last_seen = datetime.datetime.now()

        db_session.commit()
        db_session.close()
        parser.parse(force=True)


if __name__ == "__main__":
    from database import init_db
    init_db()

    # TODO: Add the rest of the processing
    # TODO: Connect to a temporary database at first, then move everything over to the live database once all processing is done and successful
    # TODO: Log to file
    # TODO: Print out the total number of generated course entries in pdf and search processing
    # FIXME: nothing seems to be getting written
    process_pdfs()