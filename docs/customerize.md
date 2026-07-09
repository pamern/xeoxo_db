# Luồng Dữ Liệu Sản Phẩm Customize

Tài liệu này chốt lại hướng xử lý nghiệp vụ `customize` theo nguyên tắc:

- `customization_request` gắn với `component_id`, không gắn với `product_line_id`
- dữ liệu giao dịch phải giữ nguyên theo thời điểm khách đặt/mua
- hồ sơ số đo cá nhân của khách được phép thay đổi theo thời gian
- vì vậy cần tách `profile` quản lý cá nhân khỏi `snapshot` số đo dùng cho từng request

## 1. Kết luận đề xuất

Hướng phù hợp nhất cho dự án là:

1. `measurement_profile` là hồ sơ số đo cá nhân hiện hành của khách.
2. Khi tạo `customization_request`, hệ thống chụp một bản snapshot số đo riêng cho request đó.
3. `cart_item` và `order_item` chỉ cần gắn với `customization_request`.
4. `customization_request` có thể lưu thêm `source_profile_id` để biết snapshot này lấy từ profile nào, nhưng không phụ thuộc profile đó để đọc dữ liệu giao dịch.
5. Khi khách sửa số đo cá nhân sau này, chỉ cập nhật `measurement_profile` hiện hành; snapshot của các request cũ giữ nguyên.

Nói ngắn gọn:

- `measurement_profile` = dữ liệu khách đang quản lý cho bản thân
- `customization_request` = yêu cầu may đo của một món cụ thể
- `customization_measurement_snapshot` = số đo bất biến tại thời điểm tạo request

## 2. Vì sao không nên dùng 3 hướng cũ theo cách thuần túy

### Hướng 1: cập nhật trực tiếp profile cũ

Không nên dùng làm nguồn dữ liệu giao dịch vì:

- `cart_item` và `order_item` đang tham chiếu về `customization_request`
- nếu `customization_request` lại đọc số đo từ `measurement_profile` đang bị update
- thì đơn hàng cũ có thể hiển thị số đo khác với lúc khách mua

Hướng này chỉ phù hợp nếu `profile` là dữ liệu quản lý cá nhân, không phải dữ liệu lịch sử giao dịch.

### Hướng 2: mỗi lần đổi số đo thì clone toàn bộ detail và tạo profile mới

Hướng này tốt hơn hướng 1 vì có lịch sử, nhưng vẫn chưa tối ưu nếu dùng profile làm nguồn chính cho giao dịch:

- logic active/inactive profile sẽ phức tạp hơn
- một khách có thể có rất nhiều profile chỉ vì chỉnh vài thông số
- frontend/backend phải xử lý chọn đúng profile đang active, profile nào dùng cho đơn cũ, profile nào dùng cho lần mua mới
- bản chất giao dịch vẫn đang phụ thuộc vào concept hồ sơ cá nhân

Hướng này chỉ nên dùng nếu nghiệp vụ thật sự cần version hóa profile cho mục đích quản lý khách hàng, không nên thay thế snapshot giao dịch.

### Hướng 3: lưu JSON số đo vào `customization_request`

Hướng này gần đúng với nhu cầu nhất vì nó tách được dữ liệu giao dịch khỏi profile cá nhân.

Tuy nhiên nếu chỉ lưu JSON thuần trong một cột thì có vài điểm yếu:

- khó validate cấu trúc chặt chẽ bằng FK
- khó query theo từng loại số đo
- khó đồng bộ với danh mục `measurement_type`
- về lâu dài dễ thành dữ liệu khó kiểm soát

Nếu muốn dùng JSON thì nên dùng như bản cache hoặc payload API, không nên là cấu trúc dữ liệu duy nhất.

## 3. Giải pháp tối ưu hơn

Nên dùng mô hình 2 lớp:

### Lớp 1: Hồ sơ cá nhân

- `customization.measurement_profile`
- `customization.measurement_profile_detail`

Vai trò:

- nơi khách xem và quản lý số đo cá nhân
- staff có thể cập nhật khi khách đo lại
- dùng làm nguồn để tạo request mới
- có thể update trực tiếp nếu sản phẩm chỉ cần giữ một hồ sơ hiện hành cho khách

### Lớp 2: Snapshot cho từng request

- `customization.customization_request`
- `customization.customization_measurement_snapshot`
- `customization.customization_measurement_snapshot_detail`

Vai trò:

- lưu bộ số đo bất biến tại thời điểm khách tạo yêu cầu may đo
- là nguồn dữ liệu để hiển thị lại trên giỏ hàng, đơn hàng, sản xuất, hậu kiểm
- không bị ảnh hưởng nếu khách sửa profile cá nhân sau này

## 4. Mô hình dữ liệu nên dùng

### 4.1. `customization_request`

Nên lưu:

- `customization_id`
- `customer_id`
- `component_id`
- `source_profile_id` nullable
- `unit_price`
- `surcharge_percent`
- `surcharge_amount`
- `custom_price`
- `customization_status`
- `customer_note`
- `staff_note`
- `created_at`
- `updated_at`

Ý nghĩa:

- `component_id` mới là đối tượng thật sự được may đo
- `source_profile_id` chỉ để truy vết snapshot được tạo từ profile nào
- không dùng `source_profile_id` làm nguồn đọc số đo động cho giao dịch

### 4.2. `customization_measurement_snapshot`

Nên có:

- `snapshot_id`
- `customization_id`
- `source_profile_id` nullable
- `measurement_source` như `PROFILE`, `APPOINTMENT`, `MANUAL`
- `captured_at`
- `captured_by`
- `note`

### 4.3. `customization_measurement_snapshot_detail`

Nên có:

- `snapshot_detail_id`
- `snapshot_id`
- `measurement_type_id`
- `measurement_value`
- `created_at`

Ý nghĩa:

- mỗi request có đúng một snapshot header
- snapshot header có nhiều detail
- cấu trúc này query và validate tốt hơn việc nhét toàn bộ vào một cột JSON

### 4.4. Có cần thêm JSON không?

Có thể thêm một cột `measurement_payload JSONB` ở bảng snapshot để:

- trả API nhanh hơn
- lưu nguyên payload frontend gửi lên
- phục vụ audit/debug

Nhưng source of truth vẫn nên là bảng detail.

## 5. Luồng nghiệp vụ đề xuất

### 5.1. Khách đặt lịch đo trước, chưa mua ngay

1. Tạo `customization.measurement_appointment`.
2. `measurement_appointment` có thể lưu `product_line_id` như thông tin tham khảo khách đang quan tâm.
3. Khi đo xong, tạo hoặc cập nhật `measurement_profile`.
4. Tạo các dòng `measurement_profile_detail`.
5. Chưa tạo `customization_request` nếu khách chưa chọn món để đặt may.

Quan hệ:

`measurement_appointment` -> `measurement_profile` -> `measurement_profile_detail`

### 5.2. Khách đã có profile và bắt đầu đặt một món customize

1. Khách chọn đúng `component_id` cần may đo.
2. Hệ thống cho khách chọn profile hiện hành hoặc nhập tay số đo.
3. Tạo `customization_request`.
4. Ghi `source_profile_id` nếu request lấy dữ liệu từ profile.
5. Tạo `customization_measurement_snapshot`.
6. Copy toàn bộ số đo sang `customization_measurement_snapshot_detail`.
7. Tính `custom_price`.
8. Thêm vào `sales.cart_item` với `customization_id`.
9. Khi checkout, tạo `sales.order_item` với cùng `customization_id`.

Quan hệ:

`measurement_profile` -> `customization_request` -> `customization_measurement_snapshot` -> `snapshot_detail`

và

`customization_request` -> `sales.cart_item` -> `sales.order_item` -> `sales.sales_order`

### 5.3. Khách nhập số đo lần đầu ngay trong lúc đặt hàng

1. Khách chọn `component_id`.
2. Khách nhập số đo online.
3. Hệ thống tạo `measurement_profile` và `measurement_profile_detail` để khách có hồ sơ cá nhân về sau.
4. Đồng thời tạo `customization_request`.
5. Tạo snapshot riêng cho request từ bộ số đo vừa nhập.
6. Thêm `customization_id` vào `cart_item`.
7. Checkout tạo `order_item`.

Điểm quan trọng:

- profile cá nhân và snapshot giao dịch được tạo cùng lúc
- nhưng sau đó tách biệt vòng đời

### 5.4. Khách sửa số đo sau một thời gian

1. Khách vào trang quản lý số đo cá nhân.
2. Hệ thống update `measurement_profile` hiện hành, hoặc version hóa profile nếu sau này cần lịch sử quản trị.
3. Không cập nhật ngược snapshot của các `customization_request` cũ.
4. Tất cả `cart_item` và `order_item` cũ vẫn đọc theo snapshot của request tương ứng.
5. Các request mới sau thời điểm đó sẽ snapshot bộ số đo mới.

## 6. Xử lý `cart_item` và `order_item`

Hiện tại việc:

- `cart_item.customization_id` -> `customization_request`
- `order_item.customization_id` -> `customization_request`

là hợp lý và nên giữ.

Thứ cần đổi không phải là liên kết này, mà là nguồn dữ liệu số đo đằng sau `customization_request`:

- không đọc động từ `measurement_profile`
- đọc từ snapshot bất biến của chính request đó

Như vậy:

- giỏ hàng đang chờ checkout vẫn giữ đúng số đo đã chốt khi thêm vào giỏ
- đơn hàng sau khi mua giữ đúng số đo tại thời điểm mua
- khách vẫn có thể sửa hồ sơ số đo cá nhân cho các lần mua tiếp theo

## 7. Trạng thái dữ liệu

### Với `measurement_appointment`

- `PENDING`: vừa tạo lịch
- `CONFIRMED`: đã xác nhận lịch
- `COMPLETED`: đã đo xong
- `CANCELLED`: hủy lịch
- `NO_SHOW`: khách không tới

### Với `customization_request`

- `REQUESTED`: vừa tạo yêu cầu
- `MEASUREMENT_PENDING`: đang chờ số đo hoặc chờ xác nhận số đo
- `MEASURED`: đã có snapshot số đo
- `CONFIRMED`: đã chốt giá và thông số
- `IN_PROGRESS`: đang may / đang xử lý
- `COMPLETED`: đã hoàn tất
- `CANCELLED`: đã hủy

## 8. Quy tắc nghiệp vụ nên chốt

- `customization_request` luôn gắn `component_id`
- `measurement_appointment` mới là nơi có thể lưu `product_line_id` tham khảo
- một `customization_request` chỉ có một snapshot số đo hiệu lực
- snapshot đã tạo thì không sửa đè; nếu thật sự cần sửa sau khi staff xác nhận, nên tạo snapshot mới và đóng snapshot cũ bằng trạng thái hoặc version
- `order_item` không được phụ thuộc vào dữ liệu số đo động của profile cá nhân

## 9. Tóm tắt quyết định

Nếu chọn một hướng duy nhất cho dự án này thì nên chọn:

- giữ `measurement_profile` để quản lý số đo cá nhân
- tạo snapshot riêng cho từng `customization_request`
- để `cart_item` và `order_item` tiếp tục tham chiếu `customization_request`
- không dùng profile mutable làm nguồn lịch sử giao dịch

Đây là hướng cân bằng nhất giữa:

- đúng nghiệp vụ
- an toàn dữ liệu lịch sử
- dễ mở rộng
- dễ báo cáo và debug hơn so với lưu JSON thuần
