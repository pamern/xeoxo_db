-- =====================================================
-- TABLE: catalog.media
-- Mô tả: Lưu trữ thông tin hình ảnh và video trên Supabase Storage
-- =====================================================

CREATE TABLE catalog.media (
    -- Mã media
    media_id BIGSERIAL PRIMARY KEY,

    -- Đường dẫn file trong Supabase Storage
    storage_key TEXT NOT NULL UNIQUE,

    -- Mô tả hình ảnh
    alt_text VARCHAR(255),

    -- Loại media
    media_type VARCHAR(20) NOT NULL,

    -- MIME type của file
    mime_type VARCHAR(100) NOT NULL,

    -- Dung lượng file (byte)
    file_size BIGINT NOT NULL,

    -- Tên bucket lưu trữ
    bucket_name VARCHAR(100) NOT NULL,

    -- Thời gian tạo
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Thời gian cập nhật
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Chỉ cho phép IMAGE hoặc VIDEO
    CONSTRAINT chk_media_type
        CHECK (media_type IN ('IMAGE', 'VIDEO'))
);

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE catalog.media IS
'Lưu thông tin hình ảnh và video được quản lý trên Supabase Storage.';

COMMENT ON COLUMN catalog.media.media_id IS
'Mã media.';

COMMENT ON COLUMN catalog.media.storage_key IS
'Đường dẫn của file trong Supabase Storage.';

COMMENT ON COLUMN catalog.media.alt_text IS
'Mô tả hình ảnh phục vụ SEO và Accessibility.';

COMMENT ON COLUMN catalog.media.media_type IS
'Loại media (IMAGE hoặc VIDEO).';

COMMENT ON COLUMN catalog.media.mime_type IS
'Định dạng MIME của file (ví dụ image/webp, image/jpeg, video/mp4).';

COMMENT ON COLUMN catalog.media.file_size IS
'Dung lượng file tính theo byte.';

COMMENT ON COLUMN catalog.media.bucket_name IS
'Tên bucket lưu file trong Supabase Storage.';

COMMENT ON COLUMN catalog.media.created_at IS
'Thời gian tạo bản ghi.';

COMMENT ON COLUMN catalog.media.updated_at IS
'Thời gian cập nhật bản ghi.';
