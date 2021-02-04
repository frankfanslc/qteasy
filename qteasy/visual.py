# coding=utf-8
# visual.py

# ======================================
# This file contains components for the qt
# to establish visual outputs of price data
# loop result and strategy optimization
# results as well
# ======================================

import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.cbook as cbook
import matplotlib.ticker as mtick

import pandas as pd
import datetime
from .tsfuncs import get_bar, name_change
from .utilfuncs import time_str_format


def candle(stock, start=None, end=None, asset_type='E', figsize=(10, 5), mav=(5, 10, 20, 30), no_visual=False):
    daily, share_name = _prepare_mpf_data(stock=stock, start=start, end=end, asset_type=asset_type)
    mc = mpf.make_marketcolors(up='r', down='g',
                               volume='in')
    s = mpf.make_mpf_style(marketcolors=mc)
    if not no_visual:
        mpf.plot(daily,
                 title=share_name,
                 volume=True,
                 type='candle',
                 style=s,
                 figsize=figsize,
                 mav=mav,
                 figscale=0.5)


def ohlc(stock, start=None, end=None, asset_type='E', figsize=(10, 5), mav=(5, 10, 20, 30), no_visual=False):
    daily, share_name = _prepare_mpf_data(stock=stock, start=start, end=end, asset_type=asset_type)
    mc = mpf.make_marketcolors(up='r', down='g',
                               volume='in')
    s = mpf.make_mpf_style(marketcolors=mc)
    if not no_visual:
        mpf.plot(daily,
                 title=share_name,
                 volume=True,
                 type='ohlc',
                 style=s,
                 figsize=figsize,
                 mav=mav,
                 figscale=0.5)


def renko(stock, start=None, end=None, asset_type='E', figsize=(10, 5), mav=(5, 10, 20, 30), no_visual=False):
    daily, share_name = _prepare_mpf_data(stock=stock, start=start, end=end, asset_type=asset_type)
    mc = mpf.make_marketcolors(up='r', down='g',
                               volume='in')
    s = mpf.make_mpf_style(marketcolors=mc)
    if not no_visual:
        mpf.plot(daily,
                 title=share_name,
                 volume=True,
                 type='renko',
                 style=s,
                 figsize=figsize,
                 mav=mav,
                 figscale=0.5)


def _prepare_mpf_data(stock, start=None, end=None, asset_type='E'):
    today = datetime.datetime.today()
    if end is None:
        end = today.strftime('%Y-%m-%d')
    if start is None:
        try:
            start = (pd.Timestamp(end) - pd.Timedelta(30, 'd')).strftime('%Y-%m-%d')
        except:
            start = today - pd.Timedelta(30, 'd')

    data = get_bar(shares=stock, start=start, end=end, asset_type=asset_type)
    if asset_type == 'E':
        share_basic = name_change(shares=stock, fields='ts_code,name,start_date,end_date,change_reason')
        if share_basic.empty:
            raise ValueError(f'stock {stock} can not be found or does not exist!')
        share_name = stock + ' - ' + share_basic.name[0]
        # debug
        # print(share_basic.head())
    else:
        share_name = stock + ' - ' + asset_type
    # data.info()
    daily = data[['open', 'high', 'low', 'close', 'vol']]
    daily.columns = ['open', 'high', 'low', 'close', 'volume']
    daily.index = data['trade_date']
    daily = daily.rename(index=pd.Timestamp).sort_index()
    # print(daily.head())
    # manipulating of mpf:
    return daily, share_name


def plot_loop_result(result, msg: dict):
    """plot the loop results in a fancy way that displays all infomration more clearly"""
    # prepare result dataframe
    if not isinstance(result, pd.DataFrame):
        raise TypeError('')
    if result.empty:
        raise ValueError()
    # TODO: needs to find out all the stock holding columns,
    # TODO: and calculate change according to the change of all
    # TODO: stocks
    result_columns = result.columns
    fixed_column_items = ['fee', 'cash', 'value', 'reference']
    stock_holdings = [item for
                      item in
                      result_columns if
                      item not in fixed_column_items and
                      item[-2:] != '_p']
    change = (result[stock_holdings] - result[stock_holdings].shift(1)).sum(1)
    start_point = result['value'].iloc[0]
    adjust_factor = result['value'].iloc[0] / result['reference'].iloc[0]
    reference = result['reference'] * adjust_factor
    ret = result['value'] - result['value'].shift(1)
    position = 1 - (result['cash'] / result['value'])
    return_rate = (result.value - start_point) / start_point * 100
    ref_rate = (reference - start_point) / start_point * 100
    position_bounds = [result.index[0]]
    position_bounds.extend(result.loc[change != 0].index)
    position_bounds.append(result.index[-1])

    # process plot figure and axes formatting
    years = mdates.YearLocator()  # every year
    months = mdates.MonthLocator()  # every month
    years_fmt = mdates.DateFormatter('%Y')

    CHART_WIDTH = 0.88

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 8), facecolor=(0.82, 0.83, 0.85))
    fig.suptitle('Back Testing Result - reference: 000300.SH')

    fig.text(0.05, 0.93, f'periods: {msg["years"]} years, '
                         f'from: {msg["loop_start"].date()} to {msg["loop_end"].date()}   ... '
                         f'time consumed:   signal creation: {time_str_format(msg["run_time_p"])};'
                         f'  back test:{time_str_format(msg["run_time_l"])}')
    fig.text(0.05, 0.90, f'operation summary: {msg["oper_count"].values.sum()}     Total operation fee:'
                         f'¥{msg["total_fee"]:13,.2f}     '
                         f'total investment amount: ¥{msg["total_invest"]:13,.2f}    '
                         f'final value:  ¥{msg["final_value"]:13,.2f}')
    fig.text(0.05, 0.87, f'Total return: {msg["rtn"] * 100 - 100:.3f}%    '
                         f'Avg annual return: {((msg["rtn"]) ** (1 / msg["years"]) - 1) * 100: .3f}%    '
                         f'ref return: {msg["ref_rtn"] * 100:.3f}%    '
                         f'Avg annual ref return: {msg["ref_annual_rtn"] * 100:.3f}%')
    fig.text(0.05, 0.84, f'alpha: {msg["alpha"]:.3f}  '
                         f'Beta: {msg["beta"]:.3f}  '
                         f'Sharp ratio: {msg["sharp"]:.3f}  '
                         f'Info ratio: {msg["info"]:.3f}  '
                         f'250-day volatility: {msg["volatility"]:.3f}  '
                         f'Max drawdown: {msg["mdd"] * 100:.3f}% from {msg["max_date"].date()} '
                         f'to {msg["low_date"].date()}')

    ax1.set_position([0.05, 0.41, CHART_WIDTH, 0.40])
    ax1.plot(result.index, ref_rate, linestyle='-',
             color=(0.4, 0.6, 0.8), alpha=0.85, label='reference')
    ax1.plot(result.index, return_rate, linestyle='-',
             color=(0.8, 0.2, 0.0), alpha=0.85, label='return')
    ax1.set_ylabel('Total return rate')
    ax1.grid(True)
    ax1.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax1.fill_between(result.index, 0, ref_rate,
                     where=ref_rate >= 0,
                     facecolor=(0.4, 0.6, 0.2), alpha=0.35)
    ax1.fill_between(result.index, 0, ref_rate,
                     where=ref_rate < 0,
                     facecolor=(0.8, 0.2, 0.0), alpha=0.35)
    ax1.yaxis.tick_right()
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['bottom'].set_visible(False)
    ax1.spines['left'].set_visible(False)
    for first, second, long_short in zip(position_bounds[:-2], position_bounds[1:], position.loc[position_bounds[:-2]]):
        # fill long/short strips with grey
        # ax1.axvspan(first, second, facecolor=str(1 - color), alpha=0.2)
        # fill long/short strips with green/red colors
        if long_short > 0:
            # fill green strips if position is long
            ax1.axvspan(first, second,
                        facecolor=((1 - 0.6 * long_short), (1 - 0.4 * long_short), (1 - 0.8 * long_short)),
                        alpha=0.2)
        else:
            # fill red strips if position is short
            ax1.axvspan(first, second,
                        facecolor=((1 - 0.2 * long_short), (1 - 0.8 * long_short), (1 - long_short)),
                        alpha=0.2)
    ax1.annotate("max_drawdown",
                 xy=(msg["max_date"], return_rate[msg["low_date"]]),
                 xytext=(0.7, 0.0),
                 textcoords='axes fraction',
                 arrowprops=dict(facecolor='black', shrink=0.3),
                 horizontalalignment='right',
                 verticalalignment='top')
    ax1.legend()

    ax2.set_position([0.05, 0.23, CHART_WIDTH, 0.18])
    ax2.plot(result.index, position)
    ax2.set_ylabel('Amount bought / sold')
    ax2.set_xlabel(None)
    ax2.yaxis.tick_right()
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['bottom'].set_visible(False)
    ax2.spines['left'].set_visible(False)
    ax2.grid(True)

    ax3.set_position([0.05, 0.05, CHART_WIDTH, 0.18])
    ax3.bar(result.index, ret)
    ax3.set_ylabel('Daily return')
    ax3.set_xlabel('date')
    ax3.yaxis.tick_right()
    ax3.spines['top'].set_visible(False)
    ax3.spines['right'].set_visible(False)
    ax3.spines['bottom'].set_visible(False)
    ax3.spines['left'].set_visible(False)
    ax3.grid(True)

    # format the ticks
    ax1.xaxis.set_major_locator(years)
    ax1.xaxis.set_major_formatter(years_fmt)
    ax1.xaxis.set_minor_locator(months)

    ax2.xaxis.set_major_locator(years)
    ax2.xaxis.set_major_formatter(years_fmt)
    ax2.xaxis.set_minor_locator(months)

    ax3.xaxis.set_major_locator(years)
    ax3.xaxis.set_major_formatter(years_fmt)
    ax3.xaxis.set_minor_locator(months)

    plt.show()


def print_loop_result(result, messages=None, columns=None, headers=None, formatter=None):
    """ 格式化打印输出单次回测的结果，根据columns、headers、formatter等参数选择性输出result中的结果
        确保输出的格式美观一致

    :param result:
    :param messages:
    :param columns:
    :param headers:
    :param formatter:
    :return:
    """
    print(f'==================================== \n'
          f'|                                  |\n'
          f'|       BACK TESTING RESULT        |\n'
          f'|                                  |\n'
          f'====================================')
    print(f'\nqteasy running mode: 1 - History back looping\n'
          f'time consumption for operate signal creation: {time_str_format(messages["run_time_p"])} ms\n'
          f'time consumption for operation back looping: {time_str_format(messages["run_time_l"])} ms\n')
    print(f'investment starts on {result.index[0]}\nends on {result.index[-1]}\n'
          f'Total looped periods: {messages["years"]} years.')
    print(f'operation summary:\n {messages["oper_count"]}\n'
          f'Total operation fee:     ¥{messages["total_fee"]:13,.2f}')
    print(f'total investment amount: ¥{messages["total_invest"]:13,.2f}\n'
          f'final value:             ¥{messages["final_value"]:13,.2f}')
    print(f'Total return: {messages["rtn"] * 100 - 100:.3f}% \n'
          f'Average Yearly return rate: {(messages["rtn"] ** (1 / messages["years"]) - 1) * 100: .3f}%')
    print(f'Total reference return: {messages["ref_rtn"] * 100:.3f}% \n'
          f'Average Yearly reference return rate: {messages["ref_annual_rtn"] * 100:.3f}%')
    print(f'strategy messages indicators: \n'
          f'alpha:               {messages["alpha"]:.3f}\n'
          f'Beta:                {messages["beta"]:.3f}\n'
          f'Sharp ratio:         {messages["sharp"]:.3f}\n'
          f'Info ratio:          {messages["info"]:.3f}\n'
          f'250 day volatility:  {messages["volatility"]:.3f}\n'
          f'Max drawdown:        {messages["mdd"] * 100:.3f}% '
          f'from {messages["max_date"].date()} to {messages["low_date"].date()}')
    print(f'\n===========END OF REPORT=============\n')



def print_table_result(result, messages=None, config=None, columns=None, headers=None, formatter=None):
    """ 以表格形式格式化输出批量数据结果，输出结果的格式和内容由columns，headers，formatter等参数控制，
        输入的数据包括多组同样结构的数据，输出时可以选择以统计结果的形式输出或者以表格形式输出，也可以同时
        以统计结果和表格的形式输出

    :param result:
    :param messages:
    :param columns:
    :param headers:
    :param formatter:
    :return:
    """

    ref_rtn, ref_annual_rtn = messages['ref_rtn'], messages['ref_annual_rtn']
    print(f'investment starts on {messages["loop_start"]}\nends on {messages["loop_end"]}\n'
          f'Total looped periods: {result.years[0]} years.')
    print(f'total investment amount: ¥{result.total_invest[0]:13,.2f}')
    print(f'Reference index type is {config.reference_asset} at {config.ref_asset_type}\n'
          f'Total reference return: {ref_rtn * 100:.3f}% \n'
          f'Average Yearly reference return rate: {ref_annual_rtn * 100:.3f}%')
    print(f'statistical analysis of optimal strategy messages indicators: \n'
          f'total return:        {result.total_return.mean() * 100:.3f}% ±'
          f' {result.total_return.std() * 100:.3f}%\n'
          f'annual return:       {result.annual_return.mean() * 100:.3f}% ±'
          f' {result.annual_return.std() * 100:.3f}%\n'
          f'alpha:               {result.alpha.mean():.3f} ± {result.alpha.std():.3f}\n'
          f'Beta:                {result.beta.mean():.3f} ± {result.beta.std():.3f}\n'
          f'Sharp ratio:         {result.sharp.mean():.3f} ± {result.sharp.std():.3f}\n'
          f'Info ratio:          {result["info"].mean():.3f} ± {result["info"].std():.3f}\n'
          f'250 day volatility:  {result.volatility.mean():.3f} ± {result.volatility.std():.3f}\n'
          f'other messages indicators are listed in below table\n')
    # result.sort_values(by='final_value', ascending=False, inplace=True)
    print(result.to_string(columns=["par",
                                            "sell_count",
                                            "buy_count",
                                            "total_fee",
                                            "final_value",
                                            "total_return",
                                            "mdd"],
                           header=["Strategy items",
                                           "Sell-outs",
                                           "Buy-ins",
                                           "Total fee",
                                           "Final value",
                                           "ROI",
                                           "MDD"],
                           formatters={'total_fee':    '{:,.2f}'.format,
                                               'final_value':  '{:,.2f}'.format,
                                               'total_return': '{:.1%}'.format,
                                               'mdd':          '{:.1%}'.format,
                                               'sell_count':   '{:.1f}'.format,
                                               'buy_count':    '{:.1f}'.format},
                           justify='center'))
    print(f'\n===========END OF REPORT=============\n')