# coding=utf-8
from abc import ABCMeta, abstractmethod
from psycopg2.extras import Json
from tornado import gen
from tornado.web import HTTPError
import numpy as np
from irt import GrmIRTInfo, GradeResponseIrtModel, BrmIRTInfo, BinaryResponseIrtModel
from utils import Flow, get_has_answered_que_id_list, del_session, get_threshold
import random


@gen.coroutine
def get_level_one_item(ans, session, q, level_one_count, db):
    """
    选出第一层的题目
    :param ans:
    :param session:
    :param q: 问卷对象
    :param level_one_count: 第一层待抽的题目数量
    :return: 返回第一次抽取的题目对象
    """
    que = None

    # 测验ID
    q_id = q.id

    # 生成答题者已经做过的题目的id列表
    can_not_in_choices_index = get_has_answered_que_id_list(ans, 1)

    # 第一层题库的题量
    _count = q.level_one_count - len(can_not_in_choices_index)

    # 没题目直接封权限
    if _count < level_one_count:
        raise HTTPError(403)

    # 题量/待抽题量，确定每道试题抽取题库的范围
    _slice = _count / level_one_count

    # json field
    # 选出来的题目放入这个字典
    selected_que_dict = {}
    # 选出来的题名顺序放入这个字典
    order_que = {}
    # 第一阶段的试题存入session的列表
    next_item_list = []

    choice_question_index_list = []

    for i in range(level_one_count):
        # 上界
        pre = _slice * i + 1
        # 下界
        nxt = _slice * (i + 1)
        try:
            choice_question_index = random.choice(xrange(pre, nxt))
        except IndexError:
            choice_question_index = i + 1
        choice_question_index_list.append(choice_question_index)

    if not can_not_in_choices_index:
        cursor = yield db.execute("""
                select * from (select *, row_number() over(order by threshold) row_num from question
                where questionnaire_id=%s and a_level=%s ) as temp
                where row_num in %s
                """, (q.id, 1, tuple(choice_question_index_list)))
    else:
        cursor = yield db.execute("""
                select * from (select *, row_number() over(order by threshold) row_num from question
                where questionnaire_id=%s and a_level=%s and not (id in %s) ) as temp
                where row_num in %s
                """, (q.id, 1, tuple(can_not_in_choices_index), tuple(choice_question_index_list)))

    use_question_list = cursor.fetchall()

    for i, use_question in enumerate(use_question_list):
        # 保存试题参数到session
        session['%s_a' % q_id].append(use_question.slop)
        session['%s_b' % q_id].append(get_threshold(use_question))
        # oder_que的key
        index_key = i + 1
        order_que[index_key] = use_question.id
        selected_que_dict[use_question.id] = {'a_level': 1,
                                              'slop': use_question.slop,
                                              'threshold': get_threshold(use_question)}
        if i == 0:
            que = use_question
        else:
            next_item_list.append(use_question)

    ans.score_answer.update(selected_que_dict)
    ans.order_answer.update(order_que)
    # session存入下面题目
    session['%s_next_item' % q.id] = next_item_list
    raise gen.Return(que)


@gen.coroutine
def get_level_others_items(session, q_id, est_theta, shadow_bank, ans, db):
    """
    选出其他层的题目
    :param session:
    :param q_id:
    :param ans:
    :param est_theta:估计特质
    :param shadow_bank: 影子题库class
    :return:问题对象
    """

    # 当前测验所属层数（阶段）
    level = session['%s_stage' % q_id]

    # 该层已作答试题列表
    # 修改为适合json field
    # 不该出现于待抽提的题目ID列表
    a_level = int(level)
    not_in_index_list = get_has_answered_que_id_list(ans, a_level=a_level)

    # 抽出来的题
    que = yield shadow_bank(q_id, a_level, est_theta, not_in_index_list, db).get_que()


    # 保存试题参数到session
    session['%s_a' % q_id].append(que.slop)
    session['%s_b' % q_id].append(get_threshold(que))

    # 返回试题
    raise gen.Return(que)


class BaseShadowBank:
    __metaclass__ = ABCMeta

    def __init__(self, q_id, a_level, est_theta, not_in_index, db):
        """
        影子题库
        :param questions: 待抽题对象列表
        :param est_theta: 估计参数
        :param not_in_index: 不该进入抽题的题目id列表
        :return: 抽出来的题
        """

        self.est_theta = est_theta

        self.q_id = q_id

        self.a_level = a_level

        self.not_in_index = not_in_index

        self.db = db

    @abstractmethod
    def get_que(self):
        # 抽题
        pass


class BrmShadowBank(BaseShadowBank):
    @gen.coroutine
    def get_que(self):
        theta = self.est_theta
        q_id = self.q_id
        a_level = self.a_level
        not_in_index = self.not_in_index

        if not not_in_index:

            query = '''
                    with temp1 as (
                        with temp as (select *, row_number() over(order by (abs(threshold-%s))) row_num
                            from question where questionnaire_id=%s and a_level=%s )
                        select * from temp where row_num < 31)
                    select * from temp1 ORDER BY (count / ((select sum(count) from temp1) + 1.0)) / ((slop ^ 2) / ((1 + exp(slop * (threshold-%s))) * (1 + exp(slop*(%s - threshold))))) limit 1
                    '''
            cursor = yield self.db.execute(query, [theta, q_id, a_level, theta, theta])

        else:
            query = '''
                    with temp1 as (
                        with temp as (select *, row_number() over(order by (abs(threshold-%s))) row_num
                            from question where questionnaire_id=%s and a_level=%s and not (id in %s ))
                        select * from temp where row_num < 31)
                    select * from temp1 ORDER BY (count / ((select sum(count) from temp1) + 1.0)) / ((slop ^ 2) / ((1 + exp(slop * (threshold-%s))) * (1 + exp(slop*(%s - threshold))))) limit 1
                    '''
            cursor = yield self.db.execute(query, [theta, q_id, a_level, tuple(not_in_index), theta, theta])

        q = cursor.fetchone()
        if q:
            raise gen.Return(q)
        else:
            HTTPError(403)


class GrmShadowBank(BaseShadowBank):
    @gen.coroutine
    def get_que(self):

        shadow_questions = yield self.get_shadow_question_list()
        count_array, info_array = self.get_count_and_info_values_list(shadow_questions)

        total_count = np.sum(count_array)

        if total_count > 0:
            # 抽取使用率最低的题目
            index_min = ((count_array / total_count) / info_array).argmin()
            qs = shadow_questions[index_min]
        else:
            qs = shadow_questions[0]
        raise gen.Return(qs)

    @gen.coroutine
    def get_shadow_question_list(self):
        q_id = self.q_id
        a_level = self.a_level
        not_in_index = self.not_in_index
        if not not_in_index:
            cursor = yield self.db.execute(
                """
                with temp as (select *, row_number() over(order by (abs(threshold-%s))) row_num
                from question where questionnaire_id=%s and a_level=%s )
                select * from temp where row_num < 31
                """,
                (self.est_theta, q_id, a_level)
            )
        else:
            cursor = yield self.db.execute(
                """
                with temp as (select *, row_number() over(order by (abs(threshold-%s))) row_num
                from question where questionnaire_id=%s and a_level=%s and not (id in %s ))
                select * from temp where row_num < 31
                """,
                (self.est_theta, q_id, a_level, tuple(not_in_index))
            )

        shadow_question_list = cursor.fetchall()
        raise gen.Return(shadow_question_list)

    def get_count_and_info_values_list(self, shadow_questions):
        a_array = np.array([])
        b_array = np.array([])
        count_array = np.array([])
        for que in shadow_questions:
            a_array = np.append(a_array, que.slop)
            b_array = np.append(a_array, get_threshold(que))
            count_array = np.append(count_array, que.count)
        # 下面将斜率变成二维数组,才能计算,否则会跳出不能计算的异常
        a_array.shape = a_array.shape[0], 1
        return count_array, GrmIRTInfo(a_array, b_array, self.est_theta).get_item_info_list()


class BaseSelectQuestion:
    __metaclass__ = ABCMeta

    def __init__(self, session, q, que_id, ans, db):
        """

        :param session:
        :param ans:
        :param db:
        :param q: 问卷对象，model对象
        :param que_id: 问卷id，整数
        """
        self.session = session
        self.q = q
        self.que_id = que_id
        self.q_id = q.id
        self.a = None
        self.b = None
        self.score = None
        self.theta = None
        self.ans = ans
        self.db = db

    @gen.coroutine
    def get_que_then_redirect(self):
        q = self.q
        q_id = self.q_id
        que_id = self.que_id
        db = self.db
        ans = self.ans
        session = self.session
        # 将是否重启测验设定为false
        session['is_%s_re_start' % q_id] = False
        # 下面是第一阶段抽题
        if session['%s_stage' % q_id] == 1:
            yield db.execute("UPDATE answer SET order_answer=%s, score_answer=%s WHERE id=%s",
                             (Json(ans.order_answer), Json(ans.score_answer), ans.aid))
            raise gen.Return('/cat/%s' % q_id)
        else:
            # 获取已作答项目参数
            self.a = np.array(session['%s_a' % q_id])
            self.b = np.array(session['%s_b' % q_id])
            self.score = np.array(session['%s_score' % q_id])

            # 计算潜在特质
            self.theta = self.get_theta()
            # 计算误差
            info = self.get_info()

            # 保存误差和潜在特质的值
            # 修改为适合json field
            ans.score_answer[str(que_id)].update({'info': info, 'theta': self.theta})
            # 被试答题过程
            flow = Flow(q.flow)

            if session['%s_stage' % q_id] == flow.level_len + 1:
                # 上面是结束规则
                yield db.execute("UPDATE answer SET theta=%s, info=%s, has_finished=%s,"
                                 "order_answer=%s, score_answer=%s WHERE id=%s",
                                 (self.theta, info, True, Json(ans.order_answer), Json(ans.score_answer), ans.aid))

                # 删除所有测验相关session键值
                del_session(session, q_id)

                # 返回到问卷列表页面
                raise gen.Return('/result/%s' % q_id)
            else:
                # 第二阶段抽题
                que = yield get_level_others_items(session, q_id, self.theta, self.get_shadow_bank(), ans, db)
                session['q_%s_id' % q_id] = que
                level = session['%s_stage' % q_id]
                index_key = session['%s_step' % q_id] + 1
                ans.score_answer[str(que.id)] = {'a_level': level,
                                                 'slop': que.slop,
                                                 'threshold': get_threshold(que)}
                session['%s_next_item' % q_id] = que
                ans.order_answer[index_key] = que.id
                yield db.execute("UPDATE answer SET order_answer=%s, score_answer=%s WHERE id=%s",
                                 (Json(ans.order_answer), Json(ans.score_answer), ans.aid))
                raise gen.Return('/cat/%s' % q_id)

    @abstractmethod
    def get_shadow_bank(self, *args, **kwargs):
        # 影子题库
        pass

    @abstractmethod
    def get_theta(self, *args, **kwargs):
        # 返回参数估计值,这里放参数估计算法
        pass

    @abstractmethod
    def get_info(self):
        # 返回信息函数计算值
        pass


class BrmSelectQuestion(BaseSelectQuestion):
    def get_shadow_bank(self):
        return BrmShadowBank

    def get_theta(self):
        return BinaryResponseIrtModel(a=self.a, b=self.b, score=self.score).get_est_theta(0)

    def get_info(self):
        return BrmIRTInfo(self.a, self.b, self.theta).get_test_info()


class GrmSelectQuestion(BaseSelectQuestion):
    def get_shadow_bank(self):
        return GrmShadowBank

    def get_theta(self):
        # 斜率的维度需要改变
        self.a.shape = self.a.shape[0], 1
        if self.session['%s_x0' % self.q_id] is not None:
            # 用前一个参数估计结果作为初始估计值,否则会不收敛出错
            theta = GradeResponseIrtModel(a=self.a, b=self.b, score=self.score).get_est_theta(
                self.session['%s_x0' % self.q_id])
        else:
            # 对前三道题的参数估计,用0作为初值
            theta = GradeResponseIrtModel(a=self.a, b=self.b, score=self.score).get_est_theta(0)
        # 将估计出来的theta值存入session，待下次调用
        self.session['%s_x0' % self.q_id] = theta
        return theta

    def get_info(self):
        return GrmIRTInfo(self.a, self.b, self.theta).get_test_info()


class SelectQuestion(object):
    grm = GrmSelectQuestion
    brm = BrmSelectQuestion
