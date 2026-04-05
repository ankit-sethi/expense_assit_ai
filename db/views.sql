-- Dashboard views for Power BI
-- Apply to a running DB: docker exec -i expense_postgres psql -U expense_user -d expenses_db < db/views.sql

-- 1. Monthly spend trend
CREATE OR REPLACE VIEW v_monthly_spend AS
SELECT
    DATE_TRUNC('month', txn_date)::DATE AS month,
    SUM(amount)                          AS total_spent,
    COUNT(*)                             AS txn_count
FROM expenses
GROUP BY 1
ORDER BY 1;

-- 2. Spend by category
DROP VIEW IF EXISTS v_category_spend;
CREATE VIEW v_category_spend AS
SELECT
    ROW_NUMBER() OVER (ORDER BY total_spent DESC) AS row_id,
    category,
    total_spent,
    txn_count
FROM (
    SELECT
        COALESCE(category, 'Other') AS category,
        SUM(amount)                 AS total_spent,
        COUNT(*)                    AS txn_count
    FROM expenses
    GROUP BY 1
) sub
ORDER BY total_spent DESC;

-- 3. Top 20 merchants by total spend
CREATE OR REPLACE VIEW v_top_merchants AS
SELECT
    merchant,
    SUM(amount)  AS total_spent,
    COUNT(*)     AS txn_count,
    AVG(amount)  AS avg_amount
FROM expenses
WHERE merchant IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 20;

-- 4. Monthly income vs expenses
CREATE OR REPLACE VIEW v_monthly_income_vs_expense AS
SELECT
    month,
    COALESCE(expenses, 0) AS expenses,
    COALESCE(income, 0)   AS income,
    COALESCE(income, 0) - COALESCE(expenses, 0) AS net
FROM (
    SELECT DATE_TRUNC('month', txn_date)::DATE AS month, SUM(amount) AS expenses
    FROM expenses GROUP BY 1
) e
FULL OUTER JOIN (
    SELECT DATE_TRUNC('month', txn_date)::DATE AS month, SUM(amount) AS income
    FROM credits GROUP BY 1
) c USING (month)
ORDER BY month;
