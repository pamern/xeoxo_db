BEGIN;

-- =========================================================
-- PURPOSE
-- - Tự động đồng bộ `iam.customer.total_spent` và
--   `iam.customer.spent_in_year` từ trạng thái đơn hàng.
-- - Khi đơn chuyển sang `COMPLETED`, cộng chi tiêu cho customer.
-- - Khi đơn rời khỏi `COMPLETED` (ví dụ sang `CANCELLED`, `RETURNED`),
--   tự động trừ ngược lại.
-- - Nếu số tiền / customer / order_date của một đơn đã `COMPLETED`
--   bị chỉnh sửa, trigger cũng tự tính phần chênh lệch.
--
-- ASSUMPTION
-- - Giá trị chi tiêu được tính theo:
--   `sales_order.total_amount - sales_order.shipping_fee`
-- - `spent_in_year` chỉ phản ánh tổng chi tiêu của năm hiện tại
--   dựa trên `order_date`.
-- - Việc rollover đầu năm không được xử lý bởi trigger này;
--   nếu cần số liệu chính xác tuyệt đối cho các năm cũ, nên có
--   thêm job định kỳ hoặc materialized aggregation riêng.
-- =========================================================

CREATE OR REPLACE FUNCTION sales.customer_spend_amount(
    p_total_amount NUMERIC,
    p_shipping_fee NUMERIC
)
RETURNS NUMERIC
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT GREATEST(
        COALESCE(p_total_amount, 0) - COALESCE(p_shipping_fee, 0),
        0
    )
$$;

COMMENT ON FUNCTION sales.customer_spend_amount(NUMERIC, NUMERIC) IS
'Tính số tiền chi tiêu hợp lệ của đơn hàng, loại trừ shipping_fee và không âm.';

CREATE OR REPLACE FUNCTION sales.is_current_year_order(
    p_order_date TIMESTAMPTZ
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT
        p_order_date IS NOT NULL
        AND EXTRACT(YEAR FROM p_order_date AT TIME ZONE 'UTC')
            = EXTRACT(YEAR FROM NOW() AT TIME ZONE 'UTC')
$$;

COMMENT ON FUNCTION sales.is_current_year_order(TIMESTAMPTZ) IS
'Kiểm tra order_date có thuộc năm hiện tại hay không để cập nhật spent_in_year.';

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
END;
$$;

COMMENT ON FUNCTION sales.apply_customer_spending_delta(BIGINT, NUMERIC, TIMESTAMPTZ) IS
'Cộng hoặc trừ phần chênh lệch chi tiêu của customer, đồng bộ total_spent và spent_in_year.';

CREATE OR REPLACE FUNCTION sales.trg_sync_customer_spending()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    old_effective_amount NUMERIC := 0;
    new_effective_amount NUMERIC := 0;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.order_status = 'COMPLETED' THEN
            PERFORM sales.apply_customer_spending_delta(
                OLD.customer_id,
                -sales.customer_spend_amount(OLD.total_amount, OLD.shipping_fee),
                OLD.order_date
            );
        END IF;

        RETURN OLD;
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.order_status = 'COMPLETED' THEN
            PERFORM sales.apply_customer_spending_delta(
                NEW.customer_id,
                sales.customer_spend_amount(NEW.total_amount, NEW.shipping_fee),
                NEW.order_date
            );
        END IF;

        RETURN NEW;
    END IF;

    old_effective_amount := CASE
        WHEN OLD.order_status = 'COMPLETED'
            THEN sales.customer_spend_amount(OLD.total_amount, OLD.shipping_fee)
        ELSE 0
    END;

    new_effective_amount := CASE
        WHEN NEW.order_status = 'COMPLETED'
            THEN sales.customer_spend_amount(NEW.total_amount, NEW.shipping_fee)
        ELSE 0
    END;

    IF OLD.customer_id IS NOT DISTINCT FROM NEW.customer_id THEN
        PERFORM sales.apply_customer_spending_delta(
            NEW.customer_id,
            new_effective_amount - old_effective_amount,
            COALESCE(NEW.order_date, OLD.order_date)
        );
    ELSE
        PERFORM sales.apply_customer_spending_delta(
            OLD.customer_id,
            -old_effective_amount,
            OLD.order_date
        );

        PERFORM sales.apply_customer_spending_delta(
            NEW.customer_id,
            new_effective_amount,
            NEW.order_date
        );
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION sales.trg_sync_customer_spending() IS
'Trigger function đồng bộ tổng chi tiêu của customer theo thay đổi trên sales.sales_order.';

DROP TRIGGER IF EXISTS trg_sync_customer_spending ON sales.sales_order;

CREATE TRIGGER trg_sync_customer_spending
AFTER INSERT OR UPDATE OF customer_id, order_date, total_amount, shipping_fee, order_status OR DELETE
ON sales.sales_order
FOR EACH ROW
EXECUTE FUNCTION sales.trg_sync_customer_spending();

COMMIT;
