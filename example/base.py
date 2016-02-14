# coding=utf-8
from tornado import gen
from utils import get_random_string
from tornado.web import RequestHandler
from psycopg2.extras import Json
from psycopg2 import IntegrityError

class BaseHandler(RequestHandler):

    @property
    def db(self):
        # 数据库
        return self.application.db


class SessionBaseHandler(BaseHandler):

    # TODO 需要更快的基于memcached或redis的session,且支持异步
    # session

    @gen.coroutine
    def prepare(self):
        # 类似于middleware的作用, 为Handler类绑定session
        # 为了防止浏览器的后退前进按钮导致试题重复出现,所以添加header
        self.add_header('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
        self.session_key, self.session = yield self._get_session()

    @gen.coroutine
    def _get_init_db_session(self):
        """
        初始化session,往数据库session表插入session记录
        往浏览器写入sessionid
        :raise gen.Return: session_key, 字符串
        """
        while True:
            session_key = get_random_string()
            try:
                yield self.db.execute("INSERT INTO session (session_key, session_data) VALUES (%s,%s)",
                                      (session_key, Json({})))
                self.set_cookie('sessionid', session_key)
                raise gen.Return(session_key)
            except IntegrityError:
                continue

    @gen.coroutine
    def _get_session(self):
        """
        得到session_key和session
        :raise gen.Return: session_key, session_data
        """
        session_key = self.get_cookie('sessionid')
        if session_key:
            cursor = yield self.db.execute("SELECT * FROM session WHERE session_key=%s",
                                           (session_key,))
            session = cursor.fetchone()
            if session:
                session_key = session.session_key
                session = session.session_data
                raise gen.Return((session_key, session))
        session_key = yield self._get_init_db_session()
        raise gen.Return((session_key, {}))

    @gen.coroutine
    def save(self):
        # 保存session数据
        session_key = self.session_key
        session_data = self.session
        yield self.db.execute("UPDATE session SET session_data = %s WHERE session_key = %s;",
                              (Json(session_data), session_key))