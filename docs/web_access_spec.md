# Web Access Specification

## 1. Mục tiêu

Tài liệu này mô tả phần đã triển khai để phục vụ web client ở lớp database:

- `index`
- `RLS`
- `view`

Đây là tài liệu đặc tả trạng thái thực tế đã triển khai, không phải tài liệu kế hoạch.

Tài liệu kế hoạch nằm ở [web_access_plan.md](/home/ngocmypzg/Projects/xeoxo_db/docs/web_access_plan.md).

---

## 2. Migration liên quan

Các migration đã được thêm cho lớp truy cập web:

- [20260702195000_create_web_access_indexes.sql](/home/ngocmypzg/Projects/xeoxo_db/supabase/migrations/20260702195000_create_web_access_indexes.sql)
- [20260702198000_enable_web_access_rls.sql](/home/ngocmypzg/Projects/xeoxo_db/supabase/migrations/20260702198000_enable_web_access_rls.sql)
- [20260702197000_create_web_access_views.sql](/home/ngocmypzg/Projects/xeoxo_db/supabase/migrations/20260702197000_create_web_access_views.sql)

Smoke test đi kèm:

- [tests/test_web_access.py](/home/ngocmypzg/Projects/xeoxo_db/tests/test_web_access.py)

---

## 3. Index đã triển khai

Các index dưới đây là `index bổ sung` phục vụ frontend. Chúng không tính các index sinh ra từ `PRIMARY KEY` hoặc `UNIQUE`.

### catalog

- `idx_category_active_department_parent`
  - bảng: `catalog.category`
  - cột: `(department, parent_id)`
  - điều kiện: `WHERE is_active = TRUE`
  - mục đích: dựng category tree public

- `idx_product_line_collection_status`
  - bảng: `catalog.product_line`
  - cột: `(collection_id, status)`
  - mục đích: listing theo collection

- `idx_product_line_color_status`
  - bảng: `catalog.product_line`
  - cột: `(color_id, status)`
  - mục đích: listing theo màu

- `idx_line_category_category_product_line`
  - bảng: `catalog.line_category`
  - cột: `(category_id, product_line_id)`
  - mục đích: truy vấn product line theo category

- `idx_product_component_product_line_display`
  - bảng: `catalog.product_component`
  - cột: `(product_line_id, display_order)`
  - mục đích: load component của product detail

- `idx_product_variant_component_status`
  - bảng: `catalog.product_variant`
  - cột: `(component_id, status)`
  - mục đích: load variant theo component

- `idx_product_line_media_line_role_order`
  - bảng: `catalog.product_line_media`
  - cột: `(product_line_id, media_role, display_order)`
  - mục đích: load gallery theo thứ tự hiển thị

- `idx_size_chart_product_line`
  - bảng: `catalog.size_chart`
  - cột: `(product_line_id)`
  - mục đích: lookup size chart theo product line

- `idx_size_measurement_size_option_measurement_type`
  - bảng: `catalog.size_measurement`
  - cột: `(size_option_id, measurement_type_id)`
  - mục đích: render bảng số đo

### sales

- `idx_cart_customer`
  - bảng: `sales.cart`
  - cột: `(customer_id)`
  - mục đích: load cart của customer hiện tại

- `idx_cart_item_cart`
  - bảng: `sales.cart_item`
  - cột: `(cart_id)`
  - mục đích: load toàn bộ cart item theo cart

### customization

- `_measurement_profile_customer_active`
  - bảng: `customization.measurement_profile`
  - cột: `(customer_id)` với partial condition `WHERE is_active = true`
  - mục đích: đảm bảo mỗi customer chỉ có tối đa một profile số đo active

- `idx_sales_order_customer_created_at`
  - bảng: `sales.sales_order`
  - cột: `(customer_id, created_at DESC)`
  - mục đích: order history

### iam

- `idx_address_customer_default_created`
  - bảng: `iam.address`
  - cột: `(customer_id, is_default DESC, created_at DESC)`
  - mục đích: sắp xếp sổ địa chỉ của customer

---

## 4. RLS đã triển khai

## 4.1 Helper function

Đã tạo function:

- `util.current_customer_id()`

Mục đích:

- map `auth.uid()` sang `iam.customer.customer_id`
- dùng lại trong policy owner-based

Function này được `GRANT EXECUTE` cho `authenticated`.

---

## 4.2 Schema usage và grant

Đã cấp `USAGE` schema như sau:

- `catalog`: `anon`, `authenticated`
- `iam`: `authenticated`
- `sales`: `authenticated`
- `customization`: `authenticated`
- `util`: `authenticated`

Đã cấp quyền bảng cho frontend đúng phạm vi:

- `anon` + `authenticated`: `SELECT` trên nhóm catalog public
- `authenticated`: quyền owner-based trên customer flow
- các bảng nhạy cảm bị `REVOKE ALL` khỏi `anon`, `authenticated`

---

## 4.3 Nhóm catalog public

Đã bật `RLS` cho toàn bộ các bảng sau và tạo policy `SELECT` public:

- `catalog.category`
- `catalog.collection`
- `catalog.product_line`
- `catalog.line_category`
- `catalog.product_component`
- `catalog.product_variant`
- `catalog.color`
- `catalog.material`
- `catalog.size_chart`
- `catalog.size_chart_category`
- `catalog.size_option`
- `catalog.size_measurement`
- `catalog.measurement_type`
- `catalog.media`
- `catalog.product_line_media`

Các policy chính:

- `category_public_select`
  - điều kiện: `is_active = TRUE`

- `collection_public_select`
  - điều kiện: `status = 'ACTIVE'`

- `product_line_public_select`
  - điều kiện: `status = 'ACTIVE'`

- `product_variant_public_select`
  - điều kiện: `status IN ('ACTIVE', 'OUT_OF_STOCK', 'PREORDER', 'COMING_SOON')`

- `material_public_select`
  - điều kiện: `is_active = TRUE`

Các bảng con còn lại dùng policy có kiểm tra quan hệ cha:

- `line_category_public_select`
- `product_component_public_select`
- `size_chart_public_select`
- `size_chart_category_public_select`
- `size_option_public_select`
- `size_measurement_public_select`
- `product_line_media_public_select`

Riêng các bảng lookup/asset dưới đây đang mở `SELECT` public trực tiếp:

- `catalog.color`
- `catalog.measurement_type`
- `catalog.media`

---

## 4.4 Nhóm owner-based

Đã bật `RLS` và tạo policy owner-based cho các bảng sau:

### iam

- `iam.customer`
  - `customer_self_select`
  - `customer_self_update`
  - điều kiện: `account_id = auth.uid()`

- `iam.address`
  - `address_self_all`
  - điều kiện: `customer_id = util.current_customer_id()`

- `iam.loyalty_reward`
  - `loyalty_reward_self_select`
  - điều kiện: reward thuộc customer hiện tại

- `iam.reward_usage`
  - `reward_usage_self_select`
  - điều kiện: usage thuộc reward của customer hiện tại

### sales

- `sales.cart`
  - `cart_self_all`
  - điều kiện: `customer_id = util.current_customer_id()`

- `sales.cart_item`
  - `cart_item_self_all`
  - điều kiện: `cart_id` phải thuộc cart của customer hiện tại

- `sales.sales_order`
  - `sales_order_self_select`
  - chỉ cho `SELECT`

- `sales.order_item`
  - `order_item_self_select`
  - chỉ cho `SELECT`

### customization

- `customization.measurement_profile`
  - `measurement_profile_self_all`

- `customization.measurement_profile_detail`
  - `measurement_profile_detail_self_all`

Điều kiện chung:

- parent `measurement_profile` phải thuộc customer hiện tại

### personal color

- `catalog.personal_color_result`
  - `personal_color_result_self_all`

- `catalog.personal_color_result_color`
  - `personal_color_result_color_self_all`

Điều kiện chung:

- result phải thuộc customer hiện tại

---

## 4.5 Nhóm bị chặn khỏi frontend

Đã `ENABLE ROW LEVEL SECURITY` và `REVOKE ALL` khỏi `anon`, `authenticated` cho các bảng sau:

- `iam.account`
- `iam.staff`
- `iam.branch`
- `inventory.inventory`
- `sales.payment`
- `sales.refund`
- `sales.shipping`
- `sales.return_request`
- `sales.return_item`
- `sales.review`
- `sales.review_media`
- `support.chat_conversation`
- `support.chat_message`
- `support.chat_message_media`
- `support.chat_assignment_history`
- `support.chat_message_read`
- `support.chat_tag`
- `support.chat_conversation_tag`

Ý nghĩa:

- frontend không truy cập trực tiếp các bảng này qua Supabase client
- nếu cần dùng trong tương lai thì phải mở bằng policy hoặc backend riêng

---

## 5. View đã triển khai

Tất cả view phục vụ frontend đều được tạo với:

- `WITH (security_invoker = true)`

Mục đích:

- đảm bảo view vẫn tôn trọng `RLS` của các bảng nền

---

## 5.1 catalog.v_product_line_card

Schema: `catalog`

Grant:

- `SELECT` cho `anon`, `authenticated`

Shape dữ liệu:

- `product_line_id`
- `line_name`
- `slug`
- `collection_id`
- `collection_name`
- `color_id`
- `color_name`
- `color_code`
- `material_id`
- `material_name`
- `is_featured`
- `status`
- `main_media_id`
- `main_storage_key`
- `min_price`
- `max_price`
- `primary_category_id`
- `primary_category_name`

Ý nghĩa:

- view card/listing cho product line

---

## 5.2 catalog.v_product_line_media_ordered

Schema: `catalog`

Grant:

- `SELECT` cho `anon`, `authenticated`

Shape dữ liệu:

- `product_line_id`
- `media_id`
- `media_role`
- `display_order`
- `storage_key`
- `bucket_name`
- `alt_text`

Ý nghĩa:

- view gallery đã join sẵn metadata của media

---

## 5.3 catalog.v_size_chart_detail

Schema: `catalog`

Grant:

- `SELECT` cho `anon`, `authenticated`

Shape dữ liệu:

- `size_chart_id`
- `chart_name`
- `product_line_id`
- `category_id`
- `size_option_id`
- `size_name`
- `measurement_type_id`
- `measurement_name`
- `unit`
- `measurement_value`
- `measurement_min`
- `measurement_max`

Ý nghĩa:

- view chi tiết bảng size, đủ dữ liệu để render cả giá trị đơn và khoảng đo

---

## 5.4 sales.v_my_order_summary

Schema: `sales`

Grant:

- `SELECT` cho `authenticated`

Shape dữ liệu:

- `order_id`
- `order_code`
- `created_at`
- `status`
- `total_amount`
- `item_count`
- `thumbnail_storage_key`

Ý nghĩa:

- view tóm tắt lịch sử đơn hàng của customer hiện tại

Ghi chú:

- view này phụ thuộc vào `RLS` của `sales.sales_order` và `sales.order_item`
- `thumbnail_storage_key` được suy ra từ ảnh `MAIN` của product line liên quan tới order item

---

## 6. Kết luận

Lớp dữ liệu phục vụ frontend hiện đã được triển khai theo hướng:

- thêm ít index nhưng bám đúng truy vấn nóng
- dùng `RLS` để tách public data, owner data và blocked data
- dùng số lượng view thấp, tập trung vào shape dữ liệu lặp lại nhiều nhất

Nếu cần mở rộng tiếp, nên sửa từ tài liệu kế hoạch trước, rồi mới bổ sung migration và cập nhật lại tài liệu đặc tả này.
