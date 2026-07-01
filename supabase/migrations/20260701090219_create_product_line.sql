CREATE TABLE catalog.product_line (
    product_line_id SERIAL PRIMARY KEY,

    collection_id INT,
    color_id INT,
    material_id INT,

    line_name VARCHAR(255) NOT NULL,
    description TEXT,

    design_style VARCHAR(500),
    features VARCHAR(500),
    usage_context VARCHAR(500),

    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_product_line_collection
        FOREIGN KEY (collection_id)
        REFERENCES catalog.collection(collection_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_product_line_color
        FOREIGN KEY (color_id)
        REFERENCES catalog.color(color_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_product_line_material
        FOREIGN KEY (material_id)
        REFERENCES catalog.material(material_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_product_line_status
        CHECK (
            status IN (
                'ACTIVE',
                'INACTIVE'
            )
        )
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.product_line IS
'Thông tin các dòng sản phẩm.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.product_line.product_line_id IS
'Mã dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.collection_id IS
'Mã bộ sưu tập';

COMMENT ON COLUMN catalog.product_line.color_id IS
'Màu chủ đạo của dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.material_id IS
'Chất liệu chính của dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.line_name IS
'Tên dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.description IS
'Mô tả ngắn của dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.design_style IS
'Kiểu dáng hoặc phong cách thiết kế';

COMMENT ON COLUMN catalog.product_line.features IS
'Đặc điểm nổi bật của dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.usage_context IS
'Hoàn cảnh hoặc mục đích sử dụng phù hợp';

COMMENT ON COLUMN catalog.product_line.status IS
'Trạng thái hoạt động của dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.is_featured IS
'Đánh dấu dòng sản phẩm nổi bật';

COMMENT ON COLUMN catalog.product_line.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.product_line.updated_at IS
'Thời gian cập nhật gần nhất';