-- Xóa constraint cũ
ALTER TABLE catalog.category
DROP CONSTRAINT IF EXISTS chk_category_department;

-- Tạo lại constraint mới
ALTER TABLE catalog.category
ADD CONSTRAINT chk_category_department
CHECK (
    department IS NULL
    OR department IN ('Men', 'Women', 'Kids')
);