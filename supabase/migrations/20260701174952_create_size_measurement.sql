CREATE TABLE catalog.size_measurement (
    measurement_id SERIAL PRIMARY KEY,

    size_option_id INT NOT NULL,
    measurement_type_id INT NOT NULL,

    measurement_value NUMERIC(10,2),

    measurement_min NUMERIC(10,2),
    measurement_max NUMERIC(10,2),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_size_measurement_size_option
        FOREIGN KEY (size_option_id)
        REFERENCES catalog.size_option(size_option_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_size_measurement_measurement_type
        FOREIGN KEY (measurement_type_id)
        REFERENCES catalog.measurement_type(measurement_type_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_size_measurement_value
        CHECK (
            measurement_value IS NOT NULL
            OR (
                measurement_min IS NOT NULL
                AND measurement_max IS NOT NULL
            )
        )
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.size_measurement IS
'Lưu các thông số đo tương ứng với từng size trong bảng size.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.size_measurement.measurement_id IS
'Mã dòng thông số đo';

COMMENT ON COLUMN catalog.size_measurement.size_option_id IS
'Mã size';

COMMENT ON COLUMN catalog.size_measurement.measurement_type_id IS
'Mã loại thông số đo';

COMMENT ON COLUMN catalog.size_measurement.measurement_value IS
'Giá trị đo cố định';

COMMENT ON COLUMN catalog.size_measurement.measurement_min IS
'Giá trị nhỏ nhất nếu thông số được biểu diễn theo khoảng';

COMMENT ON COLUMN catalog.size_measurement.measurement_max IS
'Giá trị lớn nhất nếu thông số được biểu diễn theo khoảng';

COMMENT ON COLUMN catalog.size_measurement.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.size_measurement.updated_at IS
'Thời gian cập nhật gần nhất';