# XEOXO Web - Schema Access Control

## 1. Mục tiêu

Tài liệu này mô tả cách chia schema trong PostgreSQL/Supabase cho hệ thống XEOXO Web và định nghĩa quyền truy cập dữ liệu theo từng role.

Phạm vi tài liệu bám theo các bảng hiện có trong đặc tả database, không bổ sung schema ngoài các nhóm bảng đang sử dụng.

---

## 2. Role sử dụng trong Supabase/PostgreSQL

## postgres

- Role chủ sở hữu hệ thống database.
- Dùng cho migration, tạo schema, tạo bảng, tạo policy, tạo function/trigger và thao tác kỹ thuật cấp cao.
- Chỉ dùng trong project database/migration, không sử dụng trong frontend.

## service_role

- Role backend có quyền cao.
- Dùng cho server-side API, cron job, webhook, edge function hoặc service nội bộ.
- Có thể bypass RLS nếu dùng Supabase service key, vì vậy không được đưa key này lên frontend.

## authenticated

- Người dùng đã đăng nhập.
- Đại diện cho khách hàng có tài khoản trong hệ thống.
- Quyền truy cập dữ liệu phải được kiểm soát bằng RLS theo `auth.uid()` và quan hệ với `iam.customer.account_id`.

## anon

- Người dùng chưa đăng nhập.
- Chỉ được đọc dữ liệu public và thao tác giới hạn như xem sản phẩm, tạo giỏ hàng guest hoặc chat guest nếu hệ thống hỗ trợ.

**Ghi chú:**

- Không tạo PostgreSQL role riêng cho `CUSTOMER`, `STAFF`.
- `CUSTOMER`, `STAFF` là vai trò nghiệp vụ, lưu trong `iam.account.role`.
- Nhân viên thao tác dữ liệu nghiệp vụ thông qua backend/service_role hoặc RLS nghiệp vụ, không cần database role riêng.

---

## 3. Danh sách schema đề xuất

## iam

- Mục đích: Quản lý tài khoản, khách hàng, nhân viên, chi nhánh, địa chỉ và thông tin địa lý.
- Nhóm bảng chính:
  - account
  - customer
  - staff
  - branch
  - address
  - province
  - loyalty_tier
  - loyalty_reward
  - reward_usage

**Ghi chú:**

- `loyalty_tier`, `loyalty_reward`, `reward_usage` đặt trong `iam` vì đây là dữ liệu gắn trực tiếp với hồ sơ khách hàng và hạng thành viên.
- Dữ liệu cá nhân như customer, address, reward phải bật RLS và chỉ cho người dùng xem dữ liệu của chính mình.

---

## catalog

- Mục đích: Quản lý danh mục, bộ sưu tập, dòng sản phẩm, biến thể, size, màu sắc, chất liệu, media và kết quả tư vấn màu sắc.
- Nhóm bảng chính:
  - category
  - collection
  - product_line
  - line_category
  - product_component
  - product_variant
  - color
  - material
  - size_chart
  - size_chart_category
  - size_option
  - size_measurement
  - measurement_type
  - media
  - product_line_media
  - personal_color_result
  - personal_color_result_color

**Ghi chú:**

- Đây là schema chính để frontend đọc dữ liệu hiển thị sản phẩm.
- `personal_color_result` và `personal_color_result_color` đặt trong `catalog` vì mục tiêu cuối cùng là xác định màu phù hợp và gợi ý sản phẩm theo màu.
- Không lưu danh sách sản phẩm gợi ý cố định; sản phẩm phù hợp được truy vấn động từ `catalog.product_line` và `catalog.color`.

---

## inventory

- Mục đích: Quản lý tồn kho theo chi nhánh và biến thể sản phẩm.
- Nhóm bảng chính:
  - inventory

**Ghi chú:**

- Dữ liệu tồn kho không nên cho frontend ghi trực tiếp.
- Nếu cần hiển thị còn hàng/hết hàng, nên tạo view/API riêng thay vì cho đọc trực tiếp toàn bộ tồn kho.

---

## sales

- Mục đích: Quản lý giỏ hàng, đơn hàng, thanh toán, giao hàng, đổi trả và đánh giá.
- Nhóm bảng chính:
  - cart
  - cart_item
  - sales_order
  - order_item
  - payment
  - payment_method
  - refund
  - shipping
  - return_request
  - return_item
  - review
  - review_media

**Ghi chú:**

- Đây là schema giao dịch chính.
- Người dùng chỉ được thao tác với giỏ hàng, đơn hàng, đánh giá và đổi trả của chính mình.
- Các trạng thái nhạy cảm chỉ nên cập nhật qua backend.

---

## customization

- Mục đích: Quản lý yêu cầu may đo, lịch hẹn, hồ sơ số đo và chi tiết số đo khách hàng.
- Nhóm bảng chính:
  - customization_request
  - measurement_appointment
  - measurement_profile
  - measurement_profile_detail

**Ghi chú:**

- Dữ liệu số đo là dữ liệu cá nhân, cần giới hạn theo khách hàng sở hữu.
- `measurement_type` nên đặt trong `catalog` vì đây là bảng master dùng chung cho size chart và hồ sơ số đo.

---

## support

- Mục đích: Quản lý chat, tư vấn khách hàng, phân công nhân viên và nhãn hội thoại.
- Nhóm bảng chính:
  - chat_conversation
  - chat_message
  - chat_message_media
  - chat_assignment_history
  - chat_message_read
  - chat_tag
  - chat_conversation_tag

**Ghi chú:**

- Khách đăng nhập chỉ được xem hội thoại của chính mình.
- Khách vãng lai truy cập hội thoại thông qua `guest_session_id`.

---

## metadata

- Mục đích: Lưu metadata kỹ thuật mô tả bảng, cột, quan hệ, index và routine của hệ thống.

**Ghi chú:**

- Không cho frontend truy cập trực tiếp.
- Chủ yếu dùng cho tài liệu hóa, kiểm tra cấu trúc hoặc công cụ nội bộ.

---

## util

- Mục đích: Chứa function, procedure và trigger function dùng chung.

**Ghi chú:**

- Không chứa bảng nghiệp vụ.
- Chỉ cấp quyền thực thi function cần thiết, không mở rộng quyền trực tiếp cho người dùng cuối.

---


## 4. Ma trận quyền truy cập theo schema

## iam

| Role | Quyền đề xuất |
|---|---|
| postgres | ALL |
| service_role | ALL |
| authenticated | SELECT/UPDATE dữ liệu customer, address của chính mình; SELECT reward của chính mình |
| anon | Không truy cập trực tiếp |

**Ghi chú:**

- `authenticated` chỉ được đọc/cập nhật thông tin `customer`, `address` của chính mình.
- `authenticated` được đọc `loyalty_reward`, `reward_usage` của chính mình.
- `authenticated` được đọc `loyalty_tier` nếu cần hiển thị chính sách hạng thành viên.
- Không cho người dùng đọc danh sách customer, staff, account hoặc reward của người khác.
- Không cho khách tự cập nhật `customer.total_spent`, `customer.spent_in_year`, `customer.tier_id`, `loyalty_reward.status`.

---

## catalog

| Role | Quyền đề xuất |
|---|---|
| postgres | ALL |
| service_role | ALL |
| authenticated | SELECT dữ liệu public/active; INSERT personal_color_result của chính mình nếu cần |
| anon | SELECT dữ liệu public/active; INSERT/SELECT personal_color_result theo guest_session_id nếu hỗ trợ guest |

**Ghi chú:**

- Dữ liệu public/active gồm danh mục đang hoạt động, bộ sưu tập active, sản phẩm active, biến thể active, màu, chất liệu, size, media hiển thị.
- `personal_color_result` có thể cho khách tạo kết quả tư vấn của chính mình.
- `personal_color_result_color` lưu danh sách màu đề xuất tương ứng với kết quả personal color.
- INSERT/UPDATE/DELETE dữ liệu sản phẩm, màu, chất liệu, media chỉ thực hiện qua backend hoặc migration.

---

## inventory

| Role | Quyền đề xuất |
|---|---|
| postgres | ALL |
| service_role | ALL |
| authenticated | Không truy cập trực tiếp |
| anon | Không truy cập trực tiếp |

**Ghi chú:**

- Không cho frontend đọc/ghi trực tiếp tồn kho.
- Nếu cần hiển thị trạng thái còn hàng, backend nên trả về dữ liệu đã xử lý hoặc tạo view public an toàn.

---

## sales

| Role | Quyền đề xuất |
|---|---|
| postgres | ALL |
| service_role | ALL |
| authenticated | CRUD dữ liệu giao dịch của chính mình theo RLS |
| anon | Tạo/đọc cart theo session; tạo order guest nếu hệ thống hỗ trợ |

**Ghi chú:**

- `authenticated` được thao tác với `cart`, `cart_item`, `sales_order`, `review`, `return_request` của chính mình.
- Không cho khách tự cập nhật trạng thái đơn hàng, thanh toán, giao hàng, hoàn tiền.
- Các cột nhạy cảm như `order_status`, `payment_status`, `shipping_status`, `refund_status`, `reward_discount_amount` chỉ nên cập nhật qua backend.

---

## customization

| Role | Quyền đề xuất |
|---|---|
| postgres | ALL |
| service_role | ALL |
| authenticated | CRUD yêu cầu may đo, lịch hẹn, hồ sơ số đo của chính mình |
| anon | Không truy cập trực tiếp |

**Ghi chú:**

- Dữ liệu số đo cá nhân chỉ được đọc bởi chủ sở hữu và backend.
- Nhân viên xử lý lịch hẹn thông qua API/backend, không cần role database riêng.

---

## support

| Role | Quyền đề xuất |
|---|---|
| postgres | ALL |
| service_role | ALL |
| authenticated | CRUD hội thoại/tin nhắn của chính mình |
| anon | CRUD hội thoại/tin nhắn theo guest_session_id nếu hỗ trợ chat guest |

**Ghi chú:**

- Khách đăng nhập chỉ truy cập conversation gắn với `customer_id` của mình.
- Khách vãng lai chỉ truy cập conversation gắn với `guest_session_id` hiện tại.
- Nhân viên support truy cập qua backend/RLS nghiệp vụ.

---

## metadata

| Role | Quyền đề xuất |
|---|---|
| postgres | ALL |
| service_role | SELECT |
| authenticated | Không truy cập |
| anon | Không truy cập |

**Ghi chú:**

- Không expose metadata kỹ thuật ra frontend.

---

## util

| Role | Quyền đề xuất |
|---|---|
| postgres | ALL |
| service_role | EXECUTE function cần thiết |
| authenticated | EXECUTE function public nếu có |
| anon | EXECUTE function public nếu có |

**Ghi chú:**

- Chỉ cấp EXECUTE cho những function thật sự cần gọi trực tiếp từ frontend.
- Function xử lý nghiệp vụ nhạy cảm chỉ nên cho `service_role` gọi.

---

## 5. Nguyên tắc RLS chung

## Nguyên tắc 1: Không phân quyền nghiệp vụ bằng PostgreSQL role riêng

Không tạo các database role như:

- admin
- staff
- customer
- vip

Thay vào đó:

- Database role dùng `anon`, `authenticated`, `service_role`, `postgres`.
- Vai trò nghiệp vụ lưu ở bảng `iam.account.role` và `iam.staff.position`.

---

## Nguyên tắc 2: Frontend chỉ được quyền tối thiểu

Frontend chỉ nên dùng:

- `anon`
- `authenticated`

Không bao giờ đưa `service_role` key lên frontend.

---

## Nguyên tắc 3: Dữ liệu public chủ yếu nằm ở catalog

Schema có thể mở SELECT cho `anon`:

- `catalog`

Các schema không nên mở trực tiếp cho `anon`:

- `iam`
- `inventory`
- `sales`
- `customization`
- `metadata`

Riêng `support` và một phần `catalog.personal_color_result` có thể mở giới hạn nếu có nghiệp vụ guest.

---

## Nguyên tắc 4: Dữ liệu của khách hàng phải lọc theo chủ sở hữu

Các bảng có `customer_id` phải có RLS theo customer sở hữu:

- `iam.customer`
- `iam.address`
- `iam.loyalty_reward`
- `iam.reward_usage`
- `sales.cart`
- `sales.sales_order`
- `sales.review`
- `sales.return_request`
- `customization.customization_request`
- `customization.measurement_profile`
- `support.chat_conversation`
- `catalog.personal_color_result`

---

## Nguyên tắc 5: Trạng thái nghiệp vụ nhạy cảm chỉ cập nhật qua backend

Các cột không nên cho frontend cập nhật trực tiếp:

- `sales_order.order_status`
- `sales_order.payment_status`
- `shipping.shipping_status`
- `refund.refund_status`
- `loyalty_reward.status`
- `inventory.quantity`
- `customer.total_spent`
- `customer.spent_in_year`
- `customer.tier_id`
- `sales_order.reward_discount_amount`

---

