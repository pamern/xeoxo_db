# XEOXO Web - Storage Access Control

## 1. Mục tiêu

Tài liệu này quy định cách lưu file trong Supabase Storage, cách tham chiếu file trong database và nguyên tắc phân quyền upload/read/update/delete.

Phạm vi áp dụng cho các file ảnh/video dùng trong catalog, review, chat, hồ sơ khách hàng và các file phát sinh từ backend.

---

## 2. Nguyên tắc lưu trữ

## Không lưu binary trong database

Database không lưu nội dung file dạng binary/base64.

Database chỉ lưu metadata cần thiết để truy vấn và hiển thị:

- `bucket_name`: Tên bucket trong Supabase Storage.
- `storage_key`: Đường dẫn object trong bucket.
- `alt_text`: Mô tả ảnh/video.
- `media_type`: Loại media nghiệp vụ, ví dụ `IMAGE`, `VIDEO`.
- `mime_type`: MIME type thật của file, ví dụ `image/webp`, `image/jpeg`, `video/mp4`.
- `file_size`: Dung lượng file tính theo byte.
- `created_at`, `updated_at`: Thời gian tạo/cập nhật metadata.

File thật nằm trong Supabase Storage. Bảng `catalog.media` là source of truth của metadata file dùng chung cho catalog.

## Không lưu public URL làm khóa chính

Không dùng public URL làm khóa định danh chính vì URL phụ thuộc project ref, bucket visibility và CDN config.

Quy ước:

- Dùng `storage_key` để định danh object trong bucket.
- Dùng `bucket_name + storage_key` để tạo URL khi cần hiển thị.
- Nếu import dữ liệu có `media_url`, chỉ dùng để suy ra `storage_key` hoặc audit nguồn, không đưa vào bảng nghiệp vụ chính.

Ví dụ:

```text
bucket_name: product-media
storage_key: product-lines/ao-mong-chi/main.webp
public URL:  https://<project-ref>.supabase.co/storage/v1/object/public/product-media/product-lines/ao-mong-chi/main.webp
```

---

## 3. Bucket đề xuất

## product-media

- Mục đích: Ảnh/video sản phẩm, bộ sưu tập, danh mục, chất liệu, màu sắc.
- Visibility: Public bucket.
- Read: `anon`, `authenticated`, `service_role`.
- Write: Chỉ backend/service role, migration hoặc script nội bộ.
- DB metadata: `catalog.media`.

**Ghi chú:**

- Frontend được đọc file public nhưng không được upload trực tiếp vào bucket này.
- Các bảng như `catalog.collection`, `catalog.category`, `catalog.color`, `catalog.material`, `catalog.product_line_media` chỉ tham chiếu `media_id`.

## review-media

- Mục đích: Ảnh/video đánh giá sản phẩm.
- Visibility: Private bucket nếu cần kiểm duyệt trước khi public.
- Read: Backend/service role; frontend đọc qua signed URL hoặc view/API đã kiểm duyệt.
- Write: `authenticated` được upload file của chính mình nếu có nghiệp vụ review.
- DB metadata: Nên dùng bảng liên kết `sales.review_media` tham chiếu `catalog.media` hoặc một bảng media riêng nếu cần tách quyền.

## chat-media

- Mục đích: File đính kèm trong chat.
- Visibility: Private bucket.
- Read/Write: Giới hạn theo conversation owner hoặc backend/support.
- DB metadata: `support.chat_message_media` tham chiếu media.

## customer-private

- Mục đích: File cá nhân nhạy cảm nếu phát sinh, ví dụ tài liệu đo may, ảnh fitting riêng.
- Visibility: Private bucket.
- Read/Write: Chỉ chủ sở hữu và backend/service role.
- DB metadata: Bảng nghiệp vụ tương ứng trong `customization` hoặc `iam`, không expose public.

---

## 4. Quy ước đặt storage_key

## Quy tắc chung

- Dùng chữ thường, không dấu, slug ổn định.
- Dùng `/` để chia thư mục logic.
- Không đưa email, số điện thoại, tên thật hoặc thông tin nhạy cảm vào path.
- Tên file nên có vai trò hoặc thứ tự rõ ràng: `main.webp`, `gallery-01.webp`, `cover.webp`.
- Không dùng query string trong `storage_key`.

## Catalog

```text
product-lines/{product_line_slug}/main.webp
product-lines/{product_line_slug}/gallery-01.webp
product-lines/{product_line_slug}/gallery-02.webp
collections/{collection_slug}/cover.webp
categories/{category_slug}/cover.webp
materials/{material_slug}/swatch.webp
colors/{color_slug}/swatch.webp
```

## User-owned files

```text
reviews/{customer_id}/{review_id}/{uuid}.webp
chat/{conversation_id}/{message_id}/{uuid}.webp
customers/{customer_id}/measurements/{uuid}.webp
```

**Ghi chú:**

- Với file user-owned, nếu path chứa `customer_id`, policy phải kiểm tra quyền sở hữu bằng bảng nghiệp vụ, không chỉ tin vào path.
- Với guest session, dùng `guest_session_id` dạng UUID thay vì thông tin cá nhân.

---

## 5. Quy ước database

## Bảng catalog.media

```sql
CREATE TABLE catalog.media (
    media_id BIGSERIAL PRIMARY KEY,
    storage_key TEXT NOT NULL UNIQUE,
    alt_text VARCHAR(255),
    media_type VARCHAR(20) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,
    bucket_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT chk_media_type
        CHECK (media_type IN ('IMAGE', 'VIDEO'))
);
```

## Insert metadata sau khi upload

```sql
INSERT INTO catalog.media (
    storage_key,
    alt_text,
    media_type,
    mime_type,
    file_size,
    bucket_name
)
VALUES (
    'product-lines/ao-mong-chi/main.webp',
    'Áo Mộng Chi - ảnh chính',
    'IMAGE',
    'image/webp',
    283160,
    'product-media'
)
ON CONFLICT (storage_key)
DO UPDATE SET
    alt_text = EXCLUDED.alt_text,
    media_type = EXCLUDED.media_type,
    mime_type = EXCLUDED.mime_type,
    file_size = EXCLUDED.file_size,
    bucket_name = EXCLUDED.bucket_name,
    updated_at = NOW();
```

## Query URL public cho product-media

```sql
SELECT
    media_id,
    bucket_name,
    storage_key,
    'https://<project-ref>.supabase.co/storage/v1/object/public/'
        || bucket_name || '/' || storage_key AS public_url
FROM catalog.media
WHERE bucket_name = 'product-media';
```

Trong application, ưu tiên dùng client SDK để tạo public URL thay vì hardcode project ref.

---

## 6. Quyền truy cập theo role

| Bucket | anon | authenticated | service_role |
|---|---|---|---|
| product-media | READ | READ | ALL |
| review-media | Không trực tiếp hoặc READ file đã duyệt | INSERT file của chính mình; READ file được phép | ALL |
| chat-media | Theo guest_session_id nếu hỗ trợ | READ/INSERT file trong conversation của chính mình | ALL |
| customer-private | Không truy cập | READ/INSERT file của chính mình nếu có nghiệp vụ | ALL |

**Ghi chú:**

- `service_role` bypass RLS, chỉ dùng trong backend/script nội bộ.
- Không đưa service key lên frontend.
- Các thao tác xóa/ghi đè file nên đi qua backend để đồng bộ Storage object và DB metadata.

---

## 7. Cú pháp Supabase Storage policy

Supabase Storage dùng RLS trên bảng `storage.objects`.

Theo mặc định, Storage không cho upload vào bucket nếu chưa có policy phù hợp. Muốn cho phép thao tác nào thì tạo policy cho thao tác đó trên `storage.objects`.

## Public read cho public bucket

Với public bucket như `product-media`, Supabase public bucket đã cho phép đọc object public. Không cần tạo policy đọc riêng chỉ để hiển thị ảnh public.

Frontend lấy URL:

```ts
const { data } = supabase
  .storage
  .from('product-media')
  .getPublicUrl('product-lines/ao-mong-chi/main.webp')

console.log(data.publicUrl)
```

## Chặn frontend upload vào product-media

Không tạo policy `INSERT`, `UPDATE`, `DELETE` cho `anon` hoặc `authenticated` trên bucket `product-media`.

Backend/script dùng service key để upload:

```ts
await supabase
  .storage
  .from('product-media')
  .upload('product-lines/ao-mong-chi/main.webp', file, {
    contentType: 'image/webp',
    upsert: false
  })
```

## Authenticated upload vào folder riêng

Ví dụ cho bucket private `review-media`, người dùng đăng nhập chỉ được upload vào folder theo `auth.uid()`.

```sql
CREATE POLICY "review media: authenticated upload own folder"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'review-media'
    AND (storage.foldername(name))[1] = (SELECT auth.uid()::text)
    AND storage.extension(name) IN ('jpg', 'jpeg', 'png', 'webp', 'mp4')
);
```

Path tương ứng:

```text
{auth.uid()}/{review_id}/{uuid}.webp
```

## Authenticated read own folder

```sql
CREATE POLICY "review media: authenticated read own folder"
ON storage.objects
FOR SELECT
TO authenticated
USING (
    bucket_id = 'review-media'
    AND (storage.foldername(name))[1] = (SELECT auth.uid()::text)
);
```

## Authenticated update own object

Chỉ dùng nếu cho phép overwrite. Nếu không cần overwrite, không tạo policy này.

```sql
CREATE POLICY "review media: authenticated update own object"
ON storage.objects
FOR UPDATE
TO authenticated
USING (
    bucket_id = 'review-media'
    AND owner_id = (SELECT auth.uid()::text)
)
WITH CHECK (
    bucket_id = 'review-media'
    AND owner_id = (SELECT auth.uid()::text)
);
```

## Authenticated delete own object

Chỉ dùng nếu người dùng được tự xóa file trước khi gửi/duyệt.

```sql
CREATE POLICY "review media: authenticated delete own object"
ON storage.objects
FOR DELETE
TO authenticated
USING (
    bucket_id = 'review-media'
    AND owner_id = (SELECT auth.uid()::text)
);
```

## Signed URL cho private bucket

Với private bucket, frontend không tự ghép public URL. Backend hoặc client có quyền phù hợp tạo signed URL:

```ts
const { data, error } = await supabase
  .storage
  .from('review-media')
  .createSignedUrl('user-id/review-id/image.webp', 60 * 10)
```

---

## 8. Cú pháp tạo bucket

Ưu tiên tạo bucket bằng Supabase Dashboard hoặc migration được kiểm soát.

Ví dụ bằng Supabase JS:

```ts
await supabase.storage.createBucket('product-media', {
  public: true,
  allowedMimeTypes: ['image/*', 'video/mp4'],
  fileSizeLimit: '10MB'
})
```

Ví dụ SQL trong migration nếu cần quản lý bucket bằng database:

```sql
INSERT INTO storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
VALUES (
    'product-media',
    'product-media',
    TRUE,
    10485760,
    ARRAY['image/jpeg', 'image/png', 'image/webp', 'video/mp4']
)
ON CONFLICT (id)
DO UPDATE SET
    public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;
```

---

## 9. Quy trình upload chuẩn

## Catalog media

1. Backend/script chuẩn hóa file về định dạng mong muốn, ưu tiên `webp` cho ảnh catalog.
2. Upload file vào `product-media`.
3. Ghi metadata vào `catalog.media`.
4. Gắn `media_id` vào bảng nghiệp vụ như `catalog.product_line_media`, `catalog.collection`, `catalog.category`.
5. Frontend đọc metadata và tạo public URL từ `bucket_name + storage_key`.

## User media

1. Frontend xin quyền upload hoặc nhận signed upload URL từ backend.
2. Upload file vào private bucket đúng folder owner/session.
3. Backend ghi metadata và gắn vào bảng nghiệp vụ.
4. File chỉ được public sau khi nghiệp vụ cho phép, ví dụ review đã duyệt.

---

## 10. Checklist khi thêm loại file mới

- Xác định file public hay private.
- Chọn bucket phù hợp hoặc tạo bucket mới.
- Xác định bảng metadata và bảng liên kết nghiệp vụ.
- Thiết kế `storage_key` không chứa thông tin nhạy cảm.
- Tạo policy tối thiểu trên `storage.objects`.
- Quy định MIME type và file size limit.
- Quy định ai được xóa file và khi xóa có xóa metadata không.
- Kiểm tra frontend không dùng service key.

---
