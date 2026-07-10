# Workflow Tra Cuu va Huy Don Hang

## Muc tieu

- Giup nguoi dung tra cuu don hang ma khong can dang nhap.
- Cho phep huy don hang ngay tren trang tra cuu neu don van con o trang thai cho phep huy.
- Xac minh nguoi thuc hien huy don hang bang OTP do Supabase Auth quan ly.

## Pham vi du lieu

- Khong them bang moi.
- Toan bo tra cuu va huy don hang tiep tuc bam sat cac bang hien co trong `docs/database_schema.md`.
- Trang thai don hang va giao hang van cap nhat tren cac bang don hang/shipping hien tai.

## Luong nghiep vu huy don hang tren trang tra cuu

### 1. Nguoi dung tra cuu don hang

- Nguoi dung nhap `ma don hang` va `so dien thoai hoac email dat hang`.
- He thong goi API tra cuu de tim don hang theo thong tin lien he.
- Neu tim thay, hien thi chi tiet don hang va nut `Huy Don Hang` neu trang thai don dang nam trong nhom cho phep huy.

### 2. Nguoi dung bam huy don hang

- He thong hien popup confirm huy don hang.
- Sau khi nguoi dung xac nhan, he thong tach thanh 2 nhanh xac minh:

#### Nhanh A. Tra cuu bang email

- He thong gui OTP email thong qua Supabase Auth.
- Khong su dung email magic link.
- OTP duoc gui bang cau hinh SMTP da setup tren Supabase.
- Nguoi dung nhap ma OTP trong popup xac minh.
- Frontend goi `supabase.auth.verifyOtp(...)` de xac minh OTP email.
- Chi sau khi OTP hop le thi moi goi API huy don hang.
- Khi API huy thanh cong, frontend goi lai luong tra cuu de reload thong tin moi nhat va hien thi trang thai da cap nhat.

#### Nhanh B. Tra cuu bang so dien thoai

- Hien tai day la luong demo.
- He thong hien popup OTP phone.
- Sau 5 giay, OTP duoc tu dong dien gia lap.
- He thong gia dinh OTP hop le va tiep tuc goi API huy don hang.
- Khi API huy thanh cong, frontend goi lai luong tra cuu de reload thong tin moi nhat va hien thi trang thai da cap nhat.

### 3. API huy don hang

- Neu nguoi dung dang dang nhap, backend dung luong `cancelCustomerOrder(...)`.
- Neu nguoi dung la guest lookup, backend dung luong `cancelLookupOrder(orderId, orderCode, contact)`.
- Backend doi chieu `order_id`, `order_code` va thong tin lien he voi customer cua don hang.
- Neu hop le, backend cap nhat:
  - `sales.sales_order.order_status = CANCELLED`
  - `sales.shipping.shipping_status = CANCELLED`

## Trang thai implementation hien tai

### Frontend

- Trang `Tra cuu don hang` da dung chung layout moi.
- Sau khi huy don thanh cong, trang lookup da tu dong tra cuu lai de reload trang thai moi.
- Popup OTP phone demo da co.
- Popup OTP email da duoc them, su dung Supabase Auth de:
  - gui OTP email
  - verify OTP email
  - chi huy don sau khi verify thanh cong

### Backend

- API `/api/v1/orders/[order_id]/cancel` da ho tro guest lookup.
- Backend chua can them bang moi hay doi schema.

## Luu y ky thuat

- Luong OTP email dang phu thuoc vao Supabase Auth va SMTP da cau hinh san.
- Luong OTP phone hien tai chi la demo UI/UX, chua ket noi nha cung cap SMS thuc te.
- Sau khi verify OTP email thanh cong, Supabase co the tao/xac nhan identity theo cau hinh Auth hien tai.

