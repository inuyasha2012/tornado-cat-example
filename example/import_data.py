# coding=utf-8
import psycopg2
import os.path
from settings import DSN

BASE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')


def import_csv(dsn, table_name, file_name, columns=None):
    """
    往postgresql导入csv数据
    :param dsn:
    :param table_name: 表名, str
    :param file_name: 文件名, str
    :param columns:
    """
    conn = psycopg2.connect(dsn)
    cursor = conn.cursor()
    path = os.path.join(BASE_DIR, file_name)
    _file = file(path)
    cursor.copy_from(_file, table_name, sep=",", columns=columns)
    conn.commit()
    _file.close()


if __name__ == '__main__':
    import_csv(DSN, 'questionnaire',
               'q.csv', ('id', 'name', 'type', 'flow', 'level_one_count'))
    import_csv(DSN, 'question',
               'brm-que.csv', ('id', 'question', 'slop', 'threshold', 'choice_text', 'choice_value', 'a_level',
                               'questionnaire_id'))
    import_csv(DSN, 'question',
               'grm-que.csv', ('id', 'question', 'slop', 'threshold', 'thresholds',
                               'choice_value', 'choice_text', 'a_level', 'questionnaire_id'))
