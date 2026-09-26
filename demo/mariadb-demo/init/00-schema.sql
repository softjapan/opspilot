-- Intentionally-broken demo schema: m_staff has no composite index on
-- (m_staff_mall_id, m_staff_pc_disp), so filtering on both columns forces a
-- full table scan. This mirrors the missing-index scenario described in
-- plan.md.

USE opspilot_demo;

CREATE TABLE m_staff (
    id INT PRIMARY KEY AUTO_INCREMENT,
    m_staff_mall_id INT NOT NULL,
    m_staff_pc_disp TINYINT NOT NULL DEFAULT 1,
    name VARCHAR(100) NOT NULL
);

-- Keep this setup query out of the slow log; only the seed query in
-- 01-seed-slow-query.sql should be captured.
SET SESSION long_query_time = 1000;

INSERT INTO m_staff (m_staff_mall_id, m_staff_pc_disp, name)
SELECT (seq MOD 50) + 1, seq MOD 2, CONCAT('staff_', seq)
FROM (
    SELECT a.seq + b.seq * 256 + c.seq * 65536 AS seq
    FROM seq_0_to_255 a, seq_0_to_255 b, seq_0_to_9 c
) generated
LIMIT 70000;
