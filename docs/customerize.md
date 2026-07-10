# Luồng Dữ Liệu Sản Phẩm Customize

Tài liệu này chốt lại hướng xử lý nghiệp vụ `customize` theo nguyên tắc:

- `customization_request` gắn với `component_id`, không gắn với `product_line_id`
- dữ liệu giao dịch phải giữ nguyên theo thời điểm khách đặt/mua
- hồ sơ số đo cá nhân của khách được phép thay đổi theo thời gian
- vì vậy cần tách `profile` quản lý cá nhân khỏi `snapshot` số đo dùng cho từng request/cart/order

## 1. Kết luận đề xuất

Hướng phù hợp cho schema hiện tại là:

1. `measurement_profile` là hồ sơ số đo cá nhân hiện hành của khách.
2. Khi tạo `customization_request`, hệ thống chụp `measurement_snapshot` JSON cho request đó.
3. Khi thêm vào giỏ, `sales.cart_item` chụp tiếp `customization_snapshot` từ request.
4. Khi checkout, `sales.order_item` chụp tiếp `customization_snapshot` từ cart item.
5. `measurement_profile_id` trên request chỉ để truy vết nguồn profile, không phải nguồn dữ liệu động cho giao dịch.
6. Khi khách sửa số đo cá nhân sau này, chỉ cập nhật `measurement_profile`; snapshot của request/cart/order cũ giữ nguyên.

Nói ngắn gọn:

- `measurement_profile` = dữ liệu khách đang quản lý cho bản thân
- `customization_request.measurement_snapshot` = snapshot số đo tại thời điểm tạo request
- `cart_item.customization_snapshot` = snapshot số đo tại thời điểm add-to-cart
- `order_item.customization_snapshot` = snapshot số đo tại thời điểm checkout

## 2. Vì sao không đọc động từ profile

Không nên dùng `measurement_profile` làm nguồn hiển thị lại dữ liệu giao dịch vì:

- profile cá nhân có thể bị cập nhật nhiều lần
- `cart_item` và `order_item` cần giữ nguyên dữ liệu theo thời điểm khách chốt
- nếu request đọc động từ profile thì giỏ hàng cũ và đơn hàng cũ có thể bị trôi số đo

Profile nên phục vụ:

- quản lý số đo cá nhân
- gợi ý cho lần mua tiếp theo
- làm nguồn tạo request mới

## 3. Mô hình dữ liệu chốt

### 3.1. Hồ sơ cá nhân mutable

- `customization.measurement_profile`
- `customization.measurement_profile_detail`

Vai trò:

- nơi khách xem và quản lý số đo cá nhân
- staff có thể cập nhật khi khách đo lại
- dùng làm nguồn để tạo request mới
- mỗi customer chỉ có tối đa một profile active tại một thời điểm

### 3.2. Snapshot bất biến theo từng mốc giao dịch

- `customization.customization_request.measurement_snapshot`
- `sales.cart_item.customization_snapshot`
- `sales.order_item.customization_snapshot`

Vai trò:

- giữ số đo bất biến tại thời điểm tạo request
- giữ tiếp snapshot tại thời điểm thêm vào giỏ
- giữ tiếp snapshot tại thời điểm checkout
- không bị ảnh hưởng nếu khách sửa profile cá nhân sau này

## 4. Luồng nghiệp vụ

### 4.1. Khách đặt lịch đo trước, chưa mua ngay

1. Tạo `customization.measurement_appointment`.
2. Khi đo xong, tạo hoặc cập nhật `measurement_profile`.
3. Tạo các dòng `measurement_profile_detail`.
4. Chưa tạo `customization_request` nếu khách chưa chọn món để đặt may.

Quan hệ:

`measurement_appointment` -> `measurement_profile` -> `measurement_profile_detail`

### 4.2. Khách đã có profile và bắt đầu đặt một món customize

1. Khách chọn đúng `component_id` cần may đo.
2. Hệ thống cho khách chọn profile hiện hành hoặc nhập tay số đo.
3. Tạo `customization_request`.
4. Ghi `measurement_profile_id` nếu request lấy dữ liệu từ profile.
5. Ghi `measurement_snapshot` JSON vào request.
6. Tính `custom_price`.
7. Thêm vào `sales.cart_item` với `customization_id`; nếu chưa truyền snapshot thì DB tự copy từ request.
8. Khi checkout, tạo `sales.order_item` với cùng `customization_id` và copy `customization_snapshot` từ cart item.

Quan hệ:

`measurement_profile` -> `customization_request.measurement_snapshot`

và

`customization_request` -> `sales.cart_item.customization_snapshot` -> `sales.order_item.customization_snapshot`

### 4.3. Khách nhập số đo lần đầu ngay trong lúc đặt hàng

1. Khách chọn `component_id`.
2. Khách nhập số đo online.
3. Hệ thống tạo `measurement_profile` và `measurement_profile_detail` để khách có hồ sơ cá nhân về sau.
4. Đồng thời tạo `customization_request` với `measurement_snapshot`.
5. Thêm `customization_id` và `customization_snapshot` vào `cart_item`.
6. Checkout tạo `order_item` với snapshot giữ nguyên từ cart.

### 4.4. Khách sửa số đo sau một thời gian

1. Khách vào trang quản lý số đo cá nhân.
2. Hệ thống update `measurement_profile` hiện hành.
3. Không cập nhật ngược snapshot của các `customization_request`, `cart_item`, `order_item` cũ.
4. Các request mới sau thời điểm đó sẽ snapshot bộ số đo mới.

## 5. Quy tắc nghiệp vụ nên chốt

- `customization_request` luôn gắn `component_id`.
- `measurement_appointment` mới là nơi có thể lưu `product_line_id` tham khảo.
- Mỗi customer chỉ có tối đa một `measurement_profile.is_active = true`.
- Mỗi `customization_request` chỉ có một `measurement_snapshot` hiệu lực.
- `cart_item` và `order_item` giữ snapshot riêng theo từng mốc nghiệp vụ.
- `order_item` không được phụ thuộc vào dữ liệu số đo động của profile cá nhân.

## 6. Tóm tắt quyết định

Nếu chọn một hướng duy nhất cho dự án này thì nên chọn:

- giữ `measurement_profile` để quản lý số đo cá nhân
- lưu `measurement_snapshot` ngay trên `customization_request`
- copy tiếp thành `customization_snapshot` trên `cart_item` và `order_item`
- không dùng profile mutable làm nguồn lịch sử giao dịch

Đây là hướng cân bằng nhất giữa:

- đúng nghiệp vụ
- an toàn dữ liệu lịch sử
- dễ triển khai ngay trong schema hiện tại
- dễ báo cáo và debug hơn so với đọc động từ profile
