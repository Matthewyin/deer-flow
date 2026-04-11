# 版本控制

版本号 | 修改日期 | 修改说明 | 修改人
:----------- | :-----------: | -----------: | -----------:
v1.0 | 20231204 | 新建文档 | 林丰义 



# 1.OMS迁移项目延迟

## 【事件描述】
IM202311280556628 oms_migration_delay:迁移项目延时

2023-11-28T04:24:38+08:00 [OceanBase] np_4ur1zdx1v8cg OCP告警通知-多条告警 - 名称：oms_migration_delay:迁移项目延时 - 级别：警告 - 告警数量：1 - 聚合分组：oms_migration_delay:3

告警对象：np_4ur1zdx1v8cg 生成时间：2023-11-28T04:24:38+08:00 概述：np_4ur1zdx1v8cg 迁移项目 ob_ga_pcmdb_to_dp_ga_pcmdb-1 增量同步 延时。 详情：np_4ur1zdx1v8cg 迁移项目 ob_ga_pcmdb_to_dp_ga_pcmdb-1 增量同步 延时. 延迟时间: 16871 秒 （10 秒前更新）。

## 【适用人员】
一线数据库值班人员

## 【事件分析】
1、登录OMS生产环境控制台[https://3.14.20.60:8089](https://3.14.20.60:8089/)

![1701657622351](D:\Users\linfengyi\AppData\Roaming\Typora\typora-user-images\1701657622351.png)





2、在“数据迁移”的查询框中输入迁移项目的ID “np_4ur1zdx1v8cg”

点击项目名称“ob_ga_pcmdb_to_dp_ga_pcmdb-1”后，进入[数据迁移](https://3.14.20.60:8089/oms-v2/migration)/ob_ga_pcmdb_to_dp_ga_pcmdb-1界面



![1701660051966](D:\Users\linfengyi\AppData\Roaming\Typora\typora-user-images\1701660051966.png)

通过上述界面上的报错信息，可以确认事件原因：源端数据库pcm_tenant_01.pcmdb的表function_operation_log第9个字段system_log_extend在目标端不存在

3、点击“查看组件监控”，此时incr-Sync增量同步组件的状态为“异常”

![1701672789089](D:\Users\linfengyi\AppData\Roaming\Typora\typora-user-images\1701672789089.png)

4、点击incr-Sync增量同步组件“4.14.20.62-9000:connector_v2:np_4ur1zdx1v8cg-incr_trans-1-0:0000000103”的“查看日志”链接



![1701671715961](D:\Users\linfengyi\AppData\Roaming\Typora\typora-user-images\1701671715961.png)

 [ERROR] [sinkTask-15] [Fatal exception oms record [meta[pcm_tenant_01.pcmdb-function_operation_log,1701671346,UPDATE,1701671345]prev[Struct{function_operation_id(INT64)=2,tech_system_name(VAR_CHAR_STRING)=实体渠道管理系统,system_menu_name(VAR_CHAR_STRING)=查询销售代表业主列表,system_function_name(VAR_CHAR_STRING)=查询销售代表业主列表,operation_content(VAR_CHAR_STRING)=null,original_operation_content(VAR_CHAR_STRING)={"pageNo":1,"pageSize":10,"provinceCenterId":32,"ownerType":-1,"ownerName":"","ownerStatus":[],"certificateType":-1,"certificateNo":"","realNameStatus":[],isManualAuthentication":-1,"um



分析上述报错信息，也可以确认源端数据库pcm_tenant_01.pcmdb的表function_operation_log第9个字段system_log_extend在目标端不存在





5、另外，还可查看incr-Sync增量同步组件所在服务器4.14.20.62的日志

在OMS服务器4.14.20.62的/data/oms/oms_run/4.14.20.62-9000:connector_v2:np_4ur1zdx1v8cg-incr_trans-1-0:0000000103/logs路径下

查看error.log



## 【解决方案】

1、联系研发，提供修复脚本

alter table function_operation_log add system_log_extend varchar(4000) comment '系统日志扩展';

 

2、在目标端数据库上执行修复脚本。