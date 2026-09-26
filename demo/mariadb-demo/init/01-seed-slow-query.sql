-- Force this single query into the slow log by lowering the threshold to 0
-- just for this session. This is the query OpsPilot's demo investigation
-- targets: a full table scan caused by the missing composite index.

USE opspilot_demo;

SET SESSION long_query_time = 0;

SELECT * FROM m_staff WHERE m_staff_mall_id = 5 AND m_staff_pc_disp = 1;
