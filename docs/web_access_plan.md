# Web Access Plan

## 1. Mục tiêu và phạm vi

Tài liệu này là phần triển khai tiếp theo của [schema_access_control.md](/home/ngocmypzg/Projects/xeoxo_db/docs/schema_access_control.md).

Phân vai rõ như sau:

- `schema_access_control.md`: nguồn gốc về chia schema, role và nguyên tắc quyền truy cập
- `web_access_plan.md`: chốt chính xác những `index`, `RLS`, `view` cần làm để web client chạy tốt

Tài liệu này không lặp lại toàn bộ ma trận quyền ở mức schema. Nó chỉ trả lời 3 câu hỏi:

1. Index nào thực sự phải có
2. RLS nào phải bật cho frontend
3. View nào đáng tạo ngay

Nguyên tắc:

- Không tối ưu sớm bằng số lượng index lớn
- Không tạo view nếu query thường đã đủ rõ
- Không mở bảng gốc cho frontend nếu dữ liệu nhạy cảm hoặc dễ bị lạm dụng
- Ưu tiên cấu hình ít nhưng bền, dễ bảo trì

---

## 2. Các luồng frontend cần phục vụ

Kế hoạch này chỉ tối ưu cho các luồng sau:

- Trang category
- Trang collection
- Product listing
- Product detail
- Gallery media của product line
- Bảng size
- Cart
- Order history
- Hồ sơ khách hàng, địa chỉ, loyalty
- Review public
- Personal color result của chính người dùng
- Measurement profile của chính người dùng

Không tối ưu trực tiếp cho:

- Admin dashboard
- Staff backoffice
- Search full-text nâng cao
- Analytics
- Support/chat nội bộ

Những phần đó nếu làm sau sẽ có tài liệu riêng.

---

## 3. Kế hoạch Index

## 3.1 Kết luận chung

Ở giai đoạn hiện tại, chỉ nên tạo thêm đúng 13 index bổ sung. Ngoài danh sách này, mặc định chưa làm.

Lý do:

- Phần lớn bảng master còn nhỏ
- Frontend hiện chủ yếu đọc theo một số trục rất rõ: `status`, `collection`, `category`, `product_line`, `customer`
- Thêm nhiều index sẽ làm tăng chi phí insert/update và khiến migration phình ra mà hiệu quả chưa chắc có

---

## 3.2 Danh sách index chốt triển khai

Danh sách dưới đây đã được rút về mức tối thiểu cho frontend. Nó chỉ giữ các index phục vụ trực tiếp 5 nhóm truy vấn nóng:

- dựng category / collection public
- product listing
- product detail
- cart / order history
- owner lookup cho customer data

Các index do `PK`, `UNIQUE` constraint đã tự sinh sẵn thì không tính vào con số 13 này. Ví dụ:

- `catalog.category.slug` nếu đã được khai báo unique ở migration
- `catalog.product_variant.sku` nếu đã unique
- `iam.customer.account_id` nếu đã unique
- `catalog.media.storage_key` nếu sau này được chuẩn hóa thành unique constraint

### catalog.category

Tạo:

- index trên `(department, parent_id)` với điều kiện `is_active = true`

Giải thích:

- Category tree của frontend chủ yếu đi theo `department`
- `parent_id` phục vụ dựng cây cha con
- Không cần index riêng cho `is_active`; dùng partial index là đủ

### catalog.product_line

Tạo:

- index trên `(collection_id, status)`
- index trên `(color_id, status)`

Không tạo:

- index riêng cho `material_id`
- index riêng cho `status`
- index riêng cho `is_featured`

Giải thích:

- Đây là bảng đọc nhiều nhất
- Listing hiện đi mạnh theo collection và color
- `material_id` mới là filter phụ, chưa đáng tách index riêng
- `status` luôn đi kèm filter khác nên không cần đứng một mình
- `is_featured` có thể tận dụng tập dữ liệu active hiện có, chưa đáng tách riêng ở giai đoạn đầu

### catalog.line_category

Giữ:

- PK/unique `(product_line_id, category_id)`

Tạo thêm:

- index trên `(category_id, product_line_id)`

Giải thích:

- PK hiện tại hỗ trợ join từ product sang category
- Listing theo category cần chiều ngược lại

### catalog.product_component

Tạo:

- index trên `(product_line_id, display_order)`

Giải thích:

- Product detail luôn load component theo product line và thứ tự hiển thị

### catalog.product_variant

Tạo:

- index trên `(component_id, status)`

Giải thích:

- Variant hiện được resolve chủ yếu từ component
- `size_option_id` một mình chưa phải điểm vào truy vấn chính

### catalog.product_line_media

Giữ:

- PK/unique `(product_line_id, media_id)`

Tạo thêm:

- index trên `(product_line_id, media_role, display_order)`

Giải thích:

- Gallery frontend luôn đọc theo `product_line_id`
- Cần sort ổn định theo role rồi đến display order

### catalog.size_chart

Tạo:

- index trên `(product_line_id)`

Không tạo:

- index riêng cho `is_active`

Giải thích:

- Truy vấn thực tế là tìm size chart của product line
- `is_active` chỉ là điều kiện phụ, chưa đáng index đơn lẻ

### catalog.size_measurement

Tạo:

- index trên `(size_option_id, measurement_type_id)`

Giải thích:

- Phục vụ render bảng số đo theo từng size option

### sales.cart

Tạo:

- index trên `(customer_id)`

Không tạo:

- index `session_id` ở giai đoạn này

Giải thích:

- Hiện kế hoạch frontend tập trung vào user đăng nhập
- Guest cart chỉ thêm index khi flow guest được chốt thật

### sales.cart_item

Tạo:

- index trên `(cart_id)`

Không tạo:

- index riêng cho `variant_id`

Giải thích:

- Cart item luôn được đọc theo cart trước

### sales.sales_order

Tạo:

- index trên `(customer_id, created_at DESC)`

Không tạo:

- index `(status, created_at DESC)` cho frontend

Giải thích:

- Order history của customer là use case chính
- Index theo status phù hợp admin/backoffice hơn frontend customer

### iam.address

Tạo:

- index trên `(customer_id, is_default DESC, created_at DESC)`

Giải thích:

- Trang sổ địa chỉ luôn đọc theo customer và thường ưu tiên địa chỉ mặc định trước

---

## 3.3 Danh sách index chốt không làm ở giai đoạn này

Không làm ngay các index sau:

- `catalog.collection(status, launch_date DESC)`
- `catalog.collection(season, status)`
- `catalog.product_line(material_id)`
- `catalog.product_line(status)`
- `catalog.product_line(is_featured)` partial hoặc non-partial
- `catalog.product_variant(size_option_id)`
- `catalog.size_chart_category(category_id, size_chart_id)`
- `catalog.size_option(size_chart_id, size_name)`
- `customization.measurement_profile(customer_id, created_at DESC)`
- `catalog.media(storage_key)` nếu mục tiêu chỉ là frontend query
- `catalog.media(bucket_name, media_type)`
- `iam.customer(email)`
- `iam.customer(phone)`
- `iam.loyalty_reward(customer_id, status, expired_at)`
- `sales.cart(session_id)`
- `sales.cart_item(variant_id)`
- `sales.sales_order(status, created_at DESC)`
- `sales.order_item(order_id)`
- `sales.review(product_line_id, created_at DESC)`
- `sales.review(customer_id, created_at DESC)`
- mọi index full-text
- mọi index cho `support.*`

Lý do chung:

- Chưa bám vào đường truy vấn frontend chính
- Có thể thêm sau bằng query plan thực tế

---

## 4. Kế hoạch RLS

## 4.1 Quan hệ với schema_access_control

`schema_access_control.md` đã chốt:

- schema nào public
- schema nào private
- nhóm role nào được truy cập

Tài liệu này chỉ chốt ở mức triển khai frontend:

- bảng nào bật RLS ngay
- bảng nào mở `SELECT` public
- bảng nào chỉ owner được truy cập
- bảng nào frontend không chạm trực tiếp

---

## 4.2 Nhóm public read-only phải bật ngay

Bật RLS và tạo policy `SELECT` cho `anon` + `authenticated` trên các bảng sau:

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

Điều kiện policy:

- category: `is_active = true`
- collection: `status = 'ACTIVE'`
- product_line: `status = 'ACTIVE'`
- product_variant: `status IN ('ACTIVE', 'OUT_OF_STOCK', 'PREORDER', 'COMING_SOON')`
- các bảng con còn lại chỉ đọc được nếu bản ghi cha còn public

Ghi chú triển khai:

- Có thể policy join trực tiếp hoặc dùng condition đơn giản trên bảng con tùy schema thực tế
- Nếu muốn đơn giản migration ban đầu, cho phép public read toàn bộ bảng con catalog cũng chấp nhận được, miễn các bảng cha đã chặn đúng `ACTIVE`

---

## 4.3 Nhóm owner-based phải bật ngay

### iam.customer

Cho `authenticated`:

- `SELECT` record có `account_id = auth.uid()`
- `UPDATE` record có `account_id = auth.uid()`

Không cho:

- `INSERT`
- `DELETE`

### iam.address

Cho `authenticated`:

- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`

Điều kiện:

- address phải thuộc customer map từ `auth.uid()`

### sales.cart

Cho `authenticated`:

- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`

Điều kiện:

- cart thuộc customer hiện tại

### sales.cart_item

Cho `authenticated`:

- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`

Điều kiện:

- `cart_id` phải thuộc cart của user hiện tại

### sales.sales_order

Cho `authenticated`:

- `SELECT`

Không cho trực tiếp từ frontend:

- `UPDATE`
- `DELETE`

`INSERT`:

- khuyến nghị đi qua backend/service_role, không mở trực tiếp bằng RLS ở giai đoạn đầu

### sales.order_item

Cho `authenticated`:

- `SELECT` nếu `order_id` thuộc order của chính user

### iam.loyalty_reward

Cho `authenticated`:

- `SELECT` reward của chính mình

Không cho:

- `INSERT`
- `UPDATE`
- `DELETE`

### iam.reward_usage

Cho `authenticated`:

- `SELECT` usage của reward thuộc chính mình

### customization.measurement_profile

Cho `authenticated`:

- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`

Điều kiện:

- profile thuộc customer hiện tại

### customization.measurement_profile_detail

Cho `authenticated`:

- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`

Điều kiện:

- parent profile thuộc customer hiện tại

### catalog.personal_color_result

Cho `authenticated`:

- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`

Điều kiện:

- result thuộc customer hiện tại

### catalog.personal_color_result_color

Cho `authenticated`:

- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`

Điều kiện:

- parent result thuộc customer hiện tại

---

## 4.4 Nhóm chưa mở trực tiếp cho frontend

Giữ ngoài frontend ở giai đoạn này:

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
- `support.*`
- `metadata.*`
- `util.*`

Lý do:

- hoặc là nhạy cảm
- hoặc là chưa cần cho luồng frontend lõi
- hoặc nên đi qua backend để kiểm soát tốt hơn

Ghi chú:

- `review` có thể mở ở phase sau, nhưng chưa nên đưa vào batch RLS đầu tiên vì thường kéo theo moderation/status logic

---

## 5. Kế hoạch View cho frontend

## 5.1 Kết luận chung

Chỉ tạo 4 view ở giai đoạn này. Không tạo thêm.

Lý do:

- 4 view này bao trọn các shape lặp nhiều nhất
- Các query còn lại vẫn rõ ràng nếu gọi trực tiếp vào bảng gốc
- Giữ số lượng view thấp để tránh trùng lặp và khó refactor

---

## 5.2 Danh sách view chốt triển khai

### catalog.v_product_line_card

Mục đích:

- phục vụ collection page
- category page
- product listing chung

Trả về:

- `product_line_id`
- `line_name`
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

Tại sao phải có:

- đây là shape dùng lặp lại nhiều nhất
- nếu không có view này frontend/backend sẽ lặp join giữa product_line, collection, color, material, media, variant

### catalog.v_product_line_media_ordered

Mục đích:

- phục vụ gallery của product detail

Trả về:

- `product_line_id`
- `media_id`
- `media_role`
- `display_order`
- `storage_key`
- `bucket_name`
- `alt_text`

Tại sao phải có:

- gallery luôn cần join `product_line_media -> media`
- shape này ổn định và không có logic nghiệp vụ phức tạp

### catalog.v_size_chart_detail

Mục đích:

- phục vụ bảng size

Trả về:

- `size_chart_id`
- `chart_name`
- `product_line_id`
- `category_id`
- `size_option_id`
- `size_name`
- `measurement_type_id`
- `measurement_name`
- `measurement_value`

Tại sao phải có:

- đây là query nhiều join nhất ở product detail
- để frontend tự ghép nhiều bảng sẽ rối và dễ sai

### sales.v_my_order_summary

Mục đích:

- phục vụ order history của customer

Trả về:

- `order_id`
- `order_code`
- `created_at`
- `status`
- `total_amount`
- `item_count`
- `thumbnail_storage_key`

Tại sao phải có:

- order history là màn hình đọc lặp lại
- cần shape gọn, không bắt frontend tự gom order item

Ghi chú:

- view này vẫn phải chịu RLS owner-based của order

---

## 5.3 Các view chốt không làm ở giai đoạn này

Không tạo:

- view search tổng hợp
- view review aggregate
- view inventory availability
- view recommendation/personal color aggregate
- một view khổng lồ chứa toàn bộ product detail dạng JSON lồng nhau

Lý do:

- chưa có áp lực hiệu năng đủ lớn
- dễ làm hệ thống cứng và khó sửa hơn là giúp được frontend

---

## 6. Thứ tự triển khai

Triển khai theo đúng thứ tự này:

### Bước 1

- tạo các index trong mục 3.2

### Bước 2

- bật RLS cho nhóm public read-only ở mục 4.2
- bật RLS cho nhóm owner-based ở mục 4.3

### Bước 3

- tạo 4 view trong mục 5.2

Không đổi thứ tự.

Lý do:

- index giúp các query gốc ổn trước
- RLS cần chốt trước khi view public/frontend được dùng
- view nên làm sau cùng để bám đúng các bảng và policy đã ổn định

---

## 7. Kết luận chốt

Kế hoạch triển khai cho frontend ở giai đoạn này là:

- chỉ thêm đúng số index nêu ở mục 3.2
- chỉ bật RLS cho đúng 3 nhóm: public catalog, owner-based customer flow, private blocked tables
- chỉ tạo đúng 4 view

Nếu có nhu cầu mới ngoài phạm vi này, phải chứng minh bằng:

- màn hình frontend mới
- truy vấn mới
- hoặc query plan / thời gian phản hồi thực tế

Mặc định, ngoài những gì đã chốt trong tài liệu này thì chưa làm thêm.
