-- 仅供次数 API 服务端参考；Python 微服务不连接数据库，也不执行本脚本。
-- 每人每天一行；请求摘要用英文逗号拼接为普通字符串，仅当天去重，不依赖 JSON 类型/函数。
-- 新建表脚本，不是旧表迁移脚本。已有同名旧表时应报错，不能静默沿用旧结构。
CREATE TABLE t_genuiagent_daily_usage (
    id                VARCHAR(64) NOT NULL COMMENT '主键ID',
    uid_hash          CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'uid的SHA256摘要',
    usage_date        DATE NOT NULL COMMENT '北京时间请求入口日期',
    request_id_hashes TEXT CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '当天请求摘要，英文逗号分隔',
    used_count        INT NOT NULL DEFAULT 0 COMMENT '字符串条目数，与字符串在同一事务内更新',
    create_time       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    modify_time       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_uid_date (uid_hash, usage_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户每日卡片生成成功汇总';
