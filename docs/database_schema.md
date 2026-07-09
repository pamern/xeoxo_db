# Database Specification

## MASTER DATA

## CUSTOMER

- customer_id (BIGSERIAL, PK, NOT NULL): Mã khách hàng
- account_id (UUID, FK, UNIQUE, NULL): Mã tài khoản
- customer_name (VARCHAR(255), NULL): Tên khách hàng
- email (VARCHAR(255), NULL): Email
- phone (VARCHAR(20), NULL): Số điện thoại
- gender (VARCHAR(20), NULL): Giới tính khách hàng
- birthday (DATE, NULL): Ngày sinh khách hàng
- customer_type (VARCHAR/CHECK, NOT NULL): Loại khách hàng 
- tier_id (VARCHAR(20), FK, NULL): Mã hạng thành viên
- total_spent (NUMBERIC(14,2), NOT NULL, DEFAULT 0): Tổng chi tiêu
- spent_in_year (NUMBERIC(14,2), NOT NULL, DEFAULT 0): Tổng chi tiêu trong năm
- last_tier_updated_at(TIMESTAMPTZ, NULL): Lần cập nhập hạng thành viên gần nhất
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- customer_type = {MEMBER, GUEST}
- email và phone trong CUSTOMER là thông tin liên hệ, không phải thông tin đăng nhập nên có thể không UNIQUE.
- `total_spent` và `spent_in_year` có thể được hệ thống tự đồng bộ khi đơn hàng chuyển sang `COMPLETED`, và bị bù trừ ngược nếu đơn rời khỏi trạng thái `COMPLETED`.

## LOYALTY_TIER

- loyalty_tier_id (VARCHAR(20), PK, NOT NULL): Mã hạng thành viên.
- tier_name (VARCHAR(100), NOT NULL): Tên hạng thành viên.
- min_accumulated_amount (NUMERIC(14,2), NOT NULL): Tổng chi tiêu tích lũy tối thiểu để đạt hạng.
- maintain_amount (NUMERIC(14,2), NOT NULL): Tổng chi tiêu tối thiểu trong năm để duy trì hạng.
- birthday_voucher_value (NUMERIC(14,2), NULL): Giá trị voucher sinh nhật mặc định.
- free_shipping_quota (SMALLINT, NOT NULL): Số lượt miễn phí vận chuyển được cấp.
- free_tailor_quota (SMALLINT, NOT NULL): Số lượt miễn phí may đo/chỉnh sửa được cấp.
- special_gift (VARCHAR(255), NULL): Quyền lợi hoặc quà tặng đặc biệt của hạng thành viên.
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo.
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật.

**Ghi chú / Enum:**
- loyalty_tier_id = {SILVER, GOLD, DIAMOND, MVG}
- Mỗi hạng thành viên quy định điều kiện đạt hạng và các quyền lợi mặc định được hệ thống tự động cấp.

## LOYALTY_REWARD

- reward_id (BIGSERIAL, PK, NOT NULL): Mã quyền lợi thành viên.
- customer_id (BIGINT, FK, NOT NULL): Mã khách hàng.
- loyalty_tier_id (VARCHAR(20), FK, NOT NULL): Hạng thành viên tại thời điểm cấp quyền lợi.
- reward_type (VARCHAR(30), NOT NULL): Loại quyền lợi.
- reward_name (VARCHAR(255), NOT NULL): Tên quyền lợi.
- voucher_code (VARCHAR(100), UNIQUE, NULL): Mã voucher.
- reward_value (NUMERIC(14,2), NULL): Giá trị quyền lợi hoặc voucher.
- issued_at (TIMESTAMPTZ, NOT NULL): Thời điểm cấp quyền lợi.
- expired_at (TIMESTAMPTZ, NULL): Thời điểm hết hạn.
- status (VARCHAR(20), NOT NULL): Trạng thái quyền lợi.
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo.
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật.

**Ghi chú / Enum:**
- reward_type = {BIRTHDAY_VOUCHER, TIER_VOUCHER, FREE_SHIPPING, FREE_TAILOR, SPECIAL_GIFT}
- status = {AVAILABLE, USED, EXPIRED, CANCELLED}
- voucher_code = NULL đối với các quyền lợi không sử dụng mã voucher.

## REWARD_USAGE

- usage_id (BIGSERIAL, PK, NOT NULL): Mã lịch sử sử dụng quyền lợi.
- reward_id (BIGINT, FK, NOT NULL): Quyền lợi được sử dụng.
- order_id (BIGINT, FK, NOT NULL): Đơn hàng áp dụng quyền lợi.
- used_amount (NUMERIC(14,2), NULL): Giá trị thực tế được giảm.
- used_at (TIMESTAMPTZ, NOT NULL): Thời điểm sử dụng.

**Ghi chú / Enum:**
- Mỗi bản ghi tương ứng một lần sử dụng quyền lợi trên một đơn hàng.

## ADDRESS

- address_id (BIGSERIAL, PK, NOT NULL): Mã địa chỉ khách hàng
- customer_id (BIGINT, FK, NOT NULL): Mã khách hàng
- recipient_name (VARCHAR(255), NOT NULL): Tên người nhận
- recipient_phone (CHAR(20), NOT NULL): Số điện thoại người nhận
- province_id (INT, FK, NOT NULL): Mã tỉnh/thành phố
- district_name (CHECKIN, NOT NULL): Quận
- address_detail (TEXT, NOT NULL): Địa chỉ chi tiết
- is_default (BOOLEAN, NOT NULL): Có phải địa chỉ mặc định không?
- is_active (BOOLEAN, NOT NULL): Trạng thái hoạt động
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NOT NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- ADDRESS đã được dùng trong SHIPPING thì không được sửa trực tiếp address_detail. Nếu khách đổi địa chỉ, tạo ADDRESS mới và đặt is_active = false.

## PROVINCE

- province_id (SERIAL, PK, NOT NULL): Mã tỉnh/thành phố
- province_name (VARCHAR(150), NOT NULL): Tên tỉnh/thành phố
- region (VARCHAR(30), NOT NULL): Miền
- ward (TEXT[], NOT NULL): Danh sách phường/xã/đặc khu thuộc tỉnh/thành phố
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- region = {Miền Bắc, Miền Trung, Miền Nam}
- `ward` lưu dạng mảng text để phục vụ chọn địa chỉ nhanh ở frontend/backend.

## STAFF

- staff_id (SERIAL, PK, NOT NULL): Mã nhân viên
- account_id (UUID, FK, NOT NULL): Mã tài khoản
- branch_id (INT, FK, NOT NULL): Mã chi nhánh
- staff_name (VARCHAR(255), NOT NULL): Tên nhân viên
- position (VARCHAR(100), NOT NULL): Chức vụ nhân viên
- is_active (BOOLEAN, NOT NULL): Trạng thái hoạt động
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

## ACCOUNT

- account_id (UUID, PK, NOT NULL): Mã tài khoản
- role (VARCHAR/CHECK, NOT NULL): Vai trò
- is_active (BOOLEAN, NOT NULL): Trạng thái hoạt động
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- role = {CUSTOMER, STAFF, ADMIN}

## CATEGORY

- category_id (SERIAL, PK, NOT NULL): Mã danh mục sản phẩm
- category_name (VARCHAR(255), NOT NULL): Tên danh mục sản phẩm
- description (TEXT, NULL): Mô tả danh mục sản phẩm
- parent_id (INT, FK, NULL): Mã danh mục cha
- department (VARCHAR(30), NULL): Phân loại người dùng
- slug (VARCHAR(255), NOT NULL): URL của link
- media_id (BIGINT, FK, NULL): Ảnh thumbnail của danh mục
- is_active (BOOLEAN, NOT NULL): Trạng thái hoạt động
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- department = {WOMEN, MEN, KIDS}

## COLLECTION

- collection_id (SERIAL, PK, NOT NULL): Mã bộ sưu tập
- collection_name (VARCHAR(255), NOT NULL): Tên bộ sưu tập
- description (TEXT, NULL): Mô tả bộ sưu tập
- media_id (BIGINT, FK, NULL): Mã hình ảnh
- content_json (JSONB, NULL): Nội dung dạng JSON
- season (VARCHAR(30), NOT NULL): Mùa của bộ sưu tập
- launch_date (DATE, NULL): Ngày ra mắt
- status (VARCHAR(20), NOT NULL): Trạng thái bộ sưu tập
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- season = {SPRING, SUMMER, AUTUMN, WINTER}

## PRODUCT_LINE

- product_line_id (SERIAL, PK, NOT NULL): Mã sản phẩm
- collection_id (INT, FK, NULL): Mã bộ sưu tập
- color_id (INT, FK, NULL): Mã màu chính của sản phẩm
- line_name (VARCHAR(255), NOT NULL): Tên dòng sản phẩm
- description (TEXT, NULL): Mô tả dòng sản phẩm
- material_id (INT, FK, NOT NULL): Mã chất liệu
- design_style (VARCHAR(500), NULL): Kiểu dáng thiết kế
- features (VARCHAR(500), NULL): Tính năng nổi bật của sản phẩm
- usage_context (VARCHAR(500), NULL): Ứng dụng, hoàn cảnh sử dụng
- status (VARCHAR(20), NOT NULL): Trạng thái dòng sản phẩm
- is_featured (BOOLEAN, NOT NULL): Sản phẩm nổi bật
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- status = {ACTIVE, INACTIVE}
- Hệ thống có thể tự chuyển `product_line.status = INACTIVE` khi toàn bộ variant/size của dòng sản phẩm đều hết hàng trong `inventory.inventory`.
- Nếu có ít nhất một variant có hàng trở lại, `product_line.status` có thể được đồng bộ về `ACTIVE`.

## LINE_CATEGORY

- product_line_id (INT, PK, FK, NOT NULL): Mã dòng sản phẩm
- category_id (INT, PK, FK, NOT NULL): Mã danh mục sản phẩm
- is_primary (BOOLEAN, NOT NULL): Có phải danh mục chính?
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- UNIQUE/PK đề xuất: (product_line_id, category_id)

## PRODUCT_COMPONENT

- component_id (SERIAL, PK, NOT NULL): Mã thành phần sản phẩm
- component_name (VARCHAR(255), NOT NULL): Tên thành phần
- product_line_id (INT, FK, NOT NULL): Mã dòng sản phẩm
- component_type (VARCHAR(30), NOT NULL): Loại thành phần
- is_required (BOOLEAN, NOT NULL): Có bắt buộc trong set không?
- display_order (SMALLINT, NOT NULL): Thứ tự hiển thị
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- component_type = {AO, QUAN, DAM, SET, VAY, KHAC}

## PRODUCT_VARIANT

- variant_id (SERIAL, PK, NOT NULL): Mã biến thể sản phẩm
- sku (VARCHAR(100), NOT NULL): Mã SKU
- component_id (INT, FK, NOT NULL): Mã thành phần sản phẩm
- size_option_id (INT, FK, NULL): Mã size option
- price (NUMERIC(14,2), NOT NULL): Giá sản phẩm
- status (VARCHAR(20), NOT NULL): Trạng thái biến thể
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- status = {ACTIVE, INACTIVE, OUT_OF_STOCK, COMING_SOON, PREORDER}
- Khi tổng tồn kho của một variant ở tất cả branch bằng `0`, hệ thống có thể tự đồng bộ sang `OUT_OF_STOCK`.
- Nếu variant đang `OUT_OF_STOCK` và có hàng trở lại, hệ thống có thể tự đồng bộ về `ACTIVE`.

## COLOR

- color_id (SERIAL, PK, NOT NULL): Mã màu sắc
- color_name (VARCHAR(100), NOT NULL): Tên màu
- color_code (VARCHAR(7), NOT NULL): Mã màu HEX canonical của swatch
- color_group (VARCHAR(50), NULL): Bảng màu phổ thông, hỗ trợ tìm kiếm
- personal_color_season (VARCHAR(30), NULL): Nhóm mùa personal color phù hợp với màu này.
- color_temperature (VARCHAR(20), NULL): Nhiệt độ màu của màu sắc.
- color_value (VARCHAR(20), NULL): Độ sáng/tối của màu sắc.
- color_chroma (VARCHAR(20), NULL): Độ rực/trầm của màu sắc.
- media_id (BIGINT, FK, NULL): Mã hình ảnh màu
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- `color_code` là mã HEX canonical dùng để render swatch màu chuẩn trong hệ thống.
- personal_color_season = {SPRING, SUMMER, AUTUMN, WINTER}
- color_temperature = {WARM, COOL}
- color_value = {LIGHT, DEEP}
- color_chroma = {CLEAR, SOFT, MUTED}

## SIZE_CHART

- size_chart_id (SERIAL, PK, NOT NULL): Mã bảng size
- chart_name (VARCHAR(255), NOT NULL): Tên bảng size
- product_line_id (INT, FK, NULL): Nếu bảng size chỉ áp dụng cho 1 dòng sản phẩm
- description (TEXT, NULL): Ghi chú bảng size
- is_active (BOOLEAN, NOT NULL): Trạng thái
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

## SIZE_CHART_CATEGORY

- size_chart_id (INT, PK, FK, NOT NULL): Mã bảng size
- category_id (INT, PK, FK, NOT NULL): Mã danh mục áp dụng
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- UNIQUE/PK đề xuất: (size_chart_id, category_id)

## SIZE_OPTION

- size_option_id (SERIAL, PK, NOT NULL): Mã size option
- size_chart_id (INT, FK, NOT NULL): Mã bảng size
- size_name (VARCHAR(20), NOT NULL): Tên size S, M, L, XL
- description (TEXT, NULL): Mô tả size
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

## SIZE_MEASUREMENT

- measurement_id (SERIAL, PK, NOT NULL): Mã dòng số đo
- size_option_id (INT, FK, NOT NULL): Mã size option
- measurement_type_id (INT, FK, NOT NULL): Mã loại thông số đo
- measurement_value (NUMERIC(10,2), NULL): Giá trị đo cố định
- measurement_min (NUMERIC(10,2), NULL): Giá trị nhỏ nhất nếu là khoảng
- measurement_max (NUMERIC(10,2), NULL): Giá trị lớn nhất nếu là khoảng
- measurement_order (SMALLINT, NOT NULL): Thứ tự hiển thị thông số
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

## MATERIAL

- material_id (SERIAL, PK, NOT NULL): Mã chất liệu
- material_name (VARCHAR(150), NOT NULL): Tên chất liệu
- description (TEXT, NULL): Mô tả chất liệu
- care_instruction (TEXT, NULL): Hướng dẫn bảo quản
- media_id (BIGINT, FK, NULL): Hình ảnh chất liệu
- is_active (BOOLEAN, NOT NULL): Trạng thái hoạt động
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

## MEDIA

- media_id (BIGSERIAL, PK, NOT NULL): Mã media
- storage_key (TEXT, UNIQUE, NOT NULL): Đường dẫn file trong Supabase Storage
- alt_text (VARCHAR(255), NULL): Mô tả ảnh
- media_type (VARCHAR(20), NOT NULL): Loại media
- mime_type (VARCHAR(100), NOT NULL): Loại file
- file_size (BIGINT, NOT NULL): Dung lượng file
- bucket_name (VARCHAR(100), NOT NULL): Tên bucket lưu file trong Supabase Storage
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- media_type = {IMAGE, VIDEO}

## PRODUCT_LINE_MEDIA

- product_line_id (INT, PK, FK, NOT NULL): Mã dòng sản phẩm
- media_id (BIGINT, PK, FK, NOT NULL): Mã hình ảnh
- media_role (VARCHAR(30), NOT NULL): Loại hình ảnh
- display_order (SMALLINT, NOT NULL): Thứ tự hiển thị
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo

**Ghi chú / Enum:**
- media_role = {MAIN, GALLERY, LOOKBOOK, DETAIL}
- LOOKBOOK có thể mượn ảnh từ media khác.

## BRANCH

- branch_id (INT, PK, NOT NULL): Mã chi nhánh
- branch_name (NVARCHAR(255), NOT NULL): Tên chi nhánh
- address (TEXT, NOT NULL): Địa chỉ chi nhánh
- phone (VARCHAR(20), NOT NULL): Số điện thoại chi nhánh
- is_active (BOOLEAN, NOT NULL): Trạng thái hoạt động
- manager_id (INT, FK, NULL): Mã người quản lý
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NOT NULL): Thời gian cập nhật

## INVENTORY

- inventory_id (SERIAL, PK, NOT NULL): Mã tồn kho
- branch_id (INT, FK, NOT NULL): Mã chi nhánh
- variant_id (INT, FK, NOT NULL): Mã biến thể sản phẩm
- quantity (INT, NOT NULL): Số lượng tồn kho
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

## PAYMENT_METHOD

- method_id (SERIAL, PK, NOT NULL): Mã phương thức thanh toán
- method_name (VARCHAR(100), NOT NULL): Tên phương thức thanh toán
- method_code (VARCHAR(30), UNIQUE, NOT NULL): Mã phương thức
- is_active (BOOLEAN, NOT NULL): Trạng thái hoạt động
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NOT NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- method_code = {COD, MOMO, VNPAY, CARD, BANK_TRANSFER}

## MEASUREMENT_TYPE

- measurement_type_id (SERIAL, PK, NOT NULL): Mã thông số đo
- measurement_code (VARCHAR(50), UNIQUE, NOT NULL): Mã code thông số đo
- measurement_name (VARCHAR(150), NOT NULL): Tên thông số đo
- description (TEXT, NULL): Mô tả thông số đo
- unit (VARCHAR(10), NOT NULL): Đơn vị đo
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

## ENUM

### ORDER_STATUS

- PENDING: Chờ xác nhận
- CONFIRMED: Đã xác nhận
- PACKING: Đang chuẩn bị hàng
- SHIPPING: Đang giao hàng
- COMPLETED: Giao hàng thành công
- CANCELLED: Đã huỷ
- RETURNED: Đã hoàn trả

### PAYMENT_STATUS

- PENDING: Chờ thanh toán
- PAID: Đã thanh toán
- FAILED: Thanh toán thất bại
- REFUNDED: Đã hoàn tiền

## TRANSACTION

## CART

- cart_id (BIGSERIAL, PK, NOT NULL): Mã giỏ hàng
- customer_id (BIGINT, FK, NULL): Mã khách hàng
- session_id (UUID, NULL): Mã phiên khách vãng lai
- cart_status (VARCHAR(20), NOT NULL): Trạng thái giỏ hàng
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- cart_status = {ACTIVE, CHECKOUT, ABANDONED}
- Quy định thời gian hết hạn của giỏ hàng trong logic xử lý nghiệp vụ backend.

## CART_ITEM

- cart_item_id (BIGSERIAL, PK, NOT NULL): Mã dòng giỏ hàng
- cart_id (BIGINT, FK, NOT NULL): Mã giỏ hàng
- variant_id (INT, FK, NULL): Mã biến thể sản phẩm thường
- customization_id (BIGINT, FK, NULL): Mã yêu cầu customize đang được thêm vào giỏ
- item_type (VARCHAR(20), NOT NULL): Phân loại dòng giỏ hàng
- quantity (INT, NOT NULL): Số lượng
- unit_price (NUMERIC(14,2), NOT NULL): Đơn giá tại thời điểm thêm vào giỏ hàng, với hàng customize đây là giá đã tính phụ phí hiện tại
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- UNIQUE (cart_id, variant_id)
- UNIQUE (cart_id, customization_id)
- item_type = {STANDARD, CUSTOMIZED}
- Nếu item_type = STANDARD thì variant_id NOT NULL và customization_id NULL.
- Nếu item_type = CUSTOMIZED thì variant_id NULL và customization_id NOT NULL.

## SALES_ORDER

- order_id (BIGSERIAL, PK, NOT NULL): Mã đơn hàng
- order_code (VARCHAR(50), UNIQUE, NOT NULL): Mã đơn hàng nghiệp vụ
- customer_id (BIGINT, FK, NULL): Mã khách hàng
- order_date (TIMESTAMPTZ, NOT NULL): Thời gian đặt hàng
- reward_dicount_amount (NUMERIC(14,2), NOT NULL, DEFAULT 0): Tổng số tiền giảm từ quyền lợi thành viên
- shipping_fee (NUMERIC(14,2), NOT NULL): Phí vận chuyển
- total_amount (NUMERIC(14,2), NOT NULL): Tổng số tiền thanh toán
- order_status (VARCHAR(30), NOT NULL): Trạng thái đơn hàng
- payment_status (VARCHAR(30), NOT NULL): Trạng thái thanh toán
- customer_note (TEXT, NULL): Ghi chú của khách
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- order_status tham chiếu ENUM ORDER_STATUS
- payment_status tham chiếu ENUM PAYMENT_STATUS
- Khi `order_status` chuyển sang `COMPLETED`, hệ thống có thể tự cộng chi tiêu cho `iam.customer`.
- Nếu đơn đã `COMPLETED` nhưng sau đó chuyển sang `CANCELLED` hoặc `RETURNED`, hệ thống có thể tự trừ ngược phần chi tiêu tương ứng.

## ORDER_ITEM

- order_item_id (BIGSERIAL, PK, NOT NULL): Mã dòng đơn hàng
- order_id (BIGINT, FK, NOT NULL): Mã đơn hàng
- variant_id (INT, FK, NULL): Mã biến thể sản phẩm
- customization_id (BIGINT, FK, NULL): Mã may đo cá nhân
- item_type (VARCHAR(20), NOT NULL): Phân loại sản phẩm
- quantity (INT, NOT NULL): Số lượng mua
- unit_price (NUMERIC(14,2), NOT NULL): Đơn giá tại thời điểm mua
- discount_amount (NUMERIC(14,2), NOT NULL): Số tiền giảm trên dòng hàng
- line_total (NUMERIC(14,2), NOT NULL): Thành tiền dòng hàng
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo

**Ghi chú / Enum:**
- item_type = {STANDARD, CUSTOMIZED}
- Nếu item_type = CUSTOMIZED thì variant_id NULL và customization_id NOT NULL.

## PAYMENT

- payment_id (BIGSERIAL, PK, NOT NULL): Mã thanh toán
- order_id (BIGINT, FK, NOT NULL): Mã đơn hàng
- method_id (INT, FK, NOT NULL): Mã phương thức thanh toán
- amount (NUMERIC(14,2), NOT NULL): Số tiền thanh toán
- payment_status (VARCHAR(30), NOT NULL): Trạng thái thanh toán
- transaction_code (VARCHAR(255), UNIQUE, NOT NULL): Mã giao dịch
- paid_at (TIMESTAMPTZ, NOT NULL): Thời gian thanh toán thành công
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- payment_status tham chiếu ENUM PAYMENT_STATUS

## REFUND

- refund_id (SERIAL, PK, NOT NULL): Mã hoàn tiền
- payment_id (BIGINT, FK, NOT NULL): Giao dịch thanh toán gốc
- return_id (INT, FK, NULL): Yêu cầu đổi trả liên quan
- refund_status (VARCHAR(20), NOT NULL): Trạng thái hoàn tiền
- transaction_code (VARCHAR(255), UNIQUE, NULL): Mã hoàn tiền từ cổng thanh toán
- reason (TEXT, NULL): Lý do hoàn tiền
- refunded_at (TIMESTAMPTZ, NULL): Thời gian hoàn tiền
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- refund_status = {PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED}

## SHIPPING

- shipping_id (BIGSERIAL, PK, NOT NULL): Mã thông tin giao hàng
- order_id (BIGINT, FK, NOT NULL): Mã đơn hàng
- address_id (BIGINT, FK, NOT NULL): Mã địa chỉ giao hàng
- shipping_provider (VARCHAR(100), NOT NULL): Đơn vị vận chuyển
- tracking_code (VARCHAR(100), UNIQUE, NULL): Mã vận đơn
- shipping_status (VARCHAR(30), NOT NULL): Trạng thái giao hàng
- shipped_at (TIMESTAMPTZ, NULL): Thời gian bắt đầu giao hàng
- delivered_at (TIMESTAMPTZ, NULL): Thời gian giao hàng thành công
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

## RETURN_REQUEST

- return_id (INT, PK, NOT NULL): Mã yêu cầu đổi trả
- order_id (BIGINT, FK, NOT NULL): Mã đơn hàng gốc
- customer_id (BIGINT, FK, NULL): Mã khách hàng yêu cầu đổi trả
- return_reason (TEXT, NOT NULL): Lý do đổi/trả hàng
- return_status (VARCHAR(30), NOT NULL): Trạng thái đổi trả
- requested_at (TIMESTAMPTZ, NOT NULL): Thời gian gửi yêu cầu đổi/trả
- approved_at (TIMESTAMPTZ, NULL): Thời gian duyệt yêu cầu
- completed_at (TIMESTAMPTZ, NULL): Thời gian hoàn tất đổi/trả
- handled_by (INT, FK, NULL): Nhân viên xử lý
- note (TEXT, NULL): Ghi chú xử lý
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- return_status = {REQUESTED, APPROVED, REJECTED, RETURNING, RECEIVED, COMPLETED, CANCELLED}

## RETURN_ITEM

- return_item_id (SERIAL, PK, NOT NULL): Mã dòng sản phẩm đổi/trả
- return_id (INT, FK, NOT NULL): Mã yêu cầu đổi/trả
- order_item_id (BIGINT, FK, NOT NULL): Mã dòng sản phẩm trong đơn hàng
- return_quantity (INT, NOT NULL): Số lượng đổi/trả
- return_amount (NUMERIC(14,2), NOT NULL): Số tiền hoàn trả cho dòng sản phẩm
- item_condition (VARCHAR(50), NULL): Tình trạng sản phẩm khi hoàn
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

## REVIEW

- review_id (BIGSERIAL, PK, NOT NULL): Mã đánh giá
- customer_id (BIGINT, FK, NOT NULL): Mã khách hàng đánh giá
- order_item_id (BIGINT, FK, UNIQUE, NOT NULL): Mã dòng sản phẩm đã mua
- rating (SMALLINT, NOT NULL): Số sao đánh giá
- review_content (TEXT, NULL): Nội dung đánh giá
- review_status (VARCHAR(20), NOT NULL): Trạng thái đánh giá
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- review_status = {HIDDEN, DISPLAY}
- UNIQUE (customer_id, order_item_id)

## REVIEW_MEDIA

- review_id (BIGINT, PK, FK, NOT NULL): Mã đánh giá
- media_id (BIGINT, PK, FK, NOT NULL): Mã hình ảnh/video
- display_order (SMALLINT, NOT NULL): Thứ tự hiển thị
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo

**Ghi chú / Enum:**
- Sắp xếp hiển thị theo thời gian tạo.

## CUSTOMIZATION_REQUEST

- customization_id (INT, PK, NOT NULL): Mã yêu cầu customize
- customer_id (BIGINT, FK, NULL): Mã khách hàng
- component_id (INT, FK, NOT NULL): Mã component sản phẩm cần customize
- source_profile_id (INT, FK, NULL): Hồ sơ số đo nguồn dùng để tạo snapshot
- unit_price (NUMERIC(14,2), NOT NULL): Giá gốc sản phẩm
- surcharge_percent (NUMERIC(5,2), NOT NULL): Tỷ lệ phụ phí
- surcharge_amount (NUMERIC(14,2), NOT NULL): Số tiền phụ phí
- custom_price (NUMERIC(14,2), NOT NULL): Giá sau khi cộng phụ phí
- customization_status (VARCHAR(30), NOT NULL): Trạng thái customize
- customer_note (TEXT, NULL): Ghi chú yêu cầu của khách
- staff_note (TEXT, NULL): Ghi chú xử lý của nhân viên
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- customization_status = {REQUESTED, MEASUREMENT_PENDING, MEASURED, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED}
- `customization_request` gắn với `component_id`, không gắn với `product_line_id`.
- `source_profile_id` chỉ phục vụ truy vết request được tạo từ profile nào, không phải nguồn dữ liệu động để đọc lại số đo giao dịch.
- Số đo dùng cho giao dịch nên được chụp snapshot riêng theo từng `customization_request`.

## CUSTOMIZATION_MEASUREMENT_SNAPSHOT

- snapshot_id (BIGSERIAL, PK, NOT NULL): Mã snapshot số đo của request
- customization_id (INT, FK, UNIQUE, NOT NULL): Mã yêu cầu customize
- source_profile_id (INT, FK, NULL): Hồ sơ số đo nguồn tại thời điểm chụp
- measurement_source (VARCHAR(20), NOT NULL): Nguồn phát sinh snapshot
- captured_at (TIMESTAMPTZ, NOT NULL): Thời điểm chụp snapshot
- captured_by (INT, FK, NULL): Nhân viên hoặc actor thực hiện chụp
- measurement_payload (JSONB, NULL): Payload số đo raw hoặc cache API
- note (TEXT, NULL): Ghi chú snapshot
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo

**Ghi chú / Enum:**
- measurement_source = {PROFILE, APPOINTMENT, MANUAL}
- Mỗi `customization_request` có tối đa một snapshot số đo hiệu lực.
- `measurement_payload` chỉ là dữ liệu hỗ trợ; source of truth vẫn nên nằm ở bảng detail.

## CUSTOMIZATION_MEASUREMENT_SNAPSHOT_DETAIL

- snapshot_detail_id (BIGSERIAL, PK, NOT NULL): Mã chi tiết snapshot
- snapshot_id (BIGINT, FK, NOT NULL): Mã snapshot số đo
- measurement_type_id (INT, FK, NOT NULL): Mã loại thông số đo
- measurement_value (NUMERIC(10,2), NOT NULL): Giá trị số đo tại thời điểm chụp
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo

**Ghi chú / Enum:**
- UNIQUE đề xuất: `(snapshot_id, measurement_type_id)`
- Đây là bảng bất biến phục vụ giỏ hàng, đơn hàng, sản xuất và hậu kiểm.

## MEASUREMENT_APPOINTMENT

- appointment_id (SERIAL, PK, NOT NULL): Mã lịch hẹn
- customer_id (BIGINT, FK, NULL): Mã khách hàng
- product_line_id (INT, FK, NULL): Dòng sản phẩm khách đang quan tâm khi đặt lịch đo
- branch_id (INT, FK, NOT NULL): Mã chi nhánh hẹn đo
- staff_id (INT, FK, NULL): Nhân viên phụ trách
- appointment_date (DATE, NOT NULL): Ngày hẹn
- start_time (TIME, NOT NULL): Giờ bắt đầu
- end_time (TIME, NOT NULL): Giờ kết thúc
- appointment_status (VARCHAR(20), NOT NULL): Trạng thái lịch hẹn
- customer_note (TEXT, NULL): Ghi chú của khách hàng
- staff_note (TEXT, NULL): Ghi chú của nhân viên
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- appointment_status = {PENDING, CONFIRMED, COMPLETED, CANCELLED, NO_SHOW}
- Đối với start_time và end_time, mặc định diff là 30 phút. Ví dụ UI chọn 8:00 - 8:30 thì hệ thống tách start_time = 8:00 và end_time = 8:30.
- `measurement_appointment` là nghiệp vụ lịch đo độc lập, khách có thể đặt lịch đo trước khi phát sinh `customization_request`.
- `product_line_id` chỉ phản ánh sản phẩm khách đang quan tâm tại thời điểm đặt lịch, không đồng nghĩa đã tạo `customization_request`.

## MEASUREMENT_PROFILE

- measurement_profile_id (INT, PK, NOT NULL): Mã hồ sơ số đo
- appointment_id (INT, FK, NULL): Mã lịch hẹn phát sinh số đo
- customer_id (BIGINT, FK, NULL): Mã khách hàng
- measured_by (INT, FK, NULL): Nhân viên đo
- note (TEXT, NULL): Ghi chú số đo
- is_active (BOOLEAN, NOT NULL): Trạng thái hồ sơ, có đang dùng không?
- measurement_date (TIMESTAMPTZ, NOT NULL): Thời gian đo
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- `measurement_profile` là hồ sơ số đo cá nhân hiện hành của khách, phục vụ quản lý tài khoản, gợi ý size và làm nguồn tạo request mới.
- Không nên dùng `measurement_profile` làm nguồn động để hiển thị lại số đo của giao dịch cũ.
- Khi khách nhập/chỉnh sửa số đo, hệ thống có thể cập nhật trực tiếp hồ sơ đang active; dữ liệu giao dịch vẫn được giữ ở snapshot của `customization_request`.

## MEASUREMENT_PROFILE_DETAIL

- measurement_detail_id (INT, PK, NOT NULL): Mã hồ sơ số đo chi tiết
- measurement_profile_id (INT, FK, NOT NULL): Mã hồ sơ số đo
- measurement_type_id (INT, FK, NOT NULL): Mã thông số đo
- measurement_value (NUMERIC(10,2), NOT NULL): Giá trị đo
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

## CHAT_CONVERSATION

- conversation_id (BIGSERIAL, PK, NOT NULL): Mã cuộc trò chuyện
- customer_id (BIGINT, FK, NULL): Khách hàng đã đăng nhập
- guest_session_id (UUID, NULL): Phiên khách vãng lai
- assigned_staff_id (INT, FK, NULL): Nhân viên đang phụ trách
- channel (VARCHAR(20), NOT NULL): Kênh tư vấn
- status (VARCHAR(20), NOT NULL): Trạng thái cuộc trò chuyện
- last_message_at (TIMESTAMPTZ, NULL): Thời gian tin nhắn gần nhất
- closed_at (TIMESTAMPTZ, NULL): Thời gian kết thúc cuộc trò chuyện
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo
- updated_at (TIMESTAMPTZ, NULL): Thời gian cập nhật

**Ghi chú / Enum:**
- channel = {WEB, MOBILE}
- status = {OPEN, WAITING, CLOSED}

## CHAT_MESSAGE

- message_id (BIGSERIAL, PK, NOT NULL): Mã tin nhắn
- conversation_id (BIGINT, FK, NOT NULL): Cuộc trò chuyện
- sender_type (VARCHAR(20), NOT NULL): Loại người gửi
- sender_customer_id (BIGINT, FK, NULL): Mã khách gửi
- sender_staff_id (INT, FK, NULL): Mã nhân viên gửi
- message_type (VARCHAR(20), NOT NULL): Loại tin nhắn
- message_content (TEXT, NULL): Nội dung tin nhắn
- reply_to_message_id (BIGINT, FK, NULL): Tin nhắn được trả lời
- sent_at (TIMESTAMPTZ, NOT NULL): Thời gian gửi
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo

**Ghi chú / Enum:**
- sender_type = {CUSTOMER, STAFF}
- message_type = {TEXT, IMAGE, FILE, SYSTEM}

## CHAT_MESSAGE_MEDIA

- message_id (BIGINT, PK, FK, NOT NULL): Mã tin nhắn
- media_id (BIGINT, PK, FK, NOT NULL): File trong bảng MEDIA
- display_order (SMALLINT, NOT NULL): Thứ tự hiển thị
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo

## CHAT_ASSIGNMENT_HISTORY

- assignment_id (BIGSERIAL, PK, NOT NULL): Mã phân công
- conversation_id (BIGINT, FK, NOT NULL): Mã cuộc trò chuyện
- staff_id (INT, FK, NOT NULL): Mã nhân viên được giao
- assigned_by (INT, FK, NOT NULL): Người thực hiện phân công
- assigned_at (TIMESTAMPTZ, NOT NULL): Thời gian nhận
- unassigned_at (TIMESTAMPTZ, NULL): Thời gian kết thúc phụ trách
- reason (VARCHAR(255), NULL): Lý do chuyển
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo

## CHAT_MESSAGE_READ

- message_id (BIGINT, PK, FK, NOT NULL): Mã tin nhắn
- reader_type (VARCHAR(20), PK, NOT NULL): Loại người đọc
- reader_id (BIGINT, PK, FK, NOT NULL): ID người đọc
- read_at (TIMESTAMPTZ, NOT NULL): Thời gian đọc

**Ghi chú / Enum:**
- reader_type = {CUSTOMER, STAFF}

## CHAT_TAG

- tag_id (SERIAL, PK, NOT NULL): Mã nhãn
- tag_name (VARCHAR(100), NOT NULL): Tên nhãn
- description (VARCHAR(255), NOT NULL): Mô tả
- is_active (BOOLEAN, NOT NULL): Trạng thái hoạt động
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo

**Ghi chú / Enum:**
- Ví dụ tag_name: đổi trả, tư vấn, size, ...

## CHAT_CONVERSATION_TAG

- conversation_id (BIGINT, PK, FK, NOT NULL): Mã cuộc trò chuyện
- tag_id (INT, PK, FK, NOT NULL): Mã nhãn cuộc trò chuyện
- assigned_by (INT, FK, NULL): Mã nhân viên đã gắn tag cuộc trò chuyện, NULL nếu hệ thống tự động
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo

## PERSONAL_COLOR_RESULT

- result_id (BIGSERIAL, PK, NOT NULL): Mã kết quả tư vấn personal color.
- customer_id (BIGINT, FK, NULL): Mã khách hàng đã đăng nhập.
- guest_session_id (UUID, NULL): Mã phiên khách vãng lai.
- temperature_result (VARCHAR(20), NOT NULL): Kết quả phân loại nhiệt độ màu của khách hàng.
- value_result (VARCHAR(20), NOT NULL): Kết quả phân loại độ sáng/tối của khách hàng.
- season_result (VARCHAR(30), NOT NULL): Nhóm mùa personal color được hệ thống xác định.
- recommended_at (TIMESTAMPTZ, NOT NULL): Thời điểm hệ thống đưa ra kết quả.
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo.

**Ghi chú / Enum:**
- temperature_result = {WARM, COOL}
- value_result = {LIGHT, DEEP}
- season_result = {SPRING, SUMMER, AUTUMN, WINTER}
- Quy tắc ánh xạ kết quả:
  - WARM + LIGHT = SPRING
  - WARM + DEEP = AUTUMN
  - COOL + LIGHT = SUMMER
  - COOL + DEEP = WINTER
- Câu hỏi quiz và cách tính điểm được xử lý trong frontend/backend, không lưu trong database.

## PERSONAL_COLOR_RESULT_COLOR

- result_id (BIGINT, PK, FK, NOT NULL): Mã kết quả tư vấn personal color.
- color_id (INT, PK, FK, NOT NULL): Mã màu phù hợp được hệ thống đề xuất.
- display_order (SMALLINT, NULL): Thứ tự hiển thị màu được đề xuất.
- created_at (TIMESTAMPTZ, NOT NULL): Thời gian tạo.

**Ghi chú / Enum:**
- Một kết quả personal color có thể đề xuất nhiều màu từ bảng COLOR.
- Danh sách sản phẩm phù hợp được truy vấn động dựa trên các color_id đã được đề xuất.
