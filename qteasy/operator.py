# coding=utf-8
# operator.py

# ======================================
# This file contains Operator class, that
# merges and applies investment strategies
# to generate operation signals with
# given history data.
# ======================================
import warnings

import numpy as np
from .finance import CashPlan
from .history import HistoryPanel
from .utilfuncs import str_to_list
from .strategy import Strategy
from .built_in import AVAILABLE_BUILT_IN_STRATEGIES, BUILT_IN_STRATEGIES
from .blender import blender_parser


class Operator:
    """交易操作生成类，通过简单工厂模式创建择时属性类和选股属性类，并根据这两个属性类的结果生成交易清单

    根据输入的参数生成Operator对象，在对象中创建相应的策略类型:

    input:
            :param strategies: 一个包含多个字符串的列表，表示不同策略
            :param signal_type: 信号生成器的类型，可以使用三种不同的信号生成器，分别生成不同类型的信号：
                                pt：positional target，生成的信号代表某种股票的目标仓位
                                ps：proportion signal，比例买卖信号，代表每种股票的买卖百分比
                                VS：volume signal，数量买卖信号，代表每种股票的计划买卖数量

        Operator对象其实就是若干个不同类型的操作策略的容器对象，
        在一个Operator对象中，可以包含任意多个"策略对象"，而运行Operator生成交易信号的过程，就是调用这些不同的交易策略，并通过
        不同的方法对这些交易策略的结果进行组合的过程

        目前在Operator对象中支持三种信号生成器，每种信号生成器用不同的策略生成不同种类的交易信号：

        在同一个Operator对象中，每种信号生成器都可以使用不同种类的策略：

         Gen  \  strategy  | RollingTiming | SimpleSelecting | Simple_Timing | FactoralSelecting |
         ==================|===============|=================|===============|===================|
         Positional target |       Yes     |        Yes      |       Yes     |        Yes        |
         proportion signal |       Yes     |        Yes      |       Yes     |        Yes        |
         volume signal     |       Yes     |        Yes      |       Yes     |        Yes        |

        ==五种策略类型==

        目前Operator支持四种不同类型的策略，它们并不仅局限于生成一种信号，不同策略类型之间的区别在于利用历史数据并生成最终结果的
        方法不一样。几种生成类型的策略分别如下：

            1,  RollingTiming 逐品种滚动时序信号生成器，用于生成择时信号的策略

                这类策略的共同特征是对投资组合中的所有投资产品逐个考察其历史数据，根据其历史数据，在历史数据的粒度上生成整个时间段上的
                时间序列信号。时间序列信号可以为多空信号，即用>0的数字表示多头头寸，<0的数字代表空头头寸，0代表中性头寸。也可以表示交
                易信号，即>0的数字表示建多仓或平空仓，<0的数字表示见空仓或平多仓。

                这种策略生成器将投资组合中的每一个投资产品逐个处理，每个投资产品中的NA值可以单独处理，与其他投资品种不相关、互不影响，
                同时，每个投资产品可以应用不同的参数生成信号，是最为灵活的择时信号生成器。

                另外，为了避免前视偏差，滚动择时策略仅利用一小段有限的历史数据（被称为时间窗口）来生成每一个时间点上的信号，同时确保
                时间窗口总是处于需要计算多空位置那一点的过去。这种技术称为"时间窗口滚动"。这样的滚动择时信号生成方法适用于未来数据会
                对当前的信号产生影响的情况下。采用滚动择时策略生成方法，可以确保每个时间点的交易信号只跟过去一段时间有关，从而彻底排除
                前视偏差可能给策略带来的影响。

                不过，由于时间窗口滚动的计算方式需要反复提取一段时间窗口内的数据，并反复计算，因此计算复杂度与数据总量M与时间窗口长度N
                的乘积M*N成正比，效率显著低于简单时序信号生成策略，因此，在可能的情况下（例如，简单移动平均值相关策略不受未来价格影响）
                应该尽量使用简单时序信号生成策略，以提升执行速度。

            2,  SimpleSelecting 简单投资组合分配器，用于周期性地调整投资组合中每个个股的权重比例

                这类策略的共同特征是周期性运行，且运行的周期与其历史数据的粒度不同。在每次运行时，根据其历史数据，为潜在投资组合中的每
                一个投资产品分配一个权重，并最终确保所有的权重值归一化。权重为0时表示该投资产品被从组合中剔除，而权重的大小则代表投资
                过程中分配投资资金的比例。

                这种方式生成的策略可以用于生成周期性选股蒙板，也可以用于生成周期性的多空信号模板。

                这种生成方式的策略是针对历史数据区间运行的，是运算复杂度最低的一类生成方式，对于数量超大的投资组合，可以采用这种方式生
                成投资策略。但仅仅局限于部分周期性运行的策略。

            3,  SimpleTiming 逐品种简单时序信号生成器，用于生成择时信号的策略

                这类策略的共同特征是对投资组合中的所有投资产品逐个考察其历史数据，并在历史数据的粒度上生成整个时间段上的时间序列信号。
                这种策略生成方法与逐品种滚动时序信号生成策略的信号产生方法类似，只是缺少了"滚动"的操作，时序信号是一次性在整个历史区间
                上生成的，并不考虑未来数据对当前信号的影响。这类方法生成的信号既可以代表多空信号，也可以代表交易信号。

                同时，简单时序信号生成器也保留了滚动时序信号生成器的灵活性优点：每个投资产品独立处理，不同数据的NA值互不关联，互不影响，
                同时每个不同的投资产品可以应用完全不同的策略参数。最大的区别就在于信号不是滚动生成的。

                正因为没有采用滚动计算的方式，因此简单时序信号生成器的计算复杂度只有O(M),与历史数据数量M成正比，远小于滚动生成器。
                不过，其风险在于策略本身是否受未来数据影响，如果策略本身不受未来数据的影响，则采用简单时序生成器是一种较优的选择，例如，
                基于移动平均线相交的相交线策略、基于过去N日股价变动的股价变动策略本身具备不受未来信息影响的特点，使用滚动时序生成器和
                简单时序生成器能得到相同的结果，而简单时序生成器的计算耗时大大低于滚动时序生成器，因此应该采用简单滚动生成器。又例如，
                基于指数平滑均线或加权平均线的策略，或基于波形降噪分析的策略，其输出信号受未来信息的影响，如果使用简单滚动生成器将会
                导致未来价格信息对回测信号产生影响，因此不应该使用简单时序信号生成器。

            4,  FactoralSelecting 因子选股投资组合分配器，用于周期性地调整投资组合中每个个股的权重比例

                这类策略的共同特征是周期性运行，且运行的周期与其历史数据的粒度不同。在每次运行时，根据其历史数据，为每一个股票计算一个
                选股因子，这个选股因子可以根据任意选定的数据根据任意可能的逻辑生成。生成选股因子后，可以通过对选股因子的条件筛选和
                排序执行选股操作。用户可以在策略属性层面定义筛选条件和排序方法，同时可以选择不同的选股权重分配方式

                这种方式生成的策略可以用于生成周期性选股蒙板，也可以用于生成周期性的多空信号模板。

                这种生成方式的策略是针对历史数据区间运行的，是运算复杂度最低的一类生成方式，对于数量超大的投资组合，可以采用这种方式生
                成投资策略。但仅仅局限于部分周期性运行的策略。

            5,  ReferenceTiming 参考数据信号生成器

                这类策略并不需要所选择股票本身的数据计算策略输出，而是利用参考数据例如大盘、宏观经济数据或其他数据来生成统一的股票多空
                或选股信号模版。其计算的基本方法与Timing类型生成器基本一致，但是同时针对所有的投资组合进行计算，因此信号可以用于多空
                蒙板和选股信号蒙本，计算的基础为参考信号

        ==策略的三种信号类型==

        在Operator对象中，包含的策略可以有无限多个，但是Operator会将策略用于生成三种不同类型的信号，一个Operator对象只生成一种
        类型的信号，信号类型由Operator对象的SignalGenerator属性确定。

        Operator对象可以同时将多个策略用于生成同一种信号，为了确保输出唯一，多个策略的输出将被以某种方式混合，混合的方式是Operator
        对象的属性，定义了同样用途的不同策略输出结果的混合方式，以下是三种用途及其混合方式的介绍：

            信号类型1,  仓位目标信号(Positional Target，PT信号)：
                仓位目标信号代表在某个时间点上应该持有的各种投资产品的仓位百分比。信号取值从-100% ～ 100%，或者-1～1之间，代表在
                这个时间点上，应该将该百分比的全部资产投资到这个产品中。如果百分比为负数，代表应该持有空头仓位。
                应该注意的是，PT信号并不给出明确的操作或者交易信号，仅仅是给出一个目标仓位，是否产生交易信号需要检查当前实际持仓与
                目标持仓之间的差异来确定，当这个差值大于某一个阈值的时候，产生交易信号。这个阈值由QT级别的参数确定。

            信号类型2,  比例买卖信号(Proportional Signal，PS信号)：
                比例买卖信号代表每一个时间周期上计划买入或卖出的各个股票的数量，当信号代表买入时，该信号的数值代表计划买入价值占当时
                总资产的百分比；当信号代表卖出时，该信号的数值代表计划卖出的数量占当时该股票的持有数量的百分比，亦即：
                    - 当信号代表买入时，0.3代表使用占总资产30%的现金买入某支股票
                    - 当信号代表卖出时，-0.5代表卖出所持有的某种股票的50%的份额

            信号类型3:  数量买卖信号(Volume Signal，VS信号)：
                数量买卖信号代表每一个时间周期上计划买入或卖出的各个股票的数量，这个数量代表计划买卖数量，实际买卖数量受买卖规则影响，
                因此可能与计划买卖信号不同。例如： 500代表买入相应股票500股


        ==交易信号的混合==

            尽管同一个Operator对象同时只能生成一种类型的信号，但由于Operator对象能容纳无限多个不同的交易策略，因而Operator对象
            也能产生无限多组同类型的交易策略。为了节省交易回测时的计算开销，避免冲突的交易信号或重复的交易信号占用计算资源，同时也
            为了增加交易信号的灵活度，应该将所有交易信号首先混合成一组，再送入回测程序进行回测。

            不过，在一个Operator对象中，不同策略生成的交易信号可能运行的交易价格是不同的，例如，某些策略生成开盘价交易信号，而另一
            些策略生成的是收盘价交易策略，那么不同的交易价格信号当然不应该混合。但除此之外，只要是交易价格相同的信号，都应该全部混合。
            除非所有的额交易信号都是基于"固定价格"交易而不是"市场价格"交易的。所有以"固定价格"交易的信号都不能被混合，必须单独进入
            回测系统进行混合。

            交易信号的混合即交易信号的各种运算或函数，从简单的逻辑运算、加减运算一直到复杂的自定义函数，只要能够应用于一个ndarray的
            函数，理论上都可以用于混合交易信号，只要最终输出的交易信号有意义即可。

            交易信号的混合基于一系列事先定义的运算和函数，这些函数或运算都被称为"原子函数"或"算子"，用户利用这些"算子"来操作
            Operator对象生成的交易信号，并将多个交易信号组变换成一个唯一的交易信号组，同时保持其形状不变，数字有意义。

            交易信号的混合是由一个混合表达式来确定的，例如'0 and (1 + 2) * avg(3, 4)'

            上面的表达式表示了如何将五组交易信号变换为一组信号。表达式可以是任意合法的通用四则运算表达式，表达式中可以包含任意内建
            的信号算子或函数，用户可以相当自由地组合自己的混合表达式。表达式中的数字0～4代表Operator所生成的交易信号，这些数字也
            不必唯一，可以重复，也可以遗漏，如写成"1+1+1*2+max(1, 4)"是完全合法的，只是第二组信号会被重复使用四次，而第一组(0)和第
            四组(3)数据不会被用到而已。如果数字超过了信号的个数，则会使用最后一组信号，如"999+999"表达式被用于只有两组信号的Operator
            对象时，系统会把第二组信号相加返回。

            交易信号的算子包括以下这些：

            and: 0.5 and 0.5 = 0.5 * 0.5 = 0.25,
            or:  0.5 or 0.5 = 0.5 + 0.5 = 1
            orr: 0.5 orr 0.5 = 1 - (1 - 0.5) * (1 - 0.5) = 0.75
            not: not(1) = 1 - 1 = 0; not(0.3) = 1 - 0.3 = 0.7
            + :  0.5 + 0.5 = 1
            - :  1.0 - 0.5 = 0.5
            * :  0.5 * 0.5 = 0.25
            / :  0.25 / 0.5 = 0.5

            算子还包括以下函数：

            'chg-N()': N为正整数，取值区间为1到len(timing)的值，表示多空状态在第N次信号反转时反转
            'pos-N()': N为正整数，取值区间为1到len(timing)的值，表示在N个策略为多时状态为多，否则为空
            'cumulative()': 在每个策略发生反转时都会产生交易信号，但是信号强度为1/len(timing)
            所有类型的交易信号都一样，只要交易价格是同一类型的时候，都应该混合为一组信号进入回测程序进行回测，混合的方式由混合
            字符串确定，字符串的格式为"[chg|pos]-0/9|cumulative"(此处应该使用正则表达式)

            'str-T()': T为浮点数，当多个策略多空蒙板的总体信号强度达到阈值T时，总体输出为1(或者-1)，否则为0
            'pos-N()': N为正整数，取值区间为1到len(timing)的值，表示在N个策略为多时状态为多，否则为空
                这种类型有一个变体：
                'pos-N-T': T为信号强度阈值，忽略信号强度达不到该阈值的多空蒙板信号，将剩余的多空蒙板进行计数，信号数量达到或
                超过N时，输出为1（或者-1），否则为0
            'avg()': 平均信号强度，所有多空蒙板的信号强度的平均值
            'combo()': 在每个策略发生反转时都会产生交易信号，信号的强度不经过衰减，但是通常第一个信号产生后，后续信号就再无意义

    """

    # 对象初始化时需要给定对象中包含的选股、择时、风控组件的类型列表

    AVAILABLE_BLENDER_TYPES = ['avg', 'avg_pos', 'pos', 'str', 'combo', 'none']
    AVAILABLE_SIGNAL_TYPES = {'position target':   'pt',
                              'proportion signal': 'ps',
                              'volume signal':     'vs'}

    def __init__(self, strategies=None, signal_type=None):
        """ 生成具体的Operator对象
            每个Operator对象主要包含多个strategy对象，每一个strategy对象都会被赋予一个唯一的ID，通过
            这个ID可以访问所有的Strategy对象，除ID以外，每个strategy也会有一个唯一的序号，通过该序号也可以
            访问所有的额strategy对象。或者给相应的strategy对象设置、调整参数。

        input:
            :param strategies:  str, 用于生成交易信号的交易策略清单（以交易信号的id或交易信号对象本身表示）
                                如果不给出strategies，则会生成一个空的Operator对象

            :param signal_type: str, 需要生成的交易信号的类型，包含以下三种类型:
                                        'pt', 'ps', 'vs'
                                默认交易信号类型为'ps'

        Operator对象的基本属性包括：
            signal_type:


        """
        # 如果对象的种类未在参数中给出，则直接指定最简单的策略种类
        if isinstance(strategies, str):
            stg = str_to_list(strategies)
        elif isinstance(strategies, Strategy):
            stg = [strategies]
        elif isinstance(strategies, list):
            stg = strategies
        else:
            stg = []
        if signal_type is None:
            signal_type = 'pt'
        if (signal_type.lower() not in self.AVAILABLE_SIGNAL_TYPES) and \
                (signal_type.lower() not in self.AVAILABLE_SIGNAL_TYPES.values()):
            signal_type = 'pt'

        # 初始化基本数据结构
        '''
        Operator对象的基本数据结构包含一个列表和多个字典Dict，分别存储对象中Strategy对象的信息：
        一个列表是Strategy ID list即策略ID列表：
            _stg_id:            交易策略ID列表，保存所有相关策略对象的唯一标识id（名称），如:
                                    ['MACD', 
                                     'DMA', 
                                     'MACD-1']
        
        这些Dict分为两类：
        第一类保存所有Strategy交易策略的信息：这一类字典的键都是该Strategy的ID：
                                     
            _strategies:        以字典形式存储所有交易策略对象本身
                                存储所有的策略对象，如:
                                    {'MACD':    Timing(MACD), 
                                     'DMA':     Timing(timing_DMA), 
                                     'MACD-1':  Timing(MACD)}
                                     
            _op_history_data:   以字典形式保存用于所有策略交易信号生成的历史数据切片（HistoryPanel对象切片）
                                例如：
                                    {'MACD':    ndarray-MACD, 
                                     'DMA':     ndarray-DMA, 
                                     'MACD-1':  ndarray-MACD-1}
                                     
        第二类Dict保存不同回测价格类型的交易策略的混合表达式和混合操作队列
                                
            _stg_blender_strings:
                                交易信号混合表达式，该表达式决定了一组多个交易信号应该如何共同影响
                                最终的交易决策，通过该表达式用户可以灵活地控制不同交易信号对最终交易
                                信号的影响，例如只有当多个交易信号同时存在买入时才买入，等等。
                                交易信号表达式以类似于四则运算表达式以及函数式的方式表达，解析后应用
                                到所有交易信号中
                                例如：
                                    {'close':    '0 + 1', 
                                     'open':     '2*(0+1)'}
                                
            _stg_blenders:      "信号混合"字典，包含不同价格类型交易信号的混合操作队列，dict的键对应不同的
                                交易价格类型，Value为交易信号混合操作队列，操作队列以逆波兰式
                                存储(RPN, Reversed Polish Notation)
                                例如：
                                    {'close':    ['*', '1', '0'], 
                                     'open':     ['*', '2', '+', '1', '0']}
                                
        '''

        self._signal_type = ''  # 保存operator对象输出的信号类型
        self._next_stg_index = 0  # int——递增的策略index，确保不会出现重复的index
        self._strategy_id = []  # List——保存所有交易策略的id，便于识别每个交易策略
        self._strategies = {}  # Dict——保存实际的交易策略对象
        self._op_history_data = {}  # Dict——保存供各个策略进行交易信号生成的历史数据（ndarray）
        self._stg_blender = {}  # Dict——交易信号混合表达式的解析式
        self._stg_blender_strings = {}  # Dict——交易信号混和表达式的原始字符串形式

        # 添加strategy对象
        self.add_strategies(stg)
        # 添加signal_type属性
        self.signal_type = signal_type

    def __repr__(self):
        res = list()
        res.append('Operator(')
        if self.strategy_count > 0:
            res.append(', '.join(self._strategy_id))
        res.append(')')
        return ''.join(res)

    @property
    def empty(self):
        """检查operator是否包含任何策略"""
        res = (len(self.strategies) == 0)
        return res

    @property
    def strategies(self):
        """以列表的形式返回operator对象的所有Strategy对象"""
        return [self._strategies[stg_id] for stg_id in self._strategy_id]

    @property
    def strategy_count(self):
        """返回operator对象中的所有Strategy对象的数量"""
        return len(self._strategy_id)

    @property
    def strategy_ids(self):
        """返回operator对象中所有交易策略对象的ID"""
        return self._strategy_id

    @property
    def strategy_blenders(self):
        return self._stg_blender

    @strategy_blenders.setter
    def strategy_blenders(self, blenders):
        """ setting blenders of strategy"""
        self.set_blender(price_type=None, blender=blenders)

    @property
    def signal_type(self):
        """ 返回operator对象的信号类型"""
        return self._signal_type

    @signal_type.setter
    def signal_type(self, st):
        """ 设置signal_type的值"""
        if not isinstance(st, str):
            raise TypeError(f'signal type should be a string, got {type(st)} instead!')
        elif st.lower() in self.AVAILABLE_SIGNAL_TYPES:
            self._signal_type = self.AVAILABLE_SIGNAL_TYPES[st.lower()]
        elif st.lower() in self.AVAILABLE_SIGNAL_TYPES.values():
            self._signal_type = st.lower()
        else:
            raise ValueError(f'the signal type {st} is not valid!\n'
                             f'{self.AVAILABLE_SIGNAL_TYPES}')

    @property
    def signal_type_id(self):
        """ 以数字的形式返回operator对象的信号类型，便于loop中识别使用"""
        if self._signal_type == 'pt':
            return 0
        elif self._signal_type == 'ps':
            return 1
        else:
            return 2

    @property
    def op_data_types(self):
        """返回operator对象所有策略子对象所需数据类型的集合"""
        d_types = [typ for item in self.strategies for typ in item.data_types]
        d_types = list(set(d_types))
        d_types.sort()
        return d_types

    @property
    def op_data_type_count(self):
        """ 返回operator对象生成交易清单所需的历史数据类型数量
        """
        return len(self.op_data_types)

    @property
    def op_data_freq(self):
        """返回operator对象所有策略子对象所需数据的采样频率
            如果所有strategy的data_freq相同时，给出这个值，否则给出一个排序的列表
        """
        d_freq = [stg.data_freq for stg in self.strategies]
        d_freq = list(set(d_freq))
        d_freq.sort()
        if len(d_freq) == 0:
            return ''
        if len(d_freq) == 1:
            return d_freq[0]
        warnings.warn(f'there are multiple history data frequency required by strategies', RuntimeWarning)
        return d_freq

    @property
    def bt_price_types(self):
        """返回operator对象所有策略子对象的回测价格类型"""
        p_types = [item.price_type for item in self.strategies]
        p_types = list(set(p_types))
        p_types.sort()
        return p_types

    @property
    def op_data_type_list(self):
        """ 返回一个列表，列表中的每个元素代表每一个策略所需的历史数据类型"""
        return [stg.data_types for stg in self.strategies]

    @property
    def op_history_data(self):
        """ 返回一个列表，这个列表中的每个元素都是ndarray，每个ndarray中包含了
        可以用于signal generation 的历史数据，且这些历史数据的类型与op_data_type_list
        中规定的数据类型相同，历史数据跨度满足信号生成的需求"""
        return self._op_history_data

    @property
    def opt_space_par(self):
        """一次性返回operator对象中所有参加优化（opt_tag != 0）的子策略的参数空间Space信息
            改属性的返回值是一个元组，包含ranges, types两个列表，这两个列表正好可以直接用作Space对象的创建参数，用于创建一个合适的
            Space对象

            一个完整的投资策略由三类多个不同的子策略组成。每个子策略都有自己特定的参数空间，它们的参数空间信息存储在stg.par_boes以及
            stg.par_types等属性中。通常，我们在优化参数的过程中，希望仅对部分策略的参数空间进行搜索，而其他的策略保持参数不变。为了实现
            这样的控制，我们可以给每一个子策略一个属性opt_tag优化标签，通过设置这个标签的值，可以控制这个子策略是否参与优化：
            {0: 'No optimization, 不参与优化，这个子策略在整个优化过程中将始终使用同一组参数',
             1: 'Normal optimization, 普通优化，这个子策略在优化过程中使用不同的参数，这些参数都是从它的参数空间中按照规律取出的',
             2: 'enumerate optimization, 枚举优化，在优化过程中使用不同的参数，但并非取自其参数空间，而是来自一个预设的枚举对象'}

         这个函数遍历operator对象中所有子策略，根据其优化类型选择它的参数空间信息，组合成一个多维向量用于创建可以用于生成所有相关
         策略的参数的高维空间

         return: ranges, types
        """
        ranges = []
        types = []
        for stg in self.strategies:
            if stg.opt_tag == 0:
                pass  # 策略参数不参与优化
            elif stg.opt_tag == 1:
                # 所有的策略参数全部参与优化，且策略的每一个参数作为一个个体参与优化
                ranges.extend(stg.par_boes)
                types.extend(stg.par_types)
            elif stg.opt_tag == 2:
                # 所有的策略参数全部参与优化，但策略的所有参数组合作为枚举同时参与优化
                ranges.append(stg.par_boes)
                types.extend(['enum'])
        return ranges, types

    @property
    def opt_tags(self):
        """ 返回所有策略的优化类型标签
            该属性返回值是一个列表，按顺序列出所有交易策略的优化类型标签
        """
        return [stg.opt_tag for stg in self.strategies]

    @property
    def max_window_length(self):
        """ 计算并返回operator对象所有子策略中最长的策略形成期。在准备回测或优化历史数据时，以此确保有足够的历史数据供策略形成

        :return: int
        """
        if self.strategy_count == 0:
            return 0
        else:
            return max(stg.window_length for stg in self.strategies)

    @property
    def bt_price_type_count(self):
        """ 计算operator对象中所有子策略的不同回测价格类型的数量
        :return: int
        """
        return len(self.bt_price_types)

    @property
    def ready(self):
        """ 检查Operator对象是否已经准备好，可以开始生成交易信号，如果可以，返回True，否则返回False

        返回True，表明Operator的各项属性已经具备以下条件：
            1，Operator 已经有strategy
            2，所有类型的strategy都有blender

        :return:
        """
        if self.empty:
            return False
        message = [f'Operator readiness:\n']
        is_ready = True
        if self.strategy_count == 0:
            message.append(f'No strategy -- add strategies to Operator!')
            is_ready = False
        if len(self.strategy_blenders) < self.bt_price_type_count:
            message.append(f'No blender -- some of the strategies will not be used for signal, add blender')
            is_ready = False
        else:
            pass

        if len(self.op_data_type_list) < self.strategy_count:
            message.append(f'No history data -- ')
            is_ready = False

        if not is_ready:
            print(''.join(message))

        return is_ready

    def __getitem__(self, item):
        """ 根据策略的名称或序号返回子策略"""
        item_is_int = isinstance(item, int)
        item_is_str = isinstance(item, str)
        if not (item_is_int or item_is_str):
            warnings.warn('the item is in a wrong format and can not be parsed!')
            return
        all_ids = self._strategy_id
        if item_is_str:
            if item not in all_ids:
                warnings.warn('the strategy name can not be recognized!')
                return
            return self._strategies[item]
        strategy_count = self.strategy_count
        if item >= strategy_count - 1:
            item = strategy_count - 1
        return self._strategies[all_ids[item]]

    def get_stg(self, stg_id):
        """ 获取一个strategy对象, Operator[item]的另一种用法

        """
        return self[stg_id]

    def get_strategy_by_id(self, stg_id):
        """ 获取一个strategy对象, Operator[item]的另一种用法

        """
        return self[stg_id]

    def add_strategies(self, strategies):
        """ 添加多个Strategy交易策略到Operator对象中
        使用这个方法，不能在添加交易策策略的同时修改交易策略的基本属性
        输入参数strategies可以为一个列表或者一个逗号分隔字符串
        列表中的元素可以为代表内置策略类型的字符串，或者为一个具体的策略对象
        字符串和策略对象可以混合给出

        :param strategies:
        :return:
        """
        if isinstance(strategies, str):
            strategies = str_to_list(strategies)
        assert isinstance(strategies, list), f'TypeError, the strategies ' \
                                             f'should be a list of string, got {type(strategies)} instead'
        for stg in strategies:
            if not isinstance(stg, (str, Strategy)):
                warnings.warn(f'WrongType! some of the items in strategies '
                              f'can not be added - got {stg}', RuntimeWarning)
            self.add_strategy(stg)

    def add_strategy(self, stg, **kwargs):
        """ 添加一个strategy交易策略到operator对象中
        如果调用本方法添加一个交易策略到Operator中，可以在添加的时候同时修改或指定交易策略的基本属性

        :param: stg, 需要添加的交易策略，可以为交易策略对象，也可以是内置交易策略的策略id或策略名称
        :param: **kwargs, 任意合法的策略属性，可以在添加策略时直接给该策略属性赋值，
                必须明确指定需要修改的属性名称，
                例如: opt_tag = 1
        """
        # 如果输入为一个字符串时，检查该字符串是否代表一个内置策略的id或名称，使用.lower()转化为全小写字母
        if isinstance(stg, str):
            stg = stg.lower()
            if stg not in BUILT_IN_STRATEGIES:
                raise KeyError(f'built-in timing strategy \'{stg}\' not found!')
            stg_id = stg
            strategy = BUILT_IN_STRATEGIES[stg]()
        # 当传入的对象是一个strategy对象时，直接添加该策略对象
        elif isinstance(stg, Strategy):
            if stg in AVAILABLE_BUILT_IN_STRATEGIES:
                stg_id_index = list(AVAILABLE_BUILT_IN_STRATEGIES).index(stg)
                stg_id = list(BUILT_IN_STRATEGIES)[stg_id_index]
            else:
                stg_id = 'custom'
            strategy = stg
        else:
            raise TypeError(f'The strategy type \'{type(stg)}\' is not supported!')
        stg_id = self._next_stg_id(stg_id)
        self._strategy_id.append(stg_id)
        self._strategies[stg_id] = strategy
        # 逐一修改该策略对象的各个参数
        self.set_parameter(stg_id=stg_id, **kwargs)

    def _next_stg_id(self, stg_id: str):
        """ find out next available strategy id"""
        all_ids = self._strategy_id
        if stg_id in all_ids:
            stg_id_stripped = [ID.partition("_")[0] for ID in all_ids if ID.partition("_")[0] == stg_id]
            next_id = stg_id + "_" + str(len(stg_id_stripped))
            return next_id
        else:
            return stg_id

    def remove_strategy(self, id_or_pos=None):
        """从Operator对象中移除一个交易策略"""
        pos = -1
        if id_or_pos is None:
            pos = -1
        if isinstance(id_or_pos, int):
            if id_or_pos < self.strategy_count:
                pos = id_or_pos
            else:
                pos = -1
        if isinstance(id_or_pos, str):
            all_ids = self._strategy_id
            if id_or_pos not in all_ids:
                raise ValueError(f'the strategy {id_or_pos} is not in operator')
            else:
                pos = all_ids.index(id_or_pos)
        # 删除strategy的时候，不需要实际删除某个strategy，只需要删除其id即可
        self._strategy_id.pop(pos)
        # self._strategies.pop(pos)
        return

    def clear_strategies(self):
        """clear all strategies

        :return:
        """
        if self.strategy_count > 0:
            self._strategy_id = []
            self._strategies = {}
            self._op_history_data = {}

            self._stg_blender = {}
            self._stg_blender_strings = {}
        return

    def get_strategies_by_price_type(self, price_type=None):
        """返回operator对象中的strategy对象, price_type为一个可选参数，
        如果给出price_type时，返回使用该price_type的交易策略

        :param price_type: str 一个可用的price_type

        """
        if price_type is None:
            return self.strategies
        else:
            return [stg for stg in self.strategies if stg.price_type == price_type]

    def get_op_history_data_by_price_type(self, price_type=None):
        """ 返回Operator对象中每个strategy对应的交易信号历史数据，price_type是一个可选参数
        如果给出price_type时，返回使用该price_type的所有策略的历史数据

        :param price_type: str 一个可用的price_type

        """
        all_hist_data = self._op_history_data
        if price_type is None:
            return list(all_hist_data.values())
        else:
            relevant_strategy_ids = self.get_strategy_id_by_price_type(price_type=price_type)
            return [all_hist_data[stg_id] for stg_id in relevant_strategy_ids]

    def get_strategy_count_by_price_type(self, price_type=None):
        """返回operator中的交易策略的数量, price_type为一个可选参数，
        如果给出price_type时，返回使用该price_type的交易策略数量"""
        return len(self.get_strategies_by_price_type(price_type))

    def get_strategy_names_by_price_type(self, price_type=None):
        """返回operator对象中所有交易策略对象的名称, price_type为一个可选参数，
        注意，strategy name并没有实际的作用，未来将被去掉
        在操作operator对象时，引用某个策略实际使用的是策略的id，而不是name
        如果给出price_type时，返回使用该price_type的交易策略名称"""
        return [stg.stg_name for stg in self.get_strategies_by_price_type(price_type)]

    def get_strategy_id_by_price_type(self, price_type=None):
        """返回operator对象中所有交易策略对象的ID, price_type为一个可选参数，
        如果给出price_type时，返回使用该price_type的交易策略名称"""
        all_ids = self._strategy_id
        if price_type is None:
            return all_ids
        else:
            res = []
            for stg, stg_id in zip(self.strategies, all_ids):
                if stg.price_type == price_type:
                    res.append(stg_id)
            return res

    def set_opt_par(self, opt_par):
        """optimizer接口函数，将输入的opt参数切片后传入stg的参数中

        :param opt_par:
            :type opt_par:Tuple
            一组参数，可能包含多个策略的参数，在这里被分配到不同的策略中

        :return
            None

        本函数与set_parameter()不同，在优化过程中非常有用，可以同时将参数设置到几个不同的策略中去，只要这个策略的opt_tag不为零
        在一个包含多个Strategy的Operator中，可能同时有几个不同的strategy需要寻优。这时，为了寻找最优解，需要建立一个Space，包含需要寻优的
        几个strategy的所有参数空间。通过这个space生成参数空间后，空间中的每一个向量实际上包含了不同的策略的参数，因此需要将他们原样分配到不
        同的策略中。

        举例如下：

            一个Operator对象有三个strategy，分别需要2， 3， 3个参数，而其中第一和第三个策略需要参数寻优，这个operator的所有策略参数可以写
            成一个2+3+2维向量，其中下划线的几个是需要寻优的策略的参数：
                     stg1:   stg2:       stg3:
                     tag=1   tag=0       tag=1
                    [p0, p1, p2, p3, p4, p5, p6, p7]
                     ==  ==              ==  ==  ==
            为了寻优方便，可以建立一个五维参数空间，用于生成五维参数向量：
                    [v0, v1, v2, v3, v4]
            set_opt_par函数遍历Operator对象中的所有strategy函数，检查它的opt_tag值，只要发现opt_tag不为0，则将相应的参数赋值给strategy：
                     stg1:   stg2:       stg3:
                     tag=1   tag=0       tag=1
                    [p0, p1, p2, p3, p4, p5, p6, p7]
                     ==  ==              ==  ==  ==
                    [v0, v1]            [v2, v3, v4]

            在另一种情况下，一个策略的参数本身就以一个tuple的形式给出，一系列的合法参数组以enum的形式形成一个完整的参数空间，这时，opt_tag被
            设置为2，此时参数空间中每个向量的一个分量就包含了完整的参数信息，例子如下：

            一个Operator对象有三个strategy，分别需要2， 3， 3个参数，而其中第一和第三个策略需要参数寻优，这个operator的所有策略参数可以写
            成一个2+3+2维向量，其中下划线的几个是需要寻优的策略的参数，注意其中stg3的opt_tag被设置为2：
                     stg1:   stg2:       stg3:
                     tag=1   tag=0       tag=2
                    [p0, p1, p2, p3, p4, p5, p6, p7]
                     ==  ==              ==  ==  ==
            为了寻优建立一个3维参数空间，用于生成五维参数向量：
                    [v0, v1, v2]，其中v2 = (i0, i1, i2)
            set_opt_par函数遍历Operator对象中的所有strategy函数，检查它的opt_tag值，对于opt_tag==2的策略，则分配参数给这个策略
                     stg1:   stg2:       stg3:
                     tag=1   tag=0       tag=2
                    [p0, p1, p2, p3, p4, p5, p6, p7]
                     ==  ==              ==  ==  ==
                    [v0, v1]         v2=[i0, i1, i2]
        """
        s = 0
        k = 0
        # 依次遍历operator对象中的所有策略：
        for stg in self.strategies:
            # 优化标记为0：该策略的所有参数在优化中不发生变化
            if stg.opt_tag == 0:
                pass
            # 优化标记为1：该策略参与优化，用于优化的参数组的类型为上下界
            elif stg.opt_tag == 1:
                k += stg.par_count
                stg.set_pars(opt_par[s:k])
                s = k
            # 优化标记为2：该策略参与优化，用于优化的参数组的类型为枚举
            elif stg.opt_tag == 2:
                # 在这种情况下，只需要取出参数向量中的一个分量，赋值给策略作为参数即可。因为这一个分量就包含了完整的策略参数tuple
                k += 1
                stg.set_pars(opt_par[s])
                s = k

    def set_blender(self, price_type=None, blender=None):
        """ 统一的blender混合器属性设置入口

        :param price_type:
            :type price_type: str, 一个字符串，用于指定需要混合的交易信号的价格类型，
                                如果给出price_type且price_type存在，则设置该price_type的策略的混合表达式
                                如果给出price_type而price_type不存在，则给出warning并返回
                                如果给出的price_type不是正确的类型，则报错
                                如果price_type为None，则设置所有price_type的策略的混合表达式，此时：
                                    如果给出的blender为一个字符串，则设置所有的price_type为相同的表达式
                                    如果给出的blender为一个列表，则按照列表中各个元素的顺序分别设置每一个price_type的混合表达式，
                                    如果blender中的元素不足，则重复最后一个混合表达式
        :param blender:
            :type blender: str, 一个合法的交易信号混合表达式
                                当price_type为None时，可以接受list为参数，同时为所有的price_type设置混合表达式

        :example:
            >>> op = Operator('dma, macd')
            >>> op.set_parameter('dma', price_type='close')
            >>> op.set_parameter('macd', price_type='open')

            >>> # 设置open的策略混合模式
            >>> op.set_blender('open', '1+2')
            >>> op.get_blender()
            >>> {'open': ['+', '2', '1']}

            >>> # 给所有的交易价格策略设置同样的混合表达式
            >>> op.set_blender(None, '1 + 2')
            >>> op.get_blender()
            >>> {'close': ['+', '2', '1'], 'open':  ['+', '2', '1']}

            >>> # 通过一个列表给不同的交易价格策略设置不同的混合表达式（交易价格按照字母顺序从小到大排列）
            >>> op.set_blender(None, ['1 + 2', '3*4'])
            >>> op.get_blender()
            >>> {'close': ['+', '2', '1'], 'open':  ['*', '4', '3']}

        :return
            None

        """
        if self.strategy_count == 0:
            return
        if price_type is None:
            # 当price_type没有显式给出时，同时为所有的price_type设置blender，此时区分多种情况：
            if blender is None:
                # price_type和blender都为空，退出
                return
            if isinstance(blender, str):
                # blender为一个普通的字符串，此时将这个blender转化为一个包含该blender的列表，并交由下一步操作
                blender = [blender]
            if isinstance(blender, list):
                # 将列表中的blender补齐数量后，递归调用本函数，分别赋予所有的price_type
                len_diff = self.bt_price_type_count - len(blender)
                if len_diff > 0:
                    blender.extend([blender[-1]] * len_diff)
                for bldr, pt in zip(blender, self.bt_price_types):
                    self.set_blender(price_type=pt, blender=bldr)
            else:
                raise TypeError(f'Wrong type of blender, a string or a list of strings should be given,'
                                f' got {type(blender)} instead')
            return
        if isinstance(price_type, str):
            # 当直接给出price_type时，仅为这个price_type赋予blender
            if price_type not in self.bt_price_types:
                warnings.warn(
                        f'\n'
                        f'Given price type \'{price_type}\' is not in valid price type list of \n'
                        f'current Operator, no blender will be created!\n'
                        f'current valid price type list as following:\n{self.bt_price_types}')
                return
            if isinstance(blender, str):
                # TODO: 此处似乎应该增加blender字符串的合法性检查？？
                try:
                    parsed_blender = blender_parser(blender)
                    self._stg_blender[price_type] = parsed_blender
                    self._stg_blender_strings[price_type] = blender
                except:
                    self._stg_blender_strings[price_type] = None
                    self._stg_blender[price_type] = []
            else:
                # 忽略类型不正确的blender输入
                self._stg_blender_strings[price_type] = None
                self._stg_blender[price_type] = []
        else:
            raise TypeError(f'price_type should be a string, got {type(price_type)} instead')
        return

    def get_blender(self, price_type=None):
        """返回operator对象中的多空蒙板混合器, 如果不指定price_type的话，输出完整的blender字典

        :param price_type: str 一个可用的price_type

        """
        if price_type is None:
            return self._stg_blender
        if price_type not in self.bt_price_types:
            return None
        if price_type not in self._stg_blender:
            return None
        return self._stg_blender[price_type]

    def view_blender(self, price_type=None):
        """返回operator对象中的多空蒙板混合器的可读版本, 即返回blender的原始字符串

        :param price_type: str 一个可用的price_type

        """
        if price_type is None:
            return self._stg_blender_strings
        if price_type not in self.bt_price_types:
            return None
        if price_type not in self._stg_blender:
            return None
        return self._stg_blender_strings[price_type]

    def set_parameter(self,
                      stg_id: [str, int],
                      pars: [tuple, dict] = None,
                      opt_tag: int = None,
                      par_boes: [tuple, list] = None,
                      par_types: [list, str] = None,
                      data_freq: str = None,
                      sample_freq: str = None,
                      window_length: int = None,
                      data_types: [str, list] = None,
                      price_type: str = None,
                      **kwargs):
        """ 统一的策略参数设置入口，stg_id标识接受参数的具体成员策略
            将函数参数中给定的策略参数赋值给相应的策略

            这里应该有本函数的详细介绍

            :param stg_id:
                :type stg_id: str, 策略的名称（ID），根据ID定位需要修改参数的策略

            :param pars:
                :type pars: tuple or dict , 需要设置的策略参数，格式为tuple

            :param opt_tag:
                :type opt_tag: int, 优化类型，0: 不参加优化，1: 参加优化, 2: 以枚举类型参加优化

            :param par_boes:
                :type par_boes: tuple or list, 策略取值范围列表,一个包含若干tuple的列表,代表参数中一个元素的取值范围，如
                [(0, 1), (0, 100), (0, 100)]

            :param par_types:
                :type par_types: str or list, 策略参数类型列表，与par_boes配合确定策略参数取值范围类型，详情参见Space类的介绍

            :param data_freq:
                :type data_freq: str, 数据频率，策略本身所使用的数据的采样频率

            :param sample_freq:
                :type sample_freq: str, 采样频率，策略运行时进行信号生成的采样频率，该采样频率决定了信号的频率

            :param window_length:
                :type window_length: int, 窗口长度：策略计算的前视窗口长度

            :param data_types:
                :type data_types: str or list, 策略计算所需历史数据的数据类型

            :param price_type:
                :type price_type: str, 策略回测交易时使用的交易价格类型

            :return:
        """
        assert isinstance(stg_id, (int, str)), f'stg_id should be a int or a string, got {type(stg_id)} instead'
        # 根据策略的名称或ID获取策略对象
        # TODO; 应该允许同时设置多个策略的参数（对于opt_tag这一类参数非常有用）
        strategy = self.get_strategy_by_id(stg_id)
        if strategy is None:
            raise KeyError(f'Specified strategie does not exist or can not be found!')
        # 逐一修改该策略对象的各个参数
        if pars is not None:  # 设置策略参数
            if strategy.set_pars(pars):
                pass
            else:
                raise ValueError(f'parameter setting error')
        if opt_tag is not None:  # 设置策略的优化标记
            strategy.set_opt_tag(opt_tag)
        if par_boes is not None:  # 设置策略的参数优化边界
            strategy.set_par_boes(par_boes)
        if par_types is not None:  # 设置策略的参数类型
            strategy.par_types = par_types
        has_df = data_freq is not None
        has_sf = sample_freq is not None
        has_wl = window_length is not None
        has_dt = data_types is not None
        has_pt = price_type is not None
        if has_df or has_sf or has_wl or has_dt or has_pt:
            strategy.set_hist_pars(data_freq=data_freq,
                                   sample_freq=sample_freq,
                                   window_length=window_length,
                                   data_types=data_types,
                                   price_type=price_type)
        # 设置可能存在的其他参数
        strategy.set_custom_pars(**kwargs)

    # =================================================
    # 下面是Operation模块的公有方法：
    def info(self, verbose=False):
        """ 打印出当前交易操作对象的信息，包括选股、择时策略的类型，策略混合方法、风险控制策略类型等等信息
            如果策略包含更多的信息，还会打印出策略的一些具体信息，如选股策略的信息等
            在这里调用了私有属性对象的私有属性，不应该直接调用，应该通过私有属性的公有方法打印相关信息
            首先打印Operation木块本身的信息
            :type verbose: bool

        """
        print('OPERATOR INFO:')
        print('=' * 25)
        print('Information of the Module')
        print('=' * 25)
        # 打印各个子模块的信息：
        print(f'Total {self.strategy_count} operation strategies, requiring {self.op_data_type_count} '
              f'types of historical data:')
        all_op_data_types = []
        for data_type in self.op_data_types:
            all_op_data_types.append(data_type)
        print(", ".join(all_op_data_types))
        print(f'{self.bt_price_type_count} types of back test price types:\n'
              f'{self.bt_price_types}')
        for price_type in self.bt_price_types:
            print(f'for backtest histoty price type - {price_type}: \n'
                  f'{self.get_strategies_by_price_type(price_type)}:')
            if self.strategy_blenders != {}:
                print(f'signal blenders: {self.view_blender(price_type)}')
            else:
                print(f'no blender')
        # 打印每个strategy的详细信息
        if verbose:
            print('Parameters of SimpleSelecting Strategies:')
            for stg in self.strategies:
                stg.info()
            print('=' * 25)

    # TODO 临时性使用cashplan作为参数之一，理想中应该只用一个"start_date"即可，这个Start_date可以在core.run()中具体指定，因为
    # TODO 在不同的运行模式下，start_date可能来源是不同的：
    def prepare_data(self, hist_data: HistoryPanel, cash_plan: CashPlan):
        """ 在create_signal之前准备好相关历史数据，检查历史数据是否符合所有策略的要求：

            检查hist_data历史数据的类型正确；
            检查cash_plan投资计划的类型正确；
            检查hist_data是否为空（要求不为空）；
            在hist_data中找到cash_plan投资计划中投资时间点的具体位置
            检查cash_plan投资计划中的每个投资时间点均有价格数据，也就是说，投资时间点都在交易日内
            检查cash_plan投资计划中第一次投资时间点前有足够的数据量，用于滚动回测
            检查cash_plan投资计划中最后一次投资时间点在历史数据的范围内
            从hist_data中根据各个量化策略的参数选取正确的历史数据切片放入各个策略数据仓库中
            检查op_signal混合器的设置，根据op的属性设置正确的混合器，如果没有设置混合器，则生成一个
                基础混合器（blender）

            然后，根据operator对象中的不同策略所需的数据类型，将hist_data数据仓库中的相应历史数据
            切片后保存到operator的各个策略历史数据属性中，供operator调用生成交易清单。

        :param hist_data:
            :type hist_data: HistoryPanel
            历史数据,一个HistoryPanel对象，应该包含operator对象中的所有策略运行所需的历史数据，包含所有
            个股所有类型的数据，例如，operator对象中存在两个交易策略，分别需要的数据类型如下：
                策略        所需数据类型
                ------------------------------
                策略A:   close, open, high
                策略B:   close, eps

            hist_data中就应该包含close、open、high、eps四种类型的数据
            数据覆盖的时间段和时间频率也必须符合上述要求

        :param cash_plan:
            :type cash_plan: CashPlan
            一个投资计划，临时性加入，在这里仅检查CashPlan与历史数据区间是否吻合，是否会产生数据量不够的问题

        :return:
            None
        """
        # 确保输入的历史数据是HistoryPanel类型
        if not isinstance(hist_data, HistoryPanel):
            raise TypeError(f'Historical data should be HistoryPanel, got {type(hist_data)}')
        # TODO: 临时性处理方式
        # 确保cash_plan的数据类型正确
        if not isinstance(cash_plan, CashPlan):
            raise TypeError(f'cash plan should be CashPlan object, got {type(cash_plan)}')
        # 确保输入的历史数据不为空
        if hist_data.is_empty:
            raise ValueError(f'history data can not be empty!')
        # 默认截取部分历史数据，截取的起点是cash_plan的第一个投资日，在历史数据序列中找到正确的对应位置
        first_cash_pos = np.searchsorted(hist_data.hdates, cash_plan.first_day)
        last_cash_pos = np.searchsorted(hist_data.hdates, cash_plan.last_day)
        # 确保回测操作的起点前面有足够的数据用于满足回测窗口的要求
        # TODO: 这里应该提高容错度，设置更好的回测历史区间设置方法，尽量使用户通过较少的参数设置就能完成基
        # TODO: 本的运行，不用过分强求参数之间的关系完美无缺，如果用户输入的参数之间有冲突，根据优先级调整
        # TODO: 相关参数即可，毋须责备求全。
        # TODO: 当运行模式为0时，不需要判断cash_pos与max_window_length的关系
        assert first_cash_pos >= self.max_window_length, \
            f'InputError, History data starts on {hist_data.hdates[0]} does not have enough data to cover' \
            f' first cash date {cash_plan.first_day}, ' \
            f'expect {self.max_window_length} cycles, got {first_cash_pos} records only'
        # 确保最后一个投资日也在输入的历史数据范围内
        # TODO: 这里应该提高容错度，如果某个投资日超出了历史数据范围，可以丢弃该笔投资，仅输出警告信息即可
        # TODO: 没必要过度要求用户的输入完美无缺。
        assert last_cash_pos < len(hist_data.hdates), \
            f'InputError, Not enough history data record to cover complete investment plan, history data ends ' \
            f'on {hist_data.hdates[-1]}, last investment on {cash_plan.last_day}'
        # 确认cash_plan的所有投资时间点都在价格清单中能找到（代表每个投资时间点都是交易日）
        invest_dates_in_hist = [invest_date in hist_data.hdates for invest_date in cash_plan.dates]
        if not all(invest_dates_in_hist):
            np_dates_in_hist = np.array(invest_dates_in_hist)
            where_not_in = [cash_plan.dates[i] for i in list(np.where(np_dates_in_hist == False)[0])]
            raise ValueError(f'Cash investment should be on trading days, '
                             f'following dates are not valid!\n{where_not_in}')
        # 确保op的策略都设置了参数
        assert all(stg.has_pars for stg in self.strategies), \
            f'One or more strategies has no parameter set properly!'
        # 确保op的策略都设置了混合方式，在未设置混合器时，混合器是一个空dict
        if self.strategy_blenders == {}:
            warnings.warn(f'User-defined Signal blenders do not exist, default ones will be created!', UserWarning)
            # 如果op对象尚未设置混合方式，则根据op对象的回测历史数据类型生成一组默认的混合器blender：
            # 每一种回测价格类型都需要一组blender，每个blender包含的元素数量与相应的策略数量相同
            for price_type in self.bt_price_types:
                stg_count_for_price_type = self.get_strategy_count_by_price_type(price_type)
                self.set_blender(price_type=price_type,
                                 blender='+'.join(map(str, range(stg_count_for_price_type))))
        # 使用循环方式，将相应的数据切片与不同的交易策略关联起来
        self._op_history_data = {stg_id: hist_data[stg.data_types, :, (first_cash_pos - stg.window_length):]
                                 for stg_id, stg in zip(self._strategy_id, self.strategies)}

    # TODO: 需要调查：
    # TODO: 为什么在已经通过prepare_data()方法设置好了每个不同策略所需的历史数据之后，在create_signal()方法中还需要传入
    # TODO: hist_data作为参数？这个参数现在已经没什么用了，完全可以拿掉。在sel策略的generate方法中也不应该
    # TODO: 需要传入shares和dates作为参数。只需要selecting_history_data中的一部分就可以了
    # TODO: ————上述问题的原因是生成的交易信号仍然被转化为DataFrame，shares和dates被作为列标签和行标签传入DataFrame，进而
    # TODO: 被用于消除不需要的行，同时还保证原始行号信息不丢失。在新的架构下，似乎可以不用创建一个DataFrame对象，直接返回ndarray
    # TODO: 这样不仅可以消除参数hist_data的使用，还能进一步提升速度
    def create_signal(self, hist_data: HistoryPanel):
        """生成交易信号：
            遍历Operator对象中的strategy对象，调用它们的generate方法生成策略交易信号
            如果Operator对象拥有不止一个Strategy对象，则遍历所有策略，分别生成交易信号后，再混合成最终的信号
            如果Operator拥有的Strategy对象交易执行价格类型不同，则需要分别混合，混合的方式可以相同，也可以不同



            在生成交易信号之前需要调用prepare_data准备好相应的

        input:
        :param hist_data:
            :type hist_data: HistoryPanel
            从数据仓库中导出的历史数据，包含多只股票在一定时期内特定频率的一组或多组数据
            ！！但是！！
            作为参数传入的这组历史数据并不会被直接用于交易信号的生成，用于生成交易信号的历史数据
            存储在operator对象的下面三个属性中，在生成交易信号时直接调用，避免了每次生成交易信号
            时再动态分配历史数据。
                self._selecting_history_data
                self._op_history_data
                self._ricon_history_data

        :return=====
            HistoryPanel
            使用对象的策略在历史数据期间的一个子集上产生的所有合法交易信号，该信号可以输出到回测
            模块进行回测和评价分析，也可以输出到实盘操作模块触发交易操作
        """

        # 确保输入历史数据的数据格式正确；并确保择时策略和风控策略都已经关联相应的历史数据
        if not isinstance(hist_data, HistoryPanel):
            raise TypeError(f'Type Error: historical data should be HistoryPanel, got {type(hist_data)}')
        from .blender import signal_blend
        op_signals = []
        shares = hist_data.shares
        date_list = hist_data.hdates
        # 最终输出的所有交易信号都是ndarray，且每种交易价格类型都有且仅有一组信号
        # 一个字典保存所有交易价格类型各自的交易信号ndarray
        signal_out = {}
        for bt_price_type in self.bt_price_types:
            # 针对每种交易价格类型分别遍历所有的策略
            relevant_strategies = self.get_strategies_by_price_type(price_type=bt_price_type)
            relevant_hist_data = self.get_op_history_data_by_price_type(price_type=bt_price_type)
            for stg, dt in zip(relevant_strategies, relevant_hist_data):  # 依次使用选股策略队列中的所有策略逐个生成交易信号
                # TODO: 目前选股蒙板的输入参数还比较复杂，包括shares和dates两个参数，应该消除掉这两个参数，使
                # TODO: sel.generate()函数的signature与tmg.generate()和ricon.generate()一致
                history_length = dt.shape[1]
                op_signals.append(
                        stg.generate(hist_data=dt, shares=shares, dates=date_list[-history_length:]))
                # 生成的交易信号添加到交易信号队列中，

            # 根据蒙板混合前缀表达式混合所有蒙板
            # 针对不同的looping-price-type，应该生成不同的signal，因此不同looping-price-type的signal需要分别混合
            # 最终输出的signal是多个ndarray对象，存储在一个字典中
            signal_blender = self.get_blender(bt_price_type)
            blended_signal = signal_blend(op_signals, blender=signal_blender)
            signal_out[bt_price_type] = blended_signal
        # 将字典中的ndarray对象组装成HistoryPanel对象
        signal_hp_value = np.zeros((*blended_signal.T.shape, self.bt_price_type_count))
        for i, bt_price_type in zip(range(self.bt_price_type_count), self.bt_price_types):
            signal_hp_value[:, :, i] = signal_out[bt_price_type].T
        history_length = signal_hp_value.shape[1]  # find hdate series
        signal_hp = HistoryPanel(signal_hp_value,
                                 levels=shares,
                                 columns=self.bt_price_types,
                                 rows=date_list[-history_length:])
        return signal_hp
