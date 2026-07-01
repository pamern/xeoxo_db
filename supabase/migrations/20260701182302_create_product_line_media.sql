CREATE TABLE catalog.product_line_media (
    product_line_id INT NOT NULL,

    media_id BIGINT NOT NULL,

    media_role VARCHAR(30) NOT NULL,

    display_order SMALLINT NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (product_line_id, media_id),

    CONSTRAINT fk_product_line_media_product_line
        FOREIGN KEY (product_line_id)
        REFERENCES catalog.product_line(product_line_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_product_line_media_media
        FOREIGN KEY (media_id)
        REFERENCES catalog.media(media_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_product_line_media_role
        CHECK (
            media_role IN (
                'Main',
                'Gallery',
                'Detail',
                'Lookbook'
            )
        )
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.product_line_media IS
'Liên kết hình ảnh với dòng sản phẩm và xác định vai trò hiển thị của từng hình ảnh.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.product_line_media.product_line_id IS
'Mã dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line_media.media_id IS
'Mã hình ảnh';

COMMENT ON COLUMN catalog.product_line_media.media_role IS
'Vai trò của hình ảnh trong dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line_media.display_order IS
'Thứ tự hiển thị của hình ảnh';

COMMENT ON COLUMN catalog.product_line_media.created_at IS
'Thời gian tạo';