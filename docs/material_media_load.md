# Material Media Load

## Mục đích

Script `src/load/load_media_materials.py` dùng để:

- đọc danh sách material từ `data/master/material.csv`
- lấy ảnh local trong `data/media/material/`
- convert ảnh sang `webp`
- upload lên Supabase Storage
- sync metadata vào `catalog.media`
- cập nhật `catalog.material.media_id`

## Quy ước file ảnh

File master `data/master/material.csv` hỗ trợ cột:

- `media_filename`

Script sẽ ưu tiên dùng `media_filename`. Nếu cột này trống, script fallback theo slug:

- `materials/{material_slug}/swatch.webp`

Ví dụ storage key:

```text
materials/gam/swatch.webp
materials/organza/swatch.webp
materials/tencel/swatch.webp
```

## Cách chạy

### Chạy local

```bash
uv run python -m src.load.load_media_materials --local
```

### Chạy remote

```bash
uv run python -m src.load.load_media_materials
```

## Ghi chú

- Script cần Supabase Storage credentials trong `.env` hoặc `.env.local`
- Script cần material đã tồn tại trong `catalog.material`
- Sau khi chạy, report được ghi ra:

```text
data/master/material_media.csv
```
