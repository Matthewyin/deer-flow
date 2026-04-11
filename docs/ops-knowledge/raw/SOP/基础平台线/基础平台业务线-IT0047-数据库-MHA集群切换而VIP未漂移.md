# 版本控制

版本号 | 修改日期 | 修改说明 | 修改人
:----------- | :-----------: | -----------: | -----------:
v1.0 | 20231221 | 新建文档 | 林丰义 



# 1.MHA集群切换而VIP未漂移

## 【事件描述】
IM202312200559962/技术中心巡检报竞猜翻译系统BLIDB mysql集群故障

（1）故障位置：BLIDB mysql集群

 （2）故障描述：技术中心巡检报竞猜系统BLIDB mysql集群故障。竞猜系统BLIDB mysql检测到当前的主节点无法ping通，开始自动集群切换，集群切换成功，但VIP未切换成功，导致应用存在单点风险。

 （3）故障发生时间：12月20日1:32

 （4）故障影响：应用存在单点风险

 （5）用户报障时间:12月20日7时26分

## 【适用人员】
一线数据库值班人员

## 【事件分析】
### 1、检查切换日志并**确定发生故障切换的集群**

此处以BLIDB 为例，在MHA管理节点(4.190.121.191)执行如下操作

more  /data/masterha/BLIDB/manager.log

查看日志最末尾内容，如果MHA切换成功，则应该如下显示：

----- Failover Report -----

app: MySQL Master failover 4.190.80.81(4.190.80.81:31306) to 4.190.80.82(4.190.80.82:31306) succeeded

Master 4.190.80.81(4.190.80.81:31306) is down!

Check MHA Manager logs at G3MHAMGR01:/data/masterha/BLIDB1/manager.log for details.

Started automated(non-interactive) failover.
Invalidated master IP address on 4.190.80.81(4.190.80.81:31306)
The latest slave 4.190.80.82(4.190.80.82:31306) has all relay logs for recovery.
Selected 4.190.80.82(4.190.80.82:31306) as a new master.
4.190.80.82(4.190.80.82:31306): OK: Applying all logs succeeded.
4.190.80.82(4.190.80.82:31306): OK: Activated master IP address.
4.190.80.83(4.190.80.83:31306): This host has the latest relay log events.
Generating relay diff files from the latest slave succeeded.
4.190.80.83(4.190.80.83:31306): OK: Applying all logs succeeded. Slave started, replicating from 4.190.80.82(4.190.80.82:31306)
4.190.80.82(4.190.80.82:31306): Resetting slave info succeeded.
Master failover to 4.190.80.82(4.190.80.82:31306) completed successfully.

如果没有显示“completed successfully”，则视为切换失败，此时应停止一切操作，联系系统支援处理。



### 2、 检查集群的复制健康状态&vip绑定状态

2.1  在MHA 管理节点(4.190.121.191)，检查当前集群的复制健康状态：

/usr/local/bin/masterha_check_repl --conf=/etc/mha/BLIDB/app.cnf

本例中故障主节点host为4.190.80.81，所以需要确定的是slave2(4.190.80.83)是否已经将复制转向了new master(4.190.80.82)

因为已经发生了切换，所以当前集群已经没有备选主(slave 2为异步节点，不作为备选主)。此时集群本身就是异常状态，所以只要剩余的两个节点复制是正常的，那么输出信息的最后错误信息可以忽略。

2.2 登录slave2(4.190.80.83) ，确认slave2连接的master节点为new master(4.190.80.82).

SQL> show slave status\G

 

2.3 检查MHA切换后，vip绑定是否正常。此时vip应该绑定在new master上，也就是备选主。在故障节点(4.190.80.81)和new master(4.190.80.82)上分别执行如下命令：

**ip addr show**

显示的信息中，除了eth0之外，还有一个eth0:0，就是vip。

可以判断出，vip没有漂移到 new master(4.190.80.82)上



**确认集群切换和复制状态一切正常后，开始执行修复操作。**



### 3、确定 master的log file和pos位置



分析slave1(4.190.80.82)的error.log日志：

2023-12-20T00:41:10.466457Z 8485818 [Note] Slave SQL thread for channel '' initialized, starting replication in log 'bin.000026' at position 14096080, relay log '/data/relaylog/relay.000001' position: 4
2023-12-20T00:41:10.466607Z 8485817 [Note] Slave I/O thread for channel '': **connected to master 'repl@4.190.80.81:31306',replication started in log 'bin.000026' at position 14096080**



分析slave2(4.190.80.83)的error.log日志:

2023-12-20T00:39:47.414999Z 8496541 [Note] Slave SQL thread for channel '' initialized, starting replication in log 'bin.000026' at position 14096080, relay log '/data/relaylog/relay.000001' position: 4
2023-12-20T00:39:47.415266Z 8496540 [Note] Slave I/O thread for channel '': **connected to master 'repl@4.190.80.81:31306',replication started in log 'bin.000026' at position 14096080**



通过分析slave1(4.190.80.82)和slave2(4.190.80.83)日志，确认连接master(4.190.80.81)主库的文件bin.000026和位置14096080



### **4、重新配置slave1(4.190.80.82)和slave2(4.190.80.83)**

CHANGE MASTER TO 

MASTER_HOST='4.190.80.81', 

MASTER_PORT=31306, 

MASTER_LOG_FILE='bin.000026', 

MASTER_LOG_POS=14096080,              

MASTER_USER='repl', 

MASTER_PASSWORD='********';

start slave;





