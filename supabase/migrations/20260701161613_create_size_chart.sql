CREATE TABLE catalog.size_chart (
    size_chart_id SERIAL PRIMARY KEY,

    chart_name VARCHAR(255) NOT NULL,
    product_line_id INT,

    description TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_size_chart_product_line
        FOREIGN KEY (product_line_id)
        REFERENCES catalog.product_line(product_line_id)
        ON DELETE SET NULL
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.size_chart IS
'Thông tin bảng quy đổi kích thước của sản phẩm.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.size_chart.size_chart_id IS
'Mã bảng size';

COMMENT ON COLUMN catalog.size_chart.chart_name IS
'Tên bảng size';

COMMENT ON COLUMN catalog.size_chart.product_line_id IS
'Mã dòng sản phẩm nếu bảng size chỉ áp dụng cho một dòng sản phẩm';

COMMENT ON COLUMN catalog.size_chart.description IS
'Ghi chú hoặc mô tả bảng size';

COMMENT ON COLUMN catalog.size_chart.is_active IS
'Trạng thái sử dụng của bảng size';

COMMENT ON COLUMN catalog.size_chart.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.size_chart.updated_at IS
'Thời gian cập nhật gần nhất';