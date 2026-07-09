BEGIN;

-- =========================================================
-- PURPOSE
-- - Đồng bộ trạng thái catalog dựa trên tồn kho thực tế.
-- - Khi một variant hết sạch tồn kho ở tất cả branch:
--   -> catalog.product_variant.status = 'OUT_OF_STOCK'
-- - Khi toàn bộ variant/size của một product line đều hết hàng:
--   -> catalog.product_line.status = 'INACTIVE'
-- - Khi có hàng trở lại:
--   -> variant đang OUT_OF_STOCK sẽ trở về ACTIVE
--   -> product_line sẽ trở về ACTIVE nếu còn ít nhất một variant có hàng
--
-- Ghi chú:
-- - Trigger này chỉ tự động chuyển trạng thái giữa ACTIVE <-> OUT_OF_STOCK
--   cho product_variant.
-- - Các trạng thái nghiệp vụ khác như INACTIVE, COMING_SOON, PREORDER
--   của variant sẽ không bị ghi đè khi có thay đổi tồn kho.
-- =========================================================

CREATE OR REPLACE FUNCTION inventory.sync_catalog_stock_status_for_variant(
    p_variant_id INT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    total_quantity INT := 0;
    current_variant_status VARCHAR(20);
    target_line_id INT;
    has_any_stock BOOLEAN := FALSE;
BEGIN
    IF p_variant_id IS NULL THEN
        RETURN;
    END IF;

    SELECT
        pv.status,
        pc.product_line_id
    INTO
        current_variant_status,
        target_line_id
    FROM catalog.product_variant AS pv
    JOIN catalog.product_component AS pc
        ON pc.component_id = pv.component_id
    WHERE pv.variant_id = p_variant_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT COALESCE(SUM(i.quantity), 0)::INT
    INTO total_quantity
    FROM inventory.inventory AS i
    WHERE i.variant_id = p_variant_id;

    IF total_quantity <= 0 AND current_variant_status = 'ACTIVE' THEN
        UPDATE catalog.product_variant
        SET
            status = 'OUT_OF_STOCK',
            updated_at = NOW()
        WHERE variant_id = p_variant_id;
    ELSIF total_quantity > 0 AND current_variant_status = 'OUT_OF_STOCK' THEN
        UPDATE catalog.product_variant
        SET
            status = 'ACTIVE',
            updated_at = NOW()
        WHERE variant_id = p_variant_id;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM catalog.product_variant AS pv
        JOIN catalog.product_component AS pc
            ON pc.component_id = pv.component_id
        LEFT JOIN inventory.inventory AS i
            ON i.variant_id = pv.variant_id
        WHERE pc.product_line_id = target_line_id
        GROUP BY pv.variant_id
        HAVING COALESCE(SUM(i.quantity), 0) > 0
    )
    INTO has_any_stock;

    UPDATE catalog.product_line
    SET
        status = CASE
            WHEN has_any_stock THEN 'ACTIVE'
            ELSE 'INACTIVE'
        END,
        updated_at = NOW()
    WHERE product_line_id = target_line_id
      AND status IS DISTINCT FROM CASE
            WHEN has_any_stock THEN 'ACTIVE'
            ELSE 'INACTIVE'
        END;
END;
$$;

COMMENT ON FUNCTION inventory.sync_catalog_stock_status_for_variant(INT) IS
'Đồng bộ status của product_variant và product_line dựa trên tổng tồn kho của một variant.';

CREATE OR REPLACE FUNCTION inventory.trg_sync_catalog_stock_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM inventory.sync_catalog_stock_status_for_variant(OLD.variant_id);
        RETURN OLD;
    END IF;

    PERFORM inventory.sync_catalog_stock_status_for_variant(NEW.variant_id);

    IF TG_OP = 'UPDATE' AND NEW.variant_id IS DISTINCT FROM OLD.variant_id THEN
        PERFORM inventory.sync_catalog_stock_status_for_variant(OLD.variant_id);
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION inventory.trg_sync_catalog_stock_status() IS
'Trigger function đồng bộ status catalog sau khi inventory thay đổi.';

DROP TRIGGER IF EXISTS trg_sync_catalog_stock_status ON inventory.inventory;

CREATE TRIGGER trg_sync_catalog_stock_status
AFTER INSERT OR UPDATE OR DELETE
ON inventory.inventory
FOR EACH ROW
EXECUTE FUNCTION inventory.trg_sync_catalog_stock_status();

COMMIT;
