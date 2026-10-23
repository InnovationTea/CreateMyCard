-- 仅供次数 API 服务端参考；Python 微服务不连接数据库，也不执行本脚本。
-- 不以 usage_date 作为唯一键的一部分，确保同一 uid + requestId 跨天仍只计一次。
CREATE TABLE IF NOT EXISTS t_genuiagent_daily_usage (
    id                VARCHAR(64) NOT NULL COMMENT '主键ID',
    uid_hash          CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'uid的SHA256摘要',
    request_id_hash   CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'requestId的SHA256摘要',
    usage_date        DATE NOT NULL COMMENT '北京时间请求入口日期',
    create_time       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    modify_time       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_uid_request (uid_hash, request_id_hash),
    KEY idx_uid_date (uid_hash, usage_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户每日卡片生成成功记录';
