# coding=utf-8
from collections import namedtuple
import random
import string
import weakref


class CachedProperty(object):
    """
    缓存属性的装饰器，从django抄的，
    详见https://docs.djangoproject.com/en/1.9/ref/utils/#module-django.utils.functional
    """
    def __init__(self, func, name=None):
        self.func = func
        self.__doc__ = getattr(func, '__doc__')
        self.name = name or func.__name__

    def __get__(self, instance, type=None):
        if instance is None:
            return self
        res = instance.__dict__[self.name] = self.func(instance)
        return res

cached_property = CachedProperty


def get_random_string(length=32, allowed_chars=string.ascii_lowercase + string.digits):
    """
    产生随机字符串，详见python cookbook
    :param length: 字符串长度
    :param allowed_chars: 字符串集合
    :return:
    """
    return ''.join(random.choice(allowed_chars) for i in range(length))


class Flow(object):
    """
    因为http是无状态的,so加入了这个，自适应测验流程的相关方法、属性

    >>> flow = Flow(name='abc', flow='3|4|5')
    >>> flow.level_list
    [3, 4, 5]
    >>> flow.level_len
    3
    >>> flow.total_item_count
    12
    >>> flow.get_level_item_count(1)
    3
    >>> flow.get_level_item_count(2)
    4
    >>> flow.get_level_item_count(3)
    5
    >>> flow.get_below_level_item_count(1)
    3
    >>> flow.get_below_level_item_count(2)
    7
    >>> flow.get_below_level_item_count(3)
    12
    """

    _cache = weakref.WeakValueDictionary()

    def __init__(self, name, flow, sep='|'):
        """
        初始化
        :param flow: 形如'3|4|5'的字符串, str
        :param sep: 形如'|'的分隔符, str
        """
        if not isinstance(flow, str):
            raise TypeError(u'flow必须为字符串')
        if not isinstance(sep, str):
            raise TypeError(u'分隔符sep必须为字符串')
        if sep not in flow:
            raise ValueError(u"没有在flow里面发现%s字符" % sep)
        if flow.startswith(sep) or flow.endswith(sep):
            raise ValueError(u"%s不能出现在flow的开头或结尾")
        # 层级列表
        _level_list = flow.split(sep)
        try:
            self.level_list = [int(_) for _ in _level_list]
        except ValueError:
            raise ValueError(u"flow中的非%s字符必须是数字" % sep)

    @cached_property
    def total_item_count(self):
        # 测验流程中总共需要做多少题
        level_list = self.level_list
        return sum(level_list)

    @cached_property
    def level_len(self):
        # 总层数
        level_list = self.level_list
        return len(level_list)

    def get_level_item_count(self, _round):
        # 第X层的题量
        levels = self.level_list
        return levels[_round - 1]

    def get_below_level_item_count(self, _round):
        """
        截止第X层之前，总计需要做的题量，包括1,2，。。。x这些层所有的题量
        :param _round: 整数，第几层, 和内置函数round冲突了，所以前面有下划线
        :return: 题量
        """
        levels = self.level_list
        return sum(levels[:_round])

    def __new__(cls, name, flow, sep='|'):
        if name not in cls._cache:
            instance = super(Flow, cls).__new__(cls)
            cls._cache[name] = instance
        return cls._cache[name]

def get_quiz_stage(step, stage, flow):
    """
    确定目前测验处于的阶段
    :param step: 整数，测验所做试题量
    :param stage:整数，测验所处阶段
    :param flow: Flow的实例
    :return:整数，测验应该所处阶段

    >>> flow = Flow('3|4|5')
    >>> get_quiz_stage(3, 1, flow)
    2
    >>> get_quiz_stage(2, 1, flow)
    1
    >>> get_quiz_stage(4, 2, flow)
    2
    """
    if not isinstance(flow, Flow):
        raise TypeError(u"flow必须是Flow的实例")
    if not isinstance(step, int):
        raise TypeError(u"step必须的整数")
    if not isinstance(stage, int):
        raise TypeError(u"stage必须是整数")

    if step == flow.get_below_level_item_count(stage):
        return stage + 1
    else:
        return stage


def get_threshold(que_obj):
    if not que_obj.thresholds:
        return que_obj.threshold
    else:
        thresholds = [float(_) for _ in que_obj.thresholds.split('|')]
        return thresholds


Que = namedtuple('que', ('id', 'question', 'slop', 'threshold', 'thresholds', 'intercept', 'choice_text',
                         'choice_value', 'count', 'a_level', 'questionnaire_id', 'row_num'))


def session_reset(session, q_id):
    # 设置为重启模式
    session['is_%s_re_start' % q_id] = True
    # 设置当前为第一道题，即第一步
    session['%s_step' % q_id] = 1
    # 设置当前为第一阶段
    session['%s_stage' % q_id] = 1
    # 初始化启动位置
    session['start_%s' % q_id] = None
    # 初始化当前所答试题id
    session['q_%s_id' % q_id] = None
    # 初始化试题参数
    session['%s_a' % q_id] = []
    # 初始化试题参数
    session['%s_b' % q_id] = []
    # 初始化得分
    session['%s_score' % q_id] = []
    session['%s_step_count' % q_id] = None
    session['%s_next_item' % q_id] = None
    session['%s_x0' % q_id] = None


def del_session(session, q_id):
    # 删除测验相关键值
    del session['is_%s_re_start' % q_id]
    del session['%s_step' % q_id]
    del session['%s_stage' % q_id]
    del session['start_%s' % q_id]
    del session['q_%s_id' % q_id]
    del session['%s_a' % q_id]
    del session['%s_b' % q_id]
    del session['%s_score' % q_id]
    del session['%s_next_item' % q_id]
    del session['%s_step_count' % q_id]
    del session['%s_x0' % q_id]


def get_has_answered_que_id_list(ans, a_level):
    old_ans = ans.old_answer
    que_id_list = []
    if old_ans:
        for k, v in old_ans.items():
            if v['a_level'] == a_level:
                que_id_list.append(k)
    if a_level == 1:
        return que_id_list
    else:
        ans = ans.score_answer
        if ans:
            for k, v in ans.items():
                if v['a_level'] == a_level:
                    que_id_list.append(k)
        return que_id_list


class CheckChoice(object):
    """
    检查post的数据
    """

    def __init__(self, choice, que):
        self._choice = choice
        self._que = que
        self._value = None

    def _get_value_list(self):
        # 返回试题得分的列表
        _value_list = self._que.choice_value.split('|')
        value_list = [int(each_value.strip()) for each_value in _value_list]
        min_value = min(value_list)
        return value_list, min_value

    def is_valid(self):
        # 检查是否有效
        choice = self._choice
        value_list, min_value = self._get_value_list()
        try:
            if choice == '':
                self.value = min_value
            else:
                i = int(choice)
                self.value = value_list[i]
            return True
        except IndexError:
            return False
        except ValueError:
            return False
        except TypeError:
            return False

    def get_value(self):
        # 得到得分
        if self._value is None:
            raise ValueError(u"答案不可以为空值")
        else:
            return self._value

    def set_value(self, value):
        # 设置得分
        self._value = value

    value = property(get_value, set_value)
