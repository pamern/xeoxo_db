BEGIN;

CREATE OR REPLACE FUNCTION util.current_customer_id()
RETURNS BIGINT
LANGUAGE sql
STABLE
AS $$
    SELECT c.customer_id
    FROM iam.customer AS c
    WHERE c.account_id = auth.uid()
    LIMIT 1
$$;

COMMENT ON FUNCTION util.current_customer_id() IS
'Trả về customer_id của user hiện tại dựa trên auth.uid().';

GRANT USAGE ON SCHEMA catalog TO anon, authenticated;
GRANT USAGE ON SCHEMA iam TO authenticated;
GRANT USAGE ON SCHEMA sales TO authenticated;
GRANT USAGE ON SCHEMA customization TO authenticated;
GRANT USAGE ON SCHEMA util TO authenticated;

GRANT EXECUTE ON FUNCTION util.current_customer_id() TO authenticated;

GRANT SELECT ON TABLE
    catalog.category,
    catalog.collection,
    catalog.product_line,
    catalog.line_category,
    catalog.product_component,
    catalog.product_variant,
    catalog.color,
    catalog.material,
    catalog.size_chart,
    catalog.size_chart_category,
    catalog.size_option,
    catalog.size_measurement,
    catalog.measurement_type,
    catalog.media,
    catalog.product_line_media
TO anon, authenticated;

GRANT SELECT, UPDATE ON TABLE iam.customer TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE iam.address TO authenticated;
GRANT SELECT ON TABLE iam.loyalty_reward, iam.reward_usage TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE sales.cart, sales.cart_item TO authenticated;
GRANT SELECT ON TABLE sales.sales_order, sales.order_item TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE customization.measurement_profile, customization.measurement_profile_detail TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE catalog.personal_color_result, catalog.personal_color_result_color TO authenticated;

GRANT USAGE, SELECT ON SEQUENCE
    iam.address_address_id_seq,
    sales.cart_cart_id_seq,
    sales.cart_item_cart_item_id_seq,
    customization.measurement_profile_measurement_profile_id_seq,
    customization.measurement_profile_detail_measurement_detail_id_seq,
    catalog.personal_color_result_result_id_seq
TO authenticated;

REVOKE ALL ON TABLE
    iam.account,
    iam.staff,
    iam.branch,
    inventory.inventory,
    sales.payment,
    sales.refund,
    sales.shipping,
    sales.return_request,
    sales.return_item,
    sales.review,
    sales.review_media,
    support.chat_conversation,
    support.chat_message,
    support.chat_message_media,
    support.chat_assignment_history,
    support.chat_message_read,
    support.chat_tag,
    support.chat_conversation_tag
FROM anon, authenticated;

ALTER TABLE catalog.category ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.collection ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.product_line ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.line_category ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.product_component ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.product_variant ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.color ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.material ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.size_chart ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.size_chart_category ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.size_option ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.size_measurement ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.measurement_type ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.media ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.product_line_media ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.personal_color_result ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.personal_color_result_color ENABLE ROW LEVEL SECURITY;

ALTER TABLE iam.customer ENABLE ROW LEVEL SECURITY;
ALTER TABLE iam.address ENABLE ROW LEVEL SECURITY;
ALTER TABLE iam.loyalty_reward ENABLE ROW LEVEL SECURITY;
ALTER TABLE iam.reward_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE iam.account ENABLE ROW LEVEL SECURITY;
ALTER TABLE iam.staff ENABLE ROW LEVEL SECURITY;
ALTER TABLE iam.branch ENABLE ROW LEVEL SECURITY;

ALTER TABLE sales.cart ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales.cart_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales.sales_order ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales.order_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales.payment ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales.refund ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales.shipping ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales.return_request ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales.return_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales.review ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales.review_media ENABLE ROW LEVEL SECURITY;

ALTER TABLE customization.measurement_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE customization.measurement_profile_detail ENABLE ROW LEVEL SECURITY;

ALTER TABLE inventory.inventory ENABLE ROW LEVEL SECURITY;

ALTER TABLE support.chat_conversation ENABLE ROW LEVEL SECURITY;
ALTER TABLE support.chat_message ENABLE ROW LEVEL SECURITY;
ALTER TABLE support.chat_message_media ENABLE ROW LEVEL SECURITY;
ALTER TABLE support.chat_assignment_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE support.chat_message_read ENABLE ROW LEVEL SECURITY;
ALTER TABLE support.chat_tag ENABLE ROW LEVEL SECURITY;
ALTER TABLE support.chat_conversation_tag ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS category_public_select ON catalog.category;
CREATE POLICY category_public_select
ON catalog.category
FOR SELECT
TO anon, authenticated
USING (is_active = TRUE);

DROP POLICY IF EXISTS collection_public_select ON catalog.collection;
CREATE POLICY collection_public_select
ON catalog.collection
FOR SELECT
TO anon, authenticated
USING (status = 'ACTIVE');

DROP POLICY IF EXISTS product_line_public_select ON catalog.product_line;
CREATE POLICY product_line_public_select
ON catalog.product_line
FOR SELECT
TO anon, authenticated
USING (status = 'ACTIVE');

DROP POLICY IF EXISTS line_category_public_select ON catalog.line_category;
CREATE POLICY line_category_public_select
ON catalog.line_category
FOR SELECT
TO anon, authenticated
USING (
    EXISTS (
        SELECT 1
        FROM catalog.product_line AS pl
        WHERE pl.product_line_id = line_category.product_line_id
          AND pl.status = 'ACTIVE'
    )
    AND EXISTS (
        SELECT 1
        FROM catalog.category AS c
        WHERE c.category_id = line_category.category_id
          AND c.is_active = TRUE
    )
);

DROP POLICY IF EXISTS product_component_public_select ON catalog.product_component;
CREATE POLICY product_component_public_select
ON catalog.product_component
FOR SELECT
TO anon, authenticated
USING (
    EXISTS (
        SELECT 1
        FROM catalog.product_line AS pl
        WHERE pl.product_line_id = product_component.product_line_id
          AND pl.status = 'ACTIVE'
    )
);

DROP POLICY IF EXISTS product_variant_public_select ON catalog.product_variant;
CREATE POLICY product_variant_public_select
ON catalog.product_variant
FOR SELECT
TO anon, authenticated
USING (status IN ('ACTIVE', 'OUT_OF_STOCK', 'PREORDER', 'COMING_SOON'));

DROP POLICY IF EXISTS color_public_select ON catalog.color;
CREATE POLICY color_public_select
ON catalog.color
FOR SELECT
TO anon, authenticated
USING (TRUE);

DROP POLICY IF EXISTS material_public_select ON catalog.material;
CREATE POLICY material_public_select
ON catalog.material
FOR SELECT
TO anon, authenticated
USING (is_active = TRUE);

DROP POLICY IF EXISTS size_chart_public_select ON catalog.size_chart;
CREATE POLICY size_chart_public_select
ON catalog.size_chart
FOR SELECT
TO anon, authenticated
USING (
    is_active = TRUE
    AND (
        product_line_id IS NULL
        OR EXISTS (
            SELECT 1
            FROM catalog.product_line AS pl
            WHERE pl.product_line_id = size_chart.product_line_id
              AND pl.status = 'ACTIVE'
        )
    )
);

DROP POLICY IF EXISTS size_chart_category_public_select ON catalog.size_chart_category;
CREATE POLICY size_chart_category_public_select
ON catalog.size_chart_category
FOR SELECT
TO anon, authenticated
USING (
    EXISTS (
        SELECT 1
        FROM catalog.size_chart AS sc
        WHERE sc.size_chart_id = size_chart_category.size_chart_id
          AND sc.is_active = TRUE
    )
    AND EXISTS (
        SELECT 1
        FROM catalog.category AS c
        WHERE c.category_id = size_chart_category.category_id
          AND c.is_active = TRUE
    )
);

DROP POLICY IF EXISTS size_option_public_select ON catalog.size_option;
CREATE POLICY size_option_public_select
ON catalog.size_option
FOR SELECT
TO anon, authenticated
USING (
    EXISTS (
        SELECT 1
        FROM catalog.size_chart AS sc
        WHERE sc.size_chart_id = size_option.size_chart_id
          AND sc.is_active = TRUE
    )
);

DROP POLICY IF EXISTS size_measurement_public_select ON catalog.size_measurement;
CREATE POLICY size_measurement_public_select
ON catalog.size_measurement
FOR SELECT
TO anon, authenticated
USING (
    EXISTS (
        SELECT 1
        FROM catalog.size_option AS so
        INNER JOIN catalog.size_chart AS sc
            ON sc.size_chart_id = so.size_chart_id
        WHERE so.size_option_id = size_measurement.size_option_id
          AND sc.is_active = TRUE
    )
);

DROP POLICY IF EXISTS measurement_type_public_select ON catalog.measurement_type;
CREATE POLICY measurement_type_public_select
ON catalog.measurement_type
FOR SELECT
TO anon, authenticated
USING (TRUE);

DROP POLICY IF EXISTS media_public_select ON catalog.media;
CREATE POLICY media_public_select
ON catalog.media
FOR SELECT
TO anon, authenticated
USING (TRUE);

DROP POLICY IF EXISTS product_line_media_public_select ON catalog.product_line_media;
CREATE POLICY product_line_media_public_select
ON catalog.product_line_media
FOR SELECT
TO anon, authenticated
USING (
    EXISTS (
        SELECT 1
        FROM catalog.product_line AS pl
        WHERE pl.product_line_id = product_line_media.product_line_id
          AND pl.status = 'ACTIVE'
    )
);

DROP POLICY IF EXISTS customer_self_select ON iam.customer;
CREATE POLICY customer_self_select
ON iam.customer
FOR SELECT
TO authenticated
USING (account_id = auth.uid());

DROP POLICY IF EXISTS customer_self_update ON iam.customer;
CREATE POLICY customer_self_update
ON iam.customer
FOR UPDATE
TO authenticated
USING (account_id = auth.uid())
WITH CHECK (account_id = auth.uid());

DROP POLICY IF EXISTS address_self_all ON iam.address;
CREATE POLICY address_self_all
ON iam.address
FOR ALL
TO authenticated
USING (customer_id = util.current_customer_id())
WITH CHECK (customer_id = util.current_customer_id());

DROP POLICY IF EXISTS loyalty_reward_self_select ON iam.loyalty_reward;
CREATE POLICY loyalty_reward_self_select
ON iam.loyalty_reward
FOR SELECT
TO authenticated
USING (customer_id = util.current_customer_id());

DROP POLICY IF EXISTS reward_usage_self_select ON iam.reward_usage;
CREATE POLICY reward_usage_self_select
ON iam.reward_usage
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM iam.loyalty_reward AS lr
        WHERE lr.reward_id = reward_usage.reward_id
          AND lr.customer_id = util.current_customer_id()
    )
);

DROP POLICY IF EXISTS cart_self_all ON sales.cart;
CREATE POLICY cart_self_all
ON sales.cart
FOR ALL
TO authenticated
USING (customer_id = util.current_customer_id())
WITH CHECK (customer_id = util.current_customer_id());

DROP POLICY IF EXISTS cart_item_self_all ON sales.cart_item;
CREATE POLICY cart_item_self_all
ON sales.cart_item
FOR ALL
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM sales.cart AS c
        WHERE c.cart_id = cart_item.cart_id
          AND c.customer_id = util.current_customer_id()
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM sales.cart AS c
        WHERE c.cart_id = cart_item.cart_id
          AND c.customer_id = util.current_customer_id()
    )
);

DROP POLICY IF EXISTS sales_order_self_select ON sales.sales_order;
CREATE POLICY sales_order_self_select
ON sales.sales_order
FOR SELECT
TO authenticated
USING (customer_id = util.current_customer_id());

DROP POLICY IF EXISTS order_item_self_select ON sales.order_item;
CREATE POLICY order_item_self_select
ON sales.order_item
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM sales.sales_order AS so
        WHERE so.order_id = order_item.order_id
          AND so.customer_id = util.current_customer_id()
    )
);

DROP POLICY IF EXISTS measurement_profile_self_all ON customization.measurement_profile;
CREATE POLICY measurement_profile_self_all
ON customization.measurement_profile
FOR ALL
TO authenticated
USING (customer_id = util.current_customer_id())
WITH CHECK (customer_id = util.current_customer_id());

DROP POLICY IF EXISTS measurement_profile_detail_self_all ON customization.measurement_profile_detail;
CREATE POLICY measurement_profile_detail_self_all
ON customization.measurement_profile_detail
FOR ALL
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM customization.measurement_profile AS mp
        WHERE mp.measurement_profile_id = measurement_profile_detail.measurement_profile_id
          AND mp.customer_id = util.current_customer_id()
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM customization.measurement_profile AS mp
        WHERE mp.measurement_profile_id = measurement_profile_detail.measurement_profile_id
          AND mp.customer_id = util.current_customer_id()
    )
);

DROP POLICY IF EXISTS personal_color_result_self_all ON catalog.personal_color_result;
CREATE POLICY personal_color_result_self_all
ON catalog.personal_color_result
FOR ALL
TO authenticated
USING (customer_id = util.current_customer_id())
WITH CHECK (customer_id = util.current_customer_id());

DROP POLICY IF EXISTS personal_color_result_color_self_all ON catalog.personal_color_result_color;
CREATE POLICY personal_color_result_color_self_all
ON catalog.personal_color_result_color
FOR ALL
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM catalog.personal_color_result AS r
        WHERE r.result_id = personal_color_result_color.result_id
          AND r.customer_id = util.current_customer_id()
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM catalog.personal_color_result AS r
        WHERE r.result_id = personal_color_result_color.result_id
          AND r.customer_id = util.current_customer_id()
    )
);

COMMIT;
