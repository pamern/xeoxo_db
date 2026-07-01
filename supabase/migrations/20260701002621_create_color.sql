-- =====================================================
-- TABLE: catalog.color
-- Mô tả: Danh mục màu sắc của sản phẩm
-- =====================================================

CREATE TABLE catalog.color (
    -- Mã màu sắc
    color_id SERIAL PRIMARY KEY,

    -- Tên màu
    color_name VARCHAR(100) NOT NULL,

    -- Mã màu HEX (ví dụ: #FFFFFF)
    color_code VARCHAR(7),

    -- Nhóm màu phổ thông hỗ trợ tìm kiếm
    color_group VARCHAR(50),

    -- Hình đại diện của màu
    media_id BIGINT,

    -- Thời gian tạo
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Thời gian cập nhật
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Khóa ngoại
    CONSTRAINT fk_color_media
        FOREIGN KEY (media_id)
        REFERENCES catalog.media(media_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    -- Kiểm tra mã màu HEX
    CONSTRAINT chk_color_hex
        CHECK (
            color_code IS NULL
            OR color_code ~ '^#[A-Fa-f0-9]{6}$'
        )
);

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE catalog.color IS
'Danh mục màu sắc của sản phẩm.';

COMMENT ON COLUMN catalog.color.color_id IS
'Mã màu sắc.';

COMMENT ON COLUMN catalog.color.color_name IS
'Tên màu sắc.';

COMMENT ON COLUMN catalog.color.color_code IS
'Mã màu theo chuẩn HEX (ví dụ: #FFFFFF).';

COMMENT ON COLUMN catalog.color.color_group IS
'Nhóm màu phổ thông phục vụ tìm kiếm và lọc sản phẩm.';

COMMENT ON COLUMN catalog.color.media_id IS
'Mã hình ảnh đại diện của màu sắc.';

COMMENT ON COLUMN catalog.color.created_at IS
'Thời gian tạo bản ghi.';

COMMENT ON COLUMN catalog.color.updated_at IS
'Thời gian cập nhật bản ghi.';

-- =====================================================
-- INDEXES
-- =====================================================

CREATE INDEX idx_color_group
ON catalog.color(color_group);

CREATE INDEX idx_color_media
ON catalog.color(media_id);