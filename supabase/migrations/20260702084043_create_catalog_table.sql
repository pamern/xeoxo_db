-- =========================================================
-- PROJECT: XEOXO WEB
-- FILE: 02_create_catalog_tables.sql
-- PURPOSE: Tạo các bảng thuộc schema catalog theo database specification
-- =========================================================

BEGIN;

-- =========================================================
-- 1. TABLE: catalog.material
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

-- =====================================================
-- 2. TABLE: catalog.media
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
    updated_at TIMESTAMPTZ,

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

ALTER TABLE catalog.material
    ADD CONSTRAINT fk_material_media
    FOREIGN KEY (media_id)
    REFERENCES catalog.media(media_id)
    ON UPDATE CASCADE
    ON DELETE SET NULL;

-- =====================================================
-- 3. TABLE: catalog.color
-- Mô tả: Danh mục màu sắc của sản phẩm
-- =====================================================

CREATE TABLE catalog.color (
    -- Mã màu sắc
    color_id SERIAL PRIMARY KEY,

    -- Tên màu
    color_name VARCHAR(100) NOT NULL,

    -- Mã màu HEX (ví dụ: #FFFFFF)
    color_code VARCHAR(7) NOT NULL,

    -- Nhóm màu phổ thông hỗ trợ tìm kiếm
    color_group VARCHAR(50),

    personal_color_season VARCHAR(30),
    color_temperature VARCHAR(20),
    color_value VARCHAR(20),
    color_chroma VARCHAR(20),

    -- Hình đại diện của màu
    media_id BIGINT,

    -- Thời gian tạo
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Thời gian cập nhật
    updated_at TIMESTAMPTZ,

    -- Khóa ngoại
    CONSTRAINT fk_color_media
        FOREIGN KEY (media_id)
        REFERENCES catalog.media(media_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    -- Kiểm tra mã màu HEX
    CONSTRAINT chk_color_hex
        CHECK (color_code ~ '^#[A-Fa-f0-9]{6}$'),

    CONSTRAINT chk_color_personal_color_season
        CHECK (
            personal_color_season IS NULL
            OR personal_color_season IN ('SPRING', 'SUMMER', 'AUTUMN', 'WINTER')
        ),

    CONSTRAINT chk_color_temperature
        CHECK (
            color_temperature IS NULL
            OR color_temperature IN ('WARM', 'COOL')
        ),

    CONSTRAINT chk_color_value
        CHECK (
            color_value IS NULL
            OR color_value IN ('LIGHT', 'DEEP')
        ),

    CONSTRAINT chk_color_chroma
        CHECK (
            color_chroma IS NULL
            OR color_chroma IN ('CLEAR', 'SOFT', 'MUTED')
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
'Mã màu HEX canonical dùng để render swatch màu chuẩn trong hệ thống.';

COMMENT ON COLUMN catalog.color.color_group IS
'Nhóm màu phổ thông phục vụ tìm kiếm và lọc sản phẩm.';

COMMENT ON COLUMN catalog.color.personal_color_season IS
'Nhóm mùa personal color phù hợp với màu này.';

COMMENT ON COLUMN catalog.color.color_temperature IS
'Nhiệt độ màu của màu sắc.';

COMMENT ON COLUMN catalog.color.color_value IS
'Độ sáng/tối của màu sắc.';

COMMENT ON COLUMN catalog.color.color_chroma IS
'Độ rực/trầm của màu sắc.';

COMMENT ON COLUMN catalog.color.media_id IS
'Mã hình ảnh đại diện của màu sắc.';

COMMENT ON COLUMN catalog.color.created_at IS
'Thời gian tạo bản ghi.';

COMMENT ON COLUMN catalog.color.updated_at IS
'Thời gian cập nhật bản ghi.';

-- =====================================================
-- 4. TABLE: catalog.category
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

    -- Ảnh đại diện
    media_id BIGINT,

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
        ),
    -- Khóa ngoại media
    CONSTRAINT fk_category_media
        FOREIGN KEY (media_id)
        REFERENCES catalog.media(media_id)
        ON UPDATE SET NULL
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
'Đối tượng sử dụng của danh mục (MEN, WOMEN, KIDS).';

COMMENT ON COLUMN catalog.category.slug IS
'Slug dùng để tạo URL thân thiện.';

COMMENT ON COLUMN catalog.category.media_id IS
'Mã hình ảnh đại diện của danh mục (FK -> catalog.media).';

COMMENT ON COLUMN catalog.category.is_active IS
'Trạng thái hoạt động của danh mục.';

COMMENT ON COLUMN catalog.category.created_at IS
'Thời gian tạo bản ghi.';

COMMENT ON COLUMN catalog.category.updated_at IS
'Thời gian cập nhật bản ghi.';

-- =====================================================
-- 5. TABLE: catalog.collection
-- Mô tả: Bộ sưu tập
-- =====================================================

CREATE TABLE catalog.collection (
    collection_id SERIAL PRIMARY KEY,

    collection_name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
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
            season IN ('SPRING', 'SUMMER', 'AUTUMN', 'WINTER')
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

COMMENT ON COLUMN catalog.collection.slug IS
'Slug dùng để tạo URL thân thiện cho bộ sưu tập.';

COMMENT ON COLUMN catalog.collection.description IS
'Mô tả ngắn về bộ sưu tập';

COMMENT ON COLUMN catalog.collection.media_id IS
'Ảnh đại diện của bộ sưu tập (FK -> catalog.media)';

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

-- =====================================================
-- 6. TABLE: catalog.product_line
-- Mô tả: Dòng sản phẩm
-- =====================================================
CREATE TABLE catalog.product_line (
    product_line_id SERIAL PRIMARY KEY,

    collection_id INT,
    color_id INT,
    material_id INT NOT NULL,

    line_name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,

    design_style VARCHAR(500),
    features VARCHAR(500),
    usage_context VARCHAR(500),

    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_product_line_collection
        FOREIGN KEY (collection_id)
        REFERENCES catalog.collection(collection_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_product_line_color
        FOREIGN KEY (color_id)
        REFERENCES catalog.color(color_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_product_line_material
        FOREIGN KEY (material_id)
        REFERENCES catalog.material(material_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_product_line_status
        CHECK (
            status IN (
                'ACTIVE',
                'INACTIVE'
            )
        )
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.product_line IS
'Thông tin các dòng sản phẩm.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.product_line.product_line_id IS
'Mã dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.collection_id IS
'Mã bộ sưu tập';

COMMENT ON COLUMN catalog.product_line.color_id IS
'Màu chủ đạo của dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.material_id IS
'Chất liệu chính của dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.line_name IS
'Tên dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.slug IS
'Slug dùng để tạo URL thân thiện cho dòng sản phẩm.';

COMMENT ON COLUMN catalog.product_line.description IS
'Mô tả ngắn của dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.design_style IS
'Kiểu dáng hoặc phong cách thiết kế';

COMMENT ON COLUMN catalog.product_line.features IS
'Đặc điểm nổi bật của dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.usage_context IS
'Hoàn cảnh hoặc mục đích sử dụng phù hợp';

COMMENT ON COLUMN catalog.product_line.status IS
'Trạng thái hoạt động của dòng sản phẩm';

COMMENT ON COLUMN catalog.product_line.is_featured IS
'Đánh dấu dòng sản phẩm nổi bật';

COMMENT ON COLUMN catalog.product_line.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.product_line.updated_at IS
'Thời gian cập nhật gần nhất';

-- =====================================================
-- 7. TABLE: catalog.line_category
-- Mô tả: Liên kết giữa dòng sản phẩm và danh mục sản phẩm
-- =====================================================

CREATE TABLE catalog.line_category (
    product_line_id INT NOT NULL,
    category_id INT NOT NULL,

    is_primary BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    PRIMARY KEY (product_line_id, category_id),

    CONSTRAINT fk_line_category_product_line
        FOREIGN KEY (product_line_id)
        REFERENCES catalog.product_line(product_line_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_line_category_category
        FOREIGN KEY (category_id)
        REFERENCES catalog.category(category_id)
        ON DELETE CASCADE
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.line_category IS
'Liên kết giữa dòng sản phẩm và danh mục sản phẩm.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.line_category.product_line_id IS
'Mã dòng sản phẩm';

COMMENT ON COLUMN catalog.line_category.category_id IS
'Mã danh mục sản phẩm';

COMMENT ON COLUMN catalog.line_category.is_primary IS
'Đánh dấu danh mục chính của dòng sản phẩm';

COMMENT ON COLUMN catalog.line_category.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.line_category.updated_at IS
'Thời gian cập nhật gần nhất';

-- =====================================================
-- 8. TABLE: catalog.product_component
-- Mô tả: Liên kết giữa dòng sản phẩm và thành phần sản phẩm
-- =====================================================

CREATE TABLE catalog.product_component (
    component_id SERIAL PRIMARY KEY,

    component_name VARCHAR(255) NOT NULL,
    product_line_id INT NOT NULL,

    component_type VARCHAR(30) NOT NULL,

    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    display_order SMALLINT NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_product_component_product_line
        FOREIGN KEY (product_line_id)
        REFERENCES catalog.product_line(product_line_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_product_component_type
        CHECK (
            component_type IN ('AO', 'QUAN', 'DAM', 'SET', 'VAY', 'KHAC')
        )
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.product_component IS
'Các thành phần cấu thành của một dòng sản phẩm.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.product_component.component_id IS
'Mã thành phần sản phẩm';

COMMENT ON COLUMN catalog.product_component.component_name IS
'Tên thành phần sản phẩm';

COMMENT ON COLUMN catalog.product_component.product_line_id IS
'Mã dòng sản phẩm';

COMMENT ON COLUMN catalog.product_component.component_type IS
'Loại thành phần sản phẩm';

COMMENT ON COLUMN catalog.product_component.is_required IS
'Đánh dấu thành phần bắt buộc trong bộ sản phẩm';

COMMENT ON COLUMN catalog.product_component.display_order IS
'Thứ tự hiển thị của thành phần';

COMMENT ON COLUMN catalog.product_component.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.product_component.updated_at IS
'Thời gian cập nhật gần nhất';

-- =====================================================
-- 9. TABLE: catalog.size_chart
-- Mô tả: Bảng size chart 
-- =====================================================
CREATE TABLE catalog.size_chart (
    size_chart_id SERIAL PRIMARY KEY,

    chart_name VARCHAR(255) NOT NULL,
    product_line_id INT,

    description TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_size_chart_product_line
        FOREIGN KEY (product_line_id)
        REFERENCES catalog.product_line(product_line_id)
        ON DELETE SET NULL
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.size_chart IS
'Thông tin bảng quy đổi kích thước của sản phẩm.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.size_chart.size_chart_id IS
'Mã bảng size';

COMMENT ON COLUMN catalog.size_chart.chart_name IS
'Tên bảng size';

COMMENT ON COLUMN catalog.size_chart.product_line_id IS
'Mã dòng sản phẩm nếu bảng size chỉ áp dụng cho một dòng sản phẩm';

COMMENT ON COLUMN catalog.size_chart.description IS
'Ghi chú hoặc mô tả bảng size';

COMMENT ON COLUMN catalog.size_chart.is_active IS
'Trạng thái sử dụng của bảng size';

COMMENT ON COLUMN catalog.size_chart.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.size_chart.updated_at IS
'Thời gian cập nhật gần nhất';

-- =====================================================
-- 11. TABLE: catalog.size_chart_category
-- Mô tả: Liên kết giữa bảng size chart và danh mục sản phẩm    
-- =====================================================   

CREATE TABLE catalog.size_chart_category (
    size_chart_id INT NOT NULL,
    category_id INT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT pk_size_chart_category
        PRIMARY KEY (size_chart_id, category_id),

    CONSTRAINT fk_size_chart_category_size_chart
        FOREIGN KEY (size_chart_id)
        REFERENCES catalog.size_chart(size_chart_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_size_chart_category_category
        FOREIGN KEY (category_id)
        REFERENCES catalog.category(category_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- ===========================
-- COMMENTS
-- ===========================

COMMENT ON TABLE catalog.size_chart_category IS
'Liên kết nhiều-nhiều giữa bảng size và danh mục sản phẩm áp dụng.';

COMMENT ON COLUMN catalog.size_chart_category.size_chart_id IS
'Mã bảng size.';

COMMENT ON COLUMN catalog.size_chart_category.category_id IS
'Mã danh mục sản phẩm áp dụng.';

COMMENT ON COLUMN catalog.size_chart_category.created_at IS
'Thời điểm tạo bản ghi.';

COMMENT ON COLUMN catalog.size_chart_category.updated_at IS
'Thời điểm cập nhật bản ghi gần nhất.';

-- ===========================
-- INDEXES
-- ===========================

CREATE INDEX idx_size_chart_category_category
ON catalog.size_chart_category(category_id);

-- =====================================================
-- 11. TABLE: catalog.size_option
-- Mô tả: Các tùy chọn size trong bảng size chart
-- =====================================================    
CREATE TABLE catalog.size_option (
    size_option_id SERIAL PRIMARY KEY,

    size_chart_id INT NOT NULL,

    size_name VARCHAR(20) NOT NULL,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_size_option_size_chart
        FOREIGN KEY (size_chart_id)
        REFERENCES catalog.size_chart(size_chart_id)
        ON DELETE CASCADE
);

-- =========================
-- Table Comment
-- =========================

COMMENT ON TABLE catalog.size_option IS
'Quản lý các kích thước (size) thuộc từng bảng size.';

-- =========================
-- Column Comments
-- =========================

COMMENT ON COLUMN catalog.size_option.size_option_id IS
'Mã size';

COMMENT ON COLUMN catalog.size_option.size_chart_id IS
'Mã bảng size';

COMMENT ON COLUMN catalog.size_option.size_name IS
'Tên size (XS, S, M, L, XL, XXL,...)';

COMMENT ON COLUMN catalog.size_option.description IS
'Mô tả hoặc ghi chú về size';

COMMENT ON COLUMN catalog.size_option.created_at IS
'Thời gian tạo';

COMMENT ON COLUMN catalog.size_option.updated_at IS
'Thời gian cập nhật gần nhất';

-- =====================================================
-- 12. TABLE: catalog.measurement_type
-- Mô tả: Các loại đo lường được sử dụng trong bảng size chart
-- =====================================================  
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

-- =====================================================
-- 13. TABLE: catalog.size_measurement
-- Mô tả: Lưu các thông số đo tương ứng với từng size trong bảng size
-- ===================================================== 

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

-- =====================================================
-- 14. TABLE: catalog.product_variant
-- Mô tả: Lưu các biến thể sản phẩm (SKU) tương ứng với từng thành phần và size
-- =====================================================    

CREATE TABLE catalog.product_variant (
    variant_id SERIAL PRIMARY KEY,

    sku VARCHAR(100) NOT NULL UNIQUE,

    component_id INT NOT NULL,
    size_option_id INT,

    price NUMERIC(14,2) NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT fk_product_variant_component
        FOREIGN KEY (component_id)
        REFERENCES catalog.product_component(component_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_product_variant_size_option
        FOREIGN KEY (size_option_id)
        REFERENCES catalog.size_option(size_option_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_product_variant_price
        CHECK (price >= 0),

    CONSTRAINT chk_product_variant_status
        CHECK (
            status IN (
                'ACTIVE',
                'INACTIVE',
                'OUT_OF_STOCK',
                'COMING_SOON',
                'PREORDER'
            )
        )
);

COMMENT ON TABLE catalog.product_variant IS
'Quản lý các biến thể SKU cụ thể của từng thành phần sản phẩm.';

COMMENT ON COLUMN catalog.product_variant.variant_id IS
'Mã biến thể sản phẩm';
COMMENT ON COLUMN catalog.product_variant.sku IS
'Mã SKU';
COMMENT ON COLUMN catalog.product_variant.component_id IS
'Mã thành phần sản phẩm';
COMMENT ON COLUMN catalog.product_variant.size_option_id IS
'Mã size';
COMMENT ON COLUMN catalog.product_variant.price IS
'Giá bán của biến thể';
COMMENT ON COLUMN catalog.product_variant.status IS
'Trạng thái biến thể';
COMMENT ON COLUMN catalog.product_variant.created_at IS
'Thời gian tạo';
COMMENT ON COLUMN catalog.product_variant.updated_at IS
'Thời gian cập nhật gần nhất';

-- =====================================================
-- 15. TABLE: catalog.product_line_media
-- Mô tả: Liên kết giữa dòng sản phẩm và các hình ảnh
-- =====================================================
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
                'MAIN',
                'GALLERY',
                'LOOKBOOK',
                'DETAIL'
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

-- =====================================================
-- 16. TABLE: catalog.personal_color_result
-- Mô tả: Kết quả tư vấn personal color của khách hàng/guest
-- =====================================================

CREATE TABLE catalog.personal_color_result (
    result_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT,
    guest_session_id UUID,
    temperature_result VARCHAR(20) NOT NULL,
    value_result VARCHAR(20) NOT NULL,
    season_result VARCHAR(30) NOT NULL,
    recommended_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_personal_color_owner
        CHECK (
            customer_id IS NOT NULL
            OR guest_session_id IS NOT NULL
        ),

    CONSTRAINT chk_personal_color_temperature
        CHECK (temperature_result IN ('WARM', 'COOL')),

    CONSTRAINT chk_personal_color_value
        CHECK (value_result IN ('LIGHT', 'DEEP')),

    CONSTRAINT chk_personal_color_season
        CHECK (season_result IN ('SPRING', 'SUMMER', 'AUTUMN', 'WINTER')),

    CONSTRAINT chk_personal_color_mapping
        CHECK (
            (temperature_result = 'WARM' AND value_result = 'LIGHT' AND season_result = 'SPRING')
            OR (temperature_result = 'WARM' AND value_result = 'DEEP' AND season_result = 'AUTUMN')
            OR (temperature_result = 'COOL' AND value_result = 'LIGHT' AND season_result = 'SUMMER')
            OR (temperature_result = 'COOL' AND value_result = 'DEEP' AND season_result = 'WINTER')
        )
);

COMMENT ON TABLE catalog.personal_color_result IS
'Kết quả tư vấn personal color của khách hàng đăng nhập hoặc khách vãng lai.';

COMMENT ON COLUMN catalog.personal_color_result.result_id IS
'Mã kết quả tư vấn personal color.';

COMMENT ON COLUMN catalog.personal_color_result.customer_id IS
'Mã khách hàng đã đăng nhập.';

COMMENT ON COLUMN catalog.personal_color_result.guest_session_id IS
'Mã phiên khách vãng lai.';

COMMENT ON COLUMN catalog.personal_color_result.temperature_result IS
'Kết quả phân loại nhiệt độ màu của khách hàng.';

COMMENT ON COLUMN catalog.personal_color_result.value_result IS
'Kết quả phân loại độ sáng/tối của khách hàng.';

COMMENT ON COLUMN catalog.personal_color_result.season_result IS
'Nhóm mùa personal color được hệ thống xác định.';

COMMENT ON COLUMN catalog.personal_color_result.recommended_at IS
'Thời điểm hệ thống đưa ra kết quả.';

COMMENT ON COLUMN catalog.personal_color_result.created_at IS
'Thời gian tạo.';

-- =====================================================
-- 17. TABLE: catalog.personal_color_result_color
-- Mô tả: Danh sách màu được đề xuất cho một kết quả personal color
-- =====================================================

CREATE TABLE catalog.personal_color_result_color (
    result_id BIGINT NOT NULL,
    color_id INT NOT NULL,
    display_order SMALLINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (result_id, color_id),

    CONSTRAINT fk_personal_color_result_color_result
        FOREIGN KEY (result_id)
        REFERENCES catalog.personal_color_result(result_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_personal_color_result_color_color
        FOREIGN KEY (color_id)
        REFERENCES catalog.color(color_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT chk_personal_color_result_color_display_order
        CHECK (
            display_order IS NULL
            OR display_order > 0
        )
);

COMMENT ON TABLE catalog.personal_color_result_color IS
'Danh sách màu phù hợp được đề xuất cho một kết quả tư vấn personal color.';

COMMENT ON COLUMN catalog.personal_color_result_color.result_id IS
'Mã kết quả tư vấn personal color.';

COMMENT ON COLUMN catalog.personal_color_result_color.color_id IS
'Mã màu phù hợp được hệ thống đề xuất.';

COMMENT ON COLUMN catalog.personal_color_result_color.display_order IS
'Thứ tự hiển thị màu được đề xuất trong một kết quả personal color.';

COMMENT ON COLUMN catalog.personal_color_result_color.created_at IS
'Thời gian tạo.';

COMMIT;
