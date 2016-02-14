# coding=utf-8
import numpy as np
from abc import ABCMeta, abstractmethod
import warnings
from utils import cached_property


class LogisticModel(object):
    """
    项目反应理论的基础公式， e^(a*(0-b)) / 1+e^(a*(0-b))
    """

    def __init__(self, slop, threshold, theta):
        """
        生成logistic的原始值和导数值（一阶，二阶，三阶随意）
        :param slop: 斜率，试题区分度，可以是整数、浮点数或numpy数组
        :param threshold: 阈值，试题难度，可以是整数、浮点数或numpy数组
        :param theta: 特质值，浮点或整数，或shape为（XX，1）的numpy二维数组
        """
        self.slop = slop
        self.threshold = threshold
        self.theta = theta

    @cached_property
    def prob_values(self):
        """
        e^x/(1+e^x)
        :return: logistic的值
        """
        exp = np.exp(self.slop * (self.theta - self.threshold))
        return exp / (1.0 + exp)

    @cached_property
    def d_prob_values(self):
        """
        logistic的一阶导数
        :return: logistic的一阶导数值
        """
        p = self.prob_values
        return self.slop * p * (1.0-p)

    @cached_property
    def dd_prob_values(self):
        """
        logistic二阶导数
        :return: logistic二阶导数的值
        """
        dp = self.d_prob_values
        return self.slop * dp

# =========================下面是对数似然函数============================


class LogLik:
    """
    项目反应理论的对数似然函数，抽象类
    """
    __metaclass__ = ABCMeta

    def __init__(self, score, a, b, theta, model=LogisticModel):
        """
        :param score: 得分， numpy数组
        """
        self.slop = a
        self.threshold = b
        self.theta = theta
        # logistic模型
        self.model = model(self.slop, self.threshold, self.theta)
        # 原函数
        self.p = self.model.prob_values
        # 一阶导数
        self.dp = self.model.d_prob_values
        # 二阶导数
        self.ddp = self.model.dd_prob_values
        self.score = score

    @abstractmethod
    def get_dloglik_value(self):
        """
        对数似然函数的一阶导数
        """
        pass

    @abstractmethod
    def get_ddloglik_value(self):

        """
        对数似然函数的二阶导数

        """
        pass

    def get_dddloglik_value(self):

        """
        可选，对数似然函数的三阶导数
        """
        return None


class BrmLogLik(LogLik):

    def get_ddd_prob_values(self):
        """
        :return: logistic的三阶导数
        """
        return self.slop*self.ddp

    def get_dloglik_value(self):
        return np.sum(self.slop*(self.score-self.p)) - self.theta

    def get_ddloglik_value(self):
        return (-1)*np.sum(self.ddp)-1

    def get_dddloglik_value(self):
        dddp = self.get_ddd_prob_values()
        return (-1)*np.sum(dddp)


class GrmLogLik(LogLik):

    def get_dloglik_value(self):
        # 难度值的数量加1，也是试题的得分范围
        rep_len = self.threshold.shape[1] + 1

        dloglik = 0

        for i in range(rep_len):
            _score = self.score.copy()

            # 将等级计分转换为0,1计分
            _score[_score != (i + 1)] = 0
            _score[_score == (i + 1)] = 1

            # 下面类似于P(k=1)-p(k=0)，其中k是这道题上的得分
            p_pre, dp_pre = (1, 0) if i == 0 else (self.p[:, i-1], self.dp[:, i-1])
            p, dp = (0, 0) if i == rep_len - 1 else (self.p[:, i], self.dp[:, i])
            dloglik += np.dot(_score, (dp_pre - dp) / (p_pre - p))

        return dloglik - self.theta

    def get_ddloglik_value(self):
        # 难度值的数量加1，也是试题的得分范围
        rep_len = self.threshold.shape[1] + 1
        ddloglik = 0
        for i in range(rep_len):
            # 将等级计分转换为0,1计分
            _score = self.score.copy()
            _score[_score != (i + 1)] = 0
            _score[_score == (i + 1)] = 1

            # 下面类似于P(k=1) - p(k=0),其中k是这道题上的得分
            p, dp, ddp = (0, 0, 0) if i == rep_len - 1 else (self.p[:, i], self.dp[:, i], self.ddp[:, i])
            p_pre, dp_pre, ddp_pre = (1, 0, 0) if i == 0 else (self.p[:, i-1], self.dp[:, i-1], self.ddp[:, i-1])

            left = (ddp * (2 * p - 1.0) + ddp_pre * (1.0 - 2 * p_pre)) / (p_pre - p)
            right = ((dp_pre - dp) ** 2) / ((p_pre - p) ** 2)

            ddloglik += np.dot(_score, left - right)
        return ddloglik - 1


class IRTModel(object):
    """
    IRT对数似然函数一阶导数求根，即IRT对数似然函数求极大
    """

    __metaclass__ = ABCMeta

    def __init__(self, a, b, score, loglik, zero_method):
        """
        :param a: 斜率， 区分度，整数或浮点或numpy数组
        :param b: 阈值，难度， 整数或浮点或numpy数组
        :param score: 得分，01或1234， 整数或numpy数组
        :param loglik: 对数似然类，Loglik的子类
        """
        self.loglik = loglik
        self.zero_method = zero_method
        self.a = a
        self.b = b
        self.score = score

    def get_est_theta(self, x0):
        return round(self.zero_method.get_est_result(x0=x0,
                                                     loglik=self.loglik,
                                                     a=self.a, b=self.b,
                                                     score=self.score), 3)


class IRTZeroMethod(object):
    """
    处理迭代算法，数值优化算法的类
    """

    __metaclass__ = ABCMeta

    @classmethod
    def get_est_result(cls, x0, loglik, a, b, score, max_iter, tol, *args, **kwargs):
        pass


class NewtonZeroMethod(IRTZeroMethod):
    """
    牛顿迭代（哈雷迭代类）,主要依据泰勒级数进行求根或极大
    """

    @classmethod
    def get_est_result(cls, x0, loglik, a, b, score, max_iter=50, tol=1e-5, *args, **kwargs):
        # 初始值浮点化
        p0 = x0 * 1.0
        for i in range(max_iter):
            _loglik = loglik(score=score, a=a, b=b, theta=p0)
            # 一阶导数
            f1 = _loglik.get_dloglik_value()
            # 二阶导数
            f2 = _loglik.get_ddloglik_value()
            # 三阶导数
            f3 = _loglik.get_dddloglik_value()
            if f2 == 0:
                msg = u'二阶导数非正定或为0'
                warnings.warn(msg, RuntimeWarning)
                return p0
            if f3 is None:
                # 牛顿迭代
                p = p0 - f1 / f2
            else:
                # 哈雷迭代
                discr = f2 ** 2 - 2 * f1 * f2
                if discr < 0:
                    p = p0 - f2 / f3
                else:
                    p = p0 - 2 * f1 / (f2 + np.sign(f2) * np.sqrt(discr))
            if abs(p - p0) < tol:
                return p
            p0 = p
        msg = u'经过{0}次迭代后，还是无法收敛到精度{1}'.format(max_iter, tol)
        raise RuntimeError(msg)


class BinaryResponseIrtModel(IRTModel):

    def __init__(self, *args, **kwargs):
        super(BinaryResponseIrtModel, self).__init__(loglik=BrmLogLik, zero_method=NewtonZeroMethod, *args, **kwargs)


class GradeResponseIrtModel(IRTModel):
    # TODO 测试

    def __init__(self, *args, **kwargs):
        super(GradeResponseIrtModel, self).__init__(loglik=GrmLogLik, zero_method=NewtonZeroMethod, *args, **kwargs)


class IRTInfo(object):

    __metaclass__ = ABCMeta

    @abstractmethod
    def get_item_info_list(self):
        pass

    @abstractmethod
    def get_test_info(self):
        pass


class BrmIRTInfo(IRTInfo, LogisticModel):

    def get_item_info_list(self):
        # 二级计分模型的信息函数即logistic模型的二阶导数
        p = self.prob_values
        return self.slop**2.0 * p * (1 - p)

    def get_test_info(self):
        # 测验信息函数即题目信息函数的和
        return np.sum(self.get_item_info_list())


class GrmIRTInfo(IRTInfo, LogisticModel):

    def get_item_info_list(self):
        # 多级级计分模型的信息函数公式，详见bock的书
        para_len = len(self.slop)
        _p = self.prob_values.transpose()
        _dp = self.d_prob_values.transpose()
        p = np.vstack((np.ones(para_len), _p))
        p = np.vstack((p, np.zeros(para_len)))
        dp = np.vstack((np.zeros(para_len), _dp))
        dp = np.vstack((dp, np.zeros(para_len)))
        item_info = np.sum((dp[:-1] - dp[1:])**2 / (p[:-1] - p[1:]), axis=0)
        return item_info

    def get_test_info(self):
        return np.sum(self.get_item_info_list())

if __name__ == '__main__':
    import time
    s = time.clock()
    for i in range(10000):
        theta = np.random.normal(size=1)
        a0 = np.random.uniform(1, 3, 10)
        b0 = np.random.normal(size=10)
        p = LogisticModel(a0, b0, theta).prob_values
        score0 = np.random.binomial(1, p, 10)
        t = BinaryResponseIrtModel(a=a0, b=b0, score=score0)
        t.get_est_theta(0)
    e = time.clock()
    print e - s
