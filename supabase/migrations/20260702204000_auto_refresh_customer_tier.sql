BEGIN;

-- =========================================================
-- PURPOSE
-- - Tự động tính lại hạng thành viên của customer sau khi
--   `total_spent` thay đổi.
-- - Chọn tier cao nhất mà customer đạt được theo
--   `iam.loyalty_tier.min_accumulated_amount`.
-- - Chỉ áp dụng cho customer_type = 'MEMBER'.
--
-- ASSUMPTION
-- - Việc lên/xuống hạng hiện được xác định theo `total_spent`.
-- - `maintain_amount` chưa được dùng trong flow tự động này vì
--   chưa có job rollover năm để đánh giá duy trì hạng ổn định.
-- =========================================================

CREATE OR REPLACE FUNCTION iam.refresh_customer_tier(
    p_customer_id BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_customer_type VARCHAR(20);
    v_total_spent NUMERIC(14, 2);
    v_current_tier_id VARCHAR(20);
    v_target_tier_id VARCHAR(20);
BEGIN
    IF p_customer_id IS NULL THEN
        RETURN;
    END IF;

    SELECT
        c.customer_type,
        c.total_spent,
        c.tier_id
    INTO
        v_customer_type,
        v_total_spent,
        v_current_tier_id
    FROM iam.customer AS c
    WHERE c.customer_id = p_customer_id;

    IF NOT FOUND OR v_customer_type IS DISTINCT FROM 'MEMBER' THEN
        RETURN;
    END IF;

    SELECT lt.loyalty_tier_id
    INTO v_target_tier_id
    FROM iam.loyalty_tier AS lt
    WHERE lt.min_accumulated_amount <= COALESCE(v_total_spent, 0)
    ORDER BY
        lt.min_accumulated_amount DESC,
        util.loyalty_tier_rank(lt.loyalty_tier_id) DESC
    LIMIT 1;

    IF v_target_tier_id IS NOT DISTINCT FROM v_current_tier_id THEN
        RETURN;
    END IF;

    UPDATE iam.customer
    SET
        tier_id = v_target_tier_id,
        last_tier_updated_at = NOW(),
        updated_at = NOW()
    WHERE customer_id = p_customer_id;
END;
$$;

COMMENT ON FUNCTION iam.refresh_customer_tier(BIGINT) IS
'Tự động tính lại loyalty tier của customer MEMBER dựa trên total_spent.';

CREATE OR REPLACE FUNCTION sales.apply_customer_spending_delta(
    p_customer_id BIGINT,
    p_amount_delta NUMERIC,
    p_order_date TIMESTAMPTZ
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_customer_id IS NULL OR COALESCE(p_amount_delta, 0) = 0 THEN
        RETURN;
    END IF;

    UPDATE iam.customer
    SET
        total_spent = GREATEST(total_spent + p_amount_delta, 0),
        spent_in_year = GREATEST(
            spent_in_year + CASE
                WHEN sales.is_current_year_order(p_order_date) THEN p_amount_delta
                ELSE 0
            END,
            0
        ),
        updated_at = NOW()
    WHERE customer_id = p_customer_id;

    PERFORM iam.refresh_customer_tier(p_customer_id);
END;
$$;

COMMENT ON FUNCTION sales.apply_customer_spending_delta(BIGINT, NUMERIC, TIMESTAMPTZ) IS
'Cộng hoặc trừ phần chênh lệch chi tiêu của customer, đồng bộ total_spent, spent_in_year và refresh tier.';

COMMIT;
