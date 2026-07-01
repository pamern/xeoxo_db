CREATE TABLE catalog.size_option (
    size_option_id SERIAL PRIMARY KEY,

    size_chart_id INT NOT NULL,

    size_name VARCHAR(20) NOT NULL,
    display_order SMALLINT NOT NULL,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_size_option_size_chart
        FOREIGN KEY (size_chart_id)
        REFERENCES catalog.size_chart(size_chart_id)
        ON DELETE CASCADE
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.size_option IS
'Quản lý các kích thước (size) thuộc từng bảng size.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.size_option.size_option_id IS
'Mã size';

COMMENT ON COLUMN catalog.size_option.size_chart_id IS
'Mã bảng size';

COMMENT ON COLUMN catalog.size_option.size_name IS
'Tên size (XS, S, M, L, XL, XXL,...)';

COMMENT ON COLUMN catalog.size_option.display_order IS
'Thứ tự hiển thị của size trong bảng size';

COMMENT ON COLUMN catalog.size_option.description IS
'Mô tả hoặc ghi chú về size';

COMMENT ON COLUMN catalog.size_option.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.size_option.updated_at IS
'Thời gian cập nhật gần nhất';