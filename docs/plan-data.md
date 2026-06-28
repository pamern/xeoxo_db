Nên **cào theo batch**, không nên cào “một phát hết”, dù web ít sản phẩm. Vì batch dễ kiểm tra lỗi, dễ map vào database, dễ tránh duplicate.

Thứ tự plan tối ưu nên làm như này:

```txt
1. Xác định bảng chính cần có data
   - products
   - categories
   - product_images
   - blog / posts nếu có
   - collections / product_types nếu có
   - variants nếu sản phẩm có size, màu, loại
```

```txt
2. Xác định relation trước khi cào
   Ví dụ:
   categories 1 - n products
   products 1 - n product_images
   products n - n collections
   products 1 - n variants
```

```txt
3. Cào danh sách URL trước
   Không cào chi tiết ngay.

   Ví dụ lấy trước:
   - link sản phẩm
   - tên sản phẩm sơ bộ
   - category đang nằm ở đâu
```

```txt
4. Lưu danh sách URL vào file trung gian
   Ví dụ:
   scraped-product-urls.json
   hoặc scraped-product-urls.csv

   Mục đích:
   - tránh cào lại từ đầu
   - biết tổng số sản phẩm
   - dễ chia batch
```

```txt
5. Cào chi tiết sản phẩm theo batch
   Ví dụ mỗi batch 10–20 sản phẩm.

   Với mỗi sản phẩm lấy:
   - name
   - slug
   - price
   - description
   - shortDescription
   - category
   - images
   - material
   - dimensions
   - stock
   - tags
```

```txt
6. Chuẩn hoá data trước khi import DB
   Ví dụ:
   - chuyển tên category thành category_id
   - tạo slug chuẩn
   - format giá thành number
   - bỏ ký tự dư
   - ảnh gom thành mảng
```

```txt
7. Import bảng cha trước
   Thứ tự nên là:

   1. categories
   2. collections / product_types
   3. products
   4. product_images
   5. variants
   6. bảng trung gian nếu có many-to-many
```

```txt
8. Kiểm tra duplicate
   Dựa vào:
   - slug
   - source_url
   - product name

   Nên thêm field:
   source_url
   scraped_at
```

```txt
9. Upload hình
   Có 2 cách:

   Cách tốt nhất:
   - cào URL ảnh
   - tải ảnh về
   - upload lên Supabase Storage
   - lưu public URL vào product_images

   Không nên phụ thuộc ảnh gốc của web khác lâu dài.
```

```txt
10. Test hiển thị trên web
   Sau khi import 5–10 sản phẩm đầu tiên thì test giao diện trước.
   Đừng đợi import hết mới test.
```

Plan thực tế nên làm:

```txt
Batch 1: Cào 5 sản phẩm mẫu
→ kiểm tra data có đúng bảng/relation chưa
→ import vào Supabase
→ test UI

Batch 2: Cào 20 sản phẩm
→ kiểm tra duplicate, ảnh, category

Batch 3: Cào toàn bộ còn lại
→ import final
```

Kết luận:

```txt
Không nên cào hết ngay.

Nên làm:
1. Cào URL trước
2. Cào 5 sản phẩm mẫu
3. Map đúng database
4. Import thử
5. Cào batch còn lại
6. Upload ảnh lên Supabase Storage
7. Import hoàn chỉnh
```

Với web ít sản phẩm thì batch khoảng **10–20 sản phẩm/lần** là đẹp.
