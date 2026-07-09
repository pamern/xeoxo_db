BEGIN;

CREATE OR REPLACE FUNCTION sales.checkout_order(
    p_cart_id BIGINT,
    p_customer_id BIGINT,
    p_address_id BIGINT,
    p_payment_method_id INTEGER,
    p_cart_item_ids BIGINT[],
    p_customer_note TEXT DEFAULT NULL,
    p_voucher_code TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO public, sales, catalog, inventory, iam, customization, util
AS $$
DECLARE
    v_order_id BIGINT;
    v_order_code TEXT := FORMAT(
        'XX%s%s',
        TO_CHAR(CLOCK_TIMESTAMP(), 'YYYYMMDDHH24MISSMS'),
        txid_current()
    );
    v_subtotal NUMERIC(14, 2) := 0;
    v_shipping_fee NUMERIC(14, 2) := 30000;
    v_discount NUMERIC(14, 2) := 0;
    v_total NUMERIC(14, 2);
    v_shipping_id BIGINT;
    v_payment_id BIGINT;
    v_reward iam.loyalty_reward%ROWTYPE;
    v_item RECORD;
    v_inventory RECORD;
    v_remaining INTEGER;
    v_requested_count INTEGER;
    v_selected_count INTEGER;
    v_validated_count INTEGER := 0;
    v_payment_code TEXT;
    v_has_customized_item BOOLEAN := FALSE;
    v_custom_surcharge_total NUMERIC(14, 2) := 0;
    v_reward_used_amount NUMERIC(14, 2) := 0;
BEGIN
    IF COALESCE(auth.role(), 'anon') = 'anon' THEN
        RAISE EXCEPTION 'Ban can dang nhap de checkout';
    END IF;

    IF p_customer_id IS NULL THEN
        RAISE EXCEPTION 'Thieu customer_id';
    END IF;

    IF COALESCE(auth.role(), '') = 'authenticated'
       AND util.current_customer_id() IS DISTINCT FROM p_customer_id THEN
        RAISE EXCEPTION 'Khong the checkout cho customer khac';
    END IF;

    SELECT COUNT(*)
    INTO v_requested_count
    FROM (
        SELECT DISTINCT UNNEST(p_cart_item_ids) AS cart_item_id
    ) AS selected_ids;

    IF p_cart_item_ids IS NULL OR COALESCE(v_requested_count, 0) = 0 THEN
        RAISE EXCEPTION 'Chua chon san pham';
    END IF;

    PERFORM 1
    FROM sales.cart AS c
    WHERE c.cart_id = p_cart_id
      AND c.customer_id = p_customer_id
      AND c.cart_status = 'ACTIVE'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Gio hang khong ton tai, khong thuoc tai khoan hoac da checkout';
    END IF;

    PERFORM 1
    FROM iam.address AS a
    WHERE a.address_id = p_address_id
      AND a.customer_id = p_customer_id
      AND a.is_active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Dia chi giao hang khong hop le';
    END IF;

    SELECT COUNT(*)
    INTO v_selected_count
    FROM sales.cart_item AS ci
    WHERE ci.cart_id = p_cart_id
      AND ci.cart_item_id = ANY(p_cart_item_ids);

    IF v_selected_count <> v_requested_count THEN
        RAISE EXCEPTION 'Cart item khong hop le';
    END IF;

    SELECT pm.method_code
    INTO v_payment_code
    FROM sales.payment_method AS pm
    WHERE pm.method_id = p_payment_method_id
      AND pm.is_active = TRUE;

    IF v_payment_code IS NULL THEN
        RAISE EXCEPTION 'Phuong thuc thanh toan khong hop le';
    END IF;

    FOR v_item IN
        SELECT
            ci.cart_item_id,
            ci.item_type,
            ci.variant_id,
            ci.customization_id,
            ci.quantity,
            ci.unit_price,
            pv.status AS variant_status,
            pc.product_line_id AS variant_product_line_id,
            plv.status AS variant_product_line_status,
            cr.customer_id AS customization_customer_id,
            cr.customization_status,
            cr.component_id AS customization_component_id,
            cr.surcharge_amount,
            cpc.product_line_id AS customization_product_line_id,
            plc.status AS customization_product_line_status
        FROM sales.cart_item AS ci
        LEFT JOIN catalog.product_variant AS pv
            ON pv.variant_id = ci.variant_id
        LEFT JOIN catalog.product_component AS pc
            ON pc.component_id = pv.component_id
        LEFT JOIN catalog.product_line AS plv
            ON plv.product_line_id = pc.product_line_id
        LEFT JOIN customization.customization_request AS cr
            ON cr.customization_id = ci.customization_id
        LEFT JOIN catalog.product_component AS cpc
            ON cpc.component_id = cr.component_id
        LEFT JOIN catalog.product_line AS plc
            ON plc.product_line_id = cpc.product_line_id
        WHERE ci.cart_id = p_cart_id
          AND ci.cart_item_id = ANY(p_cart_item_ids)
        FOR UPDATE OF ci
    LOOP
        v_validated_count := v_validated_count + 1;
        v_subtotal := v_subtotal + (v_item.unit_price * v_item.quantity);

        IF v_item.item_type = 'STANDARD' THEN
            IF v_item.variant_id IS NULL
               OR v_item.variant_status IS DISTINCT FROM 'ACTIVE'
               OR v_item.variant_product_line_status IS DISTINCT FROM 'ACTIVE' THEN
                RAISE EXCEPTION 'San pham thuong % khong con hop le de checkout', v_item.cart_item_id;
            END IF;

            IF (
                SELECT COALESCE(SUM(i.quantity), 0)::INT
                FROM inventory.inventory AS i
                WHERE i.variant_id = v_item.variant_id
            ) < v_item.quantity THEN
                RAISE EXCEPTION 'Variant % khong du ton kho', v_item.variant_id;
            END IF;
        ELSIF v_item.item_type = 'CUSTOMIZED' THEN
            v_has_customized_item := TRUE;

            IF v_item.customization_id IS NULL
               OR v_item.customization_customer_id IS DISTINCT FROM p_customer_id
               OR v_item.customization_product_line_status IS DISTINCT FROM 'ACTIVE'
               OR v_item.customization_status NOT IN (
                    'REQUESTED',
                    'MEASUREMENT_PENDING',
                    'MEASURED',
                    'CONFIRMED'
               ) THEN
                RAISE EXCEPTION 'Yeu cau customize % khong con hop le de checkout', v_item.customization_id;
            END IF;

            v_custom_surcharge_total := v_custom_surcharge_total
                + (COALESCE(v_item.surcharge_amount, 0) * v_item.quantity);
        ELSE
            RAISE EXCEPTION 'Loai cart item khong ho tro: %', v_item.item_type;
        END IF;
    END LOOP;

    IF v_validated_count <> v_requested_count THEN
        RAISE EXCEPTION 'Khong tim thay day du cart item hop le de checkout';
    END IF;

    IF p_voucher_code IS NOT NULL AND BTRIM(p_voucher_code) <> '' THEN
        SELECT *
        INTO v_reward
        FROM iam.loyalty_reward AS lr
        WHERE UPPER(lr.voucher_code) = UPPER(BTRIM(p_voucher_code))
          AND lr.customer_id = p_customer_id
          AND lr.status = 'AVAILABLE'
          AND (lr.expired_at IS NULL OR lr.expired_at > NOW())
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Ma quyen loi khong hop le, khong thuoc tai khoan hoac da het han';
        END IF;

        IF v_reward.reward_type = 'FREE_SHIPPING' THEN
            v_shipping_fee := 0;
            v_reward_used_amount := 30000;
        ELSIF v_reward.reward_type IN ('BIRTHDAY_VOUCHER', 'TIER_VOUCHER') THEN
            v_discount := LEAST(COALESCE(v_reward.reward_value, 0), v_subtotal);
            v_reward_used_amount := v_discount;
        ELSIF v_reward.reward_type = 'FREE_TAILOR' THEN
            IF NOT v_has_customized_item OR v_custom_surcharge_total <= 0 THEN
                RAISE EXCEPTION 'Quyen loi FREE_TAILOR chi ap dung cho san pham customize';
            END IF;

            v_discount := LEAST(v_custom_surcharge_total, v_subtotal);
            v_reward_used_amount := v_discount;
        ELSE
            RAISE EXCEPTION 'Quyen loi nay khong ap dung cho checkout';
        END IF;
    END IF;

    v_total := GREATEST(v_subtotal + v_shipping_fee - v_discount, 0);

    INSERT INTO sales.sales_order (
        order_code,
        customer_id,
        order_date,
        reward_dicount_amount,
        shipping_fee,
        total_amount,
        order_status,
        payment_status,
        customer_note,
        created_at,
        updated_at
    )
    VALUES (
        v_order_code,
        p_customer_id,
        NOW(),
        v_discount,
        v_shipping_fee,
        v_total,
        'PENDING',
        'PENDING',
        p_customer_note,
        NOW(),
        NOW()
    )
    RETURNING order_id INTO v_order_id;

    FOR v_item IN
        SELECT
            ci.cart_item_id,
            ci.item_type,
            ci.variant_id,
            ci.customization_id,
            ci.quantity,
            ci.unit_price,
            cr.customization_status
        FROM sales.cart_item AS ci
        LEFT JOIN customization.customization_request AS cr
            ON cr.customization_id = ci.customization_id
        WHERE ci.cart_id = p_cart_id
          AND ci.cart_item_id = ANY(p_cart_item_ids)
        ORDER BY ci.cart_item_id
    LOOP
        INSERT INTO sales.order_item (
            order_id,
            variant_id,
            customization_id,
            item_type,
            quantity,
            unit_price,
            discount_amount,
            line_total,
            created_at
        )
        VALUES (
            v_order_id,
            v_item.variant_id,
            v_item.customization_id,
            v_item.item_type,
            v_item.quantity,
            v_item.unit_price,
            0,
            v_item.unit_price * v_item.quantity,
            NOW()
        );

        IF v_item.item_type = 'STANDARD' THEN
            v_remaining := v_item.quantity;

            FOR v_inventory IN
                SELECT
                    i.inventory_id,
                    i.quantity
                FROM inventory.inventory AS i
                WHERE i.variant_id = v_item.variant_id
                  AND i.quantity > 0
                ORDER BY i.quantity DESC, i.inventory_id
                FOR UPDATE
            LOOP
                EXIT WHEN v_remaining = 0;

                UPDATE inventory.inventory
                SET
                    quantity = quantity - LEAST(v_inventory.quantity, v_remaining),
                    updated_at = NOW()
                WHERE inventory_id = v_inventory.inventory_id;

                v_remaining := v_remaining - LEAST(v_inventory.quantity, v_remaining);
            END LOOP;

            IF v_remaining > 0 THEN
                RAISE EXCEPTION 'Ton kho thay doi, vui long thu lai';
            END IF;
        ELSIF v_item.item_type = 'CUSTOMIZED'
           AND v_item.customization_status IN ('REQUESTED', 'MEASURED') THEN
            UPDATE customization.customization_request
            SET
                customization_status = 'CONFIRMED',
                updated_at = NOW()
            WHERE customization_id = v_item.customization_id;
        END IF;
    END LOOP;

    INSERT INTO sales.shipping (
        order_id,
        address_id,
        shipping_provider,
        tracking_code,
        shipping_status,
        shipped_at,
        delivered_at,
        created_at,
        updated_at
    )
    VALUES (
        v_order_id,
        p_address_id,
        'PENDING',
        NULL,
        'PENDING',
        NULL,
        NULL,
        NOW(),
        NOW()
    )
    RETURNING shipping_id INTO v_shipping_id;

    INSERT INTO sales.payment (
        order_id,
        method_id,
        amount,
        payment_status,
        transaction_code,
        paid_at,
        created_at,
        updated_at
    )
    VALUES (
        v_order_id,
        p_payment_method_id,
        v_total,
        'PENDING',
        v_payment_code || '-' || v_order_code,
        NOW(),
        NOW(),
        NOW()
    )
    RETURNING payment_id INTO v_payment_id;

    IF v_reward.reward_id IS NOT NULL THEN
        UPDATE iam.loyalty_reward
        SET
            status = 'USED',
            updated_at = NOW()
        WHERE reward_id = v_reward.reward_id;

        INSERT INTO iam.reward_usage (
            reward_id,
            order_id,
            used_amount,
            used_at
        )
        VALUES (
            v_reward.reward_id,
            v_order_id,
            v_reward_used_amount,
            NOW()
        );
    END IF;

    DELETE FROM sales.cart_item
    WHERE cart_id = p_cart_id
      AND cart_item_id = ANY(p_cart_item_ids);

    IF NOT EXISTS (
        SELECT 1
        FROM sales.cart_item AS ci
        WHERE ci.cart_id = p_cart_id
    ) THEN
        UPDATE sales.cart
        SET
            cart_status = 'CHECKOUT',
            updated_at = NOW()
        WHERE cart_id = p_cart_id;
    END IF;

    RETURN JSONB_BUILD_OBJECT(
        'order_id', v_order_id,
        'order_code', v_order_code,
        'order_status', 'PENDING',
        'payment_status', 'PENDING',
        'subtotal_amount', v_subtotal,
        'discount_amount', v_discount,
        'shipping_fee', v_shipping_fee,
        'total_amount', v_total,
        'shipping_id', v_shipping_id,
        'payment_id', v_payment_id
    );
END;
$$;

COMMENT ON FUNCTION sales.checkout_order(
    BIGINT,
    BIGINT,
    BIGINT,
    INTEGER,
    BIGINT[],
    TEXT,
    TEXT
) IS 'Checkout cart item standard/customized, tao order, tru ton kho va ap loyalty reward.';

REVOKE ALL ON FUNCTION sales.checkout_order(
    BIGINT,
    BIGINT,
    BIGINT,
    INTEGER,
    BIGINT[],
    TEXT,
    TEXT
) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION sales.checkout_order(
    BIGINT,
    BIGINT,
    BIGINT,
    INTEGER,
    BIGINT[],
    TEXT,
    TEXT
) TO authenticated;

GRANT EXECUTE ON FUNCTION sales.checkout_order(
    BIGINT,
    BIGINT,
    BIGINT,
    INTEGER,
    BIGINT[],
    TEXT,
    TEXT
) TO service_role;

COMMIT;
