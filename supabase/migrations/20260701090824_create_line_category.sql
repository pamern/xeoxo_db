CREATE TABLE catalog.line_category (
    product_line_id INT NOT NULL,
    category_id INT NOT NULL,

    is_primary BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    PRIMARY KEY (product_line_id, category_id),

    CONSTRAINT fk_line_category_product_line
        FOREIGN KEY (product_line_id)
        REFERENCES catalog.product_line(product_line_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_line_category_category
        FOREIGN KEY (category_id)
        REFERENCES catalog.category(category_id)
        ON DELETE CASCADE
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.line_category IS
'Liên kết giữa dòng sản phẩm và danh mục sản phẩm.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.line_category.product_line_id IS
'Mã dòng sản phẩm';

COMMENT ON COLUMN catalog.line_category.category_id IS
'Mã danh mục sản phẩm';

COMMENT ON COLUMN catalog.line_category.is_primary IS
'Đánh dấu danh mục chính của dòng sản phẩm';

COMMENT ON COLUMN catalog.line_category.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.line_category.updated_at IS
'Thời gian cập nhật gần nhất';