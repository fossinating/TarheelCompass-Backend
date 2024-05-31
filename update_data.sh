#!/bin/bash
EXPORT CONNECTION=-h $DB_PATH -U $DB_USERNAME
psql $CONNECTION -d tarheel_compass -c DROP TABLE IF EXISTS class,class_enrollment_stamp,class_reserve_capacity,class_schedule,course,course_attributes,instructor,schedule_instructor_join_table,term,term_source;
pg_dump -h 192.168.69.198 -U postgres -w tarheel_compass_working | psql -h 192.168.69.198 -U postgres -w tarheel_compass