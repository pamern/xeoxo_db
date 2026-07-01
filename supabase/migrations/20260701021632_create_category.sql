-- =====================================================
-- TABLE: catalog.category
-- Mô tả: Danh mục sản phẩm
-- =====================================================

CREATE TABLE catalog.category (
    -- Mã danh mục
    category_id SERIAL PRIMARY KEY,

    -- Tên danh mục
    category_name VARCHAR(255) NOT NULL,

    -- Mô tả danh mục
    description TEXT,

    -- Danh mục cha
    parent_id INT,

    -- Phân loại khách hàng (Nam, Nữ, Trẻ Em)
    department VARCHAR(30),

    -- Đường dẫn URL
    slug VARCHAR(255) NOT NULL UNIQUE,

    -- Trạng thái hoạt động
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Thời gian tạo
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Thời gian cập nhật
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Khóa ngoại tự tham chiếu
    CONSTRAINT fk_category_parent
        FOREIGN KEY (parent_id)
        REFERENCES catalog.category(category_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    -- Phân loại người dùng
    CONSTRAINT chk_category_department
        CHECK (
            department IS NULL
            OR department IN ('MEN', 'WOMEN', 'KIDS')
        )
);

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE catalog.category IS
'Danh mục sản phẩm.';

COMMENT ON COLUMN catalog.category.category_id IS
'Mã danh mục sản phẩm.';

COMMENT ON COLUMN catalog.category.category_name IS
'Tên danh mục sản phẩm.';

COMMENT ON COLUMN catalog.category.description IS
'Mô tả danh mục sản phẩm.';

COMMENT ON COLUMN catalog.category.parent_id IS
'Mã danh mục cha, NULL nếu là danh mục gốc.';

COMMENT ON COLUMN catalog.category.department IS
'Đối tượng sử dụng của danh mục (Men, Women, Kids).';

COMMENT ON COLUMN catalog.category.slug IS
'Slug dùng để tạo URL thân thiện.';

COMMENT ON COLUMN catalog.category.is_active IS
'Trạng thái hoạt động của danh mục.';

COMMENT ON COLUMN catalog.category.created_at IS
'Thời gian tạo bản ghi.';

COMMENT ON COLUMN catalog.category.updated_at IS
'Thời gian cập nhật bản ghi.';
