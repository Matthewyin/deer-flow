# 版本控制

版本号 | 修改日期 | 修改说明 | 修改人
:----------- | :-----------: | -----------: | -----------:
v1.0 | 20230802 | 新建文档 | 郭帅

# 1.OGG延时分析

## 【说明】
IM202301120504105 佣金未到账，本事件主因是由于二代数据结算维护导致，OGG数据同步软件会随着二代系统下线逐步下线，后续数据维护工作会逐渐减少，此后该类事件情况发生概率极低。

## 【适用人员】
一线数据库值班人员

## 【操作内容】
1、即时分析ogg是否延时步骤如下：

使用oracle用户登录出现ogg延时的相关系统
$ cd $GG_HOME              
注：两个节点都有ogg软件时，一般需要带上节点号。如节点一 cd $GG_HOME1
$ ./ggsci
GGSCI (xw-ppsordb-01) 1> info all      ------检查相应的同步链路是否存在延时
Program     Status      Group       Lag at Chkpt  Time Since Chkpt
MANAGER     RUNNING                                           
REPLICAT    RUNNING     RECLCT      00:00:05      00:00:06    
REPLICAT    RUNNING     RECLCT1     00:00:06      00:00:05    
REPLICAT    RUNNING     RECLCT10    00:00:04      00:00:07    
REPLICAT    RUNNING     RECLCT11    00:00:04      00:00:00    
REPLICAT    RUNNING     RECLCT12    00:00:00      00:00:06    
REPLICAT    RUNNING     RECLCT13    00:00:05      00:00:06    
REPLICAT    RUNNING     RECLCT14    00:00:05      00:00:06    
REPLICAT    RUNNING     RECLCT15    01:32:05      00:00:06      <------
REPLICAT    RUNNING     RECLCT16    00:00:05      00:00:06    
REPLICAT    RUNNING     RECLCT17    00:00:05      00:00:06    
。。。 
REPLICAT    RUNNING     RECLCT6     00:00:04      00:00:00    
REPLICAT    ABEND       RECLCT7     00:00:06      00:00:06          <------
REPLICAT    RUNNING     RECLCT8     00:00:05      00:00:06    
REPLICAT    RUNNING     RECLCT9     00:00:05      00:00:01    

1）如上结果，进程 RECLCT15 状态：RUNNING 存在延时：01:32:05
--通过多次执行 info  RECLCT15 检查 RBA 数值是否变化，如下结果：
GGSCI (xw-ppsordb-01) 2> info  RECLCT15   
REPLICAT   RECLCT15  Last Started 2021-11-01 22:42   Status RUNNING
Checkpoint Lag       00:00:05 (updated 00:00:06 ago)
Process ID           30316
Log Read Checkpoint  File /oracle/product/gg1/dirdat/gj000248425
                     2023-07-29 19:24:51.001498  RBA 303865811      <------

GGSCI (xw-ppsordb-01) 3> info  RECLCT15
REPLICAT   RECLCT15  Last Started 2021-11-01 22:42   Status RUNNING
Checkpoint Lag       00:00:00 (updated 00:00:01 ago)
Process ID           30316
Log Read Checkpoint  File /oracle/product/gg1/dirdat/gj000248425
                     2023-07-29 19:25:05.999537  RBA 332618071      <------
--数值变化较快：表示该进程数据同步正常，可能存在大量数据需要同步
--数值变化较慢，表示数据入库较慢或存在长事务。需要登录数据库进一步分析。
--数值长时间无变化，表示当前可能存在长事务或者进程卡死，需要登录数据库进一步分析。

2）如上结果，进程 RECLCT7 状态：ABEND   
--进程 RECLCT7 数据同步中断，通过 view report 命令查看中断原因，进一步恢复数据同步。
 GGSCI (xw-ppsordb-01) 4> view report RECLCT7              
--到 Run Time Messages 日志结尾找ERROR内容
***********************************************************************
**                     Run Time Messages                             **
***********************************************************************

2022-04-18 20:02:04  WARNING OGG-01154  Oracle GoldenGate Delivery for Oracle, reclct6.prm:  SQL error 1400 mapping TIGER.TC_ACCOUNT_TRADE_RECORD to TIGERARCH.TC_ACCOUNT_TRADE_RECORD OCI Error ORA-01400: cannot insert NULL into ("TIGERARCH"."TC_ACCOUNT_TRADE_RECORD"."CHANNEL_TYPE_CODE") (status = 1400), SQL <INSERT INTO "TIGERARCH"."TC_ACCOUNT_TRADE_RECORD" ("REPORT_DATE","PROVINCE_CENTER_ID","TERMINAL_ID","ACCOUNT_TRADE_TYPE_CODE","TID","DESCS") VALUES (:a6,:a7,:a8,:a9,:a10,:a11)>.
2022-04-18 20:02:04  ERROR   OGG-01296  Oracle GoldenGate Delivery for Oracle, reclct6.prm:  Error mapping from TIGER.TC_ACCOUNT_TRADE_RECORD to TIGERARCH.TC_ACCOUNT_TRADE_RECORD.
--如上所示Error ORA-01400: cannot insert NULL into  不能插入空值到表中 


2、历史某一时刻ogg延时分析步骤如下：

使用tiger用户通过PLSQL登录贴源库（sordb）执行如下sql：

select a.*,round((a.sordb_time-a.source_time)*24*60) lag_time
  from d_gg_log a
 where a.source_time > to_date('2023/7/25 0:26', 'yyyy-mm-dd hh24:mi')
   and a.source_time < to_date('2023/7/27 4:26', 'yyyy-mm-dd hh24:mi')
and a.sordb_time-a.source_time>4/60/24    ---延时大于3分钟
GG_SOURCE	PREV_THREAD	CURR_THREAD	SOURCE_TIME	CLCT_TIME	SORDB_TIME	LAG_TIME
TTDB1	RETT1	RECLCT10	2023/7/25 3:19:05	2023/7/25 3:23:17	2023/7/25 3:23:26	4
TTDB1	RETT1	RECLCT10	2023/7/25 3:20:12	2023/7/25 3:24:12	2023/7/25 3:24:17	4
QCDB5	REQC5	RECLCT10	2023/7/26 4:51:17	2023/7/26 4:56:08	2023/7/26 4:56:12	5
--如上结果为大于4分的延时情况，往往对生产系统产生实际影响时，延时多在30分以上，此情况下需要进一步分析。

--分析思路：
1.延时发生时，是否有长事务，如开奖时段。
2.延时发生时，数据库是否产生了大量数据需要同步，可通过小时归档量进一步分析。

