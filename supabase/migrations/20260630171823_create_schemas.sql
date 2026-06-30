-- =========================================================
-- PROJECT: XEOXO WEB
-- FILE: 01_create_schemas.sql
-- PURPOSE: Tạo các schema nghiệp vụ trong PostgreSQL/Supabase
-- =========================================================

BEGIN;

-- Quản lý tài khoản, khách hàng, nhân viên, chi nhánh
CREATE SCHEMA IF NOT EXISTS iam;

COMMENT ON SCHEMA iam IS
'Quản lý tài khoản, định danh đăng nhập, khách hàng, nhân viên và chi nhánh.';


-- Danh mục và thông tin sản phẩm
CREATE SCHEMA IF NOT EXISTS catalog;

COMMENT ON SCHEMA catalog IS
'Quản lý danh mục, bộ sưu tập, dòng sản phẩm, biến thể, size, màu, chất liệu và media.';


-- Tồn kho
CREATE SCHEMA IF NOT EXISTS inventory;

COMMENT ON SCHEMA inventory IS
'Quản lý tồn kho sản phẩm theo chi nhánh và biến thể.';


-- Khuyến mãi
CREATE SCHEMA IF NOT EXISTS promotion;

COMMENT ON SCHEMA promotion IS
'Quản lý chương trình khuyến mãi và phạm vi áp dụng.';


-- Giỏ hàng, đơn hàng, thanh toán, giao hàng, đổi trả
CREATE SCHEMA IF NOT EXISTS sales;

COMMENT ON SCHEMA sales IS
'Quản lý giỏ hàng, đơn hàng, thanh toán, vận chuyển, đổi trả và đánh giá.';


-- May đo và hồ sơ số đo
CREATE SCHEMA IF NOT EXISTS customization;

COMMENT ON SCHEMA customization IS
'Quản lý yêu cầu may đo, lịch hẹn, hồ sơ số đo và thông số đo khách hàng.';


-- Chat và tư vấn khách hàng
CREATE SCHEMA IF NOT EXISTS support;

COMMENT ON SCHEMA support IS
'Quản lý cuộc trò chuyện, tin nhắn, phân công nhân viên và nhãn tư vấn.';


-- Metadata kỹ thuật
CREATE SCHEMA IF NOT EXISTS metadata;

COMMENT ON SCHEMA metadata IS
'Lưu metadata mô tả bảng, cột, quan hệ, index và routine của hệ thống.';


-- Function và trigger dùng chung
CREATE SCHEMA IF NOT EXISTS util;

COMMENT ON SCHEMA util IS
'Chứa function, procedure và trigger function dùng chung trong hệ thống.';

COMMIT;