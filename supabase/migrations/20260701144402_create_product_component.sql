CREATE TABLE catalog.product_component (
    component_id SERIAL PRIMARY KEY,

    component_name VARCHAR(255) NOT NULL,
    product_line_id INT NOT NULL,

    component_type VARCHAR(30) NOT NULL,

    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    display_order SMALLINT NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_product_component_product_line
        FOREIGN KEY (product_line_id)
        REFERENCES catalog.product_line(product_line_id)
        ON DELETE CASCADE
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.product_component IS
'Các thành phần cấu thành của một dòng sản phẩm.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.product_component.component_id IS
'Mã thành phần sản phẩm';

COMMENT ON COLUMN catalog.product_component.component_name IS
'Tên thành phần sản phẩm';

COMMENT ON COLUMN catalog.product_component.product_line_id IS
'Mã dòng sản phẩm';

COMMENT ON COLUMN catalog.product_component.component_type IS
'Loại thành phần sản phẩm';

COMMENT ON COLUMN catalog.product_component.is_required IS
'Đánh dấu thành phần bắt buộc trong bộ sản phẩm';

COMMENT ON COLUMN catalog.product_component.display_order IS
'Thứ tự hiển thị của thành phần';

COMMENT ON COLUMN catalog.product_component.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.product_component.updated_at IS
'Thời gian cập nhật gần nhất';