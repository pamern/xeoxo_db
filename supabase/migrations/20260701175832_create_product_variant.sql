CREATE TABLE catalog.product_variant (
    variant_id SERIAL PRIMARY KEY,

    sku VARCHAR(100) NOT NULL UNIQUE,

    component_id INT NOT NULL,
    size_option_id INT,

    price NUMERIC(14,2) NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_product_variant_component
        FOREIGN KEY (component_id)
        REFERENCES catalog.product_component(component_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_product_variant_size_option
        FOREIGN KEY (size_option_id)
        REFERENCES catalog.size_option(size_option_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_product_variant_price
        CHECK (price >= 0),

    CONSTRAINT chk_product_variant_status
        CHECK (
            status IN (
                'ACTIVE',
                'INACTIVE',
                'OUT_OF_STOCK',
                'COMING_SOON',
                'PREORDER'
            )
        )
);

COMMENT ON TABLE catalog.product_variant IS
'Quản lý các biến thể SKU cụ thể của từng thành phần sản phẩm.';

COMMENT ON COLUMN catalog.product_variant.variant_id IS
'Mã biến thể sản phẩm';
COMMENT ON COLUMN catalog.product_variant.sku IS
'Mã SKU';
COMMENT ON COLUMN catalog.product_variant.component_id IS
'Mã thành phần sản phẩm';
COMMENT ON COLUMN catalog.product_variant.size_option_id IS
'Mã size';
COMMENT ON COLUMN catalog.product_variant.price IS
'Giá bán của biến thể';
COMMENT ON COLUMN catalog.product_variant.status IS
'Trạng thái biến thể';
COMMENT ON COLUMN catalog.product_variant.created_at IS
'Thời gian tạo';
COMMENT ON COLUMN catalog.product_variant.updated_at IS
'Thời gian cập nhật gần nhất';