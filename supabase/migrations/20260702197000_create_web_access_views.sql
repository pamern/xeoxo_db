BEGIN;

CREATE OR REPLACE VIEW catalog.v_product_line_card
WITH (security_invoker = true)
AS
SELECT
    pl.product_line_id,
    pl.line_name,
    pl.collection_id,
    c.collection_name,
    pl.color_id,
    clr.color_name,
    clr.color_code,
    pl.material_id,
    m.material_name,
    pl.is_featured,
    pl.status,
    main_media.media_id AS main_media_id,
    main_media.storage_key AS main_storage_key,
    price_summary.min_price,
    price_summary.max_price,
    primary_category.category_id AS primary_category_id,
    primary_category.category_name AS primary_category_name
FROM catalog.product_line AS pl
LEFT JOIN catalog.collection AS c
    ON c.collection_id = pl.collection_id
LEFT JOIN catalog.color AS clr
    ON clr.color_id = pl.color_id
LEFT JOIN catalog.material AS m
    ON m.material_id = pl.material_id
LEFT JOIN LATERAL (
    SELECT
        MIN(v.price) AS min_price,
        MAX(v.price) AS max_price
    FROM catalog.product_component AS pc
    INNER JOIN catalog.product_variant AS v
        ON v.component_id = pc.component_id
    WHERE pc.product_line_id = pl.product_line_id
      AND v.status IN ('ACTIVE', 'OUT_OF_STOCK', 'PREORDER', 'COMING_SOON')
) AS price_summary
    ON TRUE
LEFT JOIN LATERAL (
    SELECT
        lc.category_id,
        cat.category_name
    FROM catalog.line_category AS lc
    INNER JOIN catalog.category AS cat
        ON cat.category_id = lc.category_id
    WHERE lc.product_line_id = pl.product_line_id
    ORDER BY lc.is_primary DESC, lc.category_id
    LIMIT 1
) AS primary_category
    ON TRUE
LEFT JOIN LATERAL (
    SELECT
        plm.media_id,
        md.storage_key
    FROM catalog.product_line_media AS plm
    INNER JOIN catalog.media AS md
        ON md.media_id = plm.media_id
    WHERE plm.product_line_id = pl.product_line_id
      AND plm.media_role = 'MAIN'
    ORDER BY plm.display_order, plm.media_id
    LIMIT 1
) AS main_media
    ON TRUE;

CREATE OR REPLACE VIEW catalog.v_product_line_media_ordered
WITH (security_invoker = true)
AS
SELECT
    plm.product_line_id,
    plm.media_id,
    plm.media_role,
    plm.display_order,
    md.storage_key,
    md.bucket_name,
    md.alt_text
FROM catalog.product_line_media AS plm
INNER JOIN catalog.media AS md
    ON md.media_id = plm.media_id;

CREATE OR REPLACE VIEW catalog.v_size_chart_detail
WITH (security_invoker = true)
AS
SELECT
    sc.size_chart_id,
    sc.chart_name,
    sc.product_line_id,
    scc.category_id,
    so.size_option_id,
    so.size_name,
    mt.measurement_type_id,
    mt.measurement_name,
    mt.unit,
    sm.measurement_value,
    sm.measurement_min,
    sm.measurement_max
FROM catalog.size_chart AS sc
LEFT JOIN catalog.size_chart_category AS scc
    ON scc.size_chart_id = sc.size_chart_id
INNER JOIN catalog.size_option AS so
    ON so.size_chart_id = sc.size_chart_id
INNER JOIN catalog.size_measurement AS sm
    ON sm.size_option_id = so.size_option_id
INNER JOIN catalog.measurement_type AS mt
    ON mt.measurement_type_id = sm.measurement_type_id;

CREATE OR REPLACE VIEW sales.v_my_order_summary
WITH (security_invoker = true)
AS
WITH resolved_order_item_product_line AS (
    SELECT
        oi.order_item_id,
        oi.order_id,
        oi.quantity,
        COALESCE(pc.product_line_id, cr.product_line_id) AS product_line_id
    FROM sales.order_item AS oi
    LEFT JOIN catalog.product_variant AS pv
        ON pv.variant_id = oi.variant_id
    LEFT JOIN catalog.product_component AS pc
        ON pc.component_id = pv.component_id
    LEFT JOIN customization.customization_request AS cr
        ON cr.customization_id = oi.customization_id
)
SELECT
    so.order_id,
    so.order_code,
    so.created_at,
    so.order_status AS status,
    so.total_amount,
    COALESCE(SUM(ri.quantity), 0)::BIGINT AS item_count,
    MIN(md.storage_key) FILTER (WHERE md.storage_key IS NOT NULL) AS thumbnail_storage_key
FROM sales.sales_order AS so
LEFT JOIN resolved_order_item_product_line AS ri
    ON ri.order_id = so.order_id
LEFT JOIN catalog.product_line_media AS plm
    ON plm.product_line_id = ri.product_line_id
   AND plm.media_role = 'MAIN'
LEFT JOIN catalog.media AS md
    ON md.media_id = plm.media_id
GROUP BY
    so.order_id,
    so.order_code,
    so.created_at,
    so.order_status,
    so.total_amount;

GRANT SELECT ON TABLE
    catalog.v_product_line_card,
    catalog.v_product_line_media_ordered,
    catalog.v_size_chart_detail
TO anon, authenticated;

GRANT SELECT ON TABLE sales.v_my_order_summary TO authenticated;

COMMIT;
