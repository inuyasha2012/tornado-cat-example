# tornado-cat-example
这是一个基于tornado的计算机自适应测验.数据库使用的是postgresql.

MIT授权给所有人，除了中国平安保险（集团）股份有限公司以及其子公司和母公司，禁止中国平安保险（集团）股份有限公司以及其子公司和母公司使用及抄袭

## IRT模型
* 双参数二级计分模型(Binary Response Model)
* 等级计分模型(Grade Response Model)

## 抽题策略
* a分层
* 子试题池（影子题库？）
* 信息函数
* 曝光次数

### 抽题具体方法

* a分层将测验分为n个阶段,从每个阶段抽出若干道试题,其中第一阶段是依据难度随机抽题,不计算被试特质,其他阶段依据被试特质估计值进行抽题
* 第一阶段的抽题策略是:假如第一阶段需要抽出5道题,则依据难度大小把第一层次的试题分成5份,然后从这五份子试题池中抽出5道题,
从而保证随机抽题的难度均匀分布,避免发生所抽试题太简单或太难
* 其他阶段的抽题策略是:首先计算被试的特质估计值,依据估计值,寻找估计值与试题难度值差值绝对值最小的30道题,这30道题形成一个子试题池,
计算这30道题的总共使用次数,然后计算每道题的使用次数与总共使用次数之比,以及信息函数值, 计算前者与后者的比值, 最后抽出比值最小的题.
这样抽题的好处一个是计算上节省资源,不用计算每道题的信息函数,只需计算试题池中的题目, 既考虑了测验效率又降低了试题曝光率

## 参数估计方法
极大后验均值估计(MAP)

### 极大后验均值估计与其他流行方法比较
* 相比极大似然估计(MLE),极大后验均值估计对初值不敏感, 估计也比较稳健
* 相比期望后验均值(EAP), 极大后验均值的计算速度要慢了一倍(python的for循环非常耗时)...
  * 经10000测试数据(每个数据包含10道题)检验, CORE M 0.8g的CPU下, 期望后验均值的时间是大约是2.4秒, 极大后验均值的时间大约是6秒
  * 验证方法:
    * ```$ python irt.py```
    * ```$ python eap.py```

## 答题流程
* 进入首页,随意点击测验列表中的测验
![](https://github.com/inuyasha2012/MyImage/blob/master/image/list.png)
* 答题界面包含答题进度条,倒计时进度条,题干,选项
![](https://github.com/inuyasha2012/MyImage/blob/master/image/time.png)
* 鼠标悬停答题进度条,会显示还剩多少题
![](https://github.com/inuyasha2012/MyImage/blob/master/image/remain.png)
* 鼠标悬停题干,会显示当前试题的试题参数
![](https://github.com/inuyasha2012/MyImage/blob/master/image/para.png)
* 鼠标悬停选项, 会显示当前选项的得分情况
![](https://github.com/inuyasha2012/MyImage/blob/master/image/choice.png)
* 当未选中选项时,鼠标悬停按钮,会提升必须选中选项
![](https://github.com/inuyasha2012/MyImage/blob/master/image/button.png)
* 当题目作答完毕,会跳转到结果页面
![](https://github.com/inuyasha2012/MyImage/blob/master/image/result.png)

## 其他事项
* 答题过程中,若刷新页面,会重新作答测验,并且会保存你之前作答记录,所以重写作答的测验所抽试题与之前不重复
  * 如果刷新页面的过程中顺带删除了cookie中的sessionid,上述结论作废
* 若点击了浏览器的后退前进按钮,则也会重新开始测验,且试题不重复

## 数据模型

### 为什么选用postgresql
* postgresql自带json类型, 可以方便存储和查询.当然不用json类型也可以,一是数据纵向发展,但太消耗资源
二是也采用横向发展的策略,但是查询就便的很困难和消耗资源
* postgresql有很多的数学函数和统计函数
* postgresql的python适配器psycopg2原生支持异步

### 模型详解
#### questionnaire表
列名  | 解释
------------- | -------------
name  | 测验名称
type  | 测验计分类型，二级计分或多级计分
flow  | 测验流程，例如'5,4,3'代表第一阶段答5题，第二阶段答4题，第三阶段答3题
level_one_count | a分层把试题分为了多个层次，其实第一层次的题量保存在这里
second | 每一题答题所限时间，单位为秒

#### question表
列名  | 解释
------------- | -------------
question  | 题干
slop | 区分度值
threshold | 难度值
thresholds | 多个难度值，形如'1.0,-1.1,0.9'，其中,是分隔符
choice_text | 选项，例子参见测试数据
choice_value | 选定得分， 例子参加测试数据
count | 试题的曝光次数
a_level | 试题所在层次

## require
* python 2.7.x
* postgresql 9.4
* tornado 4.x
* psycopg2 2.6
* momoko 2.x
* numpy


## 使用方法
```
$ git clone https://github.com/inuyasha2012/tornado-cat-example.git

$ cd tornado-cat-example

$ pip install requirements.txt
```

通过createdb命令或pgadmin3图形界面创建数据库

按照注释修改settings.py

```
$ cd example
```

创建表

```
$ python create_table.py
```
导入试测数据

```
$ python import_data.py
```

启动服务

```
$ python main.py
```

## TODO LIST
* 单元测试
* 基于memcached或redis的session
* 三参数模型, 速度参数模型, 展开模型, 名称模型等等
* 基于momoko的orm

## 联系方式
Email: inuyasha021@163.com
