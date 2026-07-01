CREATE TABLE catalog.measurement_type (
    measurement_type_id SERIAL PRIMARY KEY,

    measurement_code VARCHAR(50) NOT NULL UNIQUE,
    measurement_name VARCHAR(150) NOT NULL,

    unit VARCHAR(10) NOT NULL,
    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

COMMENT ON TABLE catalog.measurement_type IS
'Quản lý các loại thông số đo được sử dụng trong bảng size.';

COMMENT ON COLUMN catalog.measurement_type.measurement_type_id IS
'Mã thông số đo';

COMMENT ON COLUMN catalog.measurement_type.measurement_code IS
'Mã định danh của thông số đo';

COMMENT ON COLUMN catalog.measurement_type.measurement_name IS
'Tên thông số đo';

COMMENT ON COLUMN catalog.measurement_type.unit IS
'Đơn vị đo của thông số';

COMMENT ON COLUMN catalog.measurement_type.description IS
'Mô tả ý nghĩa và cách sử dụng của thông số đo';

COMMENT ON COLUMN catalog.measurement_type.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.measurement_type.updated_at IS
'Thời gian cập nhật gần nhất';