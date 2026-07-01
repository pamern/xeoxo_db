CREATE TABLE catalog.collection (
    collection_id SERIAL PRIMARY KEY,

    collection_name VARCHAR(255) NOT NULL,
    description TEXT,

    media_id BIGINT,
    content_json JSONB,

    season VARCHAR(30) NOT NULL,
    launch_date DATE,

    status VARCHAR(20) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_collection_media
        FOREIGN KEY (media_id)
        REFERENCES catalog.media(media_id),

    CONSTRAINT chk_collection_season
        CHECK (
            season IN ('Spring', 'Summer', 'Fall', 'Winter')
        )
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.collection IS
'Thông tin các bộ sưu tập sản phẩm.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.collection.collection_id IS
'Mã bộ sưu tập';

COMMENT ON COLUMN catalog.collection.collection_name IS
'Tên bộ sưu tập';

COMMENT ON COLUMN catalog.collection.description IS
'Mô tả ngắn về bộ sưu tập';

COMMENT ON COLUMN catalog.collection.media_id IS
'Ảnh đại diện của bộ sưu tập';

COMMENT ON COLUMN catalog.collection.content_json IS
'Nội dung theo cấu trúc json để thiết kế website chi tiết bộ sưu tập';

COMMENT ON COLUMN catalog.collection.season IS
'Mùa ra mắt của bộ sưu tập';

COMMENT ON COLUMN catalog.collection.launch_date IS
'Ngày ra mắt bộ sưu tập';

COMMENT ON COLUMN catalog.collection.status IS
'Trạng thái của bộ sưu tập';

COMMENT ON COLUMN catalog.collection.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.collection.updated_at IS
'Thời gian cập nhật gần nhất';