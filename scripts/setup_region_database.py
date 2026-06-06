#!/usr/bin/env python3
# scripts/setup_region_database.py
# Creates or migrates a province database on the City Hall server.
# Usage:
#   python setup_region_database.py --region bioko
#   python setup_region_database.py --region litoral
#   python setup_region_database.py --region centrosur
#   python setup_region_database.py --region welenzas
#   python setup_region_database.py --region kientem
#   python setup_region_database.py --region interprovince

import argparse
import sys
import os
import mariadb

REGIONS = ['bioko', 'litoral', 'centrosur', 'welenzas', 'kientem', 'interprovince']

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS PARADAS (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    lat        DECIMAL(9,6) NOT NULL DEFAULT 0,
    lng        DECIMAL(9,6) NOT NULL DEFAULT 0,
    region     VARCHAR(100) NOT NULL,
    province   VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_stop_region (name, region),
    INDEX idx_region (region),
    INDEX idx_province (province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS RUTAS (
    id         VARCHAR(50)  PRIMARY KEY,
    route_type TINYINT      NOT NULL DEFAULT 1,
    client     VARCHAR(255) NOT NULL,
    region     VARCHAR(100) NOT NULL,
    province   VARCHAR(50),
    language   VARCHAR(10)  NOT NULL DEFAULT 'es',
    timezone   VARCHAR(50)  NOT NULL DEFAULT 'Africa/Malabo',
    is_interprovince TINYINT DEFAULT 0,
    created_at DATETIME     DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_region (region),
    INDEX idx_province (province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS RUTA_PARADAS (
    route_id   VARCHAR(50) NOT NULL,
    stop_order SMALLINT    NOT NULL,
    stop_id    INT         NOT NULL,
    province   VARCHAR(50),
    PRIMARY KEY (route_id, stop_order),
    FOREIGN KEY (route_id) REFERENCES RUTAS(id) ON DELETE CASCADE,
    FOREIGN KEY (stop_id)  REFERENCES PARADAS(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS registered_buses (
    bus_id     VARCHAR(255) PRIMARY KEY,
    region     VARCHAR(100),
    province   VARCHAR(50),
    last_seen  DATETIME,
    status     VARCHAR(20)  DEFAULT 'active',
    INDEX idx_region   (region),
    INDEX idx_province (province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS bus_positions (
    bus_id     VARCHAR(255) PRIMARY KEY,
    route_id   VARCHAR(50),
    stop_name  VARCHAR(255),
    lat        DECIMAL(9,6),
    lng        DECIMAL(9,6),
    direction  VARCHAR(255),
    province   VARCHAR(50),
    updated_at DATETIME,
    INDEX idx_updated  (updated_at),
    INDEX idx_province (province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stop_events (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    bus_id     VARCHAR(255) NOT NULL,
    route_id   VARCHAR(50),
    stop_name  VARCHAR(255),
    lat        DECIMAL(9,6),
    lng        DECIMAL(9,6),
    direction  VARCHAR(255),
    client     VARCHAR(255),
    region     VARCHAR(100),
    province   VARCHAR(50),
    language   VARCHAR(10),
    timezone   VARCHAR(50),
    arrived_at DATETIME NOT NULL,
    INDEX idx_bus      (bus_id),
    INDEX idx_route    (route_id),
    INDEX idx_arrived  (arrived_at),
    INDEX idx_province (province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  PARTITION BY RANGE (TO_DAYS(arrived_at)) (
    PARTITION p_old     VALUES LESS THAN (TO_DAYS('2025-01-01')),
    PARTITION p_2025    VALUES LESS THAN (TO_DAYS('2026-01-01')),
    PARTITION p_2026    VALUES LESS THAN (TO_DAYS('2027-01-01')),
    PARTITION p_future  VALUES LESS THAN MAXVALUE
  );

CREATE TABLE IF NOT EXISTS travel_times (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    route_id       VARCHAR(50)  NOT NULL,
    from_stop      VARCHAR(255) NOT NULL,
    to_stop        VARCHAR(255) NOT NULL,
    province       VARCHAR(50),
    hour_of_day    TINYINT      NOT NULL,
    day_of_week    TINYINT      NOT NULL,
    median_seconds INT          NOT NULL,
    sample_count   INT          NOT NULL,
    computed_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_tt (route_id, from_stop, to_stop, hour_of_day, day_of_week),
    INDEX idx_route    (route_id),
    INDEX idx_province (province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS engine_readings (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    bus_id           VARCHAR(255) NOT NULL,
    province         VARCHAR(50),
    recorded_at      DATETIME     NOT NULL,
    rpm              FLOAT,
    coolant_temp_c   FLOAT,
    engine_load_pct  FLOAT,
    throttle_pct     FLOAT,
    fuel_trim_short  FLOAT,
    fuel_trim_long   FLOAT,
    intake_temp_c    FLOAT,
    oil_pressure_psi FLOAT,
    battery_v        FLOAT,
    engine_runtime_s INT,
    fault_code_count TINYINT DEFAULT 0,
    fault_codes      TEXT,
    local_severity   VARCHAR(16) DEFAULT 'ok',
    INDEX idx_bus_time (bus_id, recorded_at),
    INDEX idx_province (province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  PARTITION BY RANGE (TO_DAYS(recorded_at)) (
    PARTITION p_old    VALUES LESS THAN (TO_DAYS('2025-01-01')),
    PARTITION p_2025   VALUES LESS THAN (TO_DAYS('2026-01-01')),
    PARTITION p_2026   VALUES LESS THAN (TO_DAYS('2027-01-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
  );

CREATE TABLE IF NOT EXISTS engine_alerts (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    bus_id      VARCHAR(255) NOT NULL,
    province    VARCHAR(50),
    alert_type  VARCHAR(32)  NOT NULL,
    severity    VARCHAR(16)  NOT NULL,
    sensor      VARCHAR(64),
    value       FLOAT,
    threshold   FLOAT,
    z_score     FLOAT,
    message     TEXT,
    notified    TINYINT DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_bus      (bus_id),
    INDEX idx_time     (created_at),
    INDEX idx_notified (notified),
    INDEX idx_province (province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS engine_health_scores (
    bus_id      VARCHAR(255) PRIMARY KEY,
    province    VARCHAR(50),
    score       TINYINT  NOT NULL DEFAULT 100,
    trend       VARCHAR(16) DEFAULT 'stable',
    last_alert  VARCHAR(16) DEFAULT 'ok',
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS relay_nodes (
    node_name       VARCHAR(50) PRIMARY KEY,
    province        VARCHAR(50),
    backbone_up     TINYINT  DEFAULT 1,
    cache_size      INT      DEFAULT 0,
    connected_buses INT      DEFAULT 0,
    signal_dbm      VARCHAR(20),
    last_seen       DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sms_logs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    phone       VARCHAR(30),
    province    VARCHAR(50),
    message_in  TEXT,
    message_out TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS whatsapp_sessions (
    phone      VARCHAR(30) PRIMARY KEY,
    province   VARCHAR(50),
    state      VARCHAR(50),
    context    JSON,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def main():
    parser = argparse.ArgumentParser(description='Set up a province database')
    parser.add_argument('--region',   required=True, choices=REGIONS)
    parser.add_argument('--host',     default=os.getenv('DB_HOST',     '127.0.0.1'))
    parser.add_argument('--port',     default=int(os.getenv('DB_PORT', '3306')), type=int)
    parser.add_argument('--user',     default=os.getenv('DB_USER',     'root'))
    parser.add_argument('--password', default=os.getenv('DB_PASSWORD', ''))
    args = parser.parse_args()

    db_name = f"bus_tracking_gq_{args.region}"
    print(f"Setting up database: {db_name} on {args.host}:{args.port}")

    try:
        conn = mariadb.connect(
            host=args.host, port=args.port,
            user=args.user, password=args.password
        )
        cur = conn.cursor()

        # Create database
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute(f"USE `{db_name}`")

        # Grant permissions to app user
        cur.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO 'bioko_app'@'localhost'")
        cur.execute("FLUSH PRIVILEGES")

        # Create all tables
        for stmt in SCHEMA_SQL.strip().split(';'):
            stmt = stmt.strip()
            if stmt:
                try:
                    cur.execute(stmt)
                except mariadb.Error as e:
                    if 'already exists' not in str(e).lower():
                        print(f"  Warning: {e}")

        conn.commit()
        print(f"Database {db_name} ready.")
        print(f"\nNext steps:")
        print(f"  python admin_cli.py --region {args.region} import-stops data/stops_{args.region}.csv")
        print(f"  python admin_cli.py --region {args.region} add-route --id R01 ...")

    except mariadb.Error as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == '__main__':
    main()
