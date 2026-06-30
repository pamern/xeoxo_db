-- =========================================================
-- TABLE: catalog.material
-- DESCRIPTION: Danh mục chất liệu sản phẩm
-- =========================================================

CREATE TABLE catalog.material (
    material_id SERIAL PRIMARY KEY,

    material_name VARCHAR(150) NOT NULL,

    description TEXT,

    care_instruction TEXT,

    media_id BIGINT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ
);

COMMENT ON TABLE catalog.material IS
'Danh mục chất liệu được sử dụng cho các dòng sản phẩm.';

COMMENT ON COLUMN catalog.material.material_id IS
'Khóa chính của chất liệu.';

COMMENT ON COLUMN catalog.material.material_name IS
'Tên chất liệu.';

COMMENT ON COLUMN catalog.material.description IS
'Mô tả chất liệu.';

COMMENT ON COLUMN catalog.material.care_instruction IS
'Hướng dẫn bảo quản chất liệu.';

COMMENT ON COLUMN catalog.material.media_id IS
'Hình ảnh đại diện của chất liệu (FK -> catalog.media).';

COMMENT ON COLUMN catalog.material.is_active IS
'Trạng thái hoạt động của chất liệu.';

COMMENT ON COLUMN catalog.material.created_at IS
'Thời gian tạo bản ghi.';

COMMENT ON COLUMN catalog.material.updated_at IS
'Thời gian cập nhật gần nhất.';