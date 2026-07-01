-- Thêm cột ảnh đại diện
ALTER TABLE catalog.category
ADD COLUMN media_id BIGINT;

-- Thêm khóa ngoại
ALTER TABLE catalog.category
ADD CONSTRAINT fk_category_media
FOREIGN KEY (media_id)
REFERENCES catalog.media(media_id)
ON DELETE SET NULL;

-- Mô tả cột
COMMENT ON COLUMN catalog.category.media_id IS
'Ảnh đại diện của danh mục';