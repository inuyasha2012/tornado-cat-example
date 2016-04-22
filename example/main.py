# coding=utf-8
from psycopg2.extras import NamedTupleCursor, Json
from tornado.web import Application, HTTPError
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.options import parse_command_line
import momoko
import os
from bank import SelectQuestion, get_level_one_item
from base import BaseHandler, SessionBaseHandler
from settings import MAX_ANSWER_COUNT, DSN, COOKIE_SECRET
from utils import Flow, get_quiz_stage, Que, session_reset, CheckChoice


class QuestionnaireListHandler(BaseHandler):
    @gen.coroutine
    def get(self):
        # 问卷列表
        cursor = yield self.db.execute("SELECT id, name FROM questionnaire;")
        q_list = cursor.fetchall()
        self.render('index.html', q_list=q_list)


class QuestionHandler(SessionBaseHandler):

    @gen.coroutine
    def _check_q_exist_n_get_q_a(self, q_id):
        """
        :param q_id:
        :raise gen.Return: 返回去q_a,q是questionnaire,a是answer
        """
        session_key = self.session_key
        cursor = yield self.db.execute(
            """
            SELECT answer.id as aid, answer.score_answer, answer.old_answer,
            answer.order_answer, answer.try_count,
            answer.has_finished, questionnaire.id, questionnaire.type, questionnaire.second,
            questionnaire.flow, questionnaire.level_one_count from answer
            INNER JOIN questionnaire ON answer.questionnaire_id = questionnaire.id
            WHERE answer.questionnaire_id=%s
            AND answer.session_key=%s;
            """, (q_id, session_key)
        )
        # q_a的意思是questionnaire and answer
        q_a = cursor.fetchone()
        if not q_a:
            cursor = yield self.db.execute("SELECT id, type, flow, level_one_count, second "
                                           "FROM questionnaire WHERE id=%s;",
                                           (q_id,))
            q = cursor.fetchone()

            if q:

                cursor = yield self.db.execute("INSERT INTO answer (questionnaire_id, session_key, "
                                               "score_answer, order_answer, old_answer) VALUES (%s, %s, %s, %s, %s)"
                                               "RETURNING id AS aid, score_answer, "
                                               "order_answer, old_answer, try_count, "
                                               "has_finished;",
                                               (q_id, session_key, Json({}), Json({}), Json({})))
                ans = cursor.fetchone()
                raise gen.Return((q, ans))
            else:
                raise HTTPError(404)
        else:
            raise gen.Return((q_a, q_a))

    @gen.coroutine
    def get(self, q_id):
        session = self.session
        q_a = yield self._check_q_exist_n_get_q_a(q_id)
        q, ans = q_a

        # 下面是session的键值
        is_re_start = 'is_%s_re_start' % q_id
        step = '%s_step' % q_id
        stage = '%s_stage' % q_id
        next_item = '%s_next_item' % q_id
        step_count = '%s_step_count' % q_id

        # 被试答题的过程
        flow = Flow(flow=q.flow, name=session.session_key)

        # 如果session不存在is_X_start_id，说明被试可能关闭了浏览器，所以重新启动测验
        if not session.get(is_re_start, True):
            # 判断测验的第一阶段是否处于结束位置
            if session[stage] == 1:
                next_item_list = session[next_item]
                que = Que(*next_item_list.pop(0))

            else:
                next_item = session[next_item]
                que = Que(*next_item)
            # 将是否重新测验设定为真，则若关闭浏览器或刷新页面，则重启测验
            session[is_re_start] = True
            session[step] += 1
            session[stage] = get_quiz_stage(session[step], session[stage], flow)
        else:
            # 开始测验或重启测验，session恢复出厂设置
            session_reset(session, q_id)
            # 测验作答次数+1
            if ans.try_count > (MAX_ANSWER_COUNT - 1):
                raise HTTPError(403)
            # 之前的旧答案存入old_answer中
            if ans.score_answer:
                ans.old_answer.update(ans.score_answer)
                ans.score_answer.clear()
                ans.order_answer.clear()
            # 第一阶段需要回答的题量
            count = flow.get_level_item_count(1)
            # 给用户展现的第一道试题
            que = yield get_level_one_item(ans, session, q, count, self.db)
            yield self.db.execute(
                "UPDATE answer SET has_finished = false, try_count = try_count + 1, score_answer=%s, order_answer=%s, "
                "old_answer=%s WHERE id=%s",
                (Json(ans.score_answer), Json(ans.order_answer), Json(ans.old_answer), ans.aid)
            )
            # 总共答题量
            session[step_count] = flow.total_item_count
        yield self.db.execute("UPDATE question SET count = count + 1 WHERE id=%s", (que.id, ))
        total_step_count = session[step_count]
        current_step = session[step]
        current_progress = int((current_step * 1.0 / total_step_count) * 100)
        second = q.second
        session['q_%s_id' % q_id] = que
        yield self.save()
        self.render('cat.html', que=que, current_progress=current_progress,
                    total_step_count=total_step_count, current_step=current_step,
                    q_id=q_id, second=second)

    @gen.coroutine
    def post(self, q_id):
        session = self.session
        q_a = yield self._check_q_exist_n_get_q_a(q_id)
        q, ans = q_a
        q_type = q.type
        que = Que(*session.get('q_%s_id' % q_id))
        que_choice = self.get_argument('question')
        check_choice = CheckChoice(que_choice, que)
        if check_choice.is_valid():
            # 保存作答结果
            value = check_choice.value
            session['%s_score' % q_id].append(int(value))
            ans.score_answer[str(que.id)]['score'] = value
            ans.score_answer[str(que.id)]['choice'] = que_choice
            # 生成重定向URL
            SelectQuestionClass = getattr(SelectQuestion, q_type)
            url = yield SelectQuestionClass(session=session, q=q, que_id=que.id,
                                            ans=ans, db=self.db).get_que_then_redirect()
            yield self.save()
            self.redirect(url)
        else:
            # 数据不合格则返回原作答页面
            current_step = session['%s_step' % q_id]
            total_step_count = session['%s_step_count' % q_id]
            current_progress = int((current_step * 1.0 / total_step_count) * 100)
            second = q.second
            self.render('cat.html', que=que, current_progress=current_progress,
                        total_step_count=total_step_count, current_step=current_step,
                        q_id=q_id, second=second)


class ResultHandler(BaseHandler):
    @gen.coroutine
    def _check_result_exist_n_get_q_a(self, q_id):
        session_key = self.get_cookie('sessionid')
        if not session_key:
            raise HTTPError(404)
        cursor = yield self.db.execute(
            """
            SELECT answer.score_answer, answer.order_answer, answer.has_finished from answer
            INNER JOIN questionnaire ON answer.questionnaire_id = questionnaire.id
            WHERE answer.questionnaire_id=%s
            AND answer.session_key=%s;
            """, (q_id, session_key)
        )
        # q_a的意思是questionnaire and answer
        q_a = cursor.fetchone()
        if (not q_a) or (not q_a.has_finished):
            raise HTTPError(404)
        else:
            raise gen.Return(q_a)

    @gen.coroutine
    def get(self, q_id):
        q_a = yield self._check_result_exist_n_get_q_a(q_id)
        self.render('result.html', q_a=q_a, q_id=q_id)


if __name__ == "__main__":
    parse_command_line()
    ioloop = IOLoop.instance()
    application = Application([
        (r"/", QuestionnaireListHandler),
        (r"/cat/(\d+)", QuestionHandler),
        (r"/result/(\d+)", ResultHandler)
    ],
        template_path=os.path.join(os.path.dirname(__file__), "templates"),
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        cookie_secret=COOKIE_SECRET,
        debug=True,
        xsrf_cookies=True,
    )
    application.db = momoko.Pool(
        dsn=DSN,
        size=1,
        ioloop=ioloop,
        cursor_factory=NamedTupleCursor,
    )

    future = application.db.connect()
    ioloop.add_future(future, lambda f: ioloop.stop())
    ioloop.start()
    future.result()

    http_server = HTTPServer(application)
    http_server.listen(8000, 'localhost')
    ioloop.start()
