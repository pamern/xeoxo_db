BEGIN;

CREATE INDEX IF NOT EXISTS idx_category_active_department_parent
ON catalog.category (department, parent_id)
WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_product_line_collection_status
ON catalog.product_line (collection_id, status);

CREATE INDEX IF NOT EXISTS idx_product_line_color_status
ON catalog.product_line (color_id, status);

CREATE INDEX IF NOT EXISTS idx_line_category_category_product_line
ON catalog.line_category (category_id, product_line_id);

CREATE INDEX IF NOT EXISTS idx_product_component_product_line_display
ON catalog.product_component (product_line_id, display_order);

CREATE INDEX IF NOT EXISTS idx_product_variant_component_status
ON catalog.product_variant (component_id, status);

CREATE INDEX IF NOT EXISTS idx_product_line_media_line_role_order
ON catalog.product_line_media (product_line_id, media_role, display_order);

CREATE INDEX IF NOT EXISTS idx_size_chart_product_line
ON catalog.size_chart (product_line_id);

CREATE INDEX IF NOT EXISTS idx_size_measurement_size_option_measurement_type
ON catalog.size_measurement (size_option_id, measurement_type_id);

CREATE INDEX IF NOT EXISTS idx_cart_customer
ON sales.cart (customer_id);

CREATE INDEX IF NOT EXISTS idx_cart_item_cart
ON sales.cart_item (cart_id);

CREATE INDEX IF NOT EXISTS idx_sales_order_customer_created_at
ON sales.sales_order (customer_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_address_customer_default_created
ON iam.address (customer_id, is_default DESC, created_at DESC);

COMMIT;
