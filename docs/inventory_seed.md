# XEOXO Inventory Seed

## Mục đích

Script `src/load/add_inventory.py` dùng để seed dữ liệu vào `inventory.inventory`
dựa trên dữ liệu đang có trong database:

- `catalog.collection`
- `catalog.product_line`
- `catalog.product_component`
- `catalog.product_variant`
- `iam.branch`

Script này phù hợp để:

- tạo nhanh dữ liệu tồn kho cho local Supabase
- seed dữ liệu tồn kho cho remote Supabase
- chạy lại nhiều lần mà không tạo trùng dữ liệu nhờ `upsert`

## Bảng bị ảnh hưởng

- Đọc:
  - `catalog.collection`
  - `catalog.product_line`
  - `catalog.product_component`
  - `catalog.product_variant`
  - `catalog.size_option`
  - `iam.branch`
- Ghi:
  - `inventory.inventory`

## Logic phân bổ inventory

Script phân bổ theo từng `collection`.

Trong mỗi collection, script gom variant theo `product_line`, sau đó gán trạng thái
inventory cho từng product line theo tỷ lệ gần đúng:

- Khoảng `30%` tổng dòng inventory thuộc nhóm `PARTIAL_OUT`
- Khoảng `60%` tổng dòng inventory thuộc nhóm `IN_STOCK`
- Khoảng `10%` tổng dòng inventory thuộc nhóm `FULL_OUT`

### Cách hiểu 3 trạng thái

- `IN_STOCK`
  - tất cả variant trong product line đều có `quantity > 0`
- `PARTIAL_OUT`
  - có ít nhất một variant có `quantity = 0`
  - đồng thời vẫn còn ít nhất một variant khác có `quantity > 0`
- `FULL_OUT`
  - toàn bộ variant trong product line có `quantity = 0`

### Quantity

- Variant còn hàng được random trong khoảng mặc định `1..30`
- Có thể đổi bằng `--min-quantity` và `--max-quantity`
- Script chỉ seed cho variant thực sự tồn tại trong `catalog.product_variant`

## Yêu cầu dữ liệu đầu vào

Trước khi chạy script, database cần có:

- dữ liệu `iam.branch`
- dữ liệu `catalog.collection`
- dữ liệu `catalog.product_line`
- dữ liệu `catalog.product_component`
- dữ liệu `catalog.product_variant`

Nếu chưa có branch active trong `iam.branch`, script sẽ dừng với lỗi rõ ràng.

Repo hiện đã có file seed mặc định [branch.csv](/home/ngocmypzg/Projects/xeoxo_db/data/master/branch.csv:1)
với branch `Xéo Xọ Store` để phục vụ local/demo.

## Biến môi trường

Script dùng chung cơ chế connection của project và đọc từ:

- `.env`
- hoặc `.env.local`

`.env.local` sẽ override giá trị trong `.env`.

### Kết nối local Supabase

Có thể dùng:

```env
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:15432/postgres
```

Hoặc chạy bằng cờ `--local`.

### Kết nối remote Supabase

Cần một trong hai cách:

```env
SUPABASE_DB_URL=postgresql://...
```

hoặc:

```env
SUPABASE_HOST=db.<project-ref>.supabase.co
SUPABASE_PORT=5432
SUPABASE_NAME=postgres
SUPABASE_USER=postgres.<project-ref>
SUPABASE_PASSWORD=...
SUPABASE_DB_SSLMODE=require
```

Lưu ý:

- Không hard-code service role key trong code
- Không expose secret ra frontend
- Script này dùng kết nối Postgres trực tiếp, không yêu cầu đưa key vào client-side

## Cách chạy

### Dry run local

```bash
uv run python src/load/add_inventory.py --local --dry-run
```

### Seed local Supabase

```bash
uv run python src/load/add_inventory.py --local
```

### Seed remote bằng `.env` hoặc `.env.local`

```bash
uv run python src/load/add_inventory.py
```

### Seed remote bằng database URL truyền trực tiếp

```bash
uv run python src/load/add_inventory.py --db-url "postgresql://user:password@host:5432/postgres?sslmode=require"
```

### Chỉ seed một vài branch

```bash
uv run python src/load/add_inventory.py --local --branch-id 1 --branch-id 2
```

Hoặc:

```bash
uv run python src/load/add_inventory.py --local --branch-id 1,2,3
```

### Chỉ seed một vài collection

```bash
uv run python src/load/add_inventory.py --local --collection-id 3 --collection-id 5
```

### Đổi seed random và range quantity

```bash
uv run python src/load/add_inventory.py --local --seed 42 --min-quantity 2 --max-quantity 20
```

## File output

Sau mỗi lần chạy, script export kế hoạch inventory ra file CSV mặc định:

```text
data/master/inventory.csv
```

CSV này giúp kiểm tra nhanh:

- branch nào được seed
- collection nào được seed
- `collection_slug` tương ứng nếu có trong `data/master/collections.csv`
- product line thuộc trạng thái nào
- `product_line_slug` nếu có cột `slug` trong `data/master/product_line.csv`
- variant nào có `quantity = 0`
- variant nào còn hàng

## Tính idempotent

Script dùng `ON CONFLICT (branch_id, variant_id) DO UPDATE`, nên:

- chạy lại không tạo duplicate row
- quantity sẽ được cập nhật lại theo seed hiện tại
- có thể dùng để refresh dữ liệu demo nhiều lần
