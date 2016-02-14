# coding=utf-8
import psycopg2
from settings import DSN
# TODO 添加索引

create_table_sql_query = """
                         BEGIN;
                         CREATE TABLE "session" ("session_key" varchar(40) NOT NULL PRIMARY KEY,
                                                 "session_data" jsonb NOT NULL);
                         CREATE TABLE "questionnaire" ("id" serial NOT NULL PRIMARY KEY,
                                                       "name" varchar(200) NOT NULL,
                                                       "type" varchar(20) NOT NULL,
                                                       "flow" varchar(20) NOT NULL,
                                                       "level_one_count" integer NULL,
                                                       "second" integer NOT NULL DEFAULT 30);
                         CREATE TABLE "question" ("id" serial NOT NULL PRIMARY KEY,
                                                  "question" text NOT NULL,
                                                  "slop" double precision NULL,
                                                  "threshold" double precision NULL,
                                                  "thresholds" varchar(200) NULL,
                                                  "intercept" double precision NULL,
                                                  "choice_text" text NOT NULL,
                                                  "choice_value" varchar(20) NOT NULL,
                                                  "count" integer NOT NULL DEFAULT 0,
                                                  "a_level" integer NOT NULL,
                                                  "questionnaire_id" integer REFERENCES questionnaire NOT NULL);
                         CREATE TABLE "answer" ("id" serial NOT NULL PRIMARY KEY,
                                                "questionnaire_id" integer REFERENCES questionnaire NOT NULL,
                                                "session_key"  varchar(40) REFERENCES session NOT NULL,
                                                "has_finished" boolean NOT NULL DEFAULT false,
                                                "try_count" integer NOT NULL DEFAULT 0,
                                                "theta" double precision NULL,
                                                "info" double precision NULL,
                                                "old_answer" jsonb NULL,
                                                "order_answer" jsonb NULL,
                                                "score_answer" jsonb NULL);
                         COMMIT;
                         """

try:
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute(create_table_sql_query)
except psycopg2.ProgrammingError as e:
    print e
except psycopg2.OperationalError as e:
    print e