BEGIN;

-- View dùng cho trang listing, homepage section, search result hoặc collection page.
-- Mục đích là trả về "card data" đã gom sẵn thông tin chính của product line:
-- tên dòng sản phẩm, slug, collection, màu, chất liệu, ảnh chính,
-- khoảng giá và danh mục chính để frontend render nhanh danh sách sản phẩm.
CREATE OR REPLACE VIEW catalog.v_product_line_card
WITH (security_invoker = true)
AS
SELECT
    pl.product_line_id,
    pl.line_name,
    pl.slug,
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
    ON TRUE
WHERE pl.status = 'ACTIVE';

-- View dùng khi frontend cần gallery media của một product line theo đúng thứ tự hiển thị.
-- Phù hợp cho trang chi tiết sản phẩm, carousel ảnh và các block preview media
-- vì đã join sẵn metadata file từ `catalog.media`.
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

-- View dùng khi cần render chi tiết bảng size đã trải phẳng theo từng size
-- và từng loại số đo. Phù hợp cho trang sản phẩm, modal chọn size hoặc
-- màn hình tư vấn số đo vì frontend không cần tự join nhiều bảng catalog.
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

-- View dùng khi frontend cần biết một variant hoặc product line còn hàng hay không
-- mà không đọc trực tiếp bảng inventory nội bộ. View này chỉ public trạng thái
-- tổng hợp theo variant: tổng số lượng, số chi nhánh còn hàng và cờ còn hàng.
CREATE OR REPLACE VIEW catalog.v_inventory_availability
AS
SELECT
    pl.product_line_id,
    pl.slug AS product_line_slug,
    pv.variant_id,
    pv.sku,
    pv.status AS variant_status,
    COALESCE(stock.total_quantity, 0)::INT AS total_quantity,
    COALESCE(stock.in_stock_branch_count, 0)::INT AS in_stock_branch_count,
    (COALESCE(stock.total_quantity, 0) > 0) AS is_in_stock
FROM catalog.product_variant AS pv
INNER JOIN catalog.product_component AS pc
    ON pc.component_id = pv.component_id
INNER JOIN catalog.product_line AS pl
    ON pl.product_line_id = pc.product_line_id
LEFT JOIN (
    SELECT
        i.variant_id,
        SUM(i.quantity)::BIGINT AS total_quantity,
        COUNT(*) FILTER (WHERE i.quantity > 0)::BIGINT AS in_stock_branch_count
    FROM inventory.inventory AS i
    GROUP BY i.variant_id
) AS stock
    ON stock.variant_id = pv.variant_id
WHERE pl.status = 'ACTIVE'
  AND pv.status IN ('ACTIVE', 'OUT_OF_STOCK', 'PREORDER', 'COMING_SOON');

-- View dùng cho màn hình "đơn hàng của tôi" hoặc lịch sử mua hàng của customer.
-- Mục đích là trả về summary của từng đơn: mã đơn, ngày tạo, trạng thái,
-- tổng tiền, số lượng item và thumbnail đại diện để frontend hiển thị danh sách.
CREATE OR REPLACE VIEW sales.v_my_order_summary
WITH (security_invoker = true)
AS
WITH resolved_order_item_product_line AS (
    SELECT
        oi.order_item_id,
        oi.order_id,
        oi.quantity,
        COALESCE(pc.product_line_id, cpc.product_line_id) AS product_line_id
    FROM sales.order_item AS oi
    LEFT JOIN catalog.product_variant AS pv
        ON pv.variant_id = oi.variant_id
    LEFT JOIN catalog.product_component AS pc
        ON pc.component_id = pv.component_id
    LEFT JOIN customization.customization_request AS cr
        ON cr.customization_id = oi.customization_id
    LEFT JOIN catalog.product_component AS cpc
        ON cpc.component_id = cr.component_id
)
SELECT
    so.order_id,
    so.order_code,
    so.created_at,
    so.order_status AS status,
    so.payment_status,
    so.total_amount,
    COALESCE(SUM(ri.quantity), 0)::BIGINT AS item_count,
    MIN(sh.shipping_status) FILTER (WHERE sh.shipping_status IS NOT NULL) AS shipping_status,
    MIN(sh.tracking_code) FILTER (WHERE sh.tracking_code IS NOT NULL) AS tracking_code,
    MIN(rf.refund_status) FILTER (WHERE rf.refund_status IS NOT NULL) AS refund_status,
    MIN(md.storage_key) FILTER (WHERE md.storage_key IS NOT NULL) AS thumbnail_storage_key
FROM sales.sales_order AS so
LEFT JOIN resolved_order_item_product_line AS ri
    ON ri.order_id = so.order_id
LEFT JOIN catalog.product_line_media AS plm
    ON plm.product_line_id = ri.product_line_id
   AND plm.media_role = 'MAIN'
LEFT JOIN catalog.media AS md
    ON md.media_id = plm.media_id
LEFT JOIN sales.shipping AS sh
    ON sh.order_id = so.order_id
LEFT JOIN sales.payment AS pay
    ON pay.order_id = so.order_id
LEFT JOIN sales.refund AS rf
    ON rf.payment_id = pay.payment_id
GROUP BY
    so.order_id,
    so.order_code,
    so.created_at,
    so.order_status,
    so.payment_status,
    so.total_amount;

GRANT SELECT ON TABLE
    catalog.v_product_line_card,
    catalog.v_product_line_media_ordered,
    catalog.v_size_chart_detail
TO anon, authenticated;

GRANT SELECT ON TABLE
    catalog.v_product_line_card,
    catalog.v_product_line_media_ordered,
    catalog.v_size_chart_detail
TO service_role;

GRANT SELECT ON TABLE sales.v_my_order_summary TO authenticated;
GRANT SELECT ON TABLE sales.v_my_order_summary TO service_role;

COMMIT;
