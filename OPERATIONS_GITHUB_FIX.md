# Sửa tích hợp Vận hành theo repository GitHub của nhóm

Nguồn kiểm tra: https://github.com/danghuynhthaotrinh/sunbaby-spa-django
Nhánh gốc: main, commit b44b4bb9cd6f01be4b33a5971ee7a2417849502a.
Nhánh sửa cục bộ: fix/operations-integration. Chưa đẩy lên GitHub.

## Các nguyên nhân đã xác minh trong main

- inventory/urls.py và services/urls.py còn các dấu xung đột Git đã bị commit.
- config/urls.py vẫn include kho.urls dù app kho đã bị xóa; TheKho đã chuyển sang inventory.
- Model dịch vụ hiện là ServicePackage và BOMItem, khác bản tích hợp cũ.
- Main chưa có giao diện đồ vải, DocumentSequence hoặc common/business của gói trước.
- Vai trò hiện là ADMIN, QUAN_LY, THU_KHO, LE_TAN, KTV, khác MANAGER/STAFF của bản cũ.

## Nội dung sửa

- Giữ nguyên services/models.py, ServicePackage, BOMItem và ServiceOrder.service trỏ ServicePackage.
- Loại bỏ các dấu conflict URL, giữ đầy đủ route kho và các màn hình dịch vụ thực tế.
- Chuyển /kho/ sang /inventory/ thay vì import app đã xóa.
- Tích hợp đủ 3 tab UC_5: board, xuất giặt, nhận sạch/đối soát; tìm nhanh, thêm/xóa dòng, modal xem/nhận, nhận thiếu và nhận bổ sung.
- DocumentSequence nằm ở operations.models, bảng operations_document_sequences; không thêm nó vào inventory và không cần common.
- Quyền vận hành chấp nhận ADMIN/QUAN_LY/THU_KHO, giữ tương thích MANAGER cũ; superuser được truy cập. KTV/LE_TAN không được quản lý đồ vải.
- Dùng inventory.TheKho đúng vị trí hiện tại; nhận bổ sung chỉ ghi phần nhận tăng thêm.
- Đăng ký signal để khi phân hệ kho lưu Item.stock của đồ vải, tồn sạch đã theo dõi được đồng bộ. Không đoán lại các trạng thái bẩn/đang dùng/đang giặt. Các thao tác QuerySet.update/SQL thô không chạy signal.
- Migration operations/0002 mới chuyển mỗi phiếu giặt một SKU thành chi tiết trước khi bỏ các cột cũ. Giữ mã/SKU/SL; ngày thực nhận/hạn nhận chưa từng lưu vẫn để trống, đánh dấu is_legacy. Dữ liệu không hợp lệ hoặc tồn sạch/stock mâu thuẫn sẽ khiến migrate dừng để đối soát.
- Giữ nguyên toàn bộ migration gốc của repository. Migration mới forward-only vì phiếu nhiều SKU không thể hạ cấp tự động thành một SKU.
- Chuẩn hóa requirements.txt từ UTF-16 sang UTF-8, giữ nguyên các phiên bản thư viện.

## Cách dùng khuyến nghị: tạo thư mục mới

Chạy CAI_BAN_SUA.cmd trong gói bàn giao. Script sẽ:
1. Clone repo công khai vào %USERPROFILE%\PycharmProjects\sunbaby-spa-operations-fixed.
2. Tạo nhánh fix/operations-integration từ đúng commit gốc đã kiểm tra.
3. Áp dụng patch và stage thay đổi cục bộ; không commit/push thay bạn.
4. Tạo .venv bằng Python hiện có, cài requirements, check, migrate CSDL mới và chạy tests.

Script sẽ dừng nếu thư mục đích đã tồn tại, không ghi đè thư mục đó. Thư mục sunbaby-spa-django hiện tại và db.sqlite3 cũ của bạn không bị chạm tới. Không copy DB từ bản ZIP tích hợp cũ vào bản mới: hai bản có lịch sử migration khác nhau. Nếu cần giữ dữ liệu đó, cần đối chiếu và chuyển dữ liệu riêng.

Sau khi script hoàn tất, trong PowerShell:

```powershell
cd "$env:USERPROFILE\PycharmProjects\sunbaby-spa-operations-fixed"
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py seed_operations_demo
.\.venv\Scripts\python.exe manage.py runserver
```

Mở http://127.0.0.1:8000/operations/ và Ctrl+F5. Đăng nhập bằng tài khoản vừa tạo.
Lệnh DEMO là tùy chọn: tạo 3 SKU DEMO có tồn bẩn và một xưởng DEMO, không tạo mật khẩu hay ghi đè SKU thật.

## Áp dụng thủ công cho người quen Git

Dùng checkout sạch tại commit gốc (không reset/xóa code đang làm), sau đó:

```powershell
git switch -c fix/operations-integration b44b4bb9cd6f01be4b33a5971ee7a2417849502a
git apply --index "C:\duong-dan\sunbaby_operations_fix.patch"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py test
```

Nếu dùng một DB nhóm vốn tạo đúng từ main này, sao lưu trước migrate. Đối với thư mục có các sửa tay và migration cũ từ các gói ZIP trước, dùng bản clone mới ở trên để tránh ghép chồng hai cấu trúc.

## Đẩy để nhóm xem

Bản sửa được stage sau khi áp patch. Kiểm tra rồi commit/push:

```powershell
git diff --cached --stat
git commit -m "Fix operations integration with current group models"
git push -u origin fix/operations-integration
```

Cần quyền ghi/collaborator trong repo; lỗi 403 không giải quyết bằng sửa code. Không cần force push. Tạo PR từ nhánh này vào main và mô tả phụ thuộc vào commit gốc; nếu main tiếp tục thay đổi, cần kiểm tra/ghép với các thay đổi mới trước merge.

## Kiểm tra đã hoàn tất

- Django 6.1.2 trên Python 3.12, SQLite.
- manage.py check: không lỗi.
- manage.py test: 22 bài qua, gồm kiểm tra quyền theo vai trò mới, HTTP 3 tab, forms/CSRF, phiếu thiếu/bổ sung, kho và TheKho, ServicePackage/BOMItem, seed DEMO.
- makemigrations --check --dry-run: không thiếu migration.
- python qa/check_operations_upgrade.py: nâng dữ liệu phiếu cũ trong DB tạm, giữ mã/SKU/số lượng/tồn; không tự tạo ngày nhận chưa biết.
- Giao diện/JavaScript giữ từ gói trước đã kiểm tra DOM; chưa xác nhận rendering trên trình duyệt thật trong môi trường này. Mở trên máy bạn để thử đầy đủ luồng.

Phạm vi giao diện là UC_5 đồ vải. Không xây UI ca phục vụ, FEFO hoặc xử lý đền bù xưởng trong bản sửa này.
